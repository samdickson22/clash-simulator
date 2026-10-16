# R4 probe findings and focused repairs

R4 REJECTED exact8d54d100b3a594398254366f2f98127de19249cf with two P2 probe
findings. The failed report/typed verdict remain unchanged. All five submitted
local suites passed, but those witness-only tests did not exercise the actual
clone orchestration and failure persistence. No host/build/probe ran on8d.
Native cold Dash fix and cache procedure had no additional actionable blocker
identified, which was not execution approval. Both require the fresh review.

R4-F1: the persistent Python clone was created once, while only native arms
were freshly cloned/reloaded at each pre-step. The proposal's every-boundary
Python-clone claim was not implemented. The revised probe retains the original
independent Python clone and constructs a second Python clone from the actual
reference at every current pre-step. All three Python arms advance independently;
full exports, digests and template proofs are checked. Native clone/reload are
still fresh every pre-step. Exact offset/tick clone requests are retained and
the worker requires the complete40-boundary vector for each successful case.
This covers cold landing, pending loaded seed and first ordinary-clock work
without replacing the uninterrupted reference or weakening comparison.

R4-F2: clone equality asserted before the failed post-step roots were retained;
main caught the case error and worker saw only SystemExit, losing those locals.
The revised case records a context before clone construction, including the
available reference/initial-clone/live-native roots. After all arms are made,
the complete pre-step roots are captured. It tracks each successful arm step
and stores every post-step Python/native root before assertions, template or
comparison checks. Contexts identify arm, offset and active operation. A semantic
first failure has an explicit arm/operation record; clone errors retain the full
traceback and first/failure contexts. Exceptional clone construction, partial
step, snapshot, template or comparison preserves all available arm roots and
per-arm unavailable errors. Existing valid post-step roots are not replaced by
a later failed snapshot attempt. Unstepped/partially stepped arms are identified
by completed_steps and the failed operation. No failed/partial row becomes PASS.

The same five local permitted suites pass. The Dash test now executes the exact
capture_roots/run_case AST with every engine/template/native operation mocked:
it records initial clone plus all40 current pre-step Python clone calls. A fault
triggered only when cloning the post-landing state is detected and preserves its
failed root with paired reference/native/reload states. Additional controls
cover the initial clone, native clone, failed Python/native clone construction,
partially mutating step, missing snapshot, failed template and failed comparison.
The exact main AST then runs all12 failed mocked cases, writes its real JSON to
a self-cleaned local temporary file, and exits1. Read-back verifies the post-step
clone fault and all available paired roots survive every saved case. No engine,
native, Numba, real simulation, host, Cargo or signal action is used. Mock
success proves orchestration/evidence handling, not actual fixture timing/parity.

Engine506 hashes are unchanged from rejected8d; only the probe, its worker proof
and its local tests change, plus scoped reports. No Python reference/comparator/
original helper or initialized-clock semantics changes. New native remains
UNBUILT; historicalf42/both FAIL jobs/source-cache extras/after-import evidence,
all original9fa/11ff/2ac/631ac approvals and artifacts remain preserved. Required
fresh independent exact source/probe/procedure review still covers526 inputs,
then one new source-bound build and nine serial32/12/21/8/2/42/6/2/4 phases. No
new recovery, oldnative copy, extra sweep, final full C56, main or pin switch.
Rollback only the new isolated commits. Whole diagnostic assignment remains
OPEN until actual evidence/reviewed fixes or a concrete parent-dependent blocker.
