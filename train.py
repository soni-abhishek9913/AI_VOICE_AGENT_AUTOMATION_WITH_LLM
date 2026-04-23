import torch
import os
import numpy as np
from tqdm import tqdm
from typing import Dict

from config import default_config as config
from transformer import Transformer
from data_loader import get_batch_iterator

# ── GPU check ─────────────────────────────────────────────────────────────
assert torch.cuda.is_available(), "CUDA not found. Set DEVICE='cpu' in config for testing."
print(f"GPU : {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

# ── Model ─────────────────────────────────────────────────────────────────
model = Transformer(
    n_head         = config['n_head'],
    n_embed        = config['n_embed'],
    context_length = config['context_length'],
    vocab_size     = config['vocab_size'],
    N_BLOCKS       = config['n_blocks'],
).to(config['device'])

if config['compile_model']:
    print("Compiling with torch.compile() — first steps will be slow...")
    model = torch.compile(model)

total = sum(p.numel() for p in model.parameters())
print(f"Parameters: {total:,}  (~{total/1e6:.1f}M)\n")

# ── Optimizer ─────────────────────────────────────────────────────────────
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr           = config['t_lr'],
    betas        = (0.9, 0.95),
    weight_decay = 0.1,
    fused        = True,
)
scaler = torch.amp.GradScaler('cuda', enabled=config['use_amp'])
GRAD_ACCUM = config['grad_accum_steps']
losses     = []
AVG_WINDOW = 64


# ── Eval helper ───────────────────────────────────────────────────────────
@torch.no_grad()
def estimate_loss(steps: int) -> Dict[str, float]:
    out = {}
    model.eval()
    for split in ['train', 'dev']:
        path = config['train_path'] if split == 'train' else config['dev_path']
        it   = get_batch_iterator(path, config['t_batch_size'],
                                  config['t_context_length'], config['device'])
        vals = torch.zeros(steps)
        for k in range(steps):
            try:
                xb, yb = next(it)
                with torch.amp.autocast('cuda', dtype=torch.float16, enabled=config['use_amp']):
                    _, loss = model(xb, yb)
                vals[k] = loss.item()
            except StopIteration:
                break
        out[split] = vals[:k + 1].mean().item()
    model.train()
    return out


# ── Training loop ─────────────────────────────────────────────────────────
print(f"Batch size: {config['t_batch_size']}  |  Grad accum: {GRAD_ACCUM}"
      f"  |  Effective batch: {config['t_batch_size'] * GRAD_ACCUM}")
print(f"Context: {config['t_context_length']}  |  Steps: {config['t_train_steps']}"
      f"  |  AMP: {config['use_amp']}\n")

train_iter = get_batch_iterator(config['train_path'], config['t_batch_size'],
                                config['t_context_length'], config['device'])
optimizer.zero_grad(set_to_none=True)
pbar = tqdm(range(config['t_train_steps']), dynamic_ncols=True)

for step in pbar:
    try:
        xb, yb = next(train_iter)
    except StopIteration:
        print("Data iterator exhausted.")
        break

    # Forward
    with torch.amp.autocast('cuda', dtype=torch.float16, enabled=config['use_amp']):
        _, loss = model(xb, yb)
        loss    = loss / GRAD_ACCUM

    # Backward
    scaler.scale(loss).backward()

    # Optimizer step every GRAD_ACCUM micro-steps
    if (step + 1) % GRAD_ACCUM == 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

    losses.append(loss.item() * GRAD_ACCUM)
    pbar.set_description(
        f"loss {np.mean(losses[-AVG_WINDOW:]):.4f}  |  "
        f"VRAM {torch.cuda.memory_allocated()/1e9:.1f}GB"
    )

    # Periodic eval
    if step > 0 and step % config['t_eval_steps'] == 0:
        ev = estimate_loss(config['t_eval_iters'])
        print(f"\n  Step {step:>6}  |  train {ev['train']:.4f}  |  dev {ev['dev']:.4f}")

    # LR decay
    if step == config['t_lr_decay_step']:
        print(f"\n  LR decay: {config['t_lr']:.2e} → {config['t_lr_decayed']:.2e}")
        for g in optimizer.param_groups:
            g['lr'] = config['t_lr_decayed']

# ── Final eval + save ─────────────────────────────────────────────────────
ev = estimate_loss(200)
print(f"\nFinal  →  train {ev['train']:.4f}  |  dev {ev['dev']:.4f}")

os.makedirs(os.path.dirname(config['t_out_path']), exist_ok=True)
out_path, i = config['t_out_path'], 0
while os.path.exists(out_path):
    i += 1
    out_path = os.path.splitext(config['t_out_path'])[0] + f"_{i}.pt"

torch.save({
    'model_state_dict':     model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'losses':               losses,
    'train_loss':           ev['train'],
    'dev_loss':             ev['dev'],
    'steps':                len(losses),
    'config':               config,
}, out_path)
print(f"Saved → {out_path}")