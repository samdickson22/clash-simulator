"""Fleet scheduling and verification around the unchanged, admitted v3b extractor."""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import multiprocessing
import os
import platform
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
import zipfile
import zlib

import numpy as np
import c56_v3_bootstrap as cb
import extract_v3 as ex
from qa_v3 import aggregate
from v3_common import validate

Q = cb.DATA / 'qa/fleet-v3b'
OUT = cb.DATA / 'recon/engine-v3'
NODES = ('127x01', '127x03', '127x04')


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    ex.atomic_json(path, value)


def gate():
    cb.bind_runtime()
    base = read(Q / 'mac-base.json')
    for name, digest in base['inputs'].items():
        assert cb.file_sha256(cb.DATA / name) == digest, name
    g = read(cb.DATA / 'qa/v3b/gates.json')
    assert cb.runtime_manifest()['sha256'] == g['runtime']['sha256']
    assert cb.file_sha256(Path(ex.__file__)) == g['driver_sha256']
    assert cb.file_sha256(OUT / 'runtime_manifest.json') == g['previous_manifest_sha256']
    qa = read(cb.DATA / 'qa/v3/metrics.json')
    assert qa['after']['placement_acceptance'] >= .99 and qa['illegal_labels'] == 0
    assert 'P16_IDENTITY_PASS' in (cb.DATA / 'logs/v3-identity.log').read_text()
    assert cb.file_sha256(cb.DATA / 'qa/v3/tether-determinism-a.npz') == cb.file_sha256(cb.DATA / 'qa/v3/tether-determinism-b.npz')
    return base


def verify_base():
    base = gate()
    for name, info in base['files'].items():
        path = cb.DATA / name
        assert path.stat().st_size == info['bytes'] and cb.file_sha256(path) == info['sha256'], name
    result = {'utc': ex.utc(), 'host': socket.gethostname(), 'files': len(base['files']),
              'inputs': len(base['inputs']), 'mismatches': 0}
    write(Q / f'base-verified-{socket.gethostname()}.json', result)
    return result


def unit_tuple(key, out=OUT):
    phase, stem = key.split('/')
    fields = stem.split('-')
    return int(fields[1]), int(fields[3]), phase, str(out)


def initialize():
    ex.init_worker()
    ex._STATE['runtime_sha'] = cb.runtime_manifest()['sha256']


def equivalence_one(key):
    target = Q / 'equivalence-replay'
    target.mkdir(exist_ok=True)
    assert not (cb.DATA / 'recon/engine-v2b' / (key + '.npz')).exists()
    result = ex.run_unit(unit_tuple(key, target))
    original = OUT / (key + '.npz')
    fresh = target / (key + '.npz')
    side = read(target / (key + '.json'))
    assert not side['errors']
    differences = []
    layouts = []
    with np.load(original, allow_pickle=False) as a, np.load(fresh, allow_pickle=False) as b:
        assert a.files == b.files
        old_header = json.loads(str(a['header_json'].item()))
        new_header = json.loads(str(b['header_json'].item()))
        for name in old_header.keys() | new_header.keys():
            if old_header.get(name) != new_header.get(name):
                differences.append({'field': name, 'original': old_header.get(name), 'replay': new_header.get(name)})
        assert all(d['field'] == 'extra' for d in differences), differences
        normalized = {}
        for name in a.files:
            old, new = a[name], b[name]
            if name == 'header_json':
                normalized[name] = old
                continue
            assert old.dtype == new.dtype and old.shape == new.shape, (key, name)
            assert old.tobytes() == new.tobytes(), (key, name, 'logical bytes')
            if old.flags.f_contiguous != new.flags.f_contiguous:
                layouts.append(name)
            normalized[name] = np.array(new, order='F' if old.flags.f_contiguous else 'C')
        normalized_path = target / (key + '.normalized.npz')
        ex.v5.save_npz_deterministic(normalized_path, normalized)
    orig_sha = cb.file_sha256(original)
    normalized_sha = cb.file_sha256(normalized_path)
    # zlib implementations may encode identical members differently; retain exact evidence.
    with zipfile.ZipFile(original) as a, zipfile.ZipFile(normalized_path) as b:
        assert a.namelist() == b.namelist()
        assert all(a.read(n) == b.read(n) for n in a.namelist())
    result.update(original_sha256=orig_sha, raw_replay_sha256=cb.file_sha256(fresh),
                  normalized_sha256=normalized_sha, normalized_byte_identical=orig_sha == normalized_sha,
                  logical_arrays_identical=True, all_npy_members_identical=True,
                  header_differences=differences, storage_order_fields=layouts,
                  validation=validate(fresh))
    write(Q / ('equivalence-' + key.replace('/', '-') + '.json'), result)
    return result


