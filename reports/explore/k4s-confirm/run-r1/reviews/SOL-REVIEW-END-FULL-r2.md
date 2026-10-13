VERDICT: APPROVE

# Independent SOL review — K4S END tooling, round 2

Reviewed 2026-10-12 (America/Los_Angeles). F1–F6 are FIXED. I found no new integrity defect or regression introduced by these fixes. This is an offline tooling approval; it establishes no live-host qualification or authority for a host step. Unchanged safe_input r3 and S1 retain their previous dispositions.

## Sources and boundary

Candidate source and tests came only from Git objects at `9ecf50b1f7e3cb6f7dfcf01294db7ebcbdf41d25`. The package index was read with `git show 50cc06bc:reports/explore/k4s-confirm/run-r1/end-prep/SOL-R2-PACKAGE-END-FULL.md`. I read the supplied external round-1 review (`6918d77a`). I did not read the shared worktree or alter repository files. The report is the sole persistent reviewer output.

All citations below are relative to `reports/explore/k4s-confirm/run-r1/end-prep/` at the candidate commit. Prefixes: **BS** = bootstrap-r1; **S2** = s1s2-r5/s2_end_evidence.py; **S4** = b3-r5/assemble_fleet_reference.py; **C/S1b/S3/S9/S10** = the correspondingly named Python files in s3s9s10-r3; **HT/PF/LG/LR/EV** = k4s_end_host_tool.py / k4s_end_preflight.py / k4s_end_launch_gate.py / k4s_end_launch_remote.py / k4s_end_verify_push.py in s5s6s7-r3; **EW/PW** = its two shell wrappers. Test citations use their candidate directory explicitly.

I verified every entry in all five SHA256SUMS files: BS 17, S1/S2 24, S4 22, Part A 30, Part B 76 (169 total). Each inventory's own digest matches the index. All four adopted safe_input.py files hash to `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`. S1 is byte-identical to the committed s1s2-r4b copy (SHA-256 `b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65`).

No real host, SSH connection, network clone, production model/corpus execution, real game result, outcome payload or real games/ directory was accessed. Test processes ran in a user/network namespace with no external network, at nice 19, using isolated Python. Fake-host names and adversarial outcome names belong to reviewer-created synthetic fixtures, not fleet machines or study outcomes.

## Findings F1–F6

### F1 — FIXED: bootstrap confinement and verified-byte execution

The canonical implementation at **BS/k4s_bootstrap_r1.py:52** validates the pin and already-normalized absolute path, screens every component, walks from `/` with O_DIRECTORY|O_NOFOLLOW, and inspects the leaf before opening it. Its pre-read fstat checks regular type, single link, pinned size and the inspected dev/inode. The read/hash result is passed directly to compile/exec at **:128** and **:152**. There is no pathname reopen between hashing and execution; the synthetic compile filename and seeded linecache avoid traceback/inspection rereads.

I independently compared all **11 production Python regions**, including their terminating newline, against the canonical 8,372-byte snippet, SHA-256 `5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b`: **S2:115, S4:93, C:29, S1b:35, S3:38, S9:47, S10:53, HT:85, PF:156, LG:132, EV:67**. All are byte-identical. Both shell wrappers contain the entire canonical shell fragment byte-for-byte (**EW:39, PW:37**), which embeds that snippet. **EW:234–235** invokes `python3 -I -S -c` for verification and each tool call. The shell loader's **BS/k4s_bootstrap_loader_r1.py:179** reads once and executes that returned data at **:183**, rather than executing the path it checked.

Part A sibling reuse is restricted to the exact bootstrap path/SHA/size tag (**C:203**, **C:385**, **S10:220**); a plain pre-import is refused. The remote S7 stdin bootstrap hashes the supplied bytes before compiling those same bytes (**LG:715**).

