# T1 END C1: release driver review r3

- **Reviewer:** Claude Opus 5.5, the independent code reviewer of r1 and r2. I did not write the driver (author: GPT-6.1-Sol), the builder, the reducer or the A3-P tool. This is a read-only review, written at 2026-10-12T12:16Z (`date -u` 12:15:46Z at the start of writing).
- **Subject:** origin/main **f45a3ad8**.
  - `reports/explore/t1/release_run.py`, sha256 **9ffbd2e1…8bca**;
  - `prepare_release_descendant.py`, sha256 **86ae8202…87b1**;
  - `test_release_run.py`, sha256 **056c9aa5…24f**, with 40 tests;
  - delta `receipts/END-C1-release-driver-r3.diff`, sha256 **72cca2af…3f01**. It is byte-identical to `git diff c5a99fd5 f45a3ad8` over the runbook, the driver and the tests, followed by the new builder file (`cmp` clean). The candidate receipt's driver, test, builder and diff SHAs match. The committed `END-C1-RELEASE-DRIVER-REVIEW-r2.md` is byte-identical to my r2 (e5414e3a).
- **Reviewed against:**
  - COORDINATOR 2db197ac (r2 conditions C1–C4, T1–T3);
  - COORDINATOR 4eb6c3e5 (R-M1, R-M2, R-M3);
  - the frozen producers: `mac-e4-session/a3p_poll_check.py`, `e4v3/receipts.py` `seal()`, and `measure_tiers.py` `tiers-summary.json`;
  - in `<R>`: `barrier.py` and `release_reference.committed`.
- **Scope kept:**
  - No SSH, no edits except this file, no commits.
  - I did not run the driver or the builder on real data or on `<R>`.
  - In `<R>` I read only code, git metadata and directory modes. HEAD = `refs/private/t1-registration-20261012` = 9bb349b1, detached; `status --porcelain --ignored` is empty; e4v3 is 555.
  - Tests, mutants and demos ran on a `git archive f45a3ad8` export in `/tmp/sdicks02/c1rev/r3/`, using e4v3-venv 3.12.12 under `nice -n 19` with `-B` and `PYTHONDONTWRITEBYTECODE=1`.
  - Tools are in `/tmp/sdicks02/c1rev/r3/tools/`: `mut_r3.py`, `sigdemo_r3.py`, `sigdemo_second_r3.py`, `sigdemo_main_r3.py`, `pending_exit_demo.py`, `builder_demo.py`, `desc14_demo.py`. Outputs are in `/tmp/sdicks02/c1rev/r3/{mut-r3.txt,demo/}`.

## Verdict: **APPROVE_WITH_CONDITIONS**

**The driver at 9ffbd2e1 is approved for the Mac-summary route under conditions C1–C6.**
- The 18-path allowlist equals R-M1 + R-M2 exactly.
- R-M3 is correct and fail-closed. It runs before the health guard, any game read and the reducer.
- The r2 hardening (T1–T3) is implemented. All 47 earlier mutants are killed, including the 7 r2 survivors.
- Pins are unchanged and match `<R>`.
- Pre-outcome ordering holds, and the visible record adds nothing outcome-bearing.

**The descendant builder at 86ae8202 is NOT approved to run on `<R>` as-is.** It will silently overwrite any existing `refs/private/*` ref, including `<R>`'s own protection ref (C1). The fix is builder-only and does not change the driver SHA.

**The 14-day route changes semantics under r3**, so it stays on 42219e57 as already ruled (C4).

None of the conditions needs a change to `release_run.py`. C1 changes the builder only; C6 adds tests only.

## 1. Mac-summary route allowlist (R-M1)

| Check | Result |
| --- | --- |
| `DESCENDANT_ALLOWLIST` vs ruling | **Set-equal to the 4eb6c3e5 list:** 11 `sealed/*`, 4 top-level files, `private-commit-binding.json`, and the 2 failure-only files, 18 in all. Literal paths, no wildcards. `classification/*` is excluded, so unknown classifier paths are denied (`builder_demo.py`: `allowlist_equals_ruling True 18`) |
| Driver diff | `git diff --no-renames --name-only 9bb349b1 HEAD ⊆ allowlist`. Rename detection is off, so a rename cannot hide its deleted source |
| Failure paths | On the Mac route, `sealed/failure.json` and `cleanup-failure.json` in the descendant diff are refused before any binding is read. This matches the A3-P producer, which refuses any seal that lists them |
| Mac route on undescended HEAD | Fails closed: the Mac commit is not an ancestor of 9bb349b1 (`merge-base --is-ancestor`, `check=True`) |

