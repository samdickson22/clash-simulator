# Independent review: Amendment 16 (mixed record-producer admission), r1

Reviewer: independent (Claude), for coordinator 0523ae6f. Date: 2026-10-09 UTC. Read-only.
- Tests ran from /tmp copies on 127x04, nice 19, plus a cross-check on 127x01.
- Raw-stream byte checks ran on 127x02, nice 19.
- Only this file was written in the repo.

## Verdict

**APPROVED FOR FREEZE at the r1 SHAs, for record-only production release.**

The admission, queue and verifier code does what the draft says. The contract, overlay and worker bindings are sound. I found no path from a vectorized record to timing, D4(b) measured outputs, deciding cells, heldout replay or T6.

Two kinds of required items remain:
- **Before the first vectorized registration:** R16-3, a deployment step that changes no bytes.
- **Before A1:** R16-1 and R16-2, through a follow-up file-layer delta. That delta must not change contract 3b3ebc8f, overlay 96519baf or worker 70e8deaf.

Admission accepts any `FROZEN` A16 freeze whose `producer_contract_sha256` matches. Outputs captured under the r1 release therefore stay admissible after that follow-up, so capture need not wait for it.

## 1. Hashes and delta accounting

All recomputed SHAs match the brief:

| Artifact | SHA |
|---|---|
| package | 3f125d72 |
| draft | 411d147c |
| delta | eafa80ff |
| snapshot manifest | 2ced1534 |
| contract | 3b3ebc8f |
| qualification | 40828251 |
| real admission check | 08359464 |
| A12 draft / pins / freeze | cc2357df / 60f0cb4e / bd5b7643 |
| A15 draft / delta / freeze / file-layer approval | 2d32c0b4 / fac7f864 / 33e3a071 / 5f67971b |

- **A15 bytes.** All **293** A15 files in the delta's `unchanged_a15_files_sha256` equal the frozen A15 snapshot manifest ae9cf92b exactly, and they equal the bytes in `prepared/amendment15-review-r2`.
- **Snapshot.** The A16 snapshot holds 324 files.
  - All 17 new files, 11 test files and 293 unchanged files match their pins.
  - 7 files are not in the delta: the overlay contract doc, the two A16 docs, and 4 queue-review-evidence files. All 7 are in the snapshot manifest. Acceptable.
- **Cosmetic.** `new_files_sha256` repeats 4 unchanged A15 files at their A15 hashes: `assembly_relocation`, `epoch_admission_session`, `queue_audit_io` and `queue_output_audit_v4`. The orchestration's `required` set needs them, so this is harmless. The truly new files number 13.
- **Live tree.** The live l1 tree still holds pre-A16 bytes, as expected. The execution tree must be built from the snapshot.
- **Runtime.** `clasher.vision.l1_v4` is loaded from the bundle `src/`, which is pinned by the bundle manifest at cad13d4f. It is not taken from the repo PYTHONPATH (the 04 repo copy is f8cc93be). Not a gap.

## 2. Record equivalence

**Qualification is checked by raw bytes, with no exclusion.**
- `verify_qualifications` compares every uncompressed line byte for byte (`line != next(right)`).
- It rejects any raw `available_timestamp_ms`.
- It checks `source_seq`, the count and the uncompressed digest.

**I checked independently on 02.** All 27 reference/output streams:
- match their gzip pins;
- are byte-identical after decompression;
- have exactly the planned frame count;
- contain no availability field.

**The frozen scoring never consumes availability.**
- Decoder records contain no availability. Every read path rejects it: the A16 audit, `read_records`, the qualification check and `clock_free_records`.
- Journals are opaque pins and are never opened.
- D4(c) reads only the measured cell's own clocks.

**Equivalence is sample-based, not per-match.**
- No original reference exists for a fresh match. Reviewer mutant R3 confirms this: a vectorized production record that differs but is internally consistent passes the per-match audit.
- Equivalence for production matches therefore rests on two pieces of evidence:
  - A14: 80 matches × 9 branches, raw bytes exact, decoder 4df61ab0 and adapter 82453188;
  - this qualification: 3 matches, 3,656 frames.
- The qualification has only **14 distinct streams**. e01/708's nine branches are byte-identical, e07 has 6 distinct and e15 has 7.
- For a deterministic CPU post-processing swap, the A13/A14 review already judged this adequate.

**The untested variable is production load.**
- The qualification ran on a drained 02.
- R13-3 is mechanically pinned to worker 194dbbe3 (`verify_production_audits`).
- The vectorized worker moves the bottleneck onto the GPU. It is the original worker that changes under packing, not the decoder: cuDNN/TF32 fallback during the model forward pass.
- No evidence yet covers the vectorized worker under production packing. → **R16-1.**

