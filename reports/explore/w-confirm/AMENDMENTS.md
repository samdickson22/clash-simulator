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
