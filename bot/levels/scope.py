"""Fixed supported-card belief scope for the conditional-population pilot only.

The three non-11 export failures are excluded from every arm's prior before any
player starts. Original catalog projections and the standard player factories
outside bot.levels are unchanged. No outcome-dependent exclusions are allowed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os

EXCLUDED = frozenset({'Clone', 'Earthquake', 'Tornado'})


def digest(prior):
    """Bind ordered deck rows, card orders, frequencies and catalog metadata."""
    return hashlib.sha256(json.dumps(prior, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def restricted(prior):
    rows = prior['decks']
    omitted = [r for r in rows if EXCLUDED.intersection(r['cards'])]
    kept = [copy.deepcopy(r) for r in rows if not EXCLUDED.intersection(r['cards'])]
    total = sum(r['frequency'] for r in rows)
    lost = sum(r['frequency'] for r in omitted)
    if not kept or total <= 0:
        raise ValueError('supported-card scope must retain a nonempty positive prior')
    out = dict(copy.deepcopy(prior), decks=kept)
    receipt = dict(excluded=sorted(EXCLUDED), original_sha256=digest(prior), restricted_sha256=digest(out),
                   original_decks=len(rows), retained_decks=len(kept), omitted_decks=len(omitted),
                   original_frequency=total, omitted_frequency=lost, omitted_mass=lost / total)
    return out, receipt


def install(rt):
    """Idempotent, experiment-local installation, with immutable original reference."""
    if getattr(rt, 'belief_prior', None) not in (None, 'c56') or os.environ.get('BOT_BELIEF_PRIOR') not in (None, '', 'c56'):
        raise ValueError('level pilot requires the catalog prior, not BOT_BELIEF_PRIOR override')
    if hasattr(rt, 'levels_scope'):
        if (digest(rt.PRIOR) != rt.levels_scope['restricted_sha256'] or
                digest(rt.levels_original_prior) != rt.levels_scope['original_sha256']):
            raise ValueError('experimental belief scope changed after installation')
        return rt.levels_scope
    original = copy.deepcopy(rt.PRIOR)
    rt.PRIOR, receipt = restricted(original)
    rt.levels_original_prior, rt.levels_scope = original, receipt
    return receipt
