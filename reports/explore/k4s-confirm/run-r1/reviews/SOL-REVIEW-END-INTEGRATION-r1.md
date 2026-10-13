VERDICT: REQUEST_CHANGES

Independent SOL review of the K4S END integration fix package, 2026-10-13. Two blocking findings remain: the END-JOB builder consumes obsolete S9 pins, and the new S11/S9 mutation paths can write outside their repositories through unchecked Git metadata aliases. The ordinary component suites largely pass; neither result establishes integration safety. U11 also remains explicitly deferred, so the package does not close all twelve UNTOOLED rows.

This verdict concerns the submitted tooling and its integrated contracts. It does not adjudicate sealed outcomes or authorize a host step.

**Sources and review boundary.** I started with `git show --stat d00058bb` and its added `reports/explore/k4s-confirm/run-r1/end-prep/SOL-PACKAGE-INTEGRATION-r1.md`. Candidate bytes were exported from d00058bb8721a577feac91638ab32dda25e025ce. The fix commit is be175723776b68cfa98d029b109f5b199a5b68b5; the only subsequent candidate changes through d00058bb are the Part A README correction and its inventory entry in d7a37dbbeeb190cf9138cdc3e344f36ab99fb0df. Production artifact metadata came from Git at d7a37dbb. Frozen consumer code and selected non-outcome pins came from evidence tip 98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb.

The audit is `reports/explore/k4s-confirm/run-r1/end-staging/INTEGRATION-AUDIT-r1/REPORT.md`; 0d709b5b is its SHA-256 prefix, not an available commit ID. Its full digest independently matches `0d709b5becc8cc99ccffed08ad9532d05979b4461ea29e530aa557ef6deab6f6`. I read the four current RESPONSE files and the supplied prior review, `/mpac/sdicks02/k4s-runner/run-r1/reviews/SOL-REVIEW-END-FULL-r2.md`.

I contacted no host and performed no network operation. I did not read real game results, real `games/` contents, or sealed outcome files. Candidate archives, explicit frozen source exports, test fixtures and reviewer probes were confined to scratch. No repository files were edited. The only persistent reviewer output is this report. Synthetic adversarial files are reviewer-created markers, not study outcomes.

Paths below are relative to `reports/explore/k4s-confirm/run-r1/end-prep/` at d00058bb unless explicitly stated otherwise. A = `s3s9s10-r4`; B = `s5s6s7-r4`.

**1. Blocking: END-JOB self-check is pinned to the predecessor runtime and S9 (U8; broken S9 → builder hand-off).**

`B/k4s_a6_builder.py:233` selects the production runtime path `end-staging/runtime-98566c032d0b`, but `:234` requires manifest SHA `4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04`. The rebuilt manifest exported from d7a37dbb at that exact path hashes to `1fa0ebf5e4724711a27673236aa4800c97189890621c36c8ac2ee55585b8dde3`. The production build/verify record and all six S10 dry runs identify the latter.

`frozen_inputs` refuses this mismatch at `:407` before the self-check creates its scratch clone or invokes either consumer. The submitted healthy control `B/tests/test_a6_builder.py::test_frozen_inputs_are_pinned[none]` failed with `JobRefusal: S9 runtime manifest differs from its pin`. Independently, I supplied the SHA computed from the Git-exported rebuilt manifest to the unmodified `frozen_inputs` comparison and reproduced that exact refusal; it requested no later input.

There is a second stale dependency in the same hand-off: `B/k4s_a6_builder.py:243` selects `s3s9s10-r3/s9_end_runtime.py`, pinned at `:244` to `1875a32e…`. The adopted r4 S9 hashes to `80c15b5f7704a397d03bc3ad65fb57d2d59973c6d91319547514fae7381b92ff`. The child at `:490` consequently runs the predecessor membership rules. Changing only the manifest SHA is insufficient: r3's member plan lacks the three new support members, while the r4 manifest's `git_members` includes them; equivalence compares those member inventories.

