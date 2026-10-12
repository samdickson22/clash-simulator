# K4S END prep: S1b, S3, S9, S10 — CANDIDATES r1 (for Sol review)

- **Status:** candidates only. **Nothing here has touched a host.** I made no ssh and no commit or push, and edited no existing file.
- **Boundary incident (disclosed; reverted).** At 16:50:22–16:50:32Z one mutation-test run disabled the permitted-output-root check. The confinement tests then used real paths, so the mutant created four **new** directories, holding only my own test artifacts, next to the checkout: `/mpac/sdicks02/repos/{s1b,s3,s9,s10}-should-never-exist`. They held synthetic admissions, a git-export runtime copy, a synthetic guard job and a fake-host S10 record. I inspected them, then removed exactly those four paths. Nothing inside `/mpac/sdicks02/repos/clasher` or any other tree was touched, and `git status` is unaffected. The tests now use a throw-away `/dev/shm` directory for "non-permitted" outputs, and test subprocesses run with `cwd=/tmp`. Re-running that mutant afterwards left `/mpac/sdicks02/repos` unchanged.
- **Gate:** S1b and S10 touch hosts. Each needs Sol review and then a coordinator GO (A1/A2) before it runs.
- **Written:** 2026-10-12, ~15:45–16:55Z (`date -u`), on 127x05, by an offline implementer.
- **Sources:** origin/main `caeeecdc`, read through a temporary detached worktree in /tmp that was removed afterwards.
- **Read boundary:**
  - Never opened: any `games/` directory, `complete.json`, reducer or verifier output, or outcome field.
  - T1 trees on 05 were only read: walked by name, and hashed.
