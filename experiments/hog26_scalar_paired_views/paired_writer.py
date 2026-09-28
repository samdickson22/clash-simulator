"""Observe both actual public views without another battle or policy call."""

from contextlib import ExitStack
from unittest.mock import patch

import numpy as np

from scripts.hog26_scalar_corpus import ScalarGameCorpusWriter
from scripts.hog26_scalar_death_actor_adapter import ScalarDeathActorAdapter
from scripts.hog26_scalar_reference_episode import ScalarReferenceEpisode


class PairedWriter:
    def __init__(self, paths, metadata):
        if len(paths) != 2 or len(metadata) != 2:
            raise ValueError('two explicit actor-view destinations required')
        self.writers = tuple(ScalarGameCorpusWriter(path, value) for path, value in zip(paths, metadata, strict=True))
        self.pending = None
        self.completed_rows = 0
        self.stack = None

    def __enter__(self):
        if self.stack is not None:
            raise ValueError('paired recorder cannot be reentered')
        original_build = ScalarDeathActorAdapter.build
        original_step = ScalarReferenceEpisode.step

        def build(adapter, *args, **kwargs):
            if self.pending is not None:
                raise ValueError('previous observed decision was not recorded')
            actors = original_build(adapter, *args, **kwargs)
            self.pending = {'battle': adapter.battle, 'tick': adapter.battle.tick, 'actors': actors}
            return actors

        def step(episode, actions, *args, **kwargs):
            pending = self.pending
            if pending is None or pending['battle'] is not episode.battle or pending['tick'] != episode.battle.tick or 'result' in pending:
                raise ValueError('one matching observation and physical step required')
            pending['actions'] = np.array(actions, copy=True)
            result = original_step(episode, actions, *args, **kwargs)
            pending['result'] = result
            return result

        self.stack = ExitStack()
        self.stack.enter_context(patch.object(ScalarDeathActorAdapter, 'build', build))
        self.stack.enter_context(patch.object(ScalarReferenceEpisode, 'step', step))
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self.stack.__exit__(exc_type, exc, traceback)

    def append(self, actor, inputs, *, learner_seat, tick, action, success):
        pending = self.pending
        if (pending is None or 'result' not in pending or pending['tick'] != tick
                or pending['actors'][learner_seat] is not actor
                or pending['actions'][learner_seat] != action
                or pending['result']['action_success'][learner_seat] != success):
            raise ValueError('original writer boundary does not match observed decision')
        for seat, writer in enumerate(self.writers):
            writer.append(pending['actors'][seat], inputs, learner_seat=seat, tick=tick,
                          action=int(pending['actions'][seat]), success=pending['result']['action_success'][seat])
        self.pending = None
        self.completed_rows += 1

    def finish(self, result):
        if self.pending is not None or not self.completed_rows:
            raise ValueError('complete observed stream required')
        for seat, writer in enumerate(self.writers):
            writer.finish(terminal_tick=result['ticks'], winner=result['winner'], learner_seat=seat,
                          terminal_tower_hp=result['terminal_tower_hp_by_slot'],
                          initial_tower_hp=result['initial_tower_hp_by_slot'], actual_terminal=result['complete'])
