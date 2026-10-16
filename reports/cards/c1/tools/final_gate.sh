#!/bin/bash
# PREPARATION ONLY. Independent host-script review and B2 acceptance/integration are required before use.
# On 127x04, under the existing cpu_job.sh 8 wrapper:
#   bash final_gate.sh RUN_DIR INTEGRATED_COMMIT NATIVE_SHA256 B2_ACCEPTED_COMMIT
# RUN_DIR is a fresh c1/final-<integrated sha12>[-rN] bundle; see ../FINAL-GATE-PLAN.md.
set -euo pipefail
[[ $# == 4 ]] || { echo 'Expected RUN_DIR INTEGRATED_COMMIT NATIVE_SHA256 B2_ACCEPTED_COMMIT' >&2; exit 2; }
run=$1; source_commit=$2; native_sha=$3; b2_commit=$4
[[ $(hostname -s) == 127x04 ]] || { echo 'Final gate is restricted to 127x04' >&2; exit 2; }
[[ $source_commit =~ ^[0-9a-f]{40}$ && $b2_commit =~ ^[0-9a-f]{40}$ && $native_sha =~ ^[0-9a-f]{64}$ ]]
[[ $run =~ ^/mpac/sdicks02/jobs/clasher/cards/c1/final-[0-9a-f]{12}(-r[1-9][0-9]*)?$ ]]
[[ $(readlink -f "$run") == "$run" && $(basename "$run") == final-"${source_commit:0:12}"* ]]
read -r slots lease_pgid < "/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-$PPID"
own_pgid=$(ps -o pgid= -p $$ | tr -d ' ')
[[ $slots == 8 && $lease_pgid == "$own_pgid" ]] || { echo 'Requires parent cpu_job.sh 8 lease' >&2; exit 2; }
[[ ! -e $run/gate && ! -e $run/.gate-started ]]
py=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
pin=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1/clasher_core.abi3.so
pin_sha=681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
unset CARDS_GAMEDATA CLASHER_ROOT CLASHER_BOT_RUNTIME CLASHER_DELAY_NATIVE_DIR PYTHONPATH PYTHONHOME PYTHONOPTIMIZE

# ready.json is the lead's explicit receipt binding, not an automatic assertion of approval.
# All review/integration evidence is copied into this bundle and hash-bound before readiness is signed off.
"$py" -B - "$run" "$source_commit" "$native_sha" "$b2_commit" "$0" <<'PY'
import hashlib, json, sys
from pathlib import Path
r = Path(sys.argv[1])
m = json.loads((r / 'ready.json').read_text())
assert (m['integrated_commit'], m['native_sha256'], m['b2_accepted_commit']) == tuple(sys.argv[2:5])
assert m['prerequisites'] == dict(b2_accepted=True, b2_integrated=True,
                                affected_probes_pass=True, launcher_reviewed=True)
assert m['launcher_sha256'] == hashlib.sha256(Path(sys.argv[5]).read_bytes()).hexdigest()
assert m['receipts'] and m['inputs_sha256'] == hashlib.sha256((r / 'inputs.sha256').read_bytes()).hexdigest()
for path, expected in m['receipts'].items():
    p = (r / path).resolve()
    assert p.is_relative_to(r) and p.is_file(), path
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected, path
for p in ('tree', 'rt', 'out', 'roots', 'tools', 'gate-tools'):
    assert (r / p).is_dir(), p
tools = {
    'tools/gate.sh': '21bbecaf168be4c5b5ff44f96208025b58424b62efdf80ecf9179db37353e170',
    'gate-tools/parity_fixtures.py': '057bd386f022d3770baf0a47d19b7eac2b8e9fc978a0464746ae4a6fc7afe976',
    'gate-tools/parity_roots.py': '2d721a49d003abfaadd0e5f532749f700addfd733c493e7acf2b6abe225063eb',
    'gate-tools/compare.py': 'dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e',
}
for path, expected in tools.items():
    assert hashlib.sha256((r / path).read_bytes()).hexdigest() == expected, path
assert (r / 'rt/engine-rs').resolve() == (r / 'tree').resolve()
assert (r / 'rt/src').resolve() == (r / 'tree/py/src').resolve()
assert (r / 'rt/gamedata.json').resolve() == (r / 'tree/py/gamedata.json').resolve()
assert hashlib.sha256((r / 'out/clasher_core.abi3.so').read_bytes()).hexdigest() == sys.argv[3]
PY
[[ $(sha256sum "$pin" | cut -d ' ' -f1) == "$pin_sha" ]]

# Atomic, persistent launch claim: a partial/failed run gets a new -rN bundle, never an overwrite/relaunch.
mkdir "$run/.gate-started"
finish() { status=$?; printf '%s\n' "$status" > "$run/exit-code.txt"; date -u +%FT%TZ > "$run/ended.utc"; }
trap finish EXIT
printf 'pid=%s ppid=%s pgid=%s source=%s native=%s b2=%s\n' \
  "$$" "$PPID" "$own_pgid" "$source_commit" "$native_sha" "$b2_commit" > "$run/launch.receipt"
date -u +%FT%TZ > "$run/started.utc"
(cd "$run" && sha256sum ready.json inputs.sha256 > controls.sha256 && sha256sum -c inputs.sha256 > inputs-before.log)
bash "$run/tools/gate.sh" > "$run/gate.log" 2>&1

# compare.py is descriptive and the inherited gate.sh uses bare wait. Independently reject missing rows,
# duplicate IDs, differing bytes, wrong native headers or Rust-only errors before writing PASS.
"$py" -B - "$run" "$native_sha" "$pin_sha" <<'PY'
import json, sys
from pathlib import Path
g = Path(sys.argv[1]) / 'gate'
c = json.loads((g / 'compare.json').read_text())
f, r = c['fixtures'], c['roots']
assert f['pinned'] == f['total'] == f['identical_records'] == f['rust_only_chains_equal'] == 577
assert not f['differing'] and f['rust_only_errors'] == dict(pinned=0, total=0)
assert r['records'] == dict(pinned=600, total=600) and r['identical_records'] == 600
assert r['sampled_roots'] == 300 and r['by_variant'] == dict(full=300, cut=300) and not r['differing']
assert (g / 'fixtures-pinned.jsonl').read_bytes() == (g / 'fixtures-total.jsonl').read_bytes()
for tag in ('pinned', 'total'):
    fx = [json.loads(x) for x in (g / f'fixtures-{tag}.jsonl').read_text().splitlines()]
    assert len(fx) == len({x['episode'] for x in fx}) == 577
keys = {}
for tag, sha in (('pinned', sys.argv[3]), ('total', sys.argv[2])):
    assert len(list(g.glob(f'roots-{tag}-*.jsonl'))) == 4
    rows = []
    for i in range(4):
        lines = (g / f'roots-{tag}-{i}.jsonl').read_bytes().splitlines(keepends=True)
        assert json.loads(lines[0])['native_sha256'] == sha
        assert len(lines) == 151
        rows.extend(json.loads(x) for x in lines[1:])
        other = (g / f'roots-{"total" if tag == "pinned" else "pinned"}-{i}.jsonl').read_bytes().splitlines(keepends=True)
        assert lines[1:] == other[1:]
    keys[tag] = {(x['k'], x['variant']) for x in rows}
    assert len(rows) == len(keys[tag]) == 600
    assert len({k for k, _ in keys[tag]}) == 300
assert keys['pinned'] == keys['total']
print('PASS: 577 fixtures, 577 Rust chains, 300 full + 300 cut roots; exact rows/bytes/hashes')
PY
(cd "$run" && sha256sum -c controls.sha256 && sha256sum -c inputs.sha256 > inputs-after.log)
[[ $(sha256sum "$pin" | cut -d ' ' -f1) == "$pin_sha" ]]
date -u +%FT%TZ > "$run/PASS.utc"
