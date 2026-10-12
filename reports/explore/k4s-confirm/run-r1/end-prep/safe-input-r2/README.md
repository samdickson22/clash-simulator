# safe_input r2: the shared gate for PREREG-K4S END tooling (rulings P2-1, P2-4, D1–D4)

**Status: CANDIDATE, not reviewed.** It needs a Sol review before any component adopts it. It is offline only: it touched no host and made no commit or push. Built on 127x05, 2026-10-12, from `safe-input-r1/` (copied, then changed; r1 is untouched). [ADOPTION.md](ADOPTION.md) maps every component call to its replacement. `PROGRESS-r2.md` is the resume log.

r2 adds five things to r1 and keeps everything else:
- the P2-4 git helper and a two-phase tree-then-blob API (closes S2-R3-F1, S4-R3-F1 and S4-R3-F3);
- the shared case-insensitive family denylist (S4-R3-F2);
- E1 materialised (D2);
- the S6-only D3 hash-only role;
- the D4 remote `receive` mode.

| File | Purpose |
|---|---|
| `safe_input.py` | The layer: stdlib only, Python 3.8+, Linux. A library plus a small CLI. |
| `tests/conftest.py` | Loads the module (or a mutant). Syscall recorder, audit hook, canary helpers (unchanged from r1). |
| `tests/test_*.py` | 472 tests. The r1 files are kept, with the changes listed under "Changes to r1 tests". New in r2: `test_families.py`, `test_git_r2.py`, `test_d3.py`, `test_receive.py`. |
| `tests/mutate.py` | Mutation driver: `--jobs N`, `--check-edits`, and NULL controls (unmodified source) that must survive. |
| `MUTATION-RESULTS-py38-O.json`, `MUTATION-RESULTS-py312-O.json` | Mutation results. |
| `D5-TRACKED-FAMILY-MATCHES.txt` | D5: tracked paths at origin/main that match the family denylist (names only), marked D1 member or non-member. |
| `ADOPTION.md` | Per-component mapping. |
| `SHA256SUMS` | SHA-256 of every file above, plus PROGRESS-r2.md. |

## 1. Unchanged from r1 (still guaranteed)

Every check is an explicit `raise Refusal(code, reason)`, never an `assert`, so it holds under `-O`. The following r1 behaviour is unchanged:
- Policy and roles with no defaults; names are checked before any syscall.
- Canonical roots, the component-wise `O_DIRECTORY|O_NOFOLLOW` walk, and the descriptor gate (`fstatat`, then open with `O_NOFOLLOW|O_NONBLOCK`, then `fstat`: regular file, same dev/ino, `st_nlink == 1`, size within the cap) before any byte is read.
- Exact-size reads that refuse on growth or shrink; an optional expected SHA; strict JSON.
- `walk_tree`, which refuses instead of pruning.
- E4 is hash-only: `hash_e4`, `copy_e4`, `git_hash_e4`.
- The exclusive `Writer`: `mkdir_excl`, `create_excl`, and `publish_excl` via `linkat`; refusal receipts.
- `run_checked`: explicit argv and environment, bounded output, watchdog and process-group kill, the lingering-descendant check, and rc checked before stdout is visible. `ps_checked` and `hostname_checked`.
- The remote reader (`remote_check`): two passes, all items name-gated first, and a strict parser.
- The CLI (`create-excl`, `mkdir-excl`, `publish-excl`).

The r2 code still covers every item on Sol's S2/S4-r3 "must preserve" list that sits inside this layer: lexical refusal before access; role and root validation; regular and nlink checks at both the walk and the descriptor; E1's exact committed alias with an independently gated target; E4's four opaque roles; exclusive outputs and plain copies; and status-preserving subprocesses. Component-level items stay with the components. These are S2's profile exclusivity, frozen-closure verification, artifact and S1 bindings, test-only stamps, and clock-join refusal.

New refusal codes: `indirection` (static git repository or config redirection), `git` (wrong object header or type, or a commit id that is not a commit) and `stream` (receiver framing).

## 2. Shared family denylist (P2-4; S4-R3-F2)

