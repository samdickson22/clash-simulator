# Independent complete preparation review — round 3

**APPROVE — preparation only, exact commit `32eb85cd1814b7414ee6959d5ab5e3da36612ee1`.**

No actionable findings remain in the reviewed preparation. This covers the source/provenance ledger, AST witnesses, read-only JSON inspector and prospective witness plan, including the new constructor-birth correction and the earlier R1/R2 regressions. It grants **no dynamic-cause, parity, ordinary-reachability, fixture-validity/classification, engine, host-execution, actual-witness or actual-coverage approval**. Actual B2 captures were unavailable and were not used.

## R3 constructor-birth correction

The correction faithfully represents the frozen producer's ordering. In B2 `probe_dash_semantic_v1.py`, SHA256 `007005d45a34cebab6b206a126d925a5ce24155f659e43518c333fa7771f8eea`, `one` constructs native state at line 116, enters the comparison loop at 119, and calls `cast(native)` under `lead <= 0 and t == -lead` at 120–121. Its earlier cast is restricted to `lead > 0`. Thus the lead-0 IceSpirit card is cast after construction; requiring actor 8 in that constructor rejects a legitimate prebirth root. B2's read-only wrapper captures the input and native snapshot at that constructor and captures before-state immediately before each paired step. The constructor-plus-relative tick relationship remains valid across this cast.

At `inspect_captured_troop.py:87`, the sole call requesting `allow_unborn` is the IceSpirit initial root. It does not affect either mismatch boundary. Absence produces `actor=None, actor_presence='absent'`; presence produces `actor_presence='present'` with the observed fields. This is explicit observation, not defaulting or equivalence. Asymmetric Python/native constructor presence remains visible and supplies no claim that either capture is valid. Zap and ElectroDragon still require their constructor actors, and every supplied before/after mismatch root still requires its actor.

The submitted pure-JSON suite passes. An independently constructed six-row harness at constructor tick 600 also passes both-seat unborn-to-born controls, present/asymmetric initial states, missing-before and missing-after rejection in each arm, missing-other-constructor rejection, duplicate IDs even in an unborn root, and preservation of distinct meaningful facing/mode-stat values. Static AST inspection independently confirms the single permission callsite. No engine birth or gameplay was executed or inferred from these synthetic controls.

## Earlier findings and whole-preparation assessment

**R1 outcome/error/difference/presence loss: remains CLOSED.** Independent hash-matched JSON controls preserve the real `CAPTURE_COMPLETE` collection wrapper alongside explicit semantic/natural FAILs, validation and additional nested owner errors, natural execution errors, first-boundary differences and later legacy/natural differences. Missing result keys remain missing; explicit null remains null. Only named bulk template/root blocks stay in the hash-bound raw input. Raw bytes remain unchanged. No engine PASS is derived.

**R2 detached timeline: remains CLOSED.** Independent controls reject pre-constructor 599/600 and detached 9000/9001 pairs across all six rows, noninteger/bool/negative constructor ticks, invalid comparison counts and relative index 45. Correctly anchored relative index 44 is accepted for a red structural control. The submitted suite additionally retains the earlier relative/first/after-boundary type and adjacency negatives. Constructor tick plus relative index, adjacent after-state, fixed blue first indices and the frozen 45-comparison/count bounds remain enforced. These are structural checks, not authentication of observed execution.

The independent harness records 130 named checks plus additional assertions; its exact command and complete output are in the receipt. The original R1 rejection/reproductions, R2 approval, historical harness failures and their receipts remain preserved. R2's approval still refers to `2105c2959`; this verdict independently covers the new exact commit.

The complete preparation retains the correct evidence distinctions:

- **Zap:** Python's movement `finally` runs the actual frozen-route finalizer after special movement; C1 native dash travel returns before the ordinary frozen-route branch. Fresh AST controls reproduce retained-route facing, one-node advancement, external-vector ordering and standing/travel stun dispatch. This supports forced-state continuation evidence and candidate correction constraints. Missing old constructor state, residual-stun explanation and ordinary reachability remain unproved.
- **ElectroDragon:** Python preserves heading for quantized-zero displacement; native engaged combat writes zero. The source controls support the candidate, while actual positions, selected target, prior heading and phase remain required. Boundary coincidence alone is not declared causal. Facing remains meaningful continuation state.
- **IceSpirit:** Kind 2 is excluded by `supported`; differential export derives the slow scalar from the live carrier, while native launch retains Stats. Separate flight dispatch does not establish inertness: target-removal cleanup still uses `ordinary`, and generic projectile status consumes the slow scalar. The exact-source cleanup witness reproduces both retained-clock predicate reversals on explicit states. The plan preserves precision/slow-only reconstruction, retained clocks, pending-lethal/finish cases, target death, optional areas/chains, generic children and separate battle clone/reload/gameplay Clone controls. No two-field engine fix or exporter normalization is accepted.

