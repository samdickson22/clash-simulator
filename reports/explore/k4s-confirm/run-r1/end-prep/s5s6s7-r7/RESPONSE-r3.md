# s5s6s7-r3 — response to SOL-REVIEW-END-FULL-r1 (Part B)

Scope: END-FULL-F2 (host side), F3, F5, F6 and the wrapper half of F1, plus every other Part B pre-confinement read
of safe_input / the host tool. Line numbers are r3 (this directory); "r2:" citations are the reviewer's. Every
regression test named below runs in all four modes (3.12 / 3.8, normal / -O) unless marked; results and mutation
evidence: README §Tests, `MUTATION-RESULTS-py312-O.json`, `MUTATION-RESULTS-py38-O.json`.

## END-FULL-F2 (HIGH) — S3's shallow guard repo vs the host helpers

Contract (runner decision): KEEP the minimal Q3 shallow guard repo; permit shallow ONLY in an explicit guard role.

| Fix | Where |
|---|---|
| Explicit, mandatory clone role (`CLONE_ROLES = ("repository", "guard-repo")`, keyword-only, no default); only `guard-repo` builds `si.GitRepo(..., allow=("shallow",))`; alternates/grafts stay refused | `k4s_end_host_tool.py:455`, `:462` (`clone_repo`), `:489` (`verify_clone(..., *, role)`) |
| Guard role must BE the Q3 shape: `rev-parse --is-shallow-repository` = true; `.git/shallow` read through an exact role (regular, single link, cap), only 40-hex lines, each `cat-file -e ^{commit}` present | `k4s_end_host_tool.py:530` |
| Kept for both roles: si static preflight (commondir, alternates, http-alternates, grafts, driver/include config, code-running core keys), no `refs/replace/`, hooks only `*.sample`; **new for both:** promisor/partial-clone config (`extensions.partialClone`, `remote.*.promisor`, `*.partialclonefilter`) and `objects/pack/*.promisor` refused | `k4s_end_host_tool.py:518`, `:527` |
| `seed_commits(..., *, role)` accepts only `guard-repo` (Q3 checks the guard repo only) | `k4s_end_host_tool.py:544` |
| S5: guard repo in `guard-repo` role (+ Q3 seeds), `--repository` in `repository` role (full) | `k4s_end_preflight.py:1069`, `:1072` |
| S7 host program: same two roles | `k4s_end_launch_remote.py:234`, `:236` |
| S6 frozen-exec: `--repository` in `repository` role | `k4s_end_host_tool.py:615` |