`name_gate` checks every component of the full absolute path. Each component is casefolded and matched with `fullmatch` against the families below. In the patterns, `T(x)` means token x: start of the component or a non-letter before it, and end of the component or a non-letter after it.

| Class | Family | Pattern (casefolded component) | Exceptions |
|---|---|---|---|
| OUTCOME (never grantable) | games | `T(games)`: `games`, `Games`, `.games`, `games.tmp`, `old-games`, `x_games_y`, `games2`, `check_games.py` | none |
| | hub-blocks | `T(hub[-_.]?blocks?)` | none |
| | complete-json | `.*complete.*\.json.*` (complete.json, `.tmp`/`.swp`, `*-complete.json`, `end-complete.json`, `complete-v2.json`, `incomplete.json`, `*completed*.json`) | E4: final component exactly `complete.json` at the four exact paths. D3: exactly `end-complete.json`. |
| | interference-json | `.*interference.*\.json.*` | none |
| | hub-ack-json | `.*hub[-_.]?ack.*\.json.*` (includes `hub-ack.returned.json`, `hub-ack-smoke-0001.json`) | none |
| | end-raw-json | `.*end[-_.]?raw.*\.json.*` | D3: exactly `end-raw.json` |
| END-CLAIM (grant `end-claim-exact`, exact names only) | end-job | `(start or non-letter) end[-_.]?job.*` (END-JOB.json, `.END-JOB.json`, `x-END-JOB.json`, END-JOBS.json) | |
| | end-final | `(start or non-letter) end[-_.]?final.*` | |
| | attempt-json | `.*attempt[-_.].*\.json.*` (attempt-00.json, attempt-claim.json) | |

The r1 rules still apply on top of the families:
- `k4s-confirm-*` reporting jobs (grant `reporting-job-exact`);
- `k4s-end-guard-*` (grant `guard-job`);
- the strict END pair `k4s-confirm/end` (grant `end-json-exact`; exact `.json` names inside it only; a root can never be inside it);
- the five FROZEN-T1 launch namespaces;
- `/mpac/sdicks02/repos/clasher-v4-cache`;
- `/mpac/sdicks02/jobs` on 127x04.

The E4 and D3 leaf exceptions apply to the final component only and only to the exact names (`Complete.json`, `END-RAW.json` and `end-raw.json.tmp` refuse). Exact-name grants are checked when the Role is built. Look-alikes that stay outside every family include `endgames`, `gamestate.py`, `game-001.json`, `incomplete/` (a directory with no `.json`), `attempt1.log`, `backend-jobs.py` and `END-raw-phases-20261011/`.

## 3. The git helper: every git call (P2-4; S2-R3-F1, S4-R3-F1)

`git_run(repo, args)` is the only place git is spawned. `git_checked`, `git_ls_tree`, `git_show_file`, `git_plan`, `_git_object` and the E1/E4 helpers all call it.

**Environment.** It is exactly `GIT_FIXED_ENV` plus a fresh empty `HOME` (a `tempfile.mkdtemp`, removed afterwards; if git left anything in it, the call refuses) with `XDG_CONFIG_HOME` inside it, plus allowlisted author/committer keys. Nothing is inherited: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_INDEX_FILE`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT/KEY/VALUE`, `GIT_REPLACE_REF_BASE` and every other variable are dropped. The fixed set is:
- `GIT_NO_REPLACE_OBJECTS=1`, `GIT_OPTIONAL_LOCKS=0`;
- `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_ATTR_NOSYSTEM=1`;
- `GIT_TERMINAL_PROMPT=0`, `GIT_LITERAL_PATHSPECS=1`, `GIT_PAGER=cat`, `GIT_NO_LAZY_FETCH=1`, `GIT_ASKPASS=/bin/false`;
- `LC_ALL=C`, `PATH=/usr/bin:/bin`.

**argv.** `/usr/bin/git --no-replace-objects --no-optional-locks -c core.hooksPath=/dev/null -c core.fsmonitor=false -c protocol.allow=never [-c protocol.file.allow=always if declared] --git-dir=<declared> [--work-tree=<declared>] <allowlisted subcommand> …`. The rc must be in `ok_rcs` (default 0) before stdout is returned, and the output is bounded.

