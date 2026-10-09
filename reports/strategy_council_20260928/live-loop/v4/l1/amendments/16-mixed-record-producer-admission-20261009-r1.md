# Amendment 16 — prospective mixed record-producer admission

Status: PROSPECTIVE DRAFT FOR INDEPENDENT REVIEW. Not frozen, not an execution approval. The final review package must contain the actual worker, queue-plan and three completed qualification pins; an incomplete package cannot authorize a switch.

This amendment changes only the file layer by which validation capture records enter the frozen Amendment 12 body stage and optimistic bounds. It extends frozen Amendment 15 revision 2. It changes no scientific score, threshold grid, split, truth mapping, selection ordering, timing attribution, calibration, deciding measurement, replication, heldout replay, T6 behavior, or final gate. All frozen A12 and A15 bytes remain unchanged. New, separately named A16 modules implement the extension.

## Scope and prerequisites

The original whole-match capture worker remains admitted for record-only capture. The new vectorized worker may produce record-only capture only after all of the following are independently pinned and verified:

1. A14 non-clock proof SHA256 `8f2d0e076a919cbd84d0ae1fae69aa57e2844e53b885846ed2d468f18014d003`.
2. The production-lane benchmark reaches the coordinator's fixed 15% improvement criterion. This engineering measurement is not an availability measurement or a selection input.
3. Complete whole-match qualifications for epoch 7 / `v4-phase-a-1975100738`, epoch 15 / `v4-phase-a-1975100748`, and epoch 1 / `v4-phase-a-1975100708`, using the exact new worker and source pins. Every byte of every decoded record in all nine branches must equal its retained original reference. Cold-start match 708 remains included.
4. A prospective new queue plan and typed producer contract bind that worker, its complete source pins, the A14 proof and all three completed qualification receipts.
5. Independent review, a coordinator freeze record, and explicit file-layer approval bind the final amendment and delta. The performance result alone never admits production or evidence.

CUDA tensor batching remains excluded. Neither the vectorized producer nor its journals is admitted for standalone deciding cells, D4(b) reference replay, timing, heldout replay, or T6. Those paths retain the original runtime and driver. A prospective live-runtime use is outside this amendment.

## Exactly one source, including mixed epochs

Each of the 24 assembled epochs contains exactly 64 validation matches and all nine body branches per match. Each entry carries an explicit `producer_type` equal to `original` or `vectorized`; unknown or missing values are rejected. Retained inventory entries are always original. A mixed epoch is valid when some unique matches come from original producers and other unique matches come from the qualified vectorized producer.

A producer type is established by the reopened task, host plan, child intent and launch, complete metadata, manifest, source hashes and pinned contract. It is never inferred from a label, path, FPS, or self-declared PASS. A queue entry coexisting with any retained original of the same epoch/match is rejected. Two completed queue sources for the same epoch/match are rejected. No first-wins selection or silent substitution is permitted. Already completed original outputs remain the evidence for their matches; the switch does not rerun them.

The shared-state queue overlay conserves the existing population: 583 retained originals plus 953 queue outputs equals 1,536 epoch/matches; the 61 terminal retained queue tasks cannot become claimable. All task fields controlling scientific inputs remain byte-equivalent. A worker/type change is prospective and cannot rewrite an existing claim or output. The original queue plan and state plan SHA remain unchanged. A new immutable vectorized overlay plan pins the base SHA, qualified worker/source closure and record-only evidence. Under the same queue lock, only externally registered vectorized owners may claim an overlaid task copy; old claims and original endpoint behavior remain intact. Every vectorized claim binds its overlay SHA, base SHA, host-plan SHA and exact PID/start/boot owner. The closed state registration also binds the production release receipt. Admission reopens each original or vectorized claim against its own approved plan. No active-source mutation, timeout retry, or duplicate claim is introduced.

## Whole-match qualification evidence

A qualification reference is bound to its unique retained inventory origin: host, directory, inventory SHA and manifest SHA. Non-in-place references require a pinned copy receipt with the exact nine original compressed record hashes. Reference and output directories must differ. Each candidate complete file must bind the new worker and full source-frame count.

