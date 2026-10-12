# K4S END prep: S1b, S3, S9, S10 — CANDIDATES r2 (safe_input adoption; package-2 r2 / r4 adoption)

- **Status:** offline candidates for Sol review. **Nothing touched a host:** no ssh, and S1b, S3, S9 and S10 were never run for real. Nothing was committed or pushed. r1 (`../s3s9s10-r1/`) is unchanged; this directory began as a `cp -a` copy of it.
- **Answers:** `run-r1/reviews/SOL-REVIEW-END-PKG2-r1.md` (S1b-F1, S3-F1/F2/F3, S9-F1/F2, S10-F1/F2/F3/F4 and the runner-decision opinions), the "must preserve" list of `SOL-REVIEW-END-S2S4-r3.md`, the S1b/S3/S9/S10 rows of `safe-input-r3/ADOPTION.md`, and the coordinator rulings from 2026-10-12 15:41Z onward (Q2–Q6, E1–E5, R6/R7, P2-1…P2-4, D1–D4, full clone, frozen-reader interim; origin/main 27b54d9d). **`RESPONSE-r1.md`** maps each finding to its change (file:line) and its regression test.
- **Written:** 2026-10-12, on 127x05, by an offline implementer. The resume log is `../r4-s3s9s10-PROGRESS.md`.

## safe_input pin

`safe_input.py` is vendored **byte-identical from `safe-input-r3/`**: sha256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`. r3 is r2 plus ruling E5. Before adopting it I checked two things:

- `safe-input-r3/PROGRESS-r3.md` says DONE (M8, 21:52:58Z);
- `sha256sum -c safe-input-r3/SHA256SUMS` passes for all 26 files.

Development and the first mutation campaign ran against r2 (`f9ca4926…`). After the switch, every test and both mutation campaigns were re-run on r3.

`end_prep_common.py` loads the layer as follows:
1. open `safe_input.py` with O_NOFOLLOW; it must be a regular file with st_nlink 1;
2. read it exactly and check its SHA-256 with stdlib `hashlib`;
3. execute exactly those verified bytes (it is never re-imported from disk);
4. require `constants_fingerprint()` = `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`;
5. require the shipped reader program = `2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`;
6. require the shipped receive program = `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`.

**The receive-program SHA differs from r3's README.** r3 README §8 prints `979b37a1…`. The pinned r3 bytes produce `39a92e9d…` under both /usr/bin/python3 3.8.10 and k4s-freeze 3.12.12, and no r3 test pins the receive SHA. The other two values match the README. I pinned what the bytes produce; the r3 README needs a correction.

Remote programs ship exactly as safe_input provides them: `si.remote_check` (reader) and `si.remote_receive` (receive, with its SHA-256 checked by the bootstrap on the host).

## Files

| File | Role | Touches hosts |
|---|---|---|
| `safe_input.py` | the vendored r3 layer (unchanged) | — |
| `end_prep_common.py` | the pinned safe_input load; output confinement; `publish_dir` (renameat2 RENAME_NOREPLACE); `unlink_own`/`chmod_readonly` on gated fds; `Record`; `ScrubbedEnv` (P2-4 env for frozen children) | — |
| `s1b_copy_admissions.py` | S1b: the three admissions through the pinned reader, written in E3 layout | yes, read-only, **2 logins** |
| `s3_guard_job.py` | S3: guard job builder/verifier (`-rdRR-aNN` and `-pfNN`) | no |
| `s9_end_runtime.py` | S9: `prepare-clone`, `locate`, `build`, `verify`, `equivalence` | no (network clone from GitHub only) |
| `s10_stage_host.py` | S10: stages runtime / bundles / guard job onto one host; `--print-roots` | yes, 4 + N logins (+1 with `--create-base`) |
| `RC6-ROOTS-DRAFT.json` | RC-6 roots declaration draft (`s10_stage_host.py --print-roots`) | — |
| `RESPONSE-r1.md` | finding → change → test | — |
| `tests/` | offline pytest suite (synthetic world, namespaced fake hosts) + `mutate.py` | no |
| `MUTATION-RESULTS-r3-py312-O.json`, `MUTATION-RESULTS-r3-py38-O.json` | final mutation campaigns (r3 pin) | — |
| `SHA256SUMS` | every file above | — |

r1-only artifacts were dropped: `RUNNER-PATCH-E3.diff`, `s9-locate-caeeecdc.json`, `s10-dry-run-EXAMPLE-synthetic-admissions.txt`, and the r1 tests. `--inputs`, `--admissions-dir`, `--source` and `--ssh` are gone.

Run everything on 127x05 with `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B` (3.12, stdlib only). The code is Python 3.8-compatible, and the suite also runs on /usr/bin/python3 3.8.10. Frozen children (S3, S9) are never run with `-O`. Every SHA argument below is printed by the previous step.

## S1b — admissions (Q2, E3; S1b-F1)

```bash
D=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r2; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
nice -n 19 $PY -I -B $D/s1b_copy_admissions.py --commit <C with history.json 94ee52e0> --dry-run
nice -n 19 $PY -I -B $D/s1b_copy_admissions.py --commit <C> --dest /mpac/sdicks02/k4s-runner/run-r1/end-prep/admissions-r2 \
    --outside-end-window "<GO ref>, $(date -u +%FT%TZ)"
