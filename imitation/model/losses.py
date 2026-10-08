"""Conditional weighted cross entropy and right-censored discrete hazard loss."""
from typing import Dict
import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as F
from .network import masked_log_softmax

# Twelve finite bins end at 10s; the 13th is the open >10s interval.
HAZARD_EDGES = np.geomspace(0.05, 10.0, 12)


def intent_target(seconds: float, observed: bool):
    if seconds < 0:
        raise ValueError("negative intent time")
    if observed:
        return int(np.searchsorted(HAZARD_EDGES, seconds, side="left")), True
    # Number of COMPLETED intervals. Partial censored intervals are not failures.
    return int(np.searchsorted(HAZARD_EDGES, seconds, side="right")), False


def hazard_loss(logits: Tensor, bins: Tensor, observed: Tensor) -> Tensor:
    k = torch.arange(13, device=logits.device)[None]
    prior = k < bins[:, None]
    event = (k == bins[:, None]) & observed[:, None]
    return (F.softplus(logits.float()) * prior + F.softplus(-logits.float()) * event).sum(-1)


def loss_parts(o: Dict[str, Tensor], y: Dict[str, Tensor]) -> Dict[str, Tensor]:
    a = y["action"].long()
    valid = y["supervised"].bool()
    play = valid & (a < 2304)
    gate_y = torch.where(a == 2304, 0, torch.where(a == 2305, 2, 1))
    slot, tile = (a // 576).clamp(0, 3), a.remainder(576)
    gp = masked_log_softmax(o["gate"], o["gate_mask"])
    cp = masked_log_softmax(o["card"], o["card_mask"])
    tp = masked_log_softmax(o["tile"], o["tile_mask"])
    if tp.shape[1] == 1:
        tp = tp[:, 0]
    else:
        tp = tp[torch.arange(a.shape[0], device=a.device), slot]
    w = y["weight"].float()
    gate_use = valid & o["card_mask"].any(-1)
    observed = y["intent_observed"].bool()
    intent_valid = valid & y["intent_valid"].bool()
    iy = y["intent_card"].long().clamp(0, 7)
    rows = {"gate": -gp.gather(1, gate_y[:, None]).squeeze(1),
            "card": -cp.gather(1, slot[:, None]).squeeze(1),
            "tile": -tp.gather(1, tile[:, None]).squeeze(1),
            "intent_card": F.cross_entropy(o["intent_card"].float(), iy, reduction="none"),
            "hazard": hazard_loss(o["hazard"], y["intent_bin"], observed)}
    masks = {"gate": gate_use, "card": play, "tile": play,
             "intent_card": intent_valid & observed & (y["intent_card"] >= 0), "hazard": intent_valid}
    result = {}
    for name, values in rows.items():
        weight = w * masks[name]
        result[name + "_sum"] = (values * weight).sum()
        result[name + "_weight"] = weight.sum()
    return result


def total_loss(parts: Dict[str, Tensor], denominators=None):
    """Pass full effective-batch denominators when accumulating microbatches."""
    terms = {}
    for name in ("gate", "card", "tile", "intent_card", "hazard"):
        den = parts[name+"_weight"] if denominators is None else denominators[name+"_weight"]
        terms[name] = parts[name+"_sum"] / den.clamp_min(1e-12)
    terms["loss"] = terms["gate"] + terms["card"] + terms["tile"] + .25*(terms["intent_card"]+terms["hazard"])
    return terms
