# T1 END C1: release driver review r2

- **Reviewer:** Claude Opus 5.5, the independent code reviewer of r1. I did not write the driver (author: GPT-6.1-Sol), the reducer or R7. This is a read-only review, written at 2026-10-12T11:45:46Z (`date -u`).
- **Subject:** origin/main **c5a99fd5**.
  - `reports/explore/t1/release_run.py`, sha256 **42219e57…916a5e** (blob 39a71fd2);
  - `test_release_run.py`, sha256 **683ce23c…7b8569** (blob 473ca178);
  - delta `receipts/END-C1-release-driver-r2.diff`, sha256 **92bd6333…94f**. It is byte-identical to `git diff 494fd4fb c5a99fd5` over the runbook, the driver and the tests (`cmp` clean).
  - The committed `END-C1-RELEASE-DRIVER-REVIEW-r1.md` is byte-identical to my r1 (884ed9f7). The candidate receipt's driver, test and diff SHAs match the values above.
- **Reviewed against:** my r1 (RC1–RC4, S1–S6), R7 C1–C4, and the r2 runbook delta.
- **Scope kept:**
  - No SSH, no edits except this file, no commits.
  - I did not run the driver, barrier or reducer on real data, and opened no game, outcome or proof bytes.
  - In `<R>` I read code, git metadata and directory modes only.
  - Tests, mutants and demos ran on a `git archive c5a99fd5` export in `/tmp/sdicks02/c1rev2/`, using `nice -n 19` and e4v3-venv 3.12.12 `-B` with `PYTHONDONTWRITEBYTECODE=1`. Tools are in `/tmp/sdicks02/c1rev2/tools/` (`mut_r2.py`, `sigdemo_r2.py`, `sigdemo_main_r2.py`).

## Verdict: **APPROVE_WITH_CONDITIONS**

- RC1–RC4 are implemented correctly, and every r1 mutant is killed.
- Pre-outcome ordering still holds, and the pins match `<R>` 9bb349b1 byte for byte.
- The delta adds no outcome-bearing output and no behaviour change beyond RC1–RC4 and S1–S5.
- The conditions below are operational (runbook and launch). None needs a driver change for the fourteen-day route.
- The surviving mutants are test gaps, not code defects. I verified the code paths they cover by inspection and by demo.

## 1. Delta vs RC1–RC4 (and nothing else)

| Item | r2 implementation | Status |
| --- | --- | --- |
| RC1 pins | `PINS` holds the 17 modules plus `plan.json` (§4). `DESCENDANT_ALLOWLIST = frozenset()`, checked as `set(git diff --name-only 9bb349b1 HEAD) <= allowlist`. `driver_sha256` is recorded in both success and failure records | **OK** |
| RC2 signals | `terminating_signals()` maps SIGTERM, SIGHUP and SIGINT to `TerminationSignal(BaseException)` around both `_main` and `_execute_guarded`. The reducer gets `start_new_session=True`. The runbook requires `setsid`, stdin `/dev/null`, a private log, and "exit without health record means chmod 000, failure only" | **OK** |
| RC3 tests | 21 unique tests (32 runs, because `StrongGuardTests` re-runs the 11 base tests). `MainTests` is fork-isolated, so the audit hook cannot leak between tests. It covers 25 preflight scenarios, a literal reducer argv for both routes, the scrubbed environment, the child session, the audit hook, and record-stage locks | **OK** (gaps in §2) |
| RC4 interpreter | Requires `'-B'` in the `sys.orig_argv` interpreter options, `sys.flags.dont_write_bytecode`, the env var, and `importlib.metadata.version('numpy') == '2.2.6'`. The reducer env drops every `PYTHON*` key | **OK** (parent: condition C1) |
| S1 | `without_utc` returns canonical JSON (`sort_keys`, compact separators, `allow_nan=False`), so `True ≠ 1 ≠ 1.0` | OK |
| S2 | The audit hook is the first statement of `_main` (before argparse and any hashing). It resolves paths. Under BLOCK_ROOT it allows only `<block>/{complete,interference}.json`. Neither proof may be a symlink before the guard | OK |
| S3 | The runbook forbids a concurrent barrier | OK |
| S4 | `for-each-ref --contains {9bb349b1, HEAD} refs/remotes` must be empty | OK |
| S5 | `git --no-optional-locks` is used for the status, diff, rev-parse and for-each-ref calls | OK |

**Other diff lines:**
- the `SCRATCH` constant, which is a pure refactor;
- `sys.dont_write_bytecode` changed to `sys.flags.dont_write_bytecode`, which is stricter;
- SIGINT now arrives as `TerminationSignal` instead of `KeyboardInterrupt` (same lock path);
- the `outputs_locked` field added to `preflight_or_record` failures.

None adds content to the visible record beyond `driver_sha256`.

`TerminationSignal(signum)` is published only as its type name, so the signal number does not appear in the visible record.

## 2. Independent mutant re-run (`tools/mut_r2.py`, 47 mutants)

The unmodified suite passed 32/32 on 6 runs (1 verbose and 5 repeats), so no mutant kill is a flake.

