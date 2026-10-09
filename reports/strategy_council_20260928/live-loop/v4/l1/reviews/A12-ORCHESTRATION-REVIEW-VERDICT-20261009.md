# Amendment 12 orchestration review — independent verdict, 2026-10-09 ~02:25Z

Reviewer: independent (owner mode), reporting to coordinator 0523ae6f. Scope: review items 1–3 of `A12-ORCHESTRATION-REVIEW.md`. Read-only on the owner's files. No seal, bound, measurement or heldout access. Tests and mutations ran under `nice` on 127x01, in `/tmp/sdicks02-a12rev`.

## 1. Pins (recomputed by the reviewer)

| Object | SHA256 | Result |
|---|---|---|
| `A12-ORCHESTRATION-REVIEW.md` | `16ede4ad…0706639` | matches |
| `review-package.json` | `443dfaf1…7d1d577d7d1` | matches |
| frozen draft | `cc2357df…1ace6bf2` | unchanged |
| draft pins | `60f0cb4e…7490968c5` | unchanged |
| freeze record | `bd5b7643…a5c7e17bb` | equals the package's `freeze_record_sha256` |
| test receipt (`orchestration-r5.json`) | `11d7aa84…2cad2a1e` | matches |

- **Receipts.** All 18 receipt files match `receipt_files_sha256`.
- **Snapshot.** The r5 snapshot was copied read-only from 127x15. All 45 pinned sources match, and the 380-file PYTHONPATH tree is an exact match with no extra or missing files. The frozen pin `test_measured_dominance_v4.py` (`63e87b15…`) matches the working tree.
- **Working tree (not a defect).** `pin_test_runner.py` exists only in the snapshot. Seven `src/clasher/rl/*` files in the working tree differ from the pinned PYTHONPATH because another thread's uncommitted work is in progress. Execution must therefore run from the pinned, immutable snapshot, never from the working tree. `verify_sources` enforces this: it requires an exact tree match.

**R3/R4/R5 explained.**
- **R3** failed with 1 error. In the full-216 integration test (`BoundFileIntegrationTests`), the fixture's decoder records carried `episode_id='v'` inside 64 matches with other names. `clock_free_records_v4.checked_records` correctly raised `Record/source frame identity changed`.
- **R3→R4** changed only `test_dominance_orchestration_v4.py` (`1cec66d4`→`823e5846`), which sets `episode_id=ep`. No production code changed. I diffed the receipts to confirm this.
- **R4→R5** changed only the launcher (`4c7eafbb`→`ced4f104`) and the worker (`5944dcd0`→`1e3da244`).
- **Meaning.** The R3 failure is a fixture bug, and it is positive evidence that the identity guard fires. It is correctly retained and doesn't matter for soundness.
- **Caveat.** The R5 launcher and worker changes are covered by only three heavily mocked launcher tests. The worker has no tests at all, because it needs a GPU.

## 2. Ordering, isolation and clocks

**Seal → bounds → measurement order holds on every persisted path.**

| Step | What enforces the order |
|---|---|
| Plan approval | `authenticate_plan` requires an `APPROVE_EXECUTION` receipt bound to the plan SHA and the freeze SHA. It hard-codes the draft, pins and freeze SHAs, Tier 2 false and heldout false, and checks the frozen source pins and the whole snapshot and PYTHONPATH tree. |
| `seal_body` | Takes the owner lock, refuses while suspended, refuses if a seal or bounds already exist, and writes the seal exclusively and durably. |
| `build_bounds` | `verify_body` recomputes all 24×9 body cells and requires equality with the stored seal. Bounds are written only after that check. |
| `step` | Every call to `verified_bounds` recomputes the body seal, `verify_all_bound_seals` (D4(a) on all 216 records) and all 216 bounds, then compares them with the stored files. |

Neither CLI stage has a code path that computes bounds before the seal exists. `recompute_bounds` is importable with an arbitrary seal dict, but nothing persists its output.