### Descendant builder (`prepare_release_descendant.py`)

**Correct:**
- It uses a temporary `GIT_INDEX_FILE` and `read-tree 9bb349b1` (the constant, not the ref).
- It refuses the run if `ls-tree -r <source> -- D` lists anything outside the allowlist.
- It copies only `100644 blob` rows whose `ls-tree` path equals the name exactly. Symlinks, gitlinks and trees are rejected.
- It runs `write-tree`, then `commit-tree -p 9bb349b1 -p <source>`, then checks the result's `--no-renames` diff against the allowlist.
- There is no whole-tree merge, no checkout and no push command.

**Realistic-topology demo** (`builder_demo.py`). The source is on a public branch that does *not* contain the private commit, as public main does not contain 9bb349b1. Results:
- Both 9bb349b1 and the source are ancestors of the result.
- The tree keeps the private-only file and excludes the unrelated public file.
- HEAD, the real index and the worktree are untouched.

**Two-parent ancestry vs `release_reference.committed` and `barrier.outcome_release`.** Both require `merge-base --is-ancestor <binding commit> HEAD`, a matching `git show` SHA, and equal worktree bytes.
- The END-reference bindings reach HEAD through parent 1 (9bb349b1).
- The Mac summary, A3-P and seal bindings reach HEAD through parent 2.
- Nothing in the pinned closure inspects parent shape. The only HEAD-sensitive git calls are `merge-base` and `show -s --format=%ct <binding commit>`.
- **Correct, provided HEAD is actually moved to the descendant** (see C2).

**Defects and gaps:**

- **B1 (medium): private-ref clobbering.** `update-ref <ref> <commit>` has no old-value guard. The only check is the `refs/private/` prefix.
  - Passing `refs/private/t1-registration-20261012` moves `<R>`'s protection ref onto the descendant. **Demonstrated:** `PRIVATE_REF overwritten: True`.
  - Any re-run likewise overwrites an earlier descendant ref.
  - `core.logAllRefUpdates=true` does not log `refs/private/*`, so no reflog records the old value.
  - The driver would then fail closed with "private ref changed". The damage is recoverable, because 9bb349b1 is a pinned constant and the descendant's first parent. Still, it violates "nothing can modify `<R>`".
- **B2 (low):** the builder inherits `os.environ`, so `GIT_DIR`, `GIT_WORK_TREE` or `GIT_OBJECT_DIRECTORY` could redirect it. It imports the allowlist from whatever `release_run.py` sits beside it.
- **B3 (runbook gap):** the builder deliberately does not move HEAD, but no step says how `<R>`'s detached HEAD reaches the descendant. The driver needs HEAD = descendant and the files in the worktree; both `committed()` and the driver compare worktree bytes.

### Private refs and pushing

- Neither the driver nor the builder can push.
- The builder's ref lives in the shared object store of the public clone (`git-common-dir` = `/mpac/sdicks02/repos/clasher/.git`), the same as the existing `PRIVATE_REF`. This is unchanged since r2.
- The driver's `for-each-ref --contains {9bb349b1, HEAD} refs/remotes` check still covers the descendant (A3 is killed).

## 2. R-M3 A3-P gate

**Order in `_main`:**
1. audit hook;
2. interpreter, flag and numpy checks;
3. git clean/ref/allowlist/remote/ancestry checks;
4. release SHA, R5 and envelope;
5. **if `reason == committed_mac_summary`: failure-path refusal, then `check_mac_a3p`**;
6. pins, ledger, C2, private parent;
7. imports;
8. `execute_guarded` (health guard → mkdir → barrier → reducer).

The gate reads only committed Mac metadata in `<R>` and git objects, under the audit hook. **No game byte, no health callback, no output directory and no reducer** come before it.