**Static preflight, before git runs** (`GIT_COUNTERS["runs"]` proves that git did not run):
- the work tree must be canonical;
- the git dir must be a real directory, so a gitfile or a symlinked `.git` refuses;
- a `commondir` file needs a declared `common_dir` with the same target, and a declared `common_dir` needs the file;
- `objects/` must be a real directory;
- `objects/info/alternates`, `objects/info/http-alternates`, `info/grafts` and `shallow` refuse unless declared in `GitRepo(allow=…)`;
- `config` and `config.worktree` refuse if they declare `[filter]`, `[diff]`, `[merge]`, `[include]` or `[includeIf]`, or set `core.worktree`, `fsmonitor`, `hooksPath`, `sshCommand`, `gitProxy`, `askPass`, `editor`, `pager`, `alternateRefsCommand`, `alternateRefsPrefixes` or `attributesFile`. Section and key names are casefolded; values are not interpreted.

**Positive controls on this host's git 2.25.1, each paired with the helper assertion** (`tests/test_git_r2.py`). With raw git, an inherited `GIT_DIR` returns the foreign canary, as does `GIT_REPLACE_REF_BASE`. Inherited alternates and an alternates file both make the foreign canary object readable. `GIT_INDEX_FILE` lists the foreign index. `GIT_OBJECT_DIRECTORY` redirects the store. `GIT_CONFIG_PARAMETERS`, `~/.gitconfig`, XDG config, repo hooks, repo `core.fsmonitor` and a repo filter driver each run code or change output. A static `refs/replace` substitutes the canary even for `cat-file --batch <original oid>`. A gitfile redirects to a foreign repo. In every case the helper returns exactly the true bytes, refuses before git runs, or runs no code.

**Finding: on git 2.25.1, `--no-replace-objects` does NOT disable `info/grafts`.** The grafts control rewrites history with the flag set, so the static grafts refusal is load-bearing.

`GIT_CONFIG_COUNT` (git ≥ 2.31) and `GIT_CONFIG_GLOBAL` (git ≥ 2.32) are unsupported on 2.25.1. They are still scrubbed or set; the empty `HOME` makes the global config moot.

**Object reads (phase 2).** `_git_object` is the only content read. It runs `cat-file --batch` for one object id. The reply header must be exactly `<oid> <type> <size>` of the expected tree entry, the body exactly `size` bytes plus LF, and the body must re-hash to the oid. All of this is checked before the bytes go to any caller. `GIT_COUNTERS["object_reads"]` counts these reads.

## 4. Two-phase tree-then-blob API and D1

`plan = git_plan(policy, role, repo, commit, members=None|exact paths|predicate)`.

**Phase 1** first checks that `commit` is a commit (`cat-file -t`), then runs `ls-tree -r -l -z --full-tree`. It screens all metadata to completion and refuses the whole tree on any of the following:
- syntax errors or duplicate paths;
- E4 fail-closed: any component exactly `complete.json` that is not one of the four exact E4 paths, or an E4 path that is not mode 100644 with its pinned blob OID (`E4_GIT_BLOB_OIDS`). This applies to members and non-members alike.
- for members only (everything when `members` is None): the family denylist and role allowlist (E-list exceptions only); non-blob entries, gitlinks and modes other than 100644/100755; a symlink other than the exact E1 entry (mode 120000, oid `E1_LINK_OID`, size 28); size over the cap;
- a missing E1 target, or a target that is not a regular, gated blob within the cap.

Phase 1 reads no object.

**Phase 2** is `plan.read(path_or_entry, expected_sha256)`, `plan.hash_e4(entry)`, `plan.e1_check()`, `plan.e1_verify_shipped(policy, role)` and `plan.export(writer)`. It reads planned entries only, each through `_git_object`.

**D1.** `members` is the caller's frozen membership, computed from metadata alone. For S9 it is `runtime-pin-r2 files ∪ every *.py`. Non-members are never read. A family name inside the member set refuses unless it is E-listed. A predicate selects only on an exact `True`; an exact-name list refuses if any name is missing.