```

- It reads exactly these paths, with no listing and no glob:
  - 03: `…/jobs/clasher/k4s-confirm-replacement-r4/{system-bus-admission.json, idle-services.json}`
  - 04: `…/jobs-k4s/k4s-confirm-replacement-r4/system-bus-admission.json`

  It also probes that `…/k4s-confirm-replacement-r5` is absent.
- **One `si.remote_check` login per host.** The host program:
  1. name-gates every item;
  2. checks the node name;
  3. walks every component with O_NOFOLLOW;
  4. requires each leaf to be regular, **`st_nlink == 1`** and at most 1 MiB, before any byte of any item is read.

  Locally, `parse_remote_response` re-validates everything. After the reads come the pinned r4 identities (strict JSON) and the pinned `history.json` (94ee52e0, read through `si.git_show_file`).
- **Output, written exclusively:**
  - `<dest>/end-guard-admissions/<host>-<name>`: the exact E3 layout, to be copied unchanged to `reports/explore/k4s-confirm/end-guard-admissions/`, secret-scanned and committed outcome-blind before the evidence commit P;
  - `<dest>/s1b-admissions-manifest.json`, recording each file's on-host SHA and nlink, and the reader program SHA.

  Every refusal after `<dest>` exists leaves `S1B-REFUSAL-*.json`.

## S3 — guard job (Q2/Q3/Q4; S3-F1/F2/F3)

```bash
nice -n 19 $PY -I -B $D/s3_guard_job.py build --host 127x03 --round 00 --attempt 00 --commit <P> \
    --s1b-manifest <dest>/s1b-admissions-manifest.json --s1b-manifest-sha256 <S> \
    --out /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-127x03-rd00-a00
