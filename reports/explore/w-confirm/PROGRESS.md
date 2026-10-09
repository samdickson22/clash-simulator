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

03:42Z: 1,075/1,900 reporting games complete; original/symmetric frozen latency
replays complete. Symmetric full-W one-core p95 320.8 ms; exact WAIT reuse 311.3 ms
with all 125 actions/score vectors preserved. Four-core symmetric reuse reaches
118.6 ms. Profile (eight serial original-W decisions): native step 1.783 s and
native opponent selection 0.537 s out of 3.043 s total; native engine work dominates,
so moving only the loop into Rust is not a sufficient latency fix. Adaptive
one-core style/horizon checks started after the frozen replay exited. Confirmation
continues at the frozen 600/arm target; its full outcomes are not reduced yet.

03:45Z: 1,224/1,900 complete. Coverage audit finds all completed games terminal;
both queues preserve cardinality/conservation. Two seed-95 focal Cannon executions
(control and WW) were rejected; placement is physically masked off at execution,
while the slot/card and 4.0349-elixir balance are valid. Diagnostic replay retains
these games and checks exact telemetry reductions against originals. The reducer's
zero-rejection assumption was incorrect and is removed; rejected commands remain
counted in outcome and ledger reductions. No policy, seed or reporting game changes.

03:49Z: 1,384/1,900 complete. Both diagnostic replays reproduce original metadata
and every ledger statistic exactly; rejections occur at physically illegal Cannon
placements with valid card slots/elixir. No reporting game is replaced. The extra
original-model check reaches one-core p95 178.8 ms by using one style for plays,
but exact action agreement falls to 112/125 (89.6%); play-versus-WAIT agreement is
124/125. Shortening horizon to 80 ticks reaches 185.4 ms but preserves only 89/125
choices. Two styles retain more choices but miss 200 ms. This is a measured
accuracy/cost trade-off, not a win-rate claim or live admission. Symmetric-model
extra checks are still running; all tested rows will be reported.

03:54Z: 1,632/1,900 reporting games complete. All frozen and first adaptive latency
comparisons finished. Final coarse-scan/full-refinement tests use the same corpus,
full-score references, three repeats and one core. They scan all plays once, fully
refine only 3/5/8 leading plays, keep every WAIT fully scored, and compare every
retained score exactly against full W. No new native build or confirmation workload
change. Rejection replay is exact for both cases. Peak actual lane processes so
far is 54 (including the relative-path diagnostic process), combined 57; the
supervisor's label-only own count did not include that diagnostic, which the final
compute audit accounts for explicitly. All remain within the authorized ceilings.
