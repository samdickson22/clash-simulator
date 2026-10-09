#!/usr/bin/env bash
set -euo pipefail
root=/mpac/sdicks02/repos/clasher/reports/explore/tempo
mkdir -p "$root/receipts/home" "$root/receipts/leased"
for host in 127x09 127x13 127x14 127x15 127x16; do
 mkdir -p "$root/receipts/leased/$host"
 nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac --include='tempo*.state.json' --include='tempo*.exit.json' --exclude='*' "$host:/mpac/sdicks02/repos/clasher-lease/jobs/" "$root/receipts/leased/$host/"
 nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac --include='exec-policy.json' --include='*.baseline.json' --include='baseline-recalibration-*.json' --include='baseline-idle-refresh.json' --include='early-drain-*.json' --exclude='*' "$host:/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo/receipts/" "$root/receipts/leased/$host/"
done
for host in 127x03 127x04; do
 mkdir -p "$root/receipts/home/$host"
 if [[ $host == 127x04 ]]; then
  cp /mpac/sdicks02/jobs/clasher/tempo*.exit "$root/receipts/home/$host/"
 else
  nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac --include='tempo*.exit' --exclude='*' "$host:/mpac/sdicks02/jobs/clasher/" "$root/receipts/home/$host/"
 fi
done
# Per-attempt wall/worker/clock metadata stays separate from resumed final receipts.
for host in 127x03 127x09 127x13 127x14 127x15 127x16; do
 runtime=/mpac/sdicks02/repos/clasher-lease/tempo-runtime
 [[ $host != 127x03 ]] || runtime=/mpac/sdicks02/repos/clasher-tempo-runtime
 for phase in early-reporting tuning combination reporting hw-corrected; do
  mkdir -p "$root/receipts/attempts/$host/$phase"
  nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac --include='*/' --include='worker-runtime.json' --include='receipt.json' --exclude='*' "$host:$runtime/reports/explore/tempo/$phase/" "$root/receipts/attempts/$host/$phase/" 2>/dev/null || true
 done
done
for phase in early-reporting tuning combination reporting hw-corrected; do
 mkdir -p "$root/receipts/attempts/127x04/$phase"
 nice -n 10 chrt --idle 0 rsync --rsync-path='nice -n 10 chrt --idle 0 rsync' -ac --include='*/' --include='worker-runtime.json' --include='receipt.json' --exclude='*' "$root/$phase/" "$root/receipts/attempts/127x04/$phase/" 2>/dev/null || true
done
