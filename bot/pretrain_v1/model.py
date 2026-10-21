"""pretrain-v1 policy/value network: one entity transformer over featurize.observe() output.

Tokens: 1 global (CLS) + 4 scalar / own-command + 6 towers + 5 hand (4 slots, next) + <=256 bodies / carriers + <=32
recent public play events + <=16 revealed opponent cards + 4 lagged-record summaries (<= 324 + padding).
Heads (DESIGN "Bounded tokenization and architecture"):
  gate/slot  5 logits: no-op (from CLS) + 4 pointers (one per current hand token); masked by featurize slot legality
  tile       576 logits conditioned on the chosen hand token and CLS; masked by featurize.legal_tiles
  value      W/D/L logits (index 0 loss, 1 draw, 2 win); V = P(win) - P(loss); same trunk, no privileged input
Default width 192, 4 pre-norm blocks, 6 heads, FFN 576 (~2.3M parameters; count reported by n_params()).
"""
from __future__ import annotations

import math

import numpy as np
import torch
from torch import nn

from . import featurize as F

NEG = -1e9


def fourier(xy, n=6):
    """(..., 2) in tiles -> (..., 4n) sin/cos features over the 18 x 32 board."""
    scale = torch.tensor([F.W, F.H], dtype=xy.dtype, device=xy.device)
    u = xy/scale
    freqs = (2.0**torch.arange(n, dtype=xy.dtype, device=xy.device))*math.pi
    a = u[..., None]*freqs                                  # (..., 2, n)
    return torch.cat([a.sin(), a.cos()], -1).flatten(-2)


class Block(nn.Module):
    def __init__(self, d, heads, ffn, drop):
        super().__init__()
        self.n1 = nn.LayerNorm(d)
        self.att = nn.MultiheadAttention(d, heads, dropout=drop, batch_first=True)
        self.n2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Linear(d, ffn), nn.GELU(), nn.Linear(ffn, d))
        self.drop = nn.Dropout(drop)

    def forward(self, x, pad):
        h = self.n1(x)
        x = x + self.drop(self.att(h, h, h, key_padding_mask=pad, need_weights=False)[0])
        return x + self.drop(self.ff(self.n2(x)))


