"""Bounded CPU-only registration, transport and counter checks. No engine games."""
import copy
from dataclasses import asdict
import json
import subprocess
import sys
import time

import pytest

from bot.pretrain_v1 import rl_driver as D, rl_schedule as S, rl_evaluate as E, stream_actor as A
from bot.pretrain_v1.rl_learner import LearnerConfig, ContractError
from bot.pretrain_v1.tests.test_rl_coordinator import setup, sample
from bot.pretrain_v1.tests.test_rl_learner import admitted, learner


def populations():
    row = dict(deck=list(S.HOG), cards=dict(S.HOG), tower=9, weight=4, source_id='fixture-history')
    stress = dict(row, cards={c: 12 for c in S.HOG}, tower=12, weight=1)
    return dict(schema='pv1-rl-populations-v1', vocabulary=list(S.HOG), champions=[],
        opponents=dict(empirical=[row], adjacent=[dict(row, source_id='fixture-adjacent')], stress=[stress]),
        meta=[dict(row, level_kind='realistic'), dict(stress, level_kind='stress')],
        random_card_levels=dict(S.HOG), random_tower=9, excluded_mass={'fixture': 0.}, sources=[{'fixture': True}])


def test_case_draws_pair_across_sizes_and_have_disjoint_training_namespace():
    a, b = S.Schedule(populations(), S.SEEDS[0]), S.Schedule(populations(), S.SEEDS[0])
    draws = [a.case(i) for i in range(200)]
    assert draws == [b.case(i) for i in range(200)]
    assert {r['league'] for r in draws} == set(S.LEAGUE)
    assert {r['own_kind'] for r in draws} == set(S.DECKS)
    assert {r['level_kind'] for r in draws} == set(S.LEVELS)
    assert len({r['seed'] for r in draws}) == 200
    assert all(r['seed'] >= 1 << 60 for r in draws)
    assert S.Schedule(populations(), S.SEEDS[1]).case(0)['seed'] != draws[0]['seed']
    assert all(set(r['levels']['cards'][s]) == set(r['decks'][s]) for r in draws for s in (0, 1))


@pytest.mark.parametrize('mutation', ['adjacent', 'level', 'meta', 'champions'])
def test_missing_or_incomplete_populations_fail(mutation):
    p = populations()
    if mutation == 'adjacent':
        p['opponents']['adjacent'] = []
    elif mutation == 'level':
        p['opponents']['empirical'][0]['cards'] = {'HogRider': 10}
    elif mutation == 'meta':
        p['meta'][0]['weight'] = 9
    else:
        p['champions'] = list(S.HOG)
    with pytest.raises(ValueError):
        S.Schedule(p, S.SEEDS[0])


def test_registered_optimizer_budget_and_tolerance_remain_fixed():
    config = LearnerConfig(seed=S.SEEDS[0], size='M')
    assert config.record()['logp_atol'] == 2e-6
    assert config.record()['optimizer_steps_per_update'] == 256
    with pytest.raises(ContractError):
        LearnerConfig(seed=S.SEEDS[0], size='M', steps_per_update=2048)


def test_authoritative_counter_charges_before_inference_and_cannot_regress(tmp_path):
    counter = D.GenerationCounter(tmp_path/'counter', create=True)
    try:
        actor = object.__new__(A.StreamingPolicyOursPlayer)
        actor.generated_steps = 0
        D.attach_counter(actor, counter)
        actor.generated_steps += 1
        assert actor.generated_steps == counter.read() == 1
        with pytest.raises(ValueError, match='regressed'):
            actor.generated_steps = 0
        assert actor.generated_steps == counter.read() == 1
    finally:
        counter.close()


def test_generation_counter_survives_real_process_exit(tmp_path):
    counter = D.GenerationCounter(tmp_path/'counter', create=True)
    try:
        code = ('from bot.pretrain_v1.rl_driver import GenerationCounter; '
                'import sys; c=GenerationCounter(sys.argv[1]); c.write(17); c.close()')
        subprocess.run([sys.executable, '-c', code, str(tmp_path/'counter')], check=True, timeout=20)
        assert counter.read() == 17
        with pytest.raises(FileExistsError):
            D.GenerationCounter(tmp_path/'counter', create=True)
    finally:
        counter.close()


