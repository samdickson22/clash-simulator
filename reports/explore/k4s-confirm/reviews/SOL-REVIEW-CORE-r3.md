# SOL independent core re-review r3

**Verdict: APPROVE_WITH_FIXES.** The core implementation remains acceptable in approach. Qualification is not yet acceptable as proof of the required runtimes and games: findings 14–16 are MAJOR evidence-validation gaps. Resolve them, the smoke validation gaps, and the final manifest/procedure issues before accepting qualification or freezing the runtime. This is not authorization to report.

Reviewed read-only in `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `201db04c99da5ae5277f7f15498d839c467cf0f1` plus working-tree bytes. Governing document: `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, SHA-256 `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`; implementation contract: `reports/explore/k4s-confirm/K4S-SPEC.md`. Read both prior core reviews and both author responses. Locations below are relative to `reports/explore/k4s-confirm/` unless stated otherwise.

No network, SSH, git commit/push, real game outcome data, or anything under `reports/explore/x4s2/receipts` was accessed. This review is the only file written. No manifest builder or qualification/game/STOP job was executed. Mac, END, independent-verifier and inherited OP implementations were not substantively reviewed. The requested read-only manifest verifier mechanically hashed their listed bytes; its out-of-scope failures are identified below without reviewing those implementations.

## Disposition of every r2 item

1. **RESOLVED — Guard timestamp projection.** `qualify.sh:22–24` checks the frozen SHA and compares regenerated/frozen objects after removing only `utc`; `make_qualification_receipt.py:11–12,37–38` uses that same projection and binds the fresh receipt at line 48. `QUALIFICATION.md` now describes the projection correctly. `qualify.sh` is byte-identical to the reviewed r2 version.

2. **PARTIAL — Qualification inventory/failure propagation and smoke validation.** `check_games.py:109–119,125–129,131–144,161–214` enforces all required game filenames, nonempty deadline evidence, no-deadline latency evidence, required cutoff/scored/overrun coverage and nonzero failure exit. A complete virtual fixture passed; changing every seed to 999 failed with exit 1. Identity validation is materially improved but has finding 14. Smoke value/nullability validation at `health.py:38–44` is incomplete, and zero decisions still qualify at the health layer; see finding 17.

3. **RESOLVED — Canonical descriptors and paired decks.** `schedule.py:52–68`, `run.py:357–360`, and `reduce.py:108–162` retain canonical validation before attempts and during reduction, ledger-derived replacement k/caps, unique logical ids/seeds and frozen paired-deck mapping. Schedule/reducer bytes match their recorded r2 SHAs. All eight authored schedule tests passed through direct in-memory calls; the actual canonical function accepted all 3,900 reporting and eight smoke descriptors. No real block/game inventory was loaded.

4. **PARTIAL — Full-runner injected equivalence.** The complete-runner virtual clock and command/decision comparisons remain implemented at `qualify_games.py:32–60,73–75,98–100,109–118`, `qualify_games.sh:27–30`, and `check_games.py:144–158`. The explicit one-thread override agrees with `expected_identity()` and runner affinity width. I retain r2's acceptance of this bounded deterministic harness. Source/evidence binding remains partial under item 9 and findings 15–16. No new rejection of the virtual-clock model is intended.

5. **RESOLVED — Rate inference, GC and WAIT indicators.** `reduce.py:173–202,242–263` retains paired per-game numerator/denominator bootstrapping for all five rates, separate RNG stream, full/subsample output, GC summaries and WAIT indicators. Reducer bytes are unchanged from r2. Resolution is source-level; numerical bootstrap results were not regenerated.

6. **RESOLVED — OP-6/OP-7 sensitivity contract.** `reduce.py:68–71,145–147,211–223` retains complete-proof SHAs, the compatible `(rows, rng, reps)` callback/`stratum_counts` alias, inherited final-inventory health ledger and source-proven SSH-or-apt exclusion, including subsamples. Reducer bytes are unchanged from r2. The inherited sidecar was not re-reviewed or run on real proof data.

7. **PARTIAL — Audit fields and their validation.** `run.py:271–280` records the scored K4 returned action and null on unscored paths; `310–316` records placement and sealed final tick/earned crowns/draw. Crowns are now correct (item 10). `check_games.py:85–90` checks slot/core/attempt values. The remaining arm/evidence association and smoke field validation weaknesses are findings 14 and 17. No outcome access was introduced in the checked projections.

