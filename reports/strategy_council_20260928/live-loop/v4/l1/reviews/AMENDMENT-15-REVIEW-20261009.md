# Independent review: Amendment 15 (epoch assembly file admission, A1/A2 only)

Reviewer: independent (Claude), for coordinator 0523ae6f. Date: 2026-10-09 UTC.
I was read-only on all owner files. The tests and mutations ran on 127x04 from a `/tmp/a15rev` copy of the immutable snapshot, under `nice -n 19`. The e2/e3 layout job running on 04 was not touched.

## Verdict

**APPROVED WITH REQUIRED CHANGES** (RC1–RC4 below). The design is right, and the scoring/bound input equivalence holds. Two admission provenance gaps remain open, and the test suite is too weak to protect the contract. The fixes are small.

Do not issue `APPROVE_FILE_LAYER_DELTA` (the JSON that `assemble_epoch_manifest_v4.py` and `dominance_orchestration_assembly_v4.py` require) until two things are done: RC1–RC4 have landed as a re-pinned delta, and a mechanical delta check confirms that only those changes were made.

## 1. Hashes (recomputed)

| Item | SHA-256 | OK |
|---|---|---|
| Package r1 | deead347…3f | ✔ |
| Draft 15 | 4c7fd730…1a | ✔ |
| Pin delta | e5d46b71…80 | ✔ |
| Snapshot manifest | 833af178…66, 284 files; every file re-hashed, 0 bad, 0 extra | ✔ |
| Test receipt / log | a6d5dba2… / 38e5d59b… | ✔ |
| e1 proof | e307181e… | ✔ |
| A12 draft / pins / freeze | cc2357df / 60f0cb4e / bd5b7643 | ✔ byte-unchanged |
| Frozen admission, scorer and ranking | 9d646763 / 475dcba9 / 3967be35, which equal the A12 pins | ✔ |
| A12 orchestration | 74f8faff | ✔ |
| All 8 new files and 4 test files | match the delta | ✔ |
| PYTHONPATH tree on 04 | 380 files, equal to the receipt | ✔ |

**Discrepancy:** the e1 proof ran with `queue_audit_io_v4.py` **1e8bdb2f**, not the pinned **a8883016**. I diffed the two: the only change is that a8883016 adds `nice -n 19 ionice -c 3` to the remote `cat` command. That is not a semantic change, and e1 was read locally anyway. It is still a pin mismatch (covered by RC4).

## 2. Equivalence

I diffed the old and new scorer and orchestration. Given byte-identical record streams, the frozen functions get identical inputs on both paths:
- `body_frames`, `score_frame`, `summarize`, `rank_body_cells`, `event_predictions` and `bound_cell` are fed the same values.
- The episode order is `sorted(admitted['episodes'])` in both paths. The episodes dict is built the same way, from the readiness receipts.
- The frame set is the same, and `len(records)==len(frames)` is still enforced.
- The branch mapping is `body-{k}` ↔ threshold k/10. My probe D1c, using distinct per-branch content, confirms it.
- `body_threshold=a.body/10` is unchanged, and `spells` is unchanged.
- `json.loads` on bytes and on `gzip 'rt'` lines gives identical objects for ASCII JSON.
- `read_records`' timestamp formula is identical to `frame_times`.

The only changes are additions. Records are re-read with both the compressed and uncompressed SHA verified, which replaces the old `sha(path)` recheck. The new path also rejects reordered, availability-bearing or wrongly stamped rows, which the frozen path did not check. Neither change can alter a score; they can only fail closed.

The `capture_admission` content differs: it gains locations, and `capture_manifest_sha256` is now the assembly SHA. That changes cell and seal digests, not scores. No earlier seal exists, so nothing is affected.

**What the e1 proof shows.** It shows that every inventory record pin equals the original `complete.json` pin, and that all 576 streams re-hash correctly. Combined with the code identity above, that establishes equal scoring inputs for retained e1.

It does **not** exercise `retained_source`, `recompute_assembly` or `authenticate_record_capture` on real data: the launch assignment, driver pin, manifest equality and producer source re-hash are untested on real files. Queue outputs have no old layout to compare against, so their equivalence rests on the A13 qualification plus R13-3.

## 3. Provenance

**These hold (verified by code reading and probes):**
- Queue entries require `verified_record_only`. The audit is fully recomputed from the reopened chain:
  - host plan, controller, launch, outcome, intent, complete, manifest;
  - source re-hash;
  - all 9 streams.
  - The verifier's proof must equal the recomputation, and a stale or orphan claim is rejected.
