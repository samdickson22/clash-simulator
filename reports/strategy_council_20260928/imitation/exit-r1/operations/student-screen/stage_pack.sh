#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
gen=/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1
test -f "$job/source/imitation/exit_r1/pack.py"
mkdir -p "$job/staging/03" "$job/staging/04" "$job/staging/08" "$job/cache"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export XDG_CACHE_HOME=$job/cache PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$job/source:$job/source/src
cd "$job/source"
for host in 03 04 08; do
  target=$job/selections/$host
  if [[ $host == 03 ]]; then
    python3 "$job/ops/select_cutoff.py" "$host" "$target"
    while IFS= read -r game; do ln -s "$gen/generation/$game" "$job/staging/03/$game"; done < "$target/files.txt"
  else
    ssh "127x$host" "mkdir -p '$target'"
    scp -q "$job/ops/select_cutoff.py" "127x$host:$target/select_cutoff.py"
    ssh "127x$host" "nice -n 19 python3 '$target/select_cutoff.py' '$host' '$target'"
    mkdir -p "$target"
    scp -q "127x$host:$target/selection.json" "127x$host:$target/files.txt" "$target/"
    ssh "127x$host" "exec setsid nice -n 19 tar -C '$gen/generation' -cf - -T '$target/files.txt'" | tar -C "$job/staging/$host" -xf -
  fi
done
/mpac/sdicks02/repos/clasher/.venv/bin/python -B -m imitation.exit_r1.pack \
  --roots "$job/staging/03" "$job/staging/04" "$job/staging/08" \
  --output "$job/corpus" --stop "$job/PACK.STOP" > "$job/pack.json"
sha256sum "$job/corpus/manifest.json" > "$job/corpus.sha256"
date -u +%FT%TZ > "$job/packed-at.txt"
