# R2 approved procedure: actual pre-build driver failure and repair

R2 approved exact18d6f9e05 and its524 inputs for one bounded execution. Actual
launch `c1diag-20261016T152715Z-r1` on08 at15:27:29.837546Z used PID/PGID3502954,
direct CPU4/nice15 and the frozen review/manifest/platform/admission. It failed
before `Children.start` could open build.log: parent setgid inherited by
mkdir(0700) produced2700 on job/output. The unchanged reviewed controller
correctly rejected output permissions. Its cleanup receipt hit the same guard;
the driver's unguarded stop masked the original exception and terminal write.
No build log, child receipt, target directory or new native exists. This is an
actual failed execution, not a diagnostic PASS or a completed cleanup claim.

Failure pointers/hashes, modes and exact launch are preserved in
diagnostic-152715Z-failure.json and the immutable remote job; the seven small
control/log/before artifacts were copied read-only to named local scratch.
Read-only known-PGID and lease checks found neither live group nor lease. These
observations alone do not bypass prior-job admission. The old output and all
source, controls, modes, original approvals and FAILs remain untouched.

The candidate creates new private directories with explicit chmod0700 after
mkdir, then verifies real canonical ownership and exact mode. It verifies all
four private directories again before build. It retains the controller's strict
guard unchanged. Driver finalization now records cleanup exceptions alongside
the original failure, writes a FAIL terminal when possible, and keeps
cleanup_complete=false on any cleanup exception. No guessed successful child
exit or native result is created.

`diagnostic_recover.py` is a separate, narrowly reviewed closure for this one
exact pre-build failure. Its hardcoded old job/commit/PID/PGID/driver and seven
control/log SHA bindings plus full manifest source/data inventory must match.
It rejects symlinks/foreign ownership/unexpected files or directories (including
build log, target, native or existing terminal), altered failure text/modes,
live recorded PID/group/session, recorded accounting files or any matching
group lease. It serializes with the same stage lock and rechecks the complete
evidence before its sole exclusive write: output/terminal.json retaining
DIAGNOSTIC_FAIL, original traceback and all artifact/mode hashes, exact new
review/script/source bindings and fresh no-process/no-lease evidence. It never
signals, deletes, changes old modes or source, launches a child or imports an
engine. A changed/incomplete state blocks closure. New review must explicitly
include recovery=diagnostic_recover.SPEC; full inventory gains this19th extra.

Only after fresh independent exact-commit approval may the owner run recovery
once, read and hash that FAIL terminal and verify liveness again, then stage one
new source-bound tag for the still-unperformed fresh build and eight bounded
phases. No old tag retry, copied binary, second concurrent build or full sweep.
The local Python3.8 lacks Path.is_relative_to; the original actual local stage
used existing Python3.12.12 venv at nice15. Use that same interpreter for local
reviewed recovery/staging, with no engine import. Remote build/probe limits stay
CPU4/nice15/Cargo-j4; final fullC1C56/main/pins stay withheld.

All prior D1–D3 source/control/evidence repairs and selector/Clone/terrain phases
are unchanged. Engine506-file inventory is unchanged from18d. Four local suites
pass; new controls reproduce actual inherited2700 on a setgid temporary parent,
verify exact0700 creation, preserve original+cleanup errors, reject fake
build/source/terminal drift, live PID/group/session and accounting files. The
first new mock fixture had an incorrect gamedata path; its KeyError is retained
in procedure-local-r3-tests.json and the fixture was corrected. These are local
stdlib/mock tests, not continuation evidence. The whole diagnostic assignment
remains OPEN until actual phases/fixes and diagnostic evidence are complete or
a concrete parent-dependent blocker arises. Rollback is isolated tool commits;
preserve old failed job and original refs/artifacts. No deployed state changed.
