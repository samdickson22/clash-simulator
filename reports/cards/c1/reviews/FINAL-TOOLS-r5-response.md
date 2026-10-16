# C1 final-tools r5 implementation response

Original F1–F6/F7 task and full r2/r3/r4 reports/responses remain unchanged as historical evidence. Latest
independent r4 REJECTEDc7de06ea5a6171b4490682a7bb1be9baa825a2b4 for R4-1: a stop before finally's initial
mask could raise out of mandatory cleanup, leaving known child groups and final receipts. It confirmed the
specific r3 per-label exit-storage repair and other six repair classes, both r2 fixes and hashseed correction.

R4-1 is corrected using the review's controlled-boundary alternative, replacing the raising-handler/mask
architecture. STOP_SIGNAL is a one-way latch. TERM/INT/HUP handler only records it; no I/O, mask calls or
exceptions. check_cancelled raises only at explicit safe checkpoints. Child start checks before spawn and
after PID registration; a stop inside Popen cannot break registration. wait uses one-second timeout polling,
stores a reaped status before checking cancellation, then always writes partial phase evidence on unwind.
Mandatory cleanup contains no cancellation checkpoint: entry, TERM/KILL/wait and final phase/all-child writes
cannot be interrupted by the handler, including on a first stop after an ordinary non-signal error. Multiple
stops never erase the latch. Main checks after cleanup returns, before/after temporary PASS creation and after
link/temp removal. A stop observed before the final success checkpoint removes PASS and returns1. That
checkpoint commits success; later requests are after completion. Outer exit0 plus matching receipts remains
necessary. No parent signal masks or mask-entry race remain. Worker defensively clears inherited caller masks;
exec gives workers normal signal dispositions, not the parent's Python record-only handler.

The19-group local suite passes. Added controls call only extracted handler functions with fake processes:
fixture2/root8 after prior0/17, timeout-driven cancellation, repeated stop at cleanup entry and during cleanup,
first stop at cleanup entry after ordinary failure, and stop after gate return/temp write/PASS linking plus
another stop during FAIL receipt. Success publication positive control retained. No real signal/mask/Popen/
worker/host script operation. The stdlib-only interpreter flag probe remains the only actual local child.
All prior schema/provenance/path/status controls remain. AST7 and bash-n pass; exact command/hashes/results
in repair-local-receipt-r5.json and repair-local-tests-r5.log. No engine/native/comparator/followup edits.

r4's failed first harness and entry reproduction remain untouched/hash-bound with its source/logs/receipt.
Large raw tree .bin and complete/focused .delta remain locally intact/untracked; small evidence committed.
Do not rerun old defect-expecting scripts against new source or overwrite their historical receipts.

Fresh independent review must evaluate the COMPLETE original repair plus all r2/r3/r4 objections/responses
and new record-only cancellation boundaries against the new exact commit. No unresolved code finding is
deliberately parked. Owner approval/artifact truth remains explicit owning-lead authority; typed hashes only
bind identities/content. B2 accepted/integrated exact build/affected probes, authenticated full input/platform
inventory, duplicate audit and fresh C56 remain external prerequisites, not invented by these local tests.
No host execution before approval, no engine/integration/gate acceptance, full-byte equivalence or live-pin
promotion claim. Local read-only source/Git/AST/pure/mock/stdlib flag probes only; scratch r5-independent,
no production edits/commits/push, no actual driver/main/run_gate/worker/launcher/staging/host scripts, real OS
signals/masks, engine/native, simulation/build/remote/emulator/deploy/pin. No children/tiny tasks. Strict silence,
direct-owner questions only if blocked, one automatic whole-review result. Preserve every old artifact.
