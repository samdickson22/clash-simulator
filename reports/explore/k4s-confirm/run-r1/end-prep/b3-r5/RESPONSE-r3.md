# S4 r4 (b3-r4) response to SOL-REVIEW-END-S2S4-r3 (S4: REQUEST_CHANGES)

**Candidate:** `b3-r4/` (a copy of `b3-r3b/`, which is untouched), written offline on 127x05 on 2026-10-12 from 21:28Z. No SSH, no commit, no push, no host access. `S4:L` is a line of `assemble_fleet_reference.py` in this directory (SHA in `SHA256SUMS`).

**Authority:** SOL-REVIEW-END-S2S4-r3 (all, including "What r4 safe_input adoption must preserve"), SOL-REVIEW-END-PKG1-r2, SOL-REVIEW-END-PKG2-r1; coordinator rulings E1–E3 (16:55Z), E4 (17:12Z), R6/R7 (17:23Z), P2-1..P2-3 (17:30Z), P2-4 (18:03Z), D1–D4 (18:19Z), E5 / full clone / frozen-reader wrapper (21:28Z). Shared layer: `safe-input-r2/safe_input.py` `f9ca4926…`, vendored byte-identical as `safe_input.py`; its README/ADOPTION S4 section is the checklist below.

## S4-R3-F1 (BLOCKING): git indirection under the E4/role gates

| Change | Where |
|---|---|
| r3's `git_run` (inherited env + `GIT_OPTIONAL_LOCKS=0`), `git_blob`, `committed_alias`, `committed_receipts` are deleted. The only git calls are `si.git_run(rev-parse --verify HEAD^{commit})` and `si.git_plan` (which runs `cat-file -t`, `ls-tree -r -l -z --full-tree`, and `cat-file --batch` per planned member, all through `si.git_run`): exact `GIT_FIXED_ENV` + fresh empty HOME, `--no-replace-objects` + `GIT_NO_REPLACE_OBJECTS=1`, hooks/fsmonitor off, transports off, explicit `--git-dir`/`--work-tree`, static refusal of alternates/http-alternates/grafts/shallow/gitfile/undeclared commondir/driver-and-include config/core.worktree; rc checked before stdout; object header type/size and re-hashed OID verified before bytes are returned. | `Committed` `S4:608–660` |
| E3 admissions and the END evidence are read as planned blobs with their expected SHA-256; E1 via `plan.e1_check`; E4 via `plan.hash_e4`. | `S4:748–755`, `S4:822` |
| The layer is loaded from the vendored file through a no-follow single-link descriptor, SHA-256 verified with `hashlib` on the executed bytes, fingerprint pinned; a production run re-checks the fingerprint at planning (in-process edits of E4 values etc. refuse). | `S4:76–114`, `S4:727–728` |

