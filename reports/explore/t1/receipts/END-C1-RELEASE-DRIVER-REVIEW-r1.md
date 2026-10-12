# T1 END C1: release driver review r1

- **Reviewer:** Claude Opus 5.5, independent code reviewer. I did not write the driver (author: GPT-6.1-Sol), the reducer or R7. This was a read-only review on 127x05, started after 11:14Z and written at 2026-10-12T11:21Z (`date -u`).
- **Subject:** origin/main **494fd4fb**.
  - `reports/explore/t1/release_run.py`, sha256 **51520e9b…1a97a44** (blob 02391ad7);
  - `test_release_run.py`, sha256 **168140a8…6cd12** (blob 7dd24846);
  - diff `receipts/END-C1-release-driver-r1.diff`, sha256 **d0cf5aa0…ecd6e3**. The diff's index lines name exactly these two blobs.
- **Requirements reviewed against:** R7 `END-PRODUCTION-PACKET-REVIEW-r2.md` (C1–C4 and the release procedure) and COORDINATOR 2e275312.
- **Read-only checks of `<R>`:**
  - HEAD is 9bb349b1.
  - reduce.py aebb2017, ssh_sensitivity.py bb124cc4, barrier.py 346d3c05, release_reference.py f8b61c60, check_reference.py c848baa2 and common.py 36e5eec3.
  - The blind ledger is 866e6f7f and the sidecar is 16e1b34f.
  - The C2 receipt is d433dd54.
- **Scope kept:**
  - No SSH, no edits to anything except this file, no commits.
  - I did not run the driver, barrier or reducer, and opened no game or outcome bytes.
  - The only `<R>` content I read was code plus the committed PC4 sidecar (a health file).
  - Tests and mutants ran on a `git archive` export in `/tmp/sdicks02/c1rev/`, using `nice -n 19` and e4v3-venv 3.12.12 `-B` with `PYTHONDONTWRITEBYTECODE=1`.

## Verdict: **REQUEST_CHANGES**

The guarded core (`execute_guarded`) is well designed:
- it computes the pre-guard first;
- it creates the private dir only after the guard passes;
- it runs barrier → reducer → post-check in order;
- it captures output privately and reports type and stage only.

**Ordering is sound for the code as it is pinned today.**

Four defects block approval:
- **RC1.** Most of the code that executes is unpinned. This matters because C3 *requires* a descendant HEAD for the Mac route.
- **RC2.** SIGTERM and SIGHUP leave partial outputs unlocked. I demonstrated this.
- **RC3.** The key post-check (emitted ledger == sidecar) is not actually exercised by any test. `main()` is wholly untested: 14 of 26 mutants survive.
- **RC4.** The interpreter and environment pin is incomplete. The child inherits `PYTHON*` variables, numpy 2.2.6 is not checked, and `-B` is not verified.

All four fixes are small. The guarded core needs no redesign.

## 1. Ordering: no game or outcome byte before the guard

I traced every statement of `main()` up to `health_fn`.

**Steps 1–9 (lines 112–149).**
- argparse;
- `os.umask`;
- interpreter, cwd and git checks (`git status`, `rev-parse`, `merge-base`: git metadata only);
- `sha`/`read` of `--release`, `--r5`, `reduce.py`, `ssh_sensitivity.py`, the blind ledger, the PC4 sidecar and `--copy-receipt`;
- `stat` of BLOCK_ROOT and PRIVATE.

None of these is a game or outcome file. **Caveat:** `--release`, `--r5` and `--copy-receipt` are operator paths, and they are hashed *before* the audit hook exists. A mistyped game path would be read (not parsed or printed) before the pin rejects it. See S2.

**Step 10 (line 154): the audit hook.** It refuses any parent `open` whose path has a `games` component.

**Step 11 (lines 156–158): imports from `here`.**
- `ssh_sensitivity` pulls in `common`, `ssh_budget`, `ssh_transport`, `idle_services` and `cpu_accounting`. `apt_budget` and `host_audit` are imported lazily inside functions.
- `barrier` pulls in `common`. `release_reference` and `check_reference` are lazy.
- I grepped all of these for module-level side effects. They define constants only (e.g. `FAMILIES=Families()`, whose `__init__` sets an empty dict). There are no file reads.

**Step 12 (line 164):** `glob` of `/mpac/sdicks02/tmp/t1-release-recheck-*/check.json`. This is a directory listing only.

