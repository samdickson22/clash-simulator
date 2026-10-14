"""bot.search.run for the K4C candidate arms: same games and cost columns, plus candidate diagnostics.

    python -m bot.search.cand_run --out DIR --candidate K4C-r8-k8 --opponents R3a,v1 --games 300 --workers 48

Extra per-game 'search' fields (means over searched decisions): plays_scanned (plays in the candidate set,
i.e. coarse rollouts), k_new (second-proposer plays not among R3a's), from_second (fraction of decisions whose
chosen action only the second proposer proposed).
"""
from __future__ import annotations

import bot.search.run as base

_summary = base.search_summary


def search_summary(player, timing):
    out = _summary(player, timing)
    ds = [d for d in getattr(player, 'decisions', []) if d and 'plays_scanned' in d]
    if ds:
        out.update({k: sum(d[k] for d in ds) / len(ds) for k in ('plays_scanned', 'k_new', 'from_second')})
    return out


base.search_summary = search_summary

if __name__ == '__main__':
    base.main()