Required fix: bind the builder's self-check to the adopted r4 S9 path/SHA and rebuilt runtime manifest, regenerate its inventory/proof, and exercise build → frozen `end_job` → **r4** S9 equivalence against that same runtime. Add a portable contract test tying those builder constants to the package's adopted S9 and production manifest. The existing stub-driver tests patch these dependencies, and the earlier builder proof used r3/4dd88461; they do not close this final-package hand-off. I did not rerun the real full-clone self-check because it bulk-copies `.git` and invokes real-repository processing outside this review's sealed-outcome boundary.

**2. Blocking: S11 advance and S9 refresh can write to unrelated trees through Git metadata aliases (U1/U10; new integrity defect).**

S11's `_verify` at `A/s11_host_repository.py:313` checks the clone, HEAD/ref set, clean work tree, ancestry, plain config and selected absent indirections. Its metadata role at `:328` does not screen `.git/FETCH_HEAD` or reflogs. `advance` then calls Git fetch at `:437` and checkout at `:443`. Git opens those mutable internal files independently of safe_input's descriptor gate.

I reproduced three attacks using the candidate's real S10 tools staging, S11 provision, S9 refresh/equivalence, and S11 advance fixtures. After provisioning P', I replaced one Git metadata leaf with an alias to a synthetic marker in the fake host's unrelated `/mpac/sdicks02/jobs/perception-synthetic/` tree. In every case the precheck passed, advance returned `status: advanced`, and the final verification passed **after the foreign marker had changed**:

| S11 alias | Observed foreign write |
|---|---|
| `.git/FETCH_HEAD` symlink | Marker replaced by 178 bytes of fetch metadata |
| `.git/FETCH_HEAD` hard link | Same overwrite through the shared inode |
| `.git/logs/HEAD` symlink | Marker grew to 387 bytes through reflog appends |

The new S9 `refresh-clone` has the same gap. `A/s9_end_runtime.py:589` performs the live clone check, but the fetch at `:597` writes unchecked FETCH_HEAD/reflog leaves. Its object-file and ref-value comparisons do not detect these outside writes. All three independent S9 probes returned success:

| S9 alias | Observed foreign write |
|---|---|
| `.git/FETCH_HEAD` symlink | Marker replaced by 101 bytes of fetch metadata |
| `.git/FETCH_HEAD` hard link | Same overwrite through the shared inode |
| `.git/logs/refs/remotes/origin/k4s-end-r1` symlink | Marker grew to 315 bytes through a reflog append |

These are pre-existing aliases, not races or monkeypatched Git behavior. I changed only synthetic fixture filesystem state and invoked the submitted commands. All six failures reproduce with normal Python and `-O`. S11's check and advance remained inside its one fake SSH session; the alias resolved only inside the namespace. No actual perception tree was touched.

Required fix: validate the internal Git write destinations and their ancestors before either operation mutates a repository. Refuse symlinks, nonregular files and multiply linked mutable leaves, including FETCH_HEAD and applicable HEAD/branch/remote reflogs; audit the other fetch/checkout write paths rather than fixing only these three leaves. Disabling unnecessary writes may reduce the surface but does not by itself establish confinement of the remaining writes. Add tests that require refusal **before the fetch/checkout**, with outside-marker byte equality and no successful receipt. Post-operation validation cannot undo an outside write.

The existing `test_r4_s11.py::test_host_verify_branches`, `::test_host_publish_is_no_replace`, and `test_r4_s9.py::test_refresh_refuses_a_corrupted_clone_before_the_fetch` cover other indirections and publication, but omit these mutable Git aliases. The prior approval of read-only clone checks does not approve these new Git mutation paths.

**Integrated-chain disposition.**

