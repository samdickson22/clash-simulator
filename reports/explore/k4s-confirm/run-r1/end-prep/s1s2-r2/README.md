# K4S END prep: S1 (B2 exact-path copier) and S2 (END evidence builder, offline validator, clock diagnosis): CANDIDATES r2

**Status:** these are round-2 candidates for Sol review. They answer `run-r1/reviews/SOL-REVIEW-END-PKG1-r1.md` (S1 and S2 only; S4 is a separate package). The mapping from each finding to its change is in `RESPONSE-r1.md`.

- Nothing here has been run against a host. Writing this round made no ssh connection, no commit and no push.
- It was authored on 127x05 from the r1 copy (`s1s2-r1/`, unchanged), against origin/main as fetched at 2026-10-12 ~16:00–16:35Z (`1aa63a16` → `2510ff14`). The frozen bytes the tests use are pinned by the K4S manifest, so they do not depend on which commit was fetched.

| File | Role |
|---|---|
| `s1_copy_end_sources.py` | S1: run from 05; reads 03 and 04 read-only over ssh. Stdlib only |
| `s2_end_evidence.py` | S2: `build` / `validate` / `diagnose-clock`. 05 only, no ssh. Stdlib, plus the frozen code once it has been verified |
| `tests/conftest.py`, `tests/test_s1.py`, `tests/test_s2.py`, `tests/audit_run.py` | Offline pytest: a fake ssh shim, a synthetic git repository and an audit-hook recorder |
| `RESPONSE-r1.md` | Each review finding → its change (file:line) or the justification |

**Coordinator scope ruling.** These are single-operator hosts with no adversarial process. Concurrent replacement between a check and the following open (TOCTOU) is an **accepted residual**, as in X4S-3; the full list of residuals is under "Residuals (accepted / stated)" below. Everything else in the review is addressed.

## S1: B2 exact-path copier (r2)

**What it names.** S1 names 10 fixed phase directories. The namespace comes from the committed `run-r1/rounds/history.json`, which is cross-checked against a constant table:

- 127x03: `/mpac/sdicks02/jobs/clasher/k4s-confirm-<…>/<phase>/`
- 127x04: `/mpac/sdicks02/jobs-k4s/k4s-confirm-<…>/<phase>/`

Nothing under 04's `/mpac/sdicks02/jobs/` (the perception storage) is ever named. In each phase directory exactly four full literal paths are named: `launch.json`, `supervisor-exit.json`, `mhz.jsonl` and `census.jsonl`. There is no glob, no listing and no recursion.

**Remote side (new in r2; S1-F1, S1-F3).** The only remote program is the host's own `/usr/bin/python3 -I -S -c REMOTE_PROGRAM` (`s1_copy_end_sources.py:132-206`). It uses the stdlib only, opens files O_RDONLY only and never writes. It runs under `nice -n 19`.

Per named path, the program does the following:

1. It opens the path **component by component from `/`**. Directories are opened with `O_DIRECTORY|O_NOFOLLOW`, the leaf with `O_NOFOLLOW|O_NONBLOCK`. A symlinked leaf **or ancestor** fails with ELOOP/ENOTDIR and is never resolved by the kernel. A FIFO cannot block.
2. On the opened descriptor, **before any byte is read**, it requires:
   - a regular file;
   - `st_nlink == 1` (no hard-link alias);
   - the size gate. For `launch.json` and `supervisor-exit.json`, the size must be **exactly the committed phase-meta size**; the committed maximum is 1,045,522 B. For `mhz.jsonl` and `census.jsonl`, the size must be **1 .. 95 MiB** (99,614,720 B).

   The 95 MiB cap therefore covers all four files: every committed launch/exit is under 1.1 MB, so no launch or exit file legitimately needs more.
3. **Every gate of every file passes before any file is hashed or streamed.**
4. Hashing and streaming read **the gated descriptor itself**, with no re-open. They read exactly `st_size` bytes and then require EOF, so growth during the read is refused.

