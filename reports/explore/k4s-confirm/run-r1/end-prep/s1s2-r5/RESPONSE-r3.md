# S2 r4 response to SOL-REVIEW-END-S2S4-r3 (S2: REQUEST_CHANGES)

**Candidate:** `s1s2-r4/` (a copy of `s1s2-r3/`, which is untouched), written offline on 127x05 on 2026-10-12 from 21:28Z. No SSH, no commit, no push, no host access. S1 `s1_copy_end_sources.py` is byte-identical (`b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65`). `S2:L` below is a line of `s2_end_evidence.py` in this directory (SHA in `SHA256SUMS`).

**Authority:** SOL-REVIEW-END-S2S4-r3 (all, including "What r4 safe_input adoption must preserve"); coordinator rulings P2-1 (17:30Z), P2-4 (18:03Z), D1–D4 (18:19Z), E5 / full clone / frozen-reader wrapper (21:28Z), read with `git show origin/main:reports/strategy_council_20260928/COORDINATOR.md`. The shared layer is `safe-input-r2/safe_input.py` SHA-256 `f9ca49267dd350cf7ca6fc64b25ce93f53d8e63e9326356dbc72574ec380b648`, vendored byte-identical as `safe_input.py`.

## S2-R3-F1 (BLOCKING): git replacement refs and inherited repository overrides

| Change | Where |
|---|---|
| The layer is loaded once from the vendored file: no-follow, regular, `st_nlink == 1`, ≤ 1 MiB descriptor read; SHA-256 checked with stdlib `hashlib` on the exact bytes then executed (no import path, no re-open); `constants_fingerprint()` must be `6661ca0b…`. | `S2:102–138` |
| S2's own `git()` (`subprocess.run(["git","-C",…])`, inherited environment) is deleted. Every git call is `si.git_run` (`Checkout.run`) or `si.git_show_file` (`Checkout.show`): exact `GIT_FIXED_ENV` + fresh empty HOME, `--no-replace-objects` + `GIT_NO_REPLACE_OBJECTS=1`, hooks/fsmonitor off, transports off, explicit `--git-dir`/`--work-tree`, static refusal of alternates/grafts/shallow/gitfile/undeclared commondir/driver config, rc checked before stdout, object type+size+OID verified. | `Checkout` `S2:270–294`; `full_commit` `S2:296–300` |
| Every committed read passes its expected SHA-256 to `si.git_show_file`: completion (pin), records (pins), launch (table of record / S1), supervisor exit (completion binding), mhz/census (verified S1 copy). Production refuses a read without one. | `pinned_completion` `S2:598`; `build.item`/`phase_pin` `S2:679–712` |
| Linked (detached) worktrees are still supported, now by declaration: `--git-dir` + `--git-common-dir` (production: only `/tmp/k4s-s2-<name>` of the main checkout, git dir `<main>/.git/worktrees/<name>`); undeclared, `<wt>/.git` (a gitfile) refuses before git runs. | `Roots.worktree_git_dirs` `S2:384–402`; CLI `add_worktree_options` |
| Frozen readers (ruling 21:28Z "frozen-reader interim"): before `end_evidence.end_evidence`, every artifact's committed blob is read through `si.git_show_file` with the item SHA and its work-tree file hashed through the si descriptor gate (= item SHA); then the frozen code (whose `fleet_end.artifact` runs its own `git -C … show` / `merge-base`) runs only inside `frozen_git_env()`: the checkout must have no `refs/replace/` (`si.git_run for-each-ref`, which also runs the static preflight), `os.environ` is REPLACED by `si.GIT_FIXED_ENV` + a fresh empty HOME + the declared `GIT_DIR`/`GIT_WORK_TREE`, restored afterwards; git must leave HOME empty. | `frozen_git_env` `S2:303–326`; `validate` `S2:1006–1020`; `frozen_checks` `S2:1034` |
| Nonzero-status handling preserved: `si.run_checked` refuses before stdout is visible; `merge-base --is-ancestor` requires rc 0. | `S2:972` |

