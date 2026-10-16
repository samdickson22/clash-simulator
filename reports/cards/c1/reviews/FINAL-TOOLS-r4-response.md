# C1 final-tools r4 implementation response

Original six-finding assignment/F7 docs correction remains as in r2-response and CARD LEAD original
C1-final-tools-r1.md. Full r2 and r3 verdicts/responses/artifacts are retained, not superseded as evidence.
The latest r3 independently REJECTED4bfae6b0844b4620d9482cc996a74bf86f1a1887 for R3-1: later wait interruption
lost earlier reaped exits. It confirmed both r2 startup fixes, hashseed correction, and other repair classes.

R3-1 repair: Children.completed is a label-keyed persistent mapping. Each observed status/command/time/PID
is stored before its live entry is removed. A signal in the gap leaves one identity; cleanup preserves its
original row without overwriting or duplicating it. wait's finally writes a partial phase-exits.json even
when a later wait raises. Cleanup writes phase-final-exits.json and all-child-exits.json containing the union
of prior observations and stopped children. Expected phase labels are registered before any spawn, so a
startup interruption is also represented. No status-PASS inference from partial receipts.

Whole-class cancellation boundary audit: spawn/PID registration and phase-receipt writes temporarily block
TERM/INT/HUP; deferred signals are restored only after identity/receipt preservation. Workers reset their
inherited mask immediately before bootstrap/dispatch, so their normal cancellation and pool descendants
are not left masked. Final cleanup similarly defers repeated stop signals through cleanup and final receipts,
then restores the mask; pending cancellation raises before success publication. Only known child PGIDs are
stopped. SIGKILL/power loss are not catchable; outer successful exit plus complete receipts remain necessary.
This is launcher bookkeeping, not an engine or queue mechanic change.

Local revised16-group suite PASS, including both fixture2/root8 interruption after prior0/17 exits, a stop
immediately after persistent store before live deletion, and deferred spawn cancellation after PID registration.
Mocks intercept Popen/killpg/signal-mask operations: no actual worker/process signal or mask modification.
Only the existing stdlib interpreter flag probe starts a local child. Original success/nonzero/signal,
confinement/control/identity/schema negatives remain. AST7 and bash-n pass. Exact commands/hashes in
repair-local-receipt-r4.json, log repair-local-tests-r4.log. Engine/comparator/followup unchanged.

Preserve r3-independent's failed first harness/reproduction artifacts and exact source/receipt bindings.
Its large raw Git-tree .bin and complete/focused .delta files remain untouched in the local scoped directory;
small receipts/source/logs/reproductions/verdict are committed. Hashes/paths to all originals remain in its
receipt. Do not rerun old defect-expecting scripts against new source and rewrite historical receipts.

Fresh review must cover complete repaired launcher and ALL earlier objections/responses, especially signal
unwind/duplicate/phase/start boundaries, against revised exact commit. No code finding intentionally deferred.
Review only local source/Git/AST/pure/mock/stdlib flag probes; no actual host driver/run_gate/worker/launcher,
engine/native import, simulation/build/remote/emulator/deploy/pin, or other worktree writes. New reviewer
scratch under r4-independent; no children/tiny delegates, no production edits/commit/push. Strict silence,
direct-owner questions only if blocked, one automatic complete review delivery. B2 accepted/integrated exact
build/affected probes, authenticated platform/input inventory, duplicate audit and fresh C56 remain external
prerequisites, not supplied by these synthetic checks. No live pin change or complete byte-equivalence claim.
