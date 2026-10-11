# SOL independent core re-review r4

**Verdict: APPROVE_WITH_FIXES.** The requested reducer changes are correct on the inspected and synthetic paths, and the delta manifest now verifies cleanly. Most qualification fixes are complete. Finding 16 remains partial: assembly rechecks source trees and game coverage but does not recheck the qualified native/model inputs or enforce the earlier battery-artifact hashes. Finding 19 below is MAJOR and must be fixed before accepting qualification or freezing the runtime. Finding 20 completes the remaining decision-audit validation. This verdict does not authorize reporting.

Reviewed `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `201db04c99da5ae5277f7f15498d839c467cf0f1` plus working-tree bytes. Governing document: `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, SHA-256 `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. Contract: `reports/explore/k4s-confirm/K4S-SPEC.md`, SHA-256 `e80652d4859504eaf6a9256a3b3672a247a3f1993160ab17378587e7cdd93e53`. Read all three prior core reviews/responses and the independent verifier r1 review. Locations below are relative to `reports/explore/k4s-confirm/`.

No SSH, network, git commit/push, real game outcome data, or anything under `reports/explore/x4s2/receipts` was accessed. No worktree file was written. This review is the only filesystem artifact authored; test writes were intercepted into in-memory dictionaries. Mac, END, verifier implementation and inherited OP modules were not substantively reviewed or executed. The expressly requested manifest verifier mechanically hashed its listed out-of-scope bytes. No manifest builder or live qualification/STOP/game job was run.

## Disposition of the requested core findings

| Finding | Status | Evidence and remaining work |
|---|---|---|
| 2 — Inventory/failure propagation and smoke validation | **PARTIAL** | Exact required game inventories, nonempty appropriate evidence, charge/path coverage and nonzero checker failure are retained (`check_games.py:120–230`). Smoke now rejects empty decisions and validates SD1/scan/alias fields (`health.py:15–24,47–63`). A complete virtual qualification passed; wrong seeds, pins and cohorts failed. Charged qualification still accepts the malformed decision values in finding 20. |
| 4 — Complete-runner injected equivalence | **PARTIAL** | The previously accepted deterministic full-runner model is retained; four-worker fixed-state qualification remains separate. The canonical receipts now bind both runtimes' games and source hashes (`qual_tasks.py:44–68`, `source_binding.py:65–78`). The remaining exact-runtime/evidence limitation is finding 19; this is not an objection to the bounded virtual clock or its one-thread override. |
| 7 — Audit fields and validation | **PARTIAL** | Runner bytes are unchanged from r3: scored K4 frozen action, slot/core/attempt metadata and corrected seat-first earned crowns are retained. Expected arm/metadata association and canonical placement are now checked (`check_games.py:87–104,123–128`); smoke aliases and nullability are checked. Charged qualification does not enforce those same aliases/scan values; see finding 20. |
| 8 — Identity/configuration and placement | **PARTIAL** | Independent required arm, seed/index/population/cell/seat/decks, deadline/kernel/threads, reserve/coarse horizon, SD1/opponent/native declarations and placement are now value-checked (`check_games.py:60–104`). Injected and zero overrides are correct. `runtime_pin_sha256` remains a presence-only field, and declaration equality does not revalidate current native/model bytes; see finding 19. |
| 9 — Source binding through games/STOP and assembly | **PARTIAL** | Recursive K4S/T1 snapshots bracket the batteries, games and STOP. Assembly now recomputes them, checks both snapshots and the start link, and revalidates canonical receipt/game coverage (`make_qualification_receipt.py:45–54`). `t1-reference-expected.json` retains the r3 independently checked SHA `d664d570…`. Native/model inputs and earlier artifact hash links remain outside this final recheck; see finding 19. |
| 11 — Manifest completeness/final byte proof | **RESOLVED** | Requested `PYTHONDONTWRITEBYTECODE=1 python3 reports/explore/k4s-confirm/rebind.py verify` exited 0: inventory 152; 61 identical / 14 rebound / 15 delta / 62 new; failures `[]`. New helpers/tests are covered. Builder not run. |
| 14 — Evidence-derived expected arm | **RESOLVED** | Required filename arm is passed to `identity_errors`; cohort must agree before settings are derived, and metadata arm is checked independently (`check_games.py:87–93,128`). A mismatched cohort with an updated, valid receipt hash failed with exit 1. |
| 15 — Driver inventory and game coverage | **RESOLVED** | Canonical eleven-task inventory is shared by checker and binder; the launcher is checked against it. Receipt filenames, identities, seed, arms and canonical cores are required, as are exact nonempty game lists and matching hashes (`qual_tasks.py:10–21,44–68`). Checker placement uses canonical cores. Eleven valid synthetic receipts bound 32 games; empty lists, wrong index/cores/hash, extra games, missing receipts and extra receipts were rejected. Runtime identity checking also passed/rejected as expected. |
| 16 — Historical source-binding boolean at assembly | **PARTIAL** | The original changed-source/start-link/game-coverage examples now fail and write FAIL receipts with exit 1. Current source recomputation is implemented. However, the immutable-input identity in `qualification-source-binding.json` is still accepted through its old boolean, and its battery receipt hashes are not compared to current artifacts. Recording newly consumed hashes does not check the old links. See finding 19. |
| 17 — Smoke missing SD1 values/empty decisions | **RESOLVED** | `health.py:15–24,47–63` requires decisions, scored coverage per arm seen, SD1 default/P(play), correct coarse-order and scan nullability, and action/fallback/lateness aliases. All three authored health tests passed with filesystem writes intercepted. Valid belief, prescan, sample and single-candidate paths also passed when accompanied by a scored decision. |
| 18 — Qualification after freeze | **RESOLVED** | `QUALIFICATION.md:3–6` requires accepted qualification for every named host before the freeze and distinguishes a later launch recheck. `run_qualification.sh:11–17` retains the required order and failure propagation. The document's historical host-qualification assertion was not independently validated using real game evidence. |

Prior resolved items 1, 3, 5, 6, 10, 12 and 13 are not reopened. The unchanged runner/schedule identities match r3. Guard timestamp projection and STOP/FAIL requirements remain present. Inherited OP implementations were not re-reviewed.

## Reducer changes after the verifier review

- **Fixed H-labels — RESOLVED.** `reduce.py:89–99` preserves H1/H2/H3/H5/H6/H7 at c*=0.8. Authored label/margin/stop tests pass. Additional actual-function probes checked every possible first-failure position: seven at 0.9 and six at 0.8, including `tested=false, passed=null` afterward. `verifier_view()` preserves those labels.
- **Verifier finding 3, chronological active-chain replay/final survivor — RESOLVED.** `reduce.py:109–126,139–144` requires the active physical loss, derives per-cell allocation k in event order, enforces caps and requires the counted final survivor. Valid interleaved chains for different logical originals in the same cell pass. Future losses, duplicate/inactive original losses and disconnected replacements fail. Three replacements were accepted in the full-size synthetic inventory.
- **Verifier finding 4, required winner key — RESOLVED.** `reduce.py:161–163` rejects a missing winner key before classification. A hash-consistent synthetic missing-winner record was rejected; explicit null with loss zero was accepted as a draw.
- **Verifier finding 5, frozen paired decks — RESOLVED / RETAINED.** Canonical descriptors independently derive deck indices; `reduce.py:148–160` checks every arm's sorted decks against the population-cell mapping. The deck checks predate the latest reducer edit and remain correct. A hash-consistent wrong-deck synthetic record failed. Shuffled legitimate deck arrays are handled by sorting.
- **Verifier finding 6, c* agreement — RESOLVED.** `reduce.py:161` requires every game's c_star to equal plan.json before analysis. Hash-consistent missing and mismatched c_star records were rejected. The decision function permits exactly 0.9/0.8.

The allowed `receipts/reducer-verifier-crosscheck.json` now binds the current reducer SHA `9c2e5ac0…` and the manifest-verified verifier SHA `47e59142…` in all three scenarios. Each reports 169/169 matches: admit-all, stop-at-H2 and suspended. This closes r3's stale-reducer receipt limitation. Its recorded scenarios all use the seven-label sequence; it is not evidence of an independent c*=0.8 cross-check. The separate reducer label/stop probes above cover that branch. No verifier implementation was read to conduct this review.

No false rejection was found for the legitimate evidence exercised: T1 schema differences, injected thread/affinity override, zero-mode budget/scale override, shuffled decks, explicit-null draws, canonical replacements, and belief/prescan/sample/single-candidate smoke decision paths.

## New findings

19. **MAJOR — Final assembly does not revalidate the qualified native/model inputs or enforce earlier battery-artifact hash links.**

   **Location:** `make_qualification_receipt.py:42,48–58,64–69`; `source_binding.py:50–62`; supporting earlier proof `qualification_binding.py:6–17`.

   **Scenario:** The newly recomputed snapshot covers only `repo/reports/explore/k4s-confirm`, `repo/reports/explore/t1` and declared reference files. Native code and model inputs are outside it. The earlier qualification binding records `native/clasher_core.abi3.so`, `inputs/R3a.pt`, `inputs/R3a-calibration.json` and `inputs/main02.pt`, but assembly reads only its historical `source_stable` boolean and does not recompute that inventory. Changing any of those bytes after verification still yields PASS. Hashing runtime-pin.json/staging.json does not verify their declared inputs against current bytes. Games' runtime_pin_sha256 is likewise not compared with the current pin.

   The earlier binding also contains the accepted SHA of qualification.json, belief-qualification.json and guard-support-qualification.json. Assembly never compares those links with current files. It records a new consumed_artifact_sha256 map, which binds what assembly saw but cannot establish equality with what the prior verifier accepted. The final source-binding artifact does not bind the remaining battery/check/STOP artifacts either.

   **Reproduction:** Executed the real assembler, real `source_binding.snapshot()`/`verify_receipts()` and real `qualification_binding.inventory()` on an entirely virtual fixture, with all reads/writes to that fixture intercepted in memory. The fixture included canonical eleven-task/32-game receipts and an earlier input/battery binding. Baseline: PASS, exit 0. Independently changing native, SD1 checkpoint, calibration or opponent checkpoint bytes after the end snapshot: each still PASS, exit 0, no failed checks. Replacing belief-qualification.json while retaining its required 125/125/125 counts but violating the earlier receipt SHA also passed. Controls changing run.py, a receipt-bound game, or the end-to-start SHA link produced FAIL and exit 1. The fixture models the actual acceptance logic; it is not a claim about the real hosts' files or qualification results.

   **Fix:** Extend the before/after and assembly verification to the immutable native/model inputs (and any runtime-pin-declared source/input scope needed for the qualified runtime). Recompute the current qualification-binding inventory and compare its exact identities with the earlier proof and plan pins. Compare every game's runtime_pin_sha256 with the qualification job's pin. Check the existing battery-artifact hash links, and bind the full consumed battery/check/STOP artifact inventory in the final verification receipt so assembly can enforce it. Preserve the diagnostic FAIL/nonzero behavior. Add mutation regressions for each input and for hash-inconsistent battery/check/STOP replacements.

   This is the remaining portion of finding 16 and the exact-runtime limitation in items 4/8/9, not a reopening of the now-correct K4S/T1 code-tree recheck.

20. **MINOR — Charged qualification accepts inconsistent action aliases and missing scored scan values.**

   **Location:** `check_games.py:179–198`; the corresponding implemented smoke rules are at `health.py:15–24`.

   **Scenario:** Charged qualification requires FIELDS to exist, checks frozen_action and SD1 coarse-order/default relationships, then checks lateness/charge. It never checks chosen_action == action, fallback_used == fallback, charged_extra_ticks == delayed_ticks, positive_overrun_ms == 1000*overrun_seconds, or the scan fields' scored/unscored nullability. A scored row can have plays=null and chosen_action=999 while its actual action is 7, and still qualify. Smoke subsequently applies stricter rules, but the per-host qualification receipt can already claim that malformed audit evidence passed.

   **Reproduction:** A complete 32-game outcome-free virtual checker inventory passed with exit 0, including legitimate runtime/mode overrides. Changing a scored K4S-200 charged decision to chosen_action=999 and plays=null, then updating its canonical driver receipt hash, still produced passed=true and exit 0. The actual smoke validator rejects these field changes. Wrong seed/native declaration/cohort and null SD1 default controls were rejected by the checker.

   **Fix:** Apply one reusable outcome-blind decision validator to charged qualification and smoke, with explicit exceptions for T1, no-deadline, injected and zero qualification modes. Require the specified aliases and scan nullability. Preserve null scan/frozen fields for valid unscored single-candidate and preparation-cutoff paths. Add charged-checker controls demonstrating rejection of each malformed relationship and acceptance of the valid paths.

## Verification and limits

- Native pytest, with bytecode/cache output disabled, ran `test_qual_tasks.py` and the seven reducer tests that do not require filesystem fixtures: **8 passed, 3 deselected**. Command: `/mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/test_qual_tasks.py reports/explore/k4s-confirm/test_reduce.py -k 'not end_to_end and not seal_refuses and not tampered'` (with PYTHONDONTWRITEBYTECODE=1).
- The three deselected pytest cases would create synthetic filesystem trees. Instead, the actual synthetic producer and reducer loader ran with all synthetic writes intercepted in memory: **3000 primary / 900 guard blocks, 33000 games and three replacements accepted**. The actual four-analysis bootstrap ran at **10000 resamples**, followed by both c* decision/view branches. No OP sensitivity code or real outcome input was used. This exercises loading, primary computation and decisions; it is not a claim that the complete CLI secondary-output pipeline was rerun.
- Three authored health tests ran directly with in-memory Path I/O, along with four valid-path controls. Canonical receipt validation had seven rejection controls. Actual complete checker main and assembler main ran with virtual evidence and no real game files. The assembler tests recomputed its source/receipt checks; they did not stub those checks to true.
- A denied-release probe of actual reducer main confirmed no block/game loader call. Scoped checker/health/qualification projections were inspected for seal compliance and use outcome-free synthetic records. The runner continues to record outcomes only in sealed output.
- Scoped Python sources parsed; qualify.sh, qualify_games.sh and run_qualification.sh passed bash -n. Manifest verification exited 0. The expected T1 manifest is byte-identical to the independently derived r3 version.
- Real qualification games, host topology/affinity, live STOP drainage and the three filesystem-based pytest cases were not run. No real host qualification receipt was substituted for independent tests. Mac/END/verifier/OP reviews remain separate.

## Principal reviewed source identities

```text
run.py                         78d88a572a8637956492d0f8447569c2307454818bb03356007b9ff9938a5f13
schedule.py                    b95ad6757baa1623f8af3cd6d65ac47c0a85460fd1ea231122313abf4728d131
reduce.py                      9c2e5ac00aac65827daa7596c93b5f7993d748976e405202d09e1e1bc24706c8
test_reduce.py                 70bd6257ab09c54ef58c4a1a2cd9cebdb383ee4699d0be836cc4aa721d9d6775
check_games.py                 22ff2a9567b5ab95f81c5e54e74419f0e6855f1d75c5aa36b7b96c1a44aed7f3
qual_tasks.py                  cc81b3172fc41f0fe1835e0cb9038ee96720998bde65a2836b4caba15657133e
test_qual_tasks.py             6ee1a0b2e911ec1a8f5a31870a4e39c6dfa8fd391dc5adcc69fc0a36ff7cbc16
source_binding.py              aecc104cf445f41218bdd141235f4fc61b6b876f4ce7865a3b39c70ed0595da6
make_qualification_receipt.py  52e24b0932edb0c2259863c00875122a5f291b8f040b07f0ed7f06311718d701
health.py                      5bbe9beb4db6f40e9aab64fd2cf07aa57419e04ddfcbb2dccf4bb6351b51b697
test_health.py                 ff4f2e9b53106eaa25a783442c81390bfeae23debc00340ae132b5872e218913
QUALIFICATION.md               795a4ad74e745459734e9fecbdb4b07a244722342a0925fcb774b9dfa037167f
qualify.sh                     9e9b979d517c9cb0eac3a324b57e977a6457b4fd6189b5bf850a32690872605d
run_qualification.sh           1d788704af244574ac0acd15f1492baaa9a2e1f3edda05c83b5e3f898df1ea65
rebind.py                      4857b6db0851ce1c04574181a967e1a0732d9a43a8fc76fc759a76ddf0df17f5
DELTA-MANIFEST.json             255fcd9ffb8b66933ef1e553eda91c28e3e4232461a78cbbe8b2924fb6df2fad
```
