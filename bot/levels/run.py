"""One fork per (case, arm), sharing a single parent-built Runtime and vocabulary.

Jobs are launched case-major. Atomic rows are the resume boundary: successful
rows require the same source/runtime identity; error rows are retried. Numbered
launch receipts are never replaced. B exports must already exist before forking.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time
import traceback

from .bank import REPO, utcnow

BASE_PLAYER = 'K4L-R-gs-rw-fc'
ENV_PATH = Path('/mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh')
SOURCE_DIRS = ('bot/levels', 'bot/players', 'bot/search', 'bot/cards', 'bot/fullpool',
               'bot/eval', 'reports/explore/x4s')


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, path)


def source_hashes():
    paths = sorted(p for directory in SOURCE_DIRS for p in (REPO / directory).glob('*')
                   if p.suffix in ('.py', '.sh') and p.is_file())
    paths.append(REPO / 'bot/live/levels.py')  # B0's actual root implementation.
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_hashes(paths):
    return {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in sorted(set(map(Path, paths)))}


def behavior_env():
    """Game/import settings, excluding CPU admission and unused log destinations."""
    noise = {'BOT_CPU', 'BOT_CPU_CAP', 'BOT_CPU_IGNORE', 'BOT_PPLAY_LOG'}
    names = {'PYTHONHASHSEED', 'PYTHONPATH', 'PYTHONOPTIMIZE', 'CUDA_VISIBLE_DEVICES',
             'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'RAYON_NUM_THREADS',
             'NUMPY_MADVISE_HUGEPAGE'}
    names.update(k for k in os.environ if k.startswith(('BOT_', 'CLASHER_')) and k not in noise)
    return {k: os.environ.get(k) for k in sorted(names)}


def runtime_files(root):
    """Frozen import roots and referenced weights/data; never scan job outputs."""
    council = root / 'reports/strategy_council_20260928'
    directories = [root / p for p in ('engine-rs', 'src', 'student-source', 'reports/explore/s1',
                   'reports/explore/e1', 'reports/perf-audit/quickwins')]
    directories += [council / p for p in ('engine-speed', 'search-noise-s4', 'search-noise-s6')]
    paths = list(root.glob('*.py'))
    paths += [p for directory in directories for p in directory.rglob('*.py')]
    native = Path(os.environ.get('CLASHER_DELAY_NATIVE_DIR', root / 'native'))
    paths += list(native.glob('*.so')) + list(native.glob('*.py'))
    paths += [ENV_PATH, root / 'main02.pt', root / 'R3a.pt',
              Path(os.environ.get('CLASHER_ROOT', root)) / 'gamedata.json',
              council / 'c56/engine/root-v3/human_deck_catalog.json',
              Path(os.environ.get('CLASHER_LOPP_MODELS', '/mpac/sdicks02/jobs/clasher/bot-lopp-models')) / 'pool.npz',
              REPO / 'bot/players/royalesim_vocab.json']
    # Bind the simulator implementation, not just its version string.
    spec = util.find_spec('royalesim')
    if spec is None or spec.origin is None:
        raise ValueError('RoyaleSim implementation not found')
    paths.append(Path(spec.origin))
    for directory in spec.submodule_search_locations or []:
        paths += [p for p in Path(directory).rglob('*') if p.suffix in ('.py', '.so')]
    return file_hashes(paths)


def invocation_identity(args, rt, vocab, manifest, inputs, sources, bank_sha256):
    """Complete, JSON-frozen identity, constructed before any successful-row reuse."""
    return json.loads(json.dumps(dict(protocol='levels-harness-v2', base_player=args.base_player,
        client=args.client, all11_gate=args.all11_gate, arms=sorted(args.arms.split(',')),
        bank_sha256=bank_sha256, source_sha256=sources, runtime_files=inputs,
        runtime_pins=os.environ.get('CLASHER_BOT_RUNTIME_PINS', 'r1'),
        runtime_path=str(rt.root.resolve()), pins=rt.pins, behavior_env=behavior_env(),
        python=sys.version, packages={name: metadata.version(name) for name in ('numpy', 'torch', 'royalesim')},
        levels_scope=rt.levels_scope, effective_prior_sha256=digest(rt.PRIOR),
        config_sha256=digest(rt.R.config), vocab_sha256=digest(vocab), level_cache=manifest)))


def identity_problems(identity):
    """An old/empty receipt is readable, but cannot verify an experiment."""
    if not isinstance(identity, dict):
        return ['missing v2 experiment identity']
    required = {'protocol', 'base_player', 'client', 'all11_gate', 'arms', 'bank_sha256',
        'source_sha256', 'runtime_files', 'runtime_pins', 'runtime_path', 'pins', 'behavior_env',
        'python', 'packages', 'levels_scope', 'effective_prior_sha256', 'config_sha256',
        'vocab_sha256', 'level_cache'}
    problems = [f'missing identity field {k}' for k in sorted(required - identity.keys())]
    if identity.get('protocol') != 'levels-harness-v2':
        problems.append('identity protocol is not levels-harness-v2')
    def sha(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    for name in ('bank_sha256', 'effective_prior_sha256', 'config_sha256', 'vocab_sha256'):
        if not sha(identity.get(name)):
            problems.append(f'invalid identity digest {name}')
    for name in ('source_sha256', 'runtime_files'):
        values = identity.get(name)
        if not isinstance(values, dict) or not values or not all(isinstance(k, str) and k and sha(v) for k, v in values.items()):
            problems.append(f'missing substantive identity {name}')
    for name in ('base_player', 'client', 'runtime_pins', 'runtime_path', 'python'):
        if not isinstance(identity.get(name), str) or not identity[name]:
            problems.append(f'invalid identity {name}')
    for name in ('pins', 'behavior_env', 'packages', 'levels_scope'):
        if not isinstance(identity.get(name), dict) or not identity[name]:
            problems.append(f'missing substantive identity {name}')
    for name in ('native_sha256', 'v1_sha256', 'r3a_sha256'):
        if not isinstance(identity.get('pins'), dict) or not sha(identity['pins'].get(name)):
            problems.append(f'missing identity pin {name}')
    for name in ('numpy', 'torch', 'royalesim'):
        if not isinstance(identity.get('packages'), dict) or not identity['packages'].get(name):
            problems.append(f'missing identity package {name}')
    scope = identity.get('levels_scope')
    if not isinstance(scope, dict) or scope.get('restricted_sha256') != identity.get('effective_prior_sha256'):
        problems.append('scope and effective prior digests disagree')
    arms = identity.get('arms')
    if not isinstance(arms, list) or not arms or any(a not in ('A', 'B0', 'B') for a in arms) or len(set(arms)) != len(arms):
        problems.append('invalid identity arms')
    if type(identity.get('all11_gate')) is not bool:
        problems.append('invalid identity all11_gate')
    sources = identity.get('source_sha256')
    if isinstance(arms, list) and 'B0' in arms and (not isinstance(sources, dict) or 'bot/live/levels.py' not in sources):
        problems.append('missing B0 root source identity')
    if isinstance(arms, list) and 'B' in arms:
        cache = identity.get('level_cache')
        if not isinstance(cache, dict) or not cache.get('supported') or not cache.get('exports'):
            problems.append('missing substantive B level-cache identity')
        else:
            entries = [cache['supported'], *cache['exports'].values()] if isinstance(cache['exports'], dict) else []
            if not entries or any(not isinstance(e, dict) or not all(sha(e.get(k)) for k in
                                 ('raw_sha256', 'loaded_sha256')) for e in entries):
                problems.append('missing B raw/canonical cache digests')
    return problems


def diagnostics_complete(row, *, require_exit=True):
    failures, channels = row.get('failures'), row.get('channels')
    if not isinstance(failures, dict) or not all(type(n) is int and n >= 0 for n in failures.values()):
        return False
    if not isinstance(channels, dict):
        return False
    for seat in (0, 1):
        ch = channels.get(str(seat), channels.get(seat))
        if not isinstance(ch, dict) or type(ch.get('rejected')) is not int or ch['rejected'] < 0:
            return False
    return not require_exit or type(row.get('child_exit_code')) is int


def row_issues(row, *, require_exit=True):
    """A scored fallback or rejected command still invalidates experimental evidence."""
    failures, channels = row.get('failures'), row.get('channels')
    failures = failures if isinstance(failures, dict) else {}
    channels = channels if isinstance(channels, dict) else {}
    return dict(errors=int('error' in row), native_failures=sum(n for n in failures.values() if type(n) is int and n >= 0),
                rejections=sum(c['rejected'] for c in channels.values() if isinstance(c, dict)
                               and type(c.get('rejected')) is int and c['rejected'] >= 0),
                missing_diagnostics=int(not diagnostics_complete(row, require_exit=require_exit)),
                child_failures=int(row.get('child_exit_code', 0) not in (0, None)),
                controller_prior_failures=int(row.get('protocol') == 'levels-harness-v2' and not prior_evidence_ok(row)),
                nonterminal=int('error' not in row and row.get('terminal') is not True))


def prior_evidence_ok(row):
    expected = row.get('levels_scope', {}).get('restricted_sha256')
    observations = row.get('controller_prior_sha256', {})
    return bool(expected) and all(observations.get(phase) == {'0': expected, '1': expected}
                                  for phase in ('before', 'after'))


def capture_controller_priors(row, players, identity, phase):
    observed = {str(seat): digest(player.rt.PRIOR) for seat, player in players.items()}
    row.setdefault('controller_prior_sha256', {})[phase] = observed
    expected = identity['levels_scope']['restricted_sha256']
    if observed != {'0': expected, '1': expected}:
        raise ValueError(f'controller prior mismatch {phase} play: {observed}; expected {expected}')


def resume_done(path, case, arm, identity):
    """Legacy successful rows without complete provenance fail closed."""
    if not path.exists():
        return False
    old = json.loads(path.read_text())
    if old.get('arm') != arm or any(old.get(k) != case[k] for k in
            ('index', 'seed', 'seat', 'opponent', 'decks', 'profile', 'view')):
        raise ValueError(f'existing row belongs to a different case/arm: {path}')
    if any(row_issues(old).values()):
        return False
    changed = [k for k, v in identity.items() if k not in old or old[k] != v]
    if changed:
        raise ValueError(f'existing successful row identity differs ({", ".join(changed)}): {path}')
    return True


def write_launch(out, launch):
    """Exclusive numbered receipts preserve previous launches, including launch.json."""
    payload = json.dumps(launch, indent=2, sort_keys=True) + '\n'
    numbers = [p.stem.removeprefix('launch-') for p in out.glob('launch-*.json')]
    number = max((int(n) for n in numbers if n.isdigit()), default=0) + 1
    while True:
        path = out / f'launch-{number:05d}.json'
        try:
            with path.open('x') as stream:
                stream.write(payload)
            return path
        except FileExistsError:
            number += 1


def validate_all11(case):
    """Validate both true seats and the complete fair planner view for parity."""
    try:
        decks, prof, view, seat = case['decks'], case['profile'], case['view'], case['seat']
        valid = (seat in (0, 1) and len(decks) == len(prof['cards']) == 2
                 and prof['towers'] == [11, 11]
                 and view['own_tower'] == view['opp_tower'] == 11
                 and all(set(deck) <= set(levels) and all(v == 11 for v in levels.values())
                         for deck, levels in zip(decks, prof['cards']))
                 and set(decks[seat]) <= set(view['own_levels'])
                 and all(v == 11 for v in view['own_levels'].values()))
    except (KeyError, TypeError, AttributeError, IndexError):
        valid = False
    if not valid:
        raise ValueError(f'all11 gate requires complete level-11 true profile and view: case {case.get("index")}')


def preload_configs(rt, jobs, all11_gate):
    """Only planner-known levels; missing/incomplete exports abort before any fork."""
    if not any(arm == 'B' for _, arm, _ in jobs):
        return
    from .configs import LevelConfigs, base_cards
    from .profile import OpponentEstimate
    lc = LevelConfigs(rt)

    def refuse_export(level, cards=None):
        raise ValueError(f'runner cannot build missing level export L{level}: {lc.path(level)}')

    # load()/supported() may otherwise build on a cache miss, including in a child.
    lc.build = refuse_export
    levels = {11}
    if not all11_gate:
        estimate = OpponentEstimate(rt)
        levels.update(estimate(card) for card in base_cards(rt.R.config))
        for case, arm, _ in jobs:
            if arm == 'B':
                levels.update(case['view']['own_levels'].values())
    exports = {}
    for level in sorted(levels):
        path = lc.path(level)
        if not path.is_file():
            raise ValueError(f'required level export missing: {path}')
        raw = path.read_bytes()
        data = json.loads(raw)
        lc.levels[level] = data
        exports[str(level)] = dict(path=str(path.resolve()), cards=len(data['cards']),
            raw_sha256=hashlib.sha256(raw).hexdigest(), loaded_sha256=digest(data), errors=data.get('errors', {}))

    def frozen_load(level):
        if int(level) not in lc.levels:
            raise ValueError(f'cannot build or read unregistered export L{level} after preload')
        return lc.levels[int(level)]

    lc.load = frozen_load
    reference = lc.load(11)
    missing = set(base_cards(rt.R.config)) - (set(reference['cards']) | set(reference.get('errors', {})))
    if reference.get('level') != 11 or missing:
        raise ValueError(f'incomplete L11 export: missing={sorted(missing)}')
    supported = lc.supported()  # Creates supported.json from the existing L11 export if absent.
    if not (lc.dir / 'supported.json').is_file():
        raise ValueError(f'supported manifest missing: {lc.dir}')
    raw = (lc.dir / 'supported.json').read_bytes()
    support_data = json.loads(raw)
    reference_sha = hashlib.sha256(json.dumps(rt.R.config, sort_keys=True).encode()).hexdigest()
    if (set(support_data['cards']) != supported or support_data.get('comparison') != 'native-json-v1'
            or support_data.get('reference_sha256') != reference_sha):
        raise ValueError('supported manifest changed while loading')
    lc._supported = set(support_data['cards'])
    manifest = dict(cache_dir=str(lc.dir.resolve()), supported=dict(data=support_data,
        raw_sha256=hashlib.sha256(raw).hexdigest(), loaded_sha256=digest(support_data)), exports=exports)
    for level in sorted(levels):
        data = lc.load(level)
        errors = data.get('errors', {})
        missing = set(supported) - (set(data['cards']) | set(errors))
        if data.get('level') != level or missing:
            raise ValueError(f'incomplete L{level} export: missing={sorted(missing)}')
    rt._level_configs = lc
    return manifest


def level_diagnostics(player):
    """Observe only: do not construct configs that the game never requested."""
    root = getattr(player, 'level_root', None)
    return dict(stats=dict(getattr(root, 'stats', {})),
                seat_configs={str(seat): entry[2] for seat, entry in getattr(root, '_cfg', {}).items()})


def child(rt, vocab, case, arm, args, path, identity):
    """Write failures as rows too; always terminate without parent cleanup."""
    started, cpu0 = time.monotonic(), time.process_time()
    row = dict(case, arm=arm, **identity,
               host=socket.gethostname(), pid=os.getpid(), started=utcnow())
    failures, before = None, Counter()
    player, players = None, {}
    status = 0
    try:
        if source_hashes() != identity['source_sha256']:
            raise ValueError('source changed after launch; refusing mixed-code result')
        if file_hashes(identity.get('runtime_files', {})) != identity.get('runtime_files', {}):
            raise ValueError('runtime inputs changed after launch')
        if 'behavior_env' in identity and behavior_env() != identity['behavior_env']:
            raise ValueError('behavior environment changed after launch')
        from bot.search.lopp import FAILURES
        from bot.levels.player import make_arm_player
        from bot.eval.headline import make_player
        from bot.players.royalesim_match import play_match
        failures, before = FAILURES, FAILURES.copy()
        seat = case['seat']
        player = make_arm_player(rt, arm, base=args.base_player, view=case['view'],
                                 parity_all11=args.all11_gate)
        players = {seat: player,
                   1-seat: make_player(rt, case['opponent'])}
        capture_controller_priors(row, players, identity, 'before')
        result = play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab,
                            client=args.client, verbose=True, levels=case['profile']['cards'],
                            tower_levels=case['profile']['towers'])
        winner = result['winner']
        outcome = 'draw' if winner is None else ('win' if winner == seat else 'loss')
        row.update({k: v for k, v in result.items() if k not in ('play_log', 'decks', 'seed')})
        row.update(score=dict(win=1., draw=.5, loss=0.)[outcome], outcome=outcome,
                   win=outcome == 'win', draw=outcome == 'draw', loss=outcome == 'loss',
                   play_log=result['play_log'][seat])
        capture_controller_priors(row, players, identity, 'after')
    except BaseException as exc:
        row.update(error=repr(exc), traceback=traceback.format_exc())
    finally:
        if players and 'after' not in row.get('controller_prior_sha256', {}):
            try:
                capture_controller_priors(row, players, identity, 'after')
            except Exception as exc:
                row['controller_prior_error'] = repr(exc)
                row.setdefault('error', repr(exc))
                row.setdefault('traceback', traceback.format_exc())
        row['level_diagnostics'] = level_diagnostics(player)
        row.update(wall_seconds=time.monotonic()-started, process_cpu_seconds=time.process_time()-cpu0,
                   failures=dict(failures - before) if failures is not None else {})
        status = int(any(row_issues(row, require_exit=False).values()))
        try:
            write_json(path, row)
        except BaseException:
            traceback.print_exc()
            status = 1
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--bank', type=Path, required=True)
    ap.add_argument('--arms', default='A,B0,B')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--base-player', default=BASE_PLAYER)
    ap.add_argument('--client', default='16.402')
    ap.add_argument('--all11-gate', action='store_true')
    args = ap.parse_args(argv)
    if os.environ.get('PYTHONHASHSEED') != '0':
        ap.error('launch with PYTHONHASHSEED=0')
    arms = args.arms.split(',')
    if not 1 <= args.workers <= 15 or args.start < 0 or args.count < 0:
        ap.error('workers must be in 1..15; start/count must be nonnegative')
    if args.base_player != BASE_PLAYER:
        ap.error(f'base-player must be the deterministic serial {BASE_PLAYER}')
    if len(set(arms)) != len(arms) or any(a not in ('A', 'B0', 'B') for a in arms):
        ap.error('arms must be distinct members of A,B0,B')
    if args.all11_gate and set(arms) != {'A', 'B'}:
        ap.error('all11 gate requires both arms A/B')
    return args


def select_cases(bank, start, count):
    indices = [c['index'] for c in bank['cases']]
    if any(type(i) is not int or i < 0 for i in indices) or len(set(indices)) != len(indices):
        raise ValueError('bank must contain unique nonnegative integer case indices')
    by = {c['index']: c for c in bank['cases']}
    requested = range(start, start + count)
    if any(i not in by for i in requested):
        raise ValueError('bank does not contain the full requested index range')
    return [by[i] for i in requested]


def parity_checks(rows, indices):
    """Named all11 evidence checks shared with report.py; no general readiness claim."""
    keys = [(r['arm'], r['index']) for r in rows]
    expected = {(a, i) for i in indices for a in ('A', 'B')}
    by = {(r['arm'], r['index']): r for r in rows}
    complete = bool(expected) and len(keys) == len(set(keys)) and set(keys) == expected
    issues = [row_issues(r) for r in rows]
    return dict(complete_unique_rows=complete,
                complete_diagnostics=complete and all('score' in r and 'controller_prior_sha256' in r
                                                       and diagnostics_complete(r) for r in rows),
                terminal_results=complete and all(r.get('terminal') is True for r in rows),
                zero_errors=all(not i['errors'] for i in issues),
                zero_native_failures=all(not i['native_failures'] for i in issues),
                zero_rejected_deployments=all(not i['rejections'] for i in issues),
                zero_child_failures=all(not i['child_failures'] for i in issues),
                controller_priors_match=complete and all(prior_evidence_ok(r) for r in rows),
                command_hashes_match=complete and all(by['A', i].get('command_sha256') and
                    by['A', i]['command_sha256'] == by['B', i].get('command_sha256') for i in indices),
                b_roots_exercised=complete and all(
                    by['B', i].get('level_diagnostics', {}).get('stats', {}).get('roots', 0) > 0 for i in indices))


def record_exit(path, case, arm, identity, pid, status):
    """Attach exit evidence without discarding an existing detailed result/traceback."""
    row = json.loads(path.read_text()) if path.exists() else dict(case, arm=arm, **identity,
        pid=pid, host=socket.gethostname(), error='child exited without a complete result')
    row['child_exit_code'] = os.waitstatus_to_exitcode(status) if status is not None else None
    write_json(path, row)
    return any(row_issues(row).values())


def cleanup_children(active, grace=5., kill_wait=2.):
    """waitpid verifies direct children before each signal; all waits are bounded."""
    remaining, statuses = set(active), {}
    for sig, duration in ((signal.SIGTERM, grace), (signal.SIGKILL, kill_wait)):
        for pid in list(remaining):
            try:
                done, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                remaining.remove(pid)  # Not an owned, unreaped child: never signal it.
                continue
            if done:
                remaining.remove(pid)
                statuses[pid] = status
            else:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + duration
        while remaining and time.monotonic() < deadline:
            for pid in list(remaining):
                try:
                    done, status = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    remaining.remove(pid)
                    continue
                if done:
                    remaining.remove(pid)
                    statuses[pid] = status
            if remaining:
                time.sleep(min(.05, max(0., deadline-time.monotonic())))
    return remaining, statuses


def run_jobs(rt, vocab, jobs, args, identity):
    active, pending = {}, iter(jobs)
    exhausted, failed = False, False
    try:
        while active or not exhausted:
            while len(active) < args.workers and not exhausted:
                job = next(pending, None)
                if job is None:
                    exhausted = True
                    break
                sys.stdout.flush()
                sys.stderr.flush()
                # Register the PID before a pending termination can run our cleanup.
                previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                try:
                    pid = os.fork()
                    if pid == 0:
                        try:
                            signal.signal(signal.SIGTERM, signal.SIG_DFL)
                            signal.signal(signal.SIGINT, signal.SIG_DFL)
                            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                            child(rt, vocab, *job[:2], args, job[2], identity)
                        except BaseException as exc:
                            detail = traceback.format_exc()
                            traceback.print_exc()
                            try:
                                row = json.loads(job[2].read_text()) if job[2].exists() else dict(job[0], arm=job[1], **identity)
                                row.setdefault('error', repr(exc))
                                row.setdefault('traceback', detail)
                                write_json(job[2], row)
                            except BaseException:
                                traceback.print_exc()
                        finally:
                            os._exit(1)  # Never unwind into the parent's inherited cleanup/receipts.
                    active[pid] = job
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                print(f"{utcnow()} start pid={pid} arm={job[1]} index={job[0]['index']}", flush=True)
            if not active:
                break
            pid, status = os.waitpid(-1, 0)
            if pid not in active:
                continue
            case, arm, path = active.pop(pid)
            failed |= record_exit(path, case, arm, identity, pid, status)
            print(f"{utcnow()} done pid={pid} arm={arm} index={case['index']} status={status}", flush=True)
    finally:
        if active:
            handlers = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGTERM, signal.SIGINT)}
            try:
                remaining, statuses = cleanup_children(active)
                for pid, (case, arm, path) in active.items():
                    record_exit(path, case, arm, identity, pid, statuses.get(pid))
                if remaining:
                    print(f'owned children not reaped within cleanup deadline: {sorted(remaining)}', file=sys.stderr)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
    return int(failed)


def experiment(args):
    from bot.players.runtime import Runtime, DEFAULT_RUNTIME
    from bot.players.royalesim_vocab import load
    from .scope import install
    arms = args.arms.split(',')
    raw_bank = args.bank.read_bytes()
    bank = json.loads(raw_bank)
    cases = select_cases(bank, args.start, args.count)
    if args.all11_gate:
        for case in cases:
            validate_all11(case)
    rows = args.out / 'rows'
    rows.mkdir(parents=True, exist_ok=True)
    planned = [(case, arm, rows / f"{arm}-{case['index']:05d}.json") for case in cases for arm in arms]
    print(f'{utcnow()} preflight parent={os.getpid()} requested={len(planned)} workers={args.workers}', flush=True)
    root = Path(os.environ.get('CLASHER_BOT_RUNTIME', DEFAULT_RUNTIME)).resolve()
    sources, inputs = source_hashes(), runtime_files(root)
    rt = Runtime()
    install(rt)  # The same fixed conditional-population prior for every arm/controller.
    _ = rt.STUDENT
    from bot.search.lopp import load_model
    load_model('pool')  # Freeze the serial rollout model in the parent, not lazily per child.
    vocab = load(rt)
    manifest = preload_configs(rt, planned, args.all11_gate)
    if rt.root.resolve() != root or source_hashes() != sources or runtime_files(root) != inputs:
        raise ValueError('experiment inputs changed while building runtime/preloading')
    identity = invocation_identity(args, rt, vocab, manifest, inputs, sources, hashlib.sha256(raw_bank).hexdigest())
    # Even an all-done resume reaches every validation above.
    jobs = [job for job in planned if not resume_done(job[2], job[0], job[1], identity)]
    launch = dict(args={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        time=utcnow(), host=socket.gethostname(), pid=os.getpid(), jobs=len(jobs), identity=identity,
        bank_path=str(args.bank.resolve()), bank_sha256=identity['bank_sha256'], case_indices=[c['index'] for c in cases],
        expected=[dict(arm=a, index=c['index']) for c, a, _ in planned])
    receipt = write_launch(args.out, launch)
    print(f'{utcnow()} parent={os.getpid()} jobs={len(jobs)} workers={args.workers}; receipt={receipt}', flush=True)
    status, checks = 1, None
    try:
        status = run_jobs(rt, vocab, jobs, args, identity)
        completed = [json.loads(p.read_text()) for _, _, p in planned if p.exists()]
        status |= int(len(completed) != len(planned) or any(any(row_issues(r).values()) for r in completed))
        if args.all11_gate:
            checks = parity_checks(completed, [c['index'] for c in cases])
            status |= int(not all(checks.values()))
        return status
    except Terminated as exc:
        status = 128 + exc.signum
        raise
    except KeyboardInterrupt:
        status = 130
        raise
    except BaseException:
        status = 1
        raise
    finally:
        write_json(receipt.with_name(f'{receipt.stem}-result.json'),
                   dict(finished=utcnow(), exit_code=status, parity_checks=checks))


class Terminated(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f'terminated by signal {signum}')


def main(argv=None):
    args = parse_args(argv)
    def terminate(signum, frame):
        raise Terminated(signum)
    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        return experiment(args)
    except Terminated as exc:
        return 128 + exc.signum
    except KeyboardInterrupt:
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