**Downstream detection exists only partly.**
- For measured cells, `dominance_file_verifier_v4_r2` recomputes the bound's opponent counts from the controlled original-driver records over all 64 matches. A divergence would void those cells.
- Body-seal choices and eliminated, unmeasured cells have no such check.

**Vectorized records cannot reach timing or deciding paths.** They enter only the body seal and the optimistic bounds, which is the intended record-only scope.

## 3. Mixed epochs

**Exactly one source per match.**
- `unique_source` requires exactly one of: a retained candidate or a `verified_record_only` task.
- `population` requires 64 unique matches with an explicit `producer_type`, and retained sources must be `original`.
- The queue has one task key per match with a single `current` claim.
- So an original and a vectorized output of the same match cannot both be admitted. Orphaned or voided outputs are never read.

**Nothing is first-wins.** The `available[0]` claim order is a work schedule, not a source choice.

**No switch between A1 and A2.**
- The A1 approval pins the assembly SHAs.
- Each A2 recompute re-requires the live `state.json` to equal the pinned closure snapshot (R8).
- Relocations are bound into each entry.

**Relabelling is caught.** A vectorized output relabelled `original` fails three ways:
- the original task/plan identity check;
- the frozen A15 audit's worker check (194dbbe3);
- the exact-manifest check, because the new fields are present.

## 4. Binding

**The binding chain:**
- The orchestration and the CLI require `authority.vectorized_contract.sha256 == delta.producer_contract_sha256` for all 24 epochs.
- The contract hard-codes A14 8f2d0e07 and pins worker 70e8deaf, the 27-file closure, the qualification 40828251 (plan 0f920ca0) and the single overlay 96519baf.

**Qualification checks:**
- The worker and every closure file must equal the qualification plan pins.
- `complete.capture_worker_sha256` must equal the contract worker.
- `seen == {e7/738, e15/748, e1/708}`.

**Production audit checks:**
- the task worker;
- the host-plan source pins;
- the claim plan, which must be in the contract's `queue_plans`;
- the host plan's `a16_contract_sha256`;
- the release, which binds the overlay, contract and frozen A16 freeze;
- the exact manifest;
- the complete worker.

**Queue and verifier checks:**
- Registration needs the release and the freeze.
- The owner is bound at first claim. PID reuse and takeover are rejected.

**Result:** an unqualified worker version or queue plan cannot produce admissible records. My mutants for a swapped worker pin, a closure swap, a dropped receipt, a dropped 708 cell and an unqualified host worker are all rejected.

**Minor:** the host plan's own `qualification_sha256` is pinned but not compared to the contract. The overlay's qualification is compared, which suffices.

## 5. Controller, queue and verifier

**Atomicity.** Both endpoints share `queue.lock` and `state.json`. The overlay claims only `pending` tasks, so a double-claim mutant (C12) is killed. Activation is not exposed.

**Long-tail void-and-requeue.**
- It runs through the unchanged `match_queue_recovery_intent_v4`. For a vectorized claim, its host-plan check uses the overlay SHA.
- Recovery requires a dead owner, no claim workers, and the launch/intent chain.
- It adopts a verified complete attempt, otherwise it requeues to `pending`. An output without a launch receipt suspends the queue.
- The single `current` claim keeps this exactly-once. The partial output stays orphaned.
- The coordinator's conservation receipt per void is still required.

**Verifier.** The mixed verifier dispatches by `producer_type`.
- Vectorized claims are rechecked under the lock: overlay delta, owner, contract, worker and release.
- Original claims keep the A15 audit.
- Any failure suspends the queue.

**The running original verifier suspends the queue on the first vectorized output.**
- It hits a `host_plans` KeyError or the worker-pin check, then calls `suspend(root)`.
- This fails closed, but it halts the whole fleet. → **R16-3.**

**Advisory.**
- The vectorized controller allows 127x08 after 05:00Z.
- Under the single-tenant policy, its lanes must be drained before any B deciding cell.

## 6. A1 checklist delta (amends A15 r2 §8)

