"""Policy-vs-search diagnosis recorder (play-quality owner; analysis only, never changes a decision).

ShadowRecorder is bot.livediag.ours_diag.PacketRecorder plus, at every poll of OUR seat where it can act, what the HP1 v2
human policy (student v2 @ tau*) would do on the same packet and D1 state, and - at searched decisions - the search's own
scores for every key it scored:
  shadow[n] = dict(tick, gate (v2 P(play)), v2_play (v2's top legal play), v2_top5, v2_act (v2's decoded action at tau*:
               top play if gate >= tau else WAIT), search (search's chosen action or None at polls the search did not
               decide), work/scores (the refined keys and their final scores), coarse (every play's balanced coarse-scan
               value), waits (native balanced values of WAIT and the timed waits), source (decision source)).
v2 is run here on its own CachedPolicy-equivalent forward (bot/search/candidates.py ranked + proposals.outputs) on the
search tier's poller packet/mask/D1, so the shadow reads exactly the public view the search used. Nothing it computes is
returned to the player; the RNG streams of the match and the search are untouched.

For the policy-only arm (`pv2` in bot/livediag/l16_cadence.py: LivePlayer(tier='fast') with v2 @ tau*) the plain
PacketRecorder is enough; ShadowRecorder is for the search arm.
"""
from __future__ import annotations

from bot.livediag.ours_diag import PacketRecorder

WAIT = 2304


class ShadowRecorder(PacketRecorder):
    def __init__(self, rt, inner, search, v2_path, tau):
        super().__init__(rt, inner)
        self.search, self.tau, self.shadow = search, float(tau), []
        from bot.search.candidates import load_proposer
        self.v2 = load_proposer(v2_path)[0]

    def record(self, view, d):
        super().record(view, d)
        if not view.can_act:
            return
        try:
            self.shadow.append(self._shadow(view, d))
        except Exception as ex:                       # analysis only: never break the game
            self.shadow.append(dict(tick=view.tick, error=repr(ex)[:200]))

    def _shadow(self, view, d):
        import torch
        from imitation.evaluation.d1 import model_packet
        from imitation.model.inference import single_features
        from proposals import outputs, rank_actions
        s = self.search
        mp, d1 = model_packet(view.reserved.packet, s.poller.mask), s.poller.player.last_d1
        with torch.inference_mode():
            prob, ranks = outputs(self.v2.model, single_features(mp, d1, self.v2.costs))
        gate = float(prob[0])
        plays = [int(a) for a in rank_actions(ranks[0].numpy(), mp['action_mask'])]
        st = d.stats or {}
        searched = st.get('source', '').startswith(('search', 'default'))
        out = dict(n=len(self.perc) - 1, tick=view.tick, gate=round(gate, 5), v2_play=plays[0] if plays else None,
                   v2_top5=plays[:5], v2_act=(plays[0] if plays and gate >= self.tau else WAIT),
                   source=st.get('source'), action=int(d.action))
        last = getattr(getattr(getattr(s, 'p', None), 'core', None), 'last', None) if searched else None
        if last and last.get('candidates') is not None and getattr(s.p.core.info, 'tick', None) == view.tick:
            out.update(search=int(d.action), work=[int(a) for a in last['candidates']],
                       scores=[None if v is None else round(float(v), 6) for v in last['scores']],
                       coarse={str(a): round(float(v), 6) for a, v in (last.get('coarse') or {}).items()},
                       waits={str(a): round(float(v), 6) for a, v in (last.get('waits_native') or {}).items()})
        return out
