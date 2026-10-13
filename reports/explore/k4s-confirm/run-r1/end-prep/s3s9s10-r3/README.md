# K4S END prep: S1b, S3, S9, S10 — CANDIDATES r3 (END-FULL-F4, F2 Part A, F1 end_prep_common + every Part A entrypoint)

- **Status:** offline candidates for Sol review. **Nothing touched a host:** no ssh, no network clone (synthetic `file://` repositories only), and S1b, S3, S9 and S10 were never run for real. Nothing was committed or pushed. r2 (`../s3s9s10-r2/`) is unchanged; this directory began as a `cp -a` copy of it.
- **Answers:** `run-r1/reviews/SOL-REVIEW-END-FULL-r1.md` — END-FULL-F4, the Part A side of END-FULL-F2, and the end_prep_common half of END-FULL-F1 (extended to every Part A pre-layer sibling read). **`RESPONSE-r3.md`** maps each finding to its change (file:line) and its named regression tests. `RESPONSE-r1.md` (the r2 response to the package-2 review) is kept unchanged as history; every repaired earlier finding and the accepted disclosures (D1 six support members, S9 clone exception, S3 FETCH_HEAD removal, S10 receive receipt) are preserved.
- **Written:** 2026-10-13, on 127x05, by an offline implementer. The resume log is `PROGRESS-r3.md`.

## END-FULL-F1: the canonical bootstrap (r3)

Every read of a sibling file before (or beside) the shared layer goes through bootstrap-r1's **canonical bootstrap**, pasted **verbatim** (BEGIN..END markers included; `tests/k4s_bootstrap_r1.py` is the vendored source of record, sha256 `5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b`, 8372 bytes, CANONICAL-READY 2026-10-13T00:13:28Z) in `end_prep_common.py` and in all four entrypoints. Its contract: normalized absolute path taken as Python was given it (never `abspath`/`realpath`), the outcome name families on every component, a component-wise `O_DIRECTORY|O_NOFOLLOW` walk from `/`, the leaf regular / `st_nlink == 1` / exactly the pinned size before any byte, the SHA-256 pin, then exactly the verified bytes executed (never re-read by pathname).

- `end_prep_common.py` loads `safe_input.py` (pins `SAFE_INPUT_SHA256`, `SAFE_INPUT_SIZE = 133606`), then checks the constants fingerprint and the reader/receive program SHAs as before.
- **Audit result:** r2's entrypoints also imported `end_prep_common.py` by `sys.path`, and `C.import_sibling` imported s1b/s3/s9 the same way. In r3 each entrypoint loads `end_prep_common.py` with `_k4s_common()` (the canonical loader) and its siblings with `C.load_sibling(name, *K4S_SIBLING_PINS[...])`. No module edits `sys.path` or imports a sibling.
- **Pin chain** (acyclic; each module pins the files it loads): safe_input ← end_prep_common ← s9 ← s1b ← s3 ← s10. After editing any module, run `python3 -I -B tests/k4s_adopt.py --root <dir>` (recomputes the pins in dependency order; `--canonical FILE` re-pastes the block; `--check` reports drift). A stale pin refuses the load.
- An already loaded module of a sibling's name is reused only if the bootstrap loaded it from the same path with the same pins (`__k4s_bootstrap__`); in-process importers (the tests) therefore import `s10_stage_host` first.
- Conformance: `tests/test_f1.py` runs the vendored bootstrap-r1 kit (`tests/k4s_bootstrap_kit.py`, `tests/kit_harness.py`, byte copies, sha-pinned in the test) against every entrypoint × every pinned file it loads; see §Tests.

## safe_input pin

