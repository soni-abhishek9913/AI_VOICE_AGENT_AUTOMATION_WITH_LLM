import torch
import torch.nn as nn
import torch.nn.functional as F
from transformer_block import Block


class Transformer(nn.Module):

    def __init__(self,
                 n_head: int,
                 n_embed: int,
                 context_length: int,
                 vocab_size: int,
                 N_BLOCKS: int,
                 dropout: float = 0.0):

        super().__init__()

        self.context_length = context_length

        self.token_embed = nn.Embedding(vocab_size, n_embed) # token embedding 
        self.position_embed = nn.Embedding(context_length, n_embed) # position embedding

        self.embed_dropout = nn.Dropout(dropout)

        self.attn_blocks = nn.ModuleList(
            [Block(n_head, n_embed, dropout=dropout) for _ in range(N_BLOCKS)]
        )

        self.layer_norm = nn.LayerNorm(n_embed)

        self.lm_head = nn.Linear(n_embed, vocab_size, bias=False)

        # weight tying
        self.lm_head.weight = self.token_embed.weight

        self.register_buffer(
            "pos_idxs",
            torch.arange(context_length)
        )

        self.apply(self._init_weights)


    def _init_weights(self, module):

        if isinstance(module, nn.Linear):

            nn.init.normal_(module.weight, mean=0.0, std=0.02)

            if module.bias is not None:
                nn.init.zeros_(module.bias)

        elif isinstance(module, nn.Embedding):

            nn.init.normal_(module.weight, mean=0.0, std=0.02)

 
    def _pre_attn_pass(self, idx):

        B, T = idx.shape

        tok_emb = self.token_embed(idx)

        pos_emb = self.position_embed(self.pos_idxs[:T])

        return self.embed_dropout(tok_emb + pos_emb)


    def forward(self, idx, targets=None):

        x = self._pre_attn_pass(idx)

        for block in self.attn_blocks:
            x = block(x)

        x = self.layer_norm(x)

        logits = self.lm_head(x)

        loss = None

        if targets is not None:

            B, T, C = logits.shape

            loss = F.cross_entropy(
                logits.view(B*T, C),
                targets.view(B*T).long()
            )

        return logits, loss


    @torch.no_grad()
    def generate(self,
                 idx,
                 max_new_tokens,
                 temperature=0.8,
                 top_k=40,
                 repetition_penalty=1.2):

        for _ in range(max_new_tokens):

            idx_cond = idx[:, -self.context_length:]

            logits, _ = self(idx_cond)

            logits = logits[:, -1, :]

            # repetition penalty
            if repetition_penalty != 1.0:

                for token in set(idx[0].tolist()):
                    logits[0, token] /= repetition_penalty

            # temperature
            logits = logits / temperature

            # top-k filtering
            if top_k is not None:

                values, _ = torch.topk(
                    logits,
                    min(top_k, logits.size(-1))
                )

                logits[logits < values[:, [-1]]] = -float("Inf")

            probs = F.softmax(logits, dim=-1)

            idx_next = torch.multinomial(probs, num_samples=1)

            idx = torch.cat((idx, idx_next), dim=1)

        return idx


if __name__ == "__main__":

    model = Transformer(4, 128, 32, 50304, 2)

    idx = torch.randint(0, 50304, (2, 16))

    logits, loss = model(idx, targets=idx)

    print("Logits:", logits.shape)
    print("Loss:", loss.item())