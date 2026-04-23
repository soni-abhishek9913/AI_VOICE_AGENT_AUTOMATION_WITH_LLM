import os, argparse, requests
from tqdm import tqdm
from typing import List

BASE_URL   = "https://huggingface.co/datasets/monology/pile-uncopyrighted/resolve/main"
VAL_URL    = f"{BASE_URL}/val.jsonl.zst"
TRAIN_URLS = [f"{BASE_URL}/train/{i:02d}.jsonl.zst" for i in range(65)]


def download_file(url: str, dest: str) -> None:
    r     = requests.get(url, stream=True)
    total = int(r.headers.get('content-length', 0))
    with open(dest, 'wb') as f:
        with tqdm(total=total, unit='B', unit_scale=True, desc=os.path.basename(dest)) as bar:
            for chunk in r.iter_content(65536):
                f.write(chunk)
                bar.update(len(chunk))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--train_max', type=int, default=1)
    parser.add_argument('--train_dir', default="data/train")
    parser.add_argument('--val_dir',   default="data/val")
    args = parser.parse_args()

    os.makedirs(args.train_dir, exist_ok=True)
    os.makedirs(args.val_dir,   exist_ok=True)

    val_path = os.path.join(args.val_dir, "val.jsonl.zst")
    if not os.path.exists(val_path):
        download_file(VAL_URL, val_path)
    else:
        print("Validation file already present.")

    for i, url in enumerate(TRAIN_URLS[:args.train_max]):
        name = f"{i:02d}.jsonl.zst"
        path = os.path.join(args.train_dir, name)
        if not os.path.exists(path):
            download_file(url, path)
        else:
            print(f"{name} already present.")


if __name__ == "__main__":
    main()

#1 file = 400k to 800 k sample    