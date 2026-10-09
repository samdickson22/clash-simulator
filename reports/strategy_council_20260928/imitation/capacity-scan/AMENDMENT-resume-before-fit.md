# Operational resume repair before fitting

2026-10-09T19:55Z. Original freeze commit841c44b0 remains the scientific plan.
No arm has fitted or produced NLL. The four pipelines are still staging.
16's own SHA verifier PID4049446 was briefly SIGSTOP-paused to prevent its
pipeline entering fitting until this operational repair is committed and pinned.
The other three receivers are still copying; no job or store is restarted.

The initial adapter accepted only the immutable192control checkpoint. It now
also accepts an explicitly SHA-pinned checkpoint in the current wide arm's own
output directory, subject to all unchanged qualified trainer resume contracts.
At a preempted quarter checkpoint, dev/kill processing happens before the next
optimizer step, preserving exactly95,144,680matched rows. A completed saved
quarter measurement is reused if only its control relay/decision was pending.
Scientifically killed arms cannot resume. OwnedSTOP lookup corrected to the
work root, matching the existing resource guard.

Config SHAs, sampler, architecture, seed, recipe, schedule, NLL definition,
quarter boundary and0.005kill threshold are byte-unchanged. Frozen T11/T4 sources
remain untouched. This is an operational correction, not result-based tuning.

Original adapter SHA `56d132b3633df6ea6fdbe063bfe832417fef39ddc445bf93aab680a2c15ae7bd`.
Active adapter SHA `e82ca22fe1eb5f3df3dd2ed1b2bfcac48182212d4cfdc417a8314795e7b0e174`.
Active `freeze.json` binds this repair; PLAN's original SHA stays historical.
The repair and active freeze are committed/pushed before releasing16's verifier.
