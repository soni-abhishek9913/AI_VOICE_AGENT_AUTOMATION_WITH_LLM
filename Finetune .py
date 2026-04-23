import torch
import os
import numpy as np
from tqdm import tqdm
from datasets import load_dataset
from typing import Dict, List

from config import default_config as config
from transformer import Transformer

# ── GPU check ─────────────────────────────────────────────────────────────
assert torch.cuda.is_available(), "CUDA not found."
print(f"GPU : {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

# ── Fine-tune config ───────────────────────────────────────────────────────
FT_CONFIG = {
    'base_model_path'  : 'models/transformer_rtx4060.pt',
    'out_path'         : 'models/transformer_finetuned.pt',
    'lr'               : 1e-4,
    'lr_decayed'       : 1e-5,
    'lr_decay_step'    : 15_000,
    'train_steps'      : 20_000,
    'eval_steps'       : 500,
    'eval_iters'       : 50,
    'batch_size'       : 8,
    'grad_accum'       : 4,          # Effective batch = 32
    'max_seq_len'      : 256,        # Match your context length
    'device'           : 'cuda',
    'use_amp'          : True,
}

# ── Tokenizer ──────────────────────────────────────────────────────────────
import tiktoken
enc = tiktoken.get_encoding("r50k_base")

# Conversation format tokens
USER_TOKEN      = "<|user|>"
ASSISTANT_TOKEN = "<|assistant|>"
END_TOKEN       = "<|endoftext|>"


def format_conversation(messages: List[Dict]) -> str:
    """
    Format OpenAssistant conversation into training text.
    Only uses prompter (user) and assistant turns.
    Format: <|user|> message <|assistant|> response <|endoftext|>
    """
    text     = ""
    role_map = {
        "prompter"  : USER_TOKEN,
        "assistant" : ASSISTANT_TOKEN,
    }
    for msg in messages:
        role    = role_map.get(msg.get("role", ""), None)
        content = msg.get("text", "").strip()
        if role is None or not content:
            continue
        text += f"{role} {content} "
    text += END_TOKEN
    return text


def build_finetune_dataset(max_samples: int = 10_000) -> List[List[int]]:
    """
    Download and tokenize OpenAssistant dataset into token sequences.
    Returns list of token id lists.
    """
    print("Loading OpenAssistant dataset...")
    ds = load_dataset("OpenAssistant/oasst1", split="train")

    # Build conversation chains from message tree
    print("Building conversation chains...")
    ds_list = list(ds)

    def get_chain(root) -> List[Dict]:
        """Follow the highest-ranked reply chain from root."""
        chain      = [root]
        current_id = root["message_id"]
        while True:
            children = [
                row for row in ds_list
                if row["parent_id"] == current_id
            ]
            if not children:
                break
            best = max(children, key=lambda x: x.get("rank", 0) or 0)
            chain.append(best)
            current_id = best["message_id"]
        return chain

    root_messages = [row for row in ds_list if row["parent_id"] is None]

    # Tokenize conversations
    tokenized = []
    print(f"Tokenizing up to {max_samples} conversations...")

    for root in tqdm(root_messages[:max_samples]):
        try:
            chain  = get_chain(root)
            text   = format_conversation(chain)
            if len(text.strip()) < 20:
                continue
            tokens = enc.encode(text, allowed_special={"<|endoftext|>"})
            if len(tokens) < 10:
                continue
            tokenized.append(tokens)
        except Exception:
            continue

    print(f"Built {len(tokenized):,} conversation sequences")
    return tokenized


def get_finetune_batch(sequences  : List[List[int]],
                       batch_size : int,
                       seq_len    : int,
                       device     : str):
    """Sample a batch of (x, y) pairs from tokenized sequences."""
    xs, ys  = [], []
    indices = np.random.choice(len(sequences), batch_size, replace=True)

    for idx in indices:
        tokens = sequences[idx]
        if len(tokens) < 2:
            continue
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

    if not xs:
        return None, None

    x = torch.tensor(xs, dtype=torch.long, device=device)
    y = torch.tensor(ys, dtype=torch.long, device=device)
    return x, y


# ── Load base model ────────────────────────────────────────────────────────
print(f"\nLoading base model from {FT_CONFIG['base_model_path']}...")
ckpt = torch.load(FT_CONFIG['base_model_path'],
                  map_location=FT_CONFIG['device'])

model = Transformer(
    n_head         = config['n_head'],
    n_embed        = config['n_embed'],
    context_length = config['context_length'],
    vocab_size     = config['vocab_size'],
    N_BLOCKS       = config['n_blocks'],
    dropout        = 0.1,
).to(FT_CONFIG['device'])

model.load_state_dict(ckpt['model_state_dict'])
print(f"Base model loaded — train {ckpt['train_loss']:.4f}  "
      f"|  dev {ckpt['dev_loss']:.4f}")
total = sum(p.numel() for p in model.parameters())
print(f"Parameters: {total:,}  (~{total/1e6:.1f}M)\n")

# ── Dataset ────────────────────────────────────────────────────────────────
sequences  = build_finetune_dataset(max_samples=10_000)
split      = int(len(sequences) * 0.95)
train_seqs = sequences[:split]
dev_seqs   = sequences[split:]
print(f"Train: {len(train_seqs):,}  |  Dev: {len(dev_seqs):,}\n")

# ── Optimizer ──────────────────────────────────────────────────────────────
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr           = FT_CONFIG['lr'],
    betas        = (0.9, 0.95),
    weight_decay = 0.1,
    fused        = True,
)
scaler     = torch.amp.GradScaler('cuda', enabled=FT_CONFIG['use_amp'])
GRAD_ACCUM = FT_CONFIG['grad_accum']
losses     = []
AVG_WINDOW = 50