**Step 13: `execute_guarded` → `health_fn` = `health_ledger` (bb124cc4 lines 58–71).**
- `root.glob('*/complete.json')`, then `read(complete.json)`;
- `sha(interference.json)`, when it is bound;
- `exists(hub-ack.json)` (a stat only);
- `flagged`/`apt_flagged`, which work on the parsed proof dict (`lan_connection` and `directories_valid` are pure).

No `games/` path is opened. On a mismatch or exception, `require` raises before `mkdir`, barrier or reducer.

**Is the guard meaningful?** The sidecar's 3,072 `complete_sha256` values hash, sorted, to **d0f01069…1c23fe0**, which is exactly the C2 proof-set digest. So the guard re-certifies every copied `complete.json` (and every bound `interference.json`) byte for byte before any game is read. I computed this from the committed sidecar alone.

**After the guard:**
- The in-process barrier `outcome_release` → `prerequisites` runs under the audit hook. R7 §1 logged all of its opens, and none was a game file.
- Its E4 child gets `stdout=DEVNULL` and stderr written to a diagnostics file (check_reference.py lines 45–47).
- Then the reducer subprocess runs its own `outcome_release` before `load_blocks`.

**Conclusion:** given the pinned bytes, no game or outcome file can be opened before the guard passes. RC1 is what keeps that claim true at a descendant HEAD.

## 2. Equality semantics

**Masking.** `without_utc` removes only the top-level `utc` key. Nested keys are compared. Sidecar keys: `blind_ledger_sha256, blocks, flag_counts, schema, sealed, utc`. **Correct.**

**Exactness.** `==` on parsed JSON treats `1 == True == 1.0` as equal (I verified this under 3.12.12). This is **not exploitable here**: every block carries `complete_sha256` and `interference_sha256` strings, so any change to a proof's bytes breaks equality. Even so, "exactly" is better enforced with canonical JSON (S1).

**Pins.**
- `reduce.py` and `ssh_sensitivity.py` are hashed at `here`, the very paths that are executed or imported: reduce is run by absolute path, and `sys.path[0]=here` in both processes.
- `--ignored` cleanliness rules out stale `__pycache__` being read under `-B`.
- The ledger (866e6f7f), sidecar (16e1b34f), R5 (3b7d2295) and C2 receipt (d433dd54) are hashed at their real paths.
- **Gap:** see RC1.

**Root.** BLOCK_ROOT is the literal C2 destination. Its realpath equals itself, it is checked to be a non-symlink directory, and it must equal `copy['destination']`. **Correct.**

**Reducer invocation.**
- argv: `[PYTHON, '-B', <R>/…/reduce.py, --root BLOCK_ROOT, --release <receipt>, --ledger <R>/…/blind-ledger-final-op7-r3.json, --out <private>/reduce.json]`, plus `--mac-summary <R>/<mac_summary_path>` for the Mac route only;
- `cwd=here`;
- interpreter `PYTHON`.

This is the R7 procedure verbatim. **Gap:** the child environment is inherited (RC4).

**Common root.** `common.ROOT == CANONICAL` is asserted after import, and CANONICAL's realpath is itself. **Correct.**

## 3. Fail-closed

| Path | Behaviour | Status |
| --- | --- | --- |
| Pre-guard mismatch or exception | No directory is created, no barrier or reducer runs; the record has `stage=pre_guard` and the type only | OK (tested) |
| Barrier, reducer or post-check exception, nonzero exit, `KeyboardInterrupt` | The directory gets `chmod 000`; the record has stage, type and `outputs_locked`, with `from None` | OK. `KeyboardInterrupt` is untested (mutant F5 survives) |
| Failure after `execute_guarded` (fresh≠2, HEAD/clean changed, receipt write) | `owns_output` → `chmod 000`, generic record | OK, untested (M4, M6) |
| **SIGTERM / SIGHUP / SIGKILL** | Python's default action terminates the process with no `except` or `finally`. **The directory stays 0700 with partial `reduce.json` and stdout.** A child in the same process group gets SIGHUP too, and nothing locks its partial output | **FAIL (RC2)**, demonstrated below |
| Stdout and stderr | Parent: `redirect_stdout`/`redirect_stderr` to private files. Reducer: fd-level files. Barrier's E4 child: DEVNULL / diagnostics file | OK |
| Outputs outside the private dir | The reducer writes only `<out>` and `<out>.ssh-sensitivity-ledger.json` (with a `.tmp` sibling in the same dir). The barrier writes health-only `check.json` in `/mpac/sdicks02/tmp` | OK |
| Failure message | `stage`, `exception_type`, `outputs_locked` and `no_result_reported` only. Exception type names in post-check (KeyError, ValueError, JSONDecodeError) carry no results | OK |

