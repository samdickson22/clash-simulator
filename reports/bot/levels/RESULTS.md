# Level-aware search pilot: interim evidence (exploration)

2026-10-16, resumed by Sol high. [Progress and audit](PROGRESS.md), [design](DESIGN.md).
**No primary pilot bank drawn or strength outcomes collected.** All mandatory gates now pass:145 catalogue classifications/1024 exact-binary taps,9 cold isolation tests,216 integration tests,254 native checks, and8 clean all11 rows/4A-Bcommandhashpairs/positive B roots/zero rejections. Exact original support was restored under review; seven cache files remain unchanged. Fresh pre-registration and100-case bank are next. Earlier failures remain preserved. The required s27 replay completed23/23pairs, changing3actionIDs+3wait durations with no Cannon chosen. [Replay result](S27-M02.md).
BOT LEAD accepted the reversible serial design and fixed supported-card scope before outcomes.

## Verified evidence

- RoyaleSim mixed-level reset: level-6 towers have 3312/2030 HP; Musketeer at L4/7/11 has 375/496/721 HP.
  Original job log `rsim-probe-01.txt`, SHA256 `287e3d23b993713dd29ab81ac5a19274950ec1033a55c1ba5bb15718d0a2df95`.
- Harness DEV base 1: four A games, repeated twice. All four command hashes, own logs and tower HP match;
  eight wins, zero errors/rejected deployments/search failures/translator diagnostics. First run 96.364 CPU
  s/game and 98.576 wall s/game; repeat 97.321 CPU s/game and 99.505 wall s/game. Four original unit tests passed.
  [Receipt](receipts/harness-dev-audit.json). This is runner determinism evidence, not level-aware strength.
- Fresh pinned-runtime mapping: **121/121** cached L11 exports match the native JSON. The initial raw-Python
  comparison was 3/121 because disk JSON changes coordinate tuples to lists. No export stats were changed.
  [Executed schema/tower receipt](receipts/gates-schema-towers-r2.txt), SHA256
  `cd30432de666b2e58929f59702c358b630298f36bb7c93127038b93a31b04645`.
- Tower checks: **13/13 pass** — eight HP/damage curve checks at L10/12 and five L4–8 HP checks against RoyaleSim.
  The earlier Archers catalogue alias failure is preserved in [the failed receipt](receipts/gates-towers-r1.txt).
- Two regression tests pass: cached tuple/list representation versus real damage differences, and tower-shot
  HP preservation. [Receipt](receipts/pytest-configs-r2.txt), SHA256
  `615346574e154b3beff92a0c3300cc216b1d715cbac6441c7dbf923797c8c68f`.
- Existing exports at L4/5/6/7/9 contain 118 cards and three explicit errors: Clone, Earthquake, Tornado.
  L11 contains 121 cards, zero errors. All original export logs are preserved under receipts.

## Fixed scope and interpretation

No selected true-deck projection is lost (0/54). The belief catalog restriction removes 425/2925 decks,
15,371/69,380 frequency weight = **22.15479965%**, identically for every experimental arm and policy controller.
The original projection catalog stays immutable; selected projection equality is asserted before bank creation.
[Scope audit](receipts/scope-audit-r1.json), SHA256
`c7f2c5beac6c67da79ddb4295900978b6ae6f41af40d8dbe5fb841005ef8334d`.
This is a conditional-population physics pilot, not literal current-live-prior equivalence. Missing playable or
identified body exports fail closed. There are no outcome-dependent exclusions or silent L11 substitutions.

A uses L11 roots/config/native; B0 uses the existing root-only scaler (own producing-body levels,
opponent body default5 without rarity adjustment, tower input6 on the legacy card ladder; rollouts/meta11).
B uses exact own levels, a fixed fair
opponent estimate, tower curves and per-seat rollout templates. B's crown metadata changes both leaf evaluation
and scripted crown spell lethality/Lightning ordering. Identical-state learned features remain equal at that
layer; the complete public view is not claimed invariant. [Bounded source diagnostic](receipts/leaf-diagnostic-astra-r1.md).
The pilot is serial; it makes no pooled LIVE integration or immediate promotion claim.

