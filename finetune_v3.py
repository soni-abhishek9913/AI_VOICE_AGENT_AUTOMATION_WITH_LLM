

import torch
import os
import json
import numpy as np
from tqdm import tqdm
import tiktoken

from config import default_config as config
from transformer import Transformer

FT_CONFIG = {
    "base_model_path": "models/transformer_rtx4060.pt",   # start from base model
    "out_path":        "models/transformer_hospital_v3.pt",
    "lr":              3e-5,        # lower LR → careful fine-tune
    "batch_size":      8,
    "grad_accum":      4,           # effective batch = 32
    "train_steps":     15000,       # more steps for richer dataset
    "eval_steps":      500,
    "max_seq_len":     256,
    "device":          "cuda" if torch.cuda.is_available() else "cpu",
    "use_amp":         True,
}

DATASET_PATH = "perfect_hospital_dataset.jsonl"

enc = tiktoken.get_encoding("r50k_base")

USER_TOKEN      = "<|user|>"
ASSISTANT_TOKEN = "<|assistant|>"
END_TOKEN       = "<|endoftext|>"


def tokenize(text):
    return enc.encode(text, allowed_special={"<|endoftext|>"})


def build_dataset():
    sequences = []
    print("Loading dataset...")
    with open(DATASET_PATH) as f:
        for line in tqdm(f):
            row = json.loads(line)
            text = ""
            for msg in row["messages"]:
                if msg["role"] == "user":
                    text += f"{USER_TOKEN} {msg['content']} "
                elif msg["role"] == "assistant":
                    text += f"{ASSISTANT_TOKEN} {msg['content']} "
            text += END_TOKEN
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

print("Loading base model...")
ckpt = torch.load(FT_CONFIG["base_model_path"], map_location=FT_CONFIG["device"], weights_only=False)

model = Transformer(
    n_head         = config["n_head"],
    n_embed        = config["n_embed"],
    context_length = config["context_length"],
    vocab_size     = config["vocab_size"],
    N_BLOCKS       = config["n_blocks"],
    dropout        = 0.1,
).to(FT_CONFIG["device"])

model.load_state_dict(ckpt["model_state_dict"])
print("Model loaded.")


sequences  = build_dataset()
np.random.shuffle(sequences)
split      = int(len(sequences) * 0.95)
train_seqs = sequences[:split]
dev_seqs   = sequences[split:]
print(f"Train: {len(train_seqs):,}  |  Dev: {len(dev_seqs):,}")


optimizer  = torch.optim.AdamW(model.parameters(), lr=FT_CONFIG["lr"],
                                betas=(0.9, 0.95), weight_decay=0.1)
scaler     = torch.amp.GradScaler("cuda", enabled=FT_CONFIG["use_amp"])
GRAD_ACCUM = FT_CONFIG["grad_accum"]
losses     = []


@torch.no_grad()
def estimate_loss(steps=100):
    out = {}
    model.eval()
    for name, seqs in [("train", train_seqs), ("dev", dev_seqs)]:
        vals = []
        for _ in range(steps):
            x, y = get_batch(seqs, FT_CONFIG["batch_size"],
                             FT_CONFIG["max_seq_len"], FT_CONFIG["device"])
            with torch.amp.autocast("cuda", dtype=torch.float16,
                                    enabled=FT_CONFIG["use_amp"]):
                _, loss = model(x, y)
            vals.append(loss.item())
        out[name] = np.mean(vals)
    model.train()
    return out

print(f"\nFine-tuning for {FT_CONFIG['train_steps']:,} steps...")
model.train()
optimizer.zero_grad()

for step in tqdm(range(FT_CONFIG["train_steps"])):
    x, y = get_batch(train_seqs, FT_CONFIG["batch_size"],
                     FT_CONFIG["max_seq_len"], FT_CONFIG["device"])

    with torch.amp.autocast("cuda", dtype=torch.float16, enabled=FT_CONFIG["use_amp"]):
        _, loss = model(x, y)
        loss = loss / GRAD_ACCUM

    scaler.scale(loss).backward()

    if (step + 1) % GRAD_ACCUM == 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

    losses.append(loss.item() * GRAD_ACCUM)

    if step > 0 and step % FT_CONFIG["eval_steps"] == 0:
        ev = estimate_loss()
        print(f"\n  Step {step}  |  train {ev['train']:.4f}  |  dev {ev['dev']:.4f}")


os.makedirs("models", exist_ok=True)
torch.save({
    "model_state_dict":     model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "config":               config,
    "ft_config":            FT_CONFIG,
    "train_loss":           np.mean(losses[-200:]),
}, FT_CONFIG["out_path"])

print(f"\nSaved → {FT_CONFIG['out_path']}")
print(f"Final avg loss: {np.mean(losses[-200:]):.4f}")