The regressions use an instrumented counter and a git wrapper that logs argv and stdin. A refusal-worthy entry anywhere aborts with zero object reads and no `cat-file --batch`. The tested entries include:
- S4-R3-F3's reproduction: four E4 stand-ins, then `zz-outcome/complete.json`;
- late `games/`, hub-ack, END-FINAL, `attempt-*.json`, interference, symlink and oversize entries;
- a wrong-mode E4, a changed-identity E4 blob, and a late gitlink.

In the D1 export, no non-member object id is ever requested.

## 5. E1 materialised (D2)

`git_e1_check(plan)` reads the committed entry, which phase 1 has already pinned to mode 120000 and `E1_LINK_OID` (`a79f7391…` = sha1 of `blob 28\0examples/visualize_battle.py`). It reads the link blob with `cat-file` and never follows it, requires the text to be exactly `examples/visualize_battle.py`, and reads the target blob with its OID verified. `plan.export()` writes `visualize_battle.py` as a regular 0444 file whose bytes are the verified target blob; `e1_mode` must be `'copy'`, and r1's `'symlink'` now refuses.

`git_e1_verify_shipped(plan, policy, role)` opens the shipped `visualize_battle.py` through the descriptor gate, so a symlink, hard link or special file refuses. Its bytes must hash equal to the gated target blob.

r1's `check_e1`, `walk_tree`'s root-level E1 symlink, and `Writer.create_e1_symlink` are kept for compatibility. Under D2 the runtime does not use them.

## 6. D3: the S6-only hash-only role

A role can carry exemption `D3` only if all of these hold:
- its name starts with `s6-`;
- it is a read role with exact names only, no other exemption and no grant;
- its root is exactly `D3_RECEIVE_BASE/<127x03|127x04>`, where `D3_RECEIVE_BASE` is `/mpac/sdicks02/k4s-runner/run-r1/end-received`, S6's attempt parent;
- every name is `<attempt>/durable-measurement/[…/]end-raw.json` or `…/end-complete.json`.

`hash_sealed_end_member(policy, role, rel, seal_sha256)` requires `seal_sha256` (64 lowercase hex) and gates every other component by name. It then requires both seal files (`receipt-manifest.json` and `receipt-manifest.sha256`) to pass the descriptor gate; they are opened but not read. It hashes the member through the descriptor gate and refuses `sha` unless the digest equals the caller's seal-manifest SHA. It returns `{path, sha256, size}` and never bytes.

Through every ordinary read API, and through any other role, these names refuse by family before any syscall.

## 7. D4: the remote receiver

`remote_receive(remote_policy, dest_role, local_policy, files, dirs)` makes one ssh login. The remote command is `nice -n 19 /usr/bin/python3 -I -S -c '<RECEIVE_BOOTSTRAP>' <len> <program-sha256> <manifest-sha256>`. Every other word is `[A-Za-z0-9/-]`. The single-quoted bootstrap is a fixed constant with no quote inside. It reads exactly `<len>` program bytes from stdin and exits 4 unless they hash to the argv SHA-256; only then does it run them.

The program is `_CORE` (the same gate code) plus the receive main, both py3.8 stdlib. It is a separate program from the r1 read-only reader, which keeps its own reviewed semantics; the two share `_CORE` byte for byte. It reads a framed stream from the same stdin buffer: an 8-byte length, the canonical manifest JSON (whose SHA must equal the argv commitment), the files' bytes in manifest order, and then EOF.

**Before any syscall, the program:**
- validates the manifest strictly, with the validator shared verbatim with the local sender: exact keys; normalized relative names; no `..`, absolute paths, duplicates or casefold duplicates; each directory after its parent and each file inside a declared directory; modes 0444/0555 only; total within `max_total`; E4 only at an exact path with its pinned SHA;
- name-gates the root and every name;
- checks the host.

**Then it creates:**
- the destination root, exclusively (`mkdirat`) under its canonical parent; an existing name of any kind refuses, and nothing is ever overwritten or deleted;
- the directories, with `mkdirat`;
- the files, with `O_CREAT|O_EXCL|O_NOFOLLOW` via dirfd, each streamed exactly `size` bytes, hashed, fsynced, and `fchmod`ed.

