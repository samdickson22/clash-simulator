# SOL independent core re-review r2

**Verdict: APPROVE_WITH_FIXES.** The core runner/reducer approach remains acceptable. Findings 8 and 9 are MAJOR qualification-evidence gaps and must be fixed before qualification is accepted or this runtime is frozen. Resolve the smaller regressions below and regenerate the manifest before admission. This verdict does not authorize reporting.

Reviewed read-only in `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `38c195b86b636dd0f05e7f85345ac8720ba62985` plus the working tree. The tree was being edited concurrently; source identities below identify the scoped bytes at the end of this review. Governing preregistration: PREREG-K4S r3, SHA-256 `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`; contract: `K4S-SPEC.md`. Locations are relative to `reports/explore/k4s-confirm/` unless stated otherwise.

No network, SSH, git commit/push, real game outcome data, or anything under `reports/explore/x4s2/receipts` was accessed. No implementation files were changed. This report is the only file written by the reviewer. Mac code, END implementations and the verifier were not independently reviewed here. The inherited OP modules were checked mechanically for identical/rebound provenance, not substantively re-reviewed.

## Round-1 findings

1. **RESOLVED — Guard timestamp comparison.** `qualify.sh:22–24` preserves the exact frozen guard SHA and compares the full regenerated object after removing only `utc` from each object. `make_qualification_receipt.py:11–12,37–38,46` uses the same projection and binds the fresh receipt separately. An in-memory changed-timestamp projection passed without changing the frozen object. `QUALIFICATION.md:24` still calls regeneration “byte-identical”; correct that wording when updating the procedure.

2. **PARTIAL — Qualification inventory, failures and smoke charge checks.** `check_games.py:54–67,69–146` now requires the named filenames in every no-deadline, injected, charged and zero group, rejects missing groups, requires nonempty charged/zero/injected decisions and cutoff/scored/overrun coverage, and exits nonzero after writing diagnostics (`147–150`). An empty virtual inventory produced `passed=false`, exit 1. `health.py:38–46` adds per-decision charge checks, including zero sleep at c=1, and per-path summaries for smoke. However, qualification only checks metadata presence, not its identity/configuration values; an entirely invalid metadata fixture still passed. See finding 8. Smoke fields are mostly checked for presence rather than the requested value/nullability consistency.

3. **RESOLVED — Canonical descriptors and paired decks.** `schedule.py:55–72` independently derives original/replacement id, index, seed, cell, seat, deck indices, rotation, subsample and order, permitting only host/dispatch additions. `run.py:356–359` invokes it before creating an attempt. `reduce.py:108–162` rederives ledger k/caps, checks counted replacements against canonical ledger entries, rejects duplicate seeds, checks game identities and compares every arm's shuffled decks with the frozen mapping. The primary-0050 rotation and primary-0000 index/seed examples are rejected. All 3,900 reporting originals, eight smoke descriptors and 88 additional chained replacements were accepted by the actual canonical function. Valid smoke and chained replacement descriptors were not falsely rejected. The authored canonical/schedule and ledger tests passed in the local in-memory checks.

4. **PARTIAL — Full-runner injected-clock equivalence.** The missing full-runner test is now implemented correctly in principle: `qualify_games.py:32–60,73–75,95–97,104–115`, `qualify_games.sh:27–30`, and `check_games.py:81–96` run both complete deadline-enabled K4-200 paths on qualification indices 5 and 7 and compare command hashes plus inherited decision selection/timing fields, with required preparation-cutoff, scored-cutoff and overrun coverage. I accept the virtual-clock design for r3 §4.1; see the detailed judgment below. The remaining qualification source-binding gap is finding 9: the accepted receipt does not establish that the complete evidence was collected with the same delta bytes and frozen T1 reference bytes. This is an evidence-binding limitation, not rejection of the virtual clock or its single-thread collector.

5. **RESOLVED — Rate inference, GC and WAIT indicators.** `reduce.py:173–202,242–263` now forms per-game numerators/denominators, resamples them together with shared paired draws within each cell, and emits rate CIs for the five specified rates in full/subsample analyses on the disclosed independent stream `2026101173`. GC records are retained at `156` and summarized; WAIT shares, longest runs and cutoff-WAIT shares are reported. The primary analyses remain at `166–170,305–306` with their original RNG/order. This resolution is based on code inspection; the numerical bootstrap was not rerun without NumPy.

6. **RESOLVED — OP-6/OP-7 sensitivity contract.** `reduce.py:145–147` retains `complete_sha256`; `211–223` builds the inherited final-inventory health ledger and calls `analyze_union` with `population_stats`. The latter's `(rows, rng, reps)` signature and `stratum_counts` alias match the inherited callback contract (`68–71`). Full and subsample contrasts are included on disclosed separate streams; unrelated interference is counted separately. An in-memory K4S-shaped row fixture, including all ten arm keys and complete-proof SHAs, passed the actual inherited `analyze_union` and actual adapter; an unrelated `interfered=true` flag did not exclude it. Only the numerical analysis callback was stubbed because NumPy is unavailable. No claim is made to have replayed real OP meter proofs.

7. **PARTIAL — Audit fields.** `run.py:271–280` now records plain scored K4's returned action as `frozen_action`, with null on unscored paths. `310–312` adds slot/core mask/attempt directory and sealed final tick, crowns and draw. These additions do not introduce a seal leak in the scoped health/check/qualification projections. However, the crowns have the opposite semantics to the declared player order (finding 10), and `check_games.py` only checks placement/configuration key presence (finding 8). It does not validate slot, cores or attempt-directory values.

## Injected-harness judgment

The virtual clock is installed **before importing `run`**. This matters because belief and collector modules bind `time.monotonic` in default arguments. Work advances time only after actual V1 policy polls and native rollout events; additional instrumentation clock reads do not change simulated elapsed time. `_Native.rollout_e1` enforces the supplied remaining budget in virtual time: a too-expensive rollout consumes the nonnegative remaining budget and raises `TimeoutError` without calling native; a successful rollout calls the real native routine with a large budget and then advances by its fixed cost. The collector's own post-call `clock() >= cutoff` check still rejects a rollout finishing exactly at the cutoff. An independent fake-native probe confirmed full and partial budget behavior without opening any game data.

The one-thread collector is a reasonable deterministic injected-clock qualification choice. It removes real future-completion ordering from the simulated timing test. Separately, `qualify_k4s.py:89–113` compares the four-worker T1 and delta collectors to the same 125 frozen states without deadlines, including actions/candidates/scores, and compares their deterministic injected single-thread decisions. I do not require a nondeterministic four-worker whole-game hash test to accept this design.

This is a **bounded equivalence test**, not a complete timing model: observation, belief work, candidate generation, sampling and root creation have zero simulated duration. The high poll costs exercise belief entry cutoffs; they do not exercise suspension partway through belief or preparation cutoffs newly crossed during prescan/sample. The inherited belief battery provides additional coverage, but the new whole-game harness should not be described as exercising every preparation boundary or directly proving RNG-state identity. The r3 requirement to compare command hashes and injected-clock decisions is served by this harness when its exact runtimes, identities and evidence are bound as requested in findings 8–9. I did not execute real qualification games or inspect their outcomes.

## New findings

8. **MAJOR — Correct filenames can qualify wrong seeds, populations and runtime settings.**

   **Location:** `check_games.py:30–45,54–57,69–96,99–107,138–146`.

   **Scenario:** The exact inventory is enforced only on filenames. No-deadline/injected groups do not validate metadata identities. Charged/zero groups check `missing_meta`, but never compare seed, index, population, cell, seat, threads, kernel, budget/scale/default settings or placement against the required group/arm. `META` also omits `deadline_seconds`, so renaming no-deadline evidence is not explicitly rejected as charged evidence. The checker trusts the projected cohort and speed cell instead of deriving them from the expected arm.

   **Reproduction:** Ran the real checker main on in-memory projections for every required group, with proper filenames and otherwise coherent charge/default/equivalence stats. Every game carried `seed=999`, `seed_index=999`, `population='WRONG'`, `cell=999`, `seat=999`, `threads=999`, `slot=-9`, `slot_cores=[]`, `attempt_dir=None`. It wrote `passed=true`, no errors, and exited 0. No files or game outcomes were involved.

   **Fix:** Validate an explicit outcome-free identity/config projection against each group's index/population/runtime/mode/arm specification. Include deadline and deck identities; account explicitly for the one-thread injected override and zero-mode budget/scale overrides. Validate placement values and consistency with recorded host/affinity/nice and the driver receipts. Require nonempty appropriate decision records in no-deadline evidence through an available health projection, not `deadline_stats` (legitimately empty when deadlines are disabled). Extend smoke checks to the relevant value/nullability relationships, not just key presence. Add malformed-identity/configuration fixtures that fail.

9. **MAJOR — Source-stability proof ends before games and never binds the frozen T1 reference.**

   **Location:** `qualify.sh:13,30`; `run_qualification.sh:11–14`; supporting `qualification_binding.py:6–17`, `qualify_games.py:118–120`, `make_qualification_receipt.py:41,49–52`.

   **Scenario:** The source binding is recorded/verified around the batteries, then the new whole-game and STOP phases execute afterwards. Editing a delta source between those phases or before receipt assembly leaves the old `source_stable=true` accepted. The inventory includes only top-level K4S Python/shell files and its plan, not the staged T1 runtime. The driver writes `run_py_sha256` and `plan_sha256` receipts, but the checker/assembler do not verify or bind those receipts. Changing a T1 collector/support module after export can leave qualification labeled “ef4c073a” without any accepted source proof of that identity.

   `export_staging_extras.sh:11–13` correctly exports the frozen commit and limits the T1 plan change to the job-path rebinding. That construction is useful but does not close the later evidence-binding gap; the runtime pin's added overlay inventory likewise does not enumerate the exported T1 tree.

   **Fix:** Export an expected T1 source manifest derived from ef4c073a, explicitly describing/checking the allowed plan path substitution. Verify the staged reference and delta sources before the first battery and after all game/STOP phases. Bind/check each driver receipt, its exact inventory and game hashes, against those manifests and the final qualification receipt. Recheck the completed source binding during assembly; do not accept a historical boolean alone.

10. **MINOR — New `crowns` records towers lost, reversing earned crowns.**

   **Location:** `run.py:312`; supporting frozen T1 source `src/clasher/player.py:121–138`, `src/clasher/battle.py:2588–2590`.

   **Scenario:** `PlayerState.get_crown_count()` is explicitly a legacy alias for **that player's towers lost**. Earned crowns require `BattleState.get_crown_count(player_id)`, which consults the enemy's destroyed towers. With the search seat intact and one opponent tower destroyed, the new `[seat, opponent]` field is `[0,1]` rather than earned crowns `[1,0]`. This was reproduced from the actual method AST with synthetic tower HP, without running or opening a game.

   **Fix:** Record `[b.get_crown_count(seat), b.get_crown_count(1-seat)]`; document seat-first ordering. Test asymmetric synthetic terminal tower states. Keep these checks in synthetic/unit or post-release paths: do not add outcome reads to smoke/health/qualification.

11. **MINOR — Current delta manifest does not prove the reviewed bytes or inventory.**

   **Location:** `DELTA-MANIFEST.json` (`files`); `rebind.py:47–74`.

   **Scenario:** The read-only `rebind.py verify` returned nonzero with 21 stale SHA entries at the time of the probe, including run/schedule/reduce/health/check/qualification and their tests. Seven top-level executed/support sources were entirely absent: `export_staging_extras.sh`, `make_freeze_skeleton.py`, `make_qualification_receipt.py`, `qualify_games.sh`, `run_qualification.sh`, `stop_test.py`, `test_op7_boottime.py`. The 61 identical and 14 rebound entries still conformed to frozen ef4c073a; no improper OP rebinding was found. The stale manifest is understandable during active preparation but cannot serve as the final frozen-runtime proof.

   **Fix:** After all reviews/edits finish, rebuild the manifest and rerun the independent proof. Check inventory completeness, not only hashes of listed entries; bind the clean result to the frozen sources. No builder or excluded-tree content was executed/read to regenerate this file during this review.

12. **MINOR — Added qualification job exceeds the declared slot allocation.**

   **Location:** `qualify_games.sh:20–30`, especially `30`; `qualify_games.py:78–80`.

   **Scenario:** Eleven concurrent game jobs use cores 5–59. The last injected K4S guard job runs on 55–59, outside all hosts' planned work cores 0–54 (r3 §4.2). Core 0–4's battery has already finished when this script starts, so there is an unused valid slot. The driver checks only list length, not membership, uniqueness, physical-core status or scheduler. This is not evidence that 55–59 are SMT siblings; it is a concrete mismatch with the declared allocation and a missing validation.

   **Fix:** Use the eleven planned five-core slots 0–54, or serialize one job; validate the selected slot against the host plan and observed affinity/scheduler. Update `QUALIFICATION.md:29–42`, which still says cores 5–39 and only game indices 0–4, omits injected indices 5/7, and still advertises verifier tests in the host command that does not run them.

13. **MINOR — STOP/receipt success propagation can report successful qualification after an unrelated failure.**

   **Location:** `stop_test.py:29–43`; `make_qualification_receipt.py:40,43–54`; `run_qualification.sh:14–15`.

   **Scenario:** After STOP is touched, any quick child exit with no process left satisfies the test, including ordinary completion in the race after `poll()` or an unrelated exception. `interrupted_by_owned_stop` is recorded but is required by neither the test's exit condition nor the receipt assembler. Also, the assembler writes `verdict='FAIL'` but exits normally, so the `set -e` driver can exit 0 and write `QUALIFICATION-FINISHED` for a failed receipt.

   **Fix:** Require positive evidence that a game was running and exited because of the owned STOP, using the recorded interruption evidence or a structured acknowledgment. Require that condition in the assembler. Write diagnostic FAIL receipts but exit nonzero when any check fails. Ensure cleanup preserves an externally replaced STOP rather than unconditionally unlinking whatever currently occupies the path.

## Seal and verification limits

- Scoped health/check/qualification code accesses no winner/loss/crowns/draw/final-tick fields. The runner writes them only to sealed game metadata. Static projection inspection and a guarded-metadata sentinel probe of `check_games.project()` found no outcome access. A denied-release probe of actual reducer main confirmed the game loader was never reached.
- Ran all eight authored schedule tests and four charge tests in memory; all passed. Ran all 13 S-default tests on the actual collector function loaded by AST to avoid external imports; they passed with a local Python compatibility shim for the older `ThreadPoolExecutor.shutdown` API. This is not a substitute for the staged-runtime suite. Five actual reducer decision/ledger tests passed using the real functions loaded by AST.
- Inspected all requested scoped files/tests and their fixes; checked 16 Python files by AST parsing and four qualification/staging shells with `bash -n`. No pytest temporary trees, bytecode caches or synthetic game trees were written.
- NumPy, pytest, torch and the staged native runtime are unavailable in the local interpreter. The full reducer/bootstrap, real whole-game qualifications, real STOP test and barrier tests that create/commit temporary git repositories were not run. The prohibition on git commits was honored.
- The sensitivity adapter test exercises callback/data compatibility and flag choice, not numerical CIs. The virtual-clock fake-native probe exercises budget enforcement, not actual command equivalence on real seeds. No prior qualification outcome/evidence receipt was substituted for an independent run.

## Reviewed source identities

Final checked SHA-256 values (before writing this review):

```text
run.py                       eb7a323f1d8fadaeccf5c0870187ee0333426dffff4eaaca0518ed364e8d7684
schedule.py                  b95ad6757baa1623f8af3cd6d65ac47c0a85460fd1ea231122313abf4728d131
reduce.py                    a0ac06b98ba37533d23983207a5125e30c1025e71867a5f60bf21ec4bf92a686
synthetic.py                 64b2d080865e9df8c27d81d1e4104162d30a58f56cd68844de1c4d2b3baea847
health.py                    52c4508e742420559a669388843a8f1b9cca31d43f6b106b10e5220654b59dba
check_games.py               6eb6989b07c58f4ddea64456899a47d78c8bca97bb5e7f37ad9909f1f32a0851
qualify_games.py             80f7d648c1106cc428e4d088aadf03a2c046367582f32f2a70650f3691c06343
qualify_k4s.py               12bb640f5cf7343e6e98e750517c4428f47588f5f6442068280f4b9242518de4
qualify_games.sh             d28702d07bba6b23f596f51f56eabd6ebd40d0010c422f4aba35124b13dd8087
qualify.sh                   04cb5392d94bdf0a1ef61eb43fc7f5310cdfc953135cdc636e4111c4624cc215
make_qualification_receipt.py 2f54d3967480ed35f3897eed2979fbc590524f19bd31f244752a6f0a3c265072
stop_test.py                 7dee55c8b10ca159891fc13cec398271493dedba6803215a6466dff162e31e10
run_qualification.sh         b52b18df9dce2cfbe23bacb8b03bf94dbc2c3bf6cf99ecd85170c0c5b8d26b4e
export_staging_extras.sh      d8a61f9c957f935f96a96110e3feec7692270528ee7ea9c84b11b07dc0327a65
stage_k4s.py                 568642727a1a5f4f5ef135358931079d4fbaff474a3f69ec4bb104a5a4fed5c2
qualification_binding.py     48644ca369eb246c4c43aaf64254a27e86a941eb9fc3fd69385113a2387701c0
QUALIFICATION.md             58b1b12854c4e8c6481d14725e4209cff0c07873786f03da7d8fb6d04ae3fd9e
plan.json                    38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf
test_schedule.py             b1989c36d8fcb9b755dd4bee6af8700d01ae7ba07ab0c1127235cc7785d0b1dd
test_reduce.py               86f4f876012ba6b8346dfff12583b3e02c538b513096770c65d50d9f8430f0fc
test_barrier.py              cf7fad46730be421fd551696ffbe643c986e1dcbc005eafd470c3452ae28cabd
test_sdefault.py             e211a81d1403c270e01e9bcd98bad69dc5437a15b8d3b0099b91c04a6b728eaa
test_charge.py               b8e68aa15bbde6bcb54e012bcd406e07eb3bda044a74735febca98298a177cd1
DELTA-MANIFEST.json          7165b33cd3a50763072038700023a2e34db5af40b96ef6045bc8283819b66c7b
rebind.py                    19df8c112e4d9ddbebb67dd394a5bcb739399188fcf5148d176055d8f18a42a3
```
