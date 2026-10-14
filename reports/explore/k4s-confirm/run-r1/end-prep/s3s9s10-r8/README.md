# K4S END prep: S1b, S3, S9, S10, S11 — CANDIDATES r6 (Sol fix-check r5: U10 symbolic destination ref)

## r6 — narrow fix round (SOL-FIXCHECK-END-INTEGRATION-r5: U1/U10 NOT FIXED, the sole blocker)

- **Scope:** `reviews/SOL-FIXCHECK-END-INTEGRATION-r5.md`. S9 `refresh-clone` built the ref/reflog write set from the literal destination ref and accepted a regular single-link ref file without resolving it; a pre-existing `ref: refs/remotes/victim/branch` destination moved the fetch's ref and reflog writes to the victim, whose aliased reflog (leaf symlink, hard link, symlinked ancestor) received a foreign append before the late ref comparison refused. Sol did not claim the bypass for S11. This directory began as `cp -a s3s9s10-r5`; r5 is unchanged. **`RESPONSE-r6.md`** maps each item to file:line and named tests; **`DIFF-r6.patch`** is `diff -ruN s3s9s10-r5 s3s9s10-r6` (SHA256SUMS and PROGRESS files excluded).
- **Offline only:** synthetic world, namespaced fake hosts, scratch repositories in `tempfile` dirs / `/dev/shm/s3s9s10r6-*` (removed). No ssh, no network, no host, nothing committed. One read-only metadata check of the real `repo-full/.git` write set (the new guard passes on the production clone: `checked 52`, no refusal).
- **S9 is final:** `S9-FINAL` (r6) holds the SHA-256 of `s9_end_runtime.py` (`bdc2deeb96bf60a16b8877ffa2038760673d60bb63edcde8d947195fdfdcf3a7`) and of the unchanged chain it loads (`end_prep_common.py` 2a84775b…, `safe_input.py` 806e5ebb…). The runner rebuilt the production runtime with it (`end-staging/RUNTIME-r6-READY`); `s5s6s7-r6` adopted both.
- **Unchanged:** `ADOPTED_S4_SHA256` (b3-r7 `2b8f5fb3…`), the canonical bootstrap block (byte-identical, `test_f1.py`), `TOOL_PINS` (no tool file changed; `s5s6s7-r6/TOOLS-FINAL` = r5's six rows), S1b, S3, S10 except its re-pinned `K4S_SIBLING_PINS`.

### r6.1 The fix: every ref a writing git command updates must be a DIRECT ref, checked before the command

Two independent checks, both **before** the fetch (and again before `--checkout` / each S11 command), after the existing leaf/ancestor scan; the existing late ref comparison (S9 `:996`) is kept.

1. **Shared guard (`GIT_WRITE_GUARD`, so S9 and the S11 host program run the same code).** `gw_plan(ref)` now carries `direct=[ref]` (the ref the command updates: S9 `refs/remotes/origin/k4s-end-r1`; S11 `refs/heads/k4s-end-r1`). After the `files` / `absent` / `trees` rows are validated, `gw_scan` calls `gw_refs`:
   - the loose ref file, when present, must be exactly `<40 lowercase hex>\n`: a content starting `ref:` refuses as a **symbolic ref**; any other form (empty, no newline, upper case, trailing bytes, two lines) refuses;
   - `packed-refs`, when present, must be well formed: optional `# pack-refs with:` header, `<oid> <refs/...>` lines (no space in the name, no duplicate), each optionally followed by exactly one `^<oid>` peeled line; anything else refuses (a `ref:` line, a peel line first or doubled, a bad oid, a non-`refs/` name, no final newline, non-ASCII), and the destination must have **no peeled entry**;
   - both leaves are read by `_gw_read` only after this scan validated them: the parent directories are re-walked no-follow and must be the identities the scan recorded, the leaf is opened `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY|O_CLOEXEC` relative to that directory, and its `fstat` must be the validated regular single-link inode; bounded (4 KiB loose ref, 64 MiB packed-refs). These are the guard's only content reads (`test_git_write_guard_source_is_metadata_only` now admits exactly one `os.read`, inside `_gw_read`).
2. **git's own view (read-only, scrubbed environment).** `git symbolic-ref` is **not** in the pinned `safe_input.GIT_SUBCOMMANDS` allowlist (safe_input is unchanged and pinned), so both programs ask the equivalent allowlisted question through `si.git_run`: `for-each-ref --format=%(refname) %(symref) <ref>`; the output must be empty (absent ref) or exactly `<ref> \n` (no symbolic target), else `git-write` refusal. S9: `require_direct_ref` (after `gw_check`, before the fetch and before `--checkout`); S11 host: in `_guarded`, after `gw_scan`, before `_git_w`.

`GW_RELEASE` is now `k4s-git-write-guard-r6` (the plan shape changed). The guard's composition into the host program is unchanged: canonical block + `S9.GIT_WRITE_GUARD` + `HOST_MAIN`.

**Other refs the commands update.** S9 `fetch` updates only the destination (plus `logs/HEAD` when HEAD points at it: a planned leaf). S9 `checkout --detach X` updates `HEAD` with no-deref (HEAD itself, a planned leaf; a symbolic HEAD is the normal state of a clone and is not followed): `test_s9_checkout_detach_with_a_symbolic_head_writes_no_referent_reflog` points HEAD at a victim branch whose reflog is a symlink to the marker, runs `refresh-clone --checkout` and requires the marker unchanged. S11 provision `checkout k4s-end-r1` and advance `checkout -B k4s-end-r1 X` write HEAD as a symref (the HEAD file itself) and update `refs/heads/k4s-end-r1` (the direct row).

**S11 (confirmed by code reading + tests).** advance already refused a symbolic `refs/heads/k4s-end-r1` before any mutation, at the `[check]` stage: `_verify` requires `rev-parse --symbolic-full-name HEAD` == `refs/heads/k4s-end-r1` (git resolves the whole chain, so a symbolic branch shows its referent) and exactly one ref. r6 adds the shared-guard and git-view checks to `_guarded` as well (provision + advance), and tests each with `_verify` stubbed so the earlier layer cannot mask them. provision creates `repository.partial` exclusively, so a pre-existing symbolic ref cannot occur there; the test injects one after `git init` to prove the check.

### r6.2 Pin chain, files

- `tests/k4s_adopt.py` re-pinned the chain (S9 changed; S1b/S3/S10/S11 pins follow); `--check` clean. Canonical block byte-identical; `ADOPTED_S4_SHA256` unchanged; `TOOL_PINS` unchanged.
- New: `tests/test_r6_symref.py`. Updated: `tests/test_r5_git_write.py` (release string r5 → r6, three lines), `tests/test_common.py` (the guard-source rule admits the one `_gw_read`), `tests/mutate.py` (+ `test_r6_symref.py`, + D01–D19).

### r6.3 Tests (offline; final runs on the final bytes)

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **1315 passed** (171.9 s) | **1315 passed** (171.9 s; 1 warning) |
| `/usr/bin/python3` 3.8.10 (pytest from `/dev/shm/s3s9s10r2-pytest38`) | **1315 passed** (189.0 s) | **1315 passed** (219.0 s; 1 warning) |

Runs 2026-10-13T13:15:57Z–13:19:37Z (the four in parallel): `env -i`, `nice -n 19 taskset -c 8-23`, umask 022, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, cwd `/tmp`. The `-O` warning is pytest's PytestConfigWarning, as before. r5 had 1252; r6 adds 63 (`test_r6_symref.py`).

**`tests/test_r6_symref.py` (63):**
- `test_s9_refresh_refuses_a_symbolic_destination_before_the_fetch[leaf-symlink, hardlink, ancestor-symlink]` — **Sol's three cases** on the real S9 refresh fixture: `git symbolic-ref refs/remotes/origin/k4s-end-r1 refs/remotes/victim/branch` (victim at P), the victim's reflog aliased to a synthetic marker outside the clone (leaf symlink / hard link / symlinked `logs/refs/remotes/victim` directory), origin advanced to X; `require_full_clone` passes (as Sol saw); refresh must refuse `git-write` naming the symbolic destination, **no writing git command ran** (spy on `si.run_checked`), **FETCH_HEAD byte-identical**, the marker byte-identical (and its tree's identities), only `S9-REFUSAL-*` in the record directory. All three FAIL on unmodified r5 code (checked: copy of r5 + this test file).
- `test_s9_refresh_refuses_other_indirect_destinations_before_the_fetch[onelevel-symref, loose-no-newline, loose-two-lines, packed-peeled, packed-symref-line]` (the last is refused even earlier by git itself, `subprocess`: git cannot read such a packed-refs; still before any write).
- `test_s9_git_view_check_isolated_from_the_guard` (gw_refs disabled by fault injection: `require_direct_ref` alone refuses Sol's case before the fetch), `test_s9_checkout_rechecks_the_destination[guard, git-view]` (destination made symbolic after every post-fetch check: each layer alone refuses before the checkout), `test_s9_checkout_detach_with_a_symbolic_head_writes_no_referent_reflog`.
- Shared guard, **both copies** (S9's executed source and the S11 host program's): `test_guard_loose_destination_must_be_one_object_name[6 rows x 2]`, `test_guard_packed_refs_must_be_well_formed_and_direct[10 rows x 2]`, `test_guard_accepts_direct_refs_and_peeled_tags[2]`, `test_guard_reads_only_the_validated_leaf[not-validated, identity, limit, dir-identity, symlink-to-same; x 2]` (the last: the same validated inode behind a symlink, which only `O_NOFOLLOW` refuses).
- S11 on the fake host: `test_s11_advance_refuses_a_symbolic_destination_before_the_fetch[leaf-symlink, hardlink, ancestor-symlink, onelevel]` (refused at `[check]` by the existing exact-ref VERIFY: X not fetched, FETCH_HEAD unchanged, marker unchanged, refusal receipt only, no `s11-advance.json`); host `_main` locally with `_verify` stubbed: `test_s11_host_advance_symbolic_destination_isolated_from_verify[guard, git-view]`, `test_s11_host_provision_symbolic_destination_refused_before_the_fetch`.

### r6.4 Mutation (new checks; `tests/mutate.py` under `-O`, each mutant = the whole suite with `-x` on a /dev/shm copy re-pinned by `k4s_adopt.py`)

19 mutants, **D01–D19** (`tests/mutate.py`; `--check-edits`: 237 mutants, all valid): the `gw_refs` call in `gw_scan` (D01), the loose `ref:` rule (D02) and one-object-name rule (D03), the packed-refs peeled-destination rule (D04), line grammar (D05), peel-after-ref rule (D06), final newline (D07), ASCII (D08), one peel per ref (D19), `_gw_read`'s validated inode (D09), validated-leaf precondition (D10), validated parent directories (D11), bound (D12) and `O_NOFOLLOW` (D13), the plan's `direct` row (D14), S9 `require_direct_ref` before the fetch (D15), before `--checkout` (D16) and its condition (D17), and the S11 host's git-view check (D18).

| Campaign | Result | NULL controls | outside_writes | File |
|---|---|---|---|---|
| py3.12.12 `-O`, r6 set | 19/19 killed (see note) | 3/4 survived (see note) | false | `MUTATION-RESULTS-s3s9s10-r6-py312-O-r6set.json` |
| py3.12.12 `-O`, rerun of D02 + 1 NULL | **D02 killed** by `test_s9_refresh_refuses_a_symbolic_destination_before_the_fetch[leaf-symlink]` | 1/1 survived | false | `MUTATION-RESULTS-s3s9s10-r6-py312-O-rerun.json` |
| py3.8.10 `-O`, r6 set | **19/19 killed** | 4/4 survived | false | `MUTATION-RESULTS-s3s9s10-r6-py38-O-r6set.json` |

Every mutant was killed by a `test_r6_symref.py` test aimed at it (the `killed_by` field). The guard-row mutants are killed by the `-s9` copy rows, which run first; the host copy runs the same source. **Note (pre-existing test race, not code):** in the first py3.12 campaign, D02 and one NULL started together and were both "killed" after 1.5 s by `test_common.py::test_scrubbed_env`. That r1 test removes every `/tmp/k4s-frozen-home-*` that holds a `planted` file, so concurrent suites can delete each other's HOME. The rerun shows D02 killed by its own test and the NULL surviving, and py3.8 is clean. The test is unchanged in r6 (outside this round).

### r6.5 Not covered / for the reviewer

- The `for-each-ref %(symref)` git-view check replaces the requested `git symbolic-ref -q`, which the pinned safe_input does not allow; it answers the same question through the same gated runner. For a dangling symbolic ref git prints nothing (absent); the guard's content check refuses that case (the loose `ref:` file).
- Races (a concurrent writer between the scan and git) remain outside the cases, as in r5 (single operator); the descriptor checks narrow only the guard's own window.

# (r5 README follows, unchanged except where §r6 supersedes it)

# K4S END prep: S1b, S3, S9, S10, S11 — CANDIDATES r5 (Sol integration r1 finding 2: git write confinement; U4 venv interpreter)

## r5 — diff-only fix round (Sol integration review r1: finding 2 BLOCKING; U4 ruling)

- **Scope:** `SOL-REVIEW-END-INTEGRATION-r1.md` finding 2 (U1/U10: git metadata writes outside the repository from S11 `advance` and S9 `refresh-clone`) and the coordinator's U4 ruling (10:33Z: the END interpreter is the one P′ `runtime.sh` executes). Finding 1 (U8, the END-JOB builder) belongs to `s5s6s7-r5`. This directory began as `cp -a s3s9s10-r4`; r4 is unchanged. **`RESPONSE-r5.md`** maps each item to file:line and named tests; **`DIFF-r5.patch`** is `diff -ruN s3s9s10-r4 s3s9s10-r5` (SHA256SUMS and PROGRESS files excluded).
- **Offline only:** synthetic world, namespaced fake hosts, scratch repositories in `tempfile` dirs / `/dev/shm/s3s9s10r5-*` (removed). No ssh, no network, no host, nothing committed. The only real-repository read is one non-outcome blob (`runtime.sh` at P′, by OID) for the U4 source test.
- **S9 is final:** `S9-FINAL` (written 2026-10-13T10:49:51Z) holds the SHA-256 of `s9_end_runtime.py` (`4778f6f61cb5cb69a7cf476ce5ce00c53e3b3157ca052492a3bc3e3cb3745b60`) and of the chain it loads (`end_prep_common.py` 2a84775b…, `safe_input.py` 806e5ebb…). S9 has not changed since.
- **TOOL_PINS:** `s5s6s7-r5/TOOLS-FINAL` (10:36:33Z) lists the same six files, paths and SHA-256s as S10 `TOOL_PINS`: no re-pin was needed (checked by command; comment updated only).

### r5.1 Finding 2: the git write guard (`s9_end_runtime.GIT_WRITE_GUARD`, shared by S9 and the S11 host program)

**Design.** One stdlib-only, Python 3.8-compatible source text, `GIT_WRITE_GUARD`, is executed by S9 (`_GW`) and composed **verbatim** into the S11 host program (`canonical block + S9.GIT_WRITE_GUARD + HOST_MAIN`; the test requires exactly one copy). For each writing git command it builds a **plan** (`gw_plan(ref, worktree, worktree_only)`) — the audited write set below — and `gw_scan` checks it **before** the command:

- the repository root is reached by a component walk from `/` with no-follow (`gw_open_root`);
- `dirs`: must exist, and every component is a real directory (lstat says directory, then an `O_PATH|O_DIRECTORY|O_NOFOLLOW` descriptor whose `fstat` dev/ino must be the inspected one);
- `may_dirs`: directories git may create: absent, or real directories (same test);
- `files`: every leaf git writes, appends, replaces or might write: absent, or **regular with `st_nlink == 1`** (no symlink, no hard link); its ancestors as `may_dirs`;
- `absent`: every **lock sibling** (`<file>.lock` for each `files` row) and the forbidden names (hooks, shallow, alternates, grafts, commondir, config.worktree, commit-graphs, modules, worktrees): nothing of any type;
- `trees`: everything under `.git/objects` (packs, loose objects, info) is a real directory or a regular single-link file;
- `worktree`: the checkout's paths (exactly the paths that differ, from `diff-tree -r --no-renames`): ancestors absent or real directories, leaf absent or regular single-link; `worktree_only`: a fresh work-tree root must hold exactly `.git` (S11 provision);
- only lstat/fstatat, `O_PATH` directory descriptors, `fstat`, `dup`, `close` and `os.listdir` (`.git/objects` and the fresh root only) are used: no file content is read (`test_git_write_guard_source_is_metadata_only`).

After the command, `gw_post` re-runs the scan and requires every pre-existing directory to keep its identity. **This is detection only; the guard is the scan before.** Refusals are code `git-write` (S9: `si.Refusal`; host: `_Refused`, reported through the session's `@@REFUSED`).

**Write-reducing configuration (`GW_CONFIG`, `GW_FETCH_FLAGS`).** Every writing command runs with `core.hooksPath=/dev/null`, `core.fsmonitor=false`, `core.logAllRefUpdates=false`, `core.splitIndex=false`, `core.untrackedCache=false`, `gc.auto=0`, `gc.autoDetach=false`, `maintenance.auto=false`, `fetch.writeCommitGraph=false`, `fetch.recurseSubmodules=false`, `submodule.recurse=false`, `fetch.prune=false`, `fetch.pruneTags=false`; fetches add `-q --no-tags --no-auto-gc --no-recurse-submodules`. These reduce the write set; they do not replace the scan: `core.logAllRefUpdates=false` stops reflog **creation**, but git 2.25 still **appends to an existing reflog** (observed), so reflogs stay confined rows. git 2.25.1 (05 and the Ubuntu 20.04 hosts) has **no `--no-write-fetch-head`** (rejected as an unknown option; it arrived in 2.29), so FETCH_HEAD is confined, not disabled. `si.git_run` cannot pass global `-c` options (its first argument must be the subcommand), so:

- S11 host: `_git_w` = exactly `si._git_preflight` + `si.GIT_GLOBAL_ARGS` + `GW_CONFIG` + the declared protocols + `--git-dir/--work-tree` + `si.GIT_FIXED_ENV` with a fresh empty HOME (removed; a write into it refuses); only `fetch` and `checkout`; `_guarded` = scan, `_git_w`, post;
- S9: `fetch_argv()` now carries `GW_CONFIG`/`GW_FETCH_FLAGS`; `--checkout` uses the new `checkout_argv()` (si.git_run's flags + `GW_CONFIG`, scrubbed environment).

**Where it runs.**

| Command | Guard before | Plan |
|---|---|---|
| S9 `refresh-clone` fetch (`refs/heads/k4s-end-r1:refs/remotes/origin/k4s-end-r1`) | `gw_check` right before `si.run_checked(fetch_argv())`, after the live `verify_clone` and object snapshot | `gw_plan(refs/remotes/origin/k4s-end-r1)` |
| S9 `refresh-clone --checkout` (`checkout --detach X`) | `gw_check` before `checkout_argv(X)` | the same + `worktree = diff-tree HEAD X` |
| S11 provision fetch (bundle → `refs/heads/k4s-end-r1`) | `_guarded` after `git init --template=` | `gw_plan(refs/heads/k4s-end-r1, worktree_only=[.git])` |
| S11 provision checkout | `_guarded` | the same (fresh root) |
| S11 advance fetch (bundle → FETCH_HEAD) | `_guarded` after VERIFY at P′ | `gw_plan(refs/heads/k4s-end-r1)` |
| S11 advance checkout (`checkout -B k4s-end-r1 X`) | `_guarded` after the committed END-JOB check; **the checkout's paths must be exactly `[END-JOB.json]`** (`diff-tree P′ X`, else `check` refusal) | the same + `worktree = [END-JOB.json]` |

`git init` (S11 provision) writes only inside `repository.partial`, which the host program has just created exclusively; S9 `prepare-clone` creates a new clone (it refuses an existing REPO_FULL) and is unchanged.

**The audited write set (git 2.25.1).** Derived from git's behaviour and observed without ptrace: every directory under the repository watched with **inotify** before the exact command (create/modify/close-write/moved/delete events, so transient `*.lock` and `tmp_*` files are seen) plus a before/after **lstat snapshot** (which also catches files inside directories the command created). The observation is a test (`test_observed_git_write_set_is_inside_the_plan[6 commands]`): every touched path must be a plan row, inside `.git/objects`, or a planned work-tree path.

| Path (under the repository) | Written by (observed) | git's mechanism / what an alias does (scratch experiments, git 2.25.1) | r5 confinement |
|---|---|---|---|
| `.git/FETCH_HEAD` | every fetch (S9, S11 provision, S11 advance) | `fopen("w")`: follows a symlink, truncates a hard-linked inode → **foreign write** (Sol's case) | `files` row; `.git` real dir. Not disableable in 2.25 |
| `.git/logs/HEAD` | every checkout | `O_APPEND`: follows a symlink / shared inode → **foreign write**; appended even with `core.logAllRefUpdates=false` when the file exists | `files` row; `.git/logs` `may_dirs`; GW_CONFIG stops creation |
| `.git/logs/refs/heads/k4s-end-r1` | S11 provision fetch (r4), advance `checkout -B` | as above → **foreign write** | `files` row (per ref); `.git/logs/refs`, `…/heads` `may_dirs` |
| `.git/logs/refs/remotes/origin/k4s-end-r1` | S9 fetch | as above → **foreign write** (Sol's case) | `files` row (per ref); `…/remotes`, `…/origin` `may_dirs` |
| `.git/index`, `index.lock` | every checkout | lock file **resolves a symlinked target**: `index.lock` is created beside the target and renamed over it → **foreign write** (observed for a symlinked index) | `files` row; `index.lock` `absent` row |
| `.git/HEAD`, `HEAD.lock` | every checkout | ref lock + rename (a symlinked HEAD: git refuses, rc 128) | `files` row; lock `absent` |
| `.git/refs/heads/k4s-end-r1` (+ `.lock`) | S11 provision fetch, advance `checkout -B` | ref lock (no-deref) + rename; a **symlinked `refs/heads` directory** sends the ref into the target → **foreign write** | `files` row; `.git/refs` `dirs`, `refs/heads` `may_dirs`; lock `absent` |
| `.git/refs/remotes/origin/k4s-end-r1` (+ `.lock`) | S9 fetch | as above | `files` row; `refs/remotes`, `…/origin` `may_dirs`; lock `absent` |
| `.git/packed-refs` (+ `.lock`) | not by these commands (observed); a ref deletion would rewrite it | lock file resolves symlinks | `files` row; lock `absent` |
| `.git/ORIG_HEAD` | not by fetch/checkout (observed) | — | `files` row (defensive) |
| `.git/config` (+ `config.lock`) | not written (no upstream: start points are commit IDs) | lock file resolves symlinks | `files` row; lock `absent` (S11 `_verify` / S9 `check_clone_config` read it too) |
| `.git/gc.pid`, `.git/gc.log` | only by auto-gc | — | auto-gc off (`gc.auto=0`, `--no-auto-gc`, `gc.autoDetach=false`); `files` rows |
| `.git/objects/**`: `pack/tmp_pack_*`, `pack/tmp_idx_*`, `pack/pack-*.{pack,idx}`; loose `objects/xx/*` | every fetch (bundle: index-pack; small network fetch: unpack-objects) | new names only (`mkstemp` O_EXCL, then link/rename; an existing object is never written through); a **symlinked `objects/pack`** sends the pack elsewhere → **foreign write** | `trees` row (all entries real dirs / regular single-link); `objects`, `objects/pack` `dirs`, `objects/info` `may_dirs` |
| `.git/objects/info/commit-graph`, `info/packs`; `info/commit-graphs/` | not written (`fetch.writeCommitGraph=false`) | — | `files` rows; `commit-graphs` `absent` |
| `.git/shallow`, `objects/info/alternates`, `…/http-alternates`, `info/grafts`, `commondir`, `config.worktree` | — (indirections) | — | `absent` rows (and the existing S9/S11 checks) |
| `.git/hooks` | never run (`core.hooksPath=/dev/null`) | — | `absent` row |
| `.git/modules`, `.git/worktrees`, `sharedindex.*` | not used (`--no-recurse-submodules`, `submodule.recurse=false`, `core.splitIndex=false`) | — | `absent` rows (modules, worktrees) |
| work tree: the checkout's paths | checkout (S9 `--checkout`: `diff-tree HEAD X`; S11 advance: exactly `END-JOB.json` and its new directory; S11 provision: the whole tree into a fresh root) | unlink + `O_CREAT|O_EXCL` (never written through an existing leaf); a symlinked leading directory: git itself refuses (rc 1) | `worktree` rows: ancestors absent or real dirs, leaf absent or regular single-link; `worktree_only` = `[.git]` for provision |
| the repository path and every ancestor up to `/` | — | — | `gw_open_root` no-follow walk |

**Not covered (stated):** a concurrent writer racing the scan and git (the review's cases are pre-existing aliases; the descriptor identity check narrows only the scan's own window); git's own internal behaviour beyond 2.25.1 (both hosts and 05 run 2.25.1; `check` records `git --version`).

### r5.2 U4: the END interpreter (`s10_stage_host.py`)

- `HOST_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"` — byte-equal to `s5s6s7-r5` `k4s_end_launch_gate.py:109` (vendored r5 gate; `test_u4_pins_agree_with_s7_and_the_layout`). Source of record: `runtime.sh` at P′ 98566c03 (`reports/explore/k4s-confirm/runtime.sh`, blob sha256 `67249aac5f7ff0027bb7bf5fb19c4275f1fe7d9b56a9ab4977a731169b8570f3`) ends `exec /mpac/sdicks02/repos/clasher/.venv/bin/python -B "$@"`; `test_u4_pin_is_the_runtime_sh_interpreter_at_p_prime` reads that one blob from REPO_FULL by OID and checks both. The bare uv binary pin is removed (`HOST_PYTHON_INFO = ()`).
- New pins: `HOST_PYTHON_PREFIX = /mpac/sdicks02/repos/clasher/.venv`, `HOST_PYTHON_BASE_PREFIX = /mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu`, `HOST_PYTHON_REALPATH = <base>/bin/python3.12`, `HOST_PYTHON_VERSION = 3.12.13`. The base and resolved binary come from committed evidence: the reporting-supervisor admissions' `/proc` exe on 03/04 is that binary, which is what a uv venv's `bin/python` symlink resolves to. They are **expectations the authorized probe qualifies on each host**; a mismatch refuses with every recorded fact.
- **The probe** (in the existing P-facts login, no extra login) runs exactly as END runs Python: `env -i PATH LC_ALL OMP/OPENBLAS/MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 HOME nice -n 19 <HOST_PYTHON> -B -c …` from `/`, without `-I`/`-s`. It records: `sys.executable`, its realpath and SHA-256, the version, `prefix` / `exec_prefix` / `base_prefix` and the prefix's realpath, every site-packages directory (`site.getsitepackages()` and the user site; path, realpath, exists, on `sys.path`), `pyvenv.cfg` (SHA-256, size, key = value pairs), the flags, and per module (numpy, torch, cv2, scipy) its origin, the origin's realpath and `__version__`.
- **It refuses** (`interpreter`) unless: `sys.executable == HOST_PYTHON`; version, prefix, prefix realpath, base_prefix and resolved binary equal the pins; `pyvenv.cfg` exists and its `home` is `<base>/bin`; at least one site-packages directory inside the venv is on `sys.path`; and each required module imports **from inside the venv's site-packages** (`venv_problems`, `parse_python`).
- The fake hosts now carry a real venv on the system python3 (`fakevenv/bin/python → /usr/bin/python3`, `pyvenv.cfg home = /usr/bin`, stand-in modules in its site-packages), so the probe is exercised against a working venv.

### r5.3 Pin chain, vendoring, files

- `tests/k4s_adopt.py` re-pinned the chain (end_prep_common ← s9 ← s1b ← s3 ← s10 ← s11); the canonical bootstrap block is byte-identical (`test_f1.py`); `ADOPTED_S4_SHA256` is unchanged (b3-r7 `2b8f5fb3…`).
- `tests/vendor_s5s6s7_r4/` became `tests/vendor_s5s6s7_r5/`: the S7 gate is s5s6s7-r5's (`4fc53765…`, U4 only); the other six files are byte-identical in r4, r5 and TOOLS-FINAL.
- New tests: `tests/test_r5_git_write.py`, `tests/test_r5_u4.py`, helper `tests/gw_observe.py`; updated: `test_r4_s10.py` (constants, vendor), `test_r4_s11.py` (vendor), `test_common.py` (S9's one exec of its own guard source; the guard source rules), `conftest.py` (fake venv), `mutate.py` (r5 mutants).

### r5.4 Tests (offline; final runs on the final bytes)

| Interpreter | normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **1252 passed** (163.6 s) | **1252 passed** (163.3 s; 1 warning) |
| `/usr/bin/python3` 3.8.10 (pytest from `/dev/shm/s3s9s10r2-pytest38`) | **1252 passed** (181.9 s) | **1252 passed** (212.7 s; 1 warning) |

Runs 2026-10-13T11:29:46Z–11:33:19Z: `nice -n 19 taskset -c 8-15`, umask 022, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, cwd `/tmp`. The `-O` warning is pytest's PytestConfigWarning, as before. r4 had 955; r5 adds 297: `test_r5_git_write.py` 271, `test_r5_u4.py` 25 and one in `test_common.py`; one r4 test was rewritten (`test_parse_python_requires_exactly_one_record` uses a full venv record).

**Finding 2 tests (`tests/test_r5_git_write.py`):**
- `test_s9_refresh_refuses_a_write_set_alias_before_the_fetch[27]` — **Sol's three S9 cases first** (FETCH_HEAD symlink, FETCH_HEAD hard link, `logs/refs/remotes/origin/k4s-end-r1` symlink), then hard-linked reflog, `logs/HEAD` symlink/hard link, ORIG_HEAD, index, packed-refs, the remote ref (symlink/hard link), symlinked `refs/remotes/origin`, `logs/refs/remotes/origin`, `logs`, `refs` directories, stale `index.lock` / ref lock / `packed-refs.lock` / `HEAD.lock`, `gc.pid`. Each: refusal `git-write` naming the path, **no fetch or checkout argv ran** (spy on `si.run_checked`), the foreign marker tree byte- and inode-identical, only `S9-REFUSAL-*` in the record directory. Four rows (HEAD symlink, symlinked `objects/pack`, symlinked `objects/info`, hard-linked commit-graph) are refused even earlier by existing S9 layers (git cannot open the repository; `verify_clone`; the objects snapshot walk), still before the fetch.
- `test_s11_advance_refuses_a_write_set_alias_before_the_fetch[27]` — **Sol's three S11 cases first** (FETCH_HEAD symlink, FETCH_HEAD hard link, `logs/HEAD` symlink; the symlinks name the fake host's `/mpac/sdicks02/jobs/perception-synthetic/` marker, as in Sol's probe), then the hard-linked `logs/HEAD`, branch reflog, ORIG_HEAD, index, packed-refs, the branch ref, symlinked `refs/heads` / `logs` / `logs/refs/heads`, the four lock siblings, a hard-linked pack file, `gc.pid`, commit-graph, a hard-linked HEAD. Each: `remote-refused` with the host's `git-write` refusal at the advance stage, **X not in the host repository (no fetch)**, HEAD still P′, the foreign tree unchanged, refusal receipt only (no `s11-advance.json`). Three rows (symlinked `objects/pack`, `objects/info`, hard-linked config) stop at the earlier check stage.
- `test_s9_checkout_refuses_a_work_tree_alias_before_the_checkout[3]`, `test_s11_host_checkout_guard_isolated_from_the_clean_check` (host `_main` locally, `_verify` stubbed so the clean-status check cannot mask the guard; fetch runs, the checkout is refused), `test_s11_host_main_other_checkout_guards[extra-path, fresh-root-not-empty]`.
- **The class:** `test_guard_table_every_row_refuses_its_alias[186]` — rows generated from `gw_plan` itself for both refs (every `files` row as symlink and hard link, every directory row as a symlinked directory, every required directory missing, every `absent` row as a file and a symlink, `.git/objects` with a symlink / hard link / FIFO inside, the work-tree leaf and directory), run on **both guard copies** (S9's executed source and the S11 host program's); `test_guard_table_is_complete_and_shared`; `test_guard_root_and_plan_shape[6]`; `test_guard_post_detects_a_changed_write_set[3]`; `test_guard_descriptor_must_be_the_inspected_directory`; `test_guard_lstat_rule_isolated_from_the_nofollow_open[2]`; `test_s9_post_fetch_detection`; `test_s11_host_guarded_post_check_detects[2]`; `test_s11_host_git_w_argv`; `test_s9_refresh_record_names_the_guard_and_the_config`; `test_s11_advance_healthy_records_the_guard`.
- **The audit as a test:** `test_observed_git_write_set_is_inside_the_plan[provision-fetch, provision-checkout, advance-fetch, advance-checkout, s9-fetch, s9-checkout]` (inotify + snapshot, `tests/gw_observe.py`).

**U4 tests (`tests/test_r5_u4.py`):** `test_u4_probe_records_the_venv`, `test_u4_probe_refuses_anything_but_the_pinned_venv[bare-binary, prefix, base-prefix, realpath, pyvenv-home, pyvenv-missing, import-outside-venv, symlinked-venv, version]`, `test_u4_venv_problems_row_by_row[13]`, `test_u4_pins_agree_with_s7_and_the_layout`, `test_u4_pin_is_the_runtime_sh_interpreter_at_p_prime`.


### r5.5 Mutation (new and touched guards; `tests/mutate.py` under `-O`, each mutant = the whole suite with `-x` on a /dev/shm copy re-pinned by `k4s_adopt.py`)

56 mutants: **W01–W39** (the guard: every rule, every plan row class, the S9 and S11 call sites, GW_CONFIG / `--no-auto-gc`, the host `_git_w`, the verbatim composition), **Y01–Y10** (the U4 venv pin), plus R15/R16 (retargeted: `fetch_argv` was rewritten) and V08–V12 (the probe they target changed). `--check-edits`: 218 mutants, all valid.

| Campaign | Result | NULL controls | outside_writes | File |
|---|---|---|---|---|
| py3.12.12 `-O`, r5 set (11:06–11:26Z) | 53/56 killed; V08, W04, W18 survived | 4/4 survived | false | `MUTATION-RESULTS-s3s9s10-r5-py312-O-r5set.json` |
| py3.12.12 `-O`, rerun of V08 W04 W18 with the isolating tests | **3/3 killed** | 1/1 survived | false | `MUTATION-RESULTS-s3s9s10-r5-py312-O-rerun.json` |
| py3.8.10 `-O`, r5 set, final tests | **56/56 killed** | 4/4 survived | false | `MUTATION-RESULTS-s3s9s10-r5-py38-O-r5set.json` |

**Masked guards found, and the tests that now isolate them** (test-only changes; no code changed after the first campaign):
- V08 (the declared path/version rule) was masked by `venv_problems`' executable/version rows: `test_u4_probe_refuses_anything_but_the_pinned_venv[version]` now requires the first rule's own message.
- W04 (lstat says "directory" for each write-set ancestor) and W18 (no symlinked repository ancestor) were masked by the `O_PATH|O_DIRECTORY|O_NOFOLLOW` descriptor open: `test_guard_lstat_rule_isolated_from_the_nofollow_open[write-set-dir, repository-ancestor]` replaces that open with a following one (fault injection) and requires the lstat rule's refusal.

No documented equivalents in r5. The r3/r4 mutants of unchanged code were not re-run (r4's campaigns cover them on bytes that r5 did not touch, except for the re-pinned `K4S_SIBLING_PINS` blocks).

### r5.6 Not covered / for the reviewer

- Races: a concurrent writer that changes the write set between the scan and git is outside the review's cases (pre-existing aliases). The descriptor-identity check closes only the scan's own window; `gw_post` detects afterwards and refuses.
- U4: the base prefix and resolved binary are expectations from committed evidence. Only the authorized probe on 03 and 04 can qualify the venv; a mismatch refuses before staging, with every fact recorded.
- U11 (S8) stays deferred by ruling; U8 (builder) is Part B (`s5s6s7-r5`), which consumed this package's `S9-FINAL`.


# (r4 README follows, unchanged except where §r5 supersedes it)

# K4S END prep: S1b, S3, S9, S10, S11 — CANDIDATES r4 (integration audit fix round: B2, B3, B5, B7, U1–U4, U9, U10, L4)

- **Status:** offline candidates for Sol review. **Nothing touched a host:** no ssh, scp, rsync or network (fake hosts only: user+mount+UTS namespaces); S9 `refresh-clone`, S10 and S11 were never run against a real host. Nothing was committed or pushed. r3 (`../s3s9s10-r3/`) is unchanged; this directory began as a `cp -a` copy of it.
- **Answers:** `run-r1/end-staging/INTEGRATION-AUDIT-r1/REPORT.md` (sha256 0d709b5b…, rows B2, B3, B5, B7, U1, U2, U3, U4, U9, U10, L4 and §4 specs 1–3, 8). **`RESPONSE-r4.md`** maps each row to its fix (file:line) and named tests. `RESPONSE-r3.md` / `RESPONSE-r1.md` are kept unchanged as history.
- **Written:** 2026-10-13, on 127x05, by an offline implementer. Resume log: `PROGRESS-r4.md`.
- **Rulings / ratifications needed** (details in §r4.7): the D1 extension (three more pinned support members); the END interpreter path (U4/A3); the S11 design (bundle over D4 receive, one login, depends on S10's tools); the RC-6 `commit` field's meaning; the re-pin of TOOL_PINS when s5s6s7-r4 is adopted.

## r4 — what changed

### r4.1 S9 (B3, B5; U10)

**Support members (B3/B5; a D1 extension that needs coordinator ratification).** `SUPPORT_PINS` (`s9_end_runtime.py`) adds three tracked, non-runtime_files files that the frozen identity check and S5 read from the runtime itself. Each is SHA-pinned and joins `SUPPORT_MEMBERS` (exported by tree metadata only, as the D1 six):

| Path | SHA-256 | Pin of record | Consumer |
|---|---|---|---|
| `reports/explore/k4s-confirm/SD1-MANIFEST.json` | b8ce7b4c… | K4S-MAC-MANIFEST.json (74314eda) `sd1_manifest.{path,sha256}`; S5 `FROZEN_CLOSURE` (`k4s_end_preflight.py:96`) | S5 `pre_import_pins`; frozen END default `--sd1-manifest HERE/SD1-MANIFEST.json` (`end_reference.py:426`; S7's END argv has no `--sd1-manifest`) |
| `reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` | 3501e2ac… | K4S manifest `references.t1_corpus_inventory` and `corpus.inventory`; S5/S7 `CORPUS_INVENTORY_SHA256` (`k4s_end_preflight.py:83`, `k4s_end_launch_gate.py:92`) | S5/S7 `--corpus-inventory <runtime>/<this path>` (`k4s_end_preflight.py:417-418`, `k4s_end_launch_gate.py:432-433`) |
| `reports/explore/k4s-confirm/DELTA-MANIFEST.json` | 34eca2b7… | the tracked blob at P' (`git ls-tree 98566c03`: blob 2f7fcb8f) and the freeze record's F-5 row (`reports/explore/k4s-confirm/FREEZE-RECORD-SKELETON.md:25` at P') | frozen `end_reference.k4s_pins`: `json.loads((HERE / "DELTA-MANIFEST.json").read_text())` (`end_reference.py:128`), inside `frozen_identity` |

- `check_support_pins` runs in the stdlib closure check (`verify_closure`, before any frozen import) and in `verify` (so S10 refuses a pre-r4 runtime before any login). With the K4S manifest it also requires the SD1 and corpus-inventory pins to be the manifest's own.
- **The file-hash sets do not change — proved on the real inputs.** `runtime_files` = runtime-pin-r2 names ∪ every `*.py` (`prepare_bundle.runtime_pins`) and `measurement_files` = e4v3's direct `*.py`/`*.sh`/`spec-pins.json` children; the three are `.json`, outside e4v3 and outside runtime-pin-r2. A real r4 build at P' (read-only on repo-full and the Q5 source; output in /tmp scratch, removed) gave manifest 3863cfd3…: `runtime_files_sha256` fc3dbeb4… and `measurement_files_sha256` 42b8986d…, both equal to the r3 runtime 4dd88461; its inventory is the r3 inventory plus exactly the three files at their pins (4313 → 4316 files; `changed` = `removed` = []; git members 4280 → 4283, all others identical). `REAL-S9-MEMBERSHIP-PROOF.json` records this. Existing S4 requests and bundles therefore stay valid; the runtime itself must be rebuilt (new manifest SHA) and re-staged.
- Synthetic proof in the suite: `test_r4_s9.py::test_membership_neutral_for_runtime_and_measurement_files`.

**`refresh-clone` (U10).** `s9_end_runtime.py refresh-clone --commit X [--base-commit P'] [--checkout] --record DIR`:
1. the live `verify_clone()` of REPO_FULL (F4) before anything;
2. a snapshot of every file under `.git/objects` (size, SHA-256) and of every ref;
3. ONE `git fetch` (`fetch_argv`): the prepare-clone flags (scrubbed P2-4 env with an empty HOME, `--no-replace-objects`, hooks off, `protocol.allow=never` + https only, `transfer.fsckObjects=true`) plus `gc.auto=0`, no commit-graph, no submodules, `--no-tags`, an explicit `--git-dir`, the pinned ORIGIN_URL (never the config remote) and exactly `refs/heads/k4s-end-r1:refs/remotes/origin/k4s-end-r1` **without `+`** (git itself refuses a non-fast-forward);
4. the full live `verify_clone()` again, with X (and P');
5. proofs: the tip is exactly X; no other ref moved; X descends from the old tip (and strictly from `--base-commit`); every pre-existing object file is byte-identical (objects are only added); HEAD unchanged. With `--checkout`: detached X, clean status.

Like prepare-clone, this is a network git call outside `si.git_run` (git_run disables every transport). It writes `FETCH_HEAD` and a reflog entry in the clone; the F4 checks accept both.

### r4.2 S10 (B2, B7/U9, U2, U3, U4, L4)

- **B2.** The runtime is staged at `<base>/runtime-<P12>/` (what S5 `layout()` `k4s_end_preflight.py:403-405` and S7 RC-6 `k4s_end_launch_gate.py:319-320` require). `BASE_SUBDIRS` = attempts, preflight, bundles; `runtime/` is gone. The runtime component's parent is `<base>`.
- **B7/U9: `--declare-roots`.** It writes the RC-6 `ROOTS-DECLARATION.json` exactly as S7 consumes it (`clasher.k4s.end-roots-declaration.v1`: `{schema, commit, hosts{03,04: {base, runtime, bundles{name: {path, tiers_pins_sha256, guard_job}}, repository, attempts, preflight, tools, guard_parent}}}`), from verified inputs only. The runtime comes from `S9.verify` (live clone check), and `--commit` must equal its commit. Each `--declare-bundle HOST DIR TIERS_SHA RECEIPT_SHA` goes through `bundle_header` (shared with staging): tiers-pins.json by the given SHA, its sidecar, the assembly receipt by SHA, the S4 test-only refusals, the adopted S4 (L4), a fleet-reference profile for HOST, the guard job under the Q4 parent and equal in the receipt, and runtime/measurement consistency. Per-file hashing of the bundle stays S10 staging's job. The document is self-checked by `validate_roots`, a rule-for-rule mirror of S7's (plus: both hosts declare the same `runtime-<commit12>`), written exclusively (0444) to `--out` and printed with its SHA-256. The runner commits it to **main** (ruling B6), never to k4s-end-r1. `RC6-ROOTS-DRAFT.json` and `--print-roots` are gone. `--print-layout` prints every agreed path (informational).
- **U2: `--tools-source DIR`** stages `<base>/tools/` with EXACTLY the six files the **s5s6s7-r4** S7 pins and runs (`TOOL_PINS`, read from s5s6s7-r4 `k4s_end_launch_gate.py:24-31`, file_pins `:434`, `:457`, `:480`). The pins are detach.sh 1648dfdc, k4s_end_exit_push.sh 65625fc0, k4s_preflight_push.sh c9779cfb, **k4s_end_preflight.py c7793451 (r4 L6; it was 62532c18 in r3)**, safe_input.py 806e5ebb and k4s_end_host_tool.py 22c441b1. The source is `--tools-source …/end-prep/s5s6s7-r4` (SHA256SUMS d04c6ca1, verified), where `detach.sh` is `t1-originals/detach.sh`. Each file is read through the descriptor gate (exact names, pinned size and SHA) before any login. Files are 0444 and single-link, and the dir is a-w after F. `tests/test_r4_s10.py::test_production_constants` asserts TOOL_PINS == the r4 gate's constants. A stale pin refuses before any login; re-pin whenever another Part B package is adopted. The r3 vendored copies were replaced by `tests/vendor_s5s6s7_r4/`; no test needs r3 bytes.
- **U3: `--end-inputs`** stages `<base>/end-inputs-r1/{clasher_core.abi3.so, K4-states.pkl}` from fixed 05 sources, located r4 by SHA, read-only:

  | File | SHA-256 / size | 05 source (provenance) |
  |---|---|---|
  | `clasher_core.abi3.so` | 44874fd6… / 6713424 | `/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so` (the e4v3 native; identical copies at `…/native-r6/` and `…/x4s3b-fitseed-20261013/mirror/final/*/native/`) |
  | `K4-states.pkl` | a97b1fbf… / 2829766847 | `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-publication-staging-r1/K4-states.pkl` (T1 corpus publication staging) |

  The pins equal `k4s_logic.py:10,34` (NATIVE_PROVENANCE_SHA, T1_K4_CORPUS_SHA) and S5/S7 `NATIVE_SHA256`/`CORPUS_SHA256`. **S5/S7 argv paths:** `--native <base>/end-inputs-r1/clasher_core.abi3.so`, `--corpus <base>/end-inputs-r1/K4-states.pkl`. Both are under `<base>` and outside attempts/preflight/repository/tools, as S5 `layout()` and S7 `validate_argv` require (tested against the vendored S5/S7).
- **U4: the interpreter probe**, inside the existing P-facts login (no extra login). `cd / && env -i PATH LC_ALL OMP/OPENBLAS/MKL=1 PYTHONDONTWRITEBYTECODE=1 HOME="$HOME" nice -n 19 <HOST_PYTHON> -B -c <probe> numpy torch cv2 scipy`, i.e. as END runs Python: no `-I`, `-B`, the S7 single-thread env. It records the executable, its realpath and SHA-256, the version, prefix/base_prefix, flags, and per module ok/origin/`__version__`. It REFUSES (`interpreter`) unless the executable is the declared path at `HOST_PYTHON_VERSION` and every module imports. A nonzero status refuses (`subprocess`). The required modules come from a static AST scan of the r4 runtime's END closure: numpy/torch (tier_backend, imitation.model), cv2 (replay_load / capture.replay_frames), scipy (l1_temporal, the V3 fallback's tracker). grpc is used only by the live emulator capture (`grpc_frames`), and numba is guarded. Imports run code but open no model, state or data file. The native import is S5's job. `HOST_PYTHON` = `/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12`, version 3.12.13, **pending a coordinator ruling** (see §r4.7). The probe also records `HOST_PYTHON_INFO` (`/mpac/sdicks02/repos/clasher/.venv/bin/python`) as an informational candidate that never refuses.
- **L4.** (Runner update after IR-03: `ADOPTED_S4_SHA256` = 2b8f5fb3…, the **b3-r7** `assemble_fleet_reference.py`; see RESPONSE-r4.md runner addendum.) Originally: `ADOPTED_S4_SHA256` = 76b7b7cf…, the b3-r6 `assemble_fleet_reference.py`, taken from b3-r6's verified `SHA256SUMS` after its PROGRESS said DONE (06:01:36Z). A bundle whose assembly receipt names another `assembler_sha256` (for example the audit's IA-P1 copy) refuses, both in staging and in `--declare-roots`.
- Logins are unchanged in kind: 4, plus one per component (tools and end-inputs are one receive each), plus one with `--create-base`.

### r4.3 S11 host repository (U1) — `s11_host_repository.py`, new

The `--repository` clone on 03/04: `<base>/repository`.
- It is a full, non-shallow clone; HEAD is on `refs/heads/k4s-end-r1`, at P' for preflights and at X for END.
- The work tree is writable (frozen `producer_claim`).
- It has no remote, hooks, promisor, replace refs, alternates or grafts.
- It is shipped from 05's verified REPO_FULL as a git bundle over the D4 receive.
- Each mode is **ONE ssh login**.

```bash
D=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r4; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
# after S10 --tools-source .../s5s6s7-r4 (S11 runs the S7-pinned host tool from <base>/tools):
nice -n 19 $PY -I -B $D/s11_host_repository.py provision --host 127x03 --commit <P'> --dry-run
nice -n 19 $PY -I -B $D/s11_host_repository.py provision --host 127x03 --commit <P'> --record <new dir> \
    --outside-end-window "<GO ref>, $(date -u +%FT%TZ)"
# after the END-JOB commit X is pushed: S9 refresh-clone --commit X --base-commit P', S9 equivalence --record E, then:
nice -n 19 $PY -I -B $D/s11_host_repository.py advance --host 127x03 --from <P'> --commit <X> \
    --equivalence-record E/s9-equivalence.json --equivalence-sha256 <S> --end-job-sha256 <S> --record <new dir> ...
```

**On 05, before the login:**
- the live S9 full-clone check;
- `refs/remotes/origin/k4s-end-r1` must be exactly `--commit`, which must descend from `REQUIRED_ANCESTOR` 022ec7bf (frozen `fleet_end.py:30-33`);
- advance only:
  - X must be a strict descendant of P';
  - the S9 equivalence record, read by SHA, must say P' → X, diff exactly END-JOB.json, runtime and measurement files identical;
  - the END-JOB blob OID comes from X's tree (metadata only);
- `git bundle create` of the ref, into a private `/tmp` dir that is removed afterwards:
  - provision: complete, with no prerequisites;
  - advance: `P'..ref`, whose prerequisite must be exactly P';
- the bundle header is parsed strictly (exactly one ref, at the commit), `list-heads` agrees, and the bundle is hashed.

`git bundle` is the third git call outside `si.git_run` (git_run's allowlist has no `bundle`). It uses the same fixed flags and environment, and it only reads the clone.

**The one session** (`/bin/sh -c`, through S10's `ssh_script_argv`, with `si.SSH_OPTIONS`):

| Stage | Runs | Does |
|---|---|---|
| check | the S11 host program (stdin `</dev/null`) | Loads safe_input and the host tool from `<base>/tools` through the canonical bootstrap with the S7 pins and checks the fingerprint. `<base>` is canonical. provision: repository, repository.partial and the transfer dir are absent. advance: the repository passes VERIFY at P' with a clean tree (no untracked file, so no claim exists). Records `git --version`. |
| receive | the D4 receive program (safe_input, bootstrap-verified SHA) | Creates `<base>/repository-transfer-<C12>/k4s-end-r1.bundle` exclusively (0444, single link, SHA-256). It consumes all of stdin. |
| provision | the host program | Re-hashes the bundle; `mkdir` repository.partial (exclusive); `git init --template=`; `fetch <bundle> refs/remotes/origin/k4s-end-r1:refs/heads/k4s-end-r1` (si.git_run: P2-4 env, file protocol only); `checkout k4s-end-r1`; VERIFY; `renameat2(RENAME_NOREPLACE)` to `repository`; VERIFY again. |
| advance | the host program | Re-hashes the bundle; VERIFY at P'; fetch the bundle (FETCH_HEAD only); X is a strict descendant of P' (fast-forward only); END-JOB at X has the expected OID and, with `--end-job-sha256`, those bytes through `git_show_file`, all **before** the work tree moves; `checkout -B k4s-end-r1 X`; VERIFY at X; END-JOB work-tree bytes. |

**VERIFY** (host):
- `k4s_end_host_tool.verify_clone(role="repository")`, the consumers' own check;
- HEAD = the commit and is the only ref, `refs/heads/k4s-end-r1`;
- not shallow;
- `status --porcelain --untracked-files=all` is empty;
- REQUIRED_ANCESTOR is an ancestor of HEAD;
- `.git/config` holds exactly the four `init` core keys;
- no hooks, shallow, alternates, http-alternates, grafts, commondir or config.worktree;
- the root and `reports/explore/k4s-confirm` are owner-writable.

**How the host program is shipped.** The host program is this file's canonical bootstrap block (taken from its own verified bytes) followed by `HOST_MAIN`. It is passed base64 in argv, and its SHA-256 is checked by a fixed one-line loader (`HOST_BOOTSTRAP`, no single quote) before it is executed. This is the same commitment pattern as the D4 receive bootstrap.

**After the run.** Nothing is deleted on the host:
- the transfer dir stays, and the record lists it under `host_paths_kept_needing_authorized_cleanup`;
- a refusal lists what was created or attempted.

Every stage prints `@@RC|stage|rc`. The parse is strict: every stage must return 0, there must be one CHECK and one RESULT record, and exactly one D4 receipt line, validated by `si.parse_receive_receipt`. The host program reports refusals as `@@REFUSED {code, reason}`.

### r4.4 Pin chain, files

- The pin chain is now safe_input ← end_prep_common ← s9 ← s1b ← s3 ← s10 ← **s11**. `CODE_FILES` and `tests/k4s_adopt.py` include s11. In-process importers (the tests) import `s11_host_repository` first, as the top of the DAG.
- The canonical bootstrap is byte-identical (5611c604…) in all six modules.
- New files:
  - `s11_host_repository.py`;
  - `REAL-S9-MEMBERSHIP-PROOF.json`;
  - `REAL-CHAIN-r4.json` + `chain-drivers/` (the real-input offline chain, §r4.6), `REAL-CHAIN-r4b.json` + `chain-drivers-b/` (with s5s6s7-r4, §r4.6b), `REAL-CHAIN-r4c-IR03.json` + `chain-drivers-c/` (IR-03, §r4.6c);
  - `tests/test_r4_s9.py`, `tests/test_r4_s10.py`, `tests/test_r4_s11.py`;
  - `tests/vendor_s5s6s7_r4/` (byte copies of the s5s6s7-r4 consumers and tools, SHA-pinned in `test_r4_s10.py`; also the `--tools-source` of the fake-host tests).
- Removed: `RC6-ROOTS-DRAFT.json`.

### r4.5 Tests (offline; synthetic world + namespaced fake hosts, as r3)

| Interpreter | Normal | `-O` |
|---|---|---|
| `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 | **955 passed** (101 s) | **955 passed** (102 s; 1 warning) |
| `/usr/bin/python3` 3.8.10 (pytest from `/dev/shm/s3s9s10r2-pytest38`) | **955 passed** (111 s) | **955 passed** (141 s; 1 warning) |

These are the final runs, on the final bytes, from 2026-10-13T09:17:45Z to 09:25:21Z: `nice -n 19 taskset -c 8-15`, umask 022, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`, cwd `/tmp`. The `-O` warning is pytest's PytestConfigWarning, as in r3.

**Per file:**

| Test file | Tests |
|---|---:|
| common | 30 |
| F1 | 460 (+121 for S11's kit chain) |
| F4 | 147 |
| F2 fixture | 8 |
| flow | 5 |
| **r4 S9** | **29** |
| **r4 S10** | **52** |
| **r4 S11** | **48** |
| S10 | 54 |
| S1b | 27 |
| S3 | 42 |
| S9 | 53 |
| **Total** | **955** (r3: 706 after the runner's kit sync) |

**r4 fake hosts and vendoring:**
- S11 runs its real one-login sessions in the fake hosts.
- The tools that S11's host program loads are staged by S10 from `tests/vendor_s5s6s7_r4/`.
- The S5 `layout()` and the S7 `validate_roots` / `validate_argv` run from those byte copies.

**Disclosed:** `test_r4_s11.py::test_provision_dry_run_no_login_no_leftover` was flaky under parallel suites, because it compared every `/tmp/k4s-s11-bundle-*` dir. It now tracks only its own `mkdtemp`. See §r4.5m for the mutants that were affected.


### r4.5m Mutation (`tests/mutate.py`, under -O; each mutant runs the whole suite with `-x` on a /dev/shm copy re-pinned by `k4s_adopt.py`)

There are **169** mutants: r3's 106, plus **R01–R16** (S9 support pins, refresh-clone), **V01–V20** (S10: B2, U2–U4, L4, B7), **U01–U23** (S11 local side and host program) and **Z01–Z04** (IR-03).

| Campaign | Interpreter | Result | NULL | outside_writes |
|---|---|---|---|---|
| `…-py312-O-full.json`, all 169 | 3.12.12 | 159/169 killed. Survivors: N13, N20, X17 (r3 equivalents), V17, U23 (equivalents), and U01, U05, U09, U16, U17 (masked by redundant layers) | 4/4 | false |
| `…-py312-O-rerun-c.json`: 16 = U01, U05, U09, U16, U17, plus 11 that the full run credited to the flaky test | 3.12.12 | 14/16 killed (U03 and U09 survived) | 3/3 | false |
| `…-py312-O-rerun-d.json`: U03, after its isolating test | 3.12.12 | 1/1 killed | 1/1 | false |
| `…-py38-O-r4set.json`: all 63 r4 mutants, plus the 8 r3 mutants credited to the flaky test | 3.8.10 | 68/71 killed; survivors V17, U09, U23 (documented equivalents) | 4/4 | **true: other threads** (below) |

**Final account:**
- On 3.12, **163/169** are killed. The only survivors are documented equivalents: N13, N20, X17 (r3), and V17, U09, U23 (r4, in `mutate.py` `EQUIVALENT`).
  - **V17** (same runtime on both hosts) is implied by V14 (runtime-<commit12> per host).
  - **U09** (host HEAD == commit) is implied by U10 (symbolic HEAD) and U11 (the only ref).
  - **U23** (the host re-hash of the bundle) is masked by the D4 receive program's own SHA-256 check in the same session.
- On 3.8, every r4 guard other than those three is killed.
- Every new r4 guard is either killed by a named test or documented as equivalent.

**How the campaigns found weak tests:**
- Two earlier campaigns were stopped because their bytes went stale with the runner updates; both are disclosed in PROGRESS. They exposed V11 and V14, which were masked in the tests. Two new tests now kill them: `test_parse_python_requires_exactly_one_record` and `test_validate_roots_runtime_is_runtime_commit12_on_both_hosts`.
- The final campaign exposed U01, U05, U16 and U17, also masked. New tests kill them: `test_tip_mismatch_refused_before_any_bundle`, `test_bundle_heads_are_checked_independently_of_the_header` and `test_host_end_job_checks[4]`.
- U03 is now killed by `test_advance_requires_a_strict_descendant_before_any_bundle`.

**The flaky test.** The full 3.12 run credited 11 mutants only to the flaky dry-run test: T06, T17, N04, N05, N07, X03, X05, X07, R16, U03, U08. They were re-run with the test fixed. All except U03 were killed by real tests; U03 was killed later in rerun-d.

**The 3.8 `outside_writes: true`.** During that window, other threads created `/mpac/sdicks02/integ-e` (about 09:11Z), bumped the mtime of `/mpac/sdicks02/repos` (about 09:02Z) and created `end-prep/b3-r7` (the IR-03 S4 worker). None of these names occur in this package. The mutant copies live only in `/dev/shm/s3s9s10-mut-*` and `/tmp`, and both 3.12 runs over the same mutants reported false.

**Scope note.** The unchanged r3 mutants ran on 3.12 only in r4. r3's own 3.8 campaign covered them on the r3 bytes.


### r4.6 Real-input offline chain (audit drivers re-run; `REAL-CHAIN-r4.json`, `chain-drivers/`)

The audit's fake-host chain was re-run against the r4 code. It used REAL 05 inputs, read-only: repo-full at P', the Q5 source, the T1 corpus staging, the e4v3 native, the s5s6s7-r3 tools (this first chain predates the s5s6s7-r4 adoption; see §r4.6b), the S3 guard job `guard-127x03-pf00` and the adopted b3-r6 S4. The host was a fake 127x03 (namespace). There was no network and no host. All scratch was removed afterwards.

| Step | Result |
|---|---|
| S9 r4 build at P' | manifest 3863cfd3…; runtime_files fc3dbeb4 / measurement 42b8986d = r3; +3 support files exactly (`REAL-S9-MEMBERSHIP-PROOF.json`) |
| b3-r6 S4, real requests 03-pf00 / 04-pf00 | rc 0; 03 manifest ca4ce6ef (= the audit's), assembler 76b7b7cf (adopted) |
| S10 `--declare-roots` (real runtime + both real bundles) | rc 0, sha b74ded25…; **accepted by the real, unmodified S7 r3 `validate_roots`** |
| S10 → fake 03 (`--create-base`, runtime, tools, end-inputs, bundle, guard job) | rc 0, 10 logins (P-check, P-facts, base, 5 receives, F, POST); runtime at `<base>/runtime-98566c032d0b`; interpreter probe of the bound 05 e4v3-venv (SIMULATED A3): torch 2.10.0+cpu, numpy, cv2, scipy imported |
| S11 provision from the real repo-full | rc 0, **1 login**; host repository at P' on k4s-end-r1, host-tool `verify_clone` (repository) OK |
| frozen `end_reference.frozen_identity` on the staged tree (real native + corpus digests, real bundle, r4 runtime) | **OK** (B3/B5 closed for the frozen END identity check) |
| S5 `run` (staged tools/k4s_end_preflight.py) on the fake 03 | listings_before, bundle_stamp, input_locations, guard_repo, **repository_clone**, frozen_git_env, **pre_import_pins**, frozen_import, frozen_helpers all pass; it stops at frozen_identity ONLY on the deliberate stub native (no backend, torch, native or pickle load; measure_called false, claim false) |
| S9 refresh-clone → equivalence (scratch origin with a synthetic END-JOB X) | rc 0; only the END ref moved, objects unchanged; equivalence P' → X: diff = END-JOB.json, files identical |
| S11 advance to X | rc 0, **1 login**; prerequisite exactly P'; END-JOB OID + bytes checked before the work tree moved |
| frozen `end_evidence` / `end_job` / `producer_registry` / `producer_claim` on the ADVANCED fake-host repository | all OK; the claim landed in the writable work tree (U1 closed against the frozen code) |

Audit-only deviations, as listed in the JSON:
- SIMULATED-A3: the interpreter is 05's venv;
- the S5 stub native and the missing `--compare-bundle`;
- the job dir made by hand;
- the scratch origin/clone pair for the X leg.


### r4.6b Chain-b with the adopted s5s6s7-r4 (`REAL-CHAIN-r4b.json`, `chain-drivers-b/`)

After s5s6s7-r4 was DONE (SHA256SUMS d04c6ca1), the chain ran again with the r4 Part B. Inputs were the same kind of real 05 inputs (read-only) and a fake 03, with no host and no network; scratch was removed afterwards.

| Step | Result |
|---|---|
| S9 r4 build at P' | runtime_files fc3dbeb4, measurement 42b8986d, +3 support files |
| b3-r6 S4: 03-pf00, 03-rd00-a00, 04-pf00 (real requests) | rc 0 each |
| S10 `--declare-roots` (3 real bundles) | rc 0 |
| S10 → fake 03 with `--tools-source s5s6s7-r4` | rc 0, 10 logins; `tools/k4s_end_preflight.py` = c7793451 (r4) |
| S11 provision | 1 login, rc 0 |
| **r4 S7 `build-argv`** (U5) for preflight-127x03-l00, `--native <base>/end-inputs-r1/clasher_core.abi3.so --corpus <base>/end-inputs-r1/K4-states.pkl` | rc 0. The r4 `validate_roots` accepted S10's declaration, and `validate_argv` accepted S10's end-inputs paths. **The layout matches; no mismatch.** |
| **r4 S5 `run`** with exactly that argv's options (only `--native` swapped for the stub) | every check passes up to `frozen_identity`, which stops only on the stub native (measure/claim false) |
| frozen `frozen_identity` (real staged native + corpus) | OK |
| refresh-clone → equivalence → S11 advance, with X = P' + **the s5s6s7-r4 builder's END-JOB** (06939fa7) | rc 0; advance took 1 login |
| frozen `end_evidence` / `end_job` / `producer_registry` / `producer_claim` on the advanced fake-host repository | all OK |

**Disclosure:** a driver path bug in my part-B script made its S5, frozen_identity and frozen-job steps fail before doing anything (wrong fake-host prefix). They were re-run as part C with only that path fixed. Both runs are in `steps`.

### r4.6c IR-03: 03 has no idle resident (runner update 2; proposed ruling, implemented)

- **The problem.** 03's pinned idle resident, cache service PID 2180947, is gone (`end-prep/IDLE-03-RETIREMENT-PROPOSAL.md`, proposed ruling IR-03).
- **S3 change.** S3 now builds and verifies guard-job admissions from an explicit constant, `END_ADMISSIONS = {127x03: (system-bus-admission.json,), 127x04: (system-bus-admission.json,)}` (`s3_guard_job.py`). It no longer uses `S1B.NAMES[host]`. The constant applies to:
  - the job's top level, which must be exactly `FROZEN-T1.json`, `repo` and `system-bus-admission.json`;
  - the repo role's E3 names;
  - `committed_inputs`, which ignores S1b's extra 03 idle row;
  - `verify`, where the manifest's admissions must be exactly the constant and the top level must match.
- **S1b is unchanged.** Its `NAMES` / copy contract is untouched because A1b already ran under it. The real A1b manifest (64c2fc8d) still has the 03 idle row; S3 does not use it.
- **S10 change.** S10's bundle check now requires the bundle's guard admissions to equal `S3.END_ADMISSIONS[host]`. **Consequence:** a b3-r6 03 bundle, which still pins idle-services.json, is refused, so the 03 bundles need the IR-03 S4 (b3-r7). The 04 bundles are unaffected.
- **Tests:**
  - `test_r4_s10.py::test_ir03_03_guard_job_is_bus_only_while_s1b_keeps_its_contract`;
  - `::test_ir03_guard_job_with_idle_services_is_refused[file-in-job|manifest-row]`;
  - `::test_ir03_bundle_with_03_idle_admission_refused`;
  - the updated `test_flow.py::test_s3_build_and_verify` and `test_s3.py::test_git_replace_ref_and_env_cannot_substitute_bytes`;
  - mutants Z01–Z04.
- **Real-input check, chain-c (`REAL-CHAIN-r4c-IR03.json`):**
  - r4 S3 built a REAL 03 pf00 guard job from repo-full at P' and the real A1b manifest; it is bus only, and S3 verify is OK. S10 staged it to a fake 03.
  - The frozen `fleet_validity.ReportingGuard` constructor and `check_admissions` (`fleet_validity.py:110-114`) **accept** it when the bundle's guard admissions are the IR-03 shape (the b3-r7 shape, simulated in memory on a real b3-r6 bundle).
  - It **refuses** the b3-r6 shape, where idle is pinned but the file is absent from the job (FileNotFoundError).
  - It **refuses** a job that carries an unpinned stale idle-services.json ("Every existing guard admission must be pinned").

### r4.7 Open items and rulings needed

0. **IR-03 (ratify; implemented as proposed).** 03 guard jobs and bundles carry the system-bus admission only. This requires the 03 bundles to be rebuilt by b3-r7, and the 03 guard jobs (pf00, rd00-a00, rd00-a01) to be rebuilt with this S3 (end-staging/guard-jobs were built with r3 S3 and hold idle-services.json, which r4 S3 verify refuses).
1. **D1 extension (ratify).** SD1-MANIFEST.json, the t1 corpora.json and DELTA-MANIFEST.json become SHA-pinned runtime support members (§r4.1). The proof of membership neutrality is in REAL-S9-MEMBERSHIP-PROOF.json.
2. **END interpreter (A3/U4 ruling).** Committed evidence says the K4S reporting supervisor and T1's END ran `/mpac/sdicks02/repos/clasher/.venv/bin/python -B` (k4s-confirm/runtime.sh 67249aac; stop-drill `host-admission-smoke.json` cmd lines; END plan research §"Interpreter" (T1 A5)). That is a venv whose `/proc` exe resolves to the uv `cpython-3.12.13` binary, the path the reporting supervisor admission receipts record. torch therefore came from that venv's site-packages, plus PYTHONPATH from runtime.sh; T1's END used PYTHONPATH = runtime `imitation/evaluation/runtime_dependencies` + `reports/strategy_council_20260928/imitation`. The bare uv binary (the current pinned constant) is therefore **expected to fail the torch import** unless torch is in its base or user site. The probe will show which. Proposed ruling: pin the venv path (and its realpath SHA from the probe) or install torch for the base interpreter. `HOST_PYTHON`/`HOST_PYTHON_VERSION` are the only constants to change. U5 (`build-argv`, s5s6s7-r4) must use the same path, plus the PYTHONPATH the frozen imports need (`imitation/evaluation/d1.py` imports `own_cycle` from `runtime_dependencies`), which S7 allows (`ENV_OPTIONAL`).
3. **S11 design (ratify).** S11 ships a git bundle of REPO_FULL over D4 with one login per mode, instead of a host https clone. It depends on S10's tools component (S11 verifies with the staged, S7-pinned host tool). Three more git calls run outside git_run on 05: `bundle create` and `list-heads`, read-only. On the host, FETCH_HEAD stays in the repository (nothing is deleted on hosts), and the transfer directory stays and needs a later authorized cleanup.
4. **RC-6 `commit`.** `--declare-roots` sets it to P', the runtime's commit; `--commit` must equal the S9 manifest's. The declaration itself lives on main (B6), so it cannot name its own commit. Ratify this meaning.
5. **Part B pins: done for s5s6s7-r4.** `TOOL_PINS` = the r4 S7 pins, and the vendored consumers are r4. **The end-inputs layout agrees with r4:**
   - r4 S5 `layout()` and S7 `validate_argv` accept any K4S-owned file under `<base>` outside attempts/preflight/repository/tools;
   - r4 `build-argv` takes `--native` / `--corpus` from the operator (END: from PREFLIGHT-VERIFIED);
   - `<base>/end-inputs-r1/clasher_core.abi3.so` and `<base>/end-inputs-r1/K4-states.pkl` pass both, shown by the r4 `build-argv` run in chain-b (§r4.6b);
   - no mismatch.

   The r4 S7 also pins `HOST_PYTHON` to the same pending path as S10's probe (asserted equal in the tests): one ruling changes both.
6. **Runtime rebuild.** The staged runtime must be the r4 build (new manifest SHA). S4 requests and bundles are unaffected (same runtime/measurement canonical SHAs), but each request's `runtime_root` names the r3 output path. Re-point it or rebuild at that path (a new S9 output must not overwrite the old one).
7. Not verifiable offline: the real interpreter on 03/04 (U4/V1), real transport, host git 2.25 behaviour on the real bundle (the fake hosts run 05's own git 2.25.1, the same Ubuntu 20.04 build), free space.

---

## r3 history (unchanged below; superseded where §r4 says so)

### END-FULL-F1: the canonical bootstrap (r3)

Every read of a sibling file before (or beside) the shared layer goes through bootstrap-r1's **canonical bootstrap**, pasted **verbatim** (BEGIN..END markers included; `tests/k4s_bootstrap_r1.py` is the vendored source of record, sha256 `5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b`, 8372 bytes, CANONICAL-READY 2026-10-13T00:13:28Z) in `end_prep_common.py` and in all four entrypoints. Its contract: normalized absolute path taken as Python was given it (never `abspath`/`realpath`), the outcome name families on every component, a component-wise `O_DIRECTORY|O_NOFOLLOW` walk from `/`, the leaf regular / `st_nlink == 1` / exactly the pinned size before any byte, the SHA-256 pin, then exactly the verified bytes executed (never re-read by pathname).

- `end_prep_common.py` loads `safe_input.py` (pins `SAFE_INPUT_SHA256`, `SAFE_INPUT_SIZE = 133606`), then checks the constants fingerprint and the reader/receive program SHAs as before.
- **Audit result:** r2's entrypoints also imported `end_prep_common.py` by `sys.path`, and `C.import_sibling` imported s1b/s3/s9 the same way. In r3 each entrypoint loads `end_prep_common.py` with `_k4s_common()` (the canonical loader) and its siblings with `C.load_sibling(name, *K4S_SIBLING_PINS[...])`. No module edits `sys.path` or imports a sibling.
- **Pin chain** (acyclic; each module pins the files it loads): safe_input ← end_prep_common ← s9 ← s1b ← s3 ← s10. After editing any module, run `python3 -I -B tests/k4s_adopt.py --root <dir>` (recomputes the pins in dependency order; `--canonical FILE` re-pastes the block; `--check` reports drift). A stale pin refuses the load.
- An already loaded module of a sibling's name is reused only if the bootstrap loaded it from the same path with the same pins (`__k4s_bootstrap__`); in-process importers (the tests) therefore import `s10_stage_host` first.
- Conformance: `tests/test_f1.py` runs the vendored bootstrap-r1 kit (`tests/k4s_bootstrap_kit.py`, `tests/kit_harness.py`, byte copies, sha-pinned in the test) against every entrypoint × every pinned file it loads; see §Tests.

### safe_input pin

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

### Files

| File | Role | Touches hosts |
|---|---|---|
| `safe_input.py` | the vendored r3 layer (unchanged) | — |
| `end_prep_common.py` | the canonical bootstrap (verbatim) + the pinned safe_input load and `load_sibling`; output confinement; `publish_dir` (renameat2 RENAME_NOREPLACE); `unlink_own`/`chmod_readonly` on gated fds; `Record`; `ScrubbedEnv` (P2-4 env for frozen children) | — |
| `s1b_copy_admissions.py` | S1b: the three admissions through the pinned reader, written in E3 layout | yes, read-only, **2 logins** |
| `s3_guard_job.py` | S3: guard job builder/verifier (`-rdRR-aNN` and `-pfNN`) | no |
| `s9_end_runtime.py` | S9: `prepare-clone`, `locate`, `build`, `verify`, `equivalence` | no (network clone from GitHub only) |
| `s10_stage_host.py` | S10: stages runtime / bundles / guard job / (r4) tools / end-inputs onto one host; (r4) `--declare-roots`, `--print-layout` | yes, 4 + N logins (+1 with `--create-base`) |
| `s11_host_repository.py` | (r4) S11: `<base>/repository` provision / advance | yes, 1 login per mode |
| `RESPONSE-r3.md` | END-FULL finding → change (file:line) → named tests | — |
| `RESPONSE-r1.md` | the r2 response (history, unchanged) | — |
| `SAFE-INPUT-R3-README-ERRATUM-receive-sha.txt` | byte copy of the runner's committed receive-SHA erratum | — |
| `PROGRESS-r3.md` | resumable log | — |
| `tests/` | offline pytest suite (synthetic world, namespaced fake hosts, conformance kit) + `mutate.py`; `fixture_guard_job.py` (the synthetic world + the F2 guard-job CLI); `k4s_adopt.py` (canonical paste + pin chain); `k4s_bootstrap_r1.py`, `k4s_bootstrap_kit.py`, `kit_harness.py` (vendored from bootstrap-r1) | no |
| `MUTATION-RESULTS-s3s9s10-r3-py312-O.json`, `MUTATION-RESULTS-s3s9s10-r3-py38-O.json` | final r3 mutation campaigns | — |
| `SHA256SUMS` | every file above | — |

r3 dropped r2's `MUTATION-RESULTS-r3-*.json` (they describe the r2 sources; still in `../s3s9s10-r2/`). r1-only artifacts were dropped earlier: `RUNNER-PATCH-E3.diff`, `s9-locate-caeeecdc.json`, `s10-dry-run-EXAMPLE-synthetic-admissions.txt`, and the r1 tests. `--inputs`, `--admissions-dir`, `--source` and `--ssh` are gone.

Run everything on 127x05 with `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B` (3.12, stdlib only). The code is Python 3.8-compatible, and the suite also runs on /usr/bin/python3 3.8.10. Frozen children (S3, S9) are never run with `-O`. Every SHA argument below is printed by the previous step.

### S1b — admissions (Q2, E3; S1b-F1)

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

### S3 — guard job (Q2/Q3/Q4; S3-F1/F2/F3)

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

### S9 — END runtime (Q5, D1, D2, E1–E5, R6, P2-2, full clone)

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

### S10 — staging onto one host (A2; S10-F1/F2/F3/F4, D4, R7)

```bash
nice -n 19 $PY -I -B $D/s10_stage_host.py --print-layout                              # r4: layout (informational)
# r4: RC-6 declaration (S7 schema): --declare-roots --commit <P'> --runtime-manifest-for-checks <S9 out>
#     --runtime-manifest-sha256 <S> --declare-bundle <host> <dir> <tiers SHA> <receipt SHA> ... --out <new file>
# r4: + --tools-source <adopted s5s6s7 dir> --end-inputs   (components tools/ and end-inputs-r1/)
nice -n 19 $PY -I -B $D/s10_stage_host.py --host 127x03 --create-base \
    --runtime <S9 out> --runtime-manifest-sha256 <S> \
    --bundle <S4 bundle dir> <tiers-pins SHA> <assembly-receipt SHA> \
    --guard-job <S3 out> --guard-job-name k4s-end-guard-r1-rd00-a00 --guard-manifest-sha256 <S> \
    --record /mpac/sdicks02/k4s-runner/run-r1/end-staging/s10-127x03-r1 --outside-end-window "A2 GO <ref>, $(date -u +%FT%TZ)"
# later attempts: --runtime-manifest-for-checks <S9 out> --runtime-manifest-sha256 <S> --bundle ... --guard-job ...
```

**Roots (RC-6). r4: superseded by §r4.2 (`runtime-<P12>` directly under `<base>`, plus `tools/` and `end-inputs-r1/`; `--declare-roots`).** `<base>` = `/mpac/sdicks02/jobs/clasher/k4s-end-r1` on 03 and `/mpac/sdicks02/jobs-k4s/k4s-end-r1` on 04 (`si.END_BASES`, the same as S5/S6/S7). It holds:

| Directory | Contents | Created by |
|---|---|---|
| `runtime-<P12>/` (r3: `runtime/runtime-<P12>/`) | the runtime, a-w | S10 |
| `tools/`, `end-inputs-r1/` (r4) | S7-pinned tools; native + K4 corpus, a-w | S10 |
| `bundles/<name>/` | bundles, a-w | S10 |
| `attempts/` | END attempts | dir: S10 (`--create-base`); contents: S7 |
| `preflight/` | preflights | dir: S10 (`--create-base`); contents: S7 |
| `repository/` | the `--repository` clone | S11 (r4) |

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
| P-facts | hostname, df and who, each `x=$(cmd)` with its own echoed status; any nonzero status refuses before its output is used; free space ≥ bytes + 50 GiB; r4: the interpreter probe (§r4.2 U4) |
| [base] | `--create-base` only: a receive that creates `<base>` exclusively with attempts/, preflight/, bundles/ (r4: no runtime/) |
| R-*i* | one `si.remote_receive` per component (D4); see below |
| F | one session: the reader re-checks every `.partial` is a canonical dir and every final is absent; then `chmod -R a-w` (runtime/bundles) and `mv -n -T`, with every step's status echoed and checked |
| POST | `si.remote_check`: every final has the dev/ino the F check saw for its `.partial`; a-w (or a writable guard dir); the `.partial` is absent |

Each R-*i* receive:
- creates `<target>.partial` exclusively under its canonical parent;
- creates directories with mkdirat, and files with O_CREAT|O_EXCL|O_NOFOLLOW, streamed, hashed, fsynced, mode 0444/0555;
- re-checks E4 SHA pins and E5 blob OIDs on the host;
- returns a strict receipt with size, SHA, nlink == 1 and mode for every file (R7).

Nothing is ever deleted on a host. A refusal after the first receive lists the exact paths created or attempted (`host_paths_created_or_attempted_needing_authorized_cleanup`) in `S10-REFUSAL-*.json`.

### Tests (offline, synthetic only)

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

### Mutation check (adoption points and the r3 guards, under -O)

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

### Deviations, residuals, and what cannot be verified offline

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

## r7 (2026-10-13T22:17:17Z, runner; A2 03 refusal fix)

A2 on 127x03 (GO eb73333e) refused in S10's P-facts interpreter probe at 2026-10-13T22:14:47Z: the declared interpreter `/mpac/sdicks02/repos/clasher/.venv/bin/python` imports numpy and torch but not cv2 or scipy (2 logins, P-check + P-facts; nothing created on the host). The r4/r5 module list came from a static scan that included non-fleet paths. The FLEET END path is `fleet_reference.py` → `replay_load.FleetBackground` ("deliberately no perception on fleet references") → `fleet_corpus_worker` → `TierBackend`; cv2 is imported only by `replay_load.load_worker` (the Mac / `--linux-dry-run` perception load) and scipy only by the vision trackers. A blocked-import run of `end_reference.py --help` under P' runtime.sh's PYTHONPATH loads none of torch/numpy/cv2/scipy at import time. K4S reporting ran its games through this same venv (runtime.sh at P').

Change: `HOST_PYTHON_IMPORTS = ("numpy", "torch")` (s10_stage_host.py), test expectation `tests/test_r4_s10.py`, chain re-pinned (s10, s11). S9 is unchanged (bdc2deeb), so the builder pins and the production runtime stay valid. S5's preflight (backend construction and background slots on the host) remains the live arbiter of what END imports.

## r8 (2026-10-14T00:04:51Z, runner; RO-1 COORDINATOR 02656d67)

S10 stages the declared EMPTY runtime directories `RUNTIME_EMPTY_DIRS = ("reports/strategy_council_20260928/engine-speed/results",)` (frozen es_common.py:20 mkdirs it at import; the a-w staged runtime made A4 03 l01 fail). `runtime_dirs(manifest)` appends them to the S9 inventory dirs after refusing if already tracked, holding files, or parentless; the receive creates them empty before a-w. Runtime files/manifest unchanged. Test: tests/test_r8_ro1.py. Chain re-pinned (s10, s11). For already-staged hosts the one-off host step is end-staging/a4/ro1-results.sh.

### r8 fix (Sol RO1-r1 #4, 2026-10-14T00:23:29Z)

`tests/fixture_guard_job.py` world_files() gains the synthetic `reports/strategy_council_20260928/engine-speed/es_common.py`, the parent of RUNTIME_EMPTY_DIRS, as at P'. The parentless refusal stays tested in test_r8_ro1.py. Full suite rerun in four modes.