**All 26 r1 mutants are KILLED:** G1–G6, P1–P4, F1–F5, O1–O3 and M1–M8. That includes the 14 r1 survivors. Only the `M3` audit-line anchor moved, because of indentation.

**My RC1, RC2 and RC4 mutants are KILLED (14):**
- A1: drop the allowlist check;
- A2: drop the remote-ref exclusion;
- A4: omit `driver_sha256` on failure;
- S1: no handlers in `execute_guarded`;
- S3, S4: drop SIGHUP or SIGTERM;
- S5: run the reducer in the same session;
- E1: drop the `-B` option check;
- E2: drop the numpy pin;
- E3: the child inherits `PYTHON*`;
- E4: the child scrubs only `PYTHONPATH`;
- E5: revert to the r1 flag check;
- C1: revert to dict compare;
- L2: drop the `complete.json` symlink check.

This agrees with the author's 32/32. The author's six extras overlap my E1, E2, E3, S5 and S1.

**SURVIVED (7, all hardening or test gaps; the r2 code is correct):**

| Mutant | Why it survives | Is the behaviour verified otherwise? |
| --- | --- | --- |
| **S2:** no handlers in `main()` (only `execute_guarded`) | No test signals the record stage | **Yes, by demo.** `sigdemo_main_r2.py` signals at the receipt write. r2 exits rc=1, mode **000**, `TerminationSignal`, `outputs_locked=true` for TERM, HUP and INT. With the S2 mutant, the process dies (−15 / −1) and the directory stays **0700** with `reduce.json`, the emitted ledger and the stdout files. The main-level handler is load-bearing and untested |
| **H1:** audit hook installed late (r1 position) | The `early_audit` scenario also fails on the release-pin mismatch, so the test cannot tell that the hook fired *before* hashing | By inspection: line 161 comes before argparse and `sha(args.release)` |
| H2: no BLOCK_ROOT `complete`/`interference` restriction | No scenario opens a non-proof, non-`games` file under the root | By inspection |
| H3: no `.resolve()` in the hook | No symlinked-path scenario | By inspection |
| L1: no `interference.json` symlink check | Only the `complete.json` symlink is tested | By inspection |
| A3: remote check covers 9bb349b1 only, not HEAD | The fake `for-each-ref` fails on the first call | By inspection |
| S6: handlers not restored | Not observable in one-shot use | Not needed |

## 3. Signal demo (independent, r2)

`tools/sigdemo_r2.py` is my r1 demo pointed at the r2 export: a synthetic `execute_guarded` whose reducer writes partial output and then signals itself.

| Signal | Result |
| --- | --- |
| SIGTERM | exit 1, private dir mode **000**, `ReleaseFailure` |
| SIGHUP | exit 1, private dir mode **000**, `ReleaseFailure` |
| SIGINT | exit 1, private dir mode **000**, `ReleaseFailure` |

This reproduces the author's demo. At r1, the same demo gave TERM 143/700 and HUP 129/700. The record-stage demo in §2 extends the result to `main()`.

`subprocess.run` (3.12) catches `BaseException`, `kill()`s the reducer and waits for it in `Popen.__exit__`. That happens before the `except` clause runs `chmod 000`.

## 4. Pins vs `<R>` 9bb349b1

`<R>` is `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source`, a worktree of the public clone.
- HEAD and `refs/private/t1-registration-20261012` are both 9bb349b1.
- `git status --porcelain --ignored` is empty. The one `__pycache__` present is a tracked file.
- `ls-files -v` shows no assume-unchanged or skip-worktree entries.
- `for-each-ref --contains 9bb349b1 refs/remotes` is empty.

**All 18 pins are OK.** For each entry, the sha256 of the R working-tree file, the sha256 of `git show 9bb349b1:<path>` and the driver's `PINS` value are identical. They also equal `END-C1-execution-pins-r2.json`.

**Completeness.** I computed an AST import closure from `reduce`, `barrier` and `ssh_sensitivity`, including lazy imports, over R's t1 directory. It is exactly the 17 pinned modules. There are no relative or dynamic imports, and the only non-stdlib import is numpy.

Because the allowlist is empty and the tree must be clean, the *entire* tracked tree at run time equals 9bb349b1. That covers everything the barrier executes beyond the 17 pins, including the E4 `measure_tiers.py` tree, which `release_reference` also hash-binds.

## 5. Pre-outcome ordering (re-traced at r2)

`main()` runs `terminating_signals`, then `_main`, in this order:

1. `addaudithook(parent_audit)`, first;
2. argparse and `umask`;
3. `sha(__file__)`, which is the driver in the public checkout;
4. the version, `-B`, flags and env checks;
5. **`importlib.metadata.version('numpy')`**, which reads only the dist-info metadata in the venv's site-packages;
6. git `status`, `rev-parse`, `diff --name-only`, `for-each-ref` and `merge-base` (object and ref metadata only);
7. `sha`/`read` of the release receipt, R5, the 18 pins, the ledger, the sidecar and the C2 receipt. All of these now run under the hook, so an operator game path is refused before any byte is read (S2 of r1 is closed);
8. `stat`s of BLOCK_ROOT and PRIVATE;
9. the T1 imports from `here` (unchanged, constants only);
10. a `glob` of SCRATCH;
11. in `_execute_guarded`: `glob` plus `is_symlink` (scandir and lstat only), then `health_fn`, which opens only `complete.json` and `interference.json` (the hook enforces this), then the compare;
12. only then `mkdir`, the barrier and the reducer.