def equivalence():
    assert socket.gethostname() in NODES
    assert Path('/mpac/sdicks02/jobs/clasher/smoke-p16-linux-20261007.exit').read_text().strip() == '0'
    base = verify_base()
    with concurrent.futures.ProcessPoolExecutor(3, mp_context=multiprocessing.get_context('spawn'), initializer=initialize) as pool:
        results = list(pool.map(equivalence_one, read(Q / 'mac-base.json')['equivalence_units']))
    result = {'utc': ex.utc(), 'complete': True, 'base': base, 'units': results,
              'environment': {'python': sys.version, 'numpy': np.__version__,
                  'platform': platform.platform(), 'zlib_compile': zlib.ZLIB_VERSION,
                  'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION}}
    write(Q / 'equivalence.json', result)
    return result


def partition():
    base = gate()
    assert read(Q / 'hub-base-verified.json')['mismatches'] == []
    assert read(Q / 'equivalence.json')['complete']
    all_units = []
    counts = {}
    for phase in ('s117', 's122'):
        for shard in range(52):
            pairs = ex.perspective_list(shard, phase)
            for n in range((len(pairs) + 47) // 48):
                key = f'{phase}/shard-{shard:03d}-part-{n:02d}'
                all_units.append(key)
                counts[key] = len(pairs[n * 48:(n + 1) * 48])
    finished = {str(Path(n).relative_to('recon/engine-v3')).removesuffix('.json')
                for n in base['files'] if n.endswith('.json')}
    pending = sorted(set(all_units) - finished)
    assert len(all_units) == 1767 and len(finished) == 811 and len(pending) == 956
    assert sum(counts.values()) == 82231
    result = {'utc': ex.utc(), 'method': 'sorted (phase, shard, part), pending round-robin across 01/03/04',
              'all_units': all_units, 'base_units': sorted(finished), 'perspectives': counts,
              'assignments': {host: pending[i::3] for i, host in enumerate(NODES)},
              'runtime': cb.runtime_manifest(), 'base_sha256': cb.file_sha256(Q / 'mac-base.json')}
    path = Q / 'partition.json'
    if path.exists():
        assert read(path)['assignments'] == result['assignments']
    else:
        write(path, result)
    return {host: len(units) for host, units in result['assignments'].items()}


def extract(workers):
    host = socket.gethostname()
    assert host in NODES and 1 <= workers <= 96
    assert Path('/mpac/sdicks02/jobs/clasher/smoke-p16-linux-20261007.exit').read_text().strip() == '0'
    console = subprocess.check_output(['who'], text=True)
    if console.strip():
        assert workers <= 16, console
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1'
    lock = (OUT / 'driver.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush()
    verify_base()
    assert read(Q / 'equivalence.json')['complete']
    plan = read(Q / 'partition.json')
    keys = plan['assignments'][host]
    # Include this node's canonical base in the cumulative failure denominator.
    attempted, failed = ex.published_counts(OUT)
    todo = [k for k in keys if not (OUT / (k + '.json')).exists()]
    for key in keys:
        if key not in todo:
            s = read(OUT / (key + '.json'))
            if s['npz_sha256']:
                assert cb.file_sha256(OUT / (key + '.npz')) == s['npz_sha256']
    stop = False
    def stopping(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)
    start = time.time()
    write(Q / f'launch-{host}.json', {'utc': ex.utc(), 'pid': os.getpid(), 'workers': workers,
          'who': console, 'assigned': len(keys), 'pending': len(todo), 'runtime': cb.runtime_manifest(),
          'wrapper_sha256': cb.file_sha256(Path(__file__)), 'partition_sha256': cb.file_sha256(Q / 'partition.json'),
          'disk_free_min_gib': 12, 'disk_hard_cap_gib': 7.5,
          'disk_soft_cap_gib': min(7.375, 7.5 - workers * 16 / 1024)})
    with concurrent.futures.ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn'), initializer=initialize) as pool:
        pending = {}
        iterator = iter(todo)
        exhausted = False
        while pending or not exhausted:
            free = shutil.disk_usage(cb.DATA).free
            used = ex.disk_bytes()
            soft = min(7.375, 7.5 - workers * 16 / 1024) * 2**30
            if free < 12 * 2**30 or used > soft:
                pids = [p.pid for p in pool._processes.values() if p.is_alive()]
                write(Q / f'disk-paused-{host}.json', {'utc': ex.utc(), 'pid': os.getpid(), 'workers': pids, 'free': free, 'used': used})
                for pid in pids:
                    os.kill(pid, signal.SIGSTOP)
                os.kill(os.getpid(), signal.SIGSTOP)
                continue
            if failed * 200 > attempted or (Q / 'global-failure-stop.json').exists():
                stop = True
            while not stop and not exhausted and len(pending) < workers:
                key = next(iterator, None)
                if key is None:
                    exhausted = True
                    break
                pending[pool.submit(ex.run_unit, unit_tuple(key))] = key
            if stop:
                exhausted = True
            ready, _ = concurrent.futures.wait(pending, timeout=5, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in ready:
                key = pending.pop(future)
                result = future.result()  # Broken workers fail the job instead of leaving hung async results.
                if not result.get('resumed'):
                    attempted += result['attempted']; failed += result['errors']
                print(json.dumps(result), flush=True)
            write(Q / f'status-{host}.json', {'utc': ex.utc(), 'assigned': len(keys),
                  'finished': sum((OUT / (k + '.json')).exists() for k in keys),
                  'inflight': len(pending), 'attempted_with_base': attempted, 'failed': failed,
                  'wall_seconds': time.time() - start, 'data_bytes': used, 'free_bytes': free})
    assert failed * 200 <= attempted, 'failure rate exceeds 0.5%'
    assert not stop, 'stopped before completion'
    files = {}
    for key in keys:
        side = read(OUT / (key + '.json'))
        for suffix in ('.json', '.npz') if side['npz_sha256'] else ('.json',):
            path = OUT / (key + suffix)
            files[key + suffix] = {'sha256': cb.file_sha256(path), 'bytes': path.stat().st_size}
    cpu = resource.getrusage(resource.RUSAGE_SELF); children = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {'utc': ex.utc(), 'complete': True, 'host': host, 'units': len(keys), 'files': files,
              'wall_seconds': time.time() - start,
              'cpu_seconds': cpu.ru_utime + cpu.ru_stime + children.ru_utime + children.ru_stime}
    write(Q / f'completed-{host}.json', result)
    return {k: v for k, v in result.items() if k != 'files'}


def audit_one(key):
    path = OUT / (key + '.npz'); side = read(path.with_suffix('.json'))
    cache = Q / 'unit-audits' / (key.replace('/', '-') + '.json')
    side_sha = cb.file_sha256(path.with_suffix('.json'))
    if cache.exists():
        saved = read(cache)
        if saved['sidecar_sha256'] == side_sha:
            if side['npz_sha256']:
                assert cb.file_sha256(path) == side['npz_sha256']
            else:
                assert not path.exists()
            return saved['result']
    shard, number, phase, _ = unit_tuple(key)
    pairs = ex.perspective_list(shard, phase)[number * 48:(number + 1) * 48]
    expected = [shard * 100000 + i * 2 + ('team', 'opponent').index(s) for i, s in pairs]
    actual = [s['episode_id'] for s in side['perspectives']] + [s['episode_id'] for s in side['errors']]
    assert sorted(expected) == sorted(actual) and len(actual) == len(set(actual)), key
    if side['npz_sha256'] is None:
        assert not path.exists() and not side['perspectives'] and side['errors']
        result = {'key': key, 'summaries': [], 'errors': side['errors'], 'rows': 0, 'illegal': 0}
        write(cache, {'sidecar_sha256': side_sha, 'result': result})
        return result
    assert cb.file_sha256(path) == side['npz_sha256']
    result = validate(path)
    with zipfile.ZipFile(path) as z:
        header = json.loads(str(np.lib.format.read_array(z.open('header_json.npy'), allow_pickle=False).item()))
    assert [s['episode_id'] for s in header['perspectives']] == [s['episode_id'] for s in side['perspectives']]
    assert result['rows'] == side['rows']
    result.update(key=key, summaries=header['perspectives'], errors=side['errors'])
    write(cache, {'sidecar_sha256': side_sha, 'result': result})
    return result


def audit_base(workers):
    assert socket.gethostname() == '127x02'
    verify_base()
    keys = sorted(str(Path(n).relative_to('recon/engine-v3')).removesuffix('.json')
                  for n in read(Q / 'mac-base.json')['files'] if n.endswith('.json'))
    total_rows = total_perspectives = 0
    with concurrent.futures.ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for i, result in enumerate(pool.map(audit_one, keys), 1):
            assert not result['errors'] and result['illegal'] == 0
            total_rows += result['rows']; total_perspectives += len(result['summaries'])
            if i % 100 == 0:
                print(json.dumps({'validated_base_units': i, 'rows': total_rows}), flush=True)
    result = {'utc': ex.utc(), 'units': len(keys), 'rows': total_rows, 'perspectives': total_perspectives, 'errors': 0, 'illegal': 0}
    write(Q / 'base-audit.json', result)
    return result


def finalize(workers):
    assert socket.gethostname() == '127x02'
    verify_base()
    plan = read(Q / 'partition.json')
    for host in NODES:
        receipt = read(Q / f'completed-{host}.json')
        assert receipt['complete'] and receipt['units'] == len(plan['assignments'][host])
        for name, info in receipt['files'].items():
            path = OUT / name
            assert path.stat().st_size == info['bytes'] and cb.file_sha256(path) == info['sha256'], name
    assert sorted(p.relative_to(OUT).as_posix().removesuffix('.json') for p in OUT.glob('*/shard-*.json')) == sorted(plan['all_units'])
    summaries = []; errors = []; rows = illegal = 0; index = []
    phase_summaries = {'s117': [], 's122': []}
    with concurrent.futures.ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for result in pool.map(audit_one, plan['all_units']):
            unit_summaries = result.pop('summaries')
            summaries.extend(unit_summaries)
            phase_summaries[result['key'].split('/')[0]].extend(unit_summaries)
            errors.extend(result.pop('errors'))
            rows += result['rows']; illegal += result['illegal']; index.append(result)
            if len(index) % 100 == 0:
                print(json.dumps({'validated_units': len(index), 'rows': rows}), flush=True)
    stats = aggregate(summaries)
    possible = stats['possible']
    lost = sum((s['playable_end_tick'] + 4) // 5 - s['supervised_rows'] for s in summaries
               if s['cut_reason'] in {'opponent_forced_hand', 'opponent_insufficient_elixir'})
    phases = {phase: {'expected': expected, 'extracted': sum(len(read(p)['perspectives']) for p in (OUT / phase).glob('shard-*.json')),
              'errors': sum(len(read(p)['errors']) for p in (OUT / phase).glob('shard-*.json')),
              'units': len(list((OUT / phase).glob('shard-*.json')))} for phase, expected in [('s117', 62766), ('s122', 19465)]}
    assert all(v['expected'] == v['extracted'] + v['errors'] for v in phases.values())
    for phase, members in phase_summaries.items():
        phases[phase]['stats'] = aggregate(members)
        assert phases[phase]['stats']['placement_acceptance'] >= .99
        phase_lost = sum((s['playable_end_tick'] + 4) // 5 - s['supervised_rows'] for s in members
                         if s['cut_reason'] in {'opponent_forced_hand', 'opponent_insufficient_elixir'})
        phases[phase]['opponent_cut_retention_points'] = 100 * phase_lost / phases[phase]['stats']['possible']
        assert phases[phase]['opponent_cut_retention_points'] <= 3
    assert len(summaries) + len(errors) == 82231 and len(errors) * 200 <= 82231
    assert illegal == 0 and stats['placement_acceptance'] >= .99
    assert 100 * lost / possible <= 3, 'opponent contradiction rule requires review'
    qa = {'utc': ex.utc(), 'complete': True, 'units': len(index), 'rows': rows,
          'illegal_labels': illegal, 'errors': errors, 'stats': stats, 'phases': phases,
          'opponent_cut_lost_decisions': lost, 'opponent_cut_retention_points': 100 * lost / possible,
          'output_bytes': sum(p.stat().st_size for p in OUT.glob('*/shard-*') if p.suffix in {'.json', '.npz'})}
    write(Q / 'final-qa.json', qa)
    write(OUT / 'fleet-index.json', {'utc': ex.utc(), 'units': index})
    write(OUT / 'completion.json', {'utc': ex.utc(), 'complete': True, 'phases': phases,
          'fleet_qa_sha256': cb.file_sha256(Q / 'final-qa.json')})
    return qa


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['verify', 'equivalence', 'partition', 'extract', 'finalize', 'audit-base'])
    p.add_argument('--workers', type=int, default=64); args = p.parse_args()
    result = {'verify': verify_base, 'equivalence': equivalence, 'partition': partition,
              'extract': lambda: extract(args.workers), 'finalize': lambda: finalize(args.workers),
              'audit-base': lambda: audit_base(args.workers)}[args.mode]()
    print(json.dumps(result), flush=True)