nice -n 19 $PY -I -B $D/s3_guard_job.py build --host 127x04 --preflight 00 ...        # k4s-end-guard-r1-pf00
nice -n 19 $PY -I -B $D/s3_guard_job.py verify --out <out> --job <job name> --manifest-sha256 <S>
```

- **Source.** The source is the runner-owned full clone (`REPO_FULL`), read only through `si.git_show_file` with expected SHAs:
  - FROZEN-T1 24817e16;
  - the nine modules (pinned by the freeze);
  - the 08 seed receipt;
  - the admissions, **only at the exact E3 paths**. Their expected SHA is the S1b on-host SHA, and the S1b row must be single-link at the exact Q2 path.
- **`repo/` (Q3)** is a K4S-owned **shallow** repository holding exactly the four seed/join commits:
  1. `si.git_run init --template=`;
  2. a depth-1 fetch by SHA over the file protocol only, from the full clone (upload-pack `allowAnySHA1InWant`);
  3. our own `FETCH_HEAD` unlinked;
  4. loose refs `refs/k4s-end/<label>`;
  5. the seeds checked out at their binding commits, 0444.

  It is proved by `cat-file -e` ×4, by git bytes == work-tree bytes == the binding SHA, by exact refs, by a core-only config, by FETCH_HEAD being absent, and by `is-shallow`.
- **Frozen check.** The frozen T1 `committed_binding` and `admit()` run on a throw-away copy. The child gets the P2-4 environment, and the copy's repository has passed the safe_input preflight. The child is never run with `-O`.
- **Output.** `<out>/<job>/` and `<out>/guard-job-manifest.json` (inventory, dirs). Built in `<out>.partial` and published without clobbering.
- **verify** re-walks and re-hashes everything through roles; the manifest is pinned.

## S9 — END runtime (Q5, D1, D2, E1–E5, R6, P2-2, full clone)

```bash
nice -n 19 $PY -I -B $D/s9_end_runtime.py prepare-clone --commit <P>                  # creates repo-full (GitHub, https)
nice -n 19 $PY -I -B $D/s9_end_runtime.py locate --commit <P> --record <new dir>      # exit 3 = missing pins: STOP
nice -n 19 $PY -I -B $D/s9_end_runtime.py build  --commit <P> --out /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-<P12>
nice -n 19 $PY -I -B $D/s9_end_runtime.py verify --out <out> --manifest-sha256 <S> --frozen --record <new dir>
nice -n 19 $PY -I -B $D/s9_end_runtime.py equivalence --out <out> --manifest-sha256 <S> --end-job-commit <X> --record <new dir>
```

- **`prepare-clone`** creates `/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full`:
  1. `git clone --no-checkout --template=` from `https://github.com/samdickson22/clash-simulator.git`, with no filter, the P2-4 environment, hooks disabled, `transfer.fsckObjects`, and only https enabled;
  2. verification through safe_input: an exact config key allowlist (no promisor, partialclonefilter, extensions, drivers or includes), no hooks dir, no `.promisor` pack, not shallow, no replace refs, no alternates or grafts (`_git_preflight`), and P present;
  3. `checkout --detach P` and a clean status;
  4. a receipt, `repo-full-PREPARE.json`.

  This is the only git invocation outside `si.git_run`, because `git_run` disables every network transport. I did **not** run it for real, because creating the real `repo-full` is outside this directory. The tests run it against a file:// origin.
- **`build` (at the evidence commit P):**
  - R6: the strict `reports/explore/k4s-confirm/end/` must be absent at P.
  - The pins at P are checked: f81f3655, 56b67dd4, 74314eda, and the 33 non-git names of record.
  - The 33 externals are located **only at exact paths** under the one explicit Q5 source, `t1-20261010-r1/end-a5-CANDIDATE-0775b704-0108-r1/runtime/<name>` (r1 found 33/33 there; there is no walk and no `--source`). Any refusal or mismatch is a STOP, exit 3.
  - **D1 export via `si.git_plan`.** Membership is decided from tree metadata only: **runtime-pin-r2 files ∪ every `*.py` ∪ the six `SUPPORT_MEMBERS`** (RESPONSE "Deviation 1"). Phase 1 screens the whole tree before any object read:
    - E4 fail-closed for every `complete.json`;
    - for members: the family denylist, modes, the exact E1 entry, and E5 by exact path and blob OID.

    Non-members are never read. E1 is materialised (D2). E4 entries are hash-only (pinned SHA-256). E5 entries are opaque (pinned blob OID) and written 0444.
  - The externals are copied as exclusive, plain, single-link copies with their pins (R7).
  - The whole tree is re-walked and re-hashed through roles, with E4 via `hash_e4` and E5 via `hash_e5`.
  - Stdlib checks run before any frozen import: runtime_files, the qualified sources, the K4S pins, the measurement inventory 42b8986d, and the import closure. Then the frozen cross-check runs (P2-4 env, never `-O`) and must be equal.
  - Output: `runtime-manifest.json` with `git_members` (path, mode, OID) for P2-2. Built in `.partial` and published without clobbering.
- **`equivalence` (P2-2 hard gate):**
  - X must be a strict descendant of P.
  - `diff-tree P X` must name exactly `reports/explore/k4s-confirm/end/END-JOB.json`; names only, the blob is never read.
  - At X, END-JOB must be a 100644 blob and the only END entry.
  - runtime-pin must be equal at P and X.
  - The member plans at P and X must be identical (path, mode, OID) and equal to the built manifest's `git_members`. This proves runtime_files and measurement_files are identical.

## S10 — staging onto one host (A2; S10-F1/F2/F3/F4, D4, R7)