Admission reopens all nine reference and output streams, compares every uncompressed record byte, verifies frame identity and count, and checks compressed and uncompressed hashes. This is independent of the receipt's equality booleans. Missing branches, truncated matches, wrong worker/source/plan, changed reference provenance, changed raw records, or any availability field in a raw record fail closed. Journals remain opaque pinned artifacts and are never read as clocks.

## Byte authentication and relocation

The original A15 audit path is reused unchanged for original producers. A new A16 vectorized audit requires the new typed host plan and task, exact worker/source pins, durable pre-spawn intent, exact launch command, successful outcome and complete metadata. Its manifest has the same scientific configuration as the original plus explicit vectorized provenance. Record timestamps remain production timestamps, not measured availability.

A15 relocation rules remain in force: only copies with byte-identical original proof members are admissible; receipts explicitly name the source and destination; producer metadata and bundles remain reachable through A2. Per-use compressed and uncompressed record checks and post-scoring rechecks remain unchanged. The A15 process-local admission memo, evidence ledger and documented exceptions remain unchanged. Persisted memo receipts never become authority.

## A1, A2 and timing remain staged

A16 does not approve A1. All existing A1 checklist obligations remain, including the four R13-3 production-load recaptures on two leased hosts with two cells each and original worker, closed unsuspended queue, full 24 complete assembly pins, immutable execution tree, actual admission-only dry run on 04 or 03, and coordinator approval-A1. Assembly epoch keys are checked mechanically and by the new A16 pre-body guard. All frozen scorer and ranking semantics are retained.

The real clock-free body seal must precede every bound. A2 is the timed real bounds computation only after that seal verifies. Bound publication, elimination and deciding measurements still require the coordinator's B approval and all B preconditions. All 216 bound records retain body-seal binding. D4 failure still suspends elimination/selection durably and notifies the coordinator. Tier 2 stays disabled; all 64 Tier 1 matches remain; 30 measured cells remains a reporting checkpoint, not a stop.

The original shared/packed/vectorized capture clocks remain `INVALID_RECORD_ONLY`. No clock division, backdating, modeled service, inferred offsets, or reused contended fleet latency is introduced. Frozen A12 disclosure and both final event gates remain unchanged.

## Deployment and review boundary

Capture stays on the original worker while this package is reviewed. Cache renewal proceeds separately and retains the 11:30Z deadline. After freeze and qualification, controllers switch at safe whole-match boundaries host by host; completed originals and partial evidence are preserved. No host gains permission merely from an expected release time.

The final package will include the exact source delta, source/test/PYTHONPATH manifests, discriminating mutation results, actual qualification and benchmark receipts, new worker and queue-plan pins, and the final typed contract. All missing operational evidence remains an explicit package blocker; no invented hash stands in for it.

## Freeze and release interface

The coordinator's A16 freeze record uses `schema: clasher.v4.amendment16-freeze.v1`, `decision: FROZEN`, and `producer_contract_sha256`, alongside the exact amendment/package/delta pins. A separately pinned `clasher.v4.vectorized-production-release.v1` receipt binds `queue_overlay_sha256`, `a16_contract_sha256`, `freeze_record: {path, sha256}`, and `timing_admitted: false`. Each finalized vectorized host plan pins that release path/SHA. Queue registration checks it before any vectorized child is launched. The owner registry and subsequent independent admission must agree on that same release SHA. Neither a fresh host label nor an unpinned declaration grants authority.

The following are interface descriptions, not issued approvals. The owner must not fabricate any of these coordinator receipts.

| Receipt | Required fields and exact meaning |
|---|---|
| A16 freeze | `schema = clasher.v4.amendment16-freeze.v1`; `decision = FROZEN`; `producer_contract_sha256` equals the final reviewed contract. It also records the exact draft, delta, package and independent review hashes. This freezes bytes; it is not A1. |
| A16 file-layer approval | `decision = APPROVE_FILE_LAYER_DELTA`; `delta_sha256` equals the final A16 delta; `amendment_sha256` equals the final A16 draft. Record the independent review and freeze SHA as provenance. No schema coercion converts a freeze into this approval. |
| Production release | `schema = clasher.v4.vectorized-production-release.v1`; `queue_overlay_sha256` equals the reviewed overlay; `a16_contract_sha256` equals the contract; `freeze_record = {path, sha256}` pins the actual A16 freeze file; `timing_admitted = false`. Each host plan separately pins `production_release` and `production_release_sha256`. This permits the qualified record-only producer under the fleet guards, not scoring or selection. |
| A1 approval, later | `decision = APPROVE_A1`; `execution_plan_sha256`; unchanged A12 `freeze_sha256`; `file_layer_review_sha256` equals the A16 file-layer approval receipt; `assembly_sha256` maps all 24 epoch strings to their actual complete A16 assembly SHAs. It follows all retained A1 prerequisites, not merely A16 freeze. |

The A16 execution plan schema is `clasher.v4.dominance-execution-plan.assembly-a16-v1`. It supplies `amendment16`, `file_layer_delta`, `file_layer_delta_sha256`, `file_layer_review`, `file_layer_review_sha256`, and all 24 epoch records. The delta must state `frozen_a12_pins_sha256`, `amendment_sha256`, `producer_contract_sha256`, `scientific_semantics_changed = false`, `timing_admitted = false`, and the full `new_files_sha256` map. Every epoch's authority must pin that same producer contract and all 24 assembly hashes. The record admission host marker is `ASSEMBLED_TYPED_RECORDS_A16`; the authority schema is `clasher.v4.epoch-assembly-authority.a16-v1`. These file-layer names do not alter the physical single-tenant deciding host policy.

## Actual prospective package pins

The complete evidence now exists. These hashes do not grant freeze or production authority.

- Three whole-match qualification: `408282512b67c0d9a1d90374438331a75bf450264b36bc30000eb9821b73bc6a` (`vectorized-whole-match-qualification-complete-02r1.json`).
- Worker/source closure: `1cdf6d98e09db0cdf104b8653ce1c19d8eecd51fcfb12cb7b331fe590cce8ee9` (`vectorized-scientific-source-closure-r1.json`).
- Queue overlay: `96519baf3d20451c83a373ceb1cf118e8546f8aa3d948a16aaa921cd8078b56e` (`vectorized-queue-overlay-r1.json`).
- Typed producer contract: `3b3ebc8f3e4e3f0eedd0c30de67c853b66b3cdb3c5b85287e6fbd485dea1d431` (`a16-vectorized-producer-contract-r1.json`).
- 157 synthetic test executions: `925eb755c4165803367eb77e58d0cee9bc35a9cc8dbfa5c701ad96bc872b7123` (`a16-final-tests-r1.json`).
- Admission source mutation rerun: `5cdc5fc4427f4e160cfb820f2bf6b51b5cb3987485e846cddead57087d17c70f` (`a16-admission-mutations-r3.json`).
- Actual A16 qualification admission: `08359464ed9abccbe0de2d91e1fd150568cb2460bf89ca4c4b224cdae88c4a8e` (`a16-real-qualification-admission-check-r1.json`).
- Eight-lane benchmark: `8aba8f8b19dbe0e92d99d92d0eff5c378814ee96aa09441b1daf321086e8f8cb` (`decoder-packing-comparison-04r2-complete.json`).

Tests include inherited fixture executions; the count is test executions, not 157 distinct algorithms. The 28 queue/controller/verifier tests are also separately receipted. The admission mutation result covers the declared targeted mutations, not every possible program mutation. The production worker is additionally bound by its separate seven guard tests, the 27-file scientific closure and the three actual full-match qualifications; it was added to this snapshot after the 157-test orchestration run and did not alter any tested admission module. Actual deciding timing and all A1/A2 scientific computation remain unrun.