**RC2 demonstration** (`tools/sigdemo.py`). This is a synthetic `execute_guarded` whose reducer writes `reduce.json` and then signals itself:
- **SIGTERM:** exit 143, private dir mode **700**, files = barrier.std*, pre-guard-ledger.json, **reduce.json**, reducer.std*.
- **SIGHUP:** exit 129, private dir mode **700**, the same files.

This matters because the runbook runs the driver over SSH, a disconnect sends SIGHUP, and session restarts kill jobs (a known fleet hazard).

## 4. Unchanged files

The driver writes only to `PRIVATE/<name>/`. No outcome file is written outside it: the barrier's `check.json` scratch in `/mpac/sdicks02/tmp` is health only. It opens nothing in `<R>`, aebb2017, the release roots or the C2 copy for writing.

`git status` (driver and barrier) may refresh `.git/worktrees/source1/index` stat data. That is gitdir metadata, not tracked content. S5 suggests `--no-optional-locks`.

## 5. Tests

**All 11 pass:** 0.036 s with `nice -n 19` and e4v3-venv 3.12.12 `-B`.

**Mutation run:** 26 hand-written mutants of `release_run.py`, using `tools/mut.py` in my scratch.

**Killed (12):**
- G1: drop the pre-guard compare;
- G6: mkdir before the guard;
- P3: bind only `ssh`;
- P4: tolerate a missing key;
- F1: no lock;
- F2: lock 0500;
- F3: leak `str(exc)`;
- F4: ignore the exit code;
- O1: reducer before barrier;
- O2: no barrier;
- O3: no stdout capture.

**Survived (14):**
- **P1: delete the post-check `emitted == sidecar` comparison entirely.** `test_emitted_ledger_difference_locks` rewrites the emitted ledger *after* the reducer bound its SHA, so the *binding* check fails instead. The coordinator's 2969615c check, the reason C1 exists, has no test that isolates it.
- P2: the post-check compares only `blocks`.
- G2–G5: the pre-guard masks `schema`, `blind_ledger_sha256`, `sealed`/`flag_counts` as well, or compares only `blocks`.
- F5: `except Exception` instead of `BaseException`, so a `KeyboardInterrupt` leaves the output unlocked.
- M1–M8, all in `main()`: drop the code pins; drop `--ledger` from the reducer argv; drop the audit hook; drop the `owns_output` lock; drop the dirty check; drop `fresh==2`; drop the C2 destination binding; print `repr(exc)` on failure.

`test_real_health_function_reads_only_synthetic_metadata` is useful: it uses real bb124cc4 and patches `Path.open`, which `read_text` and `read_bytes` go through. Its fixture, though, has no `interference_sha256` and no off-hub host, so the `sha(interference.json)` and `hub-ack` branches are not covered.

## Required changes (all needed for APPROVE)

**RC1. Pin every executed T1 file, and bound the descendant diff.**
- Add to `PINS`, with the bytes R7 recorded at 9bb349b1:
  - every module transitively imported by `reduce.py`, `barrier.py` and `ssh_sensitivity.py`: `apt_budget, barrier, check_reference, common, cpu_accounting, host_audit, idle_services, owned_supervisor, parent_source_seed, perception_confirmation, reduce, release_reference, schedule, ssh_budget, ssh_sensitivity, ssh_transport, system_bus`;
  - **`plan.json`** (it supplies the bootstrap seed and reps).
- **Additionally**, require that `git diff --name-only 9bb349b1 HEAD` be a subset of an explicit allowlist: `reports/explore/t1/release_run.py`, `test_release_run.py`, `RELEASE-RUNBOOK-*.md`, the coordinator's Mac summary path and the release receipt path, if committed.
- **Why:** C3 makes the Mac route run on a local merge of 9bb349b1 with public main. Today only 2 of the 17 modules are pinned. Any future public edit to `barrier.py`, `release_reference.py`, `common.py`, `schedule.py` (ARMS, COUNTS, CELLS) or `plan.json` would run unreviewed inside the barrier and reducer. (No such edit exists on origin/main today; I checked with `git log 9bb349b1..origin/main`.)
- Record `sha(__file__)` of the driver in both the success and failure health records.

