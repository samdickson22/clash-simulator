# Independent delta review: Amendment 15 r2 (RC1–RC4, relocation, memoized admission)

Reviewer: independent (Claude), for coordinator 0523ae6f. Date: 2026-10-09 UTC.

I was read-only on every owner file; this file is my only write. I ran tests and probes on 127x04 from `/tmp/a15r2rev`, a copy of the immutable r2 snapshot, under `nice -n 19 ionice -c3`. I did not start, stop or write to the queue, the verifier or the 03 archive service. The only reads from 03 and the lease hosts were the small reads of two relocated matches (§4).

## Verdict

**APPROVED FOR FREEZE at the r2 SHAs.** No required changes.

- RC1–RC4 are closed in code and tests.
- Relocation cannot admit bytes that differ from the original producer output.
- The memoized admission is non-weakening for every byte that feeds a body score or a bound.

The advisories below are non-blocking. The final A1 checklist (§8) replaces the r1 checklist.

**Freeze-record condition (documentation only; the r2 bytes don't change).** The freeze record must state the two documented memo exceptions in §5.

## 1. Bytes

**SHAs.** All recomputed SHAs match:

| Item | SHA-256 |
|---|---|
| Package r2 | c66fd6f4… |
| Draft r2 | 2d32c0b4… |
| Delta | fac7f864… |
| Changelog | d3518901… |
| Mechanical source delta | 743aaf98… |
| Snapshot manifest | ae9cf92b… |
| Tests receipt / log | 5ebb2e83… / 16290b92… |
| Runtime tree | 64a0462f… |
| Mutations result / log | 29b26107… / f1fd2eba… |
| e1/e2/e3 layout proofs | 40a4d572 / b6b896e0 / 4ecdc562 |
| e1/e2/e3 layout plans | 348db406 / bceccd4a / 1ffff084 |
| Real-scorer proof | c2203627… |
| Retained-source proofs | 14c938c1 / 9006d9e6 |

**Snapshot.** I re-hashed all 293 files: 0 bad, 0 missing, 0 extra.

**r1 and A12 are unchanged.**
- r1 package deead347, draft 4c7fd730, delta e5d46b71, snapshot manifest 833af178 and review 716989da are byte-identical.
- The live tree still holds the r1 bytes for the six changed modules and does not yet contain the two new ones.
- A12 draft cc2357df, pins 60f0cb4e and freeze bd5b7643 have no git changes.
- These files match the A12 pins in the live tree, the r1 snapshot and the r2 snapshot:
  - record_capture_admission 9d646763
  - clock_free_body_score 475dcba9
  - ranking 3967be35
  - dominance_orchestration 74f8faff
  - measured_dominance df273c95

**The delta accounts for every difference.** `diff -r` of the r1 and r2 snapshots shows exactly these differences, which equal the 15-row mechanical delta and the delta JSON:
- 6 changed modules;
- 2 new modules (relocation, session);
- 6 new tests and 1 changed test;
- the review documents swapped.

I diffed each changed module, and every hunk maps to a changelog bullet:

| Module | Change | Changelog bullet |
|---|---|---|
| `queue_audit_io` | adds HOSTS 03, ROOTS `/mpac/sdicks02/v4-archive/`, and the evidence ledger | relocation, admission reuse |
| `queue_output_audit` | adds the `transport=` parameter, `note_local`, and the intent rule | relocation, status-controller intent |
| `epoch_assembly` | adds `unique_source`, RC2 bindings, relocation and task-key checks | RC1, RC2, relocation, advisories |
| `epoch_assembly_admission` | adds the session wrapper and notes the model manifest | admission reuse |
| `clock_free_body_score_assembly` | changes only its source list | RC4 |
| `dominance_orchestration_assembly` | adds the required set, the epoch assert and the session | RC4, admission reuse, advisories |

**One understated item.** The intent rule changed from the substring `'intent' in name` to an explicit set: {`match_queue_controller_intent_v4.py`, `match_queue_controller_status_v4.py`}. Only the plain and intent controllers appear in the current host plans, so this changes nothing today.

## 2. RC closure

**RC1: closed.**
- `unique_source` counts candidates across every pinned inventory plus `verified_record_only` and requires exactly one. The entry kind and inventory must match that candidate.
- `build_epoch` also rejects a retained source while a queue task is still in flight.
- Mutant N01 (drop the cardinality check) is **killed** by 3 tests. M06 and M15 are killed.
- My D7 probe (a queue entry plus a retained row) is rejected.

**RC2: closed.**
- Every R13-3 cell must have `reference != output`, using normalized paths.
- Each cell needs a unique retained original, with `reference_origin` equal to {host, directory, inventory, manifest}.
- All 9 `reference_gzip_sha256` values must equal the inventory hashes.
- A cross-host reference needs a pinned copy receipt.
- Mutants N03, N04 and N05 are **killed**.
- My D8 probes are rejected: plain self-comparison, and `output+'/.'`.
- Copy-receipt branch probes:
  - a correct receipt is accepted;
  - a missing receipt, wrong origin, wrong bytes or a differing copy is rejected.

**RC3: closed.**
- On 04 I reproduced 184/186 tests. The other 2 are A14 prerequisite transport tests: `vectorized_gate_io`'s owned-root guard correctly rejects `/tmp`.
- On 127x01 the suite fails 35, because tests assume 127x04 is the local host (advisory A6).
- I re-ran 7 RC3 source mutants of my own (R14, R22, R25, R28, R30, R31, R06). 6 were killed. R06 is masked by `queue_source`, so it is equivalent at the system level.
- Fixtures use distinct bytes per branch.
- Real e3/738 has byte-identical branch files (1 distinct hash over 9, from pre-NMS storage). The real-data equality therefore exercises the threshold mapping, while the file mapping is covered synthetically (R22 and R28 killed).

**RC4: closed.**
- The delta pins `queue_audit_io` 1df4d0c1 and all 10 new or changed modules.
- The e1/e2/e3 layout plans pin exactly the r2 bytes for all 7 sources, and each proof embeds its plan SHA.

## 3. My mutants on r2-only code

32 non-equivalent targets: **15 killed, 17 survived.** Results are in `127x04:/tmp/a15r2rev/mutants-reviewer.json` (be99db53).

**Survivors masked by a stronger downstream check (equivalent at the system level):**
- N02: retained inventory choice;
- N08: unique original, masked by assembly `unique_source`;
- N09, N10, N11: relocation pointer, proof binding, unexpected-relocation guard. `RelocatedIO` pins equal to the proof plus recompute == proof preserve byte identity;
- N14, N15: receipt complete and source fields. The membership equality includes `complete.json`, and routing uses `proof`/`claim`;
- N17: an unpinned member. The audit reads only pinned members.

**Untested but verified by my own probes (advisory A1):**
- N06, N07: copy-receipt checks;
- N22: session key sensitivity;
- **N24, N25, N26: the evidence ledger**, which is the memo's core invariant;
- N28: epoch assert;
- N30: ROOTS;
- N31: session wiring.

## 4. Relocation

**Byte identity is required.** A relocated copy cannot be admitted without byte identity.
- `RelocatedIO` requires the following, all bound to the independently pinned original proof:
  - the receipt `files_sha256` equals {9 records, 9 opaque journals, `complete`, `manifest`};
  - an exact destination: 03 or legacy-04 prefix + source host/task/claim;
  - claim, task, source and complete bindings.
- Every routed read is hash-checked against those pins.
- The full audit is recomputed through the transport and must equal the original proof. The original-location producer metadata and sources are still read where they live.

**Real-data probe.** I ran one 03-relocated output (e15/1258) and one legacy-04 output (e15/778) (`probe-relocation.json` 02be565f):
- the recomputed audit equals the original proof;
- records are read only from the archive host;
- journals are never opened;
- a tampered receipt and a non-identical copy are both refused.

**Delete ordering is safe.** The leased copy can't be deleted before the archive copy and receipt are durable.
- The 03 transport (c1df0362, outside the delta) runs in this order:
  1. rsync, then SHA every member on 03;
  2. fsync the files and every directory up to the root;
  3. write the receipt exclusively, then `fsync_dir`;
  4. update the state pointer under `queue.lock` (rename + `fsync_dir`);
  5. only then retire the streams. Retirement re-hashes the remaining members first.
- Legacy-04 (e64cfcaf) follows the same order. It does not fsync `dest_root/host`, but ext4 journal ordering makes that moot (nit).
- If a crash loses a receipt, admission fails closed. Nothing is substituted silently.

**The mapping is tamper-evident.** These links chain to the A1 approval:
- the state's `retention` pointer {path, sha} must equal `authority.relocations[claim]`;
- the state is pinned by `queue_state_sha256`;
- the authority is pinned by the execution plan, which A1 approval binds;
- the receipt is pinned by SHA;
- the destination roots are hard-coded in pinned source.

## 5. Memoized admission

**Verdict: non-weakening for every byte that feeds a score or a bound.**

**Bytes changing between full authentication and use.**
- Records are SHA-checked, compressed and uncompressed, on every read, and re-read after scoring.
- Truth files are re-hashed by the frozen scorer.
- Every other evidence file opened during full authentication is re-hashed at each reuse, batched per host:
  - local pins, JSON, source hashes and records go through `io.note`;
  - the authority, assembly, closed queue and live state are rechecked separately;
  - the module source is rechecked as well.
- Full authentication is a deterministic function of those bytes. I found no threads (`ContextVar` isn't propagated), no clock reads and no directory listings.
- So the result equals a fresh authentication.

**Real-data probe.** I ran a retained e01 match local to 04 (`probe-session.json` 47159f63):
- the ledger held 29 code files, 9 records, the manifest, frames, inventory and launch plan, and no journal;
- a byte change in the inventory, launch plan or queue state, or a forged receipt, each aborted reuse.

**Two documented exceptions, neither consumed by any score or bound:**
- **(a) Remote producer `epoch-N.pt` copies are skipped on reuse.** Checkpoint identity is still re-established each cell by frozen `validate_portable`, which re-hashes and loads all 24 local checkpoints. `queue_source` requires that SHA.
- **(b) The equality artifact checked by `authorize()` is not in the ledger.**

**Stale or forged receipts can't be reused.**
- Entries are in-memory only, and each process uses a new `uuid` directory created with `exist_ok=False`.
- A persisted receipt is only compared against the in-memory copy and is never loaded as authority.
- A second key for the same epoch fails on the exclusive receipt.
- `admitted['epoch']` gives the receipt name.

**Crash and restart are safe.**
- A restart re-authenticates fully.
- Orphan session directories are never read.
- The seal and the bounds remain exclusive.

## 6. Clocks, heldout, selection

Nothing new is on these paths.
- The session receipt stores `full_authentication_seconds`, the process wall time. It is never returned, sealed or bound.
- The relocation receipt's `verified_utc_unix` is opaque.
- `io.safe` still refuses journals on every root, including the archive.
- Vectorized producers are still rejected.

## 7. Advisories (non-blocking)

- **A1. Add tests for the untested r2-only checks.** Cover the ledger (N24–N26), copy receipts, the session key, and an epoch assert in `recompute_body`. Keep these as a separately pinned post-freeze test addition.
- **A2. Liveness.**
  - `io.HOSTS` excludes **127x01**, the current hub, so A1/A2 must run on 04 or 03.
  - Every locally pinned admission input must be under `io.ROOTS`. Otherwise the first `get()` fails closed (my probe shows this).
- **A3. The body-seal epoch label is unchecked.**
  - r2 asserts `admitted['epoch']==e` only for bounds, not in `recompute_body`.
  - A plan that swapped e↔assembly would seal mislabeled data, which A2 would only catch afterwards.
  - Covered by A1 checklist step 8.
- **A4. The R13-3 self-comparison check is textual.** A hardlink or directory symlink on the audit host is not detected. Reference bytes are hash-bound to the original, so the residual risk is only "output not produced by the worker".
- **A5. The running verifier uses r1 code** (audit b8ff7eee, io a8883016/1e8bdb2f). Admission recomputes everything with r2, so a status-controller launch without an intent would fail closed at A1. There are 0 today.
- **A6. The suite is not hermetic.** It requires 127x04 and an owned root.
- **A7. ssh cost.** Each cell still does about 128 ssh record reads, and one hiccup aborts the stage (r1 cost advisory).

## 8. Final exact A1 checklist (replaces r1's)

1. **File-layer approval.**
   - The r2 freeze record states the §5 exceptions.
   - `APPROVE_FILE_LAYER_DELTA` binds `delta_sha256=fac7f864…` and `amendment_sha256=2d32c0b4…`.
   - The execution tree contains the r2 bytes of all 10 delta modules, not the r1 live copies.
2. **Frozen bytes.** A12 cc2357df / 60f0cb4e / bd5b7643 and 9d646763 / 475dcba9 / 3967be35 / 74f8faff / df273c95 are byte-identical.
3. **Queue closed.**
   - 1014 tasks: 953 `verified_record_only` and 61 `retained_inventory`.
   - Not suspended, and the controllers and transports are stopped.
   - The live state equals the pinned snapshot.
   - The terminal receipt matches: d9301fce, count 61, inventory 9a723422.
   - Inventories = the queue-plan pins ∪ 9a723422.
4. **All 953 proofs are recomputed by r2 admission.** This includes every relocated entry through `RelocatedIO`, with `authority.relocations` equal to the state's `retention` pointers.
5. **R13-3 passes with the RC2 bindings.**
   - At least 4 cells on at least 2 lease hosts, with at least 4 lanes for at least 90% of samples.
   - Worker 194dbbe3.
   - Includes e01/708 and e≥15/778 (3939 frames).
   - All 9 branches are byte-exact against the retained originals.
   - Each non-in-place reference has a pinned `audit_reference_copies` receipt.
   - Each output is a distinct worker-written directory (checked on the host).
   - Any mismatch suspends the queue and blocks A1.
6. **Layout proofs.** The r2 e1/e2/e3 layout proofs pass (40a4d572 / b6b896e0 / 4ecdc562).
7. **Assemblies.**
   - All 24 manifests are built by `build_epoch` and re-admitted by `authenticate_record_capture`.
   - 64 entries each, 9 branches each, one source per match.
   - No vectorized or unknown producers.
   - One spell routing, equal to the runtime routing.
8. **Epoch keys.** For each e in 1..24, the manifest `epoch == e`, and `authority.assemblies[e] == plan.epochs[e].complete_sha256 == approval.assembly_sha256[e]`.
9. **Population identity.** 583 retained + 953 queue = 1536 = 24 × 64, with no overlap.
10. **Retained-source dry runs** cover every producer host and plan. 19 are done; rerun if any plan changes.
11. **Sources stay reachable and unchanged through A2.**
    - The retained originals and archive copies;
    - the producer control roots and producer bundles on the lease hosts (pins, `.pt`, frames, receipts, code);
    - hosts 02, 03, 04, 08, 09, 13, 14 and 15.
12. **Execution host and paths.**
    - The execution host is in `io.HOSTS` (04 or 03, **not** 01).
    - All locally pinned inputs are under `io.ROOTS`.
    - A pre-seal admission-only session dry run passes: one epoch, two calls, no scoring.
13. **Immutable execution snapshot:** source tree, PYTHONPATH tree, external scientific files, `pythonpath` env.
14. **`coordinator-approval-A1.json`** binds:
    - `execution_plan_sha256` and `freeze_sha256`;
    - `file_layer_review_sha256`;
    - all 24 `assembly_sha256`.
15. **Then the A1 body seal.** Run it in one process with a fresh session. Next comes the A2 timed bounds, with D4(a) over all 216 records.
16. **B stays blocked.** B and its 11 preconditions remain blocked. Session receipts are never admission evidence.

Scripts and results are in `127x04:/tmp/a15r2rev/`:
- baseline.log bc026c6e
- mutants-reviewer.json be99db53
- mutants-reviewer-r.json 33d7be02
- probe-session.json 47159f63
- probe-relocation.json 02be565f
- probe-rc2.json 53acc64b

## Summary (under 250 words)

A15 r2 is **APPROVED FOR FREEZE** at package c66fd6f4, draft 2d32c0b4 and delta fac7f864. No changes are required.

**Bytes.** All hashes match. The r1 and A12 bytes are unchanged, and the snapshot diff equals the delta.

**RC1–RC4 are closed:**
- the one-source cardinality check is enforced;
- R13-3 references are hash-bound to the retained original, and self-comparison is rejected;
- the r1 RC3 mutants are killed, and my 6 re-run RC3 mutants are killed apart from one masked equivalent;
- the layout proofs ran under the final pins.

**Relocation** admits only bytes whose hashes equal the original independent proof. I recomputed one real 03 output and one real legacy-04 output, and both equal their proofs. Deletion happens only after a fsynced, verified archive copy, a durable receipt and a durable state pointer.

**Memoized admission is non-weakening for every byte that feeds a score or a bound:**
- records are hash-checked on every read;
- all other opened evidence is re-hashed at each reuse;
- receipts are process-local and never trusted from JSON;
- a restart re-authenticates fully.

A real-data probe confirmed that it detects changes. Two exceptions don't feed any score or bound: remote producer `.pt` copies and the equality artifact. The freeze record must document them.

**Nothing new reaches clocks, heldout data or selection.**

**Advisories:**
- 17 of my 32 new-code mutants survive. Most are masked, and I verified the rest by probes.
- A1/A2 must run on 04 or 03, because 01 is not in `io.HOSTS`.
- The body-seal epoch-label check must be done in the A1 checklist.

The new A1 checklist has 16 steps.
