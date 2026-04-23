"""
finetune_bilingual.py
Fine-tunes the base transformer on bilingual (English + Hindi) hospital data.
Features:
  - 50,000 training steps
  - Learning rate decay at step 35,000
  - Early stopping with patience=5
  - Always saves the best model (lowest dev loss)
Run AFTER generate_bilingual_dataset.py
"""

import torch
import os
import json
import numpy as np
from tqdm import tqdm
import tiktoken

from config import default_config as config
from transformer import Transformer

FT_CONFIG = {
    "base_model_path": "models/transformer_rtx4060.pt",
    "out_path":        "models/transformer_bilingual.pt",
    "lr":              3e-5,
    "lr_decay_step":   35_000,   # start decaying LR at 70% of training
    "lr_decayed":      5e-6,     # decay to this — careful fine-tuning at end
    "batch_size":      8,
    "grad_accum":      4,        # effective batch = 32
    "train_steps":     50_000,   # increased from 20,000
    "eval_steps":      1_000,    # evaluate every 1000 steps
    "patience":        5,        # early stop if dev loss doesn't improve for 5 evals
    "max_seq_len":     256,
    "device":          "cuda" if torch.cuda.is_available() else "cpu",
    "use_amp":         True,
}

DATASET_PATH = "bilingual_hospital_dataset.jsonl"

enc = tiktoken.get_encoding("r50k_base")

U = "<|user|>"
A = "<|assistant|>"
E = "<|endoftext|>"


def tokenize(text):
    return enc.encode(text, allowed_special={"<|endoftext|>"})


def build_dataset():
    sequences = []
    print("Loading bilingual dataset...")
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in tqdm(f):
            line = line.strip()
            if not line:
                continue
            row  = json.loads(line)
            text = ""
            for msg in row["messages"]:
                if msg["role"] == "user":
                    text += f"{U} {msg['content']} "
                elif msg["role"] == "assistant":
                    text += f"{A} {msg['content']} "
            text += E
            tokens = tokenize(text)
            if len(tokens) >= 10:
                sequences.append(tokens)
    print(f"Total sequences: {len(sequences):,}")
    return sequences


def get_batch(sequences, batch_size, seq_len, device):
    xs, ys  = [], []
    indices = np.random.choice(len(sequences), batch_size)
    for idx in indices:
        tokens = sequences[idx]
        if len(tokens) <= seq_len:
            start = 0
        else:
            start = np.random.randint(0, len(tokens) - seq_len)
        chunk = tokens[start : start + seq_len + 1]
        if len(chunk) < seq_len + 1:
            chunk += [enc.eot_token] * (seq_len + 1 - len(chunk))
        xs.append(chunk[:seq_len])
        ys.append(chunk[1 : seq_len + 1])
    x = torch.tensor(xs, dtype=torch.long, device=device)
    y = torch.tensor(ys, dtype=torch.long, device=device)
    return x, y


# ── Load base model ────────────────────────────────────────────────────────
print(f"Loading base model from {FT_CONFIG['base_model_path']}...")
ckpt = torch.load(
    FT_CONFIG["base_model_path"],
    map_location=FT_CONFIG["device"],
    weights_only=False,
)

model = Transformer(
    n_head         = config["n_head"],
    n_embed        = config["n_embed"],
    context_length = config["context_length"],
    vocab_size     = config["vocab_size"],
    N_BLOCKS       = config["n_blocks"],
    dropout        = 0.1,
).to(FT_CONFIG["device"])

model.load_state_dict(ckpt["model_state_dict"])
print(f"Base model loaded — train {ckpt['train_loss']:.4f} | dev {ckpt['dev_loss']:.4f}")
total = sum(p.numel() for p in model.parameters())
print(f"Parameters: {total:,}  (~{total/1e6:.1f}M)\n")

# ── Dataset ────────────────────────────────────────────────────────────────
sequences  = build_dataset()
np.random.shuffle(sequences)
split      = int(len(sequences) * 0.95)
train_seqs = sequences[:split]
dev_seqs   = sequences[split:]
print(f"Train: {len(train_seqs):,}  |  Dev: {len(dev_seqs):,}\n")

