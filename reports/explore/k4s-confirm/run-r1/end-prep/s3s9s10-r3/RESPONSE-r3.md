# RESPONSE r3 — Part A (end_prep_common, S1b, S3, S9, S10) to SOL-REVIEW-END-FULL-r1

Candidate: `run-r1/end-prep/s3s9s10-r3/` (began as `cp -a s3s9s10-r2`; r2 is unchanged). Offline only: no ssh, no host step, no network clone (synthetic `file://` repositories), nothing under real `games/` or any real outcome file was opened, nothing committed. Line numbers refer to the r3 files. Vendored `safe_input.py` is unchanged (safe-input-r3, sha256 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`).

Scope (runner assignment): END-FULL-F4; the Part A side of END-FULL-F2; the end_prep_common half of END-FULL-F1, extended to every Part A entrypoint. F3, F5 and F6 are Part B (s5s6s7-r3).

## END-FULL-F4 (HIGH): the full-clone verifier is now a mandatory, live precondition

| Fix | Where |
|---|---|
| `require_full_clone(commits, path)`: builds its own read-only policy (`clone_role`) and runs `verify_clone` **every call**; nothing is inferred from the directory name or from `repo-full-PREPARE.json` | `s9_end_runtime.py:480` |
| `verify_clone` strengthened: canonical real root / `.git` / `.git/objects` / `.git/objects/pack` (no gitfile, no symlink); `CLONE_ABSENT` names absent in any form (hooks — executable or empty —, shallow, grafts, alternates, http-alternates, commondir, config.worktree); config in a strict grammar with the exact key set (promisor, partialclonefilter, core.partialclonefilter, extensions.partialClone, includes, drivers, same-line variables after a header, bare keys, quoted/escaped/commented values, `[a.b]` sections, non-UTF-8 refuse) plus origin / format 0 / `bare = false`; pack directory only `pack-<oid>.{pack,idx,keep,bitmap,rev}` (no `.promisor`, no `tmp_pack_*`); git's own `rev-parse --absolute-git-dir --is-bare-repository --is-shallow-repository --show-toplevel` must say `<REPO_FULL>/.git`, false, false, `REPO_FULL`; no `refs/replace`; every given commit present | `s9_end_runtime.py:304–311` (constants), `:409` (`check_clone_config`), `:443` (`verify_clone`) |
| S9 `build`: first step of `_build`, inside `.partial` (a refusal leaves `S9-REFUSAL-*.json`); facts recorded as `full_clone` in the manifest | `s9_end_runtime.py:667` |
| S9 `verify`: first statement; then the manifest's commit must be in the verified clone | `s9_end_runtime.py:766–768` |
| S9 `equivalence`: first statement; facts in the result | `s9_end_runtime.py:798` |
| S9 `locate` (CLI): before `commit_pins` | `s9_end_runtime.py:868` |
| S3 `build` (reads REPO_FULL): first step of `_build`, with P and the four binding commits | `s3_guard_job.py:556` |
| S3 `verify` (vouches for a job built from the clone): first statement | `s3_guard_job.py:594` |
| S1b: when `--repository` is `REPO_FULL` (its history.json read), before the read | `s1b_copy_admissions.py:318–319` |
| S10: inherits it through S9.verify / S3.verify, before any login | (no code change; tested) |

Existing behaviour kept: D1 member set and the six SHA-pinned `SUPPORT_MEMBERS` unchanged (never in `runtime_files`); the S9 clone exception (`prepare-clone` is still the only git call outside `si.git_run`, and still verifies before checkout); every r2 refusal.

Regression tests (`tests/test_f4.py`):
- **Sol's probe** `remote.origin.promisor=true`: `test_every_entrypoint_refuses_a_corrupted_clone[promisor-s9_build|promisor-s9_verify|promisor-s9_equivalence]`, normal and -O (the matrix).
- `test_every_entrypoint_refuses_a_corrupted_clone[<kind>-<entry>]`: 21 kinds × 6 entrypoints (s9_build, s9_verify, s9_equivalence, s3_build, s3_verify, s1b). Kinds: promisor, promisor-same-line, promisor-bare-key, **promisor-pack** (`.promisor`), **extensions-partialclone**, **remote-partialclonefilter**, core-partialclonefilter, include, quoted-value, bare-true, format-1, **hooks-executable**, hooks-empty-dir, **shallow**, **replace-ref**, **alternates**, http-alternates, grafts, config-worktree, tmp-pack, gitfile. Each asserts the refusal code, that **no object content** was read and **no non-clone input** opened before the refusal, and (builds) that only a refusal receipt exists in `.partial`.
- `test_locate_cli_refuses_a_corrupted_clone[promisor|shallow|replace-ref|alternates]`; `test_s10_staging_refuses_before_any_login[promisor|hooks-executable|shallow]` (runtime and guard-job staging, zero logins); `test_s1b_live_run_on_the_clone_refuses_before_any_login`.
- `test_prepare_clone_receipt_is_not_a_substitute`, `test_config_grammar_refusals[4]`, `test_config_non_utf8_refused`, `test_commits_must_be_in_the_verified_clone` (healthy clone without P: precondition and S9.verify refuse), `test_git_view_must_agree[4]` (fault injection: git reporting bare/shallow/relocated), `test_healthy_copy_passes_every_entrypoint_precondition` (positive control; proves the open spy is live), `test_s3_and_s9_bind_the_same_clone_in_production`.
- Updated r2 tests: `test_s9.py::test_full_clone_verification_refuses[hooks-indirection]` (code now `indirection`); `test_s9.py::test_git_env_and_replace_refs_cannot_substitute_bytes` and `test_s3.py::test_git_replace_ref_and_env_cannot_substitute_bytes` now first assert the precondition refuses the replace ref, then (precondition stubbed, test-only) that the layer still ignores replace refs and the GIT_* environment.

## END-FULL-F2 (HIGH), Part A side: guard-repository contract and a real-S3 fixture

Runner decision: keep S3's minimal Q3 shallow depth-1 guard repository; Part B adds an explicit guard-role shallow allowance. S3's construction is unchanged (`build_repo`, `prove_repo` bytes identical in behaviour).

| Deliverable | Where |
|---|---|
| The contract, precisely: shallow depth 1 (`.git/shallow` = exactly the four binding commits); exactly the four commits; refs exactly `refs/k4s-end/<label>` (loose, 0444; HEAD the unborn init default); the four seed files at their binding paths, bytes == git == binding SHA, 0444; config exactly the four `core.*` init keys; `GIT_DIRS` real directories; no FETCH_HEAD / hooks; **the only allowed indirection is `shallow`**, every other `_git_preflight` refusal stays | `README.md` §S3, "Guard-repository contract" |
| `tests/fixture_guard_job.py`: the synthetic world (moved out of conftest, stdlib only) and a CLI that builds ONE real guard job with the shipped `s3_guard_job.build` into a caller-given empty `/tmp/` directory and prints its facts as JSON | `tests/fixture_guard_job.py` (`build_guard_job`, `guard_job_facts`, `main`) |

Fixture API (also in README and PROGRESS-r3): `python3 -I -B tests/fixture_guard_job.py --dir DIR [--host 127x03|127x04] [--round RR --attempt NN | --preflight NN]` on 127x05; DIR an existing empty directory under `/tmp/`; stdout one JSON object (schema `clasher.k4s.test.s3-guard-job-fixture.v1`) with `job_dir`, `repo_dir`, `job_name`, `target_job`, `host`, `job`, `manifest_path`, `manifest_sha256`, `bindings`, `q3_commits`, `refs`, `shallow`, `git_config_keys`, `git_dirs`, `admissions`, `frozen_t1_sha256`, `inventory_sha256`, `top_level`, `world`, `code_sha256`; exit 2 + stderr on refusal. The commits/SHAs are synthetic (patched S3 constants): a host checker must take `bindings`/`q3_commits` from the JSON. Deterministic except `repo/.git/index`.

Regression tests (`tests/test_fixture_guard_job.py`): `test_cli_builds_a_real_s3_job`, `test_guard_repo_contract` (shallow list, refs, absent names, HEAD, config keys, seed bytes/modes, git dirs — for an attempt job on 03 and a preflight job on 04), `test_deterministic`, `test_preflight_job_for_04`, `test_session_constants_verify_the_cli_job` (the shipped S3.verify accepts the CLI-built job), `test_shallow_needs_an_explicit_guard_role_allowance` (the F2 incompatibility reproduced: a plain `si.GitRepo` refuses the S3 repo; `allow=("shallow",)` admits it), `test_cli_refuses_a_bad_dir[nonempty|not-tmp]`.

## END-FULL-F1 (BLOCKING), end_prep_common half — and every Part A entrypoint

Adopted bootstrap-r1's CANONICAL-READY text (`k4s_bootstrap_r1.py`, sha256 `5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b`, 8372 bytes) **verbatim**, BEGIN..END markers included, in all five Part A modules. Audit result: besides C's own safe_input load, every entrypoint read `end_prep_common.py` through a `sys.path` import, and `C.import_sibling` imported s1b/s3/s9 the same way — unconfined sibling reads before (or beside) the layer. A one-off probe with the kit on the immutable r2 files confirmed it: for `s9 <- end_prep_common.py`, ancestor-symlink, hard-link and leaf-symlink canaries were **executed**; for `s9 <- safe_input.py`, ancestor and hard-link canaries were opened.

| Fix | Where |
|---|---|
| Canonical block, verbatim | `end_prep_common.py:29–184`, `s9_end_runtime.py:47–202`, `s1b_copy_admissions.py:35–190`, `s3_guard_job.py:38–193`, `s10_stage_host.py:53–208` |
| safe_input through the canonical loader: path = `k4s_bootstrap_default_path(__file__, …)` (never abspath/realpath), pins `SAFE_INPUT_SHA256` + `SAFE_INPUT_SIZE = 133606`; then fingerprint / reader / receive program pins as before | `end_prep_common.py:188–229` |
| `bootstrap_sibling` (reuse an already loaded module only with an identical `__k4s_bootstrap__` tag) and `load_sibling` (replaces `import_sibling`; caller-supplied pins) | `end_prep_common.py:203`, `:385` |
| Entrypoints load `end_prep_common.py` with `_k4s_common()` (canonical loader, `K4S_SIBLING_PINS`) and their siblings with `C.load_sibling(…, *K4S_SIBLING_PINS[…])`; no `sys.path` edit, no import of a sibling | S9 `:207–229`; S1b `:195–219`; S3 `:198–222`; S10 `:213–237` |
| Pin chain (acyclic): safe_input ← end_prep_common ← s9 ← s1b ← s3 ← s10; `tests/k4s_adopt.py` pastes the canonical file and recomputes the pins in that order (`--check` for drift) | `tests/k4s_adopt.py` |
| Reader/receive pins kept correct (`2d2f212d…`, `39a92e9d…`); README receive citation fixed; the runner's erratum shipped byte-identical (`SAFE-INPUT-R3-README-ERRATUM-receive-sha.txt`, `126016f0…`) | `end_prep_common.py:194–195`; `README.md` §safe_input pin |

Regression tests (`tests/test_f1.py`, plus two in `test_common.py`):
- `test_vendored_canonical_is_the_bootstrap_r1_text` (sha/size pinned; byte-equal to `bootstrap-r1/k4s_bootstrap_r1.py` when present; the vendored kit files sha-pinned), `test_block_is_byte_equal_to_the_canonical_text[5 modules]`, `test_pin_chain_is_consistent`, `test_loaded_modules_carry_their_bootstrap_tags`, `test_no_sys_path_import_of_a_sibling[5]`, `test_existing_unpinned_module_is_never_reused`, `test_entrypoint_refuses_a_foreign_end_prep_common[4]`, `test_kit_covers_every_entrypoint_and_pinned_file`.
- **Kit, every entrypoint × every pinned file it loads** (`test_entrypoint_alias_scenarios`, 15 pairs, 300 cases): end_prep_common (import mode) ← safe_input; s9 ← {end_prep_common, safe_input}; s1b ← {end_prep_common, safe_input, s9}; s3 ← {end_prep_common, safe_input, s1b, s9}; s10 ← {end_prep_common, safe_input, s3, s1b, s9}. Scenarios: control, swap-ok (first-loaded layer only: the kit swaps at the first bootstrap compile), **ancestor-symlink into synthetic games/**, ancestor-symlink-high, **leaf-symlink**, leaf-symlink-pinned-bytes, **hard-link**, hard-link-pinned-bytes, **wrong-size-larger/smaller**, **same-size-mismatch** (read once, refused by SHA, never executed), fifo-leaf, dir-leaf, non-normalized dotdot/dot/double-slash, and outcome-named ancestors (all 11 kit names for the first-loaded layer, `games` and `END-RAW.json.bak` for deeper layers). Each refusal case asserts **zero canary consumption** (no open, zero bytes, unchanged kernel atime, no execution marker).
- `test_common.py::test_tampered_safe_input_never_executes[True|False]` (same size: SHA refusal; other size: refused before any read), `test_no_assert_and_no_raw_io_in_production` (now scans everything outside the byte-checked block; `exec`/`compile`/`__import__` and raw `os.open/os.read` no longer allowed in end_prep_common outside it).

## Test matrix, mutation

Tests: **691 passed** in each of k4s-freeze 3.12.12 normal / -O and /usr/bin/python3 3.8.10 normal / -O (2026-10-13 00:21–00:26Z; r2 baseline 211). Mutation (`-O`, 106 mutants): **103/106 killed** on 3.12 and on 3.8, the same three documented equivalents surviving, NULL controls 4/4 survived in both; the 3.8 campaign's `outside_writes: true` is another thread's concurrent creation of `/mpac/sdicks02/probe5` and `/mpac/sdicks02/l26w` (README §Mutation explains; not produced by this package). New guards and their mutants: F01–F16 (F4), G01–G11 (F1 glue), N11 retargeted; every new guard has a mutant killed by a named test. Equivalents: N20, X17, T17 (r2) and N13 (r3: the explicit `.promisor` check is masked by the pack-name allowlist, F11).

## Design points for the reviewer

1. **F1 goes beyond safe_input.** Every pre-layer sibling read in Part A now uses the canonical loader with SHA + size pins, including the entrypoints' own `end_prep_common.py` and the s1b/s3/s9 sibling modules. Consequence: changing any module requires re-pinning its dependants (`tests/k4s_adopt.py`); a stale pin refuses the load (fail-closed). `mutate.py` re-pins each mutant copy so mutants are judged by the suite.
2. **The entrypoint script itself** is read by the interpreter from the path the operator gives; that read is outside any bootstrap's reach. The kit's ancestor scenarios run the entry through the alias and prove that nothing after it (sibling or layer) is consumed.
3. **In-process importers must import `s10_stage_host` first** (the top of the pin DAG); a sibling imported by `sys.path` first is never reused by the bootstrap (it refuses). The test harness does this.
4. **F4 receipt not bound.** `repo-full-PREPARE.json` is not required: the existing runner clone `end-prep/repo-full` has no receipt (observed by listing its parent only), and a receipt cannot vouch for the clone's current shape; the live recheck is what is enforced. A read-only look at that clone's `.git/config` shows exactly the plain-clone key set, so it is expected to pass the new checks (not run here: that would read the real clone).
5. **S1b's default `--repository`** stays the shared checkout (its single SHA-pinned history.json read, unchanged); the F4 precondition applies when it is pointed at `REPO_FULL`.
6. **Kit and swap.** The kit's post-hash swap triggers at the first `<k4s-bootstrap ` compile, so `swap-ok` runs only for each entry's first-loaded file (end_prep_common for scripts, safe_input for end_prep_common); deeper layers run every other scenario.

## Runner addendum (2026-10-13T02:22:11Z)

The bootstrap-r1 worker added one kit scenario after CANONICAL-READY (`ancestor-symlink-plain-target`: an ancestor alias whose target carries no outcome name, so only the no-follow walk can refuse it). The runner replaced `tests/k4s_bootstrap_kit.py` with the final kit (sha256 a1d2021c006b128b4ac60eaf6d9011c36268efd69d8fd478edf19326d856522f, byte-equal to bootstrap-r1's) and updated the `KIT_SHA256` pin in `tests/test_f1.py`. No production byte changed. The new scenario runs against every Part A entrypoint (15 added cases).