**Logins: 6 in total, 3 per host (unchanged).**

| # | Login | Remote | 05 checks |
|---|---|---|---|
| 1 | P 127x03 | `inspect` the 20 paths: gates first, then sha256 | launch/exit SHA == committed. The committed SHA == the constant table == completion-v2 `supervisor_exits` |
| 2 | P 127x04 | same | same. **Nothing is copied unless P passed on both hosts** |
| 3 | C 127x03 | `stream` the 10 mhz/census files. First it re-opens and re-gates all 10, requiring size, `st_dev` and `st_ino` == login P, and **refuses before writing one byte** if any changed | 05 reads **exactly the sum of the P sizes**, written straight into per-file `O_CREAT\|O_EXCL\|O_NOFOLLOW` files. It then reads **one more byte**: any excess byte kills the login and refuses. Each piece's SHA must equal P's, and is checked again by re-reading the local file |
| 4 | V 127x03 | `inspect` again | size, SHA, device and inode unchanged since P. mhz/census SHA == the local SHA |
| 5–6 | C, V 127x04 | as above | as above |

Every login has: `-T`, `BatchMode=yes`, `ControlMaster=no`, `ControlPath=none`, `StrictHostKeyChecking=yes`, `ConnectTimeout=20`, `ServerAliveInterval=15`, `ServerAliveCountMax=4`, `ClearAllForwardings=yes` and `RequestTTY=no`.

Bounds on every login:
- stdin is `/dev/null`;
- the inspect output is capped at 64 KiB;
- only the last 4 KiB of stderr is kept;
- a hard timeout kills the process: 900 s for P and V, 3600 s for C.

Production requires `ssh` to resolve to `/usr/bin/ssh`.

**Local side on 05 (S1-F2).**
- `--dest` must be:
  - absolute and normalised;
  - **canonical**: `realpath == path`, and every component is opened `O_NOFOLLOW` from `/`;
  - strictly below `DEST_ROOT = /mpac/sdicks02/k4s-runner/run-r1/end-prep`;
  - **non-existent**.
- All of this is checked before any login. The parent's descriptor is retained.
- dest is created with `mkdirat` after both P logins pass. Every directory and file below it is created **relative to the retained descriptors**, with `O_EXCL|O_NOFOLLOW`. That includes the 20 copies, `s1-copy-manifest.json` and `S1-REFUSAL.json`.
- Before the manifest is written, the tree is listed through the descriptor (`fwalk`, no follow). It must hold exactly the 20 files, all regular with nlink 1.

**Output.** S1 writes `<dest>/<host>/<phase>/{mhz.jsonl,census.jsonl}` and `<dest>/s1-copy-manifest.json`, schema `clasher.k4s.end-sources-copy.v2`. The manifest adds the following to r1's fields:
- the on-host device/inode of every file;
- the committed sizes;
- `remote_program_sha256` and `remote_python`;
- `dest_identity`.

**Refusals (S1-F4).** **Every** refusal or failure writes a receipt, `REFUSAL_DIR/S1-REFUSAL-<utc>-<pid>-<random>.json`, exclusive and no-follow, where:

- `REFUSAL_DIR` is fixed: **`/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1-refusals/`**;
- it must be canonical, and is created if missing;
- every argument error is a refusal too (`Parser.error`).

If this run created dest, a copy is also written to `<dest>/S1-REFUSAL.json`. A receipt is never written anywhere else: if `REFUSAL_DIR` is aliased, S1 prints `RECEIPT NOT WRITTEN` and still refuses.

Exit codes: 2 = refusal, 1 = unexpected error. Both write a receipt. **No success manifest is ever written on failure.** Partial copies are preserved and listed in the receipt; never commit a refused tree.