# ── Eval ───────────────────────────────────────────────────────────────────
@torch.no_grad()
def estimate_loss(steps: int) -> Dict[str, float]:
    out = {}
    model.eval()
    for split_name, seqs in [('train', train_seqs), ('dev', dev_seqs)]:
        vals = torch.zeros(steps)
        for k in range(steps):
            x, y = get_finetune_batch(
                seqs, FT_CONFIG['batch_size'],
                FT_CONFIG['max_seq_len'], FT_CONFIG['device']
            )
            if x is None:
                break
            with torch.amp.autocast('cuda', dtype=torch.float16,
                                    enabled=FT_CONFIG['use_amp']):
                _, loss = model(x, y)
            vals[k] = loss.item()
        out[split_name] = vals[:k + 1].mean().item()
    model.train()
    return out


# ── Fine-tuning loop ───────────────────────────────────────────────────────
print(f"Fine-tuning for {FT_CONFIG['train_steps']:,} steps")
print(f"Batch: {FT_CONFIG['batch_size']}  |  Grad accum: {GRAD_ACCUM}  "
      f"|  Effective batch: {FT_CONFIG['batch_size'] * GRAD_ACCUM}")
print(f"LR: {FT_CONFIG['lr']:.2e}  |  "
      f"Decay at step: {FT_CONFIG['lr_decay_step']:,}\n")

model.train()
optimizer.zero_grad(set_to_none=True)
pbar = tqdm(range(FT_CONFIG['train_steps']), dynamic_ncols=True)

for step in pbar:
    x, y = get_finetune_batch(
        train_seqs, FT_CONFIG['batch_size'],
        FT_CONFIG['max_seq_len'], FT_CONFIG['device']
    )
    if x is None:
        continue

    with torch.amp.autocast('cuda', dtype=torch.float16,
                            enabled=FT_CONFIG['use_amp']):
        _, loss = model(x, y)
        loss    = loss / GRAD_ACCUM

    scaler.scale(loss).backward()

    if (step + 1) % GRAD_ACCUM == 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

    losses.append(loss.item() * GRAD_ACCUM)
    pbar.set_description(
        f"ft_loss {np.mean(losses[-AVG_WINDOW:]):.4f}  |  "
        f"VRAM {torch.cuda.memory_allocated()/1e9:.1f}GB"
    )

    if step > 0 and step % FT_CONFIG['eval_steps'] == 0:
        ev = estimate_loss(FT_CONFIG['eval_iters'])
        print(f"\n  Step {step:>6}  |  "
              f"train {ev['train']:.4f}  |  dev {ev['dev']:.4f}")

    if step == FT_CONFIG['lr_decay_step']:
        print(f"\n  LR decay: {FT_CONFIG['lr']:.2e} "
              f"→ {FT_CONFIG['lr_decayed']:.2e}")
        for g in optimizer.param_groups:
            g['lr'] = FT_CONFIG['lr_decayed']


# ── Final eval + save ──────────────────────────────────────────────────────
ev = estimate_loss(100)
print(f"\nFinal  →  train {ev['train']:.4f}  |  dev {ev['dev']:.4f}")

os.makedirs(os.path.dirname(FT_CONFIG['out_path']), exist_ok=True)

# Avoid overwriting existing checkpoints
out_path, i = FT_CONFIG['out_path'], 0
while os.path.exists(out_path):
    i += 1
    out_path = os.path.splitext(FT_CONFIG['out_path'])[0] + f"_{i}.pt"

torch.save({
    'model_state_dict'     : model.state_dict(),
    'optimizer_state_dict' : optimizer.state_dict(),
    'losses'               : losses,
    'train_loss'           : ev['train'],
    'dev_loss'             : ev['dev'],
    'steps'                : len(losses),
    'config'               : config,
    'ft_config'            : FT_CONFIG,
    'base_model'           : FT_CONFIG['base_model_path'],
    'dataset'              : 'OpenAssistant/oasst1',
}, out_path)

print(f"Saved → {out_path}")
print("\nFine-tuning complete! ✓")
print(f"Base model loss   : {ckpt['train_loss']:.4f}")
print(f"Finetuned loss    : {ev['train']:.4f}")
print(f"Improvement       : {ckpt['train_loss'] - ev['train']:.4f}")