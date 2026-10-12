# safe_input r3: the shared gate for PREREG-K4S END tooling (rulings P2-1, P2-4, D1–D4, E5)

**Status: CANDIDATE, not reviewed.** r3 is r2 plus ruling E5 (COORDINATOR 2026-10-12 21:28Z) and nothing else. It needs a Sol review before any component adopts it. It is offline only: it touched no host, used no ssh, and made no commit or push. Built on 127x05, 2026-10-12, by copying `safe-input-r2/` and changing the copy. r2 is byte-identical afterwards (`R2-BASELINE-SHA256.txt`, checked with `sha256sum -c` in r2). [ADOPTION.md](ADOPTION.md) maps every component call to its replacement. `PROGRESS-r3.md` is the resume log.

§0 describes r3. §1–§11 are r2's text, edited only where E5 changes them (§2 exceptions, §8 pins, §9 D5, §10 verification, §11 residuals).

## 0. r3: ruling E5, exact exemptions for nine runtime members

**The constant.** `E5_RUNTIME_MEMBERS` is a tuple of exactly the nine (path, git blob OID) pairs in the ruling, verbatim. It lives in `_CORE`, so the shipped receive program carries the same pins. It equals `end-prep/E5-OIDS-ls-tree.txt` (ls-tree 104fa857) and the tree metadata at origin/main 02805c97 (§9). `E5_PATHS` is the import-time snapshot of its paths.
- `e5_blob_oid(rel)` returns the pin of an exact, case-sensitive E5 path, or None.
- It refuses `policy` unless the constant still lists exactly `E5_PATHS`, in order, each with a 40-hex OID. A test can therefore change OIDs only: a tenth entry, a moved, dropped or reordered path, a list instead of a tuple, or a malformed OID refuses.
- The constant is in `constants_fingerprint()`.

**The grant.** A role may carry exemption `E5`; `EXEMPTIONS` is now E1, E4, D3, E5. An E5 path is accepted only if all of these hold:
- the call asks for E5 (`_gate(..., e5=True)`, which only the E5 APIs below pass);
- the role carries `E5`;
- the path is exactly one of the nine.

`name_gate(..., e5_rel=rel)` then re-checks that `rel` is an exact E5 path and that the full path ends with `/<rel>`. Only then does it lift the OUTCOME family on the final component. Each E5 path matches a family in its leaf only: `games` for the eight scripts and `complete-json` for the fixture. Every other rule still applies: END-claim families, the namespaces, T1, perception, the cache repo and the role allowlist. **No family pattern is narrowed.** Any other match refuses by name, including a moved copy with the same bytes, a case variant (`Check_games.py`, `Scripts/…`, `….JSON`), or a tenth member.

**Opaque.** No API returns E5 bytes. `read_bytes`, `read_json`, `open_input`, `sha256_input`, `copy_input`, `git_show_file`, `GitPlan.read` and `git_blob` never pass the E5 flag. So an E5 path refuses there by family (`name`), or as an unplanned entry (`policy`). E5 bytes move only through these APIs:

