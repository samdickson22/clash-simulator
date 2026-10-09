#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/w-screen8-20261009-r1
repo=$job/production-repo
py=/mpac/sdicks02/repos/clasher/.venv/bin/python
export CUDA_VISIBLE_DEVICES='' PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONPYCACHEPREFIX=$job/cache/pycache CLASHER_ROOT=$repo
export CLASHER_DELAY_NATIVE_DIR=$job/native-w-screen8-v1
export PYTHONPATH=$CLASHER_DELAY_NATIVE_DIR:$repo/src:$repo/engine-rs:$repo/reports/strategy_council_20260928/engine-speed/stage5:$repo/reports/strategy_council_20260928/engine-speed:$repo/reports/strategy_council_20260928/search-noise-s6:$repo/reports/strategy_council_20260928/search-noise-s4
cd "$repo"
"$py" -B -c 'import clasher_core,pytest,sys,types,pathlib; b=types.ModuleType("bootstrap"); b.HERE=pathlib.Path("reports/strategy_council_20260928/search-noise-s6").resolve(); sys.modules["bootstrap"]=b; raise SystemExit(pytest.main(["tests/rl/test_wait_screen8.py","tests/analysis/test_delay_fixes.py","reports/perf-audit/quickwins/test_resources.py","reports/strategy_council_20260928/search-noise-s6/test_delay.py","tests/test_native_elixir.py","tests/test_native_terminal_commands.py","tests/test_native_command_checks.py","-k","not frozen_tracker"]))'
corpus=/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/latency
"$py" -B reports/explore/w-screen8/parity.py --mode off --corpus "$corpus" --out "$job/production-off.json"
"$py" -B reports/explore/w-screen8/parity.py --mode on --corpus "$corpus" --out "$job/production-on.json"
"$py" -B - "$job" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);a=json.loads((p/'baseline-off.json').read_text());b=json.loads((p/'production-off.json').read_text())
assert a['digest']==b['digest'] and a['checks']==b['checks']==250
(p/'off-comparison.json').write_text(json.dumps(dict(exact=True,states=125,checks=250,baseline_native_sha256=a['native_sha256'],production_native_sha256=b['native_sha256'],digest=a['digest']),indent=2)+'\n')
PY
printf 'PASS\n' > "$job/W-PASS"
