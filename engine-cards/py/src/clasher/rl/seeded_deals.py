"""Exogenous ordered-deck scenarios for fixed-policy complete-game collection."""

import hashlib
import json

import numpy as np
import torch


class SeededDealSchedule:
    """Precompute distinct deals per matchup; advance only rows that terminate."""

    def __init__(self, base_decks, learner_players, scenario_keys, *, seed, episodes):
        if base_decks.dtype != torch.int64 or learner_players.dtype != torch.int64:
            raise ValueError("seeded deal card IDs and learner seats must be int64")
        if base_decks.device != learner_players.device:
            raise ValueError("seeded deal templates and seats must share a device")
        base = base_decks.detach().cpu().numpy()
        seats = learner_players.detach().cpu().numpy()
        if base.ndim != 3 or base.shape[1:] != (2, 8) or episodes < 1:
            raise ValueError(
                "seeded deals require [batch, 2, 8] decks and positive episodes"
            )
        if (
            seats.shape != (len(base),)
            or not np.isin(seats, [0, 1]).all()
            or len(scenario_keys) != len(base)
        ):
            raise ValueError("seeded deal matchup rows or learner seats are misaligned")
        table = np.empty((episodes, *base.shape), dtype=np.int64)
        identities = []
        planned = {}
        for row, key in enumerate(scenario_keys):
            seat = int(seats[row])
            relative = base[row, [seat, 1 - seat]]
            if key not in planned:
                deals, ids, seen = [], [], set()
                for ordinal in range(episodes):
                    for attempt in range(1000):
                        material = json.dumps(
                            [
                                "seeded-ordered-decks-v1",
                                int(seed),
                                key,
                                ordinal,
                                attempt,
                            ],
                            separators=(",", ":"),
                        ).encode()
                        rng = np.random.default_rng(
                            int.from_bytes(
                                hashlib.sha256(material).digest()[:16], "big"
                            )
                        )
                        deal = np.stack(
                            [relative[player, rng.permutation(8)] for player in (0, 1)]
                        )
                        identity = hashlib.sha256(
                            key.encode() + deal.tobytes()
                        ).hexdigest()
                        if identity not in seen:
                            seen.add(identity)
                            deals.append(deal)
                            ids.append(identity)
                            break
                    else:
                        raise ValueError(
                            "cannot construct the declared number of distinct deals"
                        )
                planned[key] = (relative.copy(), np.stack(deals), ids)
            original, deals, ids = planned[key]
            if not np.array_equal(original, relative):
                raise ValueError(
                    "paired matchup rows disagree on relative deck templates"
                )
            table[:, row, seat] = deals[:, 0]
            table[:, row, 1 - seat] = deals[:, 1]
            identities.append(list(ids))
        self.table = torch.as_tensor(table, dtype=torch.int64, device=base_decks.device)
        self.ordinals = torch.zeros(
            len(base), dtype=torch.int64, device=base_decks.device
        )
        self._rows = torch.arange(len(base), device=base_decks.device)
        self.seed = int(seed)
        self.episodes = int(episodes)
        self.scenario_keys = tuple(scenario_keys)
        self.scenario_ids_by_stream = identities

    def initial_decks(self):
        return self.table[0].clone()

    def __call__(self, decision_index, reset_mask, step):
        if reset_mask.shape != self.ordinals.shape or reset_mask.dtype != torch.bool:
            raise ValueError("seeded deal reset mask is invalid")
        self.ordinals.add_(reset_mask.to(torch.int64))
        # Faster streams can continue after their retained quota. Their surplus
        # episodes are discarded by the corpus builder, and reuse the last deal.
        return self.table[self.ordinals.clamp_max(self.episodes - 1), self._rows]

    def metadata(self):
        return {
            "schema": "clasher.seeded-ordered-decks.v1",
            "seed": self.seed,
            "episodes_per_stream": self.episodes,
            "scenario_keys": list(self.scenario_keys),
            "scenario_ids_by_stream": self.scenario_ids_by_stream,
            "paired_seats_share_relative_deals": True,
            "retained_deals_distinct_within_matchup": True,
            "surplus_resets": "repeat-last-unretained-deal",
        }