| API | Use | Checks |
|---|---|---|
| `git_plan` phase 1 (`_screen_tree`) | an E5 member of an E5 role | Blob type, mode exactly 100644, OID equal to the pin, size within the cap. Metadata only, before any object is read. |
| `plan.hash_e5(entry)` (`git_hash_e5`) | planned E5 entries only | `_git_object` re-hashes the bytes to the OID. Returns `{path, git_oid, sha256, size}`. |
| `plan.export(writer)` | an E5 write role | A byte-exact 0444 file at the same path, created exclusively. |
| `hash_e5(policy, role, rel)` | on disk (S4's staged runtime, S5/S10 inventories) | The normal gates (canonical root, no-follow walk, descriptor gate with `st_nlink == 1`), then `sha1("blob <size>\0" + bytes)` must equal the pin. Returns `{path, git_oid, sha256, size}`. |
| `copy_e5(policy, role, rel, writer)` | on disk, into an E5 write role | A hash pass first, so nothing is created on a mismatch. Then a copy pass that is re-hashed (a mismatch refuses and the partial stays). Mode 0444. |
| `walk_tree` | an E5 role | E5 paths are listed under `e5`, not `files`. They must be regular files: a directory, symlink, FIFO or hard link at an E5 path refuses. |
| `remote_receive` and the receive program | S10 shipping the runtime | See below. |

`remote_receive` and the receive program handle E5 as follows:
- The manifest file record has a new key `e5`, a strict bool. `e5: true` is valid only at an exact E5 path, with mode 0444, and never together with `e4`.
- The sender requires `src_rel == dst` for E5. Before ssh starts, it runs `hash_e5` on every E5 source and requires the declared SHA-256 and size.
- The host program name-gates with the exact E5 path, re-hashes the received bytes to the pinned blob OID, and refuses on a mismatch. The partial file is kept and listed, as for a SHA mismatch.

**Not extended:** the r1 remote reader (`remote_check`). An E5 name still refuses there. No component in ADOPTION needs it for E5.

**D1 re-run (§9):** at origin/main 02805c97, metadata only, the member-set refusal count is **0**.

**Tests:** `tests/test_e5.py`, 76 tests. Each of the nine is accepted through a git plan and on disk. Each of these refuses: a changed OID (before any blob read, shown by zero `object_reads` and no `cat-file --batch`), a moved path, a tenth family-matching member, case variants, mode 100755, a symlink or a gitlink at an E5 path, and every parse or ordinary-read attempt on an E5 member. The receive path has its own tests. The mutation results are in §10.

r2 added five things to r1 and kept everything else:
- the P2-4 git helper and a two-phase tree-then-blob API (closes S2-R3-F1, S4-R3-F1 and S4-R3-F3);
- the shared case-insensitive family denylist (S4-R3-F2);
- E1 materialised (D2);
- the S6-only D3 hash-only role;
- the D4 remote `receive` mode.

| File | Purpose |
|---|---|
| `safe_input.py` | The layer: stdlib only, Python 3.8+, Linux. A library plus a small CLI. |
| `tests/conftest.py` | Loads the module (or a mutant). Syscall recorder, audit hook, canary helpers (unchanged from r1). |
| `tests/test_*.py` | 548 tests. The r1 and r2 files are kept, with the changes listed in §10. New in r2: `test_families.py`, `test_git_r2.py`, `test_d3.py`, `test_receive.py`. New in r3: `test_e5.py` (76). |
| `tests/mutate.py` | Mutation driver: `--jobs N`, `--check-edits`, and NULL controls (unmodified source) that must survive. |
| `MUTATION-RESULTS-py38-O.json`, `MUTATION-RESULTS-py312-O.json` | r3 mutation results. |
| `D5-TRACKED-FAMILY-MATCHES.txt` | D5: tracked paths at origin/main that match the family denylist (names only), marked D1 member or non-member, plus the r3 D1 re-run. |
| `D1-RERUN-r3.json`, `d1_rerun_r3.py` | r3: the D1 plan re-run against origin/main tree metadata (output and script). |
| `R2-BASELINE-SHA256.txt` | SHA-256 of every r2 file, taken before the copy. r2 still matches it. |
| `RUNNER-E4-OID-RATIFICATION.txt` | Carried over from r2 unchanged: the runner's independent check of the four E4 blob OIDs. |
| `ADOPTION.md` | Per-component mapping. |
| `SHA256SUMS` | SHA-256 of every file above, plus PROGRESS-r3.md. |

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
| OUTCOME (never grantable) | games | `T(games)`: `games`, `Games`, `.games`, `games.tmp`, `old-games`, `x_games_y`, `games2`, `check_games.py` | E5 (r3): the final component of the eight exact E5 script paths |
| | hub-blocks | `T(hub[-_.]?blocks?)` | none |
| | complete-json | `.*complete.*\.json.*` (complete.json, `.tmp`/`.swp`, `*-complete.json`, `end-complete.json`, `complete-v2.json`, `incomplete.json`, `*completed*.json`) | E4: final component exactly `complete.json` at the four exact paths. D3: exactly `end-complete.json`. E5 (r3): the final component of exactly `tests/fixtures/native_friendly_completed_15_535_86.json`. |
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

The E4, D3 and E5 leaf exceptions apply to the final component only and only to the exact names (E5: the exact full relative path, case-sensitive) (`Complete.json`, `END-RAW.json` and `end-raw.json.tmp` refuse). Exact-name grants are checked when the Role is built. Look-alikes that stay outside every family include `endgames`, `gamestate.py`, `game-001.json`, `incomplete/` (a directory with no `.json`), `attempt1.log`, `backend-jobs.py` and `END-raw-phases-20261011/`.

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

- `constants_fingerprint()` = **`33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592`** (r2 was `6661ca0b…`). Besides r1's constants, it covers the families, E4 blob OIDs, **E5_RUNTIME_MEMBERS (r3)**, E1 link OID, D3 constants, git policy, refused config and receive bootstrap. Adopters pin it.
- `remote_program_sha256()` = **`2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152`** (r2 `ff6f9fa4…`, r1 `5b15dfe7…`; the shared `_CORE` changed again in r3, the reader's own main did not) and `receive_program_sha256()` = **`979b37a19ca74fe55381d46d19cc67923d2a2925f5d5d7b6ade3f7aa6c67fd62`** (r2 `d259318a…`).
- `E5_RUNTIME_MEMBERS` (r3): the nine pairs listed in §9; source: ruling E5 (OIDs recorded by the runner from `git ls-tree 104fa857`, metadata only).
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

r2: a D1 export at that origin/main refused (by name, in phase 1) until the coordinator ruled.

**r3 (ruling E5: exact path + blob OID for these nine).** The D1 plan was re-run with r3 against origin/main **02805c97636eaaba0a6e67b7144c1b489f3251e9** (11,749 entries), from tree metadata only (`d1_rerun_r3.py`, output `D1-RERUN-r3.json`, summary at the end of the D5 file):
- The member rule is pin list ∪ every `*.py`, which gives 4,184 members. The pin list (1,557 names) was read from the clean working-tree file through `si.read_bytes(expected_sha256=f81f3655…)`, not from the object store. Its recomputed blob OID `bdaf6180…` equals the ls-tree OID at that commit.
- **Member-set refusal count: 0.** Each member was screened alone; the E1 alias was screened with its target.
- The global E4 rule refused nothing.
- `git_plan(members=<rule>)` was accepted: 4,173 files, E4 = [E2], E1, and the 9 E5 members. Each E5 member is mode 100644 and its OID equals the constant.
- The git calls were exactly `rev-parse`, `cat-file -t <commit>` and `ls-tree -r -l -z --full-tree` (argv-logged). The `object_reads` delta was 0, and no `cat-file --batch` ran.
- The non-member list was not re-scanned at 02805c97.

## 10. Verification (127x05, 2026-10-12; every number is from the r3 session)

r2's numbers and its disclosed mutation history are in `safe-input-r2/README.md` §10. Nothing below reuses them.

**Suite.** Every command ran under `nice -n 19` with `PYTHONDONTWRITEBYTECODE=1`, `-B` and `-p no:cacheprovider`, normally and with `-O`. `TMPDIR` and `--basetemp` pointed at a fresh `/dev/shm/si-r3-bt-*` directory, which was removed afterwards. pytest was installed only into `/dev/shm`, with `uv pip install --target`, and supplied through `PYTHONPATH`: 8.3.5 for 3.8 and 9.1.1 for the e4v3 venv. k4s-freeze already has 9.1.1. No venv was modified.

| Interpreter | Normal | `-O` |
|---|---|---|
| `/usr/bin/python3` 3.8.10 | 548 passed | 548 passed (1 warning) |
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | 548 passed | 548 passed (1 warning) |
| `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12 | 548 passed | 548 passed (1 warning) |

Under `-O`, the only warning is pytest's `PytestConfigWarning: assertions not in test modules … (are you using python -O?)`. The tests use explicit `ok()`/`refusal()` checks, not asserts. Before any change, the unmodified r3 copy passed r2's 472 tests (k4s-freeze).

**Mutation.** `python -B -O tests/mutate.py --jobs 12 --recheck-without test_cli_publish_ps.py::test_constants_fingerprint_is_pinned` ran against `safe_input.py` `806e5ebb…`; the SHA is recorded in each JSON. The two campaigns ran concurrently, each with its own `TMPDIR` under `/dev/shm`.
- **3.8.10 -O: 270/273 killed. k4s-freeze 3.12.12 -O: 270/273 killed.**
- **All 26 E5 mutants were KILLED on both interpreters, each by a `test_e5.py` test.** They cover:
  - the constant guard (E5-01);
  - the case-sensitive path lookup (E5-02);
  - `name_gate`'s e5 exactness and suffix checks (E5-03, E5-03b);
  - `_gate`'s role-exemption check and e5 refusal (E5-05, E5-07), and the exact-path check jointly with `name_gate` (E5-06J);
  - phase-1 mode, OID, cap and role checks (E5-08 to E5-11);
  - `hash_e5`'s OID check (E5-12);
  - `copy_e5`'s copy-pass re-check and hash-first order (E5-13, E5-14);
  - `git_hash_e5`'s planned-entry check (E5-15);
  - `walk_tree`'s directory and role checks (E5-16, E5-17);
  - the receiver's validation (E5-18, E5-18a, E5-18J), strict bool (E5-19), flag-gated name exemption (E5-20) and host-side blob re-hash (E5-21);
  - the sender's pre-ssh `hash_e5`, declared SHA/size and exact-path checks (E5-22, E5-22b, E5-23).
- The 3 not killed (Q11, SD01, SD08) are r2's documented equivalent mutants, and each joint (Q11J, SD01J, SD08J) was KILLED in the same run. The `equivalent_survivors` and `e5_mutants` annotations in each JSON were added after the run, from that run's data.
- Each campaign interleaves 6 NULL controls (unmodified source), and all 6 SURVIVED.
- 15 mutants were first killed only by the fingerprint pin. Re-run with that test deselected, all 15 were KILLED by behavioural tests on both interpreters. None of them is an E5 mutant.
- Each mutant runs the whole suite (`-x`) on a copy in a fresh `/dev/shm/safe-input-mut-*` directory, which is removed afterwards. Each edit target must occur exactly once (`--check-edits`: 273 valid).
- **12 r2 mutants were re-pointed, not changed:** E12, T01, X06, Q01, Q05, G02, RV10, RV10b, RV21, SD01, SD04 and SD01J. Their source lines gained E5 arguments. Each edit removes or weakens the same check as in r2, and all of them except the equivalent SD01 were KILLED.
- New equivalents in r3, with reasons in `mutate.py` `EQUIVALENT` (no mutant is run for these):
  - `_gate`'s E5 exact-path clause alone, which `name_gate`'s own exactness check masks (the joint E5-06J is run);
  - the receiver's "not e4" clause, which the E4 pin rule masks;
  - the receiver's exact-path clause alone, which the receiver's `name_gate` masks before anything is created (the joint E5-18J is run);
  - `name_gate`'s leaf-only rule for E5, which is not mutated because every E5 path matches a family only in its leaf.
- Before the full campaigns, an E5-only pass on 3.12 -O (E5 plus re-pointed mutants) killed 37 of 38; the survivor was the equivalent SD01. That pass found no test gap. One test was added afterwards (`test_on_disk_copy_of_unpinned_bytes_creates_nothing`, aimed at E5-14), and the full campaigns above include it.

**Changes to r2 tests in r3** (all intended):
- `test_receive.py`: the hand-built manifest helper adds `"e5": False`, because the manifest file key set now includes `e5`.
- `test_families.py`: `EXEMPTIONS` is now `{E1, E4, D3, E5}`.
- `test_cli_publish_ps.py`: the fingerprint pin is the r3 value, `33f594ed…`.
- New: `test_e5.py`, 76 tests. It imports helpers from `test_git_r2.py` and `test_receive.py`.

r2's "Changes to r1 tests" are still in force (`safe-input-r2/README.md` §10).

**D1 re-run.** See §9. The script and its output are `d1_rerun_r3.py` and `D1-RERUN-r3.json`.

**Write confinement.**
- Tests and mutation runs wrote only under `/dev/shm`: `si-r3-bt-*`, `safe-input-mut-*`, `si-r3-mut-tmp*`, `si-r3-d1`, and the pytest targets `si-r3-pytest38`/`si-r3-pytest312`. All of these were removed at the end, except the evidence copied into this directory.
- No `/tmp/si-git-home-*` and no mutation directory remained.
- The shared checkout was touched only by `git fetch -q origin` (as instructed) and by the read-only operations below.
- No real outcome, game, `complete.json`, reducer or verifier output was opened. **No blob of the nine E5 members was read.** Their OIDs come from the ruling, `E5-OIDS-ls-tree.txt` and ls-tree metadata.
- The only reads of real repository content were:
  - the static preflight of `/mpac/sdicks02/repos/clasher` (`.git/config` names);
  - `git show origin/main:reports/strategy_council_20260928/COORDINATOR.md`, the ruling;
  - `ls-tree` metadata at 02805c97;
  - the clean working-tree `runtime-pin-r2.json` (a pin list), read with its expected SHA-256.

No ssh was used. Every receive test goes through the local fake-ssh shim or runs the receiver directly. Nothing was committed or pushed.

## 11. Residuals and open points (disclosed)

1. **Accepted TOCTOU residual** (16:00Z ruling, restated 18:19Z). Another local actor can rewrite a file's bytes in place, without changing its size, during a read; this is undetected without an expected SHA. **All production reads must pass expected SHAs.** `hash_sealed_end_member` and `remote_receive` require them; elsewhere the layer cannot force a caller to pass one, so ADOPTION rule 0.6 makes it mandatory. The same residual covers a git repository changed concurrently between `_git_preflight` and git's own open of the files. E5 on disk always compares against the pinned blob OID, so for the nine E5 members such a rewrite refuses.
2. **D5: resolved by E5 in r3** (§9): 0 member refusals at origin/main 02805c97. The r2 non-member scan (at f15691b5) was not repeated.
3. **E4 blob OIDs.** The coordinator's 21:28Z entry records that the runner independently matched all four to their ruled SHAs (`RUNNER-E4-OID-RATIFICATION.txt`, carried over from r2 unchanged).
4. **Partial clone.** `/mpac/sdicks02/repos/clasher` is a promisor clone (its config has `promisor` and `partialclonefilter`; names only were read). Every transport is disabled, so a blob missing locally refuses instead of being fetched lazily. The 21:28Z full-clone ruling (S9 builds only from a runner-owned full clone that safe_input checks for promisor, alternates, grafts, hooks and driver config) is **not implemented in r3**. `_git_preflight` still accepts a promisor config and does not inspect `.git/hooks`; hooks are disabled per call with `core.hooksPath=/dev/null`. The D1 re-run needed tree metadata only, which this clone has.
5. **The frozen `k4s_logic.git_bytes()`** cannot adopt the helper (ADOPTION §S2). The 21:28Z frozen-reader wrapper ruling is **not implemented in r3**.
6. **The config gate is name-level.** It parses section and key names, not values or quoting edge cases, and does not interpret `info/attributes`. Attribute-assigned drivers need repo or config definitions, which are refused. Built-in diff drivers are inert for the plumbing reads used here.
7. **The receiver trusts the grants in its manifest**, as the r1 reader did. Every non-grantable rule (outcome families, T1, perception, cache) is still enforced on the host. The role allowlist (patterns) is enforced locally only. The E5 flag is not a grant: the host program accepts it only at an exact E5 path, with mode 0444, and with bytes that hash to the pinned OID.
8. **The receiver's E4 and E5 pins are inside the shipped program.** Tests patch them by substituting the shipped source; production ships the real pins, and the bootstrap SHA binds them.
9. **Partial receives.** A refused receive leaves its exclusive `.partial` root and any partial files in place (never deleted), and lists them in the refusal. An E5 blob mismatch is detected after the file was streamed, so that partial is kept too. Cleanup is a separate, authorized step.
10. **Families are deliberately broad and fail-closed.** `incomplete.json`, `*completed*.json`, `check_games.py` and `attempt-claim.json` all refuse unless granted or E-listed. E5 lists exactly nine paths, and the families are unchanged.
11. **Mutable module dicts.** `E4_COMPLETE_JSON` and `E4_GIT_BLOB_OIDS` are plain dicts so that tests can patch them. Production code must never write them; `constants_fingerprint()` exposes any edit. `E5_RUNTIME_MEMBERS` is an immutable tuple. Tests rebind the module attribute (and the receive validator's namespace) with new OIDs only, and `e5_blob_oid()` refuses any other change.
12. **Live behaviour is unverified.** Nothing ran against 03/04, real ssh, production commits, or real outcome or receipt files. The real-repository operations are listed in §10.
13. **The r1 remote reader does not know E5.** `remote_check` and `build_remote_request` refuse an E5 name by family. If a component needs to hash an E5 member on a host remotely, it must run `hash_e5` on that host (host-run code with the pinned layer) or ask for an extension.
14. **Receive manifest key set.** File records now carry `e5`, still under the schema name `clasher.k4s.safe-input.receive-request.v1`. r2 was never deployed, so no live receiver exists. The sender always ships its own receive program (bootstrap-verified by SHA), so an r2 sender and an r3 receiver never meet. The changed fingerprint and program SHAs (§8) tell r2 and r3 apart.
