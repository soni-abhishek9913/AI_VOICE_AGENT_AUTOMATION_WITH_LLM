import os, json, argparse, zstandard as zstd, tiktoken, h5py
from tqdm import tqdm
from typing import Optional


def process_directory(input_dir: str, output_file: str,
                      tokenizer_name: str, max_data: Optional[int] = None) -> None:
    enc = tiktoken.get_encoding(tokenizer_name)
    with h5py.File(output_file, 'w') as out_f:
        ds    = out_f.create_dataset('tokens', (0,), maxshape=(None,), dtype='i4')
        idx   = 0
        total = 0

        for fname in sorted(os.listdir(input_dir)):
            if not fname.endswith(".jsonl.zst"):
                continue
            count = 0
            print(f"Processing: {fname}")
            with zstd.open(os.path.join(input_dir, fname), 'rt', encoding='utf-8') as f:
                for line in tqdm(f, total=max_data, desc=fname):
                    try:
                        text = json.loads(line).get('text', '').strip()
                        if not text:
                            continue
                        tokens = enc.encode(text + "<|endoftext|>",
                                            allowed_special={'<|endoftext|>'})
                        n = len(tokens)
                        ds.resize(idx + n, axis=0)
                        ds[idx : idx + n] = tokens
                        idx   += n
                        total += n
                        count += 1
                    except Exception:
                        pass
                    if max_data and count >= max_data:
                        break
            print(f"  {count:,} docs — {total:,} tokens total")

    print(f"Done. Output: {output_file}  ({os.path.getsize(output_file)/1e6:.1f} MB)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train_dir",      default="data/train")
    p.add_argument("--val_dir",        default="data/val")
    p.add_argument("--out_train_file", default="data/train/pile_train.h5")
    p.add_argument("--out_val_file",   default="data/val/pile_dev.h5")
    p.add_argument("--tokenizer_name", default="r50k_base")
    p.add_argument("--max_data",       type=int, default=50_000)
    args = p.parse_args()

    print("=== Training data ===")
    process_directory(args.train_dir, args.out_train_file, args.tokenizer_name, args.max_data)
    print("\n=== Validation data ===")
    process_directory(args.val_dir, args.out_val_file, args.tokenizer_name, args.max_data)


if __name__ == "__main__":
    main()


#app = 80 milion para    