# R5 selector evidence finding and catch-path audit

R5 REJECTED9466f58eaa49747b34e3d48a50eb55384ac6f451 for R5-F1/P2: the selector
probe asserted clone equality before retaining failed post-step roots. All8
mocked rows failed correctly, but saved only two prior frames/traceback, losing
the third-tick failing clone and current reference/native roots. D2 module
receipts cannot recover an already unwound caught case. The immutable R5 report
and typed verdict are preserved. Both R4 Dash findings were independently
confirmed repaired; no source or host execution approval followed this REJECT.

The selector now uses the same read-only capture_roots helper already tested in
the Dash probe. Its transitive file is already in the526-input capsule. Before
clone construction and each step it records available roots/offset/operation.
After all steps it retains every Python/native post root before template,
clone/digest or semantic assertions. It records completed arm calls, native
debug phases, the first semantic arm, first/failure/current contexts and the
original traceback. A malformed debug JSON keeps the raw returned text, and
marks that the live debug-step returned before parsing failed. Construction,
partially mutating step, snapshot, template, comparison and digest exceptions
retain all available/partial arms and explicit unavailable-root errors. Good
already captured post roots survive later recapture errors. Main retains the
full case in both per-case and final JSON, never projecting away this evidence.

Selector fixture/actions, reservation observers and their paired lists,12-tick
window, all8 identities, strict semantic-v1/templates, exact visited IDs/aim/
wait/impact and native secondary inference limits stay unchanged. Its Python
and native clone/reload arms continue from the constructor as originally
specified; the separate Dash12 phase continues to require fresh pre-step arms.
No target guard, ID assumption or comparator rule is added. No state or snapshot
is rewritten by capture: this is additional read-only diagnostic evidence.

The expanded selector test executes exact helper/run_case/main AST with fake
engine/native APIs. It injects Python-clone state77 at tick3 and native-clone88,
digest-only drift, partial Python/native steps, snapshot/template/comparison
errors, Python/native/reload construction errors and malformed debug JSON. It
checks the failing arm, available paired roots and partial-step inventory. Exact
main writes all8 failed cases to local temporary per-case/final files; read-back
proves they retain clone77 and paired reference/native/reload tick3 roots, and
the process returns1. All temporary files self-clean; no engine/native import.

Catch-path audit also found an analogous trace-only return in the new C1
first-update diagnostic helper. Its error path now records operation, offset,
completed Python/native calls, the retained before root and available current
post roots for both real and control runs. Snapshot failures become explicit
unavailable errors without replacing the original traceback; intentional no
native control is represented as None. Causal/control validation remains strict
and unchanged. Mocked Python partial step, native partial step and unavailable
snapshot checks pass. The exact first-update main runs21 synthetic definitions
through both names/42 rows, persists each failed real/control result, exits1,
and read-back verifies partial roots. This tests persistence/denominator wiring,
not actual mirrored mechanics or the real21 fixtures. Original Batch A helper
and CASES are unchanged.

Original shared32, Ronin/boulder21, axe/origin2, B2 Clone6/2 and terrain4 probe
sources remain byte-identical. Their existing first-bad/partial/worker failure
evidence and strict failure statuses remain; this audit does not claim every
legacy exception retains every post arm. No missing/errored/partial outcome may
be accepted. If actual execution exposes a legacy evidence gap, retain its FAIL
and diagnose it with a reviewed bounded follow-up before claiming completion.
No generalized tracing, snapshot normalization, global catch suppression or
edits to B2-owned files were introduced.

Five permitted local stdlib/AST/mock suites PASS; exact output/source hashes in
procedure-local-r6-tests.json. Engine506 hashes remain the rejected8d inventory;
only selector/first-update diagnostic tools and their tests change plus scoped
reports. Source cold Dash/cache fix is still unbuilt/unexecuted. Preserve both
old FAIL jobs/f42, all after-import/source-cache errors, original9fa/11ff and
2ac/631ac reviews/artifacts. Fresh independent exact full source/probe/procedure
review must precede one new source-bound build/nine phases32/12/21/8/2/42/6/2/4.
No recovery/borrowed native/JIT cache/duplicate sweep/fullC56/main/pin action.
Rollback only isolated commits. Assignment OPEN until actual diagnostic evidence
and reviewed fixes or a concrete parent-dependent blocker; later reconciled
B1/current-main freeze/full C56 and remaining broad coverage stay mandatory.