S4 → S10 is otherwise coherent. Adopted b3-r7 accepts runtime-pin `files` as dict keys, exactly like frozen `prepare_bundle.runtime_pins`; list support is compatible, and ignoring those embedded per-file values follows the frozen contract. Actual runtime bytes remain hashed. Assembly receipts identify the assembler; S10 pins `2b8f5fb3…` and refuses the predecessor or audit-patched assembler. The production RC-6 declaration identifies the rebuilt bundles, their tiers SHAs and matching guard jobs.

S10 stages runtime at `<base>/runtime-98566c032d0b`, tools at `<base>/tools`, and the native/corpus at `<base>/end-inputs-r1/{clasher_core.abi3.so,K4-states.pkl}`. Those agree with S5's layout and S7's argv/identity consumers. The six staged tool pins agree with the actual Part B bytes; notably S5 is `c7793451…`, host tool `22c441b1…`, END wrapper `65625fc0…`, preflight wrapper `c9779cfb…`, and safe_input `806e5ebb…`. The actual production ROOTS-DECLARATION bytes hash to `872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40` and pass the real r4 S7 `validate_roots` for both hosts.

S10 → S11 → S5 uses the same repository path and pinned host tool. A healthy synthetic provision produces a full, writable, non-shallow repository on `k4s-end-r1` at P', compatible with the frozen evidence reader. S11's branch/commit/END-JOB checks agree with S7 and the frozen END reader. Finding 2 prevents approval of its advance safety.

S5 → S7 preserves the verified receipt schema, native/corpus/inventory identities and guard-job-free bundle digest. S7's builder emits the consumed argv shape and evidence path/SHA; its host program verifies the runtime entrypoint and the END-JOB at repository HEAD before launch. S7 → S6 now has a reviewed PREPARE-PROOF producer: verifier prepare writes byte-equal pinned copies at the exact launch/receive paths. The wrappers' unchanged bytes and the verifier/gate pins agree. The S6 claim snapshot/receive/verifier controls pass on synthetic claims. Real sealed receipt processing was not run.

S9 refresh → equivalence → S11 advance has working healthy-path tests, exact END-JOB-only tree-diff checks, unchanged runtime/measurement sets and the correct branch ref. Finding 2 leaves the refresh/advance write boundary open. The builder's reverse dependency on S9 remains broken by finding 1.

**Audit-row closure, with actual consumer tests.** “Closed offline” means the producer and consumer contract was exercised or independently checked within the permitted boundary. It does not mean live-host qualification. Test names are in the candidate directories shown.

| Row | Disposition | Relevant hand-off coverage / remaining requirement |
|---|---|---|
| B1 | Closed offline | b3-r7 `test_frozen_runtime_rule_parity`, `test_frozen_validate_bundle_accepts_and_rejects`, and `test_s4_r6_runtime_pin.py` dict-key/value/name controls; real pinned shape corroborated from Git |
| B2 | Closed offline | A `test_runtime_staged_at_base_runtime_p12_and_accepted_by_s5_layout`; real S10 output consumed by S5 layout |
| B3 | Closed offline | A `test_support_members_are_exported_pinned_and_outside_the_file_hash_sets`, `test_membership_neutral_for_runtime_and_measurement_files`; actual manifest support pins checked against Git blobs and S5/S7 constants |
| B5 | Closed offline | Same parametrized support tests; B `test_s5_pre_import_pins_require_the_pinned_delta_manifest`; recorded frozen-identity chain |
| B6 | Ruling recommended | S9 `test_s9_equivalence_of_the_refreshed_x`, builder `test_scratch_commit_is_the_job_alone`; commit placement must follow the ruling below |
| B7 | Closed offline | A `test_declare_roots_is_exactly_what_s7_consumes`; rebuilt declaration independently accepted by actual r4 S7 |
| U1 | OPEN: finding 2 | Healthy S11 provision/advance passes consumer clone checks, but foreign writes pass as successful advances |
| U2 | Closed offline | A `test_tools_and_end_inputs_staged_a_w_single_link`, `test_production_constants`; staged pins equal actual S7 consumers |
| U3 | Closed offline | Same staging test and end-input refusal cases; actual native/corpus SHA constants agree across S10/S5/S7 |
| U4 | Tool supplied; qualification OPEN | A `test_interpreter_probe_recorded`, `test_interpreter_probe_refusals`, `test_probe_command_mirrors_the_end_launch_environment`; exact host environment not established offline |
| U5 | Closed offline | B `test_build_argv_output_passes_the_gate_and_launches[end/preflight]`, plus every-token refusal tests |
| U6 | Closed offline | B `test_prepare_preflight_receive_then_build_and_launch`; prepare output passes actual gate receive checks |
| U7 | Closed offline | B `test_verifier_prepare_writes_the_proof_s7_accepts`; actual gate consumes the byte-equal proof with its printed SHA |
| U8 | OPEN: finding 1 | Build/scratch/stub tests pass; submitted healthy frozen-input test fails on the rebuilt runtime; old proof does not exercise adopted r4 S9 |
| U9 | Closed offline | Same declaration producer/consumer coverage as B7 |
| U10 | OPEN: finding 2 | Healthy refresh → equivalence test passes, but refresh follows unchecked write aliases |
| U11 | OPEN; explicitly deferred S8 | Both audit §4.9 and A RESPONSE exclude it as “after END”; no reviewed claim/receipt collection, registry/finalization and pool/recheck producer is delivered here |
| U12 | Closed offline, optional | B template schema tests and filled-template per-field refusal tests exercise actual ruling validators |

