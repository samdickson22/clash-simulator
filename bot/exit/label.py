"""DAgger-style labelling: the student acts, the K4S budget search labels the same public state.

LabelingPlayer(behavior, teacher) sits in one seat. Every 5-tick poll it forwards the view to
both: the behavior student (whose action is executed, unless beta-mixing picks the teacher's)
and the teacher SearchPlayer (which keeps its own belief, R3a proposer poller and RNG streams,
exactly as when it plays). When the teacher runs a root search (10-tick multiple, free channel,
more than one candidate) the state is recorded as one gate-c v6 training row:

- inputs = the student's own public observation at that poll: rows.observation(reserved packet,
  the student's v5 mask, the student's D1) -- the same packet + D1 R3a sees when serving;
- label = the teacher's chosen root action (timed waits 2400-2402 kept in teacher_search_action,
  expert_actions = WAIT for them), plus the teacher's complete candidate list and 3-style scores
  (core.last), i.e. the R3 root-target format (root_actions/root_scores/root_valid);
- flags: teacher_hit (budget cut before the full W-screen8 schedule), teacher_student_default
  (S-default replaced the frozen choice), behavior_action (what the student did).

Rows are sealed per (game, seat) with the frozen exit_r3 rows.seal (schema teacher-v6), so
imitation.exit_r1.pack and exit_r3 RootTeacherStore read them unchanged.
"""
from __future__ import annotations

import hashlib
import random

import numpy as np

from bot.players.base import Decision, MatchContext, PublicView, SEARCH_INTERVAL, WAIT


class LabelingPlayer:
    deadline_seconds = None

    def __init__(self, rt, behavior, teacher, *, beta=0.0, keep_features=False):
        self.rt, self.behavior, self.teacher, self.beta = rt, behavior, teacher, float(beta)
        self.name = f'{behavior.name}|label:{teacher.name}' + (f'|beta{beta:g}' if beta else '')
        self.keep_features = keep_features

    def start(self, ctx: MatchContext):
        from clasher.rl.action_space import DiscreteTileActionSpace
        self.ctx = ctx
        self.behavior.start(ctx)
        self.teacher.start(ctx)
        self.space = DiscreteTileActionSpace()
        self.rows, self.scores, self.features = [], [], []
        self.counts = dict(polls=0, searched=0, labelled=0, single_candidate=0, other_skip=0,
                           hit=0, student_default=0, teacher_play=0, behavior_play_at_label=0,
                           agree=0, executed_teacher=0)
        digest = hashlib.sha256(f'bot-exit-beta|{ctx.seed}|{ctx.seat}'.encode()).digest()
        self.beta_rng = random.Random(int.from_bytes(digest[:8], 'big'))

    def act(self, view: PublicView) -> Decision:
        self.counts['polls'] += 1
        d = self.behavior.act(view)
        t = self.teacher.act(view)
        if t.stats is None:
            return d
        self.counts['searched'] += 1
        labelled = self._record(view, t, d)
        if labelled and self.beta and self.beta_rng.random() < self.beta:
            self.counts['executed_teacher'] += 1
            return t
        return d

    def _record(self, view, t, d):
        from exit_r3.rows import observation
        st = t.stats
        if 'completed' not in st:          # <=1 candidate (or a preparation cutoff): no root scores
            self.counts['single_candidate' if st.get('candidates', 2) <= 1 else 'other_skip'] += 1
            return False
        assert view.can_act and view.tick % SEARCH_INTERVAL == 0 and not view.pending
        poller = self.behavior.poller
        mask, d1 = poller.mask, poller.player.last_d1
        core = self.teacher.p.core
        candidates = [int(a) for a in core.last['candidates']]
        scores = [None if v is None else float(v) for v in core.last['scores']]
        chosen = int(st['action'])
        expert = chosen if chosen < WAIT else WAIT
        if not mask[expert]:
            raise AssertionError('teacher label outside the student mask')
        for a, v in zip(candidates, scores):
            if v is not None and a < 2400 and not mask[a]:
                raise AssertionError('scored candidate outside the student mask')
        row = observation(view.reserved.packet, mask, d1, self.rt.R.builder)
        seat, tick = view.seat, view.tick
        position = self.space.decode_action(expert, seat).position
        xy = [np.nan, np.nan] if position is None else [position.x, position.y]
        row.update(expert_actions=np.int16(expert), expert_action_supervision_valid=np.bool_(True),
                   submitted_ticks=np.int32(tick), teacher_search_action=np.int16(chosen),
                   teacher_root=np.bool_(True), teacher_wait_kind=np.int8(0),
                   recorded_play_ticks=np.int32(-1 if expert == WAIT else tick + 27),
                   recorded_world_positions=np.array(xy, np.float32),
                   submitted_world_positions=np.array(xy, np.float32),
                   recorded_millitiles=np.array([-1, -1] if position is None else
                                                [round(position.x*1000), round(position.y*1000)], np.int32),
                   teacher_hit=np.bool_(bool(st.get('hit'))),
                   teacher_student_default=np.bool_(bool(st.get('student_default'))),
                   teacher_completed=np.int16(st.get('completed', 0)),
                   teacher_rollouts=np.float32(st.get('rollouts', -1)),
                   behavior_action=np.int16(d.action))
        # The student's own P(play) at this state (one extra forward), for on-policy threshold calibration.
        from imitation.evaluation.d1 import model_packet
        from imitation.model.inference import single_features
        from proposals import outputs
        feats = single_features(model_packet(view.reserved.packet, mask), d1, self.behavior.cached.costs)
        p_play, _ = outputs(self.behavior.cached.model, feats)
        row.update(behavior_p_play=np.float32(float(p_play[0])),
                   behavior_legal_play=np.bool_(bool(mask[:WAIT].any())))
        self.rows.append(row)
        self.scores.append(dict(candidates=candidates, scores=scores))
        if self.keep_features:
            self.features.append(feats)
        c = self.counts
        c['labelled'] += 1
        c['hit'] += bool(st.get('hit'))
        c['student_default'] += bool(st.get('student_default'))
        c['teacher_play'] += expert < WAIT
        c['behavior_play_at_label'] += d.action < WAIT
        c['agree'] += int(d.action) == expert
        return True

    def close(self):
        self.behavior.close()
        self.teacher.close()


def seal_rows(directory, rows, scores, receipt):
    """Atomic: seal into a hidden temp dir, then rename to `directory`."""
    import os
    from pathlib import Path
    from exit_r3.rows import seal
    directory = Path(directory)
    tmp = directory.parent / f'.tmp-{directory.name}-{os.getpid()}'
    if tmp.exists():
        import shutil
        shutil.rmtree(tmp)
    seal(tmp, rows, scores, receipt)
    if directory.exists():
        directory.rename(directory.parent / f'.stale-{directory.name}-{os.getpid()}')
    tmp.rename(directory)
    return directory