def test_generation_counter_reader_is_bounded_behind_blocked_writer(tmp_path):
    counter = D.GenerationCounter(tmp_path/'counter', create=True)
    program = ('import fcntl,sys; f=open(sys.argv[1],"r+b"); '
               'fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.readline()')
    process = subprocess.Popen([sys.executable, '-c', program, str(tmp_path/'counter')],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        assert process.stdout.readline() == b'locked\n'
        started = time.monotonic()
        with pytest.raises(ValueError, match='lock timeout'):
            counter.read()
        assert time.monotonic()-started < .75
    finally:
        process.communicate(b'release\n', timeout=5)
        counter.close()


def test_gpu_singleton_lock_and_soft_descriptor_admission(tmp_path, monkeypatch):
    with D.learner_lock(tmp_path/'locks'):
        with pytest.raises(RuntimeError, match='another learner'):
            with D.learner_lock(tmp_path/'locks'):
                pass
    limits = [100, 200]
    monkeypatch.setattr(D.resource, 'getrlimit', lambda _: tuple(limits))
    monkeypatch.setattr(D.resource, 'setrlimit', lambda _, values: limits.__setitem__(slice(None), values))
    result = D.ensure_fd_capacity(150)
    assert result['before_soft'] == 100 and result['after_soft'] == 150 and limits == [150, 200]
    with pytest.raises(ValueError, match='hard limit'):
        D.ensure_fd_capacity(201)
    assert limits == [150, 200]


def test_qualification_stop_cannot_charge_another_poll(tmp_path):
    counter = D.GenerationCounter(tmp_path/'counter', create=True)
    actor = object.__new__(A.StreamingPolicyOursPlayer)
    actor.generated_steps = 0
    def stopped():
        raise D.QualificationStop('fixture six-hour boundary')
    try:
        D.attach_counter(actor, counter, stopped)
        with pytest.raises(D.QualificationStop):
            actor.generated_steps += 1
        assert actor.generated_steps == counter.read() == 0
    finally:
        counter.close()


def test_relay_real_atomic_spool_to_exact_quota_coordinator(setup, tmp_path):
    c, learner, _, _ = setup(steps=4, updates=1)
    chunk = sample(learner, n=4)
    spool = A.AtomicChunkQueue(tmp_path/'transport', max_bytes=2**24, max_chunks=8,
                               runtime_manifest=learner.runtime_manifest)
    receipt = spool.write(chunk)
    boundary = A.Boundary('budget', 4, 0, 0, True, False, 0)
    publication = dict(sequence=0, game_id='game', game_sequence=0, engine_tick=106, terminal=True,
                       completed=dict(game_id='game', accepted_plays=30, seconds=300.))
    update = D.relay_publication(c, spool, chunk.actor_id, dict(receipt=asdict(receipt), boundary=asdict(boundary),
                                                              publication=publication))
    assert update.version == 0  # final budget callback does not grant more polls
    result = c.finalize()
    assert result['generated'] == result['trained'] == 4 and result['discarded'] == 0
    assert (spool.root/receipt.name).exists()  # child alone acknowledges transport
    spool.acknowledge(receipt)
    assert not (spool.root/receipt.name).exists()


@pytest.mark.parametrize('field', ['native_failure', 'search_failures', 'own_state_break', 'panics', 'error'])
def test_all_live_execution_failure_fields_stop(field):
    with pytest.raises(RuntimeError):
        D.execution_ok({field: 'fixture-failure'})
    D.execution_ok({'native_failure': None, 'completed': 10, 'source': 'search'})


def test_missing_gate_evidence_never_implies_precision_or_launch_go(tmp_path, monkeypatch):
    monkeypatch.setattr(D, 'source_digest', lambda: 'c'*64)
    config = dict(schema='pv1-rl-launch-v1', size='M', precision='float64',
                  gate_receipt=dict(path=str(tmp_path/'absent-go'), sha256='a'*64),
                  precision_registration=dict(path=str(tmp_path/'absent-precision'), sha256='b'*64))
    result = D.audit(config, verify_inputs=False)
    assert result['status'] == 'NO-GO'
    assert {s.split(':')[0] for s in result['failures']} == {
        'launch review', 'precision', 'paired league registration'}


def test_leased_fallback_can_never_authorize_registered_training(tmp_path, monkeypatch):
    monkeypatch.setattr(D, 'source_digest', lambda: 'c'*64)
    config = dict(qualification_only=True)
    result = D.audit(config, verify_inputs=False)
    assert any(f.startswith('placement:') for f in result['failures'])
    result = D.audit(config, verify_inputs=False, qualification=True)
    assert not any(f.startswith(('placement:', 'paired league registration:')) for f in result['failures'])


def test_shared_bootstrap_preserves_original_pcg64_draw_sequence():
    import numpy as np
    from bot.pretrain_v1.compare_arms import estimate
    diffs = {'a': [-1., 0., 1.], 'b': [0., 1.]}
    expected = np.zeros(257)
    generator = np.random.Generator(np.random.PCG64(73))
    for values in diffs.values():
        expected += generator.choice(np.array(values), size=(257, len(values))).mean(1)/2
    point, ci = estimate(diffs, list(diffs), np.random.Generator(np.random.PCG64(73)), 257)
    assert point == .25
    assert ci == [float(np.quantile(expected, .025)), float(np.quantile(expected, .975))]


def test_freezer_pairs_all_three_seeds_and_rejects_physical_source_overlap(tmp_path):
    from bot.pretrain_v1.prepare_registered_rl import freeze, reference
    def artifact(name, value):
        p = tmp_path/name
        p.write_bytes(S.encoded(value))
        return reference(p)
    train = dict(populations(), role='training-only', physical_source_ids=['training-game'])
    evaluation = dict(populations(), role='evaluation-only', physical_source_ids=['evaluation-game'])
    source = artifact('prior-source', {'fixture': True})
    bundle = dict(populations=artifact('train', train), evaluation_populations=artifact('eval', evaluation),
        excluded_seeds=artifact('excluded', dict(sources=[source], seeds=[12])),
        audits=dict(defense=source, spell=source), audit_input_manifest=artifact('audits', [source]),
        evaluation_seed_base=20261022000000, common={}, anchors=dict.fromkeys(S.ANCHORS, source),
        model_cfg=dict.fromkeys(S.ANCHORS, source))
    refs = freeze(bundle, tmp_path/'frozen')
    assert len(refs) == 8
    seen = set()
    for seed in S.SEEDS:
        m = json.loads((tmp_path/f'frozen/M-{seed}.json').read_text())
        s = json.loads((tmp_path/f'frozen/S100-{seed}.json').read_text())
        assert m['banks'] == s['banks']
        banks = json.loads(S.pinned(m['banks']).read_text())
        current = {r['seed'] for r in banks['primary']+banks['dev']['0']}
        assert len(current) == 1800 and not current & seen
        seen |= current
    fallback = json.loads((tmp_path/f'frozen/SOAK-M-{S.SEEDS[0]}.json').read_text())
    assert fallback['qualification_only'] is True and fallback['host'] == '127x09'
    evaluation['physical_source_ids'] = ['training-game']
    bundle['evaluation_populations'] = artifact('overlap', evaluation)
    with pytest.raises(ValueError, match='disjoint'):
        freeze(bundle, tmp_path/'must-not-exist')
    assert not (tmp_path/'must-not-exist').exists()


def test_evaluation_draws_are_not_wins_and_corrupt_identity_is_fatal():
    case = dict(seed=12, seat=0, decks=[list(S.HOG), list(S.HOG)])
    row = dict(case=case, case_sha256=S.digest(case), policy_sha256='p', bank_sha256='b', runtime_manifest={},
               result=dict(terminal=True, winner=None, seed=12, decks=case['decks']), win=0, draw=1, score=.5)
    assert E.validate_result(row, case, policy='p', bank='b', runtime={}) == 0
    row['error'] = 'fixture'
    assert E.validate_result(row, case, policy='p', bank='b', runtime={}) is None
    with pytest.raises(ValueError, match='provenance'):
        E.validate_result(row, case, policy='other', bank='b', runtime={})


def test_all_assigned_comparison_keeps_failures():
    result = E.paired_bootstrap({0: 1, 1: None, 2: 0}, {0: 0, 1: 1, 2: None}, draws=128)
    assert result['assigned'] == 3 and result['complete_pairs']['n'] == 1
    assert result['all_assigned_lower']['n'] == 3
    assert result['all_assigned_lower']['delta'] == pytest.approx(-1/3)
    assert not result['a_wins_by_registered_rule']


def test_real_process_atomic_transport_two_updates_and_adam_boundary(setup, admitted, tmp_path):
    """The child generates synthetic test features only, never an engine game."""
    from multiprocessing import Pipe
    from bot.pretrain_v1 import rl_learner as L
    parent_learner = learner(admitted, updates=2)
    coordinator, _, _, _ = setup(steps=8, updates=2, real=parent_learner)
    anchor = dict(admitted)
    anchor['anchor_path'] = str(anchor['anchor_path'])
    inputs = tmp_path/'inputs.json'
    inputs.write_text(json.dumps(anchor))
    spool = A.AtomicChunkQueue(tmp_path/'subprocess-spool', max_bytes=2**24, max_chunks=8,
                               runtime_manifest=parent_learner.runtime_manifest)
    parent, child = Pipe(duplex=True)
    program = '''
import json,sys
from dataclasses import asdict
from pathlib import Path
from multiprocessing.connection import Connection
from bot.pretrain_v1 import rl_driver as D, stream_actor as A
from bot.pretrain_v1.tests.test_rl_learner import learner,chunk
inputs,spool_root,fd,checkpoints=sys.argv[1:]
l=learner(json.loads(Path(inputs).read_text()),updates=2)
q=A.AtomicChunkQueue(spool_root,max_bytes=2**24,max_chunks=8,runtime_manifest=l.runtime_manifest)
connection=Connection(int(fd))
for version in range(2):
    c=A.Chunk(**vars(chunk(l,n=8,actor_id='a')))
    receipt=q.write(c)
    total=(version+1)*8
    boundary=A.Boundary('budget' if version==1 else 'quota',total,16-total,0,True,False,0)
    publication=dict(sequence=version,game_id='g'+str(version),game_sequence=version,
                     engine_tick=126,terminal=True,completed=dict(game_id='g'+str(version),accepted_plays=30,seconds=300.))
    D.send(connection,dict(kind='publish',generated=total,receipt=asdict(receipt),
                          boundary=asdict(boundary),publication=publication))
    permit=D.receive(connection,20)
    q.acknowledge(receipt)
    if version==0:
        assert D.S.file_sha(permit['checkpoint']['path'])==permit['checkpoint']['sha256']
        l.load_checkpoint(permit['checkpoint']['path'])
D.send(connection,dict(kind='done',generated=16,discarded=0))
connection.close()
'''
    process = subprocess.Popen([sys.executable, '-c', program, str(inputs), str(spool.root),
                                str(child.fileno()), str(coordinator.path)], pass_fds=(child.fileno(),))
    child.close()
    try:
        for version in range(2):
            message = D.receive(parent, 20)
            assert message['generated'] == (version+1)*8
            update = D.relay_publication(coordinator, spool, 'a', message)
            permit = D.checkpoint_permit(coordinator.path, update.version, update.policy_sha256, update.quota_steps)
            D.send(parent, permit)
        assert D.receive(parent, 20) == dict(kind='done', generated=16, discarded=0)
        assert process.wait(timeout=20) == 0
        final = coordinator.finalize()
        assert final['generated'] == final['accepted'] == final['trained'] == 16
        assert final['discarded'] == 0 and final['updates'] == 2
        assert not any(p.is_dir() for p in spool.root.iterdir())
        proof = learner(admitted, updates=2)
        proof.load_checkpoint(coordinator.path/'update-02.pt')
        assert proof.version == 2 and proof.optimizer_steps == 8
    finally:
        parent.close()
        process.wait(timeout=20)