**Bindings.** `bound_mac_json` enforces, for each artifact:
- the exact path;
- a 40-hex commit and a 64-hex SHA;
- the commit is an ancestor of HEAD (`check=True`);
- `git show` SHA = binding SHA;
- the worktree bytes equal the committed bytes, and `resolve()` is the identity (no symlink).

It is applied to:
- `tiers-summary.json`, via the barrier's own `release.commit`/`mac_summary_sha256`;
- `a3p-poll-check.json`;
- `sealed/receipt-manifest.json`.

**Chain:**
- A3-P `receipt_manifest_sha256` = the manifest binding SHA = the SHA of the committed manifest bytes.
- The manifest has `status == 'complete'`, and `files['tiers-summary.json']` = `mac_summary_sha256`.
- The summary has `dry_run is False`, and A3-P has `outcomes_read is False`.
- Tier coverage: `set(summary.feasibility) == set(a3p.tiers) == {K0c, S, K2, K4}`.
- Per tier, all four values are of `type is bool`, `frozen_feasible` = the summary's `feasible`, and `feasible_after_a3p == (frozen and a3p_passes)`.
- If `frozen and not feasible_after_a3p`, the driver raises `A3PRequiresRuling`.

**Schema compatibility with the frozen producers is confirmed:**
- `a3p_poll_check.py` writes `tiers[t].{frozen_feasible, feasible_after_a3p, a3p_passes}`, `receipt_manifest_sha256` and `outcomes_read=False`.
- `receipts.seal()` writes `{scope, status, files{relative name: sha}}`.
- `measure_tiers` writes `feasibility[t].feasible` and `dry_run`.

**Failure path.** `A3PRequiresRuling` is a `ValueError` subclass caught by `_main`. The visible record is `{passes:false, stage:preflight_or_record, exception_type:A3PRequiresRuling, …, outputs_locked:false}`. It reveals only that a public Mac timing gate removed a tier, which is not outcome-bearing.

**Fail-closed:** every missing key, type error, `CalledProcessError` or mismatch raises before the guard.

**Minor:** the loop raises on the first disqualified tier, in sorted order. A later tier's Boolean inconsistency would then be reported as `A3PRequiresRuling` rather than `ValueError`. Both are stops that go back to the coordinator, so this is cosmetic. Validating all tiers before deciding would be cleaner.

**Verdict on R-M3: correct and fail-closed.** It is under-tested, though (§4).

## 3. r2 hardening (T1–T3)

| Item | Implementation | Status |
| --- | --- | --- |
| T1 tests for the 7 survivors | `record_signal_{TERM,HUP,INT}` (S2), `early_audit` with a release-SHA match (H1), `audit_other` (H2), `audit_alias` (H3), interference symlink (L1), `remote_HEAD` (A3), handler-restore test (S6) | **All 7 KILLED** |
| T2 mask in failure handlers | `block_failure_signals()` is the first statement of the `except` in `_execute_guarded`, `_main` and `run_reducer`. `terminating_signals` saves and restores the mask | OK (T2a, T2b, T2d, T2e, T2i killed; T2c verified by demo, §5) |
| T2 atomic owned marker | `mkdir`, `created=True` and `on_created()` (which sets `owns_output`) run inside `ownership_signals_blocked()`. The r2 window between the return and `owns_output = True` is gone | OK (T2f killed; T2g/T2h are window-only, verified by inspection) |
| T3 kill the whole session | `run_reducer`: `Popen(start_new_session=True)`. On `BaseException` in `wait()`, it masks, runs `os.killpg(child.pid, SIGKILL)` (the unreaped child keeps the group alive, so there is no PID-reuse race) and `child.wait()`, then re-raises. The pinned closure has no `setsid`/`setpgid` (the only `start_new_session` is in unpinned `supervise.py`), so E4 grandchildren share the reducer's group | OK (T3a–T3f killed) |

## 4. Mutant re-run (`tools/mut_r3.py`, 104 mutants, independent list)

The unmodified suite passed 40/40 on 3 runs.

**Earlier 47: all KILLED.** That is the 26 from r1 and the 21 from r2, including the r2 survivors S2, H1, H2, H3, L1, A3 and S6. This agrees with the author's `END-C1-mutants-r3.txt`.

**New r3 mutants: 26 KILLED, 31 SURVIVED.**

