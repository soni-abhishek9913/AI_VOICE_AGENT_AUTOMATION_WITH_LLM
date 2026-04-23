import torch
import torch.nn as nn
from attention import MultiHeadAttention
from mlp import MLP


class Block(nn.Module):
    def __init__(self, n_head: int, n_embed: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.ln1  = nn.LayerNorm(n_embed)
        self.attn = MultiHeadAttention(n_head, n_embed, dropout=dropout)
        self.ln2  = nn.LayerNorm(n_embed)
        self.mlp  = MLP(n_embed, dropout=dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x

    def forward_embedding(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        residual   = x + self.attn(self.ln1(x))
        mlp_hidden = self.mlp.forward_embedding(self.ln2(residual))
        return mlp_hidden, residual


if __name__ == '__main__':
    x = torch.randn(2, 16, 128)
    print(Block(4, 128)(x).shape)  # (2, 16, 128)