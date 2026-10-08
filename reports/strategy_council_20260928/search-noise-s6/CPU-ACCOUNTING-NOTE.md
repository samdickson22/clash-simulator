# S6 CPU attribution note

Final attributable metered CPU is **22.762008333 core-hours**: 22.302988889
confirmation supervisor/worker hours plus 0.459019444 preflight/operation hours.
Completed-game CPU is 21.125244294 hours and overlaps the supervisor total.
Interrupted work is included in supervising GNU time. Small transfers, final
reporting and unidentified mirror-process CPU are unmetered.

Seven foreign-host log copies appeared in the 04 jobs directory: six exact
copies and one exact prefix of the completed collector log on 01. The reporting
attribution audit verifies these against owner-host bytes before excluding them.
It preserves compute-audit-before-attribution.json and cpu-log-evidence/. This
removes 510.85 duplicated seconds and a spurious missing-timing flag. All genuine
owned detached-job logs have timing. No frozen analysis source, outcome, CI or
raw receipt changed.

The first post-analysis attribution script attempted SSH from 01 to itself,
which this environment refuses. The correction reads local owner logs directly;
the initial script is preserved as audit_cpu_attribution-r1.py. The original
aggregate was not overwritten by the failed attempt. This reporting-only script
and make_summary.py are outside the frozen execution manifest.

Do not rerun compute_audit.py over the corrected report: it is the frozen generic
log scan and would reintroduce mirrored copies. The corrected accounting and
original aggregate are both retained. No S6 workload remains running.
