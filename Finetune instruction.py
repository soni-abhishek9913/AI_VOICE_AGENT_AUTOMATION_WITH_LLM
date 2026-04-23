#finetune_instruction.py
import torch
import os
import json
import numpy as np
from tqdm import tqdm
import tiktoken

from config import default_config as config
from transformer import Transformer

FT_CONFIG = {
    "base_model_path": "models/transformer_bilingual.pt",
    "out_path":        "models/transformer_v4_instruction.pt",   # v4 -- new categories + 100K dataset

    # Lower LR -- we are fine-tuning, not training from scratch
    "lr":              1e-5,
    "lr_decay_step":   40_000,
    "lr_decayed":      2e-6,

    "batch_size":      8,
    "grad_accum":      4,        # effective batch = 32
    "train_steps":     70_000,   # more steps for 100K dataset
    "eval_steps":      1_000,
    "patience":        6,
    "max_seq_len":     128,      # instruction examples are shorter
    "device":          "cuda" if torch.cuda.is_available() else "cpu",
    "use_amp":         True,
}

DATASET_PATH = "instruction_dataset_v4.jsonl"

enc = tiktoken.get_encoding("r50k_base")

# Special tokens -- same as used in bilingual training
U = "<|user|>"
A = "<|assistant|>"
E = "<|endoftext|>"

ALLOWED = {U, A, E}


def tokenize(text: str) -> list:
    return enc.encode(text, allowed_special=ALLOWED)



def build_dataset():
    """
    Returns list of (input_tokens, response_start_idx) tuples.
    response_start_idx = index where assistant reply starts.
    Loss is computed only from response_start_idx onwards.
    """
    sequences = []
    print("Loading instruction dataset...")

    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in tqdm(f):
            line = line.strip()
            if not line:
                continue

            row = json.loads(line)
            msgs = row["messages"]

            # Build full text: <|user|> prompt <|assistant|> response <|endoftext|>
            user_text      = msgs[0]["content"]   # "REPHRASE_HINT: ..."
            assistant_text = msgs[1]["content"]   # the natural variation

            user_tokens      = tokenize(f"{U} {user_text} ")
            assistant_tokens = tokenize(f"{A} {assistant_text} ")
            end_tokens       = tokenize(E)

            full_tokens        = user_tokens + assistant_tokens + end_tokens
            response_start_idx = len(user_tokens)  # where assistant starts

            if len(full_tokens) < 5:
                continue
            if len(full_tokens) > FT_CONFIG["max_seq_len"] + 1:
                # Truncate from the left (keep response intact)
                full_tokens        = full_tokens[-(FT_CONFIG["max_seq_len"] + 1):]
                response_start_idx = max(0, response_start_idx - len(user_tokens))

            sequences.append((full_tokens, response_start_idx))

    print(f"Total sequences: {len(sequences):,}")
    return sequences


def get_batch(sequences, batch_size, seq_len, device):
    """
    Returns (x, y, loss_mask) where:
      x         = input token ids  [batch, seq_len]
      y         = target token ids [batch, seq_len]
      loss_mask = 1.0 where loss should be computed (response only)
                  0.0 for prompt tokens
    """
    xs, ys, masks = [], [], []
    indices = np.random.choice(len(sequences), batch_size)

    for idx in indices:
        tokens, resp_start = sequences[idx]

        if len(tokens) <= seq_len:
            start = 0
        else:
            start = np.random.randint(0, len(tokens) - seq_len)

        chunk = tokens[start : start + seq_len + 1]

        # Pad if needed
        if len(chunk) < seq_len + 1:
            chunk = chunk + [enc.eot_token] * (seq_len + 1 - len(chunk))

        xs.append(chunk[:seq_len])
        ys.append(chunk[1 : seq_len + 1])

        # Loss mask: 1.0 for response tokens, 0.0 for prompt tokens
        mask = []
        for pos in range(seq_len):
            actual_pos = start + pos
            # Only compute loss on response tokens
            mask.append(1.0 if actual_pos >= resp_start else 0.0)
        masks.append(mask)

    x    = torch.tensor(xs,    dtype=torch.long,  device=device)
    y    = torch.tensor(ys,    dtype=torch.long,  device=device)
    mask = torch.tensor(masks, dtype=torch.float, device=device)
    return x, y, mask




print(f"\nLoading base model from {FT_CONFIG['base_model_path']}...")
ckpt = torch.load(
    FT_CONFIG["base_model_path"],
    map_location = FT_CONFIG["device"],
    weights_only = False,
)

model = Transformer(
    n_head         = config["n_head"],
    n_embed        = config["n_embed"],
    context_length = config["context_length"],
    vocab_size     = config["vocab_size"],
    N_BLOCKS       = config["n_blocks"],
    dropout        = 0.05,   # lower dropout for fine-tuning
).to(FT_CONFIG["device"])

model.load_state_dict(ckpt["model_state_dict"])
print(f"Base model loaded -- train {ckpt['train_loss']:.4f} | dev {ckpt['dev_loss']:.4f}")
total = sum(p.numel() for p in model.parameters())
print(f"Parameters: {total:,}  (~{total/1e6:.1f}M)\n")


import random  # ALWAYS at top

sequences = build_dataset()

random.shuffle(sequences)

split      = int(len(sequences) * 0.95)
train_seqs = sequences[:split]
dev_seqs   = sequences[split:]

print(f"Train: {len(train_seqs):,}  |  Dev: {len(dev_seqs):,}\n")