# ── Optimizer + scaler ─────────────────────────────────────────────────────
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr           = FT_CONFIG["lr"],
    betas        = (0.9, 0.95),
    weight_decay = 0.1,
)
scaler     = torch.amp.GradScaler("cuda", enabled=FT_CONFIG["use_amp"])
GRAD_ACCUM = FT_CONFIG["grad_accum"]
losses     = []


# ── Eval helper ────────────────────────────────────────────────────────────
@torch.no_grad()
def estimate_loss(steps=100):
    out = {}
    model.eval()
    for name, seqs in [("train", train_seqs), ("dev", dev_seqs)]:
        vals = []
        for _ in range(steps):
            x, y = get_batch(
                seqs, FT_CONFIG["batch_size"],
                FT_CONFIG["max_seq_len"], FT_CONFIG["device"],
            )
            with torch.amp.autocast("cuda", dtype=torch.float16,
                                    enabled=FT_CONFIG["use_amp"]):
                _, loss = model(x, y)
            vals.append(loss.item())
        out[name] = float(np.mean(vals))
    model.train()
    return out


# ── Training ───────────────────────────────────────────────────────────────
print(f"Fine-tuning for up to {FT_CONFIG['train_steps']:,} steps...")
print(f"Batch: {FT_CONFIG['batch_size']}  |  "
      f"Grad accum: {GRAD_ACCUM}  |  "
      f"Effective batch: {FT_CONFIG['batch_size'] * GRAD_ACCUM}")
print(f"LR: {FT_CONFIG['lr']:.2e}  ->  "
      f"decays to {FT_CONFIG['lr_decayed']:.2e} at step {FT_CONFIG['lr_decay_step']:,}")
print(f"Early stopping patience: {FT_CONFIG['patience']} evals\n")

os.makedirs("models", exist_ok=True)

model.train()
optimizer.zero_grad()

best_dev_loss  = float("inf")
patience_count = 0
lr_decayed     = False

pbar = tqdm(range(FT_CONFIG["train_steps"]), dynamic_ncols=True)

for step in pbar:

    # ── Forward + backward ─────────────────────────────────────────────────
    x, y = get_batch(
        train_seqs, FT_CONFIG["batch_size"],
        FT_CONFIG["max_seq_len"], FT_CONFIG["device"],
    )

    with torch.amp.autocast("cuda", dtype=torch.float16,
                            enabled=FT_CONFIG["use_amp"]):
        _, loss = model(x, y)
        loss    = loss / GRAD_ACCUM

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

    # ── LR decay ───────────────────────────────────────────────────────────
    if step == FT_CONFIG["lr_decay_step"] and not lr_decayed:
        for g in optimizer.param_groups:
            g["lr"] = FT_CONFIG["lr_decayed"]
        lr_decayed = True
        print(f"\n  LR decay -> {FT_CONFIG['lr_decayed']:.2e}  (step {step:,})")

    # ── Periodic eval + early stopping ────────────────────────────────────
    if step > 0 and step % FT_CONFIG["eval_steps"] == 0:
        ev = estimate_loss()
        print(f"\n  Step {step:>6}  |  "
              f"train {ev['train']:.4f}  |  "
              f"dev {ev['dev']:.4f}  |  "
              f"best_dev {best_dev_loss:.4f}")

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
                "language":             "bilingual",
            }, FT_CONFIG["out_path"])
            print(f"  ✓ New best model saved  (dev loss: {best_dev_loss:.4f})")
        else:
            patience_count += 1
            print(f"  No improvement  "
                  f"({patience_count}/{FT_CONFIG['patience']})")
            if patience_count >= FT_CONFIG["patience"]:
                print(f"\n  Early stopping at step {step:,} — "
                      f"dev loss not improving.")
                print(f"  Best dev loss achieved: {best_dev_loss:.4f}")
                break

# ── Final summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print("Fine-tuning complete!")
print(f"  Steps run       : {len(losses):,}")
print(f"  Best dev loss   : {best_dev_loss:.4f}")
print(f"  Final train loss: {np.mean(losses[-200:]):.4f}")
print(f"  Model saved to  : {FT_CONFIG['out_path']}")
print("=" * 50)
print("\nNext step: run voice_server.py")