Coverage rerun: **BS/tests/test_bootstrap_conformance.py::test_load_executes_exactly_the_hashed_bytes_and_never_reopens**; **s1s2-r5/tests/test_s2_r5_bootstrap.py::test_end_full_f1_alias_substitutions_before_bootstrap** and **test_post_hash_swap_to_a_same_size_edited_layer_runs_the_verified_bytes**; corresponding S4 tests; **s3s9s10-r3/tests/test_f1.py::test_block_is_byte_equal_to_the_canonical_text**, **test_pin_chain_is_consistent** and its entrypoint conformance cases; **s5s6s7-r3/tests/test_f1_bootstrap.py::test_python_loader_meets_every_kit_scenario**, **test_wrapper_bootstrap_meets_the_kit_scenarios**, and **test_wrapper_never_executes_a_host_tool_swapped_after_verification**. These include ancestor aliases, hard links, size/SHA drift and post-hash substitution, with zero-consumption assertions where refusal must precede content access.

### F2 — FIXED: shallow exception confined to the guard repository

**HT:462** makes role selection explicit; only `guard-repo` supplies the shallow allowance. **HT:489**, **:518**, **:527**, and **:530** retain the other indirection checks, reject promisor/partial-clone config and .promisor packs, and require the guard role actually to be shallow with a gated, valid commit-ID shallow file. **HT:544** restricts seed checks to the guard role. S5 selects the two different roles at **PF:1069/1072**; S7 does so at **LR:234/236**; frozen-exec keeps the full repository role at **HT:615**.

Coverage rerun: **s5s6s7-r3/tests/test_f2_s3_guard_integration.py::test_s5_preflight_passes_with_the_real_s3_guard_job** and **test_s7_host_program_launches_with_the_real_s3_guard_job**, plus the shallow-repository and other-indirection refusal tests. These jobs are built and verified by the real candidate S3 against a synthetic origin, not substitute full repositories. **tests/test_host_tool.py::test_verify_clone_role_is_explicit**, **test_shallow_refused_for_repository_role_allowed_for_guard_role**, **test_guard_role_requires_the_shallow_q3_shape**, and **test_verify_clone_indirections_refuse_in_both_roles** cover the boundary.

### F3 — FIXED: checked config locations equal executed locations

**HT:344** rejects relative, empty and non-normalized HOME/XDG values; **HT:361** canonicalizes the allowed HOME double slash before validation. **HT:372/382** installs that result in the executed environment. **HT:386/403/426** enumerate and gate the config files from that environment, require GIT_CONFIG_NOSYSTEM=1, and preserve the no-follow/single-link/include/driver checks. S5 installs and checks equality with that environment (**PF:1074**); frozen-exec passes the checked object directly to execvpe (**HT:619**). S7 checks the inherited wrapper environment (**LR:239**), with frozen-exec rechecking before execution.

Coverage rerun: **s5s6s7-r3/tests/test_host_tool.py::test_sol_probe_relative_xdg_include_with_git_C**, **test_frozen_exec_cli_refuses_relative_xdg_before_running**, **test_frozen_exec_executes_the_identical_checked_env**, **test_installed_git_reads_only_the_checked_config_files**, and **test_home_leading_double_slash_is_installed_canonical**; **tests/test_s5_preflight.py::test_relative_or_empty_xdg_refused_before_any_frozen_import** and **test_frozen_reader_env_is_the_checked_env_object**; **tests/test_s7_gate.py::test_host_program_refuses_relative_empty_or_odd_xdg** and **test_host_program_home_double_slash_checked_canonically**.

The implementation's HOME exception is broader than the index's wording; see non-blocking notes. It does not recreate the checked/executed path mismatch.

### F4 — FIXED: live full-clone check is mandatory

**S9:443/480** verify the live directory/config/pack/ref/Git view, with a strict plain-clone config parser at **:409**. The check runs before authoritative clone reads in build (**:667**), verify (**:766**), equivalence (**:798**) and locate (**:868**). S3 build/verify call it at **S3:556/594**; S1b checks repo-full before history access (**S1b:319**). S10 inherits the precondition through verification before any transport. A preparation receipt or a repo-full directory name cannot substitute for the live check.

Coverage rerun: **s3s9s10-r3/tests/test_f4.py::test_every_entrypoint_refuses_a_corrupted_clone** (including the original promisor probe, config variants, .promisor packs, shallow state, hooks, refs and alternates), **test_locate_cli_refuses_a_corrupted_clone**, **test_s10_staging_refuses_before_any_login**, **test_prepare_clone_receipt_is_not_a_substitute**, and **test_commits_must_be_in_the_verified_clone**. Healthy-clone controls pass.

