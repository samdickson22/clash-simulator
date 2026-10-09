# Independent review: Amendments 13 (whole-match capture) and 14 (vectorized non-clock gate)

Reviewer: independent (Claude), for coordinator 0523ae6f. Date: 2026-10-09 UTC. Read-only. Tests ran on 127x04 under `nice -n 15` from a /tmp copy.

## Verdicts

| Amendment | Verdict |
|---|---|
| **A13** whole-match queue | **APPROVED WITH REQUIRED CHANGES** (R13-1 to R13-4). Production may continue. None of these changes requires stopping the running lanes. |
| **A14** vectorized non-clock gate | **APPROVED WITH REQUIRED CHANGES** (R14-1 to R14-3). The gate may launch once e1 is complete. A pass does not by itself allow a production switch. |
| **A12 A1 stage** | **Cannot consume A13 output as-is.** The frozen admission layer accepts only single-folder `shared-epoch-capture` schemas. See "What A1 needs". |

## Evidence checked

- **Hashes:** the amendment and receipt hashes match the brief.
  - qualification c6367310; plan 11302b9d; queue plan 5d081677; tests r2 def8595f;
  - A14 tests 1ee663a7; plan 91464d55; prepared c74430ea.
  - Worker `whole_match_capture_v4.py` = 194dbbe3. That is the hash pinned in all 1014 queue tasks and in the qualification plan.
- **Tests (re-run by me):**
  - The queue, recovery, controller, integration and qualification suites: **41/41 pass**.
  - `test_vectorized_nonclock_v4`: **16/16 pass**. That is 10 new tests plus 6 inherited `GateTests`.
- **Worker diff:** `whole_match_capture_v4.py` differs from the packed driver `f151e72a` only in these places:
  - the host lists and cutoffs;
  - the episode filter, which selects one validation episode;
  - the shard filter;
  - the manifest and complete schema fields.
  - The frame loop, runtimes, record extraction and serialization are byte-identical.
- **Live queue state** on 127x04, read without taking the lock:
  - Storage is local ext4 on `/mpac`, so `flock` is real.
  - Generation 120; not suspended.
  - Tasks: 925 pending, 16 claimed, 12 captured, **61 blocked**. The 61 blocked tasks are exactly the e06 tasks retained on 02.
  - 4 operator recoveries, all on host 15 after a storage-floor exit 1. Each had its launch file, verified exit and `complete=None`, and was requeued correctly. The second attempt exited 0.

## A13 findings

### Q1. Is split-by-match equivalent to whole-epoch for all epochs and matches?

The structure supports equivalence. The qualification is narrow, but it tests the right direction.

**State is reset per match, by construction.**
- Each match gets a fresh process, a fresh `SharedModel` and nine fresh `PixelPerception` objects.
- In the whole-epoch reference, `PixelPerception.step` also resets everything on an episode change: the ring, tracker, fusion, `last_hand`, `last_elixir`, `sources`, `own_plays` and `ready_ms` (l1_v4 cad13d4f, L328–331).
- `SharedModel.begin_frame()` clears the shared encode and temporal state every frame.
- The models run inference only, in eval mode, so no RNG is involved.
- The decoder record contains only `bodies`, `event_peaks`, `causal_own_hud_cards`, `hud` and source `timestamp_ms`. No availability or fusion output feeds it. `ready_ms` and fusion state cannot leak into the record bytes.

**The cold start is covered in the right direction.**
- Match 1975100708 is cold in both modes, so it needs no test.
- The real risk is the reverse: warm-up or allocator state in the whole-epoch run changing later matches.
- The qualification compares fresh-process e7/738 and e15/748 against warm whole-epoch references, all 9 branches, 11,160 rows, byte-exact. That is a direct test of this risk.

**Two variables remain untested.**
- **Production packing:** 4–6 lanes per A6000 at about 99% utilization and about 42 GB. cuDNN or cuBLAS can fall back to a different algorithm when workspace allocation fails, and TF32 convolutions then round differently.
- **Hosts:** production hosts 09, 13, 14 and 15 versus qualification host 04. There is indirect cross-host evidence: the A14 inputs show the e3 original on 13 and the e20 original on 14 matching vectorized candidates on 02.

R13-3 closes both gaps cheaply.

### Q2. Is the queue sound?

**What holds:**
- **Atomic claims:** sound. All transactions run on 127x04 under an exclusive `flock` on local ext4. State is written by tmp file, fsync, `os.replace` and a directory fsync. A real process-race test exists.
- **No TTL:** confirmed. Heartbeat only stamps a time. No API exists to reclaim or expire a claim. Failures go to `failed_requires_operator_recovery`.
- **Idempotency:** a lost reply is retried with the same durable request ID through the local spool. A request-ID collision is rejected.
- **Crash and void path:** a new attempt writes to a fresh `output_root/task_id/claim_id` directory, and the worker refuses an existing output. A retry therefore cannot append to or mix with partial files. Partial attempts stay on disk.
- **Recovery:** it requires the same host, a dead owner (checked by boot ID and start ticks), and no process whose cmdline contains the claim ID. It adopts a verified complete attempt and never replays one.
- **Binding to producer, source and checkpoint:**
  - The task pins the worker, checkpoint, receipt and frames SHAs.
  - The controller re-hashes them before launch, and the host plan pins all sources.
  - The manifest records the checkpoint, bundle, equality and parent-driver SHAs.
  - `complete.json` records the worker SHA and every file SHA.
  - `verify_complete` re-reads every frame of every branch and its journal.
  - The binding to the claim exists only through the directory path plus `launch.json`, `outcome.json` and the queue state. A1 must re-walk that chain (see below).