- **Inputs read** (origin/main):
  - `end-plan/K4S-END-PLAN-v2.md`
  - `audits/K4S-END-PLAN-REVIEW-r1.md`
  - `end-prep/b3-r1/{DESIGN,OPEN-QUESTIONS}.md` and `assemble_fleet_reference.py`
  - `end-prep/s1s2-r1/{README.md,s1_copy_end_sources.py}`
  - frozen `e4v3/{fleet_validity,prepare_bundle}.py`
  - T1 `parent_source_seed.py`, `system_bus.py`, `idle_services.py`
  - K4S `supervise.py`, `host_audit.py`, `run-r1/tools/round.sh`
  - `mac/k4s_logic.py`, `end_pool.py`
  - `runtime-pin-r2.json`
  - COORDINATOR `fa89baa9` (Q2–Q6 rulings)
  - **`run-r1/reviews/SOL-REVIEW-END-PKG1-r1.md`** (Sol's S1/S2/S4 findings), which landed during this work. Its failure classes were designed out here; see the next section.

| File | Role | Touches hosts |
|---|---|---|
| `end_prep_common.py` | shared helpers: no-follow bounded reads, confined exclusive outputs, a bounded ssh runner | — |
| `s1b_copy_admissions.py` | S1b: exact-path reader for the guard admissions (Q2). A new file beside S1; S1 is unchanged | yes, read-only, **2 logins** |
| `s3_guard_job.py` | S3: per-attempt guard-job builder (RC-3, Q2, Q3, Q4), plus `verify` | no (05 only) |
| `s9_end_runtime.py` | S9: END runtime builder: `locate`, `build`, `verify`, `equivalence` (Q5) | no (05 only) |
| `s10_stage_host.py` | S10: staging of the runtime, the Q6 inputs, the S4 bundles and the S3 guard job onto **one** host | yes, **3 logins** per run |
| `tests/` | offline pytest: fake ssh shim, scratch git clone, real 05 bytes | no |
| `s9-locate-caeeecdc.json` | output of the **real** `locate` run (below) | — |
| `s10-dry-run-EXAMPLE-synthetic-admissions.txt` | an S10 `--dry-run` printout of the three remote scripts (no ssh). Its guard job uses **synthetic** admissions; it is for review only | — |

**Interpreters:**
- The scripts are stdlib-only. Run them with `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B` (3.12.12).
- S3 and S9 run frozen code only in a subprocess, **never with `-O`** (the frozen T1 checks are asserts, live on the hosts), and only **after** stdlib verification of its bytes.
- S1b's remote side runs the host's `/usr/bin/python3 -I -S` (3.8 on Ubuntu 20.04; the program is 3.8-compatible).
- Tests use `/mpac/sdicks02/venvs/k4s-freeze/bin/python`.

---

## How Sol's PKG1 findings are handled here (design, not claims of approval)

| PKG1 finding (class) | Here |
|---|---|
| S2-F1: frozen code imported before its pins are verified, and verifying itself | **S9:** `verify_closure()` runs **before** any import, with stdlib only: the runtime K4S manifest bytes are 74314eda; all 31 files it pins are hashed; the e4v3 measurement inventory is 42b8986d; every module of the import closure (`prepare_bundle`, `tier_backend`, `receipts`, `k4s_logic`) is covered. Only then does the subprocess import them. After import, it refuses if any runtime module outside that closure was loaded. The frozen code is a **cross-check**; S9's own stdlib computation of `runtime_files` must equal it.<br>**S3:** the nine T1 modules are SHA-checked against FROZEN-T1 **before** they are written to a private temp dir and imported; the same post-import closure check applies.<br>Canary tests prove a tampered verifier never executes (`test_closure_verified_before_any_import`, `test_tampered_guard_module_never_executes`) |
| S1-F1: a remote read happens before the type/size/alias gates | **S1b** no longer runs `stat`, `sha256sum` or `cat`. The remote python program walks **every component from `/` with `O_NOFOLLOW`**: a symlinked directory gives ENOTDIR, a symlinked leaf gives ELOOP, and both refuse before any read. It `fstat`s the opened descriptor, refuses a non-regular file or a size outside (0, 1 MiB] **before reading**, then reads exactly that many bytes (growth refuses). A FIFO leaf, a symlinked leaf and a symlinked job directory are tested.<br>**S10:** P and TV check that every ancestor of every target (`/mpac` … the END base, `bundles/`, the guard parent) is a real directory and not a symlink; TV re-checks just before `tar`, one command per line. `find` and `sha256sum` only hash `-type f` entries in the `.partial` trees that S10 itself created |
| S1-F2: local ancestor aliases; non-exclusive writes | Every local output (`--dest`, `--out`, `.partial`, `--json`, `--record`) goes through `confined_new`: absolute, normal, under `/mpac/sdicks02/k4s-runner/` or `/tmp/`, the parent's realpath equals itself, and it must not exist. Every file is created with `O_CREAT\|O_EXCL\|O_NOFOLLOW`. Tests cover symlinked-ancestor and non-permitted outputs (`/mpac/sdicks02/repos/...`) for all four scripts, and assert nothing was created |
| S1-F3: unbounded streams; the cap is checked after hashing | S1b's remote reads are capped before reading; the local ssh output is capped at header + 1 MiB × files. All ssh goes through `run_bounded`: per-stream byte caps (more kills the whole process group and refuses, while still draining so no writer blocks), and a watchdog that kills at the timeout even mid-stream. S10 streams only manifest-listed files, at most size + 1 bytes each, hashed while streaming |
| S1-F4: early refusals leave no receipt | S1b and S10 create their confined `--dest` / `--record` **first**. Every later refusal, including a missing window acknowledgement or a bad commit, writes `S1B-REFUSAL.json` / `S10-REFUSAL.json` (exclusive create). An invalid or aliased destination is refused before anything is created |
| S2-F2 / S4-F1: unconfined inventory names, symlinks in inventories | S9 refuses symlinks and specials anywhere in the built tree before computing `runtime_files`. Every runtime-pin name and K4S pin name passes `safe_rel` (no absolute path, no `..`, no empty part). Pinned JSON inputs (`runtime-pin-r2` f81f3655, qualified binding 56b67dd4, K4S manifest 74314eda) are SHA-checked at the commit. Source roots for `locate` must be real paths (no symlinked root or ancestor), `games/`, `.git/` and `__pycache__/` are pruned, links are never followed, and archives are listed but never opened |
| S4-F2: production inputs not pinned | S10 refuses a bundle unless its `files` pins **equal** the production identities: `v1.pt` d77005d5, `R3a.pt` 37509a43, `R3a-calibration.json` e3003533, `states.pkl` 0addf7c0, `states-rows.json` bcd30777, `states-rows.bin` 8cc2f611. Its guard admissions must be exactly `{system-bus, idle-services}` on 03 and `{system-bus}` on 04. S3 requires 03's idle admission and both identities. Q6 inputs are SHA- and size-pinned constants. **Not done here:** binding the bundle's own-tier `sets` to T1's A3/A5 sets; that remains S4's job (Sol S4-F2) |

---

## Real offline results (05, read-only), final code

### S9 `locate` (real run, 16:51:49Z): **all 33 found, none missing**

```
nice -n 19 $PY -I -B s9_end_runtime.py locate --commit caeeecdccb795b0aa049776d5377ff00190f4b10 \
    --json .../s3s9s10-r1/s9-locate-caeeecdc.json          # exit 0
locate: 33/33 found; missing 0
```

- All 33 come from `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-CANDIDATE-0775b704-0108-r1/runtime/<same path>`. Each is the only same-name candidate, and each matches its `runtime-pin-r2.json` SHA.
- `end-a5-0775b704-0108-r1-shipping/` holds none of them.
- The 13 `.tar` files in `/mpac/sdicks02/k4s-runner/stage/` are listed under `archives_not_searched`.
- The per-file list is in `s9-locate-caeeecdc.json`.

### S9 `build` (real run, 16:51Z, to /tmp scratch, since removed): exit 0 in 6 s

| Item | Value |
|---|---|
| stdlib pre-verification | 31 K4S pins, measurement 42b8986d, closure of 4 modules |
| frozen cross-check | `prepare_bundle.runtime_pins` equals S9's computation; `load_k4s_manifest(74314eda, require_frozen=True)` passes |
| `runtime_files` | 4,127 names, canonical `a2ad99a10e413151878a5681bab79853629ba6f29fcd52f71ffd980b277ee639` |
| `measurement_files` | canonical **`42b8986d…`** |
| tree | 11,554 files (11,521 tracked + 33), 409,700,188 bytes |

These values hold for `caeeecdc` only. The END runtime is built at the commit the coordinator chooses (open point 1).

Informational: against T1's adopted A5 `runtime-files.adopted.json` (3,785 names), ours is a superset. 3,773 names are equal; the other 12 changed in git since then, all under `reports/strategy_council_20260928/imitation/exit-r3/…/operations`.

### Q6 inputs on 05 (hashed 15:49–15:51Z, and again by the S10 dry run at ~16:53Z)

Location: `t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/`.

| File | sha256 | Size (bytes) |
|---|---|---|
| `states.pkl` | `0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1` | 11,649,583,550 |
| `states-rows.json` | `bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5` | 353,160 |
| `states-rows.bin` | `8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb` | 11,651,404,503 |

The same directory also holds `v1.pt` d77005d5, `R3a.pt` 37509a43 and `R3a-calibration.json` e3003533 (all verified), for S4.

### S3 on a scratch `--shared` clone (real FROZEN-T1, real binding commits; **synthetic** admissions)

- `git cat-file -e` passes for b2f9e25e and ce042b97, and for the 08 join commits 0e137378 and 274aed9a.
- For each seed, `git show <c>:<p>` = the checked-out bytes = the binding SHA.
- `git fsck` is clean.
- The repo has no remote, no alternates, no FETCH_HEAD, and no `/mpac/...` path in `.git`.
- **Frozen T1 `committed_binding`** ran for all four bindings, and **`admit()`** ran on a throw-away copy: hosts `[127x03, 127x08, 127x08, None]`, `accepted == []` on 05.
- `repo/` is a depth-1 fetch of exactly the four commits: 63 MB (a full clone is about 491 MB).

---

## S1b — exact-path admission reader (Q2)

**Names, taken from the frozen code:**
- `supervise.py:34` calls `host_audit.admission(j)`, which calls `system_bus.pin(j, …)`, which writes `j/'system-bus-admission.json'`.
- On 03, `round.sh finalize` runs `idle_services.py --job $J`, which writes `j/'idle-services.json'`.
- `J = <root>/<namespace>`.

Exactly these paths are read:

```
127x03  /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/system-bus-admission.json
127x03  /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/idle-services.json
127x04  /mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r4/system-bus-admission.json
```

There is also one lstat probe, of `<root>/k4s-confirm-replacement-r5` (it must be absent). The committed `run-r1/rounds/history.json` must end at r4.

**Logins: 2** (03, then 04). Each is `ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes …` with the command `exec nice -n 19 /usr/bin/python3 -I -S -c <reader> 1048576 <probe> <paths>`.

**Local checks**, in order:
1. Output within its bound.
2. The header names exactly the expected paths.
3. Each piece's recomputed SHA equals the header SHA (transport).
4. No trailing bytes.
5. JSON parses; the `host` field is right.
6. The identity matches the r4 host admissions committed at 14:04Z:
   - dbus: 03 PID 2049 / start 1273, 04 PID 2005 / start 1032, exe `/usr/bin/dbus-daemon`, cmdline f481db68…, uid 103, keys = `system_bus.KEYS`;
   - idle (03): 2180947 / ppid 2180946 / pgid 2180934 / start 139691386 / cmdline 16152ceb… / uid 3822945, the name, 3 wrapper identities.

**Refuses with exit 2.** Every live refusal after `--dest` was accepted leaves only `<dest>/S1B-REFUSAL.json`. Causes:
- an r5 probe hit;
- a missing file;
- a symlinked leaf or directory;
- a non-regular file;
- size outside the bound;
- growth while reading;
- transport corruption;
- trailing bytes;
- an output flood;
- a wrong host field or identity;
- ssh failure or timeout;
- a missing window acknowledgement;
- a bad commit or history.

**Output:** `<dest>/<host>/<name>` (0444) plus `<dest>/s1b-admissions-manifest.json`, holding on-host and local SHAs, sizes, identities, the login argv and UTC, and the script and common SHAs.

```bash
D=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r1; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
git -C /mpac/sdicks02/repos/clasher fetch -q origin; C=$(git -C /mpac/sdicks02/repos/clasher rev-parse origin/main)
nice -n 19 $PY -I -B $D/s1b_copy_admissions.py --commit $C --dry-run          # no ssh, no writes
nice -n 19 $PY -I -B $D/s1b_copy_admissions.py --commit $C \
    --dest /mpac/sdicks02/k4s-runner/run-r1/end-prep/admissions-r1 --outside-end-window "A? GO <ref>, $(date -u +%FT%TZ)"
```

Then (coordinator):
1. Copy `<dest>/<host>/<name>` to `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>`. That is S3's default; confirm the path (open point 3).
2. Secret-scan and commit outcome-blind before the END-JOB. Call that commit **A**.

## S3 — guard-job builder (05 only; 0 logins)

```bash
nice -n 19 $PY -I -B $D/s3_guard_job.py build --host 127x03 --round 00 --attempt 00 --commit <A> \
    --s1b-manifest /mpac/sdicks02/k4s-runner/run-r1/end-prep/admissions-r1/s1b-admissions-manifest.json \
    --out /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-127x03-rd00-a00
nice -n 19 $PY -I -B $D/s3_guard_job.py verify --out <same>
```

**Contents:** `<out>/k4s-end-guard-r1-rd00-a00/`, for the Q4 target `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00` (on 04: `/mpac/sdicks02/jobs-k4s/…`):
- `FROZEN-T1.json` (24817e16);
- `system-bus-admission.json`;
- on 03 only, `idle-services.json`;
- `repo/`.

Nothing else; the top level is checked exactly at build and at verify.

**`repo/` (Q3 Option A):**
- `git init --template=` with an isolated `HOME` and `GIT_CONFIG_NOSYSTEM`;
- `gc.auto=0`, `core.autocrlf=false`;
- a depth-1 `fetch` of the four binding commits from the 05 repository: `file://`, read-only upload-pack, `allowAnySHA1InWant`;
- FETCH_HEAD removed;
- refs `refs/k4s-end/{seed-03,seed-08,join-08-server,join-08-client}`;
- the four seed and join files checked out from their own binding commits, each 0444.

**Order (all before the rename):**
1. Committed inputs:
   - the freeze SHA, its three CONFIRM deltas, `parent_source_seeds` and the 08 `source_join` equal the constants;
   - the nine T1 modules equal the FROZEN-T1 pins;
   - each committed admission passes `check_admission`;
   - with `--s1b-manifest`: committed = S1b local = on-host SHA, and the on-host path is the exact Q2 path.
2. Build.
3. `prove_repo`.
4. The frozen T1 check, on a throw-away copy.
5. Exact top level; inventory (no symlinks or specials).
6. Write the manifest; rename `.partial`. Any failure removes `.partial`.

**`verify`** re-hashes the inventory and re-proves the commits and seed bytes; S10 runs it before shipping.

## S9 — END runtime builder (05 only; 0 logins)

```bash
nice -n 19 $PY -I -B $D/s9_end_runtime.py locate --commit <X> [--json new.json]   # exit 3 if anything is missing: STOP
nice -n 19 $PY -I -B $D/s9_end_runtime.py build  --commit <X> --out /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-<X12>
nice -n 19 $PY -I -B $D/s9_end_runtime.py verify --out <same> --frozen
nice -n 19 $PY -I -B $D/s9_end_runtime.py equivalence --runtime-commit <P> --end-job-commit <X>
```

**`build` steps:**
1. Check `X`:
   - a full 40-hex commit;
   - 133f3ae4 is an ancestor of, or equal to, X;
   - pinned bytes at X: f81f3655, 56b67dd4, 74314eda;
   - the non-git pin names at X = the 33 of record.
2. `locate` (if anything is missing: exit 3).
3. Export every tracked blob of X with `git cat-file --batch`:
   - each blob id is re-checked;
   - this is the content of `git archive X`; the tree has no `.gitattributes`;
   - the one tracked symlink, `visualize_battle.py` → `examples/visualize_battle.py`, is **dereferenced**, as in T1's adopted runtime (sha `85db6809…`; verified).
4. Copy the 33: an O_NOFOLLOW bounded read, SHA re-check, exclusive create.
5. The tree = git + 33 exactly, with no symlinks or specials.
6. S9's own `runtime_files`.
7. `verify_closure()` (stdlib).
8. The frozen cross-check, which must be equal.
9. Files a-w.
10. `runtime-manifest.json`, holding:
    - `runtime_files` and `measurement_files` with their canonical SHAs, computed as `end_reference.shared_bundle_pins` does;
    - externals with their 05 source path;
    - the dereferenced link;
    - `tracked_pin_sha_differs_from_git`;
    - the stdlib and frozen check records;
    - the per-file inventory for S10.
11. Rename `.partial`.

**`equivalence`:**
- P must be an ancestor of X.
- Refuses if any runtime-relevant blob differs between P and X: any `.py`, any runtime-pin name, any K4S-pinned path or the manifest, or anything under e4v3.
- Lists every other changed path.

## S10 — staging onto one host (host-touching; **not run**; 3 logins)

```bash
nice -n 19 $PY -I -B $D/s10_stage_host.py --host 127x03 --runtime <S9 out> --inputs \
    --bundle <S4 bundle 03 rd00-a00> --guard-job <S3 out 03 rd00-a00> --dry-run
nice -n 19 $PY -I -B $D/s10_stage_host.py --host 127x03 --runtime <S9 out> --inputs \
    --bundle <S4 bundle> --guard-job <S3 out> --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-rd00-a00 \
    --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
# a later attempt: only the new bundle + guard job; bundles checked against the staged runtime's manifest
... --bundle <S4 bundle a01> --guard-job <S3 out a01> --runtime-manifest-for-checks <S9 out> ...
```

**Remote layout** (constants; the END bases equal the S5/S6/S7 candidates' `HOST_BASES`):

| Component | 127x03 | 127x04 | After F |
|---|---|---|---|
| runtime | `/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1/runtime-<X12>` | `/mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1/runtime-<X12>` | all a-w (dirs 555) |
| Q6 inputs | `…/k4s-confirm-end-r1/t1-background-inputs/` | same under jobs-k4s | a-w |
| S4 bundles | `…/k4s-confirm-end-r1/bundles/<name>` | same | a-w |
| guard job | `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rdRR-aNN` | `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rdRR-aNN` | job files and 4 seed files 0444; dirs writable (the guard writes side files) |

`check_remote` enforces the remote paths. It accepts only the END base or a Q4 guard job (or a path inside one), and it also refuses these prefixes:
- T1 `jobs/clasher/t1-*`;
- the K4S reporting jobs;
- `/mpac/sdicks02/repos/`;
- on 04: `/mpac/sdicks02/jobs/` and `jobs-k4s/k4s-prep*`.

**Local checks before any login:**
- runtime: `S9.verify`;
- Q6 inputs: O_NOFOLLOW hashing (≈ 2 min for 23 GB) plus sizes;
- bundle:
  - its side SHA file matches;
  - `fleet-reference` profile, host;
  - `guard.job` is in Q4 form;
  - every pinned file present and equal; only `tiers-pins.json`, `tiers-pins.sha256` and `assembly-receipt.json` may be unpinned;
  - **the production pins**;
  - **the per-host admission set**;
  - `runtime_files` and `measurement_files` equal the S9 manifest;
  - if its guard job is staged in the same run: freeze, admission and seed copies **byte-equal** to the guard job's files (what `fleet_validity.check_admissions` re-checks after the claim);
- guard job: `S3.verify`, built for this host;
- all local roots are real paths with no symlinked ancestor.

**Logins:**

| # | Login | Does |
|---|---|---|
| 1 | **P** | hostname; every target and `.partial` absent (`-e` or `-L`); every ancestor not a symlink; the parents are sdicks02 directories; free space ≥ bytes + 50 GiB; tools present; `who` (informational) |
| 2 | **TV** | `set -euo pipefail`, one command per line: hostname; targets absent; ancestors are real directories (`mkdir` of the END base / `bundles` only if missing, then re-checked); `nice -n 19 tar -x -f - -C /mpac/sdicks02 --no-same-owner --keep-old-files` of one stream into new `<target>.partial` directories only; then the full listing plus `sha256sum` of every staged file, and the guard `git cat-file -e` (four commits) and `git show \| sha256sum` (four seeds) |
| 3 | **F** | only after 05 has compared the TV output **exactly**: `chmod`, then `mv -T` each `.partial` into place; then `stat` (dir mode 555 or 755), a writable-entry count (must be 0), the guard git checks again, and `DONE` |

- **Nothing is ever deleted on a host.** A refusal after login P records the exact `.partial` paths in `<record>/S10-REFUSAL.json`; they need a separately authorized cleanup.
- Output: `<record>/s10-staging-manifest.json`, holding:
  - the logins;
  - the P facts;
  - the per-component summaries and full inventories;
  - the TV verification;
  - the F lines;
  - the script, S3, S9 and common SHAs.

**Volume:** about 23.8 GB per host for runtime + inputs + guard job, plus about 23 GB per S4 bundle (bundles embed the states). It goes over the campus LAN.

---

## Tests (offline)

```bash
cd /mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r1
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider tests
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider tests
```

**Results:**
- **119 tests:** S1b 26, S3 30, S9 22, S10 41. Final runs are recorded in the handoff message (3× normally and 2× under `-O` after the last edit).
- One earlier full run had **1 intermittent failure, not reproduced** in later runs. The likely cause: `origin/main` moved during the session, because other threads fetch into the shared checkout, while the real-build fixture and a later test each resolved it. `head()` is now resolved once per session.
- The `-O` warning is pytest's notice about non-test modules. I checked that test-module asserts still fail under `-O` (a dummy `assert 1 == 2` failed).
- The scripts contain no bare `assert`.
- Script subprocesses propagate `-O`; frozen-code subprocesses never use it.

**Fixtures:**
- **Fake ssh** on `PATH`. It logs argv and refuses a login missing BatchMode, ControlMaster=no or ControlPath=none. It runs the command with `bash -c`, with the host's `/mpac/sdicks02` mapped to `<tmp>/hosts/<host>/…` (and mapped back in its output). Hooks: fail at login N, flip a body byte, trailing junk, a 3 MiB flood. Fake `hostname`, `tar` (append-corrupt or same-size flip after extraction) and `chmod` (no-op) are available.
- **Scratch `--shared --no-checkout` clone** of the real 05 repository. Commits are made with plumbing only.
- **One real S9 build** of origin/main from the real 05 sources.

**Coverage per script:**
- **S1b (26):**
  - happy path: 2 logins; every named path ⊆ the 3 files plus the r5 probe; O_NOFOLLOW reader; no `cat`, glob, `find` or `ls`; no `/mpac/sdicks02/jobs/` in the 04 login; decoys never named (`games/complete.json`, the r3 job, 04's perception-root look-alike);
  - dry run;
  - 13 refusals, each leaving only the receipt: r5 exists, missing, symlinked leaf, symlinked job directory, FIFO, wrong host, wrong dbus PID, wrong idle, oversize, flipped body, trailing bytes, flood, ssh failure;
  - window and dest checks with receipts; dest confinement (symlinked ancestor, non-permitted root);
  - history that does not end at r4;
  - 8 `check_admission` units; extra identity key.
- **S3 (30):**
  - 03 contents with an independent git proof, fsck, no remote, alternates or FETCH_HEAD; the frozen admit result; the side file absent;
  - 04 has no idle;
  - S1b cross-check pass plus 2 fails;
  - 5 committed-input refusals;
  - 3 bad targets; 9 `check_target` cases;
  - out or `.partial` exists;
  - verify catches 5 tampers;
  - an extra top-level entry injected during build;
  - **a tampered T1 module never executes** (canary);
  - out confinement;
  - CLI exit code.
- **S9 (22):**
  - **real locate 33/33**;
  - 4 locate misses (exit 3, MISSING, archives listed);
  - a missing pin at build (exit 3, nothing left);
  - pre-133f3ae4 commit; 3 bad commits; out exists;
  - **real build manifest**; verify `--frozen` plus tamper;
  - the frozen `runtime_pins` refuses an incomplete runtime; a changed K4S-pinned file is refused by stdlib;
  - **canaries in `k4s_logic.py` and `prepare_bundle.py` never execute** (verifier no-op'd, `runtime_pins` stubbed);
  - out permitted and symlinked-ancestor cases;
  - a symlinked `locate` root;
  - equivalence (data-only passes; `.py`, pinned `.md`, a runtime-pin name and the reverse order all refuse).
- **S10 (41):**
  - happy path inputs + bundle + guard: 3 logins in P, TV, F order; options; every named path passes `check_remote` or is a tested ancestor; no `rm`, `rmdir` or `unlink`; bytes, modes and git proofs on the "host"; no `.partial` left;
  - **the real 410 MB runtime** shipped to a fake 04 and re-verified with `S9.runtime_files` and `inventory`;
  - dry run;
  - host-side refusals with exact login counts: target exists (1), `.partial` exists (1), disk (1), append corruption (2), same-size flip (2), F failure (3), chmod no-op (3), guard-only chmod no-op (3); a symlinked END base or guard parent is refused at P (1), and the alias target is untouched;
  - 7 bundle refusals before any login (unpinned extra, pin mismatch, wrong host, admission bytes ≠ guard job, runtime mismatch, **non-production model pin**, **03 bundle without idle**);
  - a guard job for the other host; Q6 SHA mismatch;
  - window and record receipts; record confinement;
  - HashingReader;
  - `run_bounded` (cap, timeout, rc);
  - 13 `check_remote` cases; FORBIDDEN with a misconfigured base;
  - a CLI dry run.

**Mutation checks** (under `-O`, on scratch copies in /tmp, since deleted): **17 hand mutants were killed.**
- First batch (7; run on the pre-hardening code, and the checks it targets are unchanged):
  - S10: the on-host SHA compare, FORBIDDEN, disk headroom, WRITABLE;
  - S1b: the dbus identity;
  - S3: the top level at build;
  - S9: the incomplete runtime.
- Hardening batch (10):
  - S9: the closure-pin hash, the closure measurement;
  - common: the realpath ancestor check, the permitted-root check, the flood kill;
  - S10: the P `LINK` refusal, the production pins, the per-host admission set (after its test was isolated from the guard-job equality check);
  - S1b: the body-SHA (transport);
  - S3: the T1 module pin.

Four mutants first survived and were killed only after I added tests: the same-size flip, FORBIDDEN with a base, the build-time extra entry, and the isolated admission set.

Two mutants survive **by construction**, and are kept as defense in depth:
- S10's FINAL dir-mode check: a no-op chmod is also caught by WRITABLE.
- S3's `admit_accepted == []`: on 05 the hostname never matches a seed host.

**Real bugs the tests caught while I wrote this** (all fixed):
- GNU tar 1.30 rejects `--no-overwrite-dir` with `--keep-old-files`; it would have failed TV on the hosts.
- `a && b` under `set -e` did not stop the script.
- An unquoted `echo TOOLS|ok`.
- `$(…)` inside `echo` hid failures.
- Killing only `ssh`'s PID could leave a descendant holding the pipes, so a test hung. `run_bounded` now kills the process group and keeps draining.

---

## Open points for the coordinator and Sol (not decided here)

1. **Q5 wording vs RC-2 order.**
   - The ruling says "runtime built at the END-JOB commit". RC-2 needs the preflight to run "from the final runtime" **before** the END-JOB.
   - S9 builds at any commit at or after 133f3ae4, and `equivalence` proves that a runtime built at P has the same `runtime_files` and K4S-pinned bytes as the END-JOB commit X. It also lists every other changed path.
   - **Ruling needed:** build at P and prove equivalence to X, or restage at X (a new `runtime-<X12>` on both hosts after the END-JOB and before launch).
2. **Preflight guard-job name.**
   - Q4 and the b3 assembler accept only `k4s-end-guard-r1[-rdRR-aNN]`. The S5 preflight needs its own fresh guard job and bundle variant; Sol S4-F2 also asks for distinct preflight jobs.
   - S3 refuses any other name. A naming ruling is needed (e.g. a reserved round) or an assembler delta.
3. **Committed admissions path.** S3 defaults to `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>`; confirm it, or pass `--admissions-dir`.
4. **Inputs vs bundles.**
   - S4 bundles embed `states.pkl` and `states-rows.bin`. If S4 runs on 05, `--inputs` duplicates 23 GB per host.
   - Ship `--inputs` only if S4 is assembled on the host.
   - Per-attempt bundles cost about 23 GB each (P checks free space + 50 GiB).
5. **Not staged by S10:**
   - the native (`44874fd6`);
   - the K4 END corpus (`a97b1fbf`);
   - the `--repository` clone (`$base/repository`, S6/S7);
   - the venv on 03/04 (A3);
   - the own-tier `sets` binding (S4).
6. **Runtime content.**
   - The git export contains 4 committed `complete.json` files from other projects (`imitation/model/receipts/throughput-0935/`, `live-loop/v4/emulator-host/`, two `l1/receipts/b08-*`). S9 never opens them; they are hashed for the inventory and shipped as part of "git content" (Q5).
   - 17 tracked files have a `runtime-pin-r2` SHA that differs from git. S9 uses the git bytes, as T1's adopted A5 runtime did (all 17 checked). They are listed in the manifest.
7. **Guard repo is shallow** (depth 1, four commits, 63 MB, fsck clean; the frozen `committed_binding` and `admit` pass on it). If a full-history clone is preferred (~491 MB per job), only `build_repo` changes.
8. **T1 owner.** The Q6 bytes are read from T1's 05 tree only. The ruling says T1 was notified; A2 lists a T1-owner confirmation.
9. **TOCTOU.** S10's TV re-checks the ancestors just before `tar`; a swap inside that window cannot be excluded by a shell `tar`. Hosts 03/04 are reserved for K4S END (COORDINATOR 16:14Z).

## What cannot be verified offline

- That the admissions exist at the Q2 paths on 03/04 with the r4 identities, and that dbus or the idle service has not restarted since 14:04Z. S1b refuses on any drift.
- That `/usr/bin/python3` exists on 03/04 and that no `/mpac` ancestor there is a symlink (both hold on 05). The O_NOFOLLOW reader and S10's P refuse otherwise.
- Host facts: free space, git version (05: 2.25.1), GNU tar flags (tested with 05's tar 1.30, same OS image), ownership of the parents, the login shell, the `known_hosts` entries.
- Transfer speed on a 23 GB stream, and how long on-host hashing takes under `nice -n 19`.
- Whether the frozen guard on the host accepts the shipped guard job. Offline I ran only `committed_binding` and `admit()` (05 hostname). `ReportingGuard` construction and admission belong to the S5 preflight.
- Nothing ran against real admissions; S3 and S10 tests used synthetic ones.

## Output files (sha256)

The list is in the handoff message: `sha256sum` of every file in this directory, taken at the end.
