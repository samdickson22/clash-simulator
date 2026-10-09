# Technical amendments

2026-10-09, before reporting games: add process supervision and one-core-per-worker
pinning to the frozen harness. Neither changes game/search configuration. Smoke games
may exercise infrastructure; reporting remains frozen at 600 paired seeds per arm.

Latency addition, before latency comparisons: the existing `rollout_commands` path
can also represent original W's immediate opponent by setting opponent_delay=0 and
capacity=1. Include native-full, native-dedup, native-wait1/2, native-gate4/6/8 and
native-threads4, on the same frozen decision states. Verify native-full against original
Python W's complete score vectors. This tests moving the unchanged command schedule
into Rust, in addition to the originally planned cheap reductions. Keep original-W
and symmetric-d27 results separate. No reporting outcomes or agreement measurements
were inspected to choose this addition. The four-thread arm remains explicitly over
the primary one-core budget.

Build source and all admission files are retained under the new 03 task directory.
The new binary is SHA256
`542ce0977b98251d04047560a4a30fd0e54ab1002dbd49800e5056445c81153c`.

03:34Z latency-only addition, after the original frozen comparison completed:
WAIT-only reductions preserve most decisions but cannot bring its one-core tail
below 200 ms; the dense immediate-play tail dominates. Benchmark first one/two
styles for immediate plays (`plays1/2`), first one/two styles for all candidates
(`all1/2`), two styles for plays plus one for timed waits (`plays2wait1`), and
80/100/120-tick horizons. These are approximation trade-offs, not confirmation
arms. Use the same previously frozen 125 public states, candidate lists, full-W
references and three repeats; show every tested variant without win-rate claims.
No reporting outcomes inspected; reporting workers' loaded implementation and
workload are unchanged. Added branches serve only the latency consumers. Early exact
comparisons show all 125 actions preserved by WAIT reuse and native full scoring.

03:44Z reducer-only correction: a coverage/queue audit found one physical deployment
rejection in each of two seed-95 games (0 and WW). Queue conservation/capacity still
holds. The reducer's initial zero-rejection assumption was stronger than the actual
delay-fixes protocol, which intentionally releases rejected commands without refund.
Retain every game and count rejections; remove only that incorrect assertion and
include `rejected_play_fraction` / both-channel totals. Replay the unchanged two
cases for diagnostics; do not replace them or change the policy/config/seeds.
