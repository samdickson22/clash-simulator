#!/usr/bin/env bash
# All four original/runtime config x plain/scrub variants; two leased processes per batch.
set -euo pipefail
J=${CARD_TEMPLATE_JOB:?scratch job}
REPO=${CARD_TEMPLATE_SOURCE:?committed source export}
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
export CLASHER_BOT_RUNTIME=${CARD_TEMPLATE_RUNTIME:?explicit candidate runtime} CLASHER_BOT_RUNTIME_PINS=live16402b-r3
case "$CLASHER_BOT_RUNTIME" in
  "$J"/*) ;;
  /mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3)
    [[ -f "$CLASHER_BOT_RUNTIME/RECEIPT.json" && ! -w "$CLASHER_BOT_RUNTIME" ]] || { echo 'released r3 receipt/read-only preflight failed' >&2; exit 2; } ;;
  *) echo 'runtime must be own scratch or exact released r3' >&2; exit 2;;
esac
[[ ! -e "$J/totality" ]] || { echo 'totality output exists; preserve it' >&2; exit 2; }
mkdir -p "$J/totality"
pids=()
rc=0
for cfg in root runtime; do for scrub in plain scrub; do
  flags=(); [[ $cfg == runtime ]] && flags+=(--runtime-config); [[ $scrub == scrub ]] && flags+=(--scrub)
  nice -n 15 "$PY" -B "$REPO/reports/cards/live16402/tools/totality_live.py" "${flags[@]}" \
    --roots "$J/roots-nt" --out "$J/totality/$cfg-$scrub.json" \
    > "$J/totality/$cfg-$scrub.log" 2>&1 & pids+=("$!")
  if [[ ${#pids[@]} -eq 2 ]]; then
    for pid in "${pids[@]}"; do wait "$pid" || rc=1; done
    pids=()
    [[ $rc == 0 ]] || exit "$rc"
  fi
done; done
for pid in "${pids[@]}"; do wait "$pid" || rc=1; done
[[ $rc == 0 ]] || exit "$rc"
"$PY" -B - <<'PY'
import json,os
from collections import Counter
from pathlib import Path
out={}
for p in sorted((Path(os.environ['CARD_TEMPLATE_JOB'])/'totality').glob('*.json')):
    r=json.loads(p.read_text())
    failures=Counter(v for x in r['scenarios'].values() for cut in x['failures'].values() for v in cut.values())
    expected='ValueError: unsupported card absent from imported pilot configuration'
    unexpected={k:v for k,v in failures.items() if k != expected}
    out[p.stem]=dict(scenarios=len(r['scenarios']),probes=sum(x['probes'] for x in r['scenarios'].values()),
                     failing_cuts=sum(x['failing_cuts'] for x in r['scenarios'].values()),
                     panics=sum(v for k,v in failures.items() if 'panic' in k.lower()),
                     expected_rejections=failures.get(expected,0),unexpected=unexpected)
    assert not unexpected and not out[p.stem]['panics'], (p,unexpected)
    if p.stem.endswith('scrub'):
        assert not failures, (p,failures)
assert len(out)==4
(Path(os.environ['CARD_TEMPLATE_JOB'])/'totality-summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out),flush=True)
PY