- **Heldout.** Every payload loop iterates `ready['validation_receipt_sha256']` and requires `split=='validation'`. The worker also requires all 64 matches. I found no path to heldout payloads.
- **Clocks.**
  - Body scoring and ranking use the record view only: `clocks_read=False`, and capture admission skips the `-completion.jsonl` pins without opening them.
  - Bounds use only decoder records and source-frame stamps. `optimistic_counts` rejects any clock field.
  - Completion journals are opened only by `verify_d4` and measured scoring, on the 127x08 replay outputs.

**Carry-forwards from the confirmation review, all CLOSED:**

1. **D4(a) on all 216 records.** This runs on every `build_bounds` and on every controller step. M13 was killed.
2. **The selector consults suspensions.** `refuse_suspended` runs at entry, per history item, and before and after `next_step`. M6, M7 and M8 were killed.
3. **fsync of the suspension file and its directory, before notification.** M9 was killed.
4. **The two missing tests.** The timestamp-regression test (M11 killed) and the non-callable-notifier test (M10 killed) are present.
5. **Spell input pin.** The verifier requires `spells_path`. In admission, that file is written from the capture-admitted `spells` list, so the real binding is `manifest.spells == admitted.spells`. That binding is acceptable.

## 3. Controller elimination logic against the frozen text

- **Strict `<` on the full key.** The pending condition is `rank(b) >= rank(incumbent)`, and the key is (F1, precision, −epoch, threshold). This matches the frozen text exactly. Because the key includes epoch and threshold, distinct cells can never tie, so `<` and `<=` are equivalent. M1 and M2 are therefore equivalent mutants.
- **First-valid accounting.**
  - `authenticated_next` replays the whole measured history against `next_step` on every resume (M26 killed).
  - Voids skip without counting, and the retry requests the same cell.
  - A measurement above its bound halts the controller permanently. That fails closed.
- **Checkpoint.** The checkpoint is written every 30 counted cells, then the controller notifies and continues without pausing. **The content deviates from the frozen text**, which requires all of the following:
  - the label "provisional incumbent — not a selection";
  - the pending cells **with their bound keys** (the code gives only a count);
  - the host-telemetry/void summary.

  The checkpoint is also written when the controller closes at exactly 30, where the frozen text says "without closure". No test covers any of this (M15 survived).
- **Suspension.** It is sticky, with no clearing API, and it fails closed on malformed JSON. The weaknesses:
  - **No re-notification.** If notification fails after the receipt is written, every later step raises `SelectionSuspended` without notifying again, so the coordinator may never learn of the suspension.
  - **No external anchor.** Deleting `incidents/` clears the suspension.
  - **No continuation path.** The frozen continuation, "measure every remaining cell", is not implemented: the controller simply halts. That is conservative, but it needs a reviewed path before it can be used.
- **Restart and idempotency.** The pending request is returned unchanged. A crash after the exit receipt but before `record_outcome` safely gives `WAIT_EXISTING_REQUEST`. **Two holes:**
  1. **Attempt cherry-picking.** Nothing binds a request to exactly one attempt directory or records launches. The launcher's lock sits on `output.parent`, and `record_outcome` accepts any attempt whose `exit.json` carries the request SHA. An operator could therefore launch the same request twice into different directories and record the better run. This breaks "the first valid scheduled measurement is the selection measurement".
  2. **No void path for a hard-killed launcher.** A launcher killed with SIGKILL, or a host reboot, leaves no `exit.json`, so the request stays stuck forever. The only way out is the cherry-pick path above.

  Separately, `admit_measurement` treats post-hoc provenance mismatches as retry-voids rather than halting integrity incidents. Examples are a changed release file and a changed retained verification. Editing a file after looking at the outputs therefore buys a re-roll.
- **No elimination after a fidelity failure.** RecordFidelityFailure writes the suspension, notifies the coordinator and propagates. Every later step refuses before any selector call. CLOSED.

## 4. The 127x08 launcher and telemetry

