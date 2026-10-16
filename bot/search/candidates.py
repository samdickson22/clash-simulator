"""Candidate-quality arms for K4S-st: which policy proposals enter the W-screen8 candidate set (exploration).

K4S-st (bot/search/players.py) passes R3a's top-8 legal plays as policy_proposals to the frozen
C56RolloutPlanner.candidates (after the script decision, WAIT and the scripted ranks; before the 16 random
samples; duplicates dropped, public mask applied). These arms change ONLY that list:

- r<N>   R3a's top-N legal plays (its play ranking, play/wait gate ignored). r8 == K4S-st.
         N > 8 re-runs R3a's forward on the poll's packet (the cache keeps 8) and asserts the first 8 match.
- k<M>   a second proposer's top-M legal plays, appended after R3a's (R3a's win exact ties). The default
         proposer is ExIt student K (it3K step 2000, sha256 ed5a4936...; reports/bot/exit/PROGRESS.md),
         read from $CLASHER_BOT_STUDENTS (default /mpac/sdicks02/repos/clasher-bot-runtime/students).
- '@<ckpt>' replaces the second proposer (equivalence checks: K4C-r0-k8@<R3a.pt> == K4S-st).

R3a stays the 5-tick poller, the coarse-scan hint and the S-default cutoff default in every arm; scorer,
waits, refine (top-8 by coarse score) and every rng stream are unchanged. The scan order cannot matter: with
no cutoff every play gets its coarse rollout and exact ties break by candidate-list position.
Names: 'K4C-' + '-'.join(tokens), e.g. K4C-r16, K4C-r8-k8, K4C-r16-k16, K4C-r0-k8.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from bot.search.players import MultiSearchPlayer

K_NAME = 'K-it3K-step002000.pt'
K_SHA256 = 'ed5a4936c46ec184c3e618c20e8907753ac80f1efa30d03c910b9cc905038052'
_PROPOSERS: dict = {}


def load_proposer(path: Path):
    """Process-wide cache; the default K checkpoint must match its recorded sha256."""
    key = str(Path(path).resolve())
    if key not in _PROPOSERS:
        from proposals import load_student
        sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if Path(path).name == K_NAME and sha != K_SHA256:
            raise ValueError(f'{path}: sha256 {sha} != recorded {K_SHA256}')
        _PROPOSERS[key] = (load_student(path, None), sha)
    return _PROPOSERS[key]


def ranked(policy, packet, d1):
    """The proposer's legal plays, best first: exactly CachedPolicy.sample's threshold-branch ranking."""
    import torch
    from imitation.model.inference import single_features
    from proposals import outputs, rank_actions
    from clasher.rl.slot_permission import eligibility_mask
    with torch.inference_mode():
        b = single_features(packet, d1, policy.costs)
        _, ranks = outputs(policy.model, b)
    return [int(a) for a in rank_actions(ranks[0].numpy(), eligibility_mask(packet))]


class CandidateSearchPlayer(MultiSearchPlayer):
    def __init__(self, rt, *, r3a=8, second=0, second_path=None, name=None):
        super().__init__(rt, student_candidates=True, name=name)
        self.r3a, self.second = int(r3a), int(second)
        self.second_path = Path(second_path) if second_path else None
        self._info = {}

    def start(self, ctx):
        super().start(ctx)
        from imitation.evaluation.d1 import model_packet
        core, rt = self.p.core, self.rt
        original = core.candidates
        proposer = load_proposer(self.second_path)[0] if self.second else None

        def candidates(packet, policy_proposals=()):
            cached = [int(a) for a in policy_proposals]          # R3a top-8 from MultiSearchPlayer.act
            mp, d1 = model_packet(packet, self.poller.player.last_feature_mask, eligibility_mask=self.poller.mask), self.poller.player.last_d1
            if self.r3a > len(cached):
                full = ranked(rt.STUDENT, mp, d1)
                if full[:len(cached)] != cached:
                    raise AssertionError('R3a re-ranking differs from the cached proposals')
                first = full[:self.r3a]
            else:
                first = cached[:self.r3a]
            extra = ranked(proposer, mp, d1)[:self.second] if proposer is not None else []
            out, mask = original(packet, first + extra)
            plays = sum(a < 2304 for a in out)
            self._info = dict(plays_scanned=plays, k_new=len(set(extra) - set(first)), first=set(first),
                              extra=set(extra))
            return out, mask
        core.candidates = candidates

    def _done(self, action, stats, wall0, wait_ticks=0):
        info, self._info = self._info, {}
        if info:
            stats = dict(stats, plays_scanned=info['plays_scanned'], k_new=info['k_new'],
                         from_second=int(action in info['extra'] and action not in info['first']))
        return super()._done(action, stats, wall0, wait_ticks)


def make_candidate_player(rt, name):
    """'K4C-' + tokens r<N>, k<M>, optionally '@<ckpt>' for the k proposer (see module docstring)."""
    base, _, path = name.partition('@')
    kw = dict(r3a=8, second=0)
    for token in base.split('-')[1:]:
        m = re.fullmatch(r'([rk])(\d+)', token)
        if not m:
            raise ValueError(f'unknown candidate token {token!r} in {name!r}')
        kw['r3a' if m[1] == 'r' else 'second'] = int(m[2])
    students = Path(os.environ.get('CLASHER_BOT_STUDENTS', '/mpac/sdicks02/repos/clasher-bot-runtime/students'))
    return CandidateSearchPlayer(rt, second_path=path or students / K_NAME, name=name, **kw)