- The R13-1 terminal 61 are checked by exact count and task-ID equality against a pinned terminal receipt.
- Live queue state must equal the pinned snapshot, and a suspended queue is rejected.
- Retained entries require all of the following:
  - the exact inventory row;
  - the real launch assignment of `--output`;
  - the driver in an allow-list;
  - a re-hash of the producer source;
  - exact manifest equality;
  - all 9 streams.
- 64 entries, no missing or duplicate episode, frame denominators match, and the validation receipt pin is checked.
- Cold-start e01/708 and the dense-longest e≥15/778 are required in R13-3.

**Gaps:**
- **G1 (probe D7, accepted).** `recompute_assembly`, the path admission actually uses, checks retained-plus-queue duplicates in only one direction.
  - A `queue` entry is accepted even when an authority inventory also holds a retained row for the same (epoch, episode).
  - A retained row that exists in two inventories is also accepted, with the manifest choosing between them.
  - `build_epoch` would reject both cases, but admission never recomputes `build_epoch`. This is exactly the "first-wins among two completed sources" that the draft forbids.
- **G2 (probe D8, accepted).** `verify_production_audits` never binds `cell['reference']` to the retained original.
  - An R13-3 audit with `reference == output`, or with any self-chosen reference, passes.
  - R13-3 requires a byte comparison against **retained** captures.

## 4. Clock isolation

- `io.safe` refuses `*-completion.jsonl`.
- Journal SHAs are carried only as opaque values.
- Records containing `available_timestamp_ms`, or a `timestamp_ms` different from the source frame time, are rejected (probes D5a–c).
- Entries carry only SHAs, never clock values. `verified_unix` is dropped before the comparison.
- Telemetry is used only as a load gate and is never stored.
- No path reaches scoring or bounds.
- `verify_all_bound_seals` (D4(a)) is unchanged and is still called over all 216 records. Each bound row binds `capture_complete_sha256` to the assembly SHA, and A1 approval must bind all 24 assembly SHAs.

## 5. A12 compatibility

**Unchanged:**
- ordering, gates, noise, the selection key, Tier 2 (`tier2_enabled is False` is still enforced), B, heldout and T6;
- the body-seal and bound schemas;
- `verify_sources`, the frozen-pin recheck and the PINS/DRAFT/FREEZE constants.

**The file-layer pin change is handled correctly:**
- The A12 bytes are untouched.
- The delta binds `frozen_a12_pins_sha256=60f0cb4e`.
- The orchestration requires the delta, an independent review JSON, the A15 amendment SHA and an A1 approval binding the review and all 24 assemblies.
- The new files are pinned in both the delta and the execution tree.
- `dominance_orchestration_assembly` differs from 74f8faff only in its imports, the approval schema, `verify_file_layer_delta` and `record_rows`. I checked this by diff.

## 6. Tests and mutations

**Baseline:** 69/69 pass on 04, which reproduces the receipt.

**Source mutants, killed by the suite: 9 of 31 (29%).** M32 was an equivalent mutant and is excluded.

The 22 survivors include:
- dropping the `source_seq`, timestamp or availability checks in `read_records`;
- dropping the retained-plus-queue duplicate check, in both admission and build;
- dropping the `verified_record_only`, proof-equality or claim-ID checks in `queue_source`;
- dropping the terminal-ID equality check;
- dropping the R13-3 byte comparison;
- dropping the `actual == entry` check;
- dropping the manifest equality check;
- **wrong branch mapping in admission, the scorer or the bounds** (the fixture uses identical bytes for all 9 branches);
- dropping the all-24 pin check or the spell check;
- **allowing journal opens in `io.safe`**;
- dropping the compressed-SHA or unconsumed-stream check in `io.records`;
- dropping the A1 all-24 binding.

In other words, the actual A15 entry points (`queue_source`, `recompute_assembly`, `build_epoch`, `authenticate_record_capture`, `score_body_records` and the orchestration) are untested.

**Data mutations against the adapters themselves: 15 of 17 behave as required.**

| Mutation | Result |
|---|---|
| Reorder records | rejected |
| Branch swap | rejected |
| Drop a match | rejected |
| Duplicate a match (65 or 64 entries) | rejected |
| Swap producer (same bytes, unassigned directory) | rejected |
| Swap claim | rejected |
| Unverified output | rejected |
| Proof mismatch | rejected |
| Clock field / shifted stamp / journal open | rejected |
| D7 | **accepted** (gap G1) |
| D8 | **accepted** (gap G2) |

