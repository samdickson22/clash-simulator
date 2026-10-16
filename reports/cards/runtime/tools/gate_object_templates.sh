#!/usr/bin/env bash
# gate_k4l.sh HEADLINE protocol, current r1-total vs Python-patched r1-cards2.
# Run under bot/exit/cpu_job.sh 4. One HEADLINE worker plus its two rollout workers.
set -euo pipefail
J=${CARD_TEMPLATE_JOB:?scratch job}; REPO=$J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
mkdir -p "$J/gate"
cd "$REPO"
for arm in c56 patched; do
  unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
  if [[ $arm == c56 ]]; then
    export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 CLASHER_BOT_RUNTIME_PINS=r1-total
    export CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1
  else
    export CLASHER_BOT_RUNTIME=$J/dev-r1 CLASHER_BOT_RUNTIME_PINS=r1-cards2-r3
  fi
  nice -n 15 "$PY" -B -m bot.eval.headline --out "$J/gate/hl-k4l-$arm" --candidate K4L-R-gs-rw-fc-p2 \
    --opponents R3a,v1 --games 6 --workers 1 > "$J/gate/hl-k4l-$arm.log" 2>&1
done
"$PY" -B - <<'PY'
import hashlib,json,os
from pathlib import Path
j=Path(os.environ['CARD_TEMPLATE_JOB'])/'gate'
rows={a:[json.loads(x) for p in (j/f'hl-k4l-{a}').glob('games-*.jsonl') for x in p.read_text().splitlines()] for a in ('c56','patched')}
by={a:{(r['opponent'],r['index']):r for r in v} for a,v in rows.items()}
keys={(o,i) for o in ('R3a','v1') for i in range(6)}
assert all(set(v)==keys for v in by.values()), {a:len(v) for a,v in by.items()}
cases=[dict(opponent=o,index=i,baseline=by['c56'][o,i]['command_sha256'],patched=by['patched'][o,i]['command_sha256']) for o,i in sorted(keys)]
out=dict(result='PASS' if all(c['baseline']==c['patched'] for c in cases) else 'FAIL', identical=sum(c['baseline']==c['patched'] for c in cases),cases=cases,
         inputs={str(p.relative_to(j)):hashlib.sha256(p.read_bytes()).hexdigest() for p in j.glob('hl-k4l-*/games-*.jsonl')})
(j/'k4l.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out),flush=True)
assert out['result']=='PASS'
PY
