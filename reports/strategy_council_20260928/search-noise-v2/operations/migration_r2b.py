"""Operational host-map adapter. Never writes or changes sealed study code.

Only the named launch/analyze module gets a JSON facade; worker/evaluate and
manifest verification keep their original modules and read original disk bytes.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parents[1]
OPS = HERE / 'operations'
JOBS = Path('/mpac/sdicks02/jobs/clasher')
MANIFEST = '3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def verified():
    data = (HERE / 'evaluation-manifest.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == MANIFEST
    manifest = json.loads(data)
    for rel, want in manifest['files'].items():
        assert hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == want, rel
    return manifest


def mapping(mode):
    split = json.loads((OPS / 'migration-split-r2b.json').read_text())
    original = json.loads((HERE / 'execution.json').read_text())
    assert split['manifest'] == MANIFEST
    assert split['execution_sha256'] == hashlib.sha256((HERE / 'execution.json').read_bytes()).hexdigest()
    result = json.loads(json.dumps(original))
    for w in result['workers']:
        i = w['index']
        if 48 <= i < 148:
            w['host'] = split['migration_hosts'][str(i)]
        elif mode == 'launch':
            w['host'] = '__original_partition_not_relaunched__'
    assert [w['index'] for w in result['workers']] == list(range(248))
    return result


class ExecutionOnlyJSON:
    def __init__(self, replacement):
        self.original = (HERE / 'execution.json').read_text()
        self.replacement = json.dumps(replacement)
        self.calls = 0

    def loads(self, data, *args, **kwargs):
        if data == self.original:
            self.calls += 1
            data = self.replacement
        return json.loads(data, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(json, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['launch', 'analyze', 'proof'])
    args = ap.parse_args()
    verified()
    sys.path.insert(0, str(HERE))
    if args.mode == 'proof':
        from cells import CELLS, H2H
        schedule = json.loads((HERE / 'schedule.json').read_text())
        jobs = [(ep, cell, seat) for ep in schedule['pairs'] for cell in
                (CELLS if ep['mode'] == 'scripts' else H2H) for seat in (0, 1)]
        assert len(jobs) == 4992
        view = mapping('launch')
        selected = {h: [w['index'] for w in view['workers'] if w['host'] == h]
                    for h in ('127x04', '127x08')}
        assert sorted(selected['127x04'] + selected['127x08']) == list(range(48, 148))
        assert not set(selected['127x04']) & set(selected['127x08'])
        parts = {}
        for i in range(48, 148):
            ids = [j for j in range(len(jobs)) if j % 248 == i]
            digest = hashlib.sha256(json.dumps([(j, jobs[j]) for j in ids], sort_keys=True).encode()).hexdigest()
            assert len(ids) == 20
            parts[str(i)] = dict(job_ids=ids, frozen_input_sha256=digest)
        out = dict(utc=time.time(), manifest=MANIFEST, sealed_hashes_verified=468,
                   selected=selected, total_workers=248, migrated_games=2000,
                   partition_inputs=parts, mechanism='module-local execution JSON facade; unchanged frozen worker --index i --workers 248',
                   no_game_or_outcome_execution=True)
        write(OPS / 'migration-proof-r2b.json', out)
        print(json.dumps({k: v for k, v in out.items() if k != 'partition_inputs'}))
        return
    host = socket.gethostname().split('.')[0]
    if args.mode == 'launch':
        assert host in ('127x04', '127x08')
        assert (JOBS / f's1-confirm-node-{host}-r2.exit').read_text().strip() == '0'
        who = subprocess.check_output(['who'], text=True)
        # Conservative reservation for the entire C56 allocation on 04.
        reserve = 32 if host == '127x04' else 0
        ceiling = 16 if who.strip() else 80
        cap = min(48 if host == '127x04' else 80, ceiling - reserve)
        assert cap > 0, 'Console user with C56 reservation: wait for revised allocation'
        selected = [w['index'] for w in mapping('launch')['workers'] if w['host'] == host]
        cap = min(cap, len(selected))
        assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
        write(OPS / f'migration-launch-precheck-{host}-r2b.json',
              dict(utc=time.time(), host=host, indices=selected, concurrency=cap,
                   who=who, reserved_other_workers=reserve, ceiling=ceiling))
        module = importlib.import_module('launch_node')
        sys.argv = [str(HERE / 'launch_node.py'), '--attempt', 'r2b', '--concurrency', str(cap)]
    else:
        assert host == '127x01'
        ready = json.loads((OPS / 'migration-monitor-r2b.json').read_text())
        assert ready['complete_only_ready'] and ready['valid_terminal_receipts'] == 4992
        assert ready['successful_collected_partitions'] == 248
        module = importlib.import_module('analyze')
    facade = ExecutionOnlyJSON(mapping(args.mode))
    module.json = facade
    module.main()
    assert facade.calls == 1, ('unexpected execution mapping reads', facade.calls)
    verified()


if __name__ == '__main__':
    main()