Scripts and results are in `127x04:/tmp/a15rev/{mutants,probes}.{py,json}`.

## Required changes (minimal)

- **RC1.** In `recompute_assembly`, for each episode, require exactly one candidate across all authority inventories (rows matching epoch and episode) plus the queue tasks with status `verified_record_only`. The entry kind must match that candidate. Alternatively, require `manifest == build_epoch(...)`. Add the D7 test.
- **RC2.** In `verify_production_audits`, add the following, plus the D8 test:
  - Require `reference != output`.
  - For every branch, require `reference_gzip_sha256` to equal the authority inventory row's `files_sha256` for that (epoch, episode), or the pinned original `complete.json`.
  - Require each reference to be the retained original.
- **RC3.** Add tests that kill at least these mutants:
  - M01–M03, M06–M09, M12, M14, M16, M17, M20, M22–M29 and M31.
  - The fixtures must use distinct bytes per branch.
  - At least one end-to-end synthetic `authenticate_record_capture` → `score_body_records` run, compared against the frozen `clock_free_body_score_v4` on an equivalent old-layout directory, with identical `per_match` and `micro`.
- **RC4.** Re-issue the delta, snapshot and test receipt. Re-run the e1–e3 layout proofs under the final pinned sources, including `queue_audit_io` a8883016 or its successor.

**Advisory (non-blocking):**
- **Cost.** Every one of the 216 body cells, plus 216 more in `verify_body`, plus 24 in `epoch_inputs`, re-authenticates a full epoch: about 2.8 GB, roughly 2 minutes locally (e1), plus about 600 ssh sessions per cell to lease hosts. That adds up to about a day of overhead inside "timed" A2, and any ssh hiccup aborts the whole seal. Measure this before A1, or memoize admission per epoch inside the process.
- **Epoch key.** Assert `admitted['epoch'] == e` in the orchestration. This gap predates A15.
- **Defense in depth.** Assert `claim['task_id'] == state key` in `queue_source`.
- **Queue state.** The live `state.json` must stay byte-identical through A2, so the controllers must stay stopped.
- **02 availability.** The 61 retained e06 matches on 02 need 02 to be reachable for A1 and A2. It is reachable now.

## Exact A1 checklist

1. The A15 review r2 approves RC1–RC4. The re-pinned delta passes the mechanical check. The `APPROVE_FILE_LAYER_DELTA` JSON binds the delta SHA and the A15 SHA.
2. The A12 draft, pins and freeze, and the frozen 9d646763/475dcba9/3967be35/74f8faff files, are byte-identical.
3. The queue is closed:
   - 1014 tasks: 953 `verified_record_only` and 61 `retained_inventory`;
   - not suspended;
   - the live state equals the pinned snapshot;
   - the terminal receipt d9301fce (count 61, inventory 9a723422) matches;
   - inventories = the queue-plan retained pins ∪ 9a723422.
4. All 953 independent proofs are recomputed by the assembly, not merely read as status.
5. R13-3 passes, with the RC2 bindings:
   - at least 4 whole-match cells, on at least 2 of the lease hosts 09/13/14/15, under at least 4 lanes for at least 90% of samples;
   - worker 194dbbe3;
   - includes e01/708 and e≥15/778 (3939 frames);
   - byte-exact against retained originals, all 9 branches;
   - any mismatch suspends the queue and blocks A1.
6. The retained-layout equivalence proofs for e1, e2 and e3 pass under the final pins.
7. All 24 assembly manifests are built by `build_epoch` and re-admitted by `authenticate_record_capture`:
   - 64 entries each, 9 branches each, one source per match, no vectorized or unknown producers;
   - one spell routing per epoch, equal to the runtime routing.
8. The 583 retained + 953 queue = 1536 = 24 × 64 identity holds, with no overlap.
9. A real dry run of `retained_source` on at least one retained match per producer host and plan has been exercised before the seal: launch assignment, driver allow-list, source re-hash and manifest.
10. The immutable execution snapshot exists: source tree, PYTHONPATH tree, external scientific files, `pythonpath` environment.
11. `coordinator-approval-A1.json` binds:
    - `execution_plan_sha256` and `freeze_sha256`;
    - `file_layer_review_sha256`;
    - the `assembly_sha256` map of all 24 assemblies.
12. Only then: write the body seal (A1). Then run A2's timed bounds, with D4(a) over all 216 records.
13. B and the 11 preconditions stay blocked. The deciding controller must not use these manifests.