**Reviewer-probe regression controls (full entrypoints; `tests/test_s2_r4_git.py`):**
- static `git replace <completion blob> <games canary>`: positive control (raw `git show` returns the canary); `build` succeeds with the true completion (pinned SHA held, no canary in the evidence); `validate` refuses on `refs/replace/` and the frozen reader's git never runs (audit); `diagnose-clock` reports the true census SHA; unit: `Checkout.show` returns the original bytes.
- inherited `GIT_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_INDEX_FILE`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT/KEY/VALUE`, `GIT_REPLACE_REF_BASE`, a hostile `HOME/.gitconfig`: positive control for `GIT_DIR` (raw git serves the foreign repository); `build` and `validate` (frozen reader included) both succeed on the true bytes under each.
- `frozen_git_env` sets exactly the P2-4 set (+ HOME, XDG_CONFIG_HOME, declared GIT_DIR/GIT_WORK_TREE), removes HOME, restores the environment.
- static repository indirection (alternates, grafts, `core.hooksPath`, `core.fsmonitor`, a filter driver, an include, a gitfile `.git`): refused with **no git process at all** (audit: zero `subprocess.Popen`).
- linked worktree: undeclared refuses; declared validates; a wrong common dir refuses (`commondir`). Production worktree rule unit test.
- the committed blob is checked by si before the frozen reader: work-tree-only census bytes named by the evidence refuse with `committed blob pin mismatch`, frozen git never runs.
- loader: a layer with other bytes, an edited constant behind a moved SHA pin (fingerprint), and a hard-linked layer each refuse to start; an unchanged copy loads.

## What r4 safe_input adoption must preserve (each item)

| Item (Sol r3) | r4 |
|---|---|
| Lexical refusal before access | `gate_paths` keeps its pure first pass over EVERY path (`S2:442–447`): `lexical()` = absolute/normalised/safe chars + `forbidden_reason()` (now `si.name_gate`, the shared case-insensitive family denylist, plus S2's stricter local rules: any `end` component, `t1-*` trees, both host job roots; `S2:330–360`) + allowed root + name rule, with no syscall; tests `test_every_path_is_lexically_gated_before_any_is_stated`, the `no_syscalls` controls and the descriptor-helper controls (now through `gate_paths`). |
| Complete role/root validation | One `si.Policy` per `gate_paths` call, one role per supplied path (`S2:448–461`): directories with their exact names/patterns (`REPOSITORY_EXACT`/`PATTERNS`, `CODE_PATTERNS`, s1-dest; `S2:404–410`), files with exactly their leaf, outputs a write role with exactly their leaf. |
| S2's all-path lexical pass, profile source exclusivity, strict field checks | Unchanged (`load_profiles`, `check_profile`); strict JSON is now `si.loads_strict`. |
| regular/nlink at walk and at descriptor | `si.check_dir` / `si.open_input` / `si.read_bytes` / `si.sha256_input`: fstatat (regular, `st_nlink == 1`) before open, fstat after. The descriptor `gate_paths` opened is the one `read_gated` consumes (`S2:491–499`): gate-to-read identity by construction. |
| Exclusive outputs | `si.check_absent` at the gate, `si.Writer.create_excl` (`O_CREAT|O_EXCL|O_NOFOLLOW`) at write (`write_gated` `S2:513–519`). |
| Fixed pre-import frozen closure verification | `bootstrap` reads the manifest with the approved SHA and every pinned file with its pin through `si.read_bytes` (`S2:799–841`); ClosureFinder/VerifiedLoader unchanged. |
| Exact artifact/S1 bindings | Unchanged (`structure`, `s1_check`, `load_s1`); `load_s1` still refuses a direct call at a forbidden location purely (`S2:613`). |
| Test-only stamps, immutable clock-join refusal, report-only diagnosis | Unchanged. |
| Status-preserving subprocess handling | All git through `si.run_checked`. |

## Production reads take expected SHAs (accepted residual condition, 18:19Z)

Every work-tree/file read passes an expected SHA (S1 receipt, profile, evidence, frozen closure, S1 copies with size). Git reads pass one wherever a pin exists; `diagnose-clock --repository` reads end-sources at a full commit id with no other pin: those bytes are content-bound (si verifies the blob re-hashes to the OID listed in that commit's tree), which the same-size-rewrite residual cannot affect.

## Intentional test changes (r4 stricter or restructured)

- Messages of refusals now made by safe_input read `<label>: safe_input refused [<code>]: …`; tests match the code (e.g. `[nlink]`, `[symlink]`, `[root]`, `[exists]`, `[json]`, `[missing]`) — the refusals and the zero-touch assertions are unchanged.
- Unit tests of removed helpers (`open_dir`, `read_confined`, `write_new`) now exercise `gate_paths`; `test_gate_to_open_identity` now proves that the gated descriptor is the one read (a post-gate replacement is never read).
- A planted symlink at `--out`/`--result` refuses as `[exists]` (never followed; victim unchanged).
- `test_games_path_item_refused_before_any_read` renamed `test_outcome_dir_item_refused_before_any_read`: pytest names `tmp_path` after the test and a `games` token there is itself refused.
- Audit harness: `stat-ok` events record `dir_fd`; the allowlist test admits the pinned layer file, the declared `.git` and its preflight components, and tempfile's directory probe; the gate/profile violation check exempts only the interpreter's own `sys.prefix` chain (the e4v3 venv lives under `/mpac/sdicks02/jobs`; r3 failed the same tests under that interpreter for this reason).
- `test_validate_refuses_worktree_artifact_differing_from_commit` now requires S2's own `work-tree pin mismatch` (stricter than the frozen reader's message).

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