A short stream, a SHA mismatch or any extra byte refuses with `stream`/`sha`; partial files are kept. On success the program emits one JSON receipt with per-file `rel/size/sha256/nlink/mode/dev/ino`. On refusal the receipt lists what it had already created.

**Local side:**
- every source name and every destination name is gated before ssh starts;
- every source passes the descriptor gate, with its expected size, before ssh starts;
- sizes and SHA-256 are mandatory;
- each source is streamed from a gated fd with its SHA re-checked; a mismatch raises the local `Refusal`;
- `parse_receive_receipt` validates rc, the single line, the exact key sets, the manifest SHA, host/root/dirs, and every file's rel, size, SHA, `nlink == 1`, regular file and mode.

## 8. Constants and pins

- `constants_fingerprint()` = **`6661ca0b7635a3a66d8ab6612b5617435f06128d6e18b6bf96e25594a624d367`**. Besides r1's constants, it now covers the families, E4 blob OIDs, E1 link OID, D3 constants, git policy, refused config and receive bootstrap. Adopters pin it.
- `remote_program_sha256()` = **`ff6f9fa4ffb5d91b60bcbc516454d4de55dd1990879200e95649f9d701edc5e6`** (r1 was `5b15dfe7…`; the shared `_CORE` changed) and `receive_program_sha256()` = **`d259318a5a27406ba57a8bca310fa5afa5935b4765a0d3482e151398fc2a30e0`**.
- `E4_GIT_BLOB_OIDS`, from `git ls-tree` at origin/main (metadata only, no blob read):

| Entry | Blob OID | Source |
|---|---|---|
| E2 | `7c9502037a75263dcfaaf5ab33666d2b8382a201` | ls-tree only; no independent source |
| emulator-host | `a2f94dd0ce1ab1f4b233d63201a454318dc0ecff` | matches SOL-REVIEW-END-PKG2-r1 |
| gap | `9e15e1f73e4f3dd05fa635da0f621851a52c873a` | matches SOL-REVIEW-END-PKG2-r1 |
| supplemental | `1a73d2e1c54ab69fac9433047a8c957c3693d055` | matches SOL-REVIEW-END-PKG2-r1 |

  **Coordinator ratification requested.**

## 9. D5: tracked files that now match the family denylist

`D5-TRACKED-FAMILY-MATCHES.txt` was produced at origin/main **f15691b555e561c876e1f6123a21b840f4b4d736**. Names come from `git ls-tree -r -z --name-only`; no matching blob was read. **371** of 11,722 tracked paths match a family:
- 271 games;
- 71 complete-json, 4 of them the exact E4 entries;
- 16 hub-ack-json;
- 13 attempt-json.

D1 membership was computed with the frozen rule, `runtime-pin-r2.json` "files" ∪ every `*.py`. The pin list has 1,557 names; it was read through `git_show_file` pinned to `f81f3655…`. On that basis, **361 matches are non-members** and are never read under D1. These include the two `hub-ack.returned.json`, `tiers-complete.json`, the `*-complete.json` receipts, `hub-ack-smoke-*.json`, and `attempt-*` receipts.

**10 are D1 members:**
- E2 (`imitation/model/receipts/throughput-0935/complete.json`), which is E-listed and therefore fine;
- **eight `*games*.py` scripts**: `reports/explore/k4s-confirm/check_games.py`, `…/k4s-confirm/qualify_games.py`, `…/engine-speed/canonical/certify_games.py`, two `…/exit-r3/round2/…/reduce_games.py`, `…/search-tuning/timing_games.py`, `scripts/collect_public_development_games.py`, `scripts/compare_native_public_games.py`;
- **`tests/fixtures/native_friendly_completed_15_535_86.json`**.

**A D1 export at this origin/main therefore refuses (by name, in phase 1) until the coordinator rules.** The options are exact-path E-list entries for these nine, a narrower games/complete family, or a membership change. The layer does not decide.

## 10. Verification (127x05, 2026-10-12; every number is from this session)

