# K-v2 cyclic-GC guard

Recorded 2026-10-10T02:16:56Z before retained reporting.

Smoke-r2 completed32 terminal games but3 cut returns exceeded deadline+8ms (14–53ms overruns). An eight-game V120 stage-timed replay, one game per worker, did not reproduce these residuals: all maxima<120ms and maximal in-decision GC≤0.5ms. Their cause is not proved. The earlier165ms belief tail is separately identified and fixed.

A new guard disables automatic cyclic collection only during complete own/opponent decision windows, restoring the prior setting on success or exception. Reference counting remains active; logical preparation/scoring stays inside the timer. Automatic collection remains enabled between decisions/physics steps; all pauses are metered by duration/generation/location and whole-game wall/CPU includes maintenance. This prevents a known non-cancellable Python pause on reused workers without claiming it caused the three observations. Native/scorer/posterior transformations/defaults/seeds remain unchanged.

25 tests pass, including deferred automatic collection, exception restoration and preservation of previously disabled GC. Final32-game smoke-r3 must pass zero cut returns beyond deadline+8ms before reporting-r2. All earlier smoke/diagnostics and the zero-terminal reporting attempt remain excluded. Mac loaded end-to-end gates must include background maintenance and packet gaps; moving automatic collection out of a decision does not make its system cost disappear.