Regression tests:
- **Real S3 job** (unmodified Part A `s3_guard_job.build` + `verify`, Part A's own synthetic world, built by `tests/s3_guard_builder.py`; job copied byte/mode to the Q4 path), `tests/test_f2_s3_guard_integration.py`:
  - `test_real_s3_guard_repo_is_shallow_and_passes_the_guard_role` (03 -pf00, 03 -rd00-a00, 04 -pf00);
  - `test_s5_preflight_passes_with_the_real_s3_guard_job[127x03|127x04]` (full `k4s_end_preflight.run`, sealed passed);
  - `test_s7_host_program_launches_with_the_real_s3_guard_job[end|preflight]` (composed host program via fake ssh).
- **Negatives:**
  - `test_real_s3_guard_repo_refused_in_the_repository_role`;
  - `test_real_s3_guard_repo_other_indirections_still_refused[graft|alternates|replace|promisor|hook|include]`;
  - `test_s5_preflight_refuses_a_shallow_repository_clone`;
  - `test_s5_preflight_refuses_the_real_job_with_an_extra_graft`;
  - `test_s7_host_program_refuses_a_shallow_repository_clone`;
  - `test_s7_host_program_refuses_the_real_job_with_an_indirection[graft|alternates]`.
- **Unit** (`tests/test_host_tool.py`):
  - `test_verify_clone_role_is_explicit`;
  - `test_shallow_refused_for_repository_role_allowed_for_guard_role`;
  - `test_guard_role_requires_the_shallow_q3_shape`;
  - `test_verify_clone_indirections_refuse_in_both_roles` (12 indirections × 2 roles);
  - `test_guard_role_shallow_file_gates[junk|unknown-commit|empty|hard-link|symlink]`;
  - `test_seed_commits_guard_role_still_refuses_grafts`.

General S5/S7 fixtures now use a depth-1 shallow guard repo stand-in (`tests/helpers.py:104`, `shallow_guard_repo`, the S3 fetch-by-SHA shape); the real-S3 tests above use the real job. Mutants F2a–F2l.

## END-FULL-F3 (BLOCKING) — relative XDG_CONFIG_HOME checked at a different place than git reads

**Choice: refusal**, with ONE canonicalization for a strong reason. The fleet passwd home is `//home/sdicks02` (`getent passwd sdicks02` on 127x05), so sshd sets `HOME=//home/sdicks02`; refusing it would refuse every real run. A leading `//` on HOME (exactly two slashes) is replaced by `/`. That canonical value is **installed** in the executed environment. Everything else that is relative, empty-but-set or non-normalized (XDG_CONFIG_HOME or HOME) is refused, not rewritten. The env checked is the env object executed.

| Fix | Where |
|---|---|
| `env_path`: set-but-empty, relative, non-normalized (si.check_abs), non-canonical (realpath ≠ value) refuse; HOME-only leading-`//` canonicalization | `k4s_end_host_tool.py:344`, `:361` |
| `frozen_git_env`: validates HOME (required) and XDG (optional) and installs canonical HOME; GIT_* scrubbed, P2-4 keys + GIT_CONFIG_PARAMETERS | `k4s_end_host_tool.py:372`, `:382` |
| `git_config_files(env)`: enumerates exactly what git 2.25.1 reads, derived from the EXECUTED env: `/etc/gitconfig` never (requires `GIT_CONFIG_NOSYSTEM=1`), `$XDG_CONFIG_HOME/git/config` if set else `$HOME/.config/git/config`, `$HOME/.gitconfig`. Repo `config` and `config.worktree` are checked by si's preflight; includes are refused, so nothing else is reachable | `k4s_end_host_tool.py:386`, `:396` |
| `check_global_git_config(si, host, env)`: `si.name_gate` on each config path first, then a no-follow walk from `/`, then the descriptor gate and `si._check_git_config` | `k4s_end_host_tool.py:403`, `:410` |
| `frozen_env_checked`: single source of truth returning `(env, record)` | `k4s_end_host_tool.py:426` |
| S6 frozen-exec execs that same object | `k4s_end_host_tool.py:619` |
| S5 replaces `os.environ` with it and checks equality | `k4s_end_preflight.py:1074` |
| S7 checks the env the launched wrapper inherits | `k4s_end_launch_remote.py:239` |

Regression tests:
- **Sol probe, both modes:**
  - `test_host_tool.py::test_sol_probe_relative_xdg_include_with_git_C[relative|absolute]`: a control shows git 2.25 reads the canary through a relative XDG with `git -C`; r3 refuses the relative value, and the absolute form is refused for its include;
  - `test_host_tool.py::test_frozen_exec_cli_refuses_relative_xdg_before_running`: the frozen-exec CLI exits 3 and the command never runs; a positive control is included;
  - `test_s5_preflight.py::test_relative_or_empty_xdg_refused_before_any_frozen_import[xdg|""]`;
  - `test_s7_gate.py::test_host_program_refuses_relative_empty_or_odd_xdg[xdg|""|//x/y]`.
- **Identity:**
  - `test_host_tool.py::test_frozen_exec_executes_the_identical_checked_env`: the env passed to `execvpe` *is* the checked object;
  - `test_s5_preflight.py::test_frozen_reader_env_is_the_checked_env_object`.
- **Enumeration against the installed git:** `test_host_tool.py::test_installed_git_reads_only_the_checked_config_files[xdg unset|set]` runs `config --list --show-origin` under the executed env. Every file origin is a checked file or the repo config, and `/etc/gitconfig` is never read.
- **Other:**
  - `test_frozen_env_refuses_relative_empty_or_non_normalized` (14 cases);
  - `test_frozen_env_refuses_symlinked_home_or_xdg`;
  - `test_home_leading_double_slash_is_installed_canonical`;
  - `test_git_config_files_requires_nosystem`;
  - `test_global_git_config_checked` (adds a hard-linked config: refused, canary intact);
  - `test_config_paths_pass_the_name_gate`;
  - `test_s7_gate.py::test_host_program_checks_the_global_config_files`;
  - `test_s7_gate.py::test_host_program_home_double_slash_checked_canonically`.

Mutants F3a–F3i.

## END-FULL-F5 (HIGH) — RC-9 binding

| Fix | Where |
|---|---|
| (a) S5 exports `identity`: native/corpus paths used and the identities `frozen_identity` verified, required equal to `NATIVE_SHA256` 44874fd6… / `CORPUS_SHA256` a97b1fbf…. The `--corpus-inventory-sha256` pin must be `CORPUS_INVENTORY_SHA256` 3501e2ac… (corpora.json at 81f2483e) | `k4s_end_preflight.py:85`, `:427`, `:759`, `:761` |
| (a) S7 `launch_identity`: K4S identities, and paths equal to the preflight's inputs under the declared roots (both hosts). For the launching host, native/corpus/corpus-inventory must equal THIS END argv | `k4s_end_launch_gate.py:551`, `:558`, `:581` |
| (b) S5 exports `bundle_identity`: guard-job-free digest of its own and its compare bundle (`k4s_end_host_tool.bundle_sans_guard_sha256`, from the pinned bytes) | `k4s_end_preflight.py:1057`; `k4s_end_host_tool.py:440` |
| (b) S7 `bundle_binding`: `exact` if the END bundle is the preflight's compare bundle (path + RC-6 tiers-pins SHA). Otherwise `guard-job-equivalent`: never the preflight's own bundle/guard job, and the host program recomputes the digest from the attempt bundle's pinned `tiers-pins.json` and refuses on any difference | `k4s_end_launch_gate.py:562`, `:598`, `:797`; `k4s_end_launch_remote.py:227` |
| (c) `lineage_03`: 03 attempt round = round launched; admission made from this ACK and the 03 launch receipt; 03 `LAUNCH-RECEIPT.json` (SHA from the ACK) is a launched 03 END attempt with `--round` = this round, the same `roots_sha256` and the same two qualifying preflight receipts | `k4s_end_launch_gate.py:514`, `:673`, `:677` |
| (d) `bus_evidence`: present/finite/non-negative percent, seconds, ticks, int hz; `percent = 100·ticks/hz/seconds`; seconds = measured loaded duration; band = P2-3 band of the percent (same 0.3/0.7 constants as S5); gate = band on 04, `not-gated-on-127x03` on 03. S5's verified summary now carries `hz` | `k4s_end_launch_gate.py:93`, `:563`, `:619`, `:628`; `k4s_end_preflight.py:1166` |
| Schemas bumped (receipt shape changed): `clasher.k4s.end-preflight.v3`, `clasher.k4s.end-preflight-verified.v3` | `k4s_end_preflight.py:55` |

**F5(b) choice:** exact binding where the workflow allows it, and a host-verified equivalence where it cannot. A preflight requires an empty attempt parent, so none can run after a host's first claim (RC-2/RC-9). Per-attempt bundles get fresh guard jobs (RC-3), and a host may have a second attempt or a later round. The plan's `-pfNN` preflight guard jobs therefore compare against the round-00 `-rd00-a00` attempt bundle (S5 bundle_parity: identical except guard.job). Exact-only would make every later attempt unlaunchable. The equivalence explains only the fresh guard job: equal guard-job-free digests, recomputed from bytes on the host at launch.

Regression tests (`tests/test_s7_gate.py`; Sol probes in both modes):
- **Sol probes:**
  - `test_f5_probe_changed_native_or_corpus_path_refused[--native|--corpus]`;
  - `test_f5_probe_attempt_bundle_a01_vs_preflight_a00`: a01 is admitted only as `guard-job-equivalent`, and with a01 differing beyond guard.job, `test_f5_probe_a01_differing_beyond_guard_job_refused_on_host`;
  - `test_f5_probe_03_completion_must_be_this_round_and_lineage[other-round-ack, receipt-round, not-launched, receipt-host, roots, preflights, adm-ack, adm-receipt, adm-kind, ack-no-receipt]`;
  - `test_f5_probe_inconsistent_bus_evidence_refused` (12 cases, including `04-0.8-proceed`).
- **Other S7 tests:**
  - `test_f5_preflight_identity_binding` (7 cases);
  - `test_f5_probe_other_host_preflight_identity_also_bound`;
  - `test_f5_exact_bundle_binding_recorded`;
  - `test_f5_preflight_bundle_identity_required`;
  - `test_f5_preflight_digest_must_match_the_host_bundle`;
  - `test_f5_03_receipt_bound_by_ack_sha`;
  - `test_f5_nonfinite_bus_refused`;
  - `test_f5_bus_constants_equal_the_preflight_and_band_boundaries`.
- **S5:**
  - `test_identities_exported_for_rc9`;
  - `test_frozen_identity_must_be_the_k4s_end_identity`;
  - `test_corpus_inventory_pin_is_the_k4s_inventory`;
  - `test_verify_received_happy_and_exclusive`, which feeds the real S5 verified summary into S7's `launch_identity` and `bus_evidence`.

Preserved: r2 schema/provenance, duration/load, C-d, bus decision and RC-7 tests (all r2 RC-9 tests kept, fixtures moved to v3 with numerically consistent bus). Mutants F5a–F5u.

## END-FULL-F6 (MEDIUM) — shim modes

- On disk, `tests/shims/{hostname,nice,rsync,taskset,timeout}` are mode 0755, and so are both wrappers.
- `tests/helpers.py:162` `require_executable_shims()` refuses loudly unless each shim is a regular file with all execute bits. It runs in `shim_env` (`:182`) and at `pytest_sessionstart` (`tests/conftest.py:10`), so a 0644 checkout fails the whole run instead of silently using the real binaries.
- Tests:
  - `test_host_tool.py::test_shims_are_executable_on_disk`;
  - `test_host_tool.py::test_non_executable_shim_fails_loudly`.
- Counts are reported from a pristine `cp -a` copy (README §Tests). Mutant F6a.

## END-FULL-F1 (BLOCKING), wrapper half + Part B Python loaders

bootstrap-r1 CANONICAL-READY was present (written 2026-10-13T00:13:28Z); its three SHAs were verified. Adoption is byte for byte:

| Fix | Where |
|---|---|
| `k4s_end_exit_push.sh`: `test -f` + `sha256sum --check` (r2:38–39) and the by-path `tool()` (r2:77) replaced by `host_tool_size=` + the canonical shell fragment (verify-only up front, exit 90; `tool()` = loader that walks, gates, hashes and executes verified bytes on every call). Exclusive metadata creation and exit codes unchanged | `k4s_end_exit_push.sh:38`, `:39`–`:237` |
| `k4s_preflight_push.sh`: same (r2:36–37) | `k4s_preflight_push.sh:36`, `:37`–`:235` |
| Host tool: `read_pinned`/`module_from_bytes` (pre-confinement read of safe_input) replaced by the canonical Python region + `load_safe_input` | `k4s_end_host_tool.py:85`–`:240`, `:253`, `:598` |
| Preflight: `read_pinned`/`load_module` replaced; safe_input AND host tool via `k4s_bootstrap_load` (size pins) | `k4s_end_preflight.py:156`–`:311`, `:314` |
| Gate: same | `k4s_end_launch_gate.py:132`–`:287`, `:290` |
| Verifier: `load_si` (realpath + by-path read) replaced | `k4s_end_verify_push.py:67`–`:222`, `:225` |
| S7 host program: unchanged (receives bytes via stdin, SHA-checked before exec; no path read) | `k4s_end_launch_gate.py` PRELUDE |
| Pin chain: `repin.py` maintains `SAFE_INPUT_SIZE`, `HOST_TOOL_SIZE`, `host_tool_size` | `tests/repin.py` |

Regression tests (`tests/test_f1_bootstrap.py`; the kit is vendored byte-identical in `tests/bootstrap_kit/`, checked against bootstrap-r1):
- **Static:**
  - `test_vendored_kit_and_canonical_files_are_the_bootstrap_r1_bytes`;
  - `test_python_components_embed_the_canonical_region[4 files]`;
  - `test_wrappers_embed_the_canonical_shell_fragment[2]` (no sha256sum, no by-path `tool()`, pins match);
  - `test_size_pins_match_the_layers`.
- **Kit:** `test_python_loader_meets_every_kit_scenario` runs 6 loaders (host tool, preflight×2 layers, gate×2, verifier) × every kit scenario: control, swap-ok on the first-loaded layer, ancestor symlinks, leaf symlink, hard link (canary and pinned bytes), wrong sizes, same-size mismatch, FIFO/dir leaf, non-normalized forms, 11 outcome-named ancestors. It asserts zero canary opens/bytes via recorders and kernel atime, and that nothing is executed. Verifier cases skip under -O (import refusal by design).
- **Wrappers as real bash:**
  - `test_wrapper_bootstrap_meets_the_kit_scenarios[19 scenarios × 2 wrappers]`, including the review's hard-linked tool, symlinked tools dir, mismatching bytes and leaf symlink. Each refuses with exit 90 before any tool call (no argv.nul, command never started), with canary atime unmoved and no marker;
  - `test_wrapper_never_executes_a_host_tool_swapped_after_verification[2]`.
- Also updated: `test_host_tool.py::test_safe_input_bootstrap_refuses_aliases_and_drift`, and `test_s6_wrapper.py::test_wrapper_sources_have_no_writing_redirection` (now handles the multi-line single-quoted loader word).

Mutants W05, H08, H09, F1a–F1j (judged by behavioural tests only, never by the byte-equality tests).

## Earlier dispositions preserved

Every r2 test is retained, apart from three edits:
- the `read_pinned` test was replaced by its canonical-bootstrap equivalent;
- the guard-repo stand-ins became shallow (the S3 shape);
- the RC-9 fixtures moved to schema v3 with consistent bus numbers.

The r2 mutants still apply (H08/H09/H12/P11–P13/W05 retargeted to the r3 text). No check was weakened: the
`repository` role keeps every r2 refusal, and r3 adds promisor refusal there too.