| Step | Change |
|---|---|
| 1 | The A16 `APPROVE_FILE_LAYER_DELTA` binds delta eafa80ff (plus the R16-1/2 follow-up delta) and amendment 411d147c. The A16 freeze carries `producer_contract_sha256` 3b3ebc8f. The plan schema is `assembly-a16-v1`. The execution tree holds the 13 new A16 modules. |
| 2 | Also: all 293 A15 r2 files equal manifest ae9cf92b. |
| 3 | Also: vectorized controllers and the mixed verifier are stopped, and `overlay_authorizations` are frozen in the pinned snapshot. |
| 4 | Original proofs are recomputed by the A15 audit; vectorized proofs by the A16 audit, including the registration-release equality. |
| 5 | Unchanged. **New 5b:** R16-1 passes. |
| 7 | Replace "No vectorized producers" with: each entry carries an explicit `producer_type`; retained ⇒ original; vectorized only from contract 3b3ebc8f, overlay 96519baf and worker 70e8deaf; the manifest's `producer_contract_sha256` equals the delta's. Admit with `ASSEMBLED_TYPED_RECORDS_A16` and the `a16-v1` authority. |
| 8 | Also: for each of the 24 epochs, `authority.vectorized_contract.sha256 == delta.producer_contract_sha256`. |
| 9 | Also: a per-epoch original/vectorized count. Every long-tail void appears in a conservation receipt, and none of its outputs is admitted. |
| 10 | Also: an admission-only dry run with at least one vectorized entry per vectorized host plan. |
| 11 | Also: the vectorized control roots, release, freeze, contract, overlay, A14 proof, and the qualification references and outputs on 02/04 stay reachable and unchanged through A2. |
| 12–16 | Unchanged. |

## 7. Tests and mutants

**Package suite.** 157/157 pass on 04.
- On 01, 143/157 pass. The 14 errors are host-coupled: 11 tests read real retained files that exist only on 04, and 3 controller tests need an owner host on the allow-list. They are not defects.

**Data mutants (17 reviewer tests).** 16 are rejected as intended; one is admitted by design (R3).

| Mutant | Result |
|---|---|
| One-byte vectorized record (value) | rejected |
| One-byte vectorized record (whitespace only) | rejected |
| Same availability field in both reference and output | rejected |
| Worker pin swap | rejected |
| Closure swap | rejected |
| Unqualified host worker | rejected |
| Other-worker `complete` | rejected |
| Original-worker task | rejected |
| Dropped receipt | rejected |
| Dropped 708 cell | rejected |
| Relabelled original | rejected |
| Overlay qualification not in contract | rejected |
| Retained + vectorized queue for one match | rejected |
| Duplicate retained inventories | rejected |
| Duplicate entry | rejected |
| Live ≠ pinned queue state | rejected |
| Self-consistent divergent production record (R3) | **admitted, by design** (see §2) |

**Code mutants (18).**

| Test set | Killed |
|---|---|
| Package suite alone | **7/18** |
| Package suite plus reviewer tests | **13/18** |

- **Killed only by reviewer tests:**
  - C1: the qualification compares parsed JSON instead of bytes;
  - C2: the qualification worker pin;
  - C3: all three cells;
  - C9: the overlay qualification binding;
  - C10: the audit task worker;
  - C11: the audit complete worker.
- **Survivors**, all redundant and backed by downstream checks:
  - C4: availability in the qualification, which the originals never contain;
  - C5: the base task must be original;
  - C8: the original identity check, which the A15 worker pin backs;
  - C14: an original claim finished through the overlay, which owner equality blocks;
  - C16: mixed-verifier original lineage, which the A15 audit backs.
- The package's own receipt reports 20/20 targeted mutants killed. I confirm that is its declared set.

Scripts and logs are in `127x04:/tmp/sdicks02-a16rev/`: `test_reviewer_a16.py`, `rev_mutants.py`, `mut-*.log` and `suite04.log`.

## Required changes (minimal)

**R16-3 — before the first vectorized registration (deployment only, no bytes change).**
- Stop the running original verifier (`STOP_AFTER_CURRENT`).
- Launch `queue_independent_verifier_mixed_v4` with `a16_contract` 3b3ebc8f and every vectorized host plan in `host_plans`.
- Never run both verifiers against the same queue.
- Add "verifier swap" to the finalize order, after operator registration and before controller launch.
- Each newly added vectorized host plan requires a new verifier plan.

**R16-1 — before A1, and run as soon as vectorized lanes are at load.** A vectorized production-condition audit, the vectorized analogue of R13-3:
- at least 4 cells on at least 2 hosts running vectorized lanes;
- at least 4 lanes for at least 90% of samples;
- worker 70e8deaf;
- including e01/708 and e≥15/778 (3939 frames);
- all 9 branches byte-exact against the retained originals.

Enforce it mechanically: when any assembly entry has `producer_type == vectorized`, `verify_all_qualifications` must require these pinned receipts, using the contract worker rather than WORKER.

Any mismatch must:
- suspend the queue;
- revert the hosts to the original worker;
- make the vectorized outputs inadmissible, with an explicit operator void path and a conservation receipt.

This costs minutes of GPU time.

**R16-2 — before A1 (tests only).** Adopt the reviewer tests that kill C1, C2, C3, C9, C10 and C11: R1b, R5, R6b, R7b, R5d and R5e. Re-pin `test_files_sha256` in the follow-up delta.
