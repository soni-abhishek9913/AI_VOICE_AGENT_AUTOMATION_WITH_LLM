import torch
import torch.nn as nn
from torch import Tensor


class MLP(nn.Module):
    def __init__(self, n_embed: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.hidden  = nn.Linear(n_embed, 4 * n_embed)
        self.gelu    = nn.GELU()
        self.proj    = nn.Linear(4 * n_embed, n_embed)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x: Tensor) -> Tensor:
        return self.project_embedding(self.forward_embedding(x))

    def forward_embedding(self, x: Tensor) -> Tensor:
        return self.gelu(self.hidden(x))

    def project_embedding(self, x: Tensor) -> Tensor:
        return self.dropout(self.proj(x))


if __name__ == '__main__':
    x = torch.randn(2, 16, 128)
    print(MLP(128)(x).shape)  # (2, 16, 128)