# W confirmation progress

2026-10-09 UTC: preparing frozen search-vs-search study for coordinator 0523ae6f.
No games have run. Confirmation target is 600 paired seeds × 3 arms plus 100 W-vs-W.
Read tempo results/audit, command-delay research, delay-fixes implementation and
quickwins qualification. All changes live under this lane; shared owner files
are untouched. Only 127x03 is admitted for computation.

Compute preflight at ~03:03Z found no active simulations on 03; the existing
validation-cache service has three wrapper/service processes. Reservation searches
in fleet documents and task/job directories found no separate 03 reservation.
Reserve at most 56 own processes, leaving room for delay-fixes' authorized 40 and
the existing cache service within the combined 100 ceiling. Use 50 fork workers,
one parent and one supervisor, with profiling/build work within the remaining four.
Recheck the process census before launch and monitor the aggregate during runs.

03:17Z: frozen plan pushed in `e006fdba`; infrastructure/qualification additions
in `a4146d51`. Private native build completed on 03 (one idle-scheduled compiler).
Two smoke seeds × three arms completed all six games at the terminal bound.
Timed-WAIT independent schedule qualification passed 156 score/event/digest checks.
Original W wrapper and native original-W path match ten complete original score
vectors. Ordinary native candidates match the supplied quickwins build48 binary
on 84 score/event/digest checks. Compact receipts are under `receipts/`.

Reporting launched detached via setsid at ~03:17Z: 50 workers, 1,900 target games,
main arms 600 each and WW 100. Supervisor PID 1110669; latency PID 1110746.
Raw data/build/cache root (03 only):
`/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/`.
Full confirmation uses all three styles and original candidate coverage.
Latency replay uses a separate 125-state frozen public corpus, all 25 matchups.
Every candidate list and root will be regenerated and checked before timing.
The independent reference verifier's first attempt was stopped after freezing
the corpus because serializing its entire 2 MB native state every tick was
unnecessarily costly; the efficient rerun checks the same final states/events.
No reporting work was interrupted or retuned.

03:21Z: 123/1,900 reporting games complete. Peak observed census so far: 53 own /
56 combined. Latency replay's first warmup exposed a mutable PyO3 root borrow in
the four-thread original-W variant; fix gives concurrent opponent-selection calls
private roots. Only that variant changed, and the latency replay restarted on the
same frozen corpus; reporting's full native path and loaded worker modules were
unaffected. Candidate/RNG/public-root replay checks passed for all 125 states.
Smoke reduction validates paired identities, queue conservation, terminal games,
zero command rejections and pooled metric bookkeeping. No reporting outcomes used
for tuning. Supplementary WW CIs will use a separate descriptive 100-seed bootstrap.

03:28Z: 431/1,900 games complete, confirmation unchanged. Stronger timed-WAIT
qualification also passes equality of **complete final snapshots**, not just the
engine digest, for all 156 checks. This closes the digest's limited-field coverage
concern. The source snapshot matches every supplied quickwins build48 Rust source
hash before the private WAIT extension. Updated qualification and exact public
root/candidate replay receipts are committed separately from raw states.

03:37Z: 843/1,900 games complete. Original latency comparison (125 states × 16
variants × 3 repeats) finished. Exact native-full and WAIT reuse preserve every
action and complete score vector. One-core original full W p95 is 358.7 ms,
dedup 345.8 ms, native-dedup 336.7 ms. Four-core native-threads4 p95 is 124.2 ms;
it exceeds the requested one-core budget. WAIT-only approximations do not reach
200 ms. Added the latency-only tail trade-offs documented in AMENDMENTS: smaller
style counts for plays/all candidates and shorter horizons. Reporting outcomes
remain uninspected and its loaded full-work policy is unchanged. Symmetric-model
latency replay is nearing completion; the extension starts only after it exits,
avoiding overlap on the timing core.
