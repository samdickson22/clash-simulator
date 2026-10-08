"""Set transformer; no hand-slot or entity-order positional embeddings."""
from dataclasses import dataclass
from typing import Dict

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass
class ModelConfig:
    vocab: int = 360
    descriptors: int = 57
    width: int = 192
    heads: int = 6
    layers: int = 4
    ffn: int = 768
    tile_width: int = 128
    dropout: float = 0.1
    numeric: int = 24
    types: int = 24


def masked_log_softmax(logits: Tensor, mask: Tensor) -> Tensor:
    """FP32, including empty conditional supports (all log probabilities -1e9)."""
    z = logits.float().masked_fill(~mask, -1e9)
    return F.log_softmax(z, dim=-1).masked_fill(~mask, -1e9)


class Attention(nn.Module):
    def __init__(self, width: int, heads: int, context: int, dropout: float):
        super().__init__()
        self.heads, self.depth, self.dropout = heads, width // heads, dropout
        self.q = nn.Linear(width, width)
        self.kv = nn.Linear(context, 2 * width)
        self.out = nn.Linear(width, width)

    def forward(self, x: Tensor, context: Tensor, valid: Tensor) -> Tensor:
        b, n, _ = x.shape
        q = self.q(x).view(b, n, self.heads, self.depth).transpose(1, 2)
        k, v = self.kv(context).chunk(2, -1)
        k = k.view(b, -1, self.heads, self.depth).transpose(1, 2)
        v = v.view(b, -1, self.heads, self.depth).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=valid[:, None, None, :],
                                          dropout_p=self.dropout if self.training else 0.0)
        return self.out(y.transpose(1, 2).reshape(b, n, self.heads * self.depth))


class Block(nn.Module):
    def __init__(self, c: ModelConfig):
        super().__init__()
        self.n1, self.n2 = nn.LayerNorm(c.width), nn.LayerNorm(c.width)
        self.attn = Attention(c.width, c.heads, c.width, c.dropout)
        self.ffn = nn.Sequential(nn.Linear(c.width, c.ffn), nn.GELU(),
                                 nn.Dropout(c.dropout), nn.Linear(c.ffn, c.width))
        self.drop = nn.Dropout(c.dropout)

    def forward(self, x: Tensor, valid: Tensor) -> Tensor:
        z = self.n1(x)
        x = x + self.drop(self.attn(z, z, valid))
        return x + self.drop(self.ffn(self.n2(x)))