**Suite.** Every command ran under `nice -n 19` with `PYTHONDONTWRITEBYTECODE=1`, `-B` and `-p no:cacheprovider`, normally and with `-O`. pytest was installed only into `/dev/shm`, with `uv pip install --target`, and supplied through `PYTHONPATH`: 8.3.5 for 3.8 and 9.1.1 for the e4v3 venv. k4s-freeze already has 9.1.1. No venv was modified.

| Interpreter | Normal | `-O` |
|---|---|---|
| `/usr/bin/python3` 3.8.10 | 472 passed | 472 passed (1 warning) |
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | 472 passed | 472 passed (1 warning) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 | 472 passed | 472 passed (1 warning) |

Under `-O`, the only warning is pytest's `PytestConfigWarning: assertions not in test modules … (are you using python -O?)`. The tests use explicit `ok()`/`refusal()` checks, not asserts.

**Mutation.** `python -B -O tests/mutate.py --jobs 12 --recheck-without test_cli_publish_ps.py::test_constants_fingerprint_is_pinned` ran against `safe_input.py` `f9ca4926…`; the SHA is recorded in each JSON.
- **3.8.10 -O: 244/247 killed. k4s-freeze 3.12.12 -O: 244/247 killed.**
- The 3 not killed (Q11, SD01, SD08) are the documented equivalent mutants. Each is masked by a stronger earlier layer, and each joint mutant (Q11J, SD01J, SD08J) was KILLED in the same run. The `equivalent_survivors` annotation in each JSON was added after the run, from that run's data.
- Every campaign interleaves 6 NULL controls (unmodified source), which all SURVIVED. So kills are not artefacts of parallel load.
- 15 mutants were first killed only by the constants-fingerprint pin. Re-run with that test deselected, all 15 were KILLED by behavioural tests on both interpreters (`verdict_without`).
- Each mutant runs the whole suite (`-x`) on a copy in a fresh `/dev/shm/safe-input-mut-*` directory, which is removed afterwards. Each edit target must occur exactly once (`--check-edits`: 247 valid).
- Equivalents carried from r1: `rel.startswith('/')`, the growth probe alone, `O_NOFOLLOW` on `O_EXCL`, and `O_NOCTTY`. New in r2: replace-off flag alone and env alone, the `fsmonitor` override alone, the commondir "declared" check alone, the `objects/` real-directory check, the receive post-create nlink check, the E1 materialised-copy re-check, `rel in role.exact` for D3, Q11, SD01, SD08, and RV20's SHA-format part. Reasons are in `mutate.py` `EQUIVALENT`.

**Mutation history, disclosed.** The first 3.8 campaign was **void**. A test (`test_helper_home_is_fresh_and_removed`) compared the shared temp-directory listing, which concurrent suites change, so 5 of 6 NULL controls failed and 122 kills were attributed to that test. I fixed the test so it checks only the per-call HOME, then re-ran. That second run gave 238/244, with six survivors:
- three were equivalent: Q11, SD01 and SD08;
- three were real test gaps: GH14's test was refused earlier by a leftover alternates file, and nothing exercised extra receiver argv words (RV20) or a forbidden directory-only manifest (RV21).

I closed the three gaps with new controls, then ran the final campaigns above.

**Changes to r1 tests** (all intended; r2 semantics are stricter):
- `test_canaries_exemptions`: the END role now also needs `end-claim-exact` for `END-JOB.json`.
- `test_names_policy`: END-JOB needs both grants. `main01-complete.json` and `hub-ack-smoke-0001.json` moved from look-alike to refused, and new look-alikes were added.
- `test_git`:
  - the reviewer-probe test was renamed, because pytest's tmp dir would contain the token `games`;
  - "no blob read" is now proven by "no `--batch`" plus the object counter, since a `cat-file -t` commit-type probe now precedes `ls-tree`;
  - a wrong E1 link refuses in phase 1;
  - E4 OIDs are patched along with the SHAs;
  - `e1_mode='symlink'` refuses (D2);
  - the fake gits answer the commit probe and speak the `--batch` format;
  - a forged oid refuses as `git`.
- `test_subprocess`: the fake-git rc test creates `.git/objects` so that it passes the preflight; a broken-stdin test was added.
- `test_cli_publish_ps`: the fingerprint pin is the r2 value.

