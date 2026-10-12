# K4S END prep: S1 (B2 exact-path copier, APPROVED r2) and S2 (END evidence builder): S2 CANDIDATE r4b (safe_input r3 / ruling E5)

## r4b (current; 2026-10-12 from 22:56Z, offline on 127x05; `s1s2-r4b/` = copy of `s1s2-r4/`, which is untouched)

- **Only the layer moved**: `safe_input.py` is byte-identical to `safe-input-r3/safe_input.py`, SHA-256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`. S2 pins that SHA (`hashlib` on the executed bytes) and the constants fingerprint `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592` (`s2_end_evidence.py:104–106`).
- S2 grants no E-exemption: it has no runtime role and no `git_plan`, so the nine E5 names still refuse in S2 (control: `tests/test_s2_gate_profile.py:176`).
- S2 does not reference the receive program. The r3 bytes give `39a92e9d…`, which matches the erratum.
- **S1 is unchanged**: `b987ab97…`, and `tests/test_s1.py` is unchanged.
- **Tests**: **270 passed** on each of k4s-freeze 3.12.12 and e4v3-venv 3.12.12, normal and `-O` (34 S1 + 53 + 137 + 46).
- **Mutation** (`tests/mutate_s2_r4.py`, `-O`): **60/63 killed**, 0 invalid, 3/3 NULL controls survived. The 3 survivors are r4's declared equivalents, and their JOINTs were killed (`MUTATION-RESULTS-r4b.json`).
- Finding → change: `RESPONSE-r4b.md`.
- **Running:** as in r4 below, with `s1s2-r4b`. Mutation: `nice -n 19 <python> -B tests/mutate_s2_r4.py /dev/shm/<scratch> 16`.
- In the r4 text below, "safe_input r2 / f9ca4926 / 6661ca0b" is superseded by the values above. Everything else stands.

---

## r4 text (kept)

## K4S END prep: S1 (B2 exact-path copier, APPROVED r2) and S2 (END evidence builder, offline validator, clock diagnosis): S2 CANDIDATE r4 (safe_input adoption)

**Status (r4):** S2 r4 answers `run-r1/reviews/SOL-REVIEW-END-S2S4-r3.md` (S2-R3-F1: static git indirection) by adopting the shared `safe_input` r2 layer (rulings P2-1, P2-4) and the 21:28Z frozen-reader wrapper ruling. Finding → change: `RESPONSE-r3.md`. Written offline on 127x05 on 2026-10-12 from 21:28Z in `s1s2-r4/` (copy of `s1s2-r3/`, untouched). No SSH, no commit, no push, no host access.

- **S1 unchanged:** `s1_copy_end_sources.py` is byte-identical to the approved bytes (`b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65`); `tests/test_s1.py` unchanged; S1 passes its 34 tests in every run below.
- **Layer pin:** `safe_input.py` here is byte-identical to `safe-input-r2/safe_input.py` (SHA-256 `f9ca49267dd350cf7ca6fc64b25ce93f53d8e63e9326356dbc72574ec380b648`); S2 verifies that SHA with `hashlib` on the bytes it executes and requires constants fingerprint `6661ca0b7635a3a66d8ab6612b5617435f06128d6e18b6bf96e25594a624d367` before any other code touches a path.
- **New CLI options:** `--git-dir`, `--git-common-dir` (all three commands): required together for a linked (detached) worktree checkout; production: `/tmp/k4s-s2-<name>` of `/mpac/sdicks02/repos/clasher`, git dir `<main>/.git/worktrees/<name>`, common dir `<main>/.git`.
- **Frozen reader:** runs only inside `frozen_git_env()` (P2-4 environment, declared GIT_DIR/GIT_WORK_TREE, no `refs/replace/`), after every artifact's committed blob and work-tree file were checked by si with the item SHA.

| r4 file | Role |
|---|---|
| `s2_end_evidence.py` | S2 r4 |
| `safe_input.py` | the pinned shared layer (byte-identical copy) |
| `tests/test_s2_r4_git.py` | new: S2-R3-F1 probes (replace refs, GIT_* env, static indirection, linked worktrees, frozen env), loader pins, si-before-frozen ordering, case-variant names |
| `tests/test_s2.py`, `tests/test_s2_gate_profile.py`, `tests/conftest.py`, `tests/audit_run.py` | r3 suites adapted (RESPONSE-r3 "Intentional test changes") |
| `tests/mutate_s2_r4.py`, `MUTATION-RESULTS-r4.json` | r4 mutation driver and its results on the final bytes |
| `RESPONSE-r3.md` | r4 response |
| `SHA256SUMS` | SHA-256 of every file |
| kept | `tests/mutate_s2.py`, `MUTATION-RESULTS-r3.json`, `RESPONSE-r1.md`, `RESPONSE-r2.md` (r3 code; historic) |

**Running:** `cd s1s2-r4 && nice -n 19 <python> -B [-O] -m pytest -q -p no:cacheprovider tests` (tests write only under pytest's base temp in `/tmp`, which is `K4S_S2_TEST_ROOT`); mutation: `nice -n 19 <python> -B tests/mutate_s2_r4.py /dev/shm/<scratch> 16` (scratch below `/dev/shm`, pytest basetemps are `tempfile` dirs below `/tmp`, removed).

## Verification (127x05, 2026-10-12; every number from this session, on the final bytes in `SHA256SUMS`)

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **269 passed** | **269 passed** (1 warning: pytest's assertion-rewrite notice under `-O`) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 (pytest 9.1.1 from a `/dev/shm` `--target` dir) | **269 passed** | **269 passed** (same warning) |

269 = 34 S1 (`test_s1.py`, unchanged) + 53 `test_s2.py` + 136 `test_s2_gate_profile.py` + 46 `test_s2_r4_git.py`. Every S2 subprocess inherits `-O` when pytest runs under `-O`. All runs used `nice -n 19`, `-B`, `-p no:cacheprovider`.

**Mutation (`tests/mutate_s2_r4.py`, k4s-freeze 3.12.12, `-O`, `-x`, 16 jobs; `MUTATION-RESULTS-r4.json`, finished 22:44:36Z; S2, layer and test SHAs recorded inside and equal to the final bytes):** **60 of 63 killed**; 0 invalid; 3 NULL controls (unmodified source) all SURVIVED. The 3 survivors are the declared single-gate equivalents, each masked by a stronger adjacent gate, and each JOINT counterpart was KILLED:
- `R-bootstrap-si-sha-off` / `R-bootstrap-compare-off` (si's expected-SHA check and S2's explicit compare back each other up) → `R-bootstrap-both-off-JOINT` killed;
- `W-check-absent-off` (masked by `si.Writer.create_excl`, `O_EXCL`) → `W-both-off-JOINT` killed.
The 63 = 29 r4 adoption mutants (loader SHA/fingerprint/nlink; raw git for `show` and `run`; replace-ref check; frozen env inherited / unused / without declared GIT_DIR; si pre-read and work-tree hash off; undeclared worktree dirs; worktree rule; denylist off / code filter / local `end`, `t1-*`, host-root rules; a syscall before the all-path lexical pass; reads without expected SHA; strict JSON; write gates) + 34 r3 mutants whose snippets still exist (profiles, roots, bindings, bootstrap, closure).

**Scratch:** tests wrote only under pytest's base temp in `/tmp`; mutation package copies under `/dev/shm/k4s-r4-s2s4/mut-s2`, pytest basetemps `tempfile` dirs `/tmp/s2r4-mut-*`; all removed. No `/tmp/si-git-home-*` or `/tmp/s2-frozen-git-home-*` remains (checked).

---

## r3 text (kept; superseded wherever r4 above or RESPONSE-r3 differ)

### r3 header (historic)

**Status:** S2 is a round-3 candidate for Sol review. It answers the S2 section of `run-r1/reviews/SOL-REVIEW-END-PKG1-r2.md` (S2-R2-F1, S2-R2-F2), under coordinator ruling ab171591 ("2026-10-12 16:55Z"). The mapping from each finding to its change is in `RESPONSE-r2.md`; `RESPONSE-r1.md` (round 2) is kept unchanged for history.

- **S1 is APPROVED (Sol r2) and unchanged:** `s1_copy_end_sources.py` is byte-identical to the reviewed r2 bytes (`b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65`). `tests/test_s1.py` is also unchanged. The shared `tests/conftest.py` changed only in S2 helpers; S1 still passes its 34 tests.
- Nothing here has been run against a host. Writing this round made no ssh connection, no commit and no push.
- r3 was authored on 127x05 from a copy of `s1s2-r2/`, which is byte-identical to its committed 293b2fe7 bytes, against origin/main as fetched 2026-10-12 ~16:58–17:27Z (`cfee67cf` → `d482ab3d`). The frozen bytes the tests use are pinned by the K4S manifest, so they do not depend on which commit was fetched.

| File | Role |
|---|---|
| `s1_copy_end_sources.py` | S1 (approved; unchanged): run from 05; reads 03 and 04 read-only over ssh. Stdlib only |
| `s2_end_evidence.py` | S2 r3: `build` / `validate` / `diagnose-clock`. 05 only, no ssh. Stdlib, plus the frozen code once it has been verified |
| `tests/conftest.py`, `tests/test_s1.py`, `tests/test_s2.py`, `tests/audit_run.py` | Offline pytest: a fake ssh shim, a synthetic git repository and an audit recorder. The recorder logs audit-hook events, wrapped `os.stat`/`os.lstat`, and the dev/ino of every successful open |
| `tests/test_s2_gate_profile.py` | New in r3: the S2-R2-F1 location-gate controls (full audited entrypoints, canaries) and the S2-R2-F2 profile controls |
| `tests/mutate_s2.py` | New in r3: the mutation-check driver (53 mutants, under `-O`); not a pytest module |
| `RESPONSE-r2.md` | New in r3: each Sol r2 S2 finding/note → its change (file:line) or the justification |
| `MUTATION-RESULTS-r3.json` | New in r3: output of `tests/mutate_s2.py` on the final bytes (SHAs recorded inside) |
| `RESPONSE-r1.md` | Round-2 response to Sol r1 (unchanged) |

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
S1=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r3/s1_copy_end_sources.py   # == the approved r2 bytes (b987ab97…)
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

## S2: END evidence builder, offline validator and clock diagnosis (r3)

### Location gate: every explicit path, every entrypoint (new in r3; S2-R2-F1)

All three entrypoints run ONE shared gate (`gate_paths`, `s2_end_evidence.py:285-294`) over **every** path given on the command line, **before any stat, open, read or hash of it**. The paths are `--repository`, `--code-root`, `--out`, `--result`, `--s1-manifest`, `--s1-dest` and `--profile-json`. `--result` is gated first in `main`; nothing is written to an ungated result.

1. **Lexical, with no system call** (`lexical`, `:225-232`; `forbidden_reason`, `:210-222`; roots `Roots`, `:235-254`). This runs for *all* supplied paths before *any* of them is touched. Each path must be:
   - absolute, normalised (`normpath(p) == p`, no `//`, no `.`/`..`) and made of safe characters;
   - **not an outcome / strict-END location**. Refused: any component `games`, `hub-blocks` or `end` (case-insensitive); any component named like `*complete*.json*`, `*interference*.json*`, `*end-raw*.json*`, `END-JOB*.json`, `END-FINAL*.json` or `attempt-*.json`; any `k4s-confirm-*` or `t1-*` job-tree component; anything under `/mpac/sdicks02/jobs` or `/mpac/sdicks02/jobs-k4s`;
   - inside its **allowed root**:

     | Path | Allowed (production) |
     |---|---|
     | `--repository`, `--code-root` | exactly `/mpac/sdicks02/repos/clasher`, or `/tmp/k4s-s2-<name>` (a temp detached worktree) |
     | `--s1-manifest`, `--s1-dest`, `--profile-json`, `--result` | strictly below `/mpac/sdicks02/k4s-runner/run-r1/end-prep/` |
     | `build --out` | exactly `<--repository>/reports/explore/k4s-confirm/end-evidence.json` |

   - **name rules:** the S1 receipt must be named `s1-copy-manifest.json` (S1's own name). In `diagnose-clock --s1-dest`, it must be `<--s1-dest>/s1-copy-manifest.json`. The profile must be a `.json` file. Outputs must be `.json` files not named like an END authority.
2. **lstat walk** (`lstat_walk`, `:257-282`). Every component from `/` is `lstat`-ed, so no symlink is ever resolved, and a symlink anywhere is refused. Every ancestor must be a directory. By role, the leaf must be a directory; or a regular, non-empty file with **`st_nlink == 1`** (a hard-link alias is refused unread); or, for outputs, must not exist.
3. **Every read** opens the path component by component, `O_NOFOLLOW`. The leaf is `lstat`-ed through its parent descriptor **before** it is opened (`open_confined`, `:328-360`): a symlink, a non-regular file or `nlink != 1` is refused **unopened**. The opened `(st_dev, st_ino)` must equal that lstat and the gated identity (`read_gated`, `:387-391`). The same leaf-before-open rule applies to derived paths: work-tree artifacts, the frozen-code closure, the evidence and the S1-dest copies. Their repo-relative names pass the same `forbidden_reason` (`repo_relative`, `:299-307`), and their roots pass `lexical` inside `open_dir`.

The predicate refuses none of the frozen-code closure (32 files), the 44 production role paths or the README production paths: checked once offline this round against origin/main. The audited happy path (`test_valid_profile_and_receipt_accepted_with_recorded_source`) also asserts that no recorded event names a location the predicate refuses.

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
- The output is written exclusive and no-follow. In production, `--out` must be exactly the evidence path inside `--repository`; in test mode, anywhere below the test root (see the location gate).

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
   - Normalised relative paths are required, with no `..` and nothing the shared `forbidden_reason` refuses: `games`, `hub-blocks`, `end`, the outcome-name family and the job trees. Nothing under `end/` is allowed.
   - The phase order must equal the completion's.
   - Record SHAs == the pins. In production, launch/exit == the table, and the S1 receipt binds all 40 items.
3. **Work-tree confinement:**
   - the repository root has passed the location gate;
   - for every artifact, every directory component is opened `O_NOFOLLOW`;
   - every leaf is lstat-ed through its parent descriptor **before it is opened**: regular, with `st_nlink == 1` and non-empty. A symlinked or hard-linked artifact is refused unopened.

   This happens before the frozen reader opens anything.
4. **Frozen checks.** S2 then runs:
   - the frozen `end_evidence.end_evidence()`: committed bytes, ancestry, launch/exit identity and `counting()`;
   - the record bindings, the counted hosts and the membership (3900/99);
   - per host, the frozen `slot_layout` and `host_reporting`;
   - the reporting half of `compare_mhz`, applied per core: each occupied physical core must be present, with finite MHz > 0.

   If `host_reporting` refuses, the frozen refusal stands, and the result carries `clock_diagnosis` for that host (see below).
5. **Profile (r3; S2-R2-F2), checked right after the location gate, before git and the bootstrap.** Every mode needs **exactly one** of two sources:
   - `--profile-json` + `--profile-json-sha256`;
   - `--declared-default-profile`.

   Both together, neither, or a SHA without the file are refused. The profile JSON is parsed strictly: duplicate keys and `NaN`/`Infinity` are refused. It must be an object holding **exactly** the counted hosts. Each value must be a **non-empty object**, validated field by field (`check_profile`, `:787-808`; `load_profiles`, `:811-831`), against the frozen `fleet_profile.slot_layout`, `fleet_end.host_reporting` and the S4 declared profile:

   | Field | Required |
   |---|---|
   | `host` | equal to its key |
   | `reference_slot` | the int `0` (not a bool or float) |
   | `slot_count` | the int `11` |
   | `console_rule` | the bool `false` |
   | `warmup_seconds` | a finite int/float `>= 300` |
   | `perception` | `"none"` |

   Unknown fields are refused. The only other fields allowed are the S4 bundle extras: `plan`, `end_evidence` and `amendment` (non-empty strings) and `guard` (a non-empty object).

   **Nothing is ever completed from defaults.** `{}`, `null`, a list, a string, a number or a boolean is refused. The declared default is built only on the explicit `--declared-default-profile` branch, and goes through the same validator. The result records `profile_source` (`s4-bundles` / `declared-default`), `profile_json_path` and `profile_json_sha256` (both `null` for the declared default), and the validated profile per host.

The result records:
- the schema (`…validation.v2`, or `…TEST-ONLY.v2` in test mode) and `test_mode`;
- `frozen_bootstrap`: the manifest SHA, the count of files verified and the served pins;
- `frozen_module_sha256`;
- the interpreter, its executable and `optimize`;
- membership;
- per host: the reference CPUs, background slots, `census_cpu`, the full-occupancy rows per phase, and the census rows;
- `s1_manifest_path`, `s1_manifest_sha256`, `profile_source`, `profile_json_path` and `profile_json_sha256`.

### `diagnose-clock` (coordinator diagnostics request)

`diagnose-clock` is outcome-blind. It reads **only** the `end-sources/<host>/<phase>/{census,mhz}.jsonl` files, from one of two sources:
- `git show X:` of those files, plus the pinned completion for the phase list;
- or an S1 destination tree, read no-follow and checked against the S1 manifest's SHAs. Both `--s1-dest` and its `--s1-dest/s1-copy-manifest.json` pass the location gate. The receipt's rows are typed and validated before any copy is opened, and copies are lstat-ed before they are opened.

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

**Test root (r3).** Test mode also requires `K4S_S2_TEST_ROOT`, an absolute path strictly below `/tmp/` that is not itself a forbidden location. It replaces every allowed root, so checkouts, inputs and outputs must lie strictly below it. The forbidden-location predicate, the lstat walk, nlink and the name rules are **unchanged** in test mode. A production run with `K4S_S2_TEST_ROOT` set is refused.

### Real run (after X is pushed)

```bash
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python          # PC3 interpreter (3.12.12)
S2=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r3/s2_end_evidence.py
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
# after S4: re-validate with the bundles' profiles instead of --declared-default-profile (exactly one of the two).
#   The {host: reference_load_profile} file must lie strictly below /mpac/sdicks02/k4s-runner/run-r1/end-prep/
#   (e.g. b2-copy-r1/s4-profiles.json), a regular single-link file, not a symlink:
#   --profile-json <file> --profile-json-sha256 <sha>
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-build
git -C /mpac/sdicks02/repos/clasher worktree remove /tmp/k4s-s2-check
```

`/tmp/k4s-s2-check` is canonical on 05; `/tmp` is not a symlink. The location gate requires these forms: worktrees named `/tmp/k4s-s2-<name>` (or the main checkout), `--out` exactly the evidence path inside the build worktree, and the receipt, profile and results strictly below `end-prep/`. The evidence goes into a later commit Y than X: it names X in every item, and a file cannot name its own commit. The END-JOB that binds `end_evidence_sha256` comes after Y.

**Offline limits (unchanged, stated).**
- `slot_layout` gets the counted host and the plan's `nice` (10), so its live host/priority gate is not exercised here; on the host it runs before the claim.
- Nothing past `slot_layout` (backend, guard, topology, the MHz gate under load) runs on 05. That is RC-2.

## Residuals (accepted / stated)

1. **TOCTOU (accepted by coordinator ruling, as in X4S-3).**
   - S1's remote reads have no check-to-open gap: they read the descriptor that was gated. S1's local writes go through retained descriptors.
   - The remaining gaps are on 05:
     - S2's lstat gate, then its descriptor open. This gap is narrowed: the opened `(st_dev, st_ino)` must equal the gated lstat, so a replacement in between is refused.
     - S2's confinement check runs before the frozen reader re-opens each work-tree path by name (`fleet_end.artifact`);
     - the redundant frozen `load_k4s_manifest` re-reads the code root.
   - A replacement in the last two gaps is not detected beyond what the frozen committed-byte, ancestry and SHA checks catch.
2. **Mount aliases.** A bind mount of another tree onto a named directory is not a symlink or a hard link, so the lstat walk, `O_NOFOLLOW` and nlink cannot detect it. This is a single-operator host with no such mounts; not checked.
3. **A hard-link alias is detected by its own metadata.** To see `st_nlink`, S2 must `lstat` the operator-named alias. That is one metadata call on the alias's inode, never on the outcome path; no open or read follows. Directories cannot be hard-linked, so only regular files need the gate.
4. **The location predicate is name-based.** It refuses the outcome/strict-END/job-tree names listed above, and allowed roots confine every explicit path. An outcome file deliberately copied, under an innocuous single-link name, to an allowed location under end-prep is indistinguishable by location. Its SHA must still equal the operator-supplied SHA, and its schema must pass the strict receipt/profile validation before anything is used.
5. **The interpreter and its stdlib are trusted** (PC3). S2 verifies the frozen *repository* code; it does not hash the interpreter. Remote side: `/usr/bin/python3` and `nice` on 03/04 are trusted host binaries.
6. **03/04 remote prerequisite not verified this round:** `/usr/bin/python3` must be present (see the S1 prerequisites). A missing one fails closed at P.
7. **The `--dest` parent** (`…/end-prep/b2-copy-r1/`) must already exist and be canonical; S1 creates only `--dest` itself.

## Tests (offline; what was verified)

```bash
cd /mpac/sdicks02/k4s-runner/run-r1/end-prep/s1s2-r3
export PYTHONDONTWRITEBYTECODE=1
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider tests
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider tests
nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B tests/mutate_s2.py /tmp/s1s2r3-mut 8     # mutation check
```

**Results:** **221 passed** normally and **221 passed** under `-O` (34 S1, 53 `test_s2.py`, 134 `test_s2_gate_profile.py`). The only warning under `-O` is pytest's standard assertion-rewrite notice. Scripts run as subprocesses with `-I`, plus `-O` when pytest runs under `-O`; `r["optimize"]` is asserted. Every S1 and S2 subprocess run in the tests is in test mode, or is a production-mode run that the tests assert refuses before writing. No test writes a production receipt, a production result or `s1-refusals/`.

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

**S2 tests, `tests/test_s2.py` (53; the r2 file, adapted to r3).** These use a synthetic committed repository: 3000/900 counted blocks, 1 loss + replacement, 3 host/phases. The tests cover:
- **Happy path:** build + validate. TEST schema, bootstrap verified (> 30 files), the served SHAs == the manifest pins, membership 3900/1, full-occupancy rows 8/4.
- **Audit-hook allowlist** on the happy path. Every absolute `open` is stdlib, a code-root file, an exact role path, the evidence, the result or the S1 receipt. Relative opens are only path components of those. Every `git show` names an exact role path. Directory listings come only from the import system's caches of the code root and stdlib. r3: every absolute `stat`/`lstat` is an allowed path, one of its ancestors, or the interpreter tree. Zero events touch `games`, `complete.json` or `hub-blocks`.
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
  - a **symlinked frozen module** (identical bytes) is refused by the pre-open lstat, unopened;
  - a code root without the frozen code is refused;
  - unit test: `ClosureFinder` refuses a planted module and site-packages, and allows the stdlib.
- **Exact roles / zero forbidden reads, all audited:**
  - the reviewer's **games/ reproduction** is refused before any read;
  - items pointing into `end/registry/…`, at `…/complete.json`, at another phase's file or through `..` are refused before any read;
  - a **work-tree leaf symlink into `games/`** is refused by the pre-open lstat (the target is mode 000, so following it would give EACCES), and the frozen reader never opens it;
  - a **work-tree ancestor symlink** is refused, and nothing below it is opened;
  - an evidence-file symlink is refused;
  - a result that is a planted symlink is never followed (the lstat walk refuses it; nothing is written).
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

r3 adaptations of this file:
- every validate passes the explicit profile choice;
- S1 receipts are written as `<dir>/s1-copy-manifest.json`;
- symlink refusals assert the pre-open lstat message;
- the old production-mode `p.json` checks are replaced by `test_production_confines_result_and_refuses_test_root_setting` (production writes nothing outside its roots and refuses `K4S_S2_TEST_ROOT`) and `test_production_requires_s1_receipt`.

**S2 r3 controls, `tests/test_s2_gate_profile.py` (134).** These use a module-level synthetic repository with committed evidence, a valid S1 receipt and a valid S4-style profile.

The location controls run the **full CLI entrypoints** (`build`, `validate`, `diagnose-clock` in repository mode and in S1-dest mode) under `tests/audit_run.py`. The canaries hold **valid** input bytes with the matching SHA, so only the location can refuse them. Each control asserts both:
- the refusal (result `ok:false`, or stderr when no gated result location exists);
- **zero recorded events** naming the canary location or any location the predicate refuses, **no open of a canary inode**, and no stat of a canary inode except the lstat of the operator-named alias itself (which is how the alias is detected).

- **Positive controls:**
  - the canary bytes pass at an allowed location: `ok`, `profile_source: s4-bundles`, `profile_json_path`/`_sha256`, the validated profile per host, `s1_manifest_path`;
  - the declared default is recorded with `null` path/SHA.
- **S2-R2-F1 profile canaries (12, validate):**
  - **the Sol r2 reproduction `reports/explore/k4s-confirm/end/end-raw.json`**;
  - `games/`, `hub-blocks/`, `complete.json`, `complete-v2.json`, `interference.json`, `end-raw-copy.json`, `attempt-00.json`, `END-FINAL-x.json`;
  - `end/receipts/round-00/127x03/raw-00/reference-warmup.json`;
  - `k4s-confirm-reporting-r1/…`, `t1-20261010-r1/…`.

  Each canary is mode 000. git and the bootstrap never run.
- **S1-receipt canaries:**
  - 6 locations, via validate;
  - 3 via build. Build also gets an `--out` in a forbidden directory, which stays empty.
- **Location before SHA/schema:** profile and receipt canaries with a wrong SHA or invalid content are refused for their location, never with "SHA mismatch"/"schema", and stay untouched.
- **Forbidden `--repository`** (validate and diagnose-clock), **`--code-root`** and **`--result`** (validate and diagnose-clock; nothing is written and git never runs).
- **S1-dest canaries:** 3 forbidden `--s1-dest` trees for diagnose-clock; none of their inodes is touched. The receipt must be `<--s1-dest>/s1-copy-manifest.json`.
- Outside the allowed root (`/var/tmp/…`, never stat-ed); unnormalised, relative, `//` and unsafe-character paths; the receipt and profile name rules.
- **Hard-link canaries:**
  - the profile;
  - the S1 receipt through **each of build, validate and diagnose-clock**;
  - an S1-dest `mhz.jsonl`;
  - a work-tree artifact (`census.jsonl`) hard-linked into `games/`/`hub-blocks/`.

  All are refused, and **no canary inode is ever opened**.
- **Symlink canaries:** leaf and ancestor profile symlinks; the S1 receipt symlink through each of the three entrypoints; symlinked `--repository`, `--code-root` ancestor, `--s1-dest`, and a result parent that aliases `end/` (nothing is written).
- **Gate → open identity:** a profile replaced (same bytes, new inode) after the gate is refused at the open.
- **The lexical gate is pure:** run inside a context that makes any `os.stat/lstat/open/listdir/scandir` or `open()` raise. Covered:
  - 20 production-root cases (job roots, T1/K4S job trees, the END namespace, `hub-view`, `..`, relative paths, checkout forms);
  - all lexical checks run before any lstat;
  - the production `build --out` equality;
  - production validate refusing an END-namespace profile;
  - `open_dir`/`read_confined`/`write_new` on forbidden locations;
  - **the Sol r2 reproduction 2**: `load_s1(testing=False)` called directly on a production-schema receipt at `…/k4s-confirm/end/end-raw.json`;
  - the test-root rules.
- **S2-R2-F2 profiles (36 malformed variants plus parse/choice controls, all through validate):**
  - **the Sol r2 reproductions: `{}` per host, and `null` per host**;
  - lists, strings, numbers and `true` as values;
  - a missing or an extra host key; a top-level list;
  - a host mismatch or a non-string host; an unknown field;
  - `reference_slot` 1 / `false` / `0.0` / `"0"`;
  - `slot_count` 10 / 8 / `11.0`;
  - `console_rule` `true` / `0` / `"false"`;
  - `warmup_seconds` 299.9 / `"300"` / `true` / `null`;
  - `perception` `"full"` / `null`;
  - wrongly typed S4 extras;
  - each required field missing.

  Each is refused, with no `profile_source` and no `hosts` in the result. Also refused: duplicate keys, `NaN`, `Infinity` and invalid JSON; both sources, neither source, a SHA without the file, and a wrong SHA. Accepted: `300.0` and `600`, with and without the S4 extras.
- **S1 receipt contents:** wrongly typed rows, an unsafe host/phase, missing fields, a non-list or `null` row, and a duplicate key are refused.

**Mutation check (r3; `tests/mutate_s2.py`, scratch `/tmp/s1s2r3-mut/`, removed after; results kept as `MUTATION-RESULTS-r3.json`).** Each mutant applies one exact edit (or one listed set of edits) to `s2_end_evidence.py` in a scratch copy, then runs both S2 test files under **`python -O`** with `-x` and its own `--basetemp`. "Killed" means pytest exit 1 with a failed test; any other exit counts as INVALID, not killed. Result: **53/53 killed; 0 survived; 0 INVALID** (2026-10-12T17:43:48Z, on S2 `973a5ace…` and the two S2 test files whose SHAs `MUTATION-RESULTS-r3.json` records). The mutants:
- **F1 (28):**
  - the whole forbidden predicate;
  - each forbidden component (`end`, `games`, `hub-blocks`), the outcome-name family, the job-tree names and the host job roots;
  - the allowed-root check and normalisation;
  - the lstat walk's symlink and nlink gates;
  - lexical-before-any-lstat ordering;
  - the pre-open leaf lstat (symlink, nlink) and the gate→open identity;
  - `open_dir`/`write_new`/`repo_relative` lexical gates;
  - the receipt/profile name rules and the dest↔receipt pairing;
  - the production test-root refusal, test root below `/tmp/`, the production `--out` equality and the gated result;
  - typed/checked S1 rows, and strict S1 JSON.
- **F2 (19):**
  - **the r2 behaviour restored** (`profiles.get(host) or default` without the check), and the check removed;
  - each field rule; empty, missing and unknown fields; the extras' types;
  - duplicate keys and NaN;
  - both / neither source, and the SHA pairing;
  - the mislabelled source, and the unrecorded path.
- **Regression (6) of r2 gates:** bootstrap skipped, a permissive closure finder, the exact role check, work-tree confinement, finite-positive MHz, and the S1 meta cross-check.

A first campaign gave 48 killed and 5 INVALID: the pure-lexical tests had patched `os.stat` until pytest's own failure report, so a failing test crashed pytest instead of failing. The trap now restores the functions before pytest reports. Spot check without `-x`: the outcome-name mutant fails all six outcome-name profile canaries independently.

**Also verified this round (smoke, `/tmp/s2r3-smoke/` and `s1s2-r3/smoke-tmp/`, both removed after):**
- On the END interpreter `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` (3.12.12), test mode, synthetic data, normally and with `-O`:
  - `build` rc 0;
  - `validate` with an S4-style profile JSON: rc 0, `ok`, bootstrap 32 files, `profile_source: s4-bundles`, rows 8/4, `optimize` 0/1;
  - `diagnose-clock` rc 0 (clean).
- **Production mode on real origin/main (`d482ab3d`)**, END interpreter, in a temp detached worktree `/tmp/k4s-s2-r3smoke` (removed after). The placeholder production-schema S1 receipt and the results lived under `s1s2-r3/smoke-tmp/`, removed after.
  - `build` in the README form passed every location gate: the worktree checkout form, `--out` == the evidence path in the worktree, and the receipt under end-prep. It refused only at the first uncommitted `end-sources/127x03/reporting/mhz.jsonl`, as expected before B2. No evidence file was written.
  - `build` with `--out` under end-prep refused with "outside its allowed root" before any access.
  - `validate` passed the gates and the bootstrap on the real frozen code, then refused at the missing evidence (production schema, `ok:false`).
  - `diagnose-clock` refused at the same missing source.
- Not re-run in r3: the r2 `s1 --dry-run` smoke (S1 is unchanged).

**Not verified.**
- No live S1 run, and nothing on 03/04, including the presence of `/usr/bin/python3` there.
- S2 has not run on real mhz/census data, because none is committed yet.
- No real S4 bundle profile has been fed to S2: S4 r3 is not yet produced. The accepted extras (`plan`, `end_evidence`, `amendment`, `guard`) follow S4 r2's `reference_load_profile`. A future S4 field not in that list is refused, fail-closed, until added and reviewed.

## Scratch

- The tests write only under pytest's base temp directory (`/tmp/pytest-of-sdicks02/`), which is also `K4S_S2_TEST_ROOT`.
- Mutation and smoke scratch: `/tmp/s1s2r3-mut/`, `/tmp/s2r3-smoke/`, `/tmp/s1s2r3-spot/`, the worktree `/tmp/k4s-s2-r3smoke` and `s1s2-r3/smoke-tmp/`, all removed at the end of this round.
- No `__pycache__` is left in this directory (`-B` / `PYTHONDONTWRITEBYTECODE`).
