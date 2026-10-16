"""Full-pool validation controller: isolated games, paired case blocks, no search changes."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import traceback

import fullpool_eval as fp

ROOT, DEST = fp.ROOT, fp.JOB
REPO = Path('/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool')
PY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'


def remote(argv):
    return subprocess.check_output(['ssh', '127x05', shlex.join(list(map(str, argv)))], text=True)


def verify(meta):
    assert meta['source_sha256'] == {str(p.relative_to(REPO)): fp.sha(p)
        for directory in ('bot', 'reports/explore/x4s') for p in sorted((REPO / directory).rglob('*.py'))}
    assert all(fp.sha(ROOT / path) == digest for path, digest in meta['helper_sha256'].items())
    assert all(fp.sha(DEST / path) == digest for path, digest in meta['models'].items())
    assert fp.sha(DEST / 'vocab-combined.json') == meta['vocab_sha256']
    fp.MODEL_ROOT = DEST / 'models'
    fp.FAST = f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
    fp.OLD_FAST = f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'


def configure(players, seat, player_name, config):
    own = players[seat].rec.inner
    if config['mode'] == 'no-wall':
        own.search.set_deadline(None, 1)
        for field in ('native_threads', 'pool_size', 'chunks'):
            setattr(own.search, field, int(config[field]))
        own.deadline_seconds = None
        # Recorder snapshots the factory's .2 deadline at construction. Clear
        # that facade too: play_match reads it to apply lateness.
        players[seat].rec.deadline_seconds = None
        assert own.search.deadline_seconds is None and players[seat].deadline_seconds is None
    else:
        assert config['mode'] == 'wall200' and own.deadline_seconds == .2
    own.name = player_name
    players[seat].rec.name = player_name


def game(rt, strong_rt, vocab, meta, bank, case, candidate, player_name, output, block):
    from bot.players.royalesim_match import play_match
    from bot.search.lopp import FAILURES
    import time
    row = dict(case, candidate=candidate, player=player_name, stage='validation',
               scenario=meta['scenario'], host=os.uname().nodename, started_utc=fp.utc(),
               bank_sha256=fp.sha(DEST / 'validation/bank.json'), block=block)
    started = time.monotonic()
    ps = {}
    try:
        seat = case['seat']
        own = [meta['candidates'][candidate][i] for i in case['own_permutation']]
        own_levels = meta['candidate_plans'][candidate]['levels']
        decks = [own, case['opponent_deck']] if seat == 0 else [case['opponent_deck'], own]
        levels = [own_levels, case['opponent_levels']] if seat == 0 else [case['opponent_levels'], own_levels]
        factory = fp.LIVE + ('-res' if player_name.endswith('-res') else '')
        ps = fp.players(rt, factory, case['opponent'], seat, strong_rt=strong_rt)
        configure(ps, seat, player_name, meta['player_config'])
        before = Counter(FAILURES)
        result = play_match(rt, ps, seed=case['seed'], decks=decks, vocab=vocab,
                            client='16.402', levels=levels, tower_levels=[6, 6], verbose=True)
        result['public_diagnostics'] = {str(side): fp.diagnostics(player, result) for side, player in ps.items()}
        logs = result.pop('play_log'); result.pop('command_events', None)
        failures = dict(Counter(FAILURES) - before)
        errors = {str(side): [d for d in getattr(player.rec.inner, 'decisions', [])
                             if 'error' in d or d.get('native_failures')] for side, player in ps.items()}
        unmapped = {k: v for k, v in result['translator'].items() if v and ('unmapped' in k or 'missing' in k)}
        issues = []
        if not result['terminal']: issues.append('nonterminal')
        if failures: issues.append('native failures')
        if any(errors.values()): issues.append('live errors')
        if result['channels'][seat]['rejected']: issues.append('our command rejections')
        if unmapped: issues.append('unmapped public rows')
        if meta['player_config']['mode'] == 'no-wall' and result['public_diagnostics'][str(seat)]['cutoff_hits']:
            issues.append('unexpected no-wall cutoff')
        row.update(result=result, win=int(result['winner'] == seat), draw=int(result['winner'] is None),
                   score=.5 if result['winner'] is None else float(result['winner'] == seat),
                   card_plays=dict(Counter(card for _, card, _, ok in logs[seat] if ok)),
                   failures=failures, live_errors=errors, unmapped=unmapped, issues=issues)
    except BaseException as error:
        row.update(error=repr(error), traceback=traceback.format_exc())
    finally:
        # Each isolated game owns these verified library child processes.
        from bot.search import lopp_fast
        for pool in lopp_fast._POOLS.values():
            pool.close()
    row['wall_seconds'] = time.monotonic() - started
    fp.dump(output, row)


def work(label, wid, meta, bank, rt, strong_rt, vocab):
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGUSR1, stop)
    worker = f'{os.uname().nodename}-{label}-{wid}'
    arms = [(candidate, player) for candidate in bank['candidates'] for player in bank['players']]
    completed = 0
    while not stopping and not (DEST / f'PAUSE-{label}').exists():
        claim = json.loads(remote([PY, ROOT / 'fullpool_queue.py', '--worker', worker]))
        index = claim['index']
        if index is None:
            break
        case = bank['cases'][index]
        order = list(range(len(arms)))
        random.Random(case['seed'] ^ 0xA4A4).shuffle(order)
        block = dict(worker=worker, controller_label=label, worker_pid=os.getpid(), case_index=index,
                     arm_order=[arms[a] for a in order], cpu_slots=meta['player_config']['cpu_slots'],
                     affinity=sorted(os.sched_getaffinity(0)))
        fp.dump(DEST / f'active-{label}-{wid}.json', dict(utc=fp.utc(), **block))
        for position, arm in enumerate(order):
            candidate, player = arms[arm]
            output = DEST / 'validation/rows' / f'{index*len(arms)+arm:06d}.json'
            assert not output.exists(), ('unexpected existing row in newly claimed block', output)
            if meta['player_config']['mode']=='no-wall' and meta['player_config']['cpu_slots']==1:
                # Standard headline semantics: fresh Players/MatchContext with a
                # persistent Runtime; serial scoring has no background pool.
                game(rt,strong_rt,vocab,meta,bank,case,candidate,player,output,
                     dict(block,arm_position=position,game_pid=os.getpid()))
            else:
                pid = os.fork()
                if pid == 0:
                    signal.signal(signal.SIGTERM, signal.SIG_DFL)
                    signal.signal(signal.SIGUSR1, signal.SIG_DFL)
                    try:
                        game(rt, strong_rt, vocab, meta, bank, case, candidate, player, output,
                             dict(block, arm_position=position, game_pid=os.getpid()))
                    finally:
                        os._exit(0)
                _, status = os.waitpid(pid, 0)
                assert status == 0 and output.exists(), (pid, status, output)
            row = json.loads(output.read_text())
            subprocess.run(['rsync', '-a', str(output), f'127x05:{DEST}/validation/rows/'], check=True)
            if row.get('error') or row.get('issues'):
                remote(['touch', DEST / 'STOP'])
                raise RuntimeError(('unclean game retained', str(output), row.get('issues'), row.get('error')))
            completed += 1
        fp.dump(DEST / f'block-complete-{index:04d}.json', dict(utc=fp.utc(), **block))
    fp.dump(DEST / f'worker-complete-{label}-{wid}.json', dict(utc=fp.utc(), games=completed, stopping=stopping))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--workers', required=True, type=int)
    args = parser.parse_args()
    assert 1 <= args.workers <= 40
    meta = json.loads((DEST / 'manifest.json').read_text())
    bank = json.loads((DEST / 'validation/bank.json').read_text())
    assert bank['manifest_sha256'] == fp.sha(DEST / 'manifest.json')
    verify(meta)
    pgid = os.getpgrp()
    slots = 0
    for path in Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims').glob('lease-*'):
        try:
            count, group = map(int, path.read_text().split())
        except (FileNotFoundError, ValueError):
            continue
        if group == pgid:
            slots = max(slots, count)
    assert slots >= args.workers*meta['player_config']['cpu_slots'] + 2, ('insufficient CPU reservation', slots)
    rt = fp.runtime(fp.BELIEF); strong_rt = fp.runtime('c56')
    for current in (rt, strong_rt):
        assert current.pins['native_sha256'] == meta['native_sha256']
        assert current.pins['gamedata_sha256'] == meta['gamedata_sha256']
        fp.install_placement(current)
        current.STUDENT
    vocab = json.loads((DEST / 'vocab-combined.json').read_text())
    def pause(signum, frame):
        (DEST / f'PAUSE-{args.label}').touch()
    signal.signal(signal.SIGTERM, pause); signal.signal(signal.SIGUSR1, pause)
    children = []
    for wid in range(args.workers):
        pid = os.fork()
        if pid == 0:
            try:
                work(args.label, wid, meta, bank, rt, strong_rt, vocab)
            except BaseException as error:
                fp.dump(DEST / f'worker-error-{args.label}-{wid}.json', dict(utc=fp.utc(), error=repr(error), traceback=traceback.format_exc()))
                os._exit(1)
            os._exit(0)
        children.append(pid)
    fp.dump(DEST / f'controller-{args.label}.json', dict(utc=fp.utc(), pid=os.getpid(), pgid=pgid,
                                                     worker_pids=children, cpu_lease=slots))
    statuses = {pid: os.waitpid(pid, 0)[1] for pid in children}
    fp.dump(DEST / f'controller-finished-{args.label}.json', dict(utc=fp.utc(), statuses=statuses))
    assert not any(statuses.values()), statuses


if __name__ == '__main__':
    main()