**Write confinement.** Tests wrote only under pytest's `tmp_path` (`/tmp/pytest-of-sdicks02/`). Mutation runs wrote under `/dev/shm/safe-input-mut-*`, and the git helper's per-call HOME is a `tempfile.mkdtemp` that is removed. **Disclosed:** until the final run, the control that makes a fake git plant a file in its HOME (the helper correctly refuses and keeps that HOME as evidence) left one `/tmp/si-git-home-*` per suite run. That is tempfile's temp dir, so it stayed within the write boundary, but it was not cleaned up. There were 400; each held only the file `planted`, and all were removed. The test now points `tempfile.tempdir` at its own `tmp_path`. The matrix and both campaigns reported here were re-run after that change, and afterwards no `/tmp/si-git-home-*` remained. No real outcome, game, `complete.json`, reducer or verifier output was opened. The only reads of real repository content were:
- the static preflight of the clasher checkout, which reads `.git/config` names;
- `ls-tree` names and OIDs at origin/main;
- `runtime-pin-r2.json`, through the pinned `git_show_file`.

No ssh was used; every receive and remote test goes through a local fake-ssh shim that re-parses the remote words with `/bin/sh`. Nothing was committed or pushed.

## 11. Residuals and open points (disclosed)

1. **Accepted TOCTOU residual** (16:00Z ruling, restated 18:19Z). Another local actor can rewrite a file's bytes in place, without changing its size, during a read; this is undetected without an expected SHA. **All production reads must pass expected SHAs.** `hash_sealed_end_member` and `remote_receive` require them; elsewhere the layer cannot force a caller to pass one, so ADOPTION rule 0.6 makes it mandatory. The same residual covers a git repository changed concurrently between `_git_preflight` and git's own open of the files.
2. **D5 blocks a D1 export at the current origin/main** (§9); needs a coordinator ruling.
3. **E4 blob OIDs need ratification** (§8). Without them, a changed E4 blob would be refused only after it was read.
4. **Partial clone.** `/mpac/sdicks02/repos/clasher` is a promisor clone (its config has `promisor` and `partialclonefilter`; names only were read). Every transport is disabled, so a blob missing locally refuses instead of being fetched lazily. Production export needs a complete local object store. The real checkout passes the static `_git_preflight`: no alternates, grafts or shallow file, and a plain config.
5. **The frozen `k4s_logic.git_bytes()`** cannot adopt the helper (ADOPTION §S2). Until a non-frozen path replaces it, a frozen git read must be preceded by the same read through `si.git_show_file` with its expected SHA. Flagged for Sol.
6. **The config gate is name-level.** It parses section and key names, not values or quoting edge cases, and does not interpret `info/attributes`. Attribute-assigned drivers need repo or config definitions, which are refused. Built-in diff drivers are inert for the plumbing reads used here.
7. **The receiver trusts the grants in its manifest**, as the r1 reader did. Every non-grantable rule (outcome families, T1, perception, cache) is still enforced on the host. The role allowlist (patterns) is enforced locally only.
8. **The receiver's E4 pins are inside the shipped program.** Tests patch them by substituting the shipped source; production ships the real pins, and the bootstrap SHA binds them.
9. **Partial receives.** A refused receive leaves its exclusive `.partial` root and any partial files in place (never deleted), and lists them in the refusal. Cleanup is a separate, authorized step.
10. **Families are deliberately broad and fail-closed.** `incomplete.json`, `*completed*.json`, `check_games.py` and `attempt-claim.json` all refuse unless granted or E-listed.
11. **Mutable module dicts.** `E4_COMPLETE_JSON` and `E4_GIT_BLOB_OIDS` are plain dicts so that tests can patch them. Production code must never write them; `constants_fingerprint()` exposes any edit.
12. **Live behaviour is unverified.** Nothing ran against 03/04, real ssh, production commits, or real outcome or receipt files. The only real-repository operations were the static preflight of `/mpac/sdicks02/repos/clasher`, `ls-tree` names at origin/main, and one pinned `git_show_file` of `runtime-pin-r2.json` (a pin list, not outcome data).