The new top-level imports are `importlib.metadata` and `signal`, both stdlib with no file side effects. **No game or outcome byte can be read before the guard passes.**

## 6. New risk and leakage

- **Visible output:** the success record gains only `driver_sha256`. The failure record has exactly `{passes, stage, exception_type, no_result_reported, driver_sha256, outputs_locked}`, and the tests assert this set. **No outcome-bearing field.**
- **Child environment:** after the scrub, the reducer resolves numpy 2.2.6 from the venv (`sys.path` = here, stdlib, venv site-packages; no user site). It still gets `-B`.
- **Barrier E4 grandchild:** it uses `-I`, which already ignores `PYTHON*` variables. See C2 for its bytecode side effect.
- **Residual windows (accepted, non-blocking).** These are bytecode-sized and not reachable by tests:
  - a second signal arriving inside an `except` clause before `chmod`;
  - a signal arriving between `execute_guarded` returning and `owns_output = True`.

  In both cases a full health record is not printed, or the directory stays 0700, and the runbook's "no completed health record means chmod 000" rule covers it.
- **SIGKILL** remains unhandled, as documented.
- **Orphaned E4 grandchild:** when the parent kills the reducer, the reducer's own E4 recheck grandchild (in the reducer's session) is orphaned. It is health-only and writes only to scratch.

## Conditions (all needed before the release run)

**C1. Launch the parent with a minimal environment.**
- The driver *tolerates* `PYTHONPATH`, `PYTHONWARNINGS` and similar in the **parent**; `MainTests` sets them deliberately and expects success. RC4's "or" option (scrub the child) is met.
- However, a stray `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME` or `PYTHONUSERBASE` would act on the health-only parent before the audit hook exists, and could shadow the stdlib used by the guard and pin checks.
- Launch with `env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 setsid nice -n 19 … <PYTHON> -B <driver> …`, or add a parent-side `PYTHON*` refusal in a future revision.

**C2. Keep the E4 measurement root read-only.**
- `check_reference.pool_command` runs E4 with `-I`, and `-I` ignores `PYTHONDONTWRITEBYTECODE`. I confirmed that `sys.flags.dont_write_bytecode` is 0 under `-I`.
- `measure_tiers.py` imports `receipts`, `telemetry` and `tier_backend` from `<R>/…/mac-e4-package/e4v3` at module level.
- In a synthetic demo of the identical bootstrap, a writable root gets `__pycache__/helper.cpython-312.pyc` and a mode-555 root gets nothing.
- Today `e4v3/` is **dr-xr-xr-x (555)**, so this is dormant. If it were writable, the barrier would create an ignored `__pycache__` in `<R>`. The driver's final `status --porcelain --ignored` would then fail with "canonical state changed" and quarantine a *successful* one-shot release, leaving `<R>` dirty. This is fail-closed (no leak), and it predates r2, since r1 had the same record check.
- The driver does not check the directory mode (git does not track it). Immediately before launch, the operator must verify that `stat -c %a <R>/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3` is `555` and that `git -C <R> status --porcelain --ignored` is empty.

**C3. The Mac route is unavailable at this driver sha.**
- With an empty allowlist, a committed Mac summary, or any local descendant with a tracked change, fails closed. The runbook says this.
- Any allowlist change is a new driver sha and needs a new review. When it happens:
  - use `git diff --no-renames --name-only`, because rename detection reports only the new path;
  - build the C3 descendant from the allowlisted paths only. A true merge of public main would put every public change into the diff.

**C4. Pin the driver before launch.**
- The driver runs from the public checkout. It hashes itself only into the record, after the fact.
- Before launch, the operator verifies `sha256sum <driver>` = `42219e57c052ada73a3ca691839fa47166f1d554fa5600dd85553bb68a916a5e` and that the driver's directory has no stray `.py` files beyond the committed tree (the parent's `sys.path` includes the driver's directory).

## Suggested (non-blocking, next revision)

- **T1.** Add tests that kill S2 (signal during the record stage locks), H1 (an `early_audit` scenario where the release SHA *matches* a path under `games/`, so only the hook can refuse it), H2 (an open under BLOCK_ROOT other than a proof is refused), L1 (an `interference.json` symlink) and A3 (a fake `for-each-ref` that answers only for HEAD).
- **T2.** Block TERM, HUP and INT with `signal.pthread_sigmask(SIG_BLOCK, …)` at the top of both `except` paths, and set `owns_output` before `execute_guarded` returns (e.g. from `directory.exists()` in `except`). This closes the residual windows in §6.
- **T3.** On termination, `os.killpg` the reducer's session, so its E4 grandchild does not outlive it.

## Re-review scope

No re-review is needed for C1–C4: they are runbook and operator checks. T1–T3, if adopted, would change the driver sha and need a delta review.
