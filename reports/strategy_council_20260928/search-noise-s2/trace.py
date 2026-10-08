"""Scoring-only event and belief traces; no action RNG or tracker updates here."""
import numpy as np
from derived_public_state import DerivedPublicState


def snapshot(belief,tick,true_elixir,true_hand):
    if isinstance(belief,DerivedPublicState):
        d=dict(elixir_mean=belief.elixir,elixir_interval_90=[belief.elixir]*2,
               hand=belief.derived()['hand'],concentrated=True,hypotheses=1)
    else:d=belief.distribution()
    hand=d['hand'];lo,hi=d['elixir_interval_90']
    return dict(tick=tick,elixir_mean=float(d['elixir_mean']),truth_elixir=float(true_elixir),
                interval=[float(lo),float(hi)],covered=bool(lo<=true_elixir<=hi),
                hand_concentrated=hand is not None,
                hand_correct=hand is not None and sorted(hand,key=lambda x:x or '')==sorted(true_hand,key=lambda x:x or ''),
                hypothesis_concentrated=bool(d.get('concentrated',False)),hypotheses=d.get('hypotheses'))


def trajectory(rows,metric,origin):
    """Permanent means no recovery through the last recorded decision, right-censored."""
    eligible=[r for r in rows if r['tick']>=origin]
    bad=[r for r in eligible if not r[metric]]
    if not bad:return dict(first_loss_tick=None,recovered=None,terminal_loss_tick=None)
    first=bad[0]['tick'];recovered=any(r['tick']>first and r[metric] for r in eligible)
    last_good=max((r['tick'] for r in rows if r[metric]),default=-1)
    terminal=next((r['tick'] for r in eligible if r['tick']>last_good and not r[metric]),None)
    return dict(first_loss_tick=first,recovered=recovered,terminal_loss_tick=terminal,
                last_decision_tick=rows[-1]['tick'])