Regression controls (`test_s4_r4_git.py`, through `A.main`): replace refs on the E2 blob and the evidence blob (positive control: raw `cat-file`/`show` return the canary) → the run succeeds with the true bytes and no canary reaches the bundle; inherited `GIT_DIR` (positive control), `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_INDEX_FILE`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT/KEY/VALUE`, `GIT_REPLACE_REF_BASE`, hostile `HOME` and `XDG_CONFIG_HOME` → true bytes; alternates, http-alternates, grafts, shallow, `core.hooksPath`, `core.fsmonitor`, a filter driver, an include, `core.worktree`, a gitfile, an undeclared `commondir` → refused before git runs (`si.GIT_COUNTERS["runs"]` unchanged). The rc-37 behaviour is the layer's `run_checked` (tested there).

## S4-R3-F2 (BLOCKING): receipt-name families

| Change | Where |
|---|---|
| r3's `OUTCOME_DIRS`, six-name `OUTCOME_LEAVES`, `JOB_COMPONENT`, `outcome_free`, `end_namespace_free`, own T1 list, `walk`/`open_confined`/`sha_confined`/`read_confined`/`write_new`/`copy_verified`/`remove_stage` are deleted. Every name passes `si.name_gate` (case-insensitive families on every component, END claims, strict END pair, job components, T1 namespaces). | `location_free` `S4:294`; `Sources` `S4:306–331` |
| All request sources are name-gated (complete path, then `si.Policy` roots, then `si.gate_names` leaves) BEFORE the first input is opened; evidence item names are gated in a pure pass before any artifact is opened; runtime-pin entries are gated before any member is hashed; the runtime walk gates each entry before `lstat`. Declared health names pass. | `S4:306–331`, `S4:832–853`, `S4:531–556` |

Controls: Sol's four names (`END-FINAL.json`, `attempt-00.json`, `end-raw-copy.json`, `complete-v2.json`) and case/prefix/suffix variants (`End-Final.JSON`, `ATTEMPT-01.json`, `End_Raw.json`, `COMPLETE-V2.JSON`, `x-END-JOB.json`, `Hub-Ack.json`, `hub_ack-smoke-0001.json`, `Interference.Json`, `incomplete.json`, `end-complete.json`) as sets, guard freeze and model inputs, with VALID bytes (only the name can refuse): refused, canary inode never opened (audited by the inode of every returned descriptor); variant outcome directories (`GAMES`, `Games.tmp`, `old-games`, `x_games_y`, `Hub-Blocks`, `hub_block`); the same names as runtime inventory names and as evidence artifact names; a forbidden LAST-planned seed refuses with no earlier input opened; legitimate health names still pass (happy path).

## S4-R3-F3 (HIGH): metadata before blobs

| Change | Where |
|---|---|
| `si.git_plan` phase 1 screens the WHOLE HEAD tree to completion (every `complete.json` component: one of the four E4 paths, mode 100644, pinned blob OID `si.E4_GIT_BLOB_OIDS`, member or not; members' names, modes, types; the exact E1 entry) before any object is read; phase 2 reads planned members only. A changed exact-path E4 blob is refused by its OID in phase 1 (the tree OID is bound to approved metadata, as required), and the SHA-256 check still follows in phase 2. | `S4:629`, `S4:647–653` |

Controls: Sol's reproduction (four E4 stand-ins + `zz-outcome/complete.json`) and two variants → refused with **zero** object reads and no `cat-file --batch` call; changed-bytes, mode-755 and symlink E4 entries → refused with zero object reads; non-member outcome blobs (`games/`, `hub-ack.returned.json`, END-FINAL, attempt, end-raw, interference) are never requested; only planned OIDs are. The r3b E4 tests now assert the phase-1 refusal and an unchanged object-read counter.

## "What r4 safe_input adoption must preserve"

| Item | r4 |
|---|---|
| Lexical refusal before access | As F2 above; every `--repository`, `--out`, runtime root, request, synthetic pins, request source and auxiliary name is name-gated before it is touched. |
| Complete role/root validation | One exact role per input; canonical roots (`si.open_root`). |
| regular/nlink at walk and descriptor | `si.walk_tree` (walk) and `si.open_leaf` (fstatat + fstat) on every read; 52-case hard-link matrix (now including the materialised E1 copy). |
| E1 exact committed alias with independently gated target | D2: committed exact link (phase 1 OID) + target blob; shipped regular copy equal to it (`S4:640–660`, `S4:769–770`). |
| E4 four immutable opaque roles and frozen inventory membership | Layer constants; hash only; only E2 a member; frozen `runtime_pins` parity test passes. |
| E3 exact location and stale-identity refusal | Unchanged (`committed_bindings` `S4:662`). |
| Exclusive outputs and plain independent copies | `si.Writer` + `si.copy_input` (0444, `O_EXCL`), re-hashed (`write_bundle` `S4:1007–1044`). |
| Exact artifact bindings, test-only stamps | Unchanged. |
| Status-preserving subprocess handling | `si.run_checked` under every git call. |

## Rulings E1–E5, D1–D4 and the instruction items

- **E1 (D2)** as above. **E4** through the layer (`check_exemptions` requires the pins' map to equal `si.E4_COMPLETE_JSON` in every mode; `S4:393–418`).
- **E5 hook:** `E5_RUNTIME_EXEMPT = {}` (`S4:137`), `PRODUCTION_PINS["e5_runtime_exempt"] = {}`; only synthetic pins can name exact `(path, 40-hex blob OID)` entries (validated: family-named leaf, not E4, not END claim, not strict END). With entries the runtime walk is `walk_runtime_e5` (`S4:438–484`), built from the layer's primitives. Tests: empty list refuses `check_games.py`; an exact entry is accepted (hashed once, manifest + receipt record it); wrong OID, hard link, symlink, neighbour name, non-member, and invalid entries refuse; the production constant is fixed. The 21:28Z ruling's values are not recorded here (instruction: empty this round); see OPEN-QUESTIONS E5.
- **All production reads take expected SHAs:** JSON inputs read once with the request/pin SHA (`pinned_json` `S4:364`), request with `--request-sha256`, S1 runtime pin and qualified binding now pinned (`f81f3655…`, `56b67dd4…`), spec-pins with the measured SHA, admissions and evidence with their SHAs, copies with SHA and size; hash-only inputs compared with request SHAs and the runtime aggregate with `runtime_files_sha256`.
- **D1/D2/D3/D4, R6/R7, full clone, frozen-reader:** DESIGN §G and OPEN-QUESTIONS §r4.

## Intentional behaviour and test changes (r4 stricter or restructured)

1. Refusals made by the layer read `<label>: safe_input refused [<code>]: …`; tests match the code. The tests of removed helpers (`walk`, `open_confined`, `sha_confined`, `read_confined`, `copy_verified`, `git_run`, `git_blob`, `location_free(exception=)`) now exercise the layer through S4's entrypoints.
2. D2: a runtime `visualize_battle.py` symlink refuses (r3 accepted it); the fixture ships a regular copy.
3. The S1 runtime pin is read with its pin; the `runtime-pin.json` fallback is removed; tests that edit the pin list re-pin it.
4. E4 values come from the layer; synthetic E4 bytes are enabled per test by `monkeypatch` of the layer's dicts (restored after each test); production-mode tests restore the real values.
5. Guard-job freshness: the local `os.path.lexists` probe of a target-host path is removed (OPEN-QUESTIONS §r4); the test now asserts no local access to that path.
6. A failed write keeps the `.partial` stage (never deleted); tests assert it is kept, not published, and blocks a later run.
7. The in-process `audited` fixture also wraps `os.open` (inode of every returned descriptor, `dir_fd` resolved): the layer opens relative to directory descriptors, which the `open` audit event cannot resolve; without this, "never opened" checks would have been vacuous for those opens.
8. Frozen consumers run against an exact 43-file `git archive` export of origin/main into `/dev/shm` (not a full worktree), so no outcome-named path is written; the measurement-parity test measures the frozen e4v3 files copied into the World runtime (a full checkout is not a runtime: its e4v3 receipts hold family-named non-members the walk refuses).
9. `test_f1_games_directory_in_runtime_tree_never_descended` renamed (`…outcome_directory…`): pytest's `tmp_path` would contain the `games` token.

## Verification (127x05, 2026-10-12; every number from this session, on the final bytes in `SHA256SUMS`)

| Interpreter | `K4S_FROZEN_ROOT` set, normal | set, `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **449 passed** | **449 passed** (1 warning: pytest's assertion-rewrite notice) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (pytest 9.1.1 from `/dev/shm`) | **449 passed** | **449 passed** (same warning) |

Without `K4S_FROZEN_ROOT` (k4s-freeze, normal): **424 passed, 25 skipped** (the frozen-consumer and real-Q6 tests). 449 = 338 in `test_assemble_fleet_reference.py` + 111 in `test_s4_r4_git.py`. The two `test_production_q6*` tests ran (they read the 353 KB T1 Q6 index on 05, as in r3b). Frozen-consumer subprocesses inherit `-O`. All runs used `nice -n 19`, `-B`, `-p no:cacheprovider`, from `/tmp`.

**Mutation (`mutate_s4_r4.py`, k4s-freeze 3.12.12, `-O`, `-x`, frozen root set, 12 jobs; `MUTATION-RESULTS-r4.json`, finished 22:48:29Z; assembler, layer and test SHAs recorded inside and equal to the final bytes):** **34 of 38 killed**; 0 invalid; 3 NULL controls all SURVIVED. The 4 survivors are declared equivalents:
- `N Sources leaf gate off` (the full-path `si.name_gate` pass covers every leaf first) → `N Sources both gates off JOINT` killed;
- `N --out name gate off` (`si.check_absent(<out>)` gates the same leaf) → `N --out leaf never gated JOINT` killed;
- `N guard job remote gate off` (the leaf is fixed by `JOB_NAME`, which no family matches; the parent is gated when the remote `si.Policy` is built);
- `X E5 walk always used` (the E5 walk has `walk_tree`'s semantics; identical with an empty map).
A first campaign on earlier test bytes (31/37) exposed one real gap (manifest/receipt mode not asserted: added to the happy path, now killed) and one misclassification (a mutant that errors in a fixture is now counted KILLED; documented in the driver).

**Scratch:** frozen export `/dev/shm/k4s-r4-frozen-*` (43 files), mutation copies `/dev/shm/b3r4-mut-*`, pytest under `/tmp/pytest-of-sdicks02`; all removed except pytest's own retention of its last base temps.
