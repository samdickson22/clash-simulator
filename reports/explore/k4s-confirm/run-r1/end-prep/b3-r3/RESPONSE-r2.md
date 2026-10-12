# RESPONSE to SOL-REVIEW-END-PKG1-r2, S4 (b3-r2 → b3-r3)

- **Reviewed bytes (r2):** assembler `f03f534feb8dcf3ac3db1948c3cdba170a0efd9f213e60cf54c197cea8d0f473` and `RESPONSE-r1.md` `fee311fa…`. Both match the review (re-hashed in `b3-r2/` at the start of r3).
- **Candidate:** `b3-r3/` was created as a copy of `b3-r2/`. No file outside `b3-r3/` was edited.
- **Rulings applied (binding):**
  - COORDINATOR `2026-10-12 16:55Z` (ab1715910): E1, E2, E3.
  - 16:00Z scope ruling (1aa63a16): TOCTOU is the only accepted residual.
  - 15:41Z rulings (fa89baa9).
- **Line references:** `A:` is `assemble_fleet_reference.py`, `T:` is `test_assemble_fleet_reference.py` and `M:` is `mutation_check_r3.py`, all in b3-r3 (SHAs at the end).
- **Stamp:** `2026-10-12T17:17:40Z` (`date -u`), 127x05, offline.

## S4-R2-F1 (BLOCKING): static hard-link aliases can read outcome bytes

**Change.** Every regular-file input must have `st_nlink == 1`, checked twice, both before any byte is read:

1. **In the lstat walk** (`walk()` A:286), for the leaf of every file walk. Every input class reaches it:
   - `absolute()` A:290 for request sources, `--request`, synthetic pins and the assembler file;
   - the runtime inventory A:462–465;
   - the measurement entries A:407–415, all walked before any is hashed;
   - the S1 metadata;
   - the evidence artifacts;
   - the E1 target, through the alias walk A:278.
2. **At the descriptor gate** (`open_confined()` A:301–316).
   - The open uses `O_NOFOLLOW|O_NONBLOCK|O_NOCTTY` (A:304).
   - `fstat` of the opened descriptor must show a regular file with the walked `(st_dev, st_ino)` and `st_nlink == 1` (A:313–315). Otherwise the descriptor is closed before `os.fdopen`.
   - Every hash, parse and copy goes through this function, including the copy pass (`copy_verified` A:826).

There is no hard-link exception. The E1 target and the E2 file must also be single-link.

**Inode canary controls.** The audit hook is `class Audit` at T:1068. It is installed with `sys.addaudithook`, and recording starts just before `A.main` (T:283). For every `open` event it records the inode (lstat and stat) of the path, so an open through any link name of a canary is detected. Each canary is `TMP/games/<class>/complete.json` at mode 000, so any read would also fail.

| Control | Test |
|---|---|
| Hard-linked outcome canary in **22 input classes** × {consistent SHAs (canary carries the original bytes, so only the gate can refuse), stale SHAs}. Each asserts `Hard-linked input refused (<that class's label>)` and that the canary inode was never opened. The classes: runtime pin member, discovered `.py`, E1 target, E2 file, S1 runtime-pin JSON, S1 qualified JSON, measurement `.py`, `spec-pins.json`, `states.pkl`, `states-rows.json`, `states-rows.bin`, `v1.pt`, sets, END evidence, evidence artifact, telemetry, guard freeze, guard module, bus admission, idle admission, seed, synthetic pins. | `HARDLINK_CLASSES` T:1133; T:1161 (44 cases) |
| Hard-linked `--request` file | T:1170 |
| Descriptor gate, end to end: a link created after the walk of `sets`; `os.fdopen` never sees that inode | T:1185 |
| Descriptor gate, unit (`sha_confined`, `read_confined`; `fdopen` never called) plus the walk gate | T:1207 |
| A link made between planning and the copy pass is refused at the copy's open; no bundle remains | T:1221 |
| E1 target hard-linked: refused through the alias walk itself | T:1384 |
| The assembler's own file hard-linked: refused before planning (subprocess) | T:1442 |

## S4-R2-F2 (BLOCKING): auxiliary source paths can come from the sealed END namespace

**Change.** There is one name gate, `location_free()` (A:241–252), applied to the **complete absolute path** before any `lstat` or open.

