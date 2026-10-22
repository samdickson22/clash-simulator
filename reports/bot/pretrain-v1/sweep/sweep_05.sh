#!/bin/bash
# 127x05: game evaluation of the size-sweep anchors (same 400-case r2 HOG26-acct eval vs the live search), then
# paired size-vs-size comparisons. One eval_rsim at a time on 05. Started via LAN ssh (outside the T3 process tree).
set -u
SW=/mpac/sdicks02/scratch/pretrain-v1-dev/sweep
REMOTE=/mpac/sdicks02/jobs/clasher/pretrain-v1/bc-sweep
REPO=/mpac/sdicks02/repos/clasher-pretrain-v1
R2=/mpac/sdicks02/scratch/rl-search-prior-20261020-r2
FINAL=/mpac/sdicks02/scratch/pretrain-v1-dev/final
log() { echo "$(date -u +%FT%TZ) $*" >> $SW/sweep_05.log; }
wait_free() { while pgrep -f "[e]val_rsim.py --ckpt" > /dev/null; do sleep 120; done; }
evaluate() {   # name
  local n=$1
  until ssh -o BatchMode=yes 127x08 test -f $REMOTE/select-$n/selection.json < /dev/null; do sleep 300; done
  mkdir -p $SW/anchors/$n && scp -q "127x08:$REMOTE/select-$n/*" $SW/anchors/$n/
  local ck=$SW/anchors/$n/anchor.pt; [ -f $ck ] || ck=$SW/anchors/$n/PROVISIONAL-not-admitted.pt
  log "anchor $n $ck $(sha256sum $ck | cut -c1-16)"
  if [ "$n" = S100 ] && [ -f $FINAL/selection.json ] && \
     [ "$(sha256sum $ck | cut -c1-64)" = "$(sha256sum $FINAL/anchor.pt 2>/dev/null | cut -c1-64)" ]; then
    log "S100 anchor == registered S anchor: reuse final/eval-a"; ln -sfn $FINAL/eval-a $SW/eval-$n; return
  fi
  wait_free
  (cd /tmp && $R2/run.sh $REPO/bot/pretrain_v1/eval_rsim.py --ckpt $ck --out $SW/eval-$n --arm pv1-$n --workers 24 \
     > $SW/eval-$n.log 2>&1)
  (cd /tmp && $R2/run.sh $REPO/bot/pretrain_v1/eval_rsim.py --out $SW/eval-$n --arm pv1-$n --summarise \
     > $SW/eval-$n-summary.log 2>&1)
  log "eval $n done"
}
log "sweep_05 start"
for n in S100 M; do evaluate $n; done
for pair in "M S100"; do
  set -- $pair
  (cd /tmp && $R2/run.sh $REPO/bot/pretrain_v1/compare_arms.py --a $SW/eval-$1 --b $SW/eval-$2 \
     --out $SW/compare-$1-vs-$2.json > $SW/compare-$1-vs-$2.log 2>&1)
done
log "sweep_05 done"
