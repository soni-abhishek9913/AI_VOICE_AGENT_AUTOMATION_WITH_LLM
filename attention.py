import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiHeadAttention(nn.Module):
    def __init__(self, n_head: int, n_embed: int, dropout: float = 0.0) -> None:
        super().__init__()
        assert n_embed % n_head == 0, "n_embed must be divisible by n_head"

        self.n_head    = n_head
        self.n_embed   = n_embed
        self.head_size = n_embed // n_head
        self.dropout   = dropout

        # Fused QKV projection — single matrix multiply instead of 3 separate ones
        # This is faster than separate key/query/value linear layers
        self.qkv  = nn.Linear(n_embed, 3 * n_embed, bias=False)
        self.proj = nn.Linear(n_embed, n_embed, bias=False)

        self.attn_dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape

        # Compute Q, K, V in one fused matrix multiply
        qkv = self.qkv(x)                          # (B, T, 3 * n_embed)
        q, k, v = qkv.split(self.n_embed, dim=2)   # each: (B, T, n_embed)

        # Reshape into (B, n_head, T, head_size) for multi-head attention
        q = q.view(B, T, self.n_head, self.head_size).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.head_size).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.head_size).transpose(1, 2)

        # Flash Attention — PyTorch built-in, no manual mask or softmax needed
        # is_causal=True handles the causal mask automatically and efficiently
        # dropout_p only applied during training
        dropout_p = self.dropout if self.training else 0.0
        x = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask  = None,
            dropout_p  = dropout_p,
            is_causal  = True,
        )

        # Reshape back to (B, T, n_embed)
        x = x.transpose(1, 2).contiguous().view(B, T, C)

        return self.proj(x)


if __name__ == '__main__':
    B, T, C = 2, 16, 128
    x   = torch.randn(B, T, C)
    mha = MultiHeadAttention(n_head=4, n_embed=C, context_length=T)
    print(mha(x).shape)   # (2, 16, 128)

    # Parameter count comparison
    old_params = 4 * (C * (C // 4) * 3) + C * C   # 3 separate linears per head + proj
    new_params  = sum(p.numel() for p in mha.parameters())
    print(f"Old params: {old_params:,}  |  New params: {new_params:,}")