#!/usr/bin/env bash
# copy HEADLINE game jsonl (small) of ExIt evals to 05 scratch for reporting (read-only on hosts)
D=${EV:-/tmp/sdicks02-exit8/ev}; mkdir -p $D
for h in 01 04 08; do J=/mpac/sdicks02/jobs/clasher/bot-exit-r1$([ $h = 08 ] || echo -$h)
  rsync -a --include='ce-*/' --include='ce-*/eval/' --include='ce-*/eval/games-*.jsonl' --include='ce-*/cal/' --include='ce-*/cal/*.json' --exclude='*' 127x$h:$J/ $D/$h/ 2>/dev/null
done