- **Pins.** Host, `NOT_BEFORE` 05:00Z, UUID, model and driver are checked on every sample. Single-tenancy is real:
  - every `/proc` process of every user with a non-empty cmdline must match a (PID, start-tick) allowlist from a release with no compute exceptions;
  - any compute process that isn't the launcher's own voids the attempt;
  - release expiry, a MemAvailable floor of 24 GB, the 8 GB reserve and a gap of at most 30 s are all checked;
  - the child waits for a stdin handshake before any CUDA import;
  - the launcher terminates only its own Popen child.
- **The GRU.** There is no live GRU check. A live GRU is caught only by the process allowlist, and the release's GRU-exit flag is self-attested. This is acceptable only if the release allowlist is reviewed.
- **Gaps against the frozen policy:**
  1. **GPU memory and utilization are never recorded.** `snapshot` queries only uuid, name and driver. The frozen text requires "nvidia-smi GPU processes/model/driver/memory/utilization".
  2. **The allowlist is probably unworkable as written.** The reviewer sampled 127x08 read-only at ~02:15Z: there were 150 processes (52 root, 45 gdm, 39 sdicks02), and **20 new processes appeared in 90 s**. These included `fleet-console-u` ×6 and sh/wc/tr children, plus sshd and bash from the reviewer's own ssh login. Under this policy, any per-minute helper or any ssh login during a cell voids the attempt, so every cell of roughly 1 GPU-h would void. That is stricter than the frozen text, which forbids compute tenants but discloses OS services. Stricter fails closed, but it may void indefinitely.
  3. **The UUID check is untested.** M20 (UUID check removed) survived.
  4. **Release expiry inside the loop is untested.** M32 survived.
- Current 08 state: GPU `GPU-6cb558a5…`, A6000, 470.256.02, as pinned. The GRU (PID 3548451) holds 39.9 GB.

## 5. Tests and mutations

- **Baseline.** 59/59 pass on 127x01 with Python 3.12.12: the 48 package tests plus the 11 frozen `test_measured_dominance_v4` tests.
- **Mutants.** I made 40 single-site mutants. One was a syntax error and was redone; three are equivalent (M1, M2, M17). **Kill rate: 22/36 non-equivalent (61%).**

| Area | Killed | Survivors |
|---|---|---|
| D4 verifier (M9–M13) | 5/5 | — |
| Strict `<` and key (M3, M29–M31) | 3/4 | M3: dropping precision from the key goes undetected; there's no precision tiebreak test |
| Suspension consult (M6–M8, M39) | 3/4 | M39: tolerating a malformed incident; the test passes for a different reason |
| Host and launcher (M18–M24, M27, M32) | 7/9 | M20 (UUID), M32 (release expiry in the loop) |
| **Ordering guard** (M4, M5, M35, M36) | **1/4** | M4: `build_bounds` skips `verify_body`. M35: `verified_bounds` skips `verify_body`. M36: stored bounds are not compared with the recomputation. The "bounds cannot precede seal" test passes on any FileNotFoundError. |
| Plan gate (M37, M38) | 0/2 | Approval decision and Tier 2/heldout scope; the test is satisfied by other checks |
| Controller bookkeeping (M14–M16, M25, M26) | 1/5 | Bound-order, history-gap and request-SHA checks, and the checkpoint |
| **Measurement admission** (M33, M34) | **0/2** | `dominance_measurement_admission_v4.py` has **no tests at all** |

The ordering logic is correct by inspection. Its weak tests are covered by the redundant recomputation in `verified_bounds`, but M35 shows that redundancy itself is untested.

## Verdicts

### (A) Real clock-free body seal + CPU bounds: AUTHORIZED, conditional on R-A1 to R-A4

The ordering, isolation and clock exclusion are sound, and D4(a) is enforced on all 216 records.

