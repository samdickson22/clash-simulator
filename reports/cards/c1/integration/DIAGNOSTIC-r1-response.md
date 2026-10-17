# Diagnostic r1 repairs and expanded meaningful coverage

Independent r1 **REJECTED** exact75748b45f144165374b122bbff766543606721b0.
Raw REVIEW-diagnostic-r1.md SHA256
`59160d8a815da63e8a6acc9c4370e240036f15915350c3b279bbf41dbe6f3d91`
and diagnostic-review-r1.json SHA256
`604c18f1f6cbe8ccf887c95641cb3bf73b9f6db9e0046f2127c8257c2be99bec`
are preserved unchanged. No host/build/native execution has occurred.

- **D1, duplicate inherent recovery helper:** remove only clone.rs's duplicate
  recover_ground definition. Clone, dash and leap now use C1 dash.rs's existing
  pub(super) helper. Both parents clamp to the same intervals, scan dy then dx
  in the same ascending500-unit order, skip the same out-of-bounds/water points
  and replace only for strictly smaller identical metric. Its maximum possible
  metric is far below either initial sentinel, so the differing sentinels cannot
  affect choice. Clone's footprint fallback/revalidation, slide timing and all
  callers remain unchanged. Source check requires exactly one definition; actual
  compilation remains unproved. Add existing B2 six Clone bounds and two
  water/building recovery cases, plus four existing C1 dash/leap cases, to the
  same bounded fresh-build job rather than invoking a full sweep.
- **D2, failed-probe after evidence:** collect loaded module paths/hashes before
  validating result JSON, including FOCUSED_FAIL/partial results. Validate source,
  admission/build identities, initially loaded files and own Python module paths
  independently, retaining each error. Always write after-import inventory and
  identity errors for these probe outcomes; errors fail the worker without
  discarding its original failure. Full AST/mock worker executions cover a
  semantic failure, an exceptional partial result and a failed source inventory.
  All retain after modules and worker error/exit1; drift also retains its own
  identity failures. No engine or host is imported/executed by these controls.
- **D3, causal control errors:** leave the original Batch A helper and its
  historical outcomes intact. New probe_first_update_diagnostic.py reuses its
  exact21 fixture definitions/mirroring, but retains full real/control outcomes,
  completion counts, actual observed victim identity/creation point/HP/stats
  hash, initial/partial/first-bad roots and commands. It discovers victims
  created by script deployments instead of fixing an empty list at construction.
  Controls retain victim creation commands and remove attackers/opposing crown
  towers; actual victim identity and initial state must match the real fixture.
  A completed valid no-death control is distinct from a failed or missing victim.
  All42 rows remain required. Full AST/mock executions prove script-born victims
  are observed, a real death differs from a complete no-death control, and a
  thrown control step error is retained/rejected. Additional negatives reject
  missing/error/partial controls and mismatched identity, pose, HP, stats or tick.

User's renewed end-to-end requirement also adds8 explicit selector continuations
before diagnostic completion. Both seats exercise secondary/chain selection with
travel and idle positive controls, uninterrupted/native clone/reload/Python
clone and the unchanged frozen semantic-v1/template prerequisites. Secondary
Python on_attack_start observations retain actual primary/reserved IDs and live
target/effect gates. Native has no exported reservation field: its combat-phase
primary, Bandit and distractor HP/status provide a bounded effective-choice
witness with paired idle controls and source-inspected two-recipient count.
The report labels this inference precisely. Native chain release, visited IDs,
target, aim, wait and eventual delivery are observed directly against Python.
No guessed area gate is introduced. Wrong reservation/visited IDs, duplicate
membership, aim, delay, effect guard, no attack/impact and wrong damage are
rejected by both-seat AST/mock witness controls. Actual8-case coverage remains
NOT RUN and needs independent source/probe/procedure review first.

The review's source correction is retained: unlike old C1, frozen merged B2
collide already consumes/caps/divides an already queued controlled vector in
dash travel. That old early-zero explanation is not asserted for current merged
source. Actual finalizer order/threshold witnesses remain strict; no source-only
reasoning proves native parity. Other original FAILs and normal-reachability
limitations stay unchanged.

The new D2 mock test's first attempt mistakenly moved its synthetic build.json
while archiving a prior case, so a subsequent control failed with missing build
receipt. Fixed the harness to archive only shared-phase files; no real build or
artifact was involved. Local Python3.8 lacks Path.is_relative_to; the worker's
own-path check now uses canonical component-aware os.path.commonpath, enabling
the same real path predicate in local controls and remote3.12. The failed mock
attempt is retained in procedure-local-r2.json. Three local suites now PASS.

Only clone.rs native source changes from757 for D1; native is still UNBUILT.
Fresh exact-source/postmerge/probe/procedure independent review must approve
the revised commit and full input set before one admitted08 CPU4/nice15/j4
build and bounded phases32/21/8/2/42/6/2/4. Failures/partial data stay failures.
No old native, duplicate sweep, final full C1 C56, main/pin/runtime action.
Later reconciled B1/current-main freeze and complete required evidence still
precede final acceptance. Rollback only new isolated integration commits,
preserving9fa/ref, original11ff/C1, prior approvals, failed pool check, all old
FAILs, rejected reviews and raw artifacts. This is not diagnostic completion.