Thus the answer to “are all six MISMATCH and twelve UNTOOLED rows closed with real hand-off tests?” is **no**. B6 is addressed by a sound proposed ruling; U4 retains a live qualification boundary; U11 is deferred; U1/U8/U10 have the concrete defects above. Deferring U11 can be a phase decision, but it must not be reported as closure. A reviewed S8 remains required before post-END finalization/pooling.

**IR-03.** The S3/S4 changes are correct for bus-only 03. S1b keeps its historical collection contract; S3 selects `END_ADMISSIONS` rather than copying its retired idle row, and verifies the exact bus-only admissions/top-level shape. b3-r7 removes only 03's idle pin, refuses an idle binding/request before reading it, and retains the other production pins. S10 rejects a bundle whose admissions disagree with S3's set.

The frozen ReportingGuard behavior is as claimed: `fleet_validity.py:110` requires the bus admission; `:112` rejects an existing optional admission that is not pinned; `:125` checks both bundle and job admission bytes. A bus-only job therefore works, the old bundle map fails when the job's pinned idle file is missing, and an unpinned stale idle file refuses. Frozen `idle_services.pins` returns an empty list when the file is absent, so the idle meter grants no idle-service exception. I reran the real frozen constructor tests against selected Git-exported frozen sources; bus-only acceptance and stale-file rejection pass in normal and optimized modes. The REAL-CHAIN-r4c record used an in-memory map adjustment on a b3-r6 bundle; it is corroborating evidence, not a pristine final b3-r7 full-chain run.

**S11 host-safety assessment.** Its basic design is suitable: fixed base paths, pinned staged code, no host network clone, one login per mode, exclusive transfer/partial creation, template-free init, one branch, clean/writable checks, and no-replace publication. Temporary Git HOME directories and the local bundle scratch directory are tool-owned scratch; the host transfer directory and FETCH_HEAD are intentionally retained. Healthy provisioning does not edit other job trees. However, advance currently fails the explicit “never touch other trees” requirement, as finding 2 proves. It is not safe for approval until Git's write destinations are confined as well as the wrapper's explicit paths.

**Requested rulings.**

