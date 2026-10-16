#!/usr/bin/env bash
# All four original/runtime config x plain/scrub variants; four leased single-thread processes.
set -euo pipefail
J=${CARD_NONE_JOB:?scratch job}
REPO=${CARD_NONE_SOURCE:?committed source export}
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2 CLASHER_BOT_RUNTIME_PINS=live16402b-r2
mkdir -p "$J/totality"
pids=()
for cfg in root runtime; do for scrub in plain scrub; do
  flags=(); [[ $cfg == runtime ]] && flags+=(--runtime-config); [[ $scrub == scrub ]] && flags+=(--scrub)
  nice -n 15 "$PY" -B "$REPO/reports/cards/live16402/tools/totality_live.py" "${flags[@]}" \
    --roots /mpac/sdicks02/jobs/clasher/cards/runtime/roots-nt --out "$J/totality/$cfg-$scrub.json" \
    > "$J/totality/$cfg-$scrub.log" 2>&1 & pids+=("$!")
done; done
for pid in "${pids[@]}"; do wait "$pid"; done
"$PY" -B - <<'PY'
import json,os
from pathlib import Path
out={}
for p in sorted((Path(os.environ['CARD_NONE_JOB'])/'totality').glob('*.json')):
    r=json.loads(p.read_text())
    out[p.stem]=dict(scenarios=len(r['scenarios']),probes=sum(x['probes'] for x in r['scenarios'].values()),
                     failing_cuts=sum(x['failing_cuts'] for x in r['scenarios'].values()))
    assert not out[p.stem]['failing_cuts'], p
assert len(out)==4
print(json.dumps(out),flush=True)
PY
