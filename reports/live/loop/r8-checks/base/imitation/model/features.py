"""One adapter for mmap rows and CPU serving. Whitelisted v5 + public D1 only.

Coordinates in D1 histories must already be canonical normalized x/18,y/32;
ages are seconds/60; refill values are milliseconds/1000. No hidden truth is read.
Unknown cycle slots remain typed tokens; absent historical events are omitted.
"""
from collections.abc import Mapping
import numpy as np
import torch

ENTITY_COLUMNS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 23, 24, 25, 26, 27, 28, 30)
GLOBAL_COLUMNS = (0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 17, 14, 15)
BUCKETS = (48, 64, 96, 128, 192)


def get(obj, name):
    return obj[name] if isinstance(obj, Mapping) else getattr(obj, name)


def build_row(public_packet, d1, costs):
    """Required packet: v5 fields, champion_button, action_mask (unpacked bool).

    Required D1 keys are explicit; missing facts raise rather than silently invent
    an unknown derived state. own/opp_history are [<=8,4] (token,age,x,y),
    opp_abilities is [<=4,2] (token,age). elixir is raw units [0,10].
    """
    # The actual T1/T3 sidecar contract uses integer milliseconds and split
    # ID/feature columns. Normalize here so serving and training share the path.
    if isinstance(d1, Mapping) and "opp_recent_play_ids" in d1:
        d1 = dict(d1)
        for side in ("opp", "own"):
            d1[side+"_history"] = np.column_stack((d1[side+"_recent_play_ids"], d1[side+"_recent_play_features"]))
        d1["opp_abilities"] = np.column_stack((d1["opp_ability_ids"], d1["opp_ability_ages"]))
        d1["opp_refill_remaining"] = float(d1["opp_refill_remaining"])/1000
        d1["own_refill_remaining"] = float(d1["own_refill_remaining"])/1000
    ids, types, numeric = [], [], []
    def add(card, kind, values=()):
        card = int(card)
        if not 0 <= card < 360:
            raise ValueError("token outside pinned vocabulary")
        v = np.zeros(24, np.float32)
        v[:len(values)] = values
        ids.append(card); types.append(kind); numeric.append(v)

    action_mask = np.asarray(get(public_packet, "action_mask"), bool)
    if action_mask.shape != (2306,) or not action_mask.any():
        raise ValueError("need nonempty unpacked 2306 action mask")
    globals_ = np.asarray(get(public_packet, "global_features"), np.float32)
    if globals_.shape != (18,):
        raise ValueError("v5 globals must have width 18")
    hand = np.asarray(get(public_packet, "hand_ids"), np.int64)
    levels = np.asarray(get(public_packet, "hand_levels"), np.float32)
    button = float(get(public_packet, "champion_button"))
    if hand.shape != (5,) or levels.shape != (5,):
        raise ValueError("need four hand cards plus next")
    for s in range(4):
        add(hand[s], 1, (costs[hand[s]] / 10 - globals_[5],
                         action_mask[s*576:(s+1)*576].any(), button, levels[s]/16))
    deck = np.asarray(get(d1, "own_deck"), np.int64)
    if deck.shape != (8,) or len(set(deck.tolist())) != 8 or (deck == 0).any():
        raise ValueError("own deck must contain eight known distinct tokens")
    # Fixed deck positions define the auxiliary class vocabulary, not UI slots.
    for index, token in enumerate(np.sort(deck)):
        add(token, 3, (index/7,))
    add(hand[4], 2, (levels[4]/16,))
    for i, token in enumerate(get(d1, "own_queue")):
        add(token, 4+i, (float(token != 0),))
    for token in get(d1, "opp_hand_known"):
        add(token, 8, (float(token != 0),))
    token = get(d1, "opp_next_card")
    add(token, 9, (float(token != 0),))
    for i, token in enumerate(get(d1, "opp_queue")):
        add(token, 10+i, (float(token != 0),))
    for token in get(public_packet, "opponent_seen_card_ids"):
        if token:
            add(token, 14)
    for name, kind in (("opp_history", 15), ("own_history", 16)):
        history = np.asarray(get(d1, name), np.float32).reshape(-1, 4)
        if len(history) > 8:
            raise ValueError("history exceeds eight events")
        for event in history:
            if event[0]:
                add(event[0], kind, event[1:])
    abilities = np.asarray(get(d1, "opp_abilities"), np.float32).reshape(-1, 2)
    if len(abilities) > 8:
        raise ValueError("ability history exceeds eight events")
    for event in abilities:
        if event[0]:
            add(event[0], 17, event[1:])
    g = globals_[list(GLOBAL_COLUMNS)].copy()
    if not button:
        g[-2:] = 0
    values = [*g, float(get(d1, "opp_elixir"))/10,
              get(d1, "opp_refill_remaining"), get(d1, "own_refill_remaining"),
              float(get(d1, "opp_cards_revealed"))/8, float(get(d1, "elixir_exact")), button]
    add(0, 18, values)
    ent = np.asarray(get(public_packet, "entity_features"), np.float32)
    if ent.ndim != 2 or ent.shape[1] not in (17, 32):
        raise ValueError("entity features must have 17 public or 32 v5 columns")
    if ent.shape[1] == 32:
        ent = ent[:, ENTITY_COLUMNS]
    active = np.asarray(get(public_packet, "entity_mask"), bool)
    if active.sum() > 128:
        # No silent entity-order-dependent truncation.
        # Qualified C56 has rare rows above the design's sampled estimate of 64.
        raise ValueError("more than 128 visible entities: outside v5 packet cap")
    ent_ids = get(public_packet, "entity_ids")
    ent_levels = get(public_packet, "entity_levels")
    for i in np.flatnonzero(active):
        add(ent_ids[i], 0, (*ent[i], float(ent_levels[i])/16))
    if len(ids) + 1 > BUCKETS[-1]:
        raise ValueError("row exceeds token cap")
    n = np.stack(numeric)
    if not np.isfinite(n).all():
        raise ValueError("nonfinite public features")
    return {"ids": np.asarray(ids, np.int64), "types": np.asarray(types, np.int64),
            "numeric": n, "valid": np.ones(len(ids), bool), "action_mask": action_mask.copy()}


def collate_features(rows):
    longest = max(len(r["ids"]) + 1 for r in rows)
    width = next(n for n in BUCKETS if n >= longest) - 1
    result = {}
    for key in ("ids", "types", "numeric", "valid"):
        shape = (len(rows), width) + rows[0][key].shape[1:]
        a = np.zeros(shape, rows[0][key].dtype)
        for i, row in enumerate(rows):
            a[i, :len(row[key])] = row[key]
        result[key] = torch.from_numpy(a)
    result["action_mask"] = torch.from_numpy(np.stack([r["action_mask"] for r in rows]))
    return result