```bash
nice -n 19 $PY -I -B $D/s10_stage_host.py --print-roots                               # RC-6 draft (JSON)
nice -n 19 $PY -I -B $D/s10_stage_host.py --host 127x03 --create-base \
    --runtime <S9 out> --runtime-manifest-sha256 <S> \
    --bundle <S4 bundle dir> <tiers-pins SHA> <assembly-receipt SHA> \
    --guard-job <S3 out> --guard-job-name k4s-end-guard-r1-rd00-a00 --guard-manifest-sha256 <S> \
    --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-r1 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
# later attempts: --runtime-manifest-for-checks <S9 out> --runtime-manifest-sha256 <S> --bundle ... --guard-job ...
```

**Roots (RC-6; `RC6-ROOTS-DRAFT.json`).** `<base>` = `/mpac/sdicks02/jobs/clasher/k4s-end-r1` on 03 and `/mpac/sdicks02/jobs-k4s/k4s-end-r1` on 04 (`si.END_BASES`, the same as S5/S6/S7). It holds:

| Directory | Contents | Created by |
|---|---|---|
| `runtime/runtime-<P12>/` | the runtime, a-w | S10 |
| `bundles/<name>/` | bundles, a-w | S10 |
| `attempts/` | END attempts | dir: S10 (`--create-base`); contents: S7 |
| `preflight/` | preflights | dir: S10 (`--create-base`); contents: S7 |
| `repository/` | the `--repository` clone | its own authorized step |

Guard jobs go to the **separate** Q4 parent: `/mpac/sdicks02/jobs/clasher/` on 03 and `/mpac/sdicks02/jobs-k4s/` on 04, as `k4s-end-guard-r1-rdRR-aNN` or `-pfNN`, with writable dirs.

**Before any login.** The record dir is created first. Then every local input is read through a role with an expected SHA:
- S9.verify;
- S3.verify;
- per bundle:
  - the S4 test-only refusal: the `k4s_s4_synthetic` key, the `SYNTHETIC-TEST-ONLY` stamp anywhere, `production_pins` not true, a `*synthetic*` name, receipt status/schema/host/manifest binding;
  - every file hashed and equal to its pin;
  - the production identities (models, Q6 state bytes);
  - the per-host admissions;
  - runtime/measurement consistency with the staged runtime (mandatory);
  - guard-byte equality when its guard job is staged too.

There is no `--inputs`: bundles only.

**Logins** (4, plus one per component, plus one with `--create-base`; all recorded):

| Login | Does |
|---|---|
| P-check | `si.remote_check`: the base and its four subdirs (or, with `--create-base`, base absent) and the Q4 parent are canonical directories, with every ancestor lstat'ed; every target and every `.partial` is absent |
| P-facts | hostname, df and who, each `x=$(cmd)` with its own echoed status; any nonzero status refuses before its output is used; free space ≥ bytes + 50 GiB |
| [base] | `--create-base` only: a receive that creates `<base>` exclusively with attempts/, preflight/, runtime/, bundles/ |
| R-*i* | one `si.remote_receive` per component (D4); see below |
| F | one session: the reader re-checks every `.partial` is a canonical dir and every final is absent; then `chmod -R a-w` (runtime/bundles) and `mv -n -T`, with every step's status echoed and checked |
| POST | `si.remote_check`: every final has the dev/ino the F check saw for its `.partial`; a-w (or a writable guard dir); the `.partial` is absent |

Each R-*i* receive:
- creates `<target>.partial` exclusively under its canonical parent;
- creates directories with mkdirat, and files with O_CREAT|O_EXCL|O_NOFOLLOW, streamed, hashed, fsynced, mode 0444/0555;
- re-checks E4 SHA pins and E5 blob OIDs on the host;
- returns a strict receipt with size, SHA, nlink == 1 and mode for every file (R7).

Nothing is ever deleted on a host. A refusal after the first receive lists the exact paths created or attempted (`host_paths_created_or_attempted_needing_authorized_cleanup`) in `S10-REFUSAL-*.json`.

## Tests (offline, synthetic only)