8. **PARTIAL — Identity/configuration and placement checks.** `check_games.py:40–94` now checks seed/index, qualification population, matchup cell/seat, deck identities, deadlines, threads and runtime-specific kernels, with explicit zero-mode budget/scale and injected-thread overrides. All seven required indices map to the populations actually passed by `qualify_games.sh`; T1 does not get K4S-only missing-field requirements. Placement is compared with receipt cores and scheduling. The expected arm still comes from untrusted cohort content (finding 14), and receipts are not themselves validated against the required task specification (finding 15). Some projected fields, including `coarse_horizon`, reserve and pin identities, still receive presence checks rather than expected-value checks. Close those checks using the frozen plans/manifests and independently derived task expectations.

9. **PARTIAL — Source binding through game/STOP phases.** `run_qualification.sh:11,15` places the new snapshots before batteries and after games/STOP. `source_binding.py:28–62,87–95` compares recursive K4S/T1 inventories, permits only the T1 plan job-path rebinding and requires start/end equality. Independently reconstructed the expected T1 manifest with read-only `git ls-tree`/`git show`: all 92 entries exactly match `t1-reference-expected.json`; other reference declarations also match `reference-files.json`. `export_staging_extras.sh:11–20` and this expected manifest agree on exclusions/reference additions. However, driver receipt inventory/evidence coverage is not bound (finding 15), and assembly still trusts historical booleans (finding 16). The requested recheck during assembly is not implemented.

10. **RESOLVED — Earned crowns.** `run.py:312` uses `[b.get_crown_count(seat), b.get_crown_count(1-seat)]`, explicitly seat first. `src/clasher/battle.py:2588–2590` returns enemy towers lost. Executing only the actual method ASTs on synthetic tower HP with the search seat intact and one opponent tower destroyed produced earned crowns `[1,0]`. No real game or outcome was accessed.

11. **PARTIAL — Manifest completeness/final byte proof.** `rebind.py:76–79` adds inventory completeness; `build_delta_manifest.py:51–69` enumerates the same recursive file inventory. Ran only `python3 reports/explore/k4s-confirm/rebind.py verify` (with bytecode disabled). It exited 1: 143 files, classifications 61 identical / 14 rebound / 15 delta / 53 new, exactly two failures: stale hashes for `mac/K4S-MAC-MANIFEST.json` and `mac/test_measure_k4s.py`. All requested core/support entries are present and their current hashes match the manifest. Thus the core inventory fix is resolved, while the global final proof is still unclean due to separately reviewed Mac changes. Rebuild and verify after all review streams finish; the builder was not run here.

12. **RESOLVED — Qualification slot allocation.** `qualify_games.sh:20–30` now assigns eleven disjoint slots spanning exactly 0–54. `qualify_games.py:78–83` checks five contiguous, aligned cores within that range, observed affinity, SCHED_OTHER, nice 10/19 and an allowed host. These match current host-plan physical CPU lists. Injected runners correctly use the first core of their allocated five-core slot, and the checker permits this intentional override. `QUALIFICATION.md` now lists eleven slots, injected indices 5/7, excluded STOP index 6 and checkout-only verifier tests. Its freeze/launch wording has finding 18.

13. **RESOLVED — STOP and receipt success propagation.** `stop_test.py:29–48` requires a live child before writing STOP, a nonzero exit with the owned-STOP interruption, drainage and no remaining process group. Cleanup compares its token and preserves an externally replaced STOP. `make_qualification_receipt.py:40–41,57–59` requires interruption/running evidence and writes FAIL diagnostics then exits 1; the `set -e` driver cannot write `QUALIFICATION-FINISHED` after that failure. Actual STOP main was exercised with entirely virtual paths/processes: ordinary completion exited 1; owned interruption exited 0; external replacement was preserved. A live child may still be initializing at the pre-touch poll, but the required runner-specific interruption establishes that it reached the STOP-polling game loop; this is sufficient for the earlier objection.

## New findings

14. **MAJOR — Expected arm is derived from the evidence instead of the required filename.**

   **Location:** `check_games.py:79`, `check_games.py:115–118`; supporting no-deadline lookup/comparison at `135–142`.

   **Scenario:** Inventory checks filenames, but identity checks call `expected_identity(..., g['arm'])`, where `g['arm']` is the raw cohort. Nothing requires the cohort/metadata arm to equal the expected arm for that filename. Copy a valid K4S-200 no-deadline game over the required K4-200 filename, keeping its K4S cohort, kernel and configuration. It is validated as K4S, then its command hash is labeled as K4 in the equivalence table. Qualification can therefore claim K4 equivalence without collecting K4 evidence in that group.

   **Reproduction:** Executed the real checker main on a complete virtual inventory with no outcome fields. The baseline passed with exit 0. Replacing both K4S-runtime no-deadline K4-200 projections with copies of their K4S-200 projections, preserving the expected K4 filenames, still produced `passed=true`, no identity errors, exit 0. The fixture's commands were equal, as legitimate no-deadline equivalence expects.

   **Fix:** Pass each expected `(index, arm)` from the required inventory into validation, and require filename, cohort and metadata arm to agree with it before deriving any settings. Validate all projected configuration values against that independent expected spec. Add duplicate/renamed-arm fixtures that fail while genuine T1/K4S schema differences remain accepted.