- **Inventory dedup:** 522 + 1014 = 1536 = 24 × 64, with no overlap. Of the 128 tasks blocked on 02, 61 are retained (all e06) and 67 were activated (3 e06 plus all 64 e14), giving 583 retained and 953 to capture.
  - The closed-match inventory only accepts a fully decodable gzip whose CRC and EOF check out, where every frame identity matches and the journal is complete.
  - A match truncated by a kill returns `None` and is not retained.
  - The 61 retained matches are **not replayed**: they remain `blocked`.

**Defects:**
- **D13-a (duplicate risk).** `releases/` holds 129 activation releases pinned in the queue plan, including releases for the 61 retained e06 tasks. `activate` accepts any blocked task listed in a pinned release. One operator slip would capture a retained match a second time. → R13-1.
- **D13-b (orphan path).** The controller writes `launch.json` only after `Popen`, because it needs the child's PID and start ticks.
  - If the controller dies between those two steps, the child is not in `active`, so `finally` does not kill it.
  - Once that orphan exits, recovery sees `launch=None`, skips the completeness check and **requeues** the task. If the orphan finished, it leaves a second complete output under a stale claim ID.
  - This does not mix outputs, but it creates an unregistered duplicate. No test covers it. → R13-2.
- **Non-blocking:**
  - `RemotePixelCache.get` checks block length only, not a block hash. This path predates A13 and is shared with the original driver. Service start sets `payloads_verified`.
  - Any single child failure stops the whole host controller and SIGTERMs its sibling lanes, so expect more operator recoveries.

### Q3. Does A13 change anything frozen in A12? Can A13 output serve as A1's inputs?

- **Frozen inputs:** A13 does not change them. The bundle, checkpoints, split, frames, thresholds, the noise and selection rules and the A12 pin files are all untouched. A13 correctly says that capture completion is not body admission.
- **A1 input:** A13 output **cannot serve as A1's "24 complete capture SHAs" as-is**.
  - The A12-pinned `record_capture_admission_v4.py` (9d646763) requires one folder per epoch, with:
    - `complete.json` of schema `shared-epoch-capture-complete.v1` covering all 64 episodes;
    - an exact `shared-epoch-capture.v1` manifest;
    - a `clasher.v4.epoch-fanout-plan.v2` launch plan whose `epoch_assignments` cover that host.
  - `clock_free_body_score_v4.py` (475dcba9) reads `a.capture/'complete.json'` directly.
  - A13 produces per-match folders with schema `whole-match-capture*`. The retained matches from interrupted epochs have no per-epoch `complete.json` at all.
  - Copying files into synthetic `shared-epoch-capture` folders would be the "legacy schema substitution" the adapter forbids. It would also falsely assert a single producer run.

## A14 findings

### Q4. Is the exclusion scoped exactly, and is the population adequate?

**The exclusion is exact.**
- `nonclock_payload` deletes only the root `available_timestamp_ms` and each event's `available_timestamp_ms`, and requires both to be present.
- Everything else is canonical-JSON exact, including tracks, HUD, execution time, sigma, distributions, ordering and numeric types. A NaN anywhere fails closed.

**A vectorized bug cannot hide in the excluded field.**
1. Availability is never part of the decoder records. The raw-record stage (`compare_records`) is byte-exact with **no exclusion**, over all 9 branches for e1 (all 64), e3 (8) and e20 (8). Everything A12 consumes lives in those bytes. Two things are excluded and compared elsewhere: the journals are checked only as opaque identity, and the payload stage has its single exclusion.
2. In `EventFusion` and `RecordedEventFusion`, `available_ms` only fills an output field. It does not gate thresholds, NMS, `recent` or ordering. I verified this in l1_v4 L196–223. The synthetic test with a 100 ms versus 50,000 ms lag confirms it. Even if availability did affect anything, the effect would show up as a non-clock mismatch and the gate would fail closed, not pass.

**The population is adequate for a deterministic code swap.**
- The vectorized decoder changes only post-processing: batched gather and softmax, a single `.tolist()`, and an fp32 scalar threshold. That scalar cannot flip any fp32 score at the 0.1 record threshold.
- `topk` order is unchanged.
- Any reduction-order difference would show up on almost every eventful frame.
- The population covers the cold-start match 708, the longest match (778, 3939 frames) and a dense late epoch.
- The decoder SHA 4df61ab0 and adapter SHA 82453188 are identical across both candidate code roots. Only the orchestration differs for e3.