### F5 — FIXED: launch-input, bundle, lineage and bus bindings

S5 exports the fixed native/corpus/inventory identities and bundle identities (**PF:759/761**, **:1057**). **LG:551/581** require those identities and the launch host's argv paths to agree. **HT:440** removes only `reference_load_profile.guard.job` when computing bundle equivalence. **LG:598** records exact versus guard-job-equivalent binding; **LR:227** recomputes the digest from the SHA-pinned actual attempt manifest before launch. Changed model/input/member/profile pins are therefore not excused as guard-job changes. Equivalence is necessary for later attempts with fresh guard jobs; it is not an unchecked path substitution.

For 04, **LG:673** calls **lineage_03 at :677** after the complete/C-d/receipt/admission checks. It requires the 03 attempt and measurement argv to identify this round; the admission must reference this exact ACK and launch-receipt SHA; the SHA-bound receipt must be a launched 03 END attempt under the same RC-6 declaration and the same two qualifying preflight receipts. This establishes the requested 03→04 lineage independently of merely seeing a complete ACK. **LG:628** checks finite numeric bus evidence, ticks/hz/span arithmetic, measured duration, exact 0.3/0.7 band and host gate consistency.

Coverage rerun: **s5s6s7-r3/tests/test_s7_gate.py::test_f5_probe_changed_native_or_corpus_path_refused**, **test_f5_probe_attempt_bundle_a01_vs_preflight_a00**, **test_f5_probe_a01_differing_beyond_guard_job_refused_on_host**, **test_f5_preflight_digest_must_match_the_host_bundle**, **test_f5_probe_03_completion_must_be_this_round_and_lineage** (ten mutations), **test_f5_03_receipt_bound_by_ack_sha**, **test_f5_probe_inconsistent_bus_evidence_refused**, and **test_f5_nonfinite_bus_refused**. S5's **tests/test_s5_preflight.py::test_verify_received_happy_and_exclusive** checks compatibility of its emitted summary with S7's identity/bus consumers.

### F6 — FIXED: executable committed shims

`git ls-tree` records **100755** for all five Part B shims and both wrappers. **s5s6s7-r3/tests/helpers.py:162** refuses missing execute bits rather than falling through to real commands; **tests/conftest.py:10** enforces that at session start.

Coverage rerun: **tests/test_host_tool.py::test_shims_are_executable_on_disk** and **test_non_executable_shim_fails_loudly**, plus the complete fake-host suite. Git archive mode assumptions require an explicit export mask, as noted below; the original missing-execute-bit defect is repaired.

## New defects or regressions

None found that warrants REQUEST_CHANGES. The residuals and portability/documentation notes below do not leave a numbered finding unfixed.

## Six disclosures

1. **Final conformance-kit synchronization: acceptable.** The additive plain-target ancestor case strengthens coverage. Canonical region/pin-chain tests and all inventories match the submitted final bytes; the tests rerun against those bytes. I found no production-byte inconsistency from the synchronization.
2. **Accidental earlier real-Q6 test execution: acceptable as a disclosed process incident, not a permission to repeat it.** I did not investigate production inputs or independently audit that historical execution. This review explicitly excluded both tests with `-k "not test_production_q6"`; each S4 run reported two deselections. The incident alone is not a tooling integrity defect.
3. **Interpreter opens the entry script before bootstrap: acceptable stated trust boundary.** Direct entrypoint bytes/path are trusted inputs to isolated Python. The bootstrap now confines every subsequent pinned sibling read; shell tools avoid the script-path read with the inline loader. Approval does not claim protection against the interpreter initially opening an untrusted or outcome-aliased entry script.
4. **Mid-run host-tool replacement recorded as END exit 90: acceptable.** Each tool invocation revalidates and executes verified bytes; replacement fails closed, and the decoy never executes. Exit 90 loses refusal categorization but cannot establish successful END completion. Better labeling is optional.
5. **Part A import order: acceptable integration constraint.** Import s10_stage_host first for in-process use; ordinary pre-imported siblings fail explicitly. The pin chain is consistent and no unverified sibling is silently reused. Independent CLI entrypoints and the shipped fixture follow that contract.
6. **Foreign writes during the 3.8 mutation window: acceptable with an evidence limit.** The package attributes them to other work and says the runner verified that attribution. I did not access those foreign paths or independently reconstruct their creation. That window is not clean proof of exclusive outside-write confinement; final checksum consistency and this review's isolated synthetic tests remain independent evidence. No submitted production defect follows from the disclosed observation alone.