`tests/conftest.py` builds a synthetic world in one `tempfile` directory under `/tmp` (neutral names, removed at the end):
- a synthetic origin repository (branch `main`) with the production paths for the pin lists, the K4S manifest, e4v3, the E1 link, an E5 stand-in (`scripts/compare_native_public_games.py`, with only its OID patched as r3's own tests do), FROZEN-T1, the T1 modules, seed/join commits, history.json, the E3 admissions (commit P) and END-JOB (commit X);
- synthetic frozen modules that implement the frozen rules;
- the full clone, created by **`S9 prepare-clone`** itself from a `file://` origin.

Constants that bind production bytes (pins, commits, REPO_FULL, Q5_SOURCE, PRODUCTION_PINS) are patched for the session only; `ORIG` keeps the production values, and tests check them.

**Fake hosts.** A fake `ssh` runs the remote words under `/bin/sh` in a **user+mount+UTS namespace** (`unshare -Urmu`): `/mpac/sdicks02` is a bind mount of a temp tree, and the hostname is the target host. The shipped safe_input programs run **unmodified**, including their node-name check, and the real `/mpac/sdicks02` is invisible to them. The fake can inject faults: a refused login, trailing junk, a flipped base64 byte, and fake tools.

No test reads a real repository, a T1 tree, a game or receipt file, or a host. Tests write only under tempfile directories in `/tmp`. Mutation copies live in `/dev/shm`, and the confinement probes name `/dev/shm/k4s-*-never` paths.

| Interpreter | Normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 (pytest 9.1.1) | **211 passed** (105.6 s) | **211 passed** (122 s; 1 warning) |
| `/usr/bin/python3` 3.8.10 (pytest 8.3.5 from `/dev/shm/s3s9s10r2-pytest38`) | **211 passed** (62.9 s) | **211 passed** (86.7 s; 1 warning) |

These are the final runs, 2026-10-12 22:34–22:41Z, on the final sources (r3 pin). The only `-O` warning is pytest's `PytestConfigWarning` about assertions in non-test modules. The tests use explicit `ok()`/`refused()` checks, never `assert`. Wall times were longer than in earlier runs (about 37 s) because 05 was also running the S2/S4 r4 mutation campaigns (load ≈ 16).

Per file (collected): common 29, flow 5, S1b 27, S3 42, S9 53, S10 55 = 211.

Commands: `cd /tmp && PYTHONDONTWRITEBYTECODE=1 nice -n 19 PY -B [-O] -m pytest -q -p no:cacheprovider $D/tests`. For 3.8, add `PYTHONPATH=/dev/shm/s3s9s10r2-pytest38`.

**Sol's probes as regression tests:**

| Probe | Test |
|---|---|
| hard-linked admission (S1b-F1) | `test_s1b.py::test_probe_hard_linked_admission_refused_before_any_read` |
| admissions under `end/receipts/reviewer`; S1b manifest at an END location (S3-F1) | `test_s3.py::test_probe_admissions_only_under_end_receipts_refused`, `…s1b_manifest_in_end_location…` |
| hard-link / symlink / games inputs to verify (S3-F2) | `test_s3.py::test_probe_verify_refuses_aliases_and_tampering` |
| S9 export with `games/` and an unlisted `complete.json` (S9-F1) | `test_s9.py::test_probe_export_never_reads_non_members`, `…family_names_refused_in_phase_one` |
| Q5 root at `end/receipts`; hard-linked external (S9-F2) | `test_s9.py::test_probe_q5_source_in_a_forbidden_location`, `…hard_linked_external_is_not_located` |
| hard-link / games / ancestor-alias in S10 and the aux manifest (S10-F1) | `test_s10.py::test_bundle_refusals_before_any_login`, `…aux_runtime_manifest_is_role_gated` |
| base symlinked to a foreign dir | `test_s10.py::test_probe_base_symlinked_to_a_foreign_dir` |
| failed probe / subprocess with valid stdout (S10-F3, S7-F2 class) | `test_s10.py::test_probe_facts_status_is_never_masked`; S3/S9 `…frozen_check_nonzero_with_valid_stdout_refused` |
| argv-style truncation through a pre-existing hard link (S6-F2 class) | `test_s10.py::test_probe_pre_existing_targets_are_never_written` |
| GIT_* env / replace refs / alternates / grafts / hooks / include / filter / gitfile | `test_s3.py::test_git_replace_ref_and_env…`, `…repository_indirection_refused`; `test_s9.py::test_git_env_and_replace_refs…`, `…build_refuses_repository_indirection`, `…full_clone_verification_refuses`; `test_s1b.py::test_git_env_indirection…` |
| S4 test-only bundle (S10-F4) | `test_s10.py::test_bundle_refusals_before_any_login[synthetic-*, stamp-in-field, receipt-*]` |

## Mutation check (adoption points, under -O)

`tests/mutate.py` defines 82 single-edit mutants, and `--check-edits` validates that each target occurs exactly once. For each mutant it:
1. copies the code, tests and RC-6 file into a fresh `/dev/shm/s3s9s10-mut-*` directory (removed afterwards);
2. runs the whole suite with `-x` and `-O`, with cwd `/tmp`;
3. records KILLED when the suite fails.

NULL controls (unmodified copies) are interleaved and must SURVIVE. Snapshots of `/mpac/sdicks02`, `…/repos` and `…/k4s-runner`, taken before and after, must be equal: no write outside `/tmp` and `/dev/shm`.

**Final campaigns (r3 pin; the sources' SHA-256 values are recorded in each JSON and equal `SHA256SUMS`):**

| Interpreter, `-O` | Killed | Not killed | NULL controls | Writes outside /tmp and /dev/shm | Leftovers |
|---|---:|---|---|---|---|
| k4s-freeze 3.12.12 | **80/82** | N20, X17 | 4/4 survived | none | none |
| /usr/bin/python3 3.8.10 | **80/82** | N20, X17 | 4/4 survived | none | none |

The two not killed are documented as **equivalent** in `mutate.py` `EQUIVALENT`, because a stronger independent layer masks each one, and the suite exercises that layer:
- **N20**, the complete-runtime check: the frozen `runtime_pins` cross-check runs on every build and refuses the same incomplete runtime.
- **X17**, the tiers-pins expected SHA: a changed `tiers-pins.json` is also refused by the side-file read, whose expected SHA is derived from the operator's tiers SHA, and by the receipt's `manifest_sha256` binding.

**Campaign history:**
1. **Run 1, r2 pin: void.** The copy omitted `RC6-ROOTS-DRAFT.json`, so all 4 NULL controls failed, and every kill was an artefact. I fixed the driver.
2. **Run 2, r2 pin, 3.12 `-O`: 70/77 killed, NULLs 4/4 survived.** It left seven survivors:
   - C04, T13, X12, X15 and X21 were real test gaps. I added `test_wrong_layer_pins_refuse_the_import`, `test_frozen_admit_must_accept_nothing_on_05`, `test_base_subdirectory_missing_refused_at_p[attempts|preflight]`, `test_parse_f_requires_every_step_status` and `test_bundle_guard_bytes_must_equal_the_staged_guard_job`.
   - N20 and X17 are the equivalents above.
3. **r3 switch.** Five E5 adoption mutants were added: N21, N22, N23, X23, X24. A targeted run killed C04, T13, T17, X12, X15, X21 and all five E5 mutants.
4. **Final campaigns:** the two runs in the table above.

## Deviations, residuals, and what cannot be verified offline

See RESPONSE-r1.md "Deviations and decisions to confirm" (D1 support members; the one clone outside `git_run`; S3's own FETCH_HEAD unlink; loose refs / no `gc.auto`; receipt-based on-host verification; reads of own outputs; S1b's identity-bound fresh copies; the reader's lack of E5 support).

- **Accepted residual (16:00Z).** Concurrent replacement between a check and its use, including the F reader-to-`mv` window.
- **Not verified offline:**
  - the real hosts: python3 3.8 at `/usr/bin/python3`, the login shell, ancestors, free space, `known_hosts`;
  - real admissions and their r4 identities;
  - the real full clone and a real build at the real P. Under r2 the D5 names refused; under r3, E5 is expected to accept them (r3's D1 re-run at 02805c97 found 0 member refusals). This was not re-run here, because it would need the real repo-full;
  - transfer speed for about 23 GB per bundle;
  - whether the frozen guard on a host accepts the shipped guard job (that is S5's preflight).
- **Never touched:** real `games/`, `complete.json`, outcome, reducer or verifier files. The only real-repository reads were:
  - tree metadata at origin/main (names and OIDs);
  - `runtime-pin-r2.json` and `K4S-MAC-MANIFEST.json` through `si.git_show_file` with their pinned SHAs, to size D1;
  - `run-r1/rounds/history.json` (health metadata: namespaces and dispatch; S1 reads it too), to pin its SHA;
  - names-only `git grep`/`git show` of code.

  I listed two T1 directory top levels on 05 by name only, to make Q5 provenance explicit.