**RC2. Lock on termination signals.**
- Before `execute_guarded`, install handlers for SIGTERM and SIGHUP (and keep SIGINT's default `KeyboardInterrupt`) that raise an exception, so the `except BaseException` lock path runs.
- Start the reducer with `start_new_session=True`, so a terminal hangup is delivered only to the parent. `subprocess.run` then kills the child on the raised exception before `chmod 000`.
- Add to the runbook: launch detached (`setsid`, stdout to a private log), never in a bare SSH foreground.
- SIGKILL is unavoidable. The runbook must say that an exit with no health record means "treat as locked: `chmod 000` the private dir, report failure only".

**RC3. Tests that kill the surviving mutants.**
1. **Post-check isolation.** The reducer writes an emitted ledger that differs from the sidecar (e.g. one `ssh_flagged` flipped, or the blocks reordered), and *binds all three `ledger_sha256` to that file*. Expect a locked failure with `stage=post_check`. This kills P1 and P2.
2. **Per-key mismatches.** For each top-level key (`schema`, `sealed`, `blind_ledger_sha256`, `flag_counts`, `blocks`), a pre-guard mismatch and a post-check mismatch both fail. A nested `utc` inside `blocks` is not masked. This kills G2–G5.
3. **Interrupts.** A reducer that raises `KeyboardInterrupt` gives a locked failure (kills F5). After RC2, a reducer that sends SIGTERM/SIGHUP to its own pid also gives a locked failure.
4. **`main()` tests** with the module constants (CANONICAL, BLOCK_ROOT, PRIVATE, PYTHON, the pins) patched to a synthetic git repo and synthetic receipts:
   - every preflight `require` fails closed, with no private dir and only the generic record printed. That covers interpreter, cwd, dirty or ignored files, private ref, ancestry, release, R5, code, blind and PC4 pins, C2 root, C2 binding, private name and private parent mode;
   - **reducer argv equals a literal expected list** for both release reasons;
   - the audit hook refuses an open of `…/games/x`;
   - a record-stage failure (e.g. `fresh≠2`) locks;
   - stdout contains exactly one JSON object, with only the documented keys.

   This kills M1–M8.
5. **Extend the real-`health_ledger` fixture** with a bound `interference.json` and a non-01 host carrying `hub-ack.json`.

**RC4. Complete the interpreter and environment pin (C4).**
- Require `'-B'` in the interpreter options of `sys.orig_argv`. Currently `PYTHONDONTWRITEBYTECODE=1` alone satisfies the check.
- Require `importlib.metadata.version('numpy') == '2.2.6'` (C4 names it, and the reducer's bootstrap depends on it).
- Refuse to run if any `PYTHON*` variable other than `PYTHONDONTWRITEBYTECODE` is set (`PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONSAFEPATH`, `PYTHONUSERBASE`, `PYTHONWARNINGS`, …), or pass the reducer a sanitized env. Today the reducer inherits `os.environ`, so a stray `PYTHONPATH` could shadow numpy or inject a `sitecustomize` in the outcome-reading process.

## Suggested (non-blocking)

- **S1.** Compare canonical JSON (`json.dumps(x, sort_keys=True, separators=(',',':'))` of both sides, with the computed side round-tripped through JSON) in both the pre-guard and the post-check. This makes "exact" literal: no `True == 1 == 1.0`.
- **S2.** Install the audit hook as the first statement of `main()`. Tighten it so that, under BLOCK_ROOT, the parent may open only `*/complete.json` and `*/interference.json`. Also `lstat` that neither is a symlink before the guard.
- **S3.** `fresh == 2` will lock a *successful* release if any other `prerequisites` run creates a `t1-release-recheck-*` dir at the same time. Have the runbook forbid concurrent barrier runs, or identify the two scratch dirs by creation within the driver's run window plus `check.json` content (`checked_at_utc`).
- **S4.** Check C3's "never pushed" offline: `git for-each-ref --contains 9bb349b1 refs/remotes` and `--contains HEAD` must both be empty.
- **S5.** Use `git --no-optional-locks` for the driver's `status` calls.
- **S6.** `hub-ack.json` is only existence-checked, by both the guard and the frozen reducer. C2 verified all 1,100 ACK hashes at copy time, so this is informational only.

## Re-review scope

Send a delta diff against 51520e9b, plus the new test file and its run receipt. I will re-run the mutant set (`/tmp/sdicks02/c1rev/tools/mut.py`), adding RC2/RC4 mutants, and expect every listed mutant to be killed. No production run is needed for re-review.