The witness plan remains prospective, preserves meaningful shared-state comparisons and live-reader negative controls, and requires exact old versus current-source witnesses without translating B2 `timer/destination` into C1 `wait/goal`. The independent JSON harness verifies that old dash keys survive unchanged. A supplied hash binds raw bytes; selected observations and equal digests establish neither byte equivalence nor fixture classification.

## Provenance and independent verification

HEAD and reviewed tracked files match the exact commit, tree `fc34fdd43240d40a6346abdd48436c37014ebdf8`. All changes since `e6b017ff6` are C1 preparation/report paths; engine tree `64ed8e5bb66bff6cbe0e746ec59fbd0dd36b48f7` is unchanged. Eight protected launcher/comparator/followup/tool paths match `97171f5`. Original f68/native631ac and launcher approvals remain scoped to their immutable artifacts.

All 16 frozen B2 source bindings independently match their owner-admitted `/tree/` entries and current read-only B2 files; C1 hashes are verified separately. Identity SHA256 remains `7e8e60e7fa12a3833ed1a8c48a22c30c6059e0d621d4d70eccddc2b9c5f6e79b`; the controlling contract remains `0a67e7117fe1b2f69e55acdff2512bdbcdcdb1c9339a0a394a936d55dd5f9172`.

Fresh local helper outputs exactly equal the committed shared-source witness v2 (SHA256 `e097f0617d2bb38966f5d8a4d95806e5e9d9772c1e2cf99dbad958ed5e01eeb7`) and cleanup witness (SHA256 `24a87924685fa4d4746bd3f98e55c2c1cd4a3da8901a8c563982104d97f9cfda`). The original retained B2 difference lists and summary hashes are unchanged. Current receipts match their files; earlier inspection receipts bind historical Git versions. As already recorded in R2, the historical v1 source receipt's pre-commit helper bytes are unavailable and are not reauthenticated; current approval rests on the reproduced v2 witness.

The current B2 collector proposal was read only, at SHA256 `4aceeb4fb3d98790c5280b4893cc187c540563fa7c12c321955ed09c960968ac`, differing from R2's draft. Its constructor/pre-step/comparison convention was inspected; neither producer was imported or executed, and these bytes receive no collector or launch approval.

Permitted local stdlib/AST/mock/JSON checks and `git diff --check e6b017ff6..32eb85cd1` pass. Two reviewer harness failures are retained: treating receipt `base_commit` as the post-edit version, then using unavailable `ast.unparse`. Historical blob lookup and structural AST comparison correct those harness assumptions; neither was a product finding. The JSON receipt binds exact commands, outputs/hashes, source/blob bindings and preservation checks.

Only this report and `review-preparation-r3-receipt.json` were written in the checkout. No engine imports, battle/native execution, simulation, Cargo/build, SSH/scp, host scripts, process polling, gates/sweeps, git mutation/push, engine/comparator edits or children occurred.

## Unchanged acceptance boundary

B2 owns independently reviewed exact bounded collection/host bytes after the frozen old collector becomes terminal; this review did not poll it or authorize launch. Actual captures, supported fixes, meaningful continuations/regressions and fresh independent implementation review remain required. CARD LEAD's frozen B2-first prerequisite controls integration; no pre-copy selectors or immediate combined build/gate/sweep.

B2 exact-source C56 precedes combined C1 C56. Preserve all applicable failures, all31-source/40-offset/both-seat and C1 selector/counter/projectile/clone/reload coverage, then exact combined-native C56: 577 fixtures/chains, 429 reference parity, zero native errors, 600 roots (300 full/300 cut), 12 games/1800 selections. No filtered acceptance, new normalization or identity waiver follows from preparation approval.