S1 refuses on any of these:
- **Arguments:** an argument error; `--dest` missing on a live run; `--outside-end-window` missing.
- **Destination:** `--dest` exists, is non-canonical or aliased, or lies outside `DEST_ROOT`.
- **Committed bytes:** the commit is not a full 40-hex commit; history or completion differ from the tables; a committed phase-meta file is outside 1..95 MiB.
- **ssh:** a production ssh other than `/usr/bin/ssh`; any login nonzero (rc 37 included), timed out, or with oversized output.
- **Remote refusals:**
  - any symlink or alias component;
  - a hard link;
  - a non-regular file;
  - a missing file;
  - a launch/exit size ≠ committed;
  - an mhz/census size outside 1..95 MiB;
  - a file that grows or shrinks while read;
  - at C, a size, device or inode changed since P.
- **On 05:**
  - a launch/exit SHA ≠ committed;
  - the stream ends early, or carries any excess byte;
  - a piece SHA, or a local re-read, ≠ P;
  - at V, anything changed;
  - the destination holds unexpected or special files.

**Test mode.** Test mode is on only when the environment holds `K4S_S1_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION`. Any other value of that variable is refused.

Test mode allows three things:
- `K4S_S1_TEST_DEST_ROOT`;
- `K4S_S1_TEST_REFUSAL_DIR`;
- an ssh other than `/usr/bin/ssh`.

Every manifest and receipt then carries the `…TEST-ONLY.v2` schema and `test_mode: true`, and S2 refuses such a manifest in production.

**Prerequisites on 03 and 04, not verified (no ssh this round).**
- `/usr/bin/python3` must exist. The fleet notes say Ubuntu 20.04 with python3 3.8. If it is missing, login P fails (rc 127) and S1 refuses before reading anything.
- The tests run the exact `REMOTE_PROGRAM` under 05's `/usr/bin/python3` (3.8.10).

Prerequisites on 05:
- `ssh 127x03` and `ssh 127x04` must use the LAN fleet key;
- `known_hosts` must already hold both host keys. `StrictHostKeyChecking=yes`; do not relax it.

**Timing (unchanged).** S1 must never run inside an END timing window on any host (from the first quiet read until exit + C-d) or during an RC-2 preflight. It cannot detect a window itself, so it requires `--outside-end-window "<GO ref + UTC>"`, which is recorded in the manifest and the receipts.

### Real run (after Sol review and the A1 GO; from 127x05)

```bash
git -C /mpac/sdicks02/repos/clasher fetch -q origin
C=$(git -C /mpac/sdicks02/repos/clasher rev-parse origin/main)
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python        # 3.12.12; S1 needs the stdlib only
S1=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r2/s1_copy_end_sources.py
# 1. dry run: prints the six planned ssh argv (C operands show <P size>/<P dev>/<P ino> placeholders) and the
#    committed SHAs/sizes; no ssh, no writes (a refusal would still write a receipt in s1-refusals/)
nice -n 19 $PY -I $S1 --repository /mpac/sdicks02/repos/clasher --commit $C --dry-run
# 2. live copy (exactly 6 logins)
nice -n 19 $PY -I $S1 --repository /mpac/sdicks02/repos/clasher --commit $C \
    --dest /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources \
    --outside-end-window "A1 GO <ref>, $(date -u +%FT%TZ)"
sha256sum /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources/s1-copy-manifest.json   # = M_SHA
```

The `b2-copy-r1/` parent must exist and be canonical; it is not created. If the copy refuses, look in `/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1-refusals/`.

After the copy, these coordinator steps follow (not part of S1):
1. Copy `end-sources/` byte-for-byte to `reports/explore/k4s-confirm/end-sources/`.
2. Re-check the SHAs against the manifest.
3. Run `clasher-secret-scan` on the staged diff.
4. Commit via a temp index, then push. This commit is **X**.

**Optional, before committing:** `s2 diagnose-clock --s1-dest … --s1-manifest … --s1-manifest-sha256 $M_SHA` (see below).

## S2: END evidence builder, offline validator and clock diagnosis (r2)

### `build`

`build` writes `clasher.k4s.end-evidence.v1`, kind `counted-reporting`, with exactly the keys `schema, kind, plan, completion, blind_ledger, counted_inventory, phases`.

