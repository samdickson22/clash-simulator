# RESPONSE r4 — Part A (S9, S10, new S11) to INTEGRATION-AUDIT-r1

Candidate: `run-r1/end-prep/s3s9s10-r4/` (began as `cp -a s3s9s10-r3`; r3 unchanged). Audit: `run-r1/end-staging/INTEGRATION-AUDIT-r1/REPORT.md` (sha256 0d709b5b...). Offline only: fake hosts, no ssh / network, nothing committed. Line numbers refer to the r4 files as shipped (generated from anchors).

| Row | Audit finding | Fix | Where (file:line) | Named tests / evidence |
|---|---|---|---|---|
| **B2** | S10 staged the runtime at `<base>/runtime/runtime-<P12>`; S5/S7 require `<base>/runtime-<P12>` | runtime component parent = `<base>`; `BASE_SUBDIRS` without runtime; `roots()` gives `runtime-<commit12>` under `<base>`; `--print-roots` draft removed | `s10_stage_host.py:250`, `s10_stage_host.py:380`, `s10_stage_host.py:324` | `test_r4_s10.py::test_runtime_staged_at_base_runtime_p12_and_accepted_by_s5_layout` (the vendored S5 `layout()` accepts the S10 paths and refuses r3's), `test_s10.py::test_bases_and_layout`, `test_flow.py::test_s10_stage_runtime_bundle_guard`; mutants V01, V02 |
| **B3** | SD1-MANIFEST.json and the t1 corpora.json were not runtime members | `SUPPORT_PINS` (+3 SHA-pinned members, a D1 extension); `check_support_pins` in the stdlib closure check (with the K4S-manifest cross-check) and in `verify` | `s9_end_runtime.py:275`, `s9_end_runtime.py:708`, `s9_end_runtime.py:703`, `s9_end_runtime.py:914` | `test_r4_s9.py::test_support_members_are_exported_pinned_and_outside_the_file_hash_sets`, `::test_membership_neutral_for_runtime_and_measurement_files`, `::test_a_pre_r4_runtime_is_refused_by_verify`, `::test_support_pin_mismatch_refuses_the_build[3]`, `::test_support_pins_cross_checked_against_the_k4s_manifest[6]`, `::test_support_members_must_be_tracked`; real proof `REAL-S9-MEMBERSHIP-PROOF.json`; mutants R01-R06 |
| **B5** | DELTA-MANIFEST.json (read by frozen end_reference.py:128) was not exported | the third `SUPPORT_PINS` member (34eca2b7, the tracked blob at P' / FREEZE-RECORD F-5) | `s9_end_runtime.py:274` | as B3 (parametrized over the three paths); REAL-CHAIN-r4.json: frozen `frozen_identity` on the staged r4 runtime |
| **B7 / U9** | no producer of the S7 RC-6 declaration; S10's draft schema differed | `--declare-roots` writes exactly `clasher.k4s.end-roots-declaration.v1` from S9.verify + `bundle_header` (tiers SHA, receipt SHA, adopted S4, guard job), self-checked by `validate_roots` (S7's rules), exclusive `--out` | `s10_stage_host.py:715`, `s10_stage_host.py:761`, `s10_stage_host.py:445` | `test_r4_s10.py::test_declare_roots_is_exactly_what_s7_consumes` (the REAL S7 `validate_roots` and `validate_argv` from the vendored r3 gate accept it), `::test_declare_roots_refusals[11]`, `::test_validate_roots_matches_s7_rule_for_rule[13]`, `::test_declare_roots_cli`; mutants V13-V20 |
| **U1** | no tool provisions `<base>/repository` | new S11: provision at P' / advance to X on k4s-end-r1, one login per mode, git bundle over D4, host VERIFY with the S7-pinned host tool | `s11_host_repository.py:613`, `s11_host_repository.py:506`, `s11_host_repository.py:550`, `s11_host_repository.py:313`, `s11_host_repository.py:393` | `test_r4_s11.py` (all: provision one login + consumer verify_clone, refusals[10], advance + refusals[7], host VERIFY branches[10], no-replace publish[4], bundle identity[4], CLI); REAL-CHAIN-r4.json (real repo-full -> fake 03; frozen end_evidence/end_job/producer_claim on the provisioned/advanced repository); mutants U01-U23 |
| **U2** | no tool stages `<base>/tools` | `--tools-source` component: exactly `TOOL_PINS` (= S7's pins), gated by size + SHA before any login | `s10_stage_host.py:264`, `s10_stage_host.py:397` | `test_r4_s10.py::test_tools_and_end_inputs_staged_a_w_single_link`, `::test_tools_refused_before_any_login[5]`, `::test_production_constants` (TOOL_PINS == the vendored s5s6s7-r4 S7 constants); REAL-CHAIN-r4b.json; mutants V03, V04 |
| **U3** | no tool stages the native + K4 corpus | `--end-inputs` component from fixed 05 sources (located by SHA), `<base>/end-inputs-r1/` | `s10_stage_host.py:282`, `s10_stage_host.py:410` | `test_r4_s10.py::test_tools_and_end_inputs_staged_a_w_single_link`, `::test_end_inputs_refused_before_any_login[3]`, `::test_production_constants`; real hashing in REAL-CHAIN-r4.json; mutant V05 |
| **U4** | interpreter on 03/04 unverified | read-only probe in the existing P-facts login (no extra login): version, executable SHA, imports of numpy/torch/cv2/scipy; refusal on failure; path pending ruling | `s10_stage_host.py:294`, `s10_stage_host.py:573`, `s10_stage_host.py:613` | `test_r4_s10.py::test_interpreter_probe_recorded`, `::test_interpreter_probe_refusals[6]`, `::test_probe_command_mirrors_the_end_launch_environment`; REAL-CHAIN-r4.json (05's e4v3-venv bound into the fake 03: torch/cv2/numpy/scipy imported); mutants V08-V12 |
| **U10** | X cannot enter REPO_FULL | `refresh-clone`: fetch of refs/heads/k4s-end-r1 only, no '+', prepare-clone hygiene, live verify before/after, objects never rewritten, only the END ref moves, HEAD untouched unless --checkout | `s9_end_runtime.py:566`, `s9_end_runtime.py:579` | `test_r4_s9.py::test_refresh_brings_x_and_proves_nothing_else_changed`, `::test_refresh_checkout_only_when_asked`, `::test_refresh_refusals[4]`, `::test_refresh_refuses_a_corrupted_clone_before_the_fetch[4]`, `::test_refresh_never_rewrites_existing_objects`, `::test_refresh_forced_fetch_is_still_fast_forward_only`, `::test_refresh_head_must_not_move`, `::test_refresh_other_refs_must_not_move`, `::test_refresh_cli`, `::test_s9_equivalence_of_the_refreshed_x`; mutants R07-R16 |
| **L4** | S10/S5 never checked which S4 built a bundle | `ADOPTED_S4_SHA256` (b3-r6, from its SHA256SUMS) required in staging and --declare-roots | `s10_stage_host.py:306`, `s10_stage_host.py:440` | `test_r4_s10.py::test_bundle_from_another_s4_refused`, `::test_declare_roots_refusals[other-s4]`, `::test_production_constants`; mutants V06, V07 |
| **IR-03** | runner update 2: 03's idle resident (PID 2180947) is gone (IDLE-03-RETIREMENT-PROPOSAL.md, proposed ruling) | S3 builds/verifies guard-job admissions from `END_ADMISSIONS` (03: bus only; 04: bus only), not `S1B.NAMES` (S1b unchanged; its 03 idle row is ignored); verify requires exactly those admissions and the top level; S10's bundle check requires the bundle guard admissions == `S3.END_ADMISSIONS[host]` (b3-r6 03 bundles refused: b3-r7) | `s3_guard_job.py:264`, `s3_guard_job.py:364`, `s3_guard_job.py:615`, `s10_stage_host.py:497` | `test_r4_s10.py::test_ir03_03_guard_job_is_bus_only_while_s1b_keeps_its_contract`, `::test_ir03_guard_job_with_idle_services_is_refused[file-in-job|manifest-row]`, `::test_ir03_bundle_with_03_idle_admission_refused`; updated `test_flow.py::test_s3_build_and_verify`, `test_s3.py::test_git_replace_ref_and_env_cannot_substitute_bytes`; REAL-CHAIN-r4c-IR03.json (real 03 pf00 job from the real A1b manifest: bus only, S3 verify OK; frozen ReportingGuard accepts it (IR-03 shape) and refuses the b3-r6 shape and a stale unpinned idle file); mutants Z01-Z04 |
| **Part B r4** | runner update 1: s5s6s7-r4 adopted (SHA256SUMS d04c6ca1) | TOOL_PINS = the r4 S7 pins (k4s_end_preflight.py c7793451); vendored consumers = s5s6s7-r4; end-inputs paths confirmed against r4 S5 layout / S7 validate_argv / build-argv (no mismatch); S7 r4 HOST_PYTHON == S10 HOST_PYTHON | `s10_stage_host.py:264`, `s10_stage_host.py:270` | `test_r4_s10.py::test_production_constants` (TOOL_PINS == r4 gate constants, HOST_PYTHON == r4 gate's, SD1/corpora pins == r4), `::test_declare_roots_is_exactly_what_s7_consumes` (r4 validate_roots + validate_argv with r4's host-python / evidence / SD1 pins); REAL-CHAIN-r4b.json (r4 build-argv with S10's paths; r4 S5 run of that argv) |

Rows not in this package's scope: B1 (b3-r6), B6 (ruling; `--declare-roots` output goes to main), U5-U8 / L1 / L6 / U12 (s5s6s7-r4), U11 (S8, after END). M-rows unchanged (re-checked by the chain where they apply).

## Masked guards found by mutation, and the tests that now isolate them

| Mutant | Guard | Masked by | Isolating test |
|---|---|---|---|
| V11 | exactly one interpreter probe record | the executable check | `test_r4_s10.py::test_parse_python_requires_exactly_one_record` |
| V14 | runtime == runtime-<commit12> | the two-host equality (V17) | `::test_validate_roots_runtime_is_runtime_commit12_on_both_hosts` |
| U01 | END tip == --commit | the bundle identity | `test_r4_s11.py::test_tip_mismatch_refused_before_any_bundle` |
| U03 | X is a strict descendant of P' | the equivalence record / bundle prerequisite | `::test_advance_requires_a_strict_descendant_before_any_bundle` |
| U05 | list-heads names the ref | the header parse | `::test_bundle_heads_are_checked_independently_of_the_header` |
| U16, U17 | host END-JOB OID / bytes | git_show_file's own SHA check | `::test_host_end_job_checks[oid, worktree-bytes]` |

Also added: `test_r4_s9.py::test_refresh_forced_fetch_is_still_fast_forward_only`, `::test_refresh_head_must_not_move` and `::test_refresh_other_refs_must_not_move` (fault injection behind git's own non-fast-forward refusal); and `test_r4_s11.py::test_host_verify_branches[10]` and `::test_host_publish_is_no_replace[4]` (the host program's guards, run locally).

**Documented equivalents** (in `mutate.py` `EQUIVALENT`): V17, U09, U23 (r4), and N13, N20, X17 (r3).

## Evidence on real inputs (offline; fake hosts only)

- `REAL-S9-MEMBERSHIP-PROOF.json`: a real r4 S9 build at P'. runtime_files fc3dbeb4 and measurement 42b8986d are unchanged; the inventory gains exactly the three support files.
- `REAL-CHAIN-r4.json`: the audit chain re-run on real inputs, with s5s6s7-r3 tools.
  - b3-r6 bundles built;
  - `--declare-roots` accepted by the real S7 r3 `validate_roots`;
  - S10 staged to a fake 03 in 10 logins;
  - S11 provision and advance took 1 login each;
  - the frozen `frozen_identity` passed;
  - S5 passed every check up to the deliberate stub stop;
  - the frozen `end_job` / `producer_claim` worked on the advanced repository.
- `REAL-CHAIN-r4b.json`: the same chain with the adopted **s5s6s7-r4**.
  - The r4 S7 `build-argv` accepted S10's declaration and S10's end-inputs paths: `<base>/end-inputs-r1/clasher_core.abi3.so` and `<base>/end-inputs-r1/K4-states.pkl`. **No mismatch.**
  - The r4 S5 ran exactly that argv and passed every check up to `frozen_identity` (stub stop).
  - X was the r4 builder's END-JOB.
- `REAL-CHAIN-r4c-IR03.json`: IR-03 on real inputs.
  - A real bus-only 03 guard job, built from the real A1b manifest, verified.
  - The frozen ReportingGuard accepts it with the IR-03 bundle shape.
  - It refuses the b3-r6 shape and a stale unpinned idle file.

## Rulings and ratifications needed

1. IR-03, as implemented. The 03 guard jobs must be rebuilt with this S3, and the 03 bundles with b3-r7.
2. The D1 extension: SD1-MANIFEST.json, corpora.json and DELTA-MANIFEST.json as SHA-pinned support members.
3. A3, the END interpreter. The constant is the uv cpython-3.12.13 binary, which equals the r4 S7 `HOST_PYTHON`. Committed evidence says reporting and T1's END ran `/mpac/sdicks02/repos/clasher/.venv/bin/python` (a venv on that base). The bare binary may lack torch, and the probe will tell.
4. The S11 design: a git bundle over D4, one login per mode, verified with the S7-pinned host tool staged by S10. FETCH_HEAD and the transfer dir are left on the host for a later authorized cleanup.
5. The RC-6 `commit` field means P', the runtime commit. The declaration itself is committed to main (B6).

## Runner addendum (2026-10-13T09:41:39Z)

L4 pin moved to the IR-03 S4: `ADOPTED_S4_SHA256` = b3-r7 `assemble_fleet_reference.py` 2b8f5fb3b79b85103394e18c39330b772fbf2deb28d95fbd01d2d73273d7f016 (was b3-r6 76b7b7cf…), in `s10_stage_host.py:306` and `tests/test_r4_s10.py:107`. `tests/k4s_adopt.py` re-pinned the chain (s11 pins s10). No other byte changed. The REAL-CHAIN records were produced before this update with the b3-r6 pin and are kept as written.
- Runner, same addendum: `tests/test_r4_s10.py:108` also hashes the adopted S4 file; it now points at `b3-r7/assemble_fleet_reference.py`.
