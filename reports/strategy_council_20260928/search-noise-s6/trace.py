"""Scoring-only event and belief traces; no action RNG or tracker updates here."""
import numpy as np
from collections import Counter
from elt import ELT
from derived_public_state import DerivedPublicState


def snapshot(belief,tick,true_elixir,true_hand):
    if isinstance(belief,DerivedPublicState):
        d=dict(elixir_mean=belief.elixir,elixir_interval_90=[belief.elixir]*2,
               hand=belief.derived()['hand'],concentrated=True,hypotheses=1)
    else:d=belief.distribution()
    d=dict(d)
    if isinstance(belief,DerivedPublicState):
        d.update(hand90=d['hand'],hand90_mass=1. if d['hand'] is not None else 0.)
    elif isinstance(belief,ELT):
        masses=Counter()
        for state,w in zip(belief.projected(),belief.weights):
            h=state.derived()['hand']
            if h is not None:masses[tuple(h)]+=float(w)
        h,m=max(masses.items(),key=lambda x:x[1],default=(None,0.))
        d.update(hand90=h if m>=.9 else None,hand90_mass=m)
    elif 'hand_probability' in d:
        d.update(hand90=d['hand'],hand90_mass=d['hand_probability'])
    hand=d['hand']
    # Old unanimity is a scoring-only diagnostic, distinct from T3's >=90% field.
    from tracker_v3 import TrackerV3
    if isinstance(belief,TrackerV3) and not belief.perfect:
        hands=[]
        for state,w in belief._hands:
            x=belief._clone_hand(state);x.advance(belief.tick)
            known=sorted(x.revealed-set(x.queue))
            hands.append(tuple(known+[None]*(4-len(known))) if len(known)==8-len(x.queue) else None)
        hand=hands[0] if hands and hands[0] is not None and all(h==hands[0] for h in hands) else None
    lo,hi=d['elixir_interval_90']
    return dict(tick=tick,elixir_mean=float(d['elixir_mean']),truth_elixir=float(true_elixir),
                interval=[float(lo),float(hi)],covered=bool(lo<=true_elixir<=hi),
                hand_concentrated=hand is not None,
                hand_correct=hand is not None and sorted(hand,key=lambda x:x or '')==sorted(true_hand,key=lambda x:x or ''),
                hypothesis_concentrated=bool(d.get('concentrated',False)),hypotheses=d.get('hypotheses'),hand90=d.get('hand90'),hand90_mass=d.get('hand90_mass'),
                hand90_correct=d.get('hand90') is not None and sorted(d['hand90'],key=lambda x:x or '')==sorted(true_hand,key=lambda x:x or ''))


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