15. **MAJOR — Eleven receipts do not establish the required driver inventory or cover the checked games.**

   **Location:** `source_binding.py:65–75,88–92`; `check_games.py:112–118`.

   **Scenario:** The source verifier only counts receipt files, checks their run/plan hashes and checks hashes for whatever games they elect to list. It does not require the eleven particular group/runtime/mode/population/index/arm jobs, nonempty game lists, or exact coverage of the games consumed by the checker. The checker independently reads only receipt index/cores, ignoring these identities and game hashes. Consequently, validly named game files may pass the checker while all receipts omit them; the accepted source binding never binds those checked files to driver evidence.

   **Reproduction:** The actual `verify_receipts()` returned `(11, [])` for eleven synthetic receipts in one group, each with matching K4S run/plan hashes and `games=[]`. With unchanged snapshots and a valid T1 manifest, line 91's acceptance predicate has no further inventory objection. This is a validation hole; it does not claim that the current launcher normally emits empty receipts.

   **Fix:** Define one canonical expected task inventory shared by launcher/checker/binder. Require exactly one receipt for every expected task; validate runtime/mode/index/seed/population/cell/arms, valid slot and receipt filename/group; require its exact nonempty game list and cross-check every checked game's hash against that list. Reject duplicate indices/tasks, empty lists, omitted games and extras. Bind the receipt identities/hashes in the final qualification evidence.

16. **MAJOR — Receipt assembly still accepts a historical source-binding boolean.**

   **Location:** `make_qualification_receipt.py:42–43,52–55`; ordering at `run_qualification.sh:15–16`.

   **Scenario:** The final source verification is a separate process. Assembly reads its `passed` boolean and hashes the saved binding artifacts, but does not recompute the current snapshot, revalidate driver/game coverage, compare the end artifact's `start_sha256` with the current start file, or bind the current battery/check/STOP artifacts to the verified evidence. Editing a staged runner/support/plan file or replacing checked evidence between final verification and assembly is accepted. For a changed plan, line 55 even records the new plan SHA alongside the old passing source evidence. This is the outstanding explicit r2 requirement to recheck during assembly.

   **Reproduction:** Ran the real assembler main with virtual artifact/path helpers: all checks passed, a historical end binding named `old-run`, and the synthetic current run/start hashes differed. Assembly produced `verdict=PASS`, exit 0. No current source snapshot or receipt verification was requested. This probes the assembler's acceptance logic, not real qualification artifacts.

   **Fix:** Before deciding PASS, recompute and compare current source/input identity with both verified snapshots, check the saved start link, revalidate receipt/game coverage and bind hashes of every consumed battery/check/STOP artifact. Use a reusable read-only verification function so assembly checks current evidence directly rather than trusting a previous process's boolean. Write FAIL diagnostics and exit nonzero on any mismatch.

17. **MINOR — Smoke admission still accepts missing SD1 values and empty decision evidence.**

   **Location:** `health.py:33–44`; smoke admission uses the result at `smoke_pass.py:16`.

   **Scenario:** For SD1, line 41 only requires a nonnull P(play); it does not require the recorded SD1 default action or the coarse-order hash on a scored path. Other audit relationships, such as chosen_action/action, fallback_used/fallback, extra-tick/overrun aliases and scan nullability, are presence-only. Also, `stats=[]` and `latency_seconds=[]` satisfy the length check and skip all decision/charge checks. Nothing at final smoke admission requires a decision or charged-path summary. This can admit structurally complete smoke games that did not exercise the promised search/charge audit paths.

   **Reproduction:** Actual `health(..., validate=True)` returned `passed=true` for a virtual scored K4S-200 decision with `sd1_p_play=.9` but both `sd1_default_action=None` and `coarse_order_sha256=None`. It also passed the same virtual game with both decision/latency lists empty. No outcome values were supplied or accessed; terminal was only a health flag.

   **Fix:** Require nonempty appropriate smoke decision evidence and required per-arm/path coverage. Validate SD1 default/P(play) and coarse-order nullability according to the runner's belief/scored/single-candidate paths, scan nullability on preparation cutoffs, and the specified aliases/value relationships. Keep these projections outcome-blind. Add malformed-field and empty-decision fixtures.

