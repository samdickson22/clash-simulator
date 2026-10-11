#!/usr/bin/env bash
# K4S runner r1: commit the latest sealed health receipt + one PROGRESS line (temp index on origin/main, secret-scanned).
set -euo pipefail
L=/mpac/sdicks02/k4s-runner/run-r1; R=reports/explore/k4s-confirm/run-r1
f=$(python3 -c "import json;print(json.load(open('$L/health/last-check.json'))['out'])")
line=$(python3 -c "import json;d=json.load(open('$f'));print('- '+d['utc']+' SEALED health: '+d['summary']+('; ANOMALIES: '+'; '.join(d['anomalies']) if d['anomalies'] else '; no anomalies'))")
python3 - "$line" <<'EOF'
import sys
p='/mpac/sdicks02/k4s-runner/run-r1/PROGRESS.md';s=open(p).read();line=sys.argv[1]
marker='## Health checkpoints (SEALED, health only)\n'
if marker not in s:s+='\n'+marker
s=s.rstrip('\n')+'\n'+line+'\n';open(p,'w').write(s)
EOF
bash /mpac/sdicks02/k4s-runner/commit_paths.sh "K4S run r1: SEALED health checkpoint $(basename $f .json)" "$f=$R/health/$(basename $f)" "$L/PROGRESS.md=$R/PROGRESS.md" | tail -1
echo "$line"