optimizer = torch.optim.AdamW(
    model.parameters(),
    lr           = FT_CONFIG["lr"],
    betas        = (0.9, 0.95),
    weight_decay = 0.01,   # lower weight decay for fine-tuning
)
scaler     = torch.amp.GradScaler("cuda", enabled=FT_CONFIG["use_amp"])
GRAD_ACCUM = FT_CONFIG["grad_accum"]
losses     = []



@torch.no_grad()
def estimate_loss(steps: int = 100) -> dict:
    out = {}
    model.eval()
    for name, seqs in [("train", train_seqs), ("dev", dev_seqs)]:
        vals = []
        for _ in range(steps):
            x, y, mask = get_batch(
                seqs, FT_CONFIG["batch_size"],
                FT_CONFIG["max_seq_len"], FT_CONFIG["device"],
            )
            with torch.amp.autocast("cuda", dtype=torch.float16,
                                    enabled=FT_CONFIG["use_amp"]):
                logits, _ = model(x)
                # Response-only loss
                B, T, V = logits.shape
                logits_flat = logits.reshape(B * T, V)
                y_flat      = y.reshape(B * T)
                mask_flat   = mask.reshape(B * T)

                loss_all = torch.nn.functional.cross_entropy(
                    logits_flat, y_flat, reduction="none"
                )
                # Apply mask: only response tokens contribute
                loss = (loss_all * mask_flat).sum() / (mask_flat.sum() + 1e-8)

            vals.append(loss.item())
        out[name] = float(np.mean(vals))
    model.train()
    return out




print(f"Fine-tuning for up to {FT_CONFIG['train_steps']:,} steps...")
print(f"Strategy: RESPONSE-ONLY LOSS (only trains on assistant reply tokens)")
print(f"Batch: {FT_CONFIG['batch_size']}  |  Grad accum: {GRAD_ACCUM}  |  "
      f"Effective batch: {FT_CONFIG['batch_size'] * GRAD_ACCUM}")
print(f"LR: {FT_CONFIG['lr']:.1e}  ->  {FT_CONFIG['lr_decayed']:.1e} at step {FT_CONFIG['lr_decay_step']:,}")
print(f"Early stop patience: {FT_CONFIG['patience']} evals\n")

os.makedirs("models", exist_ok=True)
model.train()
optimizer.zero_grad()

best_dev_loss  = float("inf")
patience_count = 0
lr_decayed     = False

pbar = tqdm(range(FT_CONFIG["train_steps"]), dynamic_ncols=True)

for step in pbar:

    # -- Forward ------------------------------------------------------------
    x, y, mask = get_batch(
        train_seqs, FT_CONFIG["batch_size"],
        FT_CONFIG["max_seq_len"], FT_CONFIG["device"],
    )

    with torch.amp.autocast("cuda", dtype=torch.float16,
                            enabled=FT_CONFIG["use_amp"]):
        logits, _ = model(x)

        # Response-only loss -- THE KEY CHANGE
        B, T, V     = logits.shape
        logits_flat = logits.reshape(B * T, V)
        y_flat      = y.reshape(B * T)
        mask_flat   = mask.reshape(B * T)

        loss_all = torch.nn.functional.cross_entropy(
            logits_flat, y_flat, reduction="none"
        )
        loss = (loss_all * mask_flat).sum() / (mask_flat.sum() + 1e-8)
        loss = loss / GRAD_ACCUM

    scaler.scale(loss).backward()

    if (step + 1) % GRAD_ACCUM == 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

    losses.append(loss.item() * GRAD_ACCUM)
    pbar.set_description(
        f"loss {np.mean(losses[-100:]):.4f}  |  "
        f"best_dev {best_dev_loss:.4f}  |  "
        f"VRAM {torch.cuda.memory_allocated() / 1e9:.1f}GB"
    )

    # -- LR decay -----------------------------------------------------------
    if step == FT_CONFIG["lr_decay_step"] and not lr_decayed:
        for g in optimizer.param_groups:
            g["lr"] = FT_CONFIG["lr_decayed"]
        lr_decayed = True
        print(f"\n  LR decay -> {FT_CONFIG['lr_decayed']:.1e}  (step {step:,})")

    # -- Eval + early stopping ----------------------------------------------
    if step > 0 and step % FT_CONFIG["eval_steps"] == 0:
        ev = estimate_loss()
        print(f"\n  Step {step:>6}  |  "
              f"train {ev['train']:.4f}  |  "
              f"dev {ev['dev']:.4f}  |  "
              f"best {best_dev_loss:.4f}")

        if ev["dev"] < best_dev_loss:
            best_dev_loss  = ev["dev"]
            patience_count = 0
            torch.save({
                "model_state_dict":     model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "config":               config,
                "ft_config":            FT_CONFIG,
                "train_loss":           ev["train"],
                "dev_loss":             ev["dev"],
                "step":                 step,
                "losses":               losses,
                "training_type":        "instruction_finetuned_v4",
            }, FT_CONFIG["out_path"])
            print(f"  [OK] Best model saved (dev loss: {best_dev_loss:.4f})")
        else:
            patience_count += 1
            print(f"  No improvement ({patience_count}/{FT_CONFIG['patience']})")
            if patience_count >= FT_CONFIG["patience"]:
                print(f"\n  Early stopping at step {step:,}")
                break



print("\n" + "=" * 55)
print("Instruction fine-tuning v4 complete!")
print(f"  Steps run     : {len(losses):,}")
print(f"  Best dev loss : {best_dev_loss:.4f}")
print(f"  Model saved   : {FT_CONFIG['out_path']}")
print("=" * 55)