## Native gates passed; complete-game parity pending

The corrected native suite passed **254/254** checks: exports, towers, mixed seats, spell impacts,
32 public root bodies, snapshot/cut/cache transport and fair-information roots/decisions.
[Executed receipt](receipts/gates-all-r11.txt), [raw snapshot audit](receipts/gates-r11-owner-audit.json).
Both native snapshot comparisons differ only because serde emits absent `spell_name` as an empty string
(10 fields per seat). There are no numeric/type/entity/order/position/qualified-key changes.
Thirty action values each match their uncut references through cut, snapshot and one-worker raw-fc transport;
A→B→A changes then reuses the content key, with shipped cache sizes [1,2,2]. Four real B decisions invoke
roots under identical public states and different hidden opponent levels; roots/commands match in both seats.
This scripted balanced transport check makes no learned-pool or LIVE deployment claim.

Final harness source review R12 conditionally approved execution; matching-byte tests passed114/114.
The forced-all11 run completed all8 rows and matched4/4 A/B command hashes, with positive B roots in all4games.
It **failed acceptance**: Cannon deployments were rejected identically in both arms (case1 OUT_OF_TERRITORY3;
case2 OUT_OF_TERRITORY1 and WATER1 per arm). Parent exit1/report qualityFAIL; zero nativeFAILURES.
The complete failed run is preserved in the job directory, with [audit](receipts/all11-r12-failed-audit.json)
and [report](receipts/all11-r12-failed-report.txt). No primarybank has been drawn. The [bounded source diagnostic](receipts/territory-diagnostic-astra-r13.md) located the shipped simulator
ordinary-building own-half rule, while the native/public mask opens troop bridge/pocket territory for buildings.
A reviewed common public mask intersection now passes the exact-binary placement probe described below; integration acceptance remains blocked.
It amends actual command eligibility identically in every arm/controller, with weights, feature definitions
and native rollout physics unchanged. No gate is relaxed or case excluded. Repair requires fresh independent
review, binary probe, meaningful integration tests and the same complete all11 bank in a fresh output. Original deferred probes on03 have twice exhausted
30-minute admission windows without running; full-pool priority is preserved and no retry is left queued.
BOT LEAD explicitly accepted this as a nonblocking resource deferral: the reviewed matching-runtime suite
supplies physics, transport and fairness evidence. No additional03 window or retry is needed.

The required s27-m02 offline diagnostic is complete; [its result and limits](S27-M02.md) support no causal conclusion. No account/emulator actions,
frozen-runtime edits, pin/model changes or LIVE deployment occurred. Rollback selects standard A outside the
experimental factory, preserving all original catalogs and receipts.

## Exact-binary placement evidence and remaining blockers

The reviewed R14 probe exited0 with64/64 Cannon fixtures:40 expected refusals and24 accepted controls. All16 boundary controls relocated inward to own centre y13.5, preserving a fitting3×3 box. [Binary receipt](receipts/placement-micro-r14.json), [owner audit](receipts/placement-micro-r14-owner-audit.json).

This is **Cannon-only PASS, overall placement blocked**. Knight and Minions at the tested bridge edge were refused as WATER in both seats, while the shared public mask admits that location; tested bridge-interior/home controls and all six Fireball controls were accepted. No dependent test/native/all11 run was launched after that contradiction. This historical failure prompted a common public geometry correction; the subsequent v3 result below confirms the selected simulator placements.

Fresh review also found a resume provenance gap: frozen imitation policy/mask/feature Python sources were absent from the runtime manifest. Their source closure and resume-tamper regressions were added, then raw-token identity was also repaired and freshly reviewed, without changing runtime behavior. [Review](receipts/review-sol-r15-placement.md). Primary bank/games remain blocked; no BASE or outcomes exist.

