import torch
import numpy as np
import h5py
from typing import Iterator, Tuple


def get_batch_iterator(data_path: str, batch_size: int, context_length: int,
                       device: str = "cpu") -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
    with h5py.File(data_path, 'r') as f:
        dataset    = f['tokens']
        n_examples = (dataset.shape[0] - 1) // context_length
        idxs       = np.arange(n_examples)
        np.random.shuffle(idxs)
        epoch, counter = 0, 0

        while True:
            if counter + batch_size > n_examples:
                np.random.shuffle(idxs)
                counter = 0
                epoch  += 1
                print(f"  [DataLoader] Epoch {epoch}")

            starts  = idxs[counter : counter + batch_size] * context_length
            samples = torch.tensor(
                np.array([dataset[s : s + context_length + 1] for s in starts]),
                dtype=torch.long,
            )
            xb = samples[:, :context_length].to(device)
            yb = samples[:, 1 : context_length + 1].to(device)
            counter += batch_size
            yield xb, yb


if __name__ == '__main__':
    import os, h5py
    path = "dummy.h5"
    if not os.path.exists(path):
        with h5py.File(path, 'w') as f:
            f.create_dataset('tokens', data=np.arange(10_000, dtype=np.int32))
    xb, yb = next(get_batch_iterator(path, 4, 16))
    print(f"xb: {xb.shape}  yb: {yb.shape}")    