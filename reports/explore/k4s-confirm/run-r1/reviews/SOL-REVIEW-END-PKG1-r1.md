# SOL review: K4S END package 1, r1

**Verdicts: S1 — REQUEST_CHANGES; S2 — REQUEST_CHANGES; S4 — REQUEST_CHANGES.** The ordinary tests pass, but independent probes reproduce failures of the stated read/write boundaries and of frozen-code verification. This package is not approved for production use.

Reviewed on 2026-10-12 against `origin/main = caeeecdccb795b0aa049776d5377ff00190f4b10`. Repository sources were read with `git show`, including the last COORDINATOR sections at `reports/strategy_council_20260928/COORDINATOR.md` (7270b5fa and fa89baa9), plan v2 (9e85afd3), and the prior review at `/mpac/sdicks02/jobs/clasher/k4s-audits/K4S-END-PLAN-REVIEW-r1.md`. The Q2–Q6/Q9 rulings govern this review, including state inputs from 05 only, T1 guard semantics, and fresh guard jobs per attempt.

There were no changes or commits to the clasher repository, no SSH connections, and no live S1 run. Tests, synthetic git repositories, fake hosts, and mutated copies were confined to `/tmp/sol-end-pkg1-r1-ujdby8d2/`. Paths named `games/` in the reproductions contain reviewer-generated canary bytes only; no real outcome files or block directories were opened.

The candidate bytes match the package:

- S1: `697068344355f3f3517764cf2347279f981da3a6e3dfea7e4abdd9b697b8911e`.
- S2: `06b51f9da44acee878469bb85081ca3e450aea37ec52d8c4408072d354053942`.
- S4: `00f4dea5fe434f51b484f2ef9a30fcaa6cab3bb8ee39e1c87a75393a906bcd89`.
- conftest/test_s1/test_s2: `217923bc…` / `393bdc02…` / `82afcf1a…`.
- S4 tests/design: `4b74e866…` / `950ecb7a…`.

Source references below use these committed bytes. S1/S2 live under `reports/explore/k4s-confirm/run-r1/end-prep/s1s2-r1/`; S4 under the sibling `b3-r1/` directory.

**S1 — REQUEST_CHANGES**

The literal command construction is good. `expectations()` binds all ten host/phase pairs to the committed history, completion-v2, and the twenty launch/exit SHAs. Remote operands name only the four allowed filenames, without enumeration, globbing, or recursive commands. The 04 command strings use `/mpac/sdicks02/jobs-k4s/`, never `/mpac/sdicks02/jobs/`. `shlex.quote`, a restrictive path alphabet, fixed host names, and argv-based subprocess calls make the remote quoting safe. The success path has exactly P03, P04, C03, V03, C04, V04, with the required SSH options and low-priority remote commands.

The pre/post metadata checks, stream-length check, local hashes, and post-stream remote hashes prevent acceptance of changed bytes. `Session.run()` handles standard Linux/OpenSSH exit codes correctly: nonzero, including a remote rc 37 after otherwise valid output, refuses. No platform-specific exit-code adjustment is needed. Only the twenty telemetry files are stored locally; launch/exit bytes already exist as committed phase-meta and are hashed remotely.

These protections do not establish the required filesystem confinement:

1. **S1-F1, blocking: remote rejection happens after forbidden reads; directory aliases are accepted** (`inspect_command`, lines 179–182; `parse_inspection`, 213–225). P/V run `stat` on every operand, then unconditionally run `sha256sum` on every operand. The regular-file and size decisions happen on 05 after both commands finish. A leaf symlink is therefore followed and its target read before the local refusal. A nonregular object can also reach the hashing command. More seriously, `stat` does not establish that parent components are not symlinks: a phase-directory alias produces regular-file leaf stats and can pass every SHA check.

   Reproductions: a synthetic 03 `mhz.jsonl` symlink into `games/decoy.json` was passed to `sha256sum` before S1 returned “not a regular file.” A synthetic 04 phase directory symlink into its fake `/mpac/sdicks02/jobs/clasher/` tree completed successfully. Literal command-string exclusion of that prefix does not exclude reading through an alias.

   **Required:** check fixed path components and regular-file identity before any content read, reject aliases into forbidden trees, and use an opening/streaming mechanism that cannot follow a substituted symlink between checks and reads. This can remain within the six sessions and use only explicitly named paths. Check types and bounds on the remote side before hashing; a later local refusal cannot undo a read.

2. **S1-F2, blocking: local ancestor aliases are accepted** (`run`, 283–294; `split_stream`, 250–254; refusal writer, 333–336). The destination's own existence/symlink test does not inspect its ancestors. A fresh destination below a symlinked parent is accepted, and all output is written into the alias target. The probe returned success and created `s1-copy-manifest.json` there. `mkdir(..., exist_ok=True)` and the refusal writer also lack confinement checks on the directories/files they use.

   **Required:** establish a canonical, permitted destination on 05, reject unsafe ancestor aliases, and retain that directory identity for all creation, splitting, manifest, and refusal writes. Use exclusive/no-follow receipt creation; `open(..., "w")` must not overwrite an existing symlink or hard-linked receipt. Add ancestor-alias and output-substitution tests.

3. **S1-F3, blocking: the cap is checked after hashing, and streaming is unbounded** (`check_inspection`, 228–237; `run`, 297–301; `split_stream`, 244–245). An oversized source is fully hashed before refusal. After P, an enlarged source is streamed by unrestricted `cat` into a local file until command completion or the one-hour timeout; only then is its length rejected. Thus the cap prevents a successful oversized copy but does not bound the remote reads or local writes. The README also explicitly exempts launch/exit from the size cap, whereas this review brief states `0 < size <= 95 MiB` for the files.

   **Required:** apply regular-file and size gates before hashing all four named files, and bound C's reads and 05's stream sink to the inspected lengths, with explicit excess-byte detection and nonzero refusal. Preserve the existing SHA checks and remote-rc handling. Add a growth/oversized-stream control that verifies the amount read/written is bounded, not merely that final acceptance fails.

4. **S1-F4, required: early refusals have no receipt** (`run`, 269–294 and 332–337). Missing window acknowledgement, invalid committed expectations, and P-stage failures occur before a destination is created or before the receipt handler. The existing tests intentionally expect no destination in these cases. The independent missing-window probe also produced no receipt.

   **Required:** provide a safe, explicitly declared refusal-receipt destination available before host access, or another equivalent structured receipt mechanism. Cover every refusal without creating or writing into a rejected/aliased destination. Preserve partial copies and never publish a success manifest on failure.

**S2 — REQUEST_CHANGES**

The builder obtains artifact bytes through `git show` of one full commit. Its default record pins are correct: plan `38064dcd`, completion `3794d953`, inventory `22c41cb7`, ledger `649272bd`. It binds exit hashes to completion, requires committed nonempty artifacts, and keeps evidence outside the strict END namespace. The validator's default membership, layout, full-occupancy, core-coverage, and finite-positive MHz checks are useful. Its work-tree artifact reads are subsequently checked for byte equality with committed blobs and ancestry by the frozen reader.

I separately verified the exported frozen code against manifest `74314eda` before importing it in the reviewer harness, then ran its `counting()` on the real committed completion-v2, ledger, inventory, and ten exit documents: **3,900 blocks, 99 losses, all ten host/phases**, normally and under `-O`. Full real-telemetry `end_evidence()`/`host_reporting()` validation remains unavailable before B2; the supplied S2 success fixture covers 3,900 blocks and one synthetic loss with explicit expectation overrides.

1. **S2-F1, blocking: unverified code executes and performs its own verification** (`frozen_modules`, 205–219). S2 imports `k4s_logic`, `end_evidence`, and `end_pool` before checking their pins. It then calls the imported, still-untrusted `L.load_k4s_manifest()` to establish their identity. File-location checks prove location, not bytes.

   Reproductions: appending a harmless top-level canary write to the exported `end_evidence.py` executed that write before S2 refused the pin mismatch. Appending `verify_pinned = lambda *args, **kwargs: None` to exported `k4s_logic.py`, and changing exported `fleet_end.py`, caused normal validation to return **`ok:true` and `frozen_manifest_verified:true`**, with the default 74314eda manifest expectation. This is a successful false verification, not just import side effects on a failing run.

   **Required:** bootstrap verification in trusted S2 using stdlib only: hash the raw manifest against the fixed approved SHA, parse its pinned inventories, and verify the complete code/dependency closure before importing any of it or calling its functions. Retain import-origin checks afterwards. Add both pre-import canary and modified-verifier controls. The production entrypoint must require frozen verification; isolate `--no-manifest-check` and record-pin overrides as explicit test facilities that cannot produce a production approval receipt.

2. **S2-F2, blocking: validator artifact paths are not the declared health-only paths** (`structure`, 187–202; `validate`, 235 onward). `structure()` checks key sets, a commit, and a textual path relationship. It does not require the exact top-level and per-host/phase paths used by `build()`, or reject outcome/block locations before the frozen reader opens them. The record checks following `E.end_evidence()` cannot protect the preceding reads.

   Reproduction: place synthetic valid MHz JSONL under `reports/explore/k4s-confirm/games/synthetic-clock.jsonl`, commit it in the synthetic repository, and change one evidence `mhz` item's `path`/`repository_path` accordingly. The unchanged validator consumes it and returns success. No real outcome data was used.

   **Required:** validate every artifact's exact role/path and registered host/phase against the declared inputs before artifact access. Check normalized relative paths and resolved filesystem confinement, including ancestor/leaf aliases, before work-tree reads. Validate known record pins before opening corresponding data. Keep the frozen committed-byte/ancestry checks as additional checks. Add games/block-path and symlink controls that assert zero forbidden reads, including when eventual validation would fail.

3. **S2-F3, required tests:** add controls for nonfinite/nonpositive MHz and for an S1 launch/exit metadata mismatch while telemetry remains correct. Deleting these checks survives every supplied S2 test; the reviewer controls kill those mutants. Production validation should use the verified S1 receipt and the final S4 profiles as described in the runbook.

**S4 — REQUEST_CHANGES**

The generated manifest/profile, evidence subdirectory, T1 guard-module and four seed/join mappings are compatible with the frozen consumers on valid fixtures. The request SHA, exact request keys, plan/model/guard pins, copy rehashes, canonical serialization, and staged publication are meaningful. The actual frozen `validate_bundle` and `ReportingGuard.__init__` accept the test bundle/job, and reject the tested corruptions. Inputs on the ordinary success path are read-only.

1. **S4-F1, blocking: runtime and measurement inventory reads bypass confinement** (`runtime_files`, 153–166; `measurement_files`, 148–150). The S1 runtime-pin JSON controls `names`. Names are not passed through `relative()` or checked to remain under the runtime root before `root / name` is hashed. Absolute names replace the root; `..` escapes it. Discovered `.py` files and measurement-directory entries can be symlinks. These paths never pass through `no_outcome_path()`. The composite inventory SHA is compared only after the reads.

   Reproductions, all accepted by `plan_bundle()` with a consistent request: an absolute runtime-pin entry outside the runtime root; `../synthetic-marker.json`; a runtime `.py` symlink to a synthetic `games/` canary; and a measurement `.py` symlink outside the runtime tree. The canary target was actually hashed. A stale composite SHA would fail later but would still permit the prior read.

   **Required:** validate inventory metadata and every discovered entry before hashing. Require normalized relative names, enforce the declared-root boundary, reject unsafe aliases and outcome/block locations in both inventories, and protect against replacement between validation and opening. Apply this to metadata/dependency JSON paths too. Keep the frozen inventory membership rule for legitimate files; reproducing its membership rule does not require reproducing unsafe path resolution. Add these four controls and verify that forbidden bytes are never read.

2. **S4-F2, required: enforce the ruled production inputs, not merely internally consistent substitutes** (`models`/index/sets checks, 203–240; admissions, 325–342). State pickle/index/bin are pinned only to request-supplied values; speed sets need only nonempty unique IDs, not T1's own-tier 300-state sets. On 03 the required `idle-services.json` can be omitted. The synthetic fixture successfully uses a different pickle, a twelve-row index, and three speed IDs per tier; a separate omission probe accepts a 03 bundle with no idle admission.

   **Required:** bind the production request to the Q6 byte identities (`states.pkl` 0addf7c0, index bcd30777, bin 8cc2f611) and the committed T1 A3/A5 own-tier sets, through fixed pins or a separately verified approved-reference binding. Require 03's idle admission and the host's committed Q2 bus admission. Use only their authorized copies on 05. Maintain distinct fresh guard jobs for preflights and each attempt. Bind topology to target-host evidence and retain the mandatory on-host topology/identity/preflight checks; this assembler only validates topology's shape.

3. **S4-F3, required: state-index acceptance is weaker than the frozen loader** (`plan_bundle`, 216–227). The assembler accepts a wrong `pickle_protocol` and noncontiguous offsets. Frozen `StateRows.__init__` rejects these at `state_rows.py:34–54`; later backend construction can otherwise encounter them after a claim. The independent probe changed protocol to 999 and the first offset to 77 and still obtained a planned manifest.

   **Required:** either enforce the exact approved immutable index from S4-F2, or mirror the frozen loader's protocol, contiguous positive-length rows, final length, and associated shape checks without unpickling. Add rejection controls. Do not replace the mandatory preflight with these offline checks.

The package does not exercise live `ReportingGuard` admission, seed-commit lookups, model/native loading, or background load. Those remain S3/S5 responsibilities. The test guard `repo/` is a file tree, not proof of the Q3 git clone/commit requirement. The real-consumer tests patch three policy-model SHA constants to synthetic values and use synthetic states/admissions; they establish layout compatibility, not verification of the real approved input bytes. DESIGN's descriptions of unavailable T1 inputs and old draft questions should be reconciled with fa89baa9's rulings before operational use.

**Tests and mutation evidence**

Every test and reviewer driver ran with `nice -n 19` using `/mpac/sdicks02/venvs/k4s-freeze/bin/python` (3.12.12). No real SSH executable was invoked by the S1 tests; their shim runs local shell commands over synthetic trees.

- Supplied S1/S2 suite: **34/34** normally, **34/34** under `-O` (15 S1, 19 S2). The fixture propagates `-O` into script subprocesses. Pytest rewrites assertions in the test modules, so these runs are not simply vacuous; the standard optimization warning was present.
- Supplied S4 suite with `K4S_FROZEN_ROOT` set to the exported committed closure: **92/92** normally and **92/92** under `-O`, with no skipped consumer tests. My first export omitted the reviewed A5 inventory JSON, causing one fixture failure; after exporting that committed JSON, both runs passed. This was reviewer fixture setup, not a candidate defect.
- S4's `frozen_python()` does **not** propagate `-O` to frozen-consumer subprocesses. I additionally ran a separate scratch test copy that adds `-O` there: **92/92** passed. Fix the checked-in helper if its “under -O” claim is meant to include those consumers.
- Thirteen synthetic confinement/verification/specification probes reproduced the described behavior normally and under `-O` (seven S1/S2, six S4). Four additional regression controls passed on the originals under `-O`: same-length transport corruption, valid output with remote rc 37, NaN MHz, and S1 launch-meta mismatch.
- **21 targeted mutants under `-O`: 18 detected, 3 survived.** Detected changes cover S1's pre-copy binding, cap, nonempty/file-kind/window/host-key/remote-rc/post-copy gates; S2's manifest/evidence/membership/structure gates; S4's copy hash, seed map, host, explicitly supplied outcome paths, evidence-root boundary, and frozen model pin. Some detected deletions are caught by redundant downstream guards or diagnostic assertions; this is not a claim that every guard was independently isolated.
- Surviving mutants were: removal of both S1 per-piece/local-rehash comparisons (**15/15 S1 tests still passed**); removal of S2 finite-positive MHz validation (**19/19**); removal of S2 S1 launch/exit metadata cross-checks (**19/19**). The corresponding reviewer regression controls killed all three. The valid-payload/nonzero-rc control also killed the S1 rc mutant directly.

The suites are meaningful, but their passing totals do not establish the advertised confinement. Add the reviewer regressions and boundary probes to the production suites with expectations changed to refusal-before-access for the current defects.

Reproduction assets are retained in the scratch directory: exported candidates under `reports/explore/k4s-confirm/run-r1/end-prep/`; `test_reviewer_probes.py` and `test_reviewer_regressions.py`; `run_mutations.py`; `mutation-results.json`; per-mutant `mutation.log`; `survivor-regression-results.json`; `real_counting.py`; and the separately optimized S4 consumer-test copy.

**Census/MHz misalignment**

The frozen join is fail-closed and must remain unchanged. `fleet_end.host_reporting():204–221` rejects duplicate/wrong-host census rows, duplicate/unmatched MHz UTC keys, slot mismatches, unequal UTC-key inventories, and fewer than two selected full-occupancy rows per host. S2 catches that exception, writes `ok:false`, and returns 2. The supplied missing-MHz-row control verifies this refusal.

The source-level diagnosis is precise with one qualification: `supervise.py:109–117` obtains **one** `progress['utc']`, appends census, reads `/proc/cpuinfo`, and appends MHz using **that same UTC**. Time spent obtaining MHz does not itself create timestamp skew. An abrupt termination, crash, or write/read error between the appends can leave an unmatched census row. Ordinary SIGTERM/SIGINT are handled by setting `interrupted` and stopping children (`:51–54`); they do not inherently terminate execution between those writes. Whole-second timestamps plus a one-second sleep make duplicates unlikely during steady forward wall-clock operation; repeated wall-clock timestamps still require rejection.

The present error receipt usually carries only a generic frozen message such as “Reporting MHz/census inventories differ,” with no host/phase or unmatched UTC details. **Required diagnostic improvement:** retain the frozen refusal while adding an outcome-blind diagnosis identifying host/phase, row/key counts, and the first missing/extra/duplicate UTC. Do not filter rows, repair timestamps, zip by index, or relax the join. Preserve and bind the unmodified raw sources; any real mismatch requires the coordinator ruling described in the README. No actual mismatch is asserted here because the reporting telemetry has not been copied/committed.

All blocking changes require a revised package and review before use. The separate coordinator authorizations and on-host preflight gates remain in force after code approval.