class PolicyV1(nn.Module):
    def __init__(self, d=192, layers=4, heads=6, ffn=576, drop=0.0, n_cards=None, n_bodies=None):
        super().__init__()
        cat = F.catalog()
        n_cards = n_cards or cat.n_cards
        n_bodies = n_bodies or cat.n_bodies
        self.cfg = dict(d=d, layers=layers, heads=heads, ffn=ffn, drop=drop, n_cards=n_cards, n_bodies=n_bodies)
        self.card = nn.Embedding(n_cards, d)
        self.body = nn.Embedding(n_bodies, d)
        self.owner = nn.Embedding(2, d)
        self.tok_type = nn.Embedding(12, d)                     # token type
        self.place = nn.Embedding(5, d)
        self.slot = nn.Embedding(5, d)
        self.src = nn.Embedding(5, d)
        self.lagpos = nn.Embedding(len(F.LAGS), d)
        self.towpos = nn.Embedding(6, d)
        self.ent_num = nn.Linear(12 + 24 + 24, d)
        self.tow_num = nn.Linear(3, d)
        self.hand_num = nn.Linear(4, d)
        self.clock_num = nn.Linear(8, d)
        self.pend_num = nn.Linear(4 + 24, d)
        self.own_num = nn.Linear(6, d)
        self.opp_num = nn.Linear(6, d)
        self.ev_num = nn.Linear(2 + 24, d)
        self.rev_num = nn.Linear(5, d)
        self.lag_num = nn.Linear(F.L_COLS, d)
        self.cls = nn.Parameter(torch.zeros(d))
        self.blocks = nn.ModuleList(Block(d, heads, ffn, drop) for _ in range(layers))
        self.norm = nn.LayerNorm(d)
        self.noop = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.ptr = nn.Sequential(nn.Linear(2*d, d), nn.GELU(), nn.Linear(d, 1))
        self.tile = nn.Sequential(nn.Linear(2*d, 2*d), nn.GELU(), nn.Linear(2*d, F.NTILE))
        self.value = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 3))
        # frozen post-hoc gate intercept (DESIGN: one scalar fitted on natural-frequency DEV after BC); added to no-op
        self.register_buffer('gate_bias', torch.zeros(()))

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    # -- embedding -------------------------------------------------------------------------------------------------
    def embed(self, b):
        """b: collate() dict of tensors -> (tokens (B, T, d), pad (B, T) True = padding, hand token index base)."""
        d = self.cls.shape[0]
        ent = b['ent'].float()
        e_valid = b['ent_mask']
        B = ent.shape[0]
        x, y = ent[..., F.E_X]/F.XY_Q, ent[..., F.E_Y]/F.XY_Q
        hp, age = ent[..., F.E_HP], ent[..., F.E_AGE]
        aim = torch.stack([ent[..., F.E_AX], ent[..., F.E_AY]], -1)/F.XY_Q
        carrier = (ent[..., F.E_KIND] == 2).float()
        num = torch.stack([x/F.W, y/F.H, (hp.clamp(min=0)/F.HP_Q), (hp < 0).float(), age.clamp(min=0)/F.AGE_CAP,
                           (age < 0).float(), ent[..., F.E_VX]/F.V_Q*5, ent[..., F.E_VY]/F.V_Q*5,
                           ent[..., F.E_MOT], carrier, carrier*(aim[..., 0] - x)/F.W, carrier*(aim[..., 1] - y)/F.H], -1)
        ent_tok = (self.ent_num(torch.cat([num, fourier(torch.stack([x, y], -1)), fourier(aim)*carrier[..., None]], -1))
                   + self.card(b['ent'][..., F.E_CARD].long()) + self.body(b['ent'][..., F.E_BODY].long())
                   + self.owner(b['ent'][..., F.E_OWNER].long().clamp(0, 1))
                   + self.tok_type(b['ent'][..., F.E_KIND].long().clamp(0, 2) + 8))
        tow = b['tow'].float()
        tow_tok = (self.tow_num(torch.stack([tow[..., F.T_PRESENT], tow[..., F.T_ALIVE], tow[..., F.T_HP]/F.HP_Q], -1))
                   + self.towpos.weight[None] + self.tok_type.weight[1])
        hand = b['hand'].long()
        hand_tok = (self.card(hand[..., F.H_CARD]) + self.slot.weight[None] + self.place(hand[..., F.H_PLACE].clamp(0, 4))
                    + self.hand_num(torch.stack([hand[..., F.H_COST].float()/10, hand[..., F.H_AFFORD].float(),
                                                 hand[..., F.H_LEGAL].float(), hand[..., F.H_NEXT].float()], -1))
                    + self.tok_type.weight[2])
        g = b['glob'].float()
        t = g[:, F.G_TICK]
        clock = torch.stack([t/6000, (t >= 2400).float(), (t >= 3600).float(), (t >= 4800).float(),
                             g[:, F.G_ELIXIR]/F.EL_Q/10, torch.sin(t/6000*math.pi), (g[:, F.G_GAP].clamp(min=0))/10,
                             (g[:, F.G_GAP] < 0).float()], -1)
        busy = g[:, F.G_BUSY]
        ptile = g[:, F.G_PEND_TILE].clamp(min=0)
        pxy = torch.stack([ptile % F.W + .5, torch.div(ptile, F.W, rounding_mode='floor') + .5], -1)
        pend = (self.pend_num(torch.cat([torch.stack([busy, g[:, F.G_PEND_AGE].clamp(min=0)/100,
                                                       g[:, F.G_PEND_SLOT].clamp(min=0)/3, (g[:, F.G_PEND_TILE] >= 0).float()], -1),
                                          fourier(pxy)*busy[:, None]], -1))
                + self.card(g[:, F.G_PEND_CARD].long())*busy[:, None])
        own = self.own_num(torch.stack([g[:, F.G_OWN_LAST].clamp(min=0)/F.AGE_CAP, (g[:, F.G_OWN_LAST] < 0).float(),
                                        g[:, F.G_REJ_LAST].clamp(min=0)/F.AGE_CAP, (g[:, F.G_REJ_LAST] < 0).float(),
                                        g[:, F.G_SINCE_SUBMIT].clamp(min=0)/F.AGE_CAP, g[:, F.G_N_OWN]/50], -1))
        opp = self.opp_num(torch.stack([g[:, F.G_N_OPP]/50, g[:, F.G_N_REV]/8, (8 - g[:, F.G_N_REV]).clamp(min=0)/8,
                                        g[:, F.G_X_UNITS], g[:, F.G_X_SPELLS], g[:, F.G_POLLS]/255], -1))
        scal = torch.stack([self.clock_num(clock), pend, own, opp], 1) + self.tok_type.weight[3]
        ev = b['ev'].float()
        exy = torch.stack([ev[..., F.V_X], ev[..., F.V_Y]], -1)/F.XY_Q
        known = (ev[..., F.V_X] >= 0).float()
        ev_tok = (self.ev_num(torch.cat([torch.stack([ev[..., F.V_AGE]/F.EV_WINDOW, 1 - known], -1),
                                         fourier(exy.clamp(min=0))*known[..., None]], -1))
                  + self.card(b['ev'][..., F.V_CARD].long()) + self.owner(b['ev'][..., F.V_OWNER].long().clamp(0, 1))
                  + self.src(b['ev'][..., F.V_SRC].long().clamp(0, 4)) + self.tok_type.weight[4])
        rv = b['rev'].float()
        rev_tok = (self.rev_num(torch.stack([rv[..., F.R_N]/15, rv[..., F.R_SINCE]/2400, rv[..., F.R_OTHERS]/15,
                                             rv[..., F.R_FIRST]/6000, (rv[..., F.R_OTHERS] >= 7).float()], -1))
                   + self.card(b['rev'][..., F.R_CARD].long()) + self.tok_type.weight[5])
        lg = b['lag'].float()
        scale = torch.tensor([1, 40, F.EL_Q] + [F.HP_Q]*6 + [20]*6, dtype=lg.dtype, device=lg.device)
        lag_tok = self.lag_num(lg/scale) + self.lagpos.weight[None] + self.tok_type.weight[6]
        cls = (self.cls + self.tok_type.weight[0]).expand(B, 1, d)
        toks = torch.cat([cls, scal, tow_tok, hand_tok, ent_tok, ev_tok, rev_tok, lag_tok], 1)
        dev = toks.device
        fixed = torch.zeros(B, 1 + 4 + 6 + 5, dtype=torch.bool, device=dev)
        # lag summaries are always tokens: an absent one is its all-zero row (L_PRESENT 0 says "missing")
        lag_pad = torch.zeros(B, len(F.LAGS), dtype=torch.bool, device=dev)
        pad = torch.cat([fixed, ~e_valid, ~b['ev_mask'], ~b['rev_mask'], lag_pad], 1)
        return toks, pad, 1 + 4 + 6

    def trunk(self, b):
        x, pad, h0 = self.embed(b)
        for blk in self.blocks:
            x = blk(x, pad)
        x = self.norm(x)
        return x[:, 0], x[:, h0:h0 + 4]                 # CLS, 4 hand-slot tokens

    def gate_logits(self, cls, hand, slot_ok):
        """(B, 5): [no-op, slot0..3], illegal slots masked; no-op always legal."""
        noop = self.noop(cls) + self.gate_bias
        ptr = self.ptr(torch.cat([cls[:, None].expand_as(hand), hand], -1)).squeeze(-1)
        ptr = ptr.masked_fill(~slot_ok, NEG)
        return torch.cat([noop, ptr], 1)

    def tile_logits(self, cls, hand, slot, tile_ok):
        """slot: (B,) chosen slot; tile_ok: (B, 576) bool -> (B, 576) masked logits."""
        h = hand[torch.arange(hand.shape[0], device=hand.device), slot.clamp(min=0)]
        return self.tile(torch.cat([cls, h], -1)).masked_fill(~tile_ok, NEG)

    def tile_logits_all(self, cls, hand, tiles_ok):
        """tiles_ok: (B, 4, 576) -> (B, 4, 576) masked logits (all slots; RL KL / inference)."""
        z = self.tile(torch.cat([cls[:, None].expand_as(hand), hand], -1))
        return z.masked_fill(~tiles_ok, NEG)

    def forward(self, b):
        cls, hand = self.trunk(b)
        return dict(gate=self.gate_logits(cls, hand, b['slot_ok']), cls=cls, hand=hand, value=self.value(cls))