- Every artifact item is `{path, sha256, commit, repository_path}`:
  - `commit` is X;
  - `repository_path` is the fixed path of its role;
  - `path` is that path relative to `reports/explore/k4s-confirm/`.
- Bytes come only from `git show X:<path>`.
- Production pins: plan `38064dcd`, completion-v2 `3794d953`, inventory `22c41cb7`, ledger `649272bd`.
- The phases must be **exactly the 10 pairs of record**. Each launch/exit SHA must equal the committed table, and each exit must be bound by the completion.
- **`--s1-manifest` + `--s1-manifest-sha256` are required.** S2 checks that the receipt has the production schema and that every row is a verified copy: local == on-host before == after. It then requires:
  - mhz/census local SHA and size == the committed bytes;
  - launch/exit on-host SHA == committed SHA == the item, with the same committed path.
- The output is written exclusive and no-follow under a canonical parent.

### `validate` (fail closed; one JSON result, exclusive and no-follow; exit 0 only if `ok`)

0. **Mode.** Production uses the constants of record. Every override is TEST-ONLY, as described under "Production vs test mode" below.
1. **Stdlib-only bootstrap (S2-F1), before any frozen import:**
   - The raw `mac/K4S-MAC-MANIFEST.json` in the code root must hash to the **fixed** approved `74314eda…`. There is no override.
   - Every file it pins is read no-follow and hashed: `k4s_files`, `end_files`, `reused_readonly` and the kernel files. This follows `k4s_logic.load_k4s_manifest(..., require_frozen=True)`: the measure_tiers statement, the native provenance, `frozen: true`, the filled SD1 pin and the filled kernel pins. 32 files.
   - The five frozen modules S2 executes are then run **from exactly those verified bytes**, by a meta-path loader (`ClosureFinder`/`VerifiedLoader`): `k4s_logic`, `end_evidence`, `fleet_end`, `fleet_profile` and `receipts`. Nothing is re-opened and no `.pyc` is used.
   - **Any other non-stdlib import is refused.** That covers site-packages, and any repository or code-root file even after the frozen `end_evidence` has put its directories on `sys.path`.
   - After the import: origin checks. The verified frozen `k4s_logic.load_k4s_manifest` runs as a second opinion. At the end, a closure audit confirms that every module loaded after the bootstrap is stdlib or served.
2. **Before any artifact read (S2-F2):**
   - The evidence is read no-follow at its fixed path and checked against `--evidence-sha256`.
   - The completion item must be the completion of record. The pinned completion is read via `git show` and checked by SHA, and its `counted_host_phases` fix the roles.
   - **Every item must be exactly its role's `repository_path`**, with `path` == that path relative to the evidence, and commit X.
   - Normalised relative paths are required, with no `..`, no `games`, no `complete.json`, no `hub-blocks` and nothing under `end/`.
   - The phase order must equal the completion's.
   - Record SHAs == the pins. In production, launch/exit == the table, and the S1 receipt binds all 40 items.
3. **Work-tree confinement:**
   - the repository root is canonical;
   - for every artifact, every component is opened `O_NOFOLLOW`;
   - every leaf is regular, with `st_nlink == 1` and non-empty.

   This happens before the frozen reader opens anything.
4. **Frozen checks.** S2 then runs:
   - the frozen `end_evidence.end_evidence()`: committed bytes, ancestry, launch/exit identity and `counting()`;
   - the record bindings, the counted hosts and the membership (3900/99);
   - per host, the frozen `slot_layout` and `host_reporting`;
   - the reporting half of `compare_mhz`, applied per core: each occupied physical core must be present, with finite MHz > 0.

   If `host_reporting` refuses, the frozen refusal stands, and the result carries `clock_diagnosis` for that host (see below).