It refuses:
- outcome/block components and leaves;
- `k4s-confirm-*` and `k4s-end-guard-*` components;
- FROZEN-T1 launch namespaces;
- the strict END namespace, via `end_namespace_free()` (A:233–238): any `k4s-confirm` component followed by `end` (`END_PAIR` A:78; `END_DIR` A:77). This is END-RUNBOOK's `reports/explore/k4s-confirm/end/`, wherever it is rooted.

Where it is applied:

| Location | Where |
|---|---|
| Every walked input. `walk()` calls it first (A:261), so every request source, `--repository`, `runtime_root`, e4v3, every runtime/measurement entry, the S1 metadata, every evidence artifact, `--request`, synthetic pins, the assembler file and the `--out` parent are covered. | A:261 |
| Runtime tree: the END namespace directory is refused **without being listed or descended** | A:433 |
| Evidence items (explicit, before the SHA/commit checks; replaces r2's `startswith("end/")`) | A:670 |
| Committed-admission paths, then the exact E3 path | A:555, A:557 |
| `git cat-file` paths | A:532 |
| Guard-job parent (`JOB_PARENTS[host]`) | A:705 |
| Seed paths (r2 used only `outcome_free`) | A:759 |
| `--out` | A:804 |
| `--request`: now confined and read through `Source` (r2 used `Path.read_bytes()`) | A:901 |

**Controls.** Each control asserts its refusal message; where bytes are at stake, it also asserts that the canary inode was never opened.

| Control | Test |
|---|---|
| The reviewer's reproduction: valid sets JSON at `end/receipts/round-00/127x03/raw-00/reference-warmup.json` | T:1235 |
| `end/attempt-00.json`, `end/registry/…/attempt-00.json`, `end/END-JOB.json`, `copy/k4s-confirm/end/pools/…` as a request source | T:1247 |
| An END-namespace runtime member, and the END directory in the runtime tree (two messages) | T:1254 |
| The END directory is never passed to `os.scandir` | T:1263 |
| `runtime_root` in the END namespace | T:1272 |
| `--repository` in the END namespace, `games/` or a job tree; refused by name before `lstat` (the paths do not exist) | T:1283 |
| `--out` in the END namespace, `games/`, a guard-job tree, or named `end-raw.json`; nothing written | T:1293 |
| `--out` in a T1 launch namespace | T:1300 |
| Guard-job parent in a `games`, T1 or END location; the two real parents pass | T:1305 |
| `git cat-file` path and frozen seed path in the END namespace | T:1315 |
| `end-guard-admissions/` is not the END namespace; `END_DIR` is | T:1325 |
| Unsafe absolute paths are refused by `location_free()` | T:1429 |
| Committed-admission paths: END namespace, `games/`, wrong host, not exact E3, `t1/receipts` | T:843 (param list) |
| Evidence item under `end/` (now the shared gate) | T:654 |

## S4-R2-F3 (MEDIUM): synthetic pins bypass the confinement helpers

**Change.** `active_pins()` reads the file with `read_confined(*absolute(location, SYNTHETIC_ENV, "file"))` (A:388). It therefore goes through the same name, lstat, hard-link and descriptor gates. `check_exemptions()` (A:391, A:395–404) then refuses pins that widen or move E1/E2.

| Control | Test |
|---|---|
| Pins through a symlinked parent; real file at mode 000, inode never opened | T:1331 |
| Pins under `games/` or the END namespace, or named `complete.json`; inode never opened | T:1345 |
| Hard-linked pins | T:1161 (`synthetic-pins` class) |
| Relative and non-normalized `K4S_S4_SYNTHETIC_PINS` | T:1352 |
| Test mode cannot widen or move the E1/E2 exemptions | T:1365 |

## Coordinator rulings E1–E3 (16:55Z)

- **E1.** The alias is checked in three places:
  - `committed_alias()` (A:536–543, called at A:589) requires the `--repository` HEAD entry `visualize_battle.py` to be mode `120000`, with a blob that is exactly `examples/visualize_battle.py` (`git ls-tree -z` + `git cat-file`; `git_run` A:518).
  - The runtime link must be root-level with exactly that text (A:273–277).
  - The link is never opened: the walk restarts at the target (A:278), which passes `location_free()`, the no-symlink walk and the hard-link gate.

  The alias map is fixed to E1 (`E1_ALIAS, E1_TARGET` A:81; `check_exemptions` A:395). The real repository has this entry at origin/main fa32ab3f (`120000 blob a79f7391…`, blob text verified), and it is the only tracked symlink.

  Tests:
  - T:1370: a regular file with the same text, a different link text, and no entry are each refused;
  - T:1393: no open event names the link, and the target is opened;
  - T:1384: hard-link gate through the alias walk;
  - T:1365: test mode cannot widen the map.
- **E2.** `E2_PATH` and `E2_SHA256` are code constants (A:82–83).
  - `check_exemptions` (A:395–404) allows exactly that path. In production its SHA must be `d1492d0f…`; test mode may substitute only the SHA of synthetic bytes. It is called by `active_pins` and by `runtime_files` (A:444).
  - Only the runtime walk passes `exception=True`, and only for that name (A:465).
  - The file is hashed with the other members (A:473) and compared with its pin (A:475). It is never parsed.

  Tests:
  - T:1400: exactly one open of its inode, and never passed to `parse_json`;
  - T:1410: refused at another path;
  - T:1417: production constants equal the ruled path and SHA, and a production SHA change is refused;
  - r2's wrong-SHA control is kept.
- **E3.**
  - The path must be exactly `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>` (A:557; `ADMISSION_REPO_DIR` A:79).
  - The identities stay pinned from r4 (`PRODUCTION_PINS` A:107).
  - A stale identity is refused, with a message naming the coordinator re-pin ruling that is then needed (`STALE_IDENTITY` A:146; A:743, A:750).
  - Tests: T:843 for paths; T:870 and the new T:1456 for stale identities.

## Other r2-review notes

- **"Apply this uniformly to inventory, metadata, models, evidence, admission and seed inputs."** Done. The 22-class table above covers each one, in both SHA states.
- **"Add inode-based canary controls … including stale composite SHA cases."** Done. The `stale-shas` parametrization covers this, and the `consistent-shas` cases show that the gate, not a later SHA check, refuses.
- **"Keep legitimate END health inputs at their declared external locations."** Evidence stays at `REPO/reports/explore/k4s-confirm/end-evidence.json` and its items under `reports/explore/k4s-confirm/` outside `end/`. Admissions are at the E3 path. Unchanged otherwise.
- **R4/R5 (Sol support).** Recorded in OPEN-QUESTIONS; no code change. S3 must still enforce distinct host jobs per preflight and attempt.
- **S3/S5 must reject the synthetic stamp and `production_pins:false`.** This is unchanged and still disclosed (README, DESIGN §C.3).
- **Production consequences of the new gates.** These are new OPEN-QUESTIONS items:
  - **R6:** the runtime that S4 hashes must exclude `reports/explore/k4s-confirm/end/`. The END-JOB is committed there, and the runbook uses R as both runtime root and repository. The host-side `validate_bundle` hashes only the listed `runtime_files` (`receipts.verify_files`), so excluding it has no host-side effect.
  - **R7:** every input must be a single-link file. The three Q6 copies on 05 are (`stat -c %h` = 1).

## Verification (127x05, origin/main fa32ab3f in a detached worktree under `/tmp`, removed afterwards)

Command: `cd /tmp && K4S_FROZEN_ROOT=/tmp/b3r3-wt nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B [-O] -m pytest -q -p no:cacheprovider <b3-r3>/test_assemble_fleet_reference.py`.

**Frozen paths.** Between 1aa63a16 and fa32ab3f, no file changed under e4v3, `reports/explore/k4s-confirm/*.py` (outside `run-r1/`), `plan.json`, FROZEN-T1, the T1 modules, the S1 receipts or the `visualize_battle.py` entries (`git diff --name-only`).

**Test results:**
- **252 passed** normally;
- **252 passed** under `-O` (1 pytest missing-assertion warning; the suite uses `ok()`);
- without `K4S_FROZEN_ROOT`: **227 passed, 25 skipped**.
- The two real-Q6 tests ran on 05; they read only the 353 KB index.

**Name rules on real lists (r3 rules, names only).**
- 0 refusals among the 1,557 names in `runtime-pin-r2.json` and the 3,785 names in each A3 manifest's `runtime_files`.
- Of the 11,619 tracked paths at fa32ab3f, 4 are outcome-named leaves: E2, plus three `complete.json` files under `live-loop/v4/`, which are not runtime members.
- No tracked path is in the END namespace or a job tree.

**Mutation check.** `M:` is `mutation_check_r3.py` under `-O`, with scratch copies in a fresh temp dir that is deleted. The baseline (unmutated) passes 252 first. **27 of 27 killed.**

| Mutant (M:) | Result | Failing tests (count; first killers) |
|---|---|---|
| F1 walk `st_nlink` gate removed | KILLED | 48; the hard-link class matrix (T:1161), T:1170, T:1384 |
| F1 descriptor `st_nlink` gate removed | KILLED | 3; T:1185, T:1207, T:1221 |
| F2 END namespace gate is a no-op | KILLED | 16; T:654, T:843, T:1235, T:1247 … |
| F2 `location_free` not called by `walk` | KILLED | 22; r2 outcome-name controls, T:1247, T:1272, T:1283, T:1345 |
| F2 `location_free` skips the END namespace | KILLED | 15 |
| F2 `location_free` skips the T1 namespaces | KILLED | 3; r2 T1 request control, T:1300, T:1305 |
| F2 `location_free` accepts unsafe absolute paths | KILLED | 1; T:1429 |
| F2 runtime END directory descended | KILLED | 2; T:1254, T:1263 |
| F2 `--out` location gate removed | KILLED | 5; T:1293, T:1300 |
| F2 guard-job parent not gated | KILLED | 1; T:1305 |
| F2 committed-admission location gate removed | KILLED | 2; T:843 |
| F2/E3 exact admission path not required | KILLED | 3; T:843 |
| F2 evidence item location gate removed | KILLED | 1; T:654 |
| F2 `git_blob` location gate removed | KILLED | 1; T:1315 |
| F2 seed path back to `outcome_free` only | KILLED | 1; T:1315 |
| F2 `--request` read without the gates | KILLED | 1; T:1170 |
| F2 assembler self-hash without the gates | KILLED | 1; T:1442 |
| F3 synthetic pins read without the gates (r2 form) | KILLED | 7; T:1161 (synthetic-pins), T:1331, T:1345 |
| E1/E2 `check_exemptions` is a no-op | KILLED | 6; T:1365 |
| E1/E2 `runtime_files` skips `check_exemptions` | KILLED | 1; T:1435 |
| E2 production SHA not enforced | KILLED | 1; T:1417 |
| E1 committed alias not checked | KILLED | 1; T:1370 |
| E1 git mode not required | KILLED | 1; T:1370 |
| E1 link text at HEAD not required | KILLED | 1; T:1370 |
| E1 alias target gated only by name (no hard-link gate through the alias walk) | KILLED | 1; T:1384 |
| E3 stale bus identity accepted (r2 gate, re-checked) | KILLED | 2; T:870, T:1456 |
| E3 stale idle identity accepted (r2 gate, re-checked) | KILLED | 1; T:870 |

Two gates are each killed by a single control. "F2 `git_blob` location gate removed" is killed only by T:1315, because production paths reach `git_blob` only through the fixed evidence path and the exact E3 path. "E1/E2 `runtime_files` skips `check_exemptions`" is killed only by T:1435, because `active_pins` already checks pins on the CLI path. Both are defense in depth for direct callers.

## Not done or not claimed

- **No production-mode end-to-end run.** The runtime tree, END evidence and committed E3 admissions do not exist yet. Their link counts and their END-namespace exclusion (R6/R7) are unverified.
- **Not re-run:** r2's 33-mutant campaign. Its gates are unchanged except where r3 replaced them: evidence `end/` and the r2 committed-admission rules, which are covered above.
- **Not exercised:** the TOCTOU residual (ancestor replacement between walk and open). It remains the accepted residual and is not claimed as fixed.
- No host access, no SSH, no commits, no pushes. The only new access to T1-owned files on 05 was `stat -c %h` of the three Q6 files. No game file, `games/` directory, outcome `complete.json`, reducer/verifier output or outcome field was opened. The E2 receipt's bytes were not opened by me; only the synthetic stand-ins in the tests were.