- **B6: endorse.** Commit RC-6 declarations, disclosures and other pre-X paperwork to main. Keep `k4s-end-r1` at P' until a single END-JOB addition produces X; do not merge/cherry-pick that paperwork onto the evidence branch. RC-6's `commit` identifies P', the runtime commit, not the declaration's main commit. Preserve S9's exact diff gate. This resolves the rule/tool mismatch without widening the runtime equivalence allowance.
- **U4: do not ratify the bare executable unconditionally from `/proc/exe` evidence.** `runtime.sh` at P' actually executes `/mpac/sdicks02/repos/clasher/.venv/bin/python -B`; the base uv binary's resolved path does not identify that venv's site-packages. The Part A README explicitly expects the bare binary may fail torch import. The submitted S10 probe and S7 builder agree on the bare 3.12.13 path and the probe fails closed, which is useful tooling, but the fake-host evidence used 05's e4v3 venv. Accept the proposed path only after the authorized probe establishes its exact environment on both hosts. If the venv path is selected instead, update S10 and S7 together, repin their dependents and rerun argv/probe integration. No host capability was inferred or tested here.
- **D1 extension: endorse.** The three added support files are tracked, SHA-pinned to P', and required by frozen consumers: SD1 `b8ce7b4c…`, corpus inventory `3501e2ac…`, DELTA `34eca2b7…`. Their actual Git blobs and rebuilt inventory agree. All three remain outside `runtime_files` and the measurement set. The rebuilt runtime has 4,316 inventory files; runtime canonical SHA stays `fc3dbeb42a7737ab844f1f6033ff42b19cd1d514f9670631e36cc7f72a2008e7`, measurement SHA stays `42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25`. The overall manifest and `git_members` do change: every consumer of those identities, including the builder, must adopt the new pins.

**Verification and cleanup.** All 250 listed candidate inventory entries verify: b3-r6 30, b3-r7 42, Part A 73, Part B 105. Each SHA256SUMS file's digest matches the package index. The Part A vendored Part B pins agree with the delivered Part B sources; unchanged safe_input remains `806e5ebb…`.

Tests ran at nice 19, umask 022, through `/mpac/sdicks02/venvs/k4s-freeze/bin/python3` 3.12.12 with `-I -B`, bytecode/cache output disabled and network namespaces denying external network. Fake hosts additionally used the shipped mount/UTS namespaces. Git archive used `tar.umask=0022`. I did not rerun the complete four-interpreter matrix or mutation campaigns.

| Reviewer run | Result |
|---|---|
| Part A supplied suite, normal | 955 passed |
| Part B supplied suite, normal; real full-clone proof and real committed-pin test deselected | 723 passed, 1 failed, 2 deselected; failure is finding 1's healthy frozen-input control |
| Adopted b3-r7, normal; real Q6 and live request comparisons deselected, no frozen-root setting | 533 passed, 27 skipped, 5 deselected |
| Selected b3-r7 frozen consumer controls, explicit safe source export | 33 passed normal; 33 passed optimized; 532 deselected in each selection |
| Reviewer foreign-write probes | All 6 fail the no-outside-write assertion in normal and optimized modes; S11/S9 nevertheless report successful operations |

The two real-Q6 tests were never executed. The b3-r7 skips include the unconfigured frozen consumers and real-runtime controls; the separate frozen run supplies the applicable consumer coverage. Repeated probes/control overlaps are not added into a claimed distinct-test total. Pytest's optimized assertion warning is informational; the defect probes use explicit raises.

Reproduction of finding 2 requires only synthetic fixtures. For S11, use `test_r4_s11.ready`, `advanced_clone`, and `provision_at_p`; replace the provisioned clone's FETCH_HEAD or HEAD reflog with the aliases described above; invoke `run(advance_args(...))`; compare the foreign marker before/after. For S9, use `repo_copy` and `origin_branch(world.X2)` from `test_r4_s9`, install the listed aliases, and invoke `refresh(..., base=world.P)`. Neither probe alters candidate code or substitutes Git. No real repository/bundle/evidence processing is necessary.

All test/probe processes completed. The `/dev/shm` exports, pytest bases, reviewer probe file, and synthetic fixtures were removed; fixture-owned `/tmp` trees were cleaned by their teardown. No review-owned process remains. No fix was made during this review.
