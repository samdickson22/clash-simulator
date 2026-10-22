"""Disposable CPU actor and IPC fixtures. Never import or launch an engine."""
import argparse
from dataclasses import asdict
import json
from multiprocessing.connection import Connection
import os
from pathlib import Path
import signal
import sys
import time

# File entry mirrors the real driver's process transport, without bootstrapping.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bot.pretrain_v1 import rl_driver as D, stream_actor as A, actor_worker as W


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--config')
    parser.add_argument('--out')
    parser.add_argument('--worker-spec')
    parser.add_argument('--fd', type=int)
    args = parser.parse_args()
    spec = json.loads(Path(args.worker_spec).read_text())
    config = json.loads(Path(args.config).read_text())
    connection = Connection(args.fd)
    mode = config['fixture_mode']
    if mode == 'not-ready':
        time.sleep(config.get('fixture_hang_seconds', 60))
        return
    if mode in ('hung-engine', 'partial-receiver', 'startup-error'):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (Path(args.out)/f'fixture-ready-{spec["actor_id"]}').touch()
    D.send(connection, dict(kind='ready', generated=spec.get('restore', {}).get('record', {}).get('counters', {}).get('generated_steps', 0), pid=os.getpid()))
    if mode in ('hung-engine', 'partial-receiver', 'startup-error'):
        if mode == 'partial-receiver':
            os.write(connection.fileno(), b'\0\0')
        time.sleep(config.get('fixture_hang_seconds', 60))
        return
    if mode == 'cooperative':
        while not Path(spec['qualification_stop_file']).exists() and not Path(spec['stop_file']).exists():
            time.sleep(.01)
        try:
            D.send(connection, dict(kind='qualification_stopped', generated=0))
        except (BrokenPipeError, EOFError):
            pass  # same permitted shutdown race as the production worker
        return
    assert mode == 'recycle'
    import pytest
    from bot.pretrain_v1.tests import test_actor_worker as T
    manifest = json.loads((Path(args.out)/'runtime.json').read_text())
    schedule = D.S.Schedule(json.loads(D.S.pinned(config['populations']).read_text()), config['seed'])
    spool = A.AtomicChunkQueue(spec['spool'], max_bytes=spec['spool_bytes'], max_chunks=spec['spool_chunks'],
                               runtime_manifest=manifest)
    sequence = 0
    def publish(chunk, boundary):
        nonlocal sequence
        receipt = spool.write(chunk)
        pin = dict(family='current', version=0, policy_sha256=chunk.policy_sha256)
        publication = dict(sequence=sequence, game_id='fixture-game', game_sequence=0, engine_tick=108,
                           terminal=True, completed=dict(game_id='fixture-game', accepted_plays=30, seconds=300.))
        D.send(connection, dict(kind='publish', generated=chunk.generated_steps, receipt=asdict(receipt),
                                boundary=asdict(boundary), publication=publication, opponent=pin))
        permit = D.receive(connection, 10)
        assert permit['kind'] == 'permit'
        spool.acknowledge(receipt)
        sequence += 1
        return A.PolicyUpdate(permit['version'], permit['policy_sha256'])
    m = T.model()
    if 'restore' not in spec:
        a = A.StreamingPolicyOursPlayer(m, publish, actor_id=spec['actor_id'], seed=config['seed'],
            anchor_sha256='a'*64, provenance_sha256=A.manifest_sha256(manifest), opponent_id='current',
            budget_steps=spec['quota']*spec['updates'], quota_steps=spec['quota'], chunk_rows=128)
        counter = D.GenerationCounter(spec['generation_counter'])
        a = D.attach_counter(a, counter)
        with pytest.MonkeyPatch.context() as patch:
            T.game(a, patch)
        assert a.completed_games == 1 and a.unfinished_games == 0
        cursor = dict(publication_sequence=sequence, next_game_sequence=1, seed=a.seed, actor_id=a.actor_id,
                      schedule_sha256=schedule.sha256, runtime_provenance_sha256=a.provenance_sha256)
        cp = W.ActorCheckpoint.capture(a, cursor)
        try:
            W.ActorCheckpoint.restore_record(cp.record, m, publish, expected_sha256=cp.sha256,
                    driver_state=cursor, claim_directory=spec['claims'])
        except W.WorkerError as ex:
            assert 'still live' in str(ex)
        else:
            raise AssertionError('live source handoff admitted')
        D.send(connection, dict(kind='recycle', record=cp.record, sha256=cp.sha256, cursor=cursor,
                               generated=a.generated_steps))
        counter.close()
    else:
        restore = spec['restore']
        a = W.ActorCheckpoint.restore_record(restore['record'], m, publish, expected_sha256=restore['sha256'],
                driver_state=spec['cursor'], claim_directory=spec['claims'])
        # The actual driver's first successor must preserve R41's refusal rules.
        try:
            W.ActorCheckpoint.restore_record(restore['record'], m, publish, expected_sha256=restore['sha256'],
                    driver_state=spec['cursor'], claim_directory=spec['claims'])
        except W.WorkerError as ex:
            assert 'already claimed' in str(ex)
        else:
            raise AssertionError('duplicate handoff admitted')
        D.S.require(a.generated_steps == 4 and a.version == 0 and a.completed_games == 1, 'restore drift')
        (Path(args.out)/'successor-verified').write_text(json.dumps(dict(generated=a.generated_steps,
            completed=a.completed_games, unfinished=a.unfinished_games, version=a.version)))
        while not Path(spec['qualification_stop_file']).exists() and not Path(spec['stop_file']).exists():
            time.sleep(.01)
        try:
            D.send(connection, dict(kind='qualification_stopped', generated=a.generated_steps))
        except (BrokenPipeError, EOFError):
            pass
    connection.close()


if __name__ == '__main__':
    main()
