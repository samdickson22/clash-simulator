"""Read-only evidence for v6 admission/config blockers; does not alter enforcement."""
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from clasher.rl import council_pilot as cp

KIT = Path(__file__).resolve().parent
RC = KIT.parents[1]
RT = RC / 'm0/runtime-snapshots/pilot-runtime-v6'
BASE = RT.with_name('pilot-runtime-v5')
ADMITTED = RT.with_name('native-final-v7')
manifest = json.loads((RT / 'pilot-runtime.json').read_text())
admission = json.loads((RC / 'm0/readiness/tier-a-fresh-v7/admission.json').read_text())
report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'runtime': str(RT)}
try:
    cp.verify_pilot_source_scope(pilot_root=RT, admitted_root=ADMITTED,
                                admitted_pins=admission['source_pins'],
                                pilot_pins=json.loads((RT/'pilot-source-pins.json').read_text()))
    report['scope'] = 'passed'
except ValueError as e:
    report['scope'] = str(e)
report['changed_bound_definitions_vs_v5'] = {}
for relative in ('src/clasher/rl/train_recurrent.py', 'src/clasher/rl/parallel_rollout.py'):
    original = cp._top_level_bindings(ast.parse((BASE/relative).read_text()))
    current = cp._top_level_bindings(ast.parse((RT/relative).read_text()))
    closure = cp._bound_symbol_closure(original, set(cp.PILOT_BOUND_SYMBOLS[relative]))
    report['changed_bound_definitions_vs_v5'][relative] = sorted(
        name for name in closure if [item for item,_ in original[name]] != [item for item,_ in current.get(name,[])])
report['config_validation'] = {}
for seed in (2901, 2902):
    try:
        cp.load_pilot_config(KIT/'configs'/f'council-pilot-v7r5-seed{seed}.toml')
        report['config_validation'][str(seed)] = 'passed'
    except ValueError as e:
        report['config_validation'][str(seed)] = str(e)
log = (KIT.parent/'logs/stop-v7r4h-at-2m.log').read_text()
processes = subprocess.check_output(['ps','-axo','pid=,ppid=,command='], text=True).splitlines()
report['host_gate'] = {
    'stop_log_lines': [line for line in log.splitlines() if '2M present' in line],
    'stop_log_passed': all(f'seed {s}: 2M present' in log for s in (2901,2902)),
    'v7r4h_trainers': [line.strip() for line in processes if ' -m clasher.rl.train_recurrent ' in line and any(f'v7r4h-seed{s}' in line for s in (2901,2902))],
}
report['v7r4h_first20'] = {}
for seed in (2901,2902):
    p = KIT.with_name('v7r4h-launch')/'runs'/f's{seed}'/f'seed-{seed}'/'scripted/training-monitor.jsonl'
    rows=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    rows=[r for r in rows if r.get('event') is None and 1 <= r.get('update',0) <= 20]
    report['v7r4h_first20'][str(seed)] = rows
path = KIT/'logs/blockers.json'
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'v7r4h_first20'}, indent=2))