- **R-A1.** Add a JSON round-trip guard to `seal_body`, `verify_body` and `verified_bounds`: compare `json.loads(canonical(x))` (or assert round-trip identity before the exclusive write). Without it, any tuple, Path or Fraction in the readiness or admission dicts would make an exclusively written seal permanently unverifiable. The current tests mock `recompute_body`, so this is unproven.
- **R-A2.** Add tests that kill M4, M35 and M36: a tampered seal or tampered stored bounds must be rejected by `build_bounds` and by `verified_bounds` through recomputation, not by FileNotFoundError. Add a precision tiebreak test for M3, and make the M37 and M39 tests discriminating.
- **R-A3.** Execute only from the immutable, repository-shaped snapshot. The execution plan must pin all 24 externally observed complete capture SHAs; no placeholders. A separately pinned coordinator `APPROVE_EXECUTION` receipt is required. The body seal must wait for all 24 complete captures.
- **R-A4.** Keep the controller root outside the pinned l1 tree. Benchmark one `verify_body` plus `recompute_bounds` pass on CPU before measurements start, because every controller step repeats it.

### (B) Preconditions for the first real deciding measurement on 127x08

1. (A) has completed: the seal, the 216 bounds and `complete.json` exist and pass `verified_bounds` on a fresh process.
2. **Attempt binding.** The request must name one claimed attempt directory under the controller root, claimed exclusively before the child starts. `record_outcome` must accept only that attempt. Every launched attempt is recorded in order. A crashed attempt with no `exit.json` must become void-retained through an explicit receipt, never by launching again.
3. **Integrity incidents halt.** Post-hoc evidence or provenance mismatches in admission, such as a changed release file, attempt or retained verification, must be halting integrity incidents, not retry-voids. Retry-voids are only the frozen causes: contamination, lost telemetry, a hardware, source or input change, or D4(a)/(c).
4. **Telemetry fields.** Telemetry must record GPU memory used and utilization per sample, as the frozen text requires.
5. **Telemetry dry run.** After the GRU exits, run a non-deciding dry run of the monitor on 127x08 for at least one cell's duration, with no GPU deciding work, and get zero contamination. Either stop the per-minute `fleet-console-users` and similar helpers, or have a reviewed policy disclose OS/ssh transients. Neither may admit compute. Operators must not ssh to 127x08 during a cell.
6. **Release receipt.** The coordinator's 127x08 release must follow the actual GRU exit and evidence, after 05:00Z, with the exact PID/start-tick allowlist of OS/control processes and no compute exceptions.
7. **Tests.** Add tests for `dominance_measurement_admission_v4` (killing M33 and M34), plus the UUID check (M20), expiry inside the loop (M32), the bound-order and history checks (M14, M25) and `record_outcome` (M16).
8. **Checkpoint content.** The checkpoint must match the frozen text: the provisional-incumbent label, the pending cells with their bound keys, and the telemetry/void summary, with no checkpoint at closure. Fix this now, so the controller isn't re-pinned mid-run.
9. **Controller CLI and notifier.** Provide a pinned controller CLI and a real coordinator notifier with a stable idempotency key. Re-deliver an existing suspension on `SelectionSuspended`.
10. **Non-deciding GPU smoke run.** Run one smoke cell through the launcher and worker on 127x08, outside the controller root, to prove the handshake, the per-match reset and the manifest. It is not a selection measurement.
11. **Re-pin and review.** The changed sources must be re-pinned, the tests re-run, and a delta check by this reviewer passed.

### (C) Non-blocking notes

- The package's tests ran on 127x15, which is in the roader range of the 2026-10-07 split. `LEASED-HOSTS.md` documents a clasher CPU lease on 127x15; confirm the lease is still current.
- The "measure everything after a D4(b) failure" continuation needs its own reviewed path before it is needed. The current halt is acceptable.
- The suspension has no anchor outside the root. The final verifier should cross-check the coordinator's notification ledger.
- Each step costs O(N²): every resume re-admits all measured cells and reloads 24 checkpoints. Benchmark this before a long run.
- Embed the selector, cleaner and source SHAs in the body seal directly, not only through the plan SHA.
- The worker manifest should record the torch/CUDA versions and the device name. `set_per_process_memory_fraction(.65)` must be identical for the heldout replay.
- Controller closure is not a joint seal. The winner-epoch nine cells, combined calibration, replication and joint T6/T7 seal remain required, as the owner states.