`safe_input.py` is vendored **byte-identical from `safe-input-r3/`**: sha256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`. r3 is r2 plus ruling E5. Before adopting it I checked two things:

- `safe-input-r3/PROGRESS-r3.md` says DONE (M8, 21:52:58Z);
- `sha256sum -c safe-input-r3/SHA256SUMS` passes for all 26 files.

Development and the first mutation campaign ran against r2 (`f9ca4926…`). After the switch, every test and both mutation campaigns were re-run on r3.

`end_prep_common.py` loads the layer as follows (r3: through the canonical bootstrap, §END-FULL-F1):
1. the path `<dir of end_prep_common.py as given>/safe_input.py` must be absolute and normalized, with no outcome-family component; every ancestor is walked `O_DIRECTORY|O_NOFOLLOW` from `/`;
2. the leaf must be a regular file with st_nlink 1 and exactly 133606 bytes **before any byte is read**; then exactly that many bytes are read from that descriptor and their SHA-256 checked with stdlib `hashlib`;
3. execute exactly those verified bytes (it is never re-imported or re-opened from disk);
4. require `constants_fingerprint()` = `33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`;
5. require the shipped reader program = `2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`;
6. require the shipped receive program = `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4`.

**Receive-program SHA (corrected citation, r3).** The receive program of the pinned r3 bytes is `39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4` (computed from the bytes under /usr/bin/python3 3.8.10 and k4s-freeze 3.12.12; Sol END-FULL disclosure 8 recomputed the same value), and the reader program is `2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`. These are the values `end_prep_common.py` pins and the values of the runner's committed erratum (origin/main `reports/explore/k4s-confirm/run-r1/end-prep/safe-input-r3/README-ERRATUM-receive-sha.txt`), which this directory ships byte-identically as `SAFE-INPUT-R3-README-ERRATUM-receive-sha.txt` (sha256 `126016f06728c9746f740db476b17133323bf1d3e69bf78833d80ccf168334a8`, in `SHA256SUMS`). safe-input-r3's README §8 misprints the receive value; that is a documentation error only (safe_input.py unchanged).

Remote programs ship exactly as safe_input provides them: `si.remote_check` (reader) and `si.remote_receive` (receive, with its SHA-256 checked by the bootstrap on the host).

## Files

| File | Role | Touches hosts |
|---|---|---|
| `safe_input.py` | the vendored r3 layer (unchanged) | — |
| `end_prep_common.py` | the canonical bootstrap (verbatim) + the pinned safe_input load and `load_sibling`; output confinement; `publish_dir` (renameat2 RENAME_NOREPLACE); `unlink_own`/`chmod_readonly` on gated fds; `Record`; `ScrubbedEnv` (P2-4 env for frozen children) | — |
| `s1b_copy_admissions.py` | S1b: the three admissions through the pinned reader, written in E3 layout | yes, read-only, **2 logins** |
| `s3_guard_job.py` | S3: guard job builder/verifier (`-rdRR-aNN` and `-pfNN`) | no |
| `s9_end_runtime.py` | S9: `prepare-clone`, `locate`, `build`, `verify`, `equivalence` | no (network clone from GitHub only) |
| `s10_stage_host.py` | S10: stages runtime / bundles / guard job onto one host; `--print-roots` | yes, 4 + N logins (+1 with `--create-base`) |
| `RC6-ROOTS-DRAFT.json` | RC-6 roots declaration draft (`s10_stage_host.py --print-roots`) | — |
| `RESPONSE-r3.md` | END-FULL finding → change (file:line) → named tests | — |
| `RESPONSE-r1.md` | the r2 response (history, unchanged) | — |
| `SAFE-INPUT-R3-README-ERRATUM-receive-sha.txt` | byte copy of the runner's committed receive-SHA erratum | — |
| `PROGRESS-r3.md` | resumable log | — |
| `tests/` | offline pytest suite (synthetic world, namespaced fake hosts, conformance kit) + `mutate.py`; `fixture_guard_job.py` (the synthetic world + the F2 guard-job CLI); `k4s_adopt.py` (canonical paste + pin chain); `k4s_bootstrap_r1.py`, `k4s_bootstrap_kit.py`, `kit_harness.py` (vendored from bootstrap-r1) | no |
| `MUTATION-RESULTS-s3s9s10-r3-py312-O.json`, `MUTATION-RESULTS-s3s9s10-r3-py38-O.json` | final r3 mutation campaigns | — |
| `SHA256SUMS` | every file above | — |

r3 dropped r2's `MUTATION-RESULTS-r3-*.json` (they describe the r2 sources; still in `../s3s9s10-r2/`). r1-only artifacts were dropped earlier: `RUNNER-PATCH-E3.diff`, `s9-locate-caeeecdc.json`, `s10-dry-run-EXAMPLE-synthetic-admissions.txt`, and the r1 tests. `--inputs`, `--admissions-dir`, `--source` and `--ssh` are gone.

Run everything on 127x05 with `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B` (3.12, stdlib only). The code is Python 3.8-compatible, and the suite also runs on /usr/bin/python3 3.8.10. Frozen children (S3, S9) are never run with `-O`. Every SHA argument below is printed by the previous step.

## S1b — admissions (Q2, E3; S1b-F1)

```bash
D=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r3; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
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
- **Guard-repository contract (r3, END-FULL-F2; S3's construction is unchanged).** The runner kept S3's minimal Q3 repository. Every consumer of `<job>/repo` (S3 `prove_repo`/`verify`, S5 preflight and S7 launch via Part B's guard-role allowance) relies on exactly this shape:

  | Property | Contract |
  |---|---|
  | Shallowness | **shallow, depth 1.** `.git/shallow` lists exactly the four binding commits; `rev-parse --is-shallow-repository` is `true`. A full guard repository is NOT the contract. |
  | Commits | exactly the four seed/join binding commits (`SEEDS` b2f9e25e, ce042b97; `JOINS` 0e137378, 274aed9a), each `cat-file -e <c>^{commit}`; the Q3 two first |
  | Refs | exactly `refs/k4s-end/<label>` → its binding commit, as loose files (0444); no branches, no tags, no `refs/replace`, no `refs/remotes`; `HEAD` is the `init` default (an unborn `refs/heads/master`) |
  | Work tree | exactly the four seed/join files at their binding paths, git bytes == work-tree bytes == the binding SHA-256, mode 0444 |
  | Config | exactly `core.bare`, `core.filemode`, `core.logallrefupdates`, `core.repositoryformatversion` (`GUARD_GIT_CONFIG_KEYS`): no remote, no promisor/partial-clone keys, no extensions, includes or drivers |
  | Git dir | `GIT_DIRS` exist as real directories; `.git` is a directory (no gitfile); no `FETCH_HEAD`, no hooks (`init --template=`) |
  | Indirections | **the ONLY allowed indirection is `shallow`** (`si.GitRepo(..., allow=("shallow",))`). Alternates, http-alternates, grafts, commondir, `config.worktree`, replace refs, hooksPath/fsmonitor/attributes keys and every other `_git_preflight` refusal stay refused |

  A consumer must declare the shallow allowance for this guard role only (an ordinary `si.GitRepo` refuses `.git/shallow` before git runs; `tests/test_fixture_guard_job.py::test_shallow_needs_an_explicit_guard_role_allowance`), and keep the evidence/END-JOB repositories full.
- **Fixture for Part B (`tests/fixture_guard_job.py`).** Builds ONE real guard job with the shipped `s3_guard_job.build` (only the S1b admissions manifest is a stand-in; it is read by SHA exactly as an S1b run's would be):
  ```bash
  D=$(mktemp -d /tmp/k4s-guardfx-XXXX)      # must be an existing EMPTY directory under /tmp/ (S3's output root)
  nice -n 19 /usr/bin/python3 -I -B <this dir>/tests/fixture_guard_job.py --dir $D [--host 127x03|127x04] \
      [--round RR --attempt NN | --preflight NN] > facts.json     # on 127x05; exit 0, or 2 + reason on stderr
  chmod -R u+w $D && rm -rf $D                 # afterwards (files are 0444)
  ```
  stdout is one JSON object (schema `clasher.k4s.test.s3-guard-job-fixture.v1`): `job_dir`, `repo_dir` (= `<job_dir>/repo`), `job_name`, `target_job` (the Q4 path), `host`, `job`, `manifest_path`, `manifest_sha256`, `bindings` ([label, path, commit, sha256] ×4), `q3_commits`, `refs` ({ref: commit}), `shallow` (sorted commits in `.git/shallow`), `git_config_keys`, `git_dirs`, `admissions` ({name: sha256}), `frozen_t1_sha256`, `inventory_sha256`, `top_level`, `world` (synthetic origin and full clone) and `code_sha256`. The commits/SHAs are **synthetic** (the patched S3 constants), so a host checker fed this job must be given `bindings`/`q3_commits` instead of the production pins. Two runs give identical bindings, refs, shallow lists, objects and files; only `repo/.git/index` (its stat cache) differs. In-process, `build_guard_job(base, host, round_, attempt, preflight)` returns the same dict (it patches the module constants; call `restore()` afterwards).
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
  2. verification through safe_input (`verify_clone`, below), and P present;
  3. `checkout --detach P` and a clean status;
  4. a receipt, `repo-full-PREPARE.json`.

  This is the only git invocation outside `si.git_run`, because `git_run` disables every network transport. I did **not** run it for real, because creating the real `repo-full` is outside this directory. The tests run it against a file:// origin.
- **Full-clone verification is a mandatory, live precondition (r3, END-FULL-F4).** `S9.require_full_clone(commits)` builds its own read-only policy over `REPO_FULL` and runs `verify_clone` **every time**, as the first step of every entrypoint that reads the dedicated clone or vouches for an artifact built from it: S9 `locate`, `build`, `verify`, `equivalence` (and `prepare-clone`), S3 `build` and `verify`, S1b when `--repository` is `REPO_FULL`, and therefore S10 (through S9.verify / S3.verify) before any login. Nothing is inferred from the directory name or from `repo-full-PREPARE.json` (the receipt is not bound: the existing runner clone has none, and a receipt cannot vouch for the clone's current shape). The live checks:
  - identity: the clone root, `.git`, `.git/objects`, `.git/objects/pack` are canonical real directories (no symlinked ancestor, no gitfile); git itself (`rev-parse --absolute-git-dir --is-bare-repository --is-shallow-repository --show-toplevel`) reports `<REPO_FULL>/.git`, not bare, not shallow, work tree `REPO_FULL`;
  - absent in any form (`CLONE_ABSENT`): `.git/hooks` (any hooks dir, executable or empty), `.git/shallow`, `.git/info/grafts`, `.git/objects/info/alternates`, `.git/objects/info/http-alternates`, `.git/commondir`, `.git/config.worktree`;
  - config: exactly `CLONE_CONFIG_KEYS`, each once, in a strict grammar (UTF-8; `[section]`/`[section "sub"]` alone on a line; `key = value` with no quote, backslash or comment character): `remote.*.promisor`, `remote.*.partialclonefilter`, `core.partialclonefilter`, `extensions.partialClone`, includes and drivers refuse, as do a variable after a section header (`[remote "origin"] promisor = true`, which git honours), a bare `promisor` key, old-style `[remote.origin]`; origin URL, `repositoryformatversion = 0`, `bare = false`;
  - packs: only `pack-<oid>.{pack,idx,keep,bitmap,rev}`; a `.promisor` marker (or a `tmp_pack_*`) refuses;
  - no `refs/replace` refs; every given commit present (S9.verify also binds the runtime manifest's commit to the verified clone).

  The refusal happens before any object content or any other input is read (`tests/test_f4.py`). Each manifest/result records the facts as `full_clone`.
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

`tests/fixture_guard_job.py` (r3; used by `tests/conftest.py`) builds a synthetic world in one `tempfile` directory under `/tmp` (neutral names, removed at the end):
- a synthetic origin repository (branch `main`) with the production paths for the pin lists, the K4S manifest, e4v3, the E1 link, an E5 stand-in (`scripts/compare_native_public_games.py`, with only its OID patched as r3's own tests do), FROZEN-T1, the T1 modules, seed/join commits, history.json, the E3 admissions (commit P) and END-JOB (commit X);
- synthetic frozen modules that implement the frozen rules;
- the full clone, created by **`S9 prepare-clone`** itself from a `file://` origin.

Constants that bind production bytes (pins, commits, REPO_FULL, Q5_SOURCE, PRODUCTION_PINS) are patched for the session only; `ORIG` keeps the production values, and tests check them.

**Fake hosts.** A fake `ssh` runs the remote words under `/bin/sh` in a **user+mount+UTS namespace** (`unshare -Urmu`): `/mpac/sdicks02` is a bind mount of a temp tree, and the hostname is the target host. The shipped safe_input programs run **unmodified**, including their node-name check, and the real `/mpac/sdicks02` is invisible to them. The fake can inject faults: a refused login, trailing junk, a flipped base64 byte, and fake tools.

**Conformance kit (F1).** Each kit case builds a fresh synthetic tree under a `tempfile` directory in `/tmp`, substitutes the alias before the entrypoint starts, and runs the entrypoint in a fresh interpreter (`-I -B`, plus `-O` when the suite runs under `-O`) under `kit_harness.py`, whose recorders (`os.open/read/pread/readv`, `open`, `io.open_code`) and the kernel atime of every watched inode, plus canary execution markers, must show zero canary consumption.

No test reads a real repository, a T1 tree, a game or receipt file, or a host. Tests write only under tempfile directories in `/tmp`. Mutation copies live in `/dev/shm`, and the confinement probes name `/dev/shm/k4s-*-never` paths.

| Interpreter | Normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 (pytest 9.1.1) | **691 passed** (63.3 s) | **691 passed** (62.1 s; 1 warning) |
| `/usr/bin/python3` 3.8.10 (pytest 8.3.5 from `/dev/shm/s3s9s10r2-pytest38`) | **691 passed** (56.6 s) | **691 passed** (75.9 s; 1 warning) |

These are the final runs, 2026-10-13 00:21:28–00:25:48Z, on the final sources (`nice -n 19 taskset -c 16-23`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`). The only `-O` warning is pytest's `PytestConfigWarning` about assertions in non-test modules; the tests use explicit `ok()`/`refused()` checks, never `assert`, and the kit subprocesses run under `-O` too.

Per file (collected): common 30, F1 324, F4 147, F2 fixture 8, flow 5, S1b 27, S3 42, S9 53, S10 55 = **691** (r2: 211; r3 adds 1 split common test, 324 + 147 + 8 new).

Commands: `cd /tmp && PYTHONDONTWRITEBYTECODE=1 nice -n 19 taskset -c 16-23 PY -B [-O] -m pytest -q -p no:cacheprovider $D/tests`. For 3.8, add `PYTHONPATH=/dev/shm/s3s9s10r2-pytest38` (pytest 8.3.5, a local copy; no network).

**r3 regression tests:** END-FULL-F4 `tests/test_f4.py` (Sol's probe: `test_every_entrypoint_refuses_a_corrupted_clone[promisor-s9_build|promisor-s9_verify|promisor-s9_equivalence]`), END-FULL-F2 `tests/test_fixture_guard_job.py`, END-FULL-F1 `tests/test_f1.py`; RESPONSE-r3.md lists every name.

**Sol's earlier (package-2) probes as regression tests (unchanged):**

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

## Mutation check (adoption points and the r3 guards, under -O)

`tests/mutate.py` defines **106** single-edit mutants (r2's 82, with C01–C03 retired because the r2 loader they targeted is gone and N11 retargeted to `CLONE_ABSENT`, plus **F01–F16** for END-FULL-F4 and **G01–G11** for the END-FULL-F1 glue), and `--check-edits` validates that each target occurs exactly once. For each mutant it:
1. copies the code, tests, kit and RC-6 file into a fresh `/dev/shm/s3s9s10-mut-*` directory (removed afterwards);
2. **r3:** re-pins the sibling chain of the copy with `tests/k4s_adopt.py`, so the mutant is judged by the suite and not merely refused by the pin;
3. runs the whole suite with `-x` and `-O`, with cwd `/tmp`, and records KILLED when the suite fails.

NULL controls (unmodified copies) are interleaved and must SURVIVE. Snapshots of `/mpac/sdicks02`, `…/repos`, `…/k4s-runner`, `…/run-r1` and `…/end-prep`, taken before and after, must be equal: no write outside `/tmp` and `/dev/shm`. The canonical block's own internals are not mutated here: any edit is killed by the byte-equality test, and bootstrap-r1 ran its own campaign on the canonical text.

**Final r3 campaigns (`MUTATION-RESULTS-s3s9s10-r3-*.json`; each records the SHA-256 of the six code files, equal to `SHA256SUMS`):**

| Interpreter, `-O` | Window (UTC) | Killed | Not killed | NULL controls | `outside_writes` |
|---|---|---:|---|---|---|
| k4s-freeze 3.12.12 | 2026-10-13 00:26:06–00:43:14Z | **103/106** | N13, N20, X17 (equivalents) | 4/4 survived | false |
| /usr/bin/python3 3.8.10 | 2026-10-13 00:43:14–01:08:07Z | **103/106** | N13, N20, X17 (equivalents) | 4/4 survived | **true — concurrent activity, not this package** (below) |

**The 3.8 campaign's `outside_writes: true`.** The flag compares the *names* in `/mpac/sdicks02`, `…/repos`, `…/k4s-runner`, `…/run-r1` and `…/end-prep` before and after. During the window, `/mpac/sdicks02` gained `probe5/` (harness/, patch/, screen/, trees/) and `l26w/` (`canonical-20261012{c,d}.code-manifest.json`, ref-harness/, tools/, verify_manifest.py), created 01:04:39–01:06:46Z, with an mtime bump of `/mpac/sdicks02/repos` at 01:04:44Z and no newer entry there (an entry moved out). These are another thread's work on this shared host: neither name occurs anywhere in this package (`grep -r`), no mutant copy or test path is under `/mpac` (copies in `/dev/shm/s3s9s10-mut-*`, tests and kit trees under `/tmp`), and the 3.12 campaign over the same 106 mutants reported no change. Identical kill sets in both campaigns. I did not rerun the 3.8 campaign.

Not killed, all documented as **equivalent** in `mutate.py` `EQUIVALENT` (a stronger independent layer masks each one, and the suite exercises that layer):
- **N20**, the complete-runtime check: the frozen `runtime_pins` cross-check runs on every build and refuses the same incomplete runtime.
- **X17**, the tiers-pins expected SHA: a changed `tiers-pins.json` is also refused by the side-file read, whose expected SHA is derived from the operator's tiers SHA, and by the receipt's `manifest_sha256` binding.
- **N13** (r3), the explicit `.promisor` pack refusal: the new pack-name allowlist (F11, killed) refuses every non-pack name in the pack directory, `.promisor` included.

Every **new** r3 guard has a mutant killed by a named test: F01–F07 (the precondition at S9 build / verify / equivalence / locate, S3 build / verify, S1b) by `test_f4.py::test_every_entrypoint_refuses_a_corrupted_clone` / `test_locate_cli…`; F08 `CLONE_ABSENT`, F09 same-line variable, F10 `bare`, F11 pack names, F14 `.git` real dir, F15 UTF-8 by the kind matrix and grammar tests; F12/F13 by `test_commits_must_be_in_the_verified_clone`; F16 (git's own view, otherwise masked) by the fault-injection `test_git_view_must_agree`; G01 by `test_existing_unpinned_module_is_never_reused`; G03/G07/G08/G09 by `test_entrypoint_refuses_a_foreign_end_prep_common`; G02/G04 by the kit's non-normalized scenarios; G05/G06/G10/G11 by the sys.path/raw-I/O static checks, the tag test and the tamper test.

**Campaign history (r3):** a targeted run of F01–F16 found F16 surviving (masked by the file checks); `test_git_view_must_agree` was added and kills it. The G mutants were all killed in their first targeted run. The two final campaigns are in the table. Each campaign's `new_tmp_leftovers` field lists `/tmp/si-git-home-*` names present at its end; they belonged to concurrent safe_input users on this shared host (other workers' in-flight `git_run` homes) and were gone moments later — no mutant left anything behind (every copy and kit/world directory was removed).

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

  **r3 real reads (all read-only, none outcome-bearing):** `git show origin/main:` of the committed receive-SHA erratum (shipped as a byte copy); a listing of `run-r1/end-prep/` (to confirm the runner's `repo-full` has no `repo-full-PREPARE.json`) and of `repo-full/.git` (top level and the pack directory's names), plus its `.git/config` (it holds exactly the plain-clone key set and the GitHub origin, so the F4 checks are expected to accept it; they were not run against it); bootstrap-r1's canonical text, kit and PROGRESS/marker; and the immutable r2 code files, for a kit probe of the r2 loader (synthetic canaries only).
- **r3 residuals.** The interpreter reads the entrypoint script itself from the path the operator types, before any bootstrap; everything after it is confined (kit ancestor scenarios). Bind mounts stay under the accepted single-operator mount assumption. The F4 recheck runs before every use but cannot exclude a concurrent change of the clone between the recheck and a later git call (the accepted check/use residual); every git call still re-runs `_git_preflight`.
