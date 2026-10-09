# HISTORICAL RECEIPT: superseded worker limits; do not execute.
#!/usr/bin/env bash
set -euo pipefail
root=/mpac/sdicks02/repos/clasher
out=reports/explore/search-ab
cd "$root"
run_on() {
  local host=$1; shift
  if [ "$host" = "$(hostname -s)" ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" "$*"; fi
}
for spec in '127x04 search-ab-tune-w4-v1 tune-w4' '127x01 search-ab-tune-w1-v1 tune-w1' '127x01 search-ab-tune-w64-v1 tune-w64' '127x08 search-ab-tune-w0w16-v1 tune-w0w16'; do
  read -r host label run <<< "$spec"
  while ! run_on "$host" "test -f /mpac/sdicks02/jobs/clasher/$label.exit"; do sleep 10; done
  rc=$(run_on "$host" "cat /mpac/sdicks02/jobs/clasher/$label.exit")
  test "$rc" = 0
  if [ "$host" != "$(hostname -s)" ]; then rsync -az "$host:$root/$out/$run/" "$out/$run/"; fi
 done
weight=$(.venv/bin/python "$out/select_weight.py" "$out")
printf 'selected reserve weight %s\n' "$weight"
for spec in '127x04 0 350 96 0-95' '127x08 350 350 96 0-95' '127x01 700 300 80 0-79'; do
 read -r host offset pairs workers affinity <<< "$spec"
 run_on "$host" "cd $root && bash reports/strategy_council_20260928/fleet/fleet_run.sh search-ab-primary-$host-v1 taskset -c $affinity env RAYON_NUM_THREADS=1 .venv/bin/python -m clasher.analysis.loss_review.simulate --out $out/primary-$host --workers $workers --pairs $pairs --pair-offset $offset --seed-base $((281474976720656+offset)) --delays 27 --arms 0 C R CR --reserve-weight $weight --exclusions $out/exclusions.json"
 done
printf 'primary reporting launched\n'