class SetPolicy(nn.Module):
    def __init__(self, c: ModelConfig, descriptors: Tensor, tiles: Tensor, costs: Tensor):
        super().__init__()
        if descriptors.shape != (c.vocab, c.descriptors) or tiles.shape != (576, 12):
            raise ValueError("static asset dimensions do not match config")
        self.register_buffer("descriptors", descriptors.float())
        self.register_buffer("tile_features", tiles.float())
        self.register_buffer("costs", costs.float())
        self.register_buffer("temperatures", torch.ones(3))
        self.register_buffer("frequencies", 2.0 ** torch.arange(8) * torch.pi)
        self.card_embed = nn.Embedding(c.vocab, c.width)
        self.type_embed = nn.Embedding(c.types, c.width)
        # Separate numeric projection for each semantic type.
        self.numeric_weight = nn.Parameter(torch.empty(c.types, c.numeric, c.width))
        nn.init.normal_(self.numeric_weight, std=0.02)
        self.descriptor = nn.Linear(c.descriptors, c.width, bias=False)
        self.fourier = nn.Linear(32, c.width, bias=False)
        self.cls = nn.Parameter(torch.zeros(1, 1, c.width))
        self.blocks = nn.ModuleList([Block(c) for _ in range(c.layers)])
        self.norm = nn.LayerNorm(c.width)
        self.gate = nn.Sequential(nn.Linear(c.width, c.width), nn.GELU(), nn.Linear(c.width, 3))
        self.card = nn.Sequential(nn.Linear(2*c.width, c.width), nn.GELU(), nn.Linear(c.width, 1))
        self.tile_embed = nn.Parameter(torch.randn(576, c.tile_width) * 0.02)
        self.tile_static = nn.Linear(12, c.tile_width)
        self.tile_norm = nn.LayerNorm(c.tile_width)
        self.cross = Attention(c.tile_width, 4, c.width, c.dropout)
        self.tile_ffn_norm = nn.LayerNorm(c.tile_width)
        self.tile_ffn = nn.Sequential(nn.Linear(c.tile_width, 256), nn.GELU(),
                                      nn.Linear(256, c.tile_width))
        self.condition = nn.Linear(c.width, c.tile_width)
        self.tile_score = nn.Sequential(nn.Linear(c.tile_width, c.tile_width), nn.GELU(),
                                        nn.Linear(c.tile_width, 1))
        self.intent = nn.Sequential(nn.Linear(c.width, c.width), nn.GELU(), nn.Linear(c.width, 21))

    def encode(self, b: Dict[str, Tensor]) -> Tensor:
        ids, types, numeric = b["ids"], b["types"], b["numeric"]
        # bmm of selected weights avoids a Python loop over token types.
        numeric_embedding = torch.matmul(numeric.unsqueeze(-2), self.numeric_weight[types]).squeeze(-2)
        x = (self.card_embed(ids) + self.type_embed(types) + numeric_embedding
             + self.descriptor(self.descriptors[ids]))
        phase = numeric[:, :, :2, None] * self.frequencies
        fourier = torch.cat((phase.sin(), phase.cos()), -1).flatten(-2)
        x = x + self.fourier(fourier) * (types == 0).unsqueeze(-1)
        x = torch.cat((self.cls.expand(ids.shape[0], -1, -1), x), 1)
        valid = torch.cat((torch.ones_like(b["valid"][:, :1]), b["valid"]), 1)
        for layer in self.blocks:
            x = layer(x, valid)
        return self.norm(x)

    def forward(self, b: Dict[str, Tensor], teacher: Tensor) -> Dict[str, Tensor]:
        """teacher=[B] hand slots for training, or empty long tensor for all four."""
        x = self.encode(b)
        cls, hand = x[:, 0], x[:, 1:5]
        card_logits = self.card(torch.cat((cls[:, None].expand(-1, 4, -1), hand), -1)).squeeze(-1)
        tile_mask = b["action_mask"][:, :2304].view(-1, 4, 576)
        card_mask = tile_mask.any(-1)
        gate_mask = torch.stack((b["action_mask"][:, 2304], card_mask.any(-1),
                                 b["action_mask"][:, 2305]), -1)
        q = (self.tile_embed + self.tile_static(self.tile_features))[None].expand(x.shape[0], -1, -1)
        valid = torch.cat((torch.ones_like(b["valid"][:, :1]), b["valid"]), 1)
        q = q + self.cross(self.tile_norm(q), x, valid)
        q = q + self.tile_ffn(self.tile_ffn_norm(q))
        if teacher.numel() > 0:
            selected = hand.gather(1, teacher[:, None, None].expand(-1, 1, hand.shape[-1]))
            tile_mask = tile_mask.gather(1, teacher[:, None, None].expand(-1, 1, 576))
        else:
            selected = hand
        conditioned = q[:, None] * self.condition(selected)[:, :, None]
        tiles = self.tile_score(conditioned).squeeze(-1)
        intent = self.intent(cls)
        return {"gate": self.gate(cls), "card": card_logits, "tile": tiles,
                "gate_mask": gate_mask, "card_mask": card_mask, "tile_mask": tile_mask,
                "intent_card": intent[:, :8], "hazard": intent[:, 8:]}

    @torch.jit.export
    def log_policy(self, b: Dict[str, Tensor]) -> Dict[str, Tensor]:
        o = self.forward(b, torch.empty(0, dtype=torch.long, device=b["ids"].device))
        return {"gate": masked_log_softmax(o["gate"] / self.temperatures[0], o["gate_mask"]),
                "card": masked_log_softmax(o["card"] / self.temperatures[1], o["card_mask"]),
                "tile": masked_log_softmax(o["tile"] / self.temperatures[2], o["tile_mask"])}