18. **MINOR — Procedure permits qualification after the freeze.**

   **Location:** `QUALIFICATION.md:3–4`.

   **Scenario:** The procedure says hosts 01/04/08 are qualified at launch and frames the requirement as before admission. Governing r3 §4.1 requires qualification on every named host before the freeze; §7 places qualification at step 5 and freeze at step 6. The document can therefore direct a nonconforming sequence if launch follows freeze. No coordinator amendment changing this order was provided in this review's inputs.

   **Fix:** State that every host named in the freeze needs accepted qualification before that freeze. Describe any launch-time repeat separately as a recheck. If the intended process defers qualification, obtain and cite the coordinator's explicit amendment rather than silently changing the preregistered sequence.

## Seal, compatibility and verification limits

- Scoped checker/health/qualification source accesses no loss, winner, crowns, draw or final-tick outcome fields. Health and driver retain the existing terminal health check; command hashes are used only for preregistered qualification equivalence. The runner records outcomes in sealed game output. An actual `check_games.project()` probe with guarded mappings raised on any forbidden outcome access and completed without such access. Source binding hashes opaque game bytes without interpreting outcome fields.
- A complete virtual checker fixture covered T1 versus K4S schema differences, primary indices 0/2/4/5 and guard indices 1/3/7, sorted deck identities, all four modes, injected thread/affinity override and zero-mode budget/scale override. It passed; wrong seeds failed. The normal launcher records `attempt_dir=str(a.out)` and passes the same Path-normalized group directory to checking. No false failure was found for this documented path convention. Arbitrary relocation/alternate relative CLI spellings were not claimed to be supported.
- The T1 expected source inventory exactly matches independent git derivation. The global delta verifier found no missing/extra entries and no stale scoped core hashes; only the two out-of-scope Mac hashes above prevented a clean result. `build_delta_manifest.py` was inspected, never executed.
- Eight schedule and four charge tests passed through direct calls, with a small in-memory `pytest.raises` substitute for unavailable pytest. Thirteen scoped Python files parsed by AST; four qualification/export shells passed `bash -n`. The synthetic crown, checker, source-receipt, assembler, smoke and STOP probes used actual functions with virtual I/O and no real game files. These are focused acceptance/control-flow tests, not substitutes for staged-runtime qualification.
- Full native games, actual STOP drainage, numerical NumPy bootstraps, host affinity/topology and live qualification were not executed. Previously resolved reducer/schedule items were re-inspected and their r2 source hashes matched; no new real-outcome analysis was performed. Mac/END/verifier and inherited OP implementation reviews remain separate.

## Reviewed source identities

SHA-256 of the principal scoped bytes at review time:

```text
run.py                       78d88a572a8637956492d0f8447569c2307454818bb03356007b9ff9938a5f13
schedule.py                  b95ad6757baa1623f8af3cd6d65ac47c0a85460fd1ea231122313abf4728d131
reduce.py                    a0ac06b98ba37533d23983207a5125e30c1025e71867a5f60bf21ec4bf92a686
health.py                    a173e0b2dba5b7cc0b0f8759993aa09b5a2468cd58a7316ffae45e0dcbeeb26f
check_games.py               3e5bcf0c845f6811f68e7d65fc92f3f5f44cca42a232356202ce111effd3cb61
qualify_games.py             13b18a7bde9917dbb1300f6041cbb02542cb9c4543f6d11db837d9be971ece2b
source_binding.py            67ed6a037e62406f90690e30aac51d53c40fb24182271cdd85f64614e3ce0a7a
t1-reference-expected.json   d664d570abeace863fc1c5e3b836149022d237b025226d2946498bf2c98914fd
make_qualification_receipt.py 5bc8247f496601d5ccca22587da3d3ecc4ee66b850399a8516de07dc5bfdbbb8
stop_test.py                 ef0ab1a18918592372f4160d1bc10ae717004fdc8b9f8170e3f79243f3ce0f23
run_qualification.sh         1d788704af244574ac0acd15f1492baaa9a2e1f3edda05c83b5e3f898df1ea65
qualify_games.sh             3fa3961677db602be35588b161dbd7572ef674d369f48c0f1203503af956d7c2
rebind.py                    4857b6db0851ce1c04574181a967e1a0732d9a43a8fc76fc759a76ddf0df17f5
DELTA-MANIFEST.json          c200fa88a507249224a16d6b7a574593dd208bf0f63e7d709371ed5f11f41717
QUALIFICATION.md            a9afae5c234561b0bbc82e69784ba0c209a7f3ae3897412cd44f7c7ceeb68578
```