# -- batching --------------------------------------------------------------------------------------------------------
def pad_ragged(parts, cap, cols, dtype=np.int16):
    n = max([len(p) for p in parts] + [1])
    n = min(n, cap)
    out = np.zeros((len(parts), n, cols), dtype)
    mask = np.zeros((len(parts), n), bool)
    for i, p in enumerate(parts):
        k = min(len(p), n)
        out[i, :k] = p[:k]
        mask[i, :k] = True
    return out, mask


def collate(feats, device='cpu'):
    """List of featurize.observe() dicts (or stored rows with the same keys; ev/rev may be present-only) -> tensors."""
    ent, ent_mask = pad_ragged([f['ent'] for f in feats], F.MAX_ENT, F.E_COLS)
    ev, ev_mask = pad_ragged([f['ev'][f['ev'][:, F.V_PRESENT] == 1] for f in feats], F.MAX_EV, F.V_COLS)
    rev, rev_mask = pad_ragged([f['rev'][f['rev'][:, F.R_PRESENT] == 1] for f in feats], F.MAX_REV, F.R_COLS)
    b = dict(ent=ent, ent_mask=ent_mask, ev=ev, ev_mask=ev_mask, rev=rev, rev_mask=rev_mask,
             tow=np.stack([f['tow'] for f in feats]), hand=np.stack([f['hand'] for f in feats]),
             glob=np.stack([f['glob'] for f in feats]), lag=np.stack([f['lag'] for f in feats]).astype(np.int16),
             slot_ok=np.stack([f['slot_ok'] for f in feats]), alive=np.stack([f['alive'] for f in feats]))
    return {k: torch.from_numpy(v).to(device) for k, v in b.items()}


def tiles_ok_np(hand, slot_ok, alive):
    """(B,5,H_COLS), (B,4), (B,6) numpy -> (B,4,576) bool legal tiles (featurize.tile_mask, cached)."""
    B = hand.shape[0]
    out = np.zeros((B, 4, F.NTILE), bool)
    for i in range(B):
        al = tuple(bool(a) for a in alive[i])
        for s in range(4):
            if slot_ok[i, s]:
                out[i, s] = F.tile_mask(int(hand[i, s, F.H_PLACE]), al)
    return out