## Non-blocking notes

- **HOME exception wording:** HT:361 accepts any HOME beginning with exactly two slashes, then applies the normal path/canonical/config gates and installs the single-slash value. The package index calls `//home/sdicks02` the sole exception, but `//tmp/<clean-home>` is also intentionally accepted by the delivered test. On the Linux target, this does not bypass the no-follow/name/config gates or misalign Git's environment. Make the index accurately describe HOME-only double-slash normalization, or narrow the code and tests to the fleet home if literal restriction is intended. XDG retains strict refusal.
- **Test mode assumptions:** Git's default tar export produced 0775 shims, so the new exact-0755 assertion failed despite every shim being executable. Re-exporting the shim directory with `git -c tar.umask=0022 archive` made both F6 tests pass. Separately, a test process inherited umask 0077, yielding 0700 guard directories and 0500 staged read-only directories; three S10 assertions expected 0755/0555. Those tests pass with explicit process umask 0022. S10's entire production tail after `si = C.si` is byte-identical to r2, and safe_input is unchanged. Document the masks for reproducibility; these are not source regressions.
- The six-disclosure judgments concerning historical activity are limited to the evidence supplied. Offline synthetic success does not verify clocks, production mounts, live admission freshness, real preflight/load, actual frozen inputs or fleet execution.

## Reviewer verification and cleanup

Sources were exported in `/dev/shm`; tests used `/mpac/sdicks02/venvs/k4s-freeze/bin/python` 3.12.12 with `-I -B`, nice 19, bytecode/cache writes disabled, and no-network namespaces. Both normal and `-O` modes were exercised. Shipped fake-host children also use local fleet Python 3.8. I did not independently rerun a complete four-interpreter matrix or mutation campaign.

| Selected suite | Normal | -O |
|---|---:|---:|
| bootstrap-r1 | 371 passed, 4 skipped | 371 passed, 4 skipped |
| S2 new bootstrap tests | 61 passed | 61 passed |
| S4, real-Q6 excluded, no frozen-root export | 498 passed, 24 skipped, 2 deselected | same |
| Part A | 703 passed, 3 environment-mode failures; those 3 passed with umask 0022 | same |
| Part B | 610 passed, 1 export-mode failure; that control passed after explicit tar mask | 560 passed, 50 skipped, 1 export-mode failure; that control passed after explicit tar mask |

The bootstrap skips are four predecessor-comparison controls whose old sibling directories were deliberately not exported. S4's 24 frozen-consumer skips are explicit because K4S_FROZEN_ROOT was unset. I reran only S2's 61 new bootstrap controls to avoid the older suite's moving origin/main and real-repository fixtures; S1 approval is retained, with immutable byte equality independently verified. Part B's 50 optimized skips preserve the verifier's deliberate -O refusal.

Distinct selected controls that passed, including the targeted environment-corrected reruns: **2,247 normal and 2,197 optimized**. Repeated diagnostic/targeted passes are not added to these totals. The report preserves the initial failures rather than presenting a full pristine run with zero failures. No candidate source or test bytes were patched.

Independent auxiliary checks verified inventories, all production bootstrap copies, shell embedding, vendored-layer hashes, S1 identity and committed executable bits. A synthetic Git-parser probe confirmed ordinary promisor config refuses; commented malformed bare-key variants also refuse through Git's checked nonzero status. It performed no remote operation.

Temporary exports, test bases, diagnostic fixtures and their synthetic contents were removed after verification. All review test/probe processes completed; no review-owned process was left running.