The broader R17 probe exited1 before deployment tests. Its145 native catalogue rows expose two static classification disagreements (Tornado and MergeMaiden); Cannon/river tap counts are both zero. [Failed receipt](receipts/placement-micro-r17-failed.json), [audit](receipts/placement-micro-r17-owner-audit.json). Generic schema precedence/variant-class reconciliation and the final raw-token manifest repair passed fresh R23 source review. This historical failed run supplies no physics evidence.

Current blocking update 2026-10-16T11:50:11.593285+00:00: full integration179PASS/12FAIL; timedWAIT fixture handling and changed Fireball support-cache baseline under source-only R24 repair plus bounded Astra cause audit. No cache restoration yet; fresh review→tests→native→clean four-caseall11 still required before primarybank. See PROGRESS R24 audit and job/gates-r24-repair-brief.md.

## V3 probe passed; integration repair pending

The R23-reviewed v3 probe passed **145/145 catalogue classifications and all1,024 commands**:64 Cannon controls plus960 card/seat/river/territory controls. It retained the original18 edge cases. Overall results were380 accepted controls,512 expected WATER refusals and132 expected territory refusals. All16 inward Cannon relocations fit their3×3 own-half box. [Binary receipt](receipts/placement-micro-r21.json), [count audit](receipts/placement-micro-r21-owner-audit.json). This supports the common simulator command adapter; native rollout geometry and LIVE placement rules are not claimed equivalent.

The subsequent five-file integration suite **failed:179passed/12failed**. Ten fixtures treated timed-WAIT2400 as a publicmask index(size2306). Two real B-root fairness fixtures failed closed on FireballL4 after the suite changed the supported-card whitelist. All six raw level exports remain unchanged. [Failure audit](receipts/integration-failure-r24-owner-audit.json), [original failed log](receipts/pytest-placement-r21.txt). The original whitelist bytes have been reconstructed exactly for review, but the cache has not yet been restored.

R24 source-only repair is complete: semantic WAIT checks, Runtime-first fixture construction and existing-only immutable caches including primary preload. The bounded Astra source audit established the cache/call-order defect. Fresh independent R25 review is active before restoration or execution. A fresh independent review, passing full integration, fresh native gates and clean complete-game all11 evidence remain required before any primary bank or games. No support/physics gate has been relaxed.

The bounded [Astra source audit](receipts/fireball-bootstrap-astra-r24.md) establishes an early global spell-registry initialization path: stale Fireball crown damage172HP versus normalized159HP atL11. Its existing L4 export remains357ordinary/83crownHP. It also identifies a separate support-manifest writer in the primary preload that must become read-only. The full failed-process config was not captured, so the complete reference-hash change is not claimed empirically to differ in only one field. No numerical tolerance or physics change is accepted.

## R26 repair validation

The cold isolated no-write regression passes9/9cases. Full clean-process integration passes**216/216** with no skips, exact121-card qualification, Fireball688/159 atL11 and357/83 atL4, and unchanged seven-file cache. [Audit](receipts/integration-r25-owner-audit.json). The original support bytes were restored exactly after independent review, with the failed manifest retained.

Fresh native gates pass**254/254** at the same reviewed source/cache:121exports,13towerchecks,32publicbodies,fouractualfairBdecisions and30eachcut/snapshot/raw-fc comparisons. All20rawsnapshot differences are only missing spell_name becoming empty strings; no numeric/entity/ordering/owner/position/key waiver. [Audit](receipts/gates-r25-owner-audit.json). The original four-case clean all11 run is in progress in a fresh output. No primary BASE/bank/outcomes exist.

## Clean complete-game all11 acceptance

The final same-bank DEV run passes**8/8 clean terminal rows and4/4 complete A/B command-hash pairs**. B actually built102,113,106 and67roots, with zero unmapped bodies. Both controllers and seats are covered, every recorded deployment is accepted, all child/parent exits are0, and completeness/provenance report quality isPASS. Seven cache hashes remain unchanged. [Owner audit](receipts/all11-r25-owner-audit.json), [report](receipts/all11-r25-report.txt). This closes the earlier Cannon rejection blocker and qualifies the frozen serial experiment for fresh registration; it is no mixed-level strength result.