| Group | Killed | Survived (all code-correct by inspection; test gaps) |
| --- | --- | --- |
| T2/T3 (15) | 12 | **T2c** (no mask in `run_reducer` except; load-bearing per §5 demo); T2g, T2h (bytecode windows) |
| Allowlist (5) | AL3 (extra classifier path), AL4 (missing path) | **AL1** (rename detection in driver diff); **AL2** (prefix/wildcard allowlist: no driver test commits an unlisted path under `D`); **AL5** (failure paths not refused) |
| R-M3 (24) | R1 (no gate), R2 (no raise), R3 (gate moved after the guard), R4 (seal SHA), R13, R24 (exception type) | **R5–R12:** manifest status/summary entry, `dry_run`, `outcomes_read`, tier coverage, bool types, `frozen_feasible` binding, `after_a3p` binding. **R14–R23:** path, regex, ancestry, SHA, worktree bytes, symlink, A3-P commit or SHA ignored, manifest SHA ignored, summary path not forced |
| Builder (13) | D2, D4, D6, D9, D12, D13 | **D1** (any ref name), **D3** (symlink blob allowed), **D5** (source-only parent: the test's source descends from base, unlike real public main), D7 and D8 (equivalent by construction, since only allowlisted names are ever added), D10, D11 |

Only the two headline R-M3 scenarios, `a3p_reject` and `a3p_seal_mismatch`, are tested. The commit/SHA bindings and Boolean-consistency checks that the ruling names are not reached by any test.

I checked each surviving check by reading the code against the producers, and all are correct. This is test debt, not a defect, but it is the newest safety code (C6).

## 5. Signal demos (independent, r3)

**`sigdemo_r3.py`:** the real `run_reducer` under `execute_guarded`. The reducer child spawns a sleeping grandchild, writes partial `reduce.json`, then sends the parent 1, 2 or 5 signals.

- For TERM, HUP and INT, at every count, all 9 runs gave:
  - `ReleaseFailure`, stage `reducer`, `TerminationSignal`, `outputs_locked=true`;
  - private dir **000**;
  - **child dead, grandchild dead.**
- In r2 the grandchild was orphaned.

**`sigdemo_second_r3.py`:** a second SIGTERM injected at the start of `killpg`.
- **r3:** kill and reap complete in 0.4 s. Mode 000; child and grandchild dead. The deferred signal surfaces later as `TerminationSignal`.
- **T2c mutant:** the parent **hangs 30 s** in `Popen.__exit__` waiting on an unkilled reducer.
- **The `run_reducer` mask is load-bearing.**

**`sigdemo_main_r3.py`:** signal at the record-stage receipt write in `main()`. For TERM, HUP and INT: rc=1, mode **000**, `TerminationSignal`, `outputs_locked=true`.

**`pending_exit_demo.py` (residual, new to r3, fail-closed).**
- If a *second* signal arrives while `_main`'s failure handler is masked, it stays pending.
- On return, `main()`'s `terminating_signals` first restores `SIG_DFL` and then unmasks, so the default action kills the process: **rc 143, and the buffered health line is lost** (0 bytes when stdout is a file).
- The directory is already 000. The runbook's rule "no completed health record means locked, failure only" covers this.
- Suggested fix: `print(..., flush=True)`, or unmask before restoring handlers so the pending signal raises into Python instead.

## 6. Launch conditions (runbook)

The runbook now states:
- `env -i` with HOME, `PATH=/usr/bin:/bin` and `PYTHONDONTWRITEBYTECODE=1`;
- setsid, stdin `/dev/null`, a private exclusive log;
- verify the driver SHA and that its directory has only the committed tree;
- e4v3 mode exactly 555 and `status --porcelain --ignored` empty.

This satisfies the 2db197ac C1–C3 conditions as runbook checks, not code. It does **not** yet record 9ffbd2e1 as the reviewed SHA; it says "requires its own review and recorded SHA" (C5).

## 7. Unchanged invariants

- **Pins.** `PINS` is unchanged, and all 18 equal `<R>` working-tree bytes (recomputed: 0 mismatches).
- **Ordering.** As in §2. `bound_mac_json`'s `git show`/`merge-base` and the reads of `<R>/D/*` all happen under the audit hook, and none touches `BLOCK_ROOT`.
- **Leakage.** The success record is unchanged from r2. The failure record keeps the same 6 keys (asserted by tests); the only new visible value is the type name `A3PRequiresRuling`. The reducer env and argv are unchanged (the literal argv test passes for both routes).
- **`<R>` modification.** The driver writes nothing in `<R>`. The builder writes only objects and the named ref (B1).
- **14-day route: not unaffected.**
  - With HEAD = 9bb349b1, r3 behaves identically to 42219e57: the diff is empty, the A3-P block is skipped, and only the signal handling differs.
  - But r3 *also* accepts `fourteen_day_escape` on a Mac descendant HEAD, even one that carries `sealed/failure.json`. The failure-path refusal and A3-P gate are skipped there.
  - **Demonstrated** (`desc14_demo.py`): the fourteen-day route on a failure-carrying descendant gives rc 0, with calls health → barrier → reducer, `passes: true`. The same tree is refused on the Mac route. At 42219e57 this tree is refused ("unapproved descendant diff").
  - This is benign for outcomes, since the 14-day reducer ignores Mac files, but it is a semantics change.

## Conditions

**C1. Fix builder private-ref handling before the builder ever runs on `<R>`.** This is a builder-only delta with a narrow review; the driver SHA is unchanged. The builder must:
- refuse `PRIVATE_REF`;
- create the ref only if absent, e.g. `git update-ref <ref> <commit> ""` (an empty or zero old value requires absence);
- assert `rev-parse PRIVATE_REF == 9bb349b1` before and after.

Also add tests for D1 (prefix), D3 (symlink at an allowlisted path) and D5. D5 needs a realistic fixture whose source branch does not contain the base.

**C2. Specify the HEAD move in the state-change ruling and runbook.** For example: `git -C <R> switch --detach <descendant>`, after the builder and before the driver. Then verify:
- HEAD equals the builder's `commit`;
- `status --porcelain --ignored` is empty;
- `diff --no-renames --name-only 9bb349b1 HEAD` ⊆ allowlist, with no failure paths;
- `PRIVATE_REF` is still 9bb349b1;
- e4v3 is still 555.

**C3. Builder launch hygiene.**
- Run it under `env -i`, with no `GIT_*` variables, as `python -B`.
- Run it from a directory whose `release_run.py` is 9ffbd2e1 and whose builder is the reviewed (C1) SHA, with no extra `.py` files.
- Use a fresh, unused `refs/private/…` name.

**C4. Keep the 14-day route on 42219e57**, as 2db197ac already rules. Alternatively, use r3 only with `<R>` HEAD exactly 9bb349b1. Any later driver revision should add `reason != committed_mac_summary ⇒ descendant diff == ∅`.

**C5. Record the reviewed driver SHA in the runbook before the Mac route launches.** The SHA is `9ffbd2e197e58b5c56b3d58cefe4008d47cb4fdf50764808e841218294408bca`. The r2 operator checks (`env -i`, e4v3 555 and a clean tree, the driver SHA plus a committed-only directory) apply unchanged.

**C6. Add tests before the Mac-route release.** These change only the tests, not the driver SHA. Cover:
- R-M3 bindings (R14–R23);
- seal and scope (R5–R8);
- tier coverage, types and consistency (R9–R12);
- an unlisted path under `D` in the driver (AL2);
- Mac route with `failure.json` (AL5);
- a rename-from-pinned-path descendant (AL1);
- a second signal during `run_reducer` cleanup (T2c).

Rerun the mutant suite with `tools/mut_r3.py`. All R- and AL- mutants and T2c must be killed; the D-mutants are covered under C1. Record the receipt. I can verify it without a full re-review.

## Suggested (non-blocking)

- `print(..., flush=True)` for both visible records, or unmask before restoring handlers in `terminating_signals` (§5 residual).
- In `check_mac_a3p`, validate every tier before raising `A3PRequiresRuling`.
- Bind `sealed/receipt-manifest.sha256` content against the manifest SHA as well. It is already allowlisted and verified Mac-side by A3-P.

## Re-review scope

- **C1:** a narrow delta review of the builder only.
- **C6:** a mutant-rerun receipt only.
- **C2–C5:** runbook and operator checks only.
- `release_run.py` 9ffbd2e1 needs no further code review for the Mac route.
