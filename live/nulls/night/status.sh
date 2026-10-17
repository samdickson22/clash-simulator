#!/bin/bash
# 05: one-screen night status (read-only on the Mac): runners, headroom, landed frames/GB, labeller backlog.
N=/mpac/sdicks02/scratch/nulls/night
ssh macmini-fleet 'cd ~/clasher-live/nulls/night/code && ~/clasher-live/venv/bin/python -B nightcap.py status 2>&1 | tail -6;
  for i in 0 1 2 3; do [ -f ../state/night-$i.log ] && tail -1 ../state/night-$i.log | cut -c1-170; done;
  sysctl -n vm.loadavg; memory_pressure | tail -1; echo __RC=0'
/mpac/sdicks02/scratch/nulls/venv/bin/python - <<'EOF'
import glob, json, os, time
N = '/mpac/sdicks02/scratch/nulls/night'
now = time.time()
metas = [f for f in glob.glob(f'{N}/raw/i*/*/chunk-*/*.json') if not f.endswith(('manifest.json', 'events.json'))]
recent = [f for f in metas if now - os.path.getmtime(f) < 600]
lab = [f for f in glob.glob(f'{N}/i*/*/chunk-*/READY')]
raw = glob.glob(f'{N}/raw/i*/*/chunk-*/READY')
print(f'frames on 05: {len(metas)} (landed last 10 min: {len(recent)} -> {len(recent) * 6} /h); '
      f'chunks raw {len(raw)} labelled {len(lab)} (backlog {len(raw) - len(lab)})')
EOF
du -sh $N/raw | cut -f1 | sed 's/^/raw size: /'; df -h /mpac | tail -1; tail -1 $N/logs/pull.log