**Test gaps (minor):**
- No test injects a mutation into a raw record or checks that `compare_records` has no exclusion.
- No test covers `card_distribution` tuple-versus-list equivalence. It is benign under JSON, but it is not stated.
- → R14-3.

### Q5. If A14 passes, what may the vectorized decoder be used for?

**It may be used for:**
- Only **record-only decoder capture** of not-yet-claimed queue matches.
- Only through a **new versioned whole-match worker** whose only diff from 194dbbe3 is swapping `decode_bodies`/`extract_event_records` for `vectorized_decoder_v4` (4df61ab0) plus the adapter (82453188).
- Only through a **new queue plan or tasks**. Existing tasks pin `worker_sha256=194dbbe3`, and the controller enforces it, so a silent switch is impossible. Keep that property.
- Only at clean match boundaries, after R14-2.

**It must stay on the original path:**
- the A12 Tier-1 deciding measurements, which use the controlled 127x08 driver;
- the measured outputs used in D4(b);
- any timing or availability;
- heldout replay;
- T6;
- the A13 qualification references.

**Throughput:** production is GPU-bound at about 99% utilization, so a switch is worth making only if a measured packing benefit exceeds the cost of adding a third producer class to every A1 assembly.

## Required changes

**A13**
- **R13-1.** Make the 61 retained e06 tasks terminal. Either add a queue operation or a pinned receipt that revokes their release files (moving them to `retained_inventory`), or rely on the A1 assembly to reject any match with more than one source. In that case, if a duplicate exists, it must be byte-identical and the retained copy is used.
- **R13-2.** Fix the orphan path for future runs:
  - Before `Popen`, durably write an intent record holding the claim and the command.
  - In recovery, when `launch.json` is absent, inspect `output_root/task_id/claim_id`. If it exists, suspend for manual adjudication instead of requeueing.
  - Add a test for the "child spawned, no launch.json, child completed" case.
  - The 4 recoveries so far are unaffected, because all had launch files.
- **R13-3.** Before A1, run a production-condition audit:
  - Re-capture at least 4 retained (epoch, match) pairs with worker 194dbbe3 on at least 2 lease hosts while lanes are running.
  - Include e01/708 and the longest match of a late dense epoch.
  - Byte-compare them with `qualify_whole_match_v4.compare`.
  - Any mismatch suspends the queue and blocks A1.
- **R13-4.** Add independent verification of every queue output, moving each from `captured_pending_independent_verification` to verified. The verifier must be a separate process from the producer, and it should be part of the A1 assembly.

**A14**
- **R14-1.** A pass grants only the scope given in Q5. The receipt must keep `production_switch_admitted=false`.
- **R14-2.** Before any vectorized production run, the new vectorized whole-match worker must reproduce e7/738, e15/748 and e01/708 byte-exact against the original captures, from its own pinned plan.
- **R14-3.** Add a no-exclusion mutation test for `compare_records`, including an injected `available_timestamp_ms` key in a raw record, which must fail.

## What A1 needs from A13/A14 outputs

1. **24 per-epoch assembly manifests** (new schema, e.g. `clasher.v4.epoch-capture-assembly.v1`). Their SHAs, externally pinned, are the "24 complete capture SHAs" of R-A3. Each manifest contains:
   - the epoch, checkpoint SHA, bundle SHA and equality SHA a32a1602;
   - exactly the 64 validation episodes, with **one source each**;
   - per entry: source kind, host, directory, manifest SHA, the 9 `decoder.jsonl.gz` SHAs, the uncompressed record SHAs and the frame count. Completion-journal SHAs are listed but opaque and never opened.
   - For each source kind, its provenance:
     - **Retained:** the per-host closed-match inventory SHA (04/09/13/14/15 from the queue plan, plus 02 inventory 9a723422), the original launch plan SHA and the driver SHA f151e72a.
     - **Queue:** queue plan 5d081677, task and claim IDs, host plan SHA, `launch.json` SHA, outcome SHA, `complete.json` SHA and worker 194dbbe3.
     - **Vectorized (if any):** additionally the A14 receipt SHA, the R14-2 receipt SHA and the new worker SHA.
2. **A new pinned, tested assembly admission module and a matching body-scorer path.** These replace the single-folder assumptions of `record_capture_admission_v4`/`clock_free_body_score_v4`. They must emit the same admission contract, and scoring, ranking and rules stay unchanged.
   - Because this changes A12 pins at the file layer only, it needs a pin-table delta and the reviewer delta check under B11.
   - Required tests: a missing or duplicate match, a duplicate retained-plus-queue source, a wrong checkpoint, a tampered file, a mixed or unknown schema, and a check that journals are never opened.
3. **Receipts:** R13-3 and R13-4 must pass. All 953 queue tasks must be verified, the 61 must be retained, and the queue must not be suspended.
4. **A14:** if any vectorized match is included, the A14 PASS receipt and R14-2. Otherwise the assembly asserts that it includes no vectorized producer.