5. **Profile.** Production requires either `--profile-json` + `--profile-json-sha256` (the S4 bundles' `reference_load_profile`), or an explicit `--declared-default-profile`. The result records which one was used, in `profile_source`.

The result records:
- the schema (`…validation.v2`, or `…TEST-ONLY.v2` in test mode) and `test_mode`;
- `frozen_bootstrap`: the manifest SHA, the count of files verified and the served pins;
- `frozen_module_sha256`;
- the interpreter, its executable and `optimize`;
- membership;
- per host: the reference CPUs, background slots, `census_cpu`, the full-occupancy rows per phase, and the census rows;
- `s1_manifest_sha256`, `profile_source` and `profile_json_sha256`.

### `diagnose-clock` (coordinator diagnostics request)

`diagnose-clock` is outcome-blind. It reads **only** the `end-sources/<host>/<phase>/{census,mhz}.jsonl` files, from one of two sources:
- `git show X:` of those files, plus the pinned completion for the phase list;
- or an S1 destination tree, read no-follow and checked against the S1 manifest's SHAs.

From each row it keeps only `utc`, `host` and `inflight` (census), and `utc`, `slots` and the core count / finiteness of `physical_core_mhz` (MHz). The census progress counters are never output.

Per host/phase, it reports:
- the row counts and any unparseable line numbers;
- duplicate census utc values (with their lines) and wrong-host census rows;
- duplicate MHz utc values;
- MHz rows with no census row (with utc and line);
- census rows with no MHz row (with utc, line, position first/interior/last, and the neighbouring joined utc on each side);
- slot mismatches;
- joined and full-occupancy row counts, and non-finite full-occupancy MHz;
- `frozen_join_would_pass`, and the **first frozen `host_reporting` rule that would refuse**, following its rule order at `fleet_end.py:204-221`.

Per host it reports the total of full-occupancy rows and whether the frozen minimum of ≥ 2 is met. Exit 0 = clean, 3 = mismatch diagnosed, 2 = refusal.

It **never repairs, filters, re-times or zips rows**, and the frozen refusal is unchanged (`repair: "none…"`). A real mismatch still needs a coordinator ruling.

Two things are known from source (`supervise.py:109-117`):
- both rows of one loop iteration carry the **same** `progress['utc']`;
- the census row is appended before `/proc/cpuinfo` is read and the MHz row is appended.

An abrupt termination, crash or I/O error between those two appends leaves a census row with no MHz row, typically `position: "last"`. Ordinary SIGTERM/SIGINT only set `interrupted`.

### Production vs test mode (S2-F1)

TEST-ONLY options:
- `--expect-plan`, `--expect-completion`, `--expect-counted-inventory`, `--expect-blind-ledger`;
- `--expect-hosts`, `--expect-blocks`, `--expect-losses`;
- `--evidence-repository-path`, `--warmup-seconds`;
- `--no-manifest-check`.

These are accepted only with **both** `--test-mode` and the environment `K4S_S2_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION`. Either one alone is refused, and so is a wrong marker value.

A test-mode run can only write the `…TEST-ONLY` schema, with `test_mode: true`. A production schema is never written in test mode, and a production `ok:true` needs the verified bootstrap.

### Real run (after X is pushed)

```bash
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python          # PC3 interpreter (3.12.12)
S2=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r2/s2_end_evidence.py
M=/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources/s1-copy-manifest.json; M_SHA=$(sha256sum $M | cut -c1-64)
git -C /mpac/sdicks02/repos/clasher fetch -q origin
X=<full SHA of the end-sources commit>
# optional outcome-blind clock diagnosis on the committed sources (exit 0 clean / 3 mismatch)
nice -n 19 $PY -I $S2 diagnose-clock --repository /mpac/sdicks02/repos/clasher --commit $X \
    --result /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/s2-clock-diagnosis.json
git -C /mpac/sdicks02/repos/clasher worktree add --detach /tmp/k4s-s2-build $X
nice -n 19 $PY -I $S2 build --repository /tmp/k4s-s2-build --commit $X \
    --out /tmp/k4s-s2-build/reports/explore/k4s-confirm/end-evidence.json --s1-manifest $M --s1-manifest-sha256 $M_SHA
sha256sum /tmp/k4s-s2-build/reports/explore/k4s-confirm/end-evidence.json
# coordinator: commit end-evidence.json alone (commit Y, child of X; temp index; secret scan; push)
git -C /mpac/sdicks02/repos/clasher worktree add --detach /tmp/k4s-s2-check <Y>
nice -n 19 $PY -I $S2 validate --repository /tmp/k4s-s2-check --commit $X \
    --evidence-sha256 <sha of end-evidence.json> --s1-manifest $M --s1-manifest-sha256 $M_SHA \
    --declared-default-profile \
    --result /mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/s2-validation.json
# after S4: re-validate with the bundles' profiles instead of --declared-default-profile
#   --profile-json <{host: reference_load_profile}> --profile-json-sha256 <sha>
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-build
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-check
```

`/tmp/k4s-s2-check` is canonical on 05; `/tmp` is not a symlink. The evidence goes into a later commit Y than X: it names X in every item, and a file cannot name its own commit. The END-JOB that binds `end_evidence_sha256` comes after Y.

**Offline limits (unchanged, stated).**
- `slot_layout` gets the counted host and the plan's `nice` (10), so its live host/priority gate is not exercised here; on the host it runs before the claim.
- Nothing past `slot_layout` (backend, guard, topology, the MHz gate under load) runs on 05. That is RC-2.

## Residuals (accepted / stated)

1. **TOCTOU (accepted by coordinator ruling, as in X4S-3).**
   - S1's remote reads have no check-to-open gap: they read the descriptor that was gated. S1's local writes go through retained descriptors.
   - The remaining gaps are on 05:
     - S2's confinement check runs before the frozen reader re-opens each work-tree path by name (`fleet_end.artifact`);
     - the redundant frozen `load_k4s_manifest` re-reads the code root.
   - A replacement in either gap is not detected beyond what the frozen committed-byte, ancestry and SHA checks catch.
2. **Mount aliases.** A bind mount of another tree onto a named directory is not a symlink or a hard link, so `O_NOFOLLOW` and nlink cannot detect it. This is a single-operator host with no such mounts; not checked.
3. **The interpreter and its stdlib are trusted** (PC3). S2 verifies the frozen *repository* code; it does not hash the interpreter. Remote side: `/usr/bin/python3` and `nice` on 03/04 are trusted host binaries.
4. **03/04 remote prerequisite not verified this round:** `/usr/bin/python3` must be present (see the S1 prerequisites). A missing one fails closed at P.
5. **The `--dest` parent** (`…/end-prep/b2-copy-r1/`) must already exist and be canonical; S1 creates only `--dest` itself.

## Tests (offline; what was verified)

```bash
cd /mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r2
export PYTHONDONTWRITEBYTECODE=1
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider tests
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider tests
```

**Results:** **86 passed** normally and **86 passed** under `-O` (34 S1, 52 S2). The only warning under `-O` is pytest's standard assertion-rewrite notice. Scripts run as subprocesses with `-I`, plus `-O` when pytest runs under `-O`; `r["optimize"]` is asserted. Every S1 and S2 run in the tests is in test mode, so no test writes a production receipt or `s1-refusals/`.

The tests need the real clasher checkout at origin/main (`CLASHER_REPO` overrides the location):
- S1's fake hosts serve the real committed phase-meta bytes;
- S2's code root is the K4S manifest closure exported via `git show`.

**S1 tests (34).** The fake `ssh` on `PATH` really runs `REMOTE_PROGRAM` (under local `/usr/bin/python3` 3.8.10) against `FAKE_SSH_ROOT/<host>/`. It logs argv and enforces the hygiene options. Its hooks inject stream corruption, extra bytes, a flood, growth, a same-bytes replacement, a mutation after the copy, or a forced rc. The tests cover:
- **Happy path:** the 6 logins in order. Each remote command is the exact `REMOTE_PROGRAM` with the fixed prefix; operands are only allowed names in that host's phase directories; nothing under `/mpac/sdicks02/jobs/` on 04. The bytes are equal, and the manifest is TEST schema with dev/ino recorded.
- **Dry run:** no ssh and no writes.
- **Launch/exit:** a launch size mismatch is refused remotely before any read. Same-size launch and exit SHA mismatches are refused.
- **Size gate:**
  - oversize on 03 and on 04 is refused;
  - a **64 GiB sparse source is never hashed** (refused in seconds);
  - an empty source is refused;
  - unit tests: the boundary cases, and that the remote stream cap == `MAX_BYTES`.
- **File type and aliases:**
  - a missing file is refused (ENOENT);
  - a **leaf symlink into `games/` is refused with ELOOP** (the target is mode 000, so following it would give EACCES);
  - a **phase directory aliased into 04's perception tree** is refused at that component;
  - a namespace ancestor symlink is refused;
  - a **hard-link alias is refused remotely**;
  - a FIFO is refused without blocking.
- **Changes around the copy:**
  - a mutation during the copy is refused at V, and the partial copy is kept and listed;
  - **growth or same-bytes replacement between P and C** is refused before one byte is streamed.
- **Stream integrity:**
  - **excess bytes** are refused;
  - a **256 MiB flood** is bounded: local files equal the inspected sizes, and the writer is stopped;
  - **same-length corruption** is refused;
  - a **valid stream with rc 37** is refused;
  - ssh rc 255 is refused.
- **Receipts** for: a missing window acknowledgement, an existing dest, a **dest below a symlinked ancestor** (the alias target stays untouched), a dest outside the root, an argument error, an invalid commit, and a P failure. A **refusal dir that is a symlink is never written**.
- **Units:** `O_EXCL|O_NOFOLLOW` never overwrites a planted symlink or file; the forbidden-prefix guard; the test-marker check; the production `/usr/bin/ssh` pin.

**S2 tests (52).** These use a synthetic committed repository: 3000/900 counted blocks, 1 loss + replacement, 3 host/phases. The tests cover:
- **Happy path:** build + validate. TEST schema, bootstrap verified (> 30 files), the served SHAs == the manifest pins, membership 3900/1, full-occupancy rows 8/4.
- **Audit-hook allowlist** on the happy path. Every absolute `open` is stdlib, a code-root file, an exact role path, the evidence, the result or the S1 receipt. Relative opens are only path components of those. Every `git show` names an exact role path. Directory listings come only from the import system's caches of the code root and stdlib. Zero events touch `games`, `complete.json` or `hub-blocks`.
- **Build refusals:**
  - an `end/` namespace path; an authority-like name; the record pins used against synthetic data;
  - uncommitted sources; an unbound exit;
  - an existing output, or **an output that is a planted symlink** (the target stays untouched);
  - the S1 cross-check, pass and fail; an **S1 launch-meta mismatch**.
- **Mode separation:**
  - test-only options refused in production;
  - `--test-mode` without the env marker, the env marker without `--test-mode`, and a wrong marker value: all refused;
  - `--no-manifest-check` is TEST-only and recorded;
  - production requires the profile choice and the S1 receipt;
  - production `load_s1` refuses a TEST receipt or a wrong receipt SHA.
- **Bootstrap:**
  - a **pre-import canary** appended to `end_evidence.py` never executes;
  - the **modified-verifier** attack (`verify_pinned = lambda …: None` in `k4s_logic.py`, plus a changed `fleet_end.py`) is refused, with no `frozen_manifest_verified` in the result;
  - a modified helper is refused, and so is a modified manifest;
  - a **symlinked frozen module** (identical bytes) is refused with ELOOP;
  - a code root without the frozen code is refused;
  - unit test: `ClosureFinder` refuses a planted module and site-packages, and allows the stdlib.
- **Exact roles / zero forbidden reads, all audited:**
  - the reviewer's **games/ reproduction** is refused before any read;
  - items pointing into `end/registry/…`, at `…/complete.json`, at another phase's file or through `..` are refused before any read;
  - a **work-tree leaf symlink into `games/`** is refused with ELOOP, and the frozen reader never opens it;
  - a **work-tree ancestor symlink** is refused, and nothing below it is opened;
  - an evidence-file symlink is refused;
  - a result that is a planted symlink is never followed.
- **r1 validate refusals, unchanged:** evidence SHA mismatch, a work-tree file differing from its commit, a commit that is not an ancestor, an extra key, the membership expectation, and an existing result.
- **S1 cross-checks in validate:** a **launch and an exit meta mismatch with correct telemetry**, and an mhz/census mismatch.
- **MHz / census join:**
  - **NaN, +inf, 0 and −1 MHz** in a full-occupancy row are refused;
  - a missing occupied core is refused;
  - NaN in a *non*-full-occupancy row is not selected, so validation passes; this matches frozen `compare_mhz`;
  - the full-occupancy selection counts are checked;
  - too few full-occupancy rows are refused, and the diagnosis shows 0 full-occupancy rows with a clean join;
  - a **kill between the writes** (last census row with no MHz row) is diagnosed as `position: last` with its neighbours;
  - an interior gap, a duplicate census utc, MHz with no census row, and a slots mismatch are each diagnosed.
- **`diagnose-clock`:** repository mode (exit 3, audited: only the completion and the 6 source paths are read via `git show`, and no census counters are output); clean S1-dest mode (exit 0); and an S1-dest copy that differs from its manifest (refused).

**Mutation check.** This was a scratch run, `/tmp/s1s2r2-mut/run_mutations.py`, under `-O`: **23/23 targeted mutants were killed**. They include the review's three survivors:
- removing both S1 piece comparisons;
- removing S2's finite-positive MHz check;
- removing S2's S1 launch/exit cross-check.

The others cover each remote gate (no-follow, nlink, regular file, max size, exact size, stream identity), excess bytes, the stream rc, V, the launch SHA, local no-follow/canonical, O_EXCL, the refusal receipt, the production ssh pin, the bootstrap, exact roles, work-tree confinement, the test-only gate, the closure finder and the diagnosis. In the first run the remote nlink mutant survived, because the redundant local check is post-hash; the test now requires the remote refusal.

**Also verified (smoke, `/tmp/s2r2-smoke/`, removed after):**
- `s2 build` and `validate` on the e4v3 interpreter `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` (3.12.12), normally and with `-O`: `ok`, bootstrap 32 files verified, rows 8/4.
- **Production-mode** validate with the exported real frozen closure: the bootstrap passed, then it refused at the synthetic evidence's completion item. That is the expected next gate, and the result had the production schema with `ok:false`.
- `s2 build` in production mode on **real origin/main** (`12928087`):
  - without an S1 manifest it refuses "--s1-manifest … required";
  - with a hand-made production-schema placeholder receipt (only in `/tmp`, deleted afterwards) it passed the record pins, the 10 production phases, the first phase's launch/exit table check, the S1 meta check and the exit binding. It then refused at the first uncommitted source (`end-sources/127x03/reporting/mhz.jsonl`), which is expected before B2.
- `s1 --dry-run` on the real repository with the e4v3 interpreter: 6 planned logins, and the committed sizes/SHAs resolved (exit sizes up to 1,045,522 B). It ran in test mode with the refusal dir in `/tmp`; nothing was written.

**Not verified.**
- No live S1 run, and nothing on 03/04, including the presence of `/usr/bin/python3` there.
- S2 has not run on real mhz/census data, because none is committed yet.

## Scratch

- The tests write only under pytest `tmp_path` (`/tmp/pytest-of-sdicks02/`).
- Mutation and smoke scratch: `/tmp/s1s2r2-mut/`, `/tmp/s2r2-smoke/`, both removed at the end of this round.
- No `__pycache__` is left in this directory (`-B` / `PYTHONDONTWRITEBYTECODE`).
