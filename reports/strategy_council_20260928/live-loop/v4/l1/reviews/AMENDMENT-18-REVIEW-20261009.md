# Amendment 18 review: owned evidence and retained recovery (r1)

Reviewer: independent Claude reviewer for coordinator 0523ae6f, 2026-10-09. The review was read-only. Tests, probes and mutants ran on 127x04 (idle, no console users) under nice 19 in `/tmp/sdicks02-a18rev/`, using `/mpac/sdicks02/envs/clasher-gpu/bin/python`. 03 was used only for four small `cat` reads of routed R16 reports. Nothing ran on 05 beyond reading the repo.

**Verdict: REQUIRED CHANGES (minimal).** There are two small changes, R18-1 and R18-2. A diff-only coordinator check of r2 is enough, as with A17 r3; no further full review is needed.

## 1. Bytes

| Item | Recomputed SHA | Result |
|---|---|---|
| Review package | 34e0c6b2… | match |
| Draft | 329b3c91… | match |
| Delta | 89faa69f… | match |
| Snapshot manifest | 9d39051f… | match |
| Diff / test receipt | a9222b1c… / b3cc7d6d… | match |
| Coverage r2 / actual checks | 2068464c… / 11b4e775… | match, both locally and on 04 |
| Recovery closure / activation | d15c753c… / 7ecdc1fb… | match |
| Authority (04 packet) | 9ba1cc02… | equals `authority_sha256` in coverage and actual checks |

- **Snapshot.** All 346 files were re-hashed, both in `prepared/amendment18-review-r1` and in the 04 runtime snapshot: 0 bad, 0 missing, 0 extra.
- **A17 members.** `unchanged-a17-files.json` is byte-identical to the A17 r3 snapshot manifest (ecb9359c). All 334 members are unchanged in the A18 snapshot.
- **Frozen records.** These are unmodified in git:
  - A12 freeze bd5b7643;
  - A15 freeze 33e3a071 and approval 5f67971b;
  - A16 freeze cae72ebd, supplement 3e5c04b8, approval 730c86e8 and release 0dd2f265;
  - A17 freeze cdfc5573, §5 check 90728bde, conditional approval 64b1ebe4 and condition-satisfied 05fa63c8.
- **A17 freeze chain.** The A17 r3 draft b1a3e249, delta de2b2877 and package 5e20d9cc match the A17 freeze record.
- **Delta completeness.**
  - The snapshot adds exactly the 12 files listed in `changed_files`, and `a18.diff` covers all 12.
  - The delta's `new_files_sha256` has 27 rows: those 12 plus 15 A17 members re-listed with identical hashes. The overlap is harmless.
  - The A17→A18 module diff only adds routing, retirement, the recovery merge, the R16 call and the new bindings. No scoring, decoder, tie, bound or population logic changed.
- **Live tree.** The live repo's `queue_audit_io_v4.py` differs from the pinned bytes. A1 must therefore run from the installed snapshot, never the live tree (checklist item 3).

## 2. Single source per match

**Population.** The actual authority holds these inventories:
- 404 leased rows (09: 138, 13: 96, 15: 88, 14: 82);
- 118 rows on 04;
- 61 rows on 02, all in inventory 9a723422.

The original queue has 953 `verified_record_only` tasks and 61 `retained_inventory` tasks. **No current claim is on 02.** The current claims are on 04 (162), 08 (160), and 631 on 09/13/14/15, which are A15-relocated. The recovery namespace has 61 verified vectorized tasks (09: 17, 13: 15, 14: 12, 15: 17) and 953 `blocked` tasks.

**Retired 02 sources can't be admitted, even if 02 returns.** Each path that could admit one has its own guard:
- `retained_candidates` excludes the 61 rows;
- `retained_source` refuses host 02 (line 65);
- `Routes` refuses a 02 source, and `route()` refuses any read from 02;
- `merged_state` refuses a recovery owner on 02;
- the inventory set is fixed to the plan pins plus 9a723422;
- both live states are hash-pinned.

My probes P1a–c pass.

**Recovery is bound to the A16 producer contract.**
- `queue_source` runs `verify_task_overlay` and `verify_owner_authorization` against frozen contract 3b3ebc8f.
- The overlay must be listed in the contract's `queue_plans`.
- The registration must equal the production release.
- The full A16 independent proof is recomputed and checked for equality.
- Overlay-authorization collisions are refused.

**No first-wins in admission.** These all require exactly one match:
- `unique_source`, `population` (64 unique episodes), inventory rows, base tasks, assignments, R13/R16 references and the routing source key.

My probes P2a–c pass.

**One latent last-wins: R18-1.**
- `Routes` doesn't refuse two source members that share one `destination_path`.
- Routed `hashes()` groups pins by destination with `groups[h][n]=d`, so the last pin overwrites the first and only one is verified.
- My probe P2d confirms it: two sources pinned X and Y route to one destination, and only Y is checked.
- `read` and `records` still check each member's pin, so the exposure is confined to hash-only members, such as producer code pins.
- The actual manifest efff5b98 has 13,102 members and **0 duplicate destinations**, so the pinned data isn't affected. It is still a first-wins pattern that the coordinator ruled out.

## 3. Relocation

**Each route is proved.** A route must be proved by its exact pinned copy receipt: same source → destination mapping and same hash, with checksum, fsync and no source deletion. Destinations must be on 03 under `/v4-archive/verified-capture-20261009-r1/`.

**Admitted bytes are the original bytes.**
- When the caller supplies the original pin, `route()` must match it exactly.
- When the caller supplies none (controller, launch and outcome reads), the read is still bound to the copy-receipt pin.
- The recomputed A15/A16 proof is then compared for equality with the original proof.
- Retained members are pinned by the inventory's manifest and record hashes and by the launch's `source_files`.

**One-byte changes are rejected.** In probe P3, a real one-byte change in a routed JSON, code or gzip member was rejected in all 4 cases, including the unpinned read with JSON that is still valid.

**Leased copies are never required.**
- `io.HOSTS` plus `LEASED` mean that any 09/13/14/15 read without a route raises, and only 03/04/08 pass through.
- The A15 `RelocatedIO` control-file reads also go through the patched transport.
- Every R13 and R16 read on a lease host goes through a route.
- No module in the admission chain binds `io.read`, `io.hashes` or `io.records` by name or calls ssh directly.
- Journal sources are refused by `io.safe` at route construction.

## 4. R16-1 enforcement

`verify_all_qualifications` runs R16, then R13, then A17, at both `build_epoch` and recompute.

`verify_r16` requires all of the following:
- `exact_selection`, which needs pins 151771eb / eb5d996b / a0f70344 and assertions enabled, and must reproduce the selection;
- exactly 4 reports on 4 distinct lease hosts, each with `pass_nonclock` true, timing and selection false, the original worker 194dbbe3, and the exact selected row and plan;
- the claim, proof and reference-copy chain, including any A15 relocation;
- all 9 raw streams compared byte for byte;
- `verify_dense`, covering e20/778 on 04, driver fe2009fb, the 27-file closure, qualifier eba6349d, ≥4 lanes in ≥90% of samples, and the retained-original copy.

**Probe P4 refuses** each of the following: a missing PASS, a missing report, a duplicate claim, a stress failure, and a non-original output.

**Real files on 04 and 03:**
- `evaluate()` reproduces selection eb5d996b: 589 eligible, 54 excluded, epochs 17/8/16/9.
- All 4 routed PASS reports have matching hashes and `pass_nonclock=true`.
- Dense report d75ed9c6 has `min_lanes=5`.

## 5. Clocks, heldout, selection

Nothing new reaches them.
- Journals are refused by `safe()` and can't enter the route map.
- Records with `available_timestamp_ms` are refused.
- The R16 selector reads only collection, launch, proof and telemetry metadata.
- There is no heldout path, and all 64 validation matches, including 1975100708, stay in every epoch.
- `timing_admitted=false` throughout.

## 6. Tests and mutants

**Suites.** The baseline is 402 executions OK on 04. That is the A18 suite, the reviewer A16 and A17 suites, and the A16/A17 suites, which is a broader collection than the receipt's 281. The reviewer probes are `test_rev_a18.py` (e23fae36), 20 cases; 19 pass, and P2d fails as designed (R18-1).

**Test-file defect.** `unittest.main()` sits mid-file in `test_a18_file_layer.py`. Running the file directly therefore runs only 30 of its 47 cases.

**Code mutants (mutants-out 62da9a9b, plus the M4 rerun):**

| Mutant | Existing suite | Reviewer probes |
|---|---|---|
| M1 retained 02 source admitted | survives | killed |
| M2 retired filter removed | survives | killed |
| M3 first-wins in `unique_source` | survives | killed |
| M4 route drops receipt pin | survives | killed (P3 valid-JSON one-byte) |
| M5 R16 PASS ignored | survives | killed |
| M6 leased fallback | killed | killed |
| M7 02 route source accepted | survives | killed |

The existing suite kills only 1 of 7. The guards hold on real data, but they are untested in the negative direction, which repeats the R17-4 gap.

## 7. Required changes (minimal)

- **R18-1.** In `Routes.__init__`, refuse a duplicate `(destination_host, destination_path)`, and add a test for it. My P2d then passes as a refusal.
- **R18-2.**
  - Adopt `test_rev_a18.py` e23fae36 byte for byte, as the A16 reviewer cases were.
  - Move `unittest.main()` in `test_a18_file_layer.py` to the end of the file.
  - Re-run M1–M7, which must all be killed.

**Advisories (non-blocking).** These should be disclosed in the r2 draft or the freeze record:
- the 3-registration control-root collision incident (9c88fb44);
- coverage r1 0f06656e was superseded: its recovery/04/08 counts were 84/149/150, against 61/162/160 in r2 (same 1,536 total);
- the coverage generator script isn't pinned;
- the `verify_dense` error text says "host08" but the check requires 04;
- `compare_records` is imported but unused.

## 8. Final A1 checklist after A18 (replaces A15 r2 §8, as amended by A16 §6 and A17)

1. **A18 freeze.** It binds the r2 package, draft, delta, snapshot manifest, test receipt, this review, and the R18-1/2 diff-only check. `APPROVE_FILE_LAYER_DELTA` binds the r2 delta and draft with `scientific_semantics_changed=false` and `timing_admitted=false`. The plan schema is `assembly-a18-v1`.
2. **Frozen bytes.** All earlier frozen bytes are unchanged:
   - A12 cc2357df / 60f0cb4e / bd5b7643;
   - all 334 A17 members (ecb9359c);
   - contract 3b3ebc8f, worker 70e8deaf, original worker 194dbbe3.
3. **Execution tree.** The exact r2 snapshot is installed on **04 or 03**. `verify_sources` passes against the source tree, the PYTHONPATH tree, the external files and `PYTHONPATH`. It must not be the live repo tree.
4. **Final authority.** For all 24 epochs, the `a18-v1` authorities differ from 9ba1cc02 only in `assemblies` and `scope`, checked by a mechanical JSON diff.
5. **Coordinator check: `a18_bindings` are identical across all 24 and equal to the APPROVE_A1 values.**

   | Binding | SHA |
   |---|---|
   | routes | efff5b98 |
   | retirement | e5d14103 |
   | r16_audits | 2c9e5c00 |
   | a17_condition | 05fa63c8 |
   | recovery_state | a334155a |
   | activation | 7ecdc1fb |

   The route manifest must also have unique destinations.
6. **A17 bindings.** These hold in every authority and in APPROVE_A1:
   - `evidence_recovery` 1adf50de;
   - `evidence_recovery_approval` 64b1ebe4;
   - condition 05fa63c8, whose `conditional_approval_sha256` is 64b1ebe4.
7. **Closures unchanged at A1 time.**

   | Item | SHA |
   |---|---|
   | Original live and snapshot state | fb9e6a75 |
   | Plan | 5d081677 |
   | Terminal | 7de8255c |
   | Recovery live state | a334155a |

   - The recovery plan equals 5d081677.
   - The namespaces are disjoint.
   - All controllers and transports are stopped.
   - 61 recovery tasks are verified and 953 are blocked.
8. **R16 and R13.** R16-1 and R13-3 pass inside admission. Python is never run with `-O`.
9. **Assemblies.** All 24 manifests are built with `assemble_epoch_manifest_a18_v4` and re-admitted with `ASSEMBLED_TYPED_RECORDS_A18`. For each epoch e:
   - `manifest.epoch == e`;
   - `authority.assemblies[e] == plan.epochs[e].complete_sha256 == approval.assembly_sha256[e]`.
10. **Admission-only dry run** of all 24 epochs, in a fresh process with no scoring. It must emit a coverage receipt from a **pinned** script showing:
    - 1,536 matches and 2,561,856 frames;
    - one source per (epoch, match);
    - class counts 404/118/162/160/587/44/61;
    - 64 matches per epoch, including 1975100708.
11. **Coordinator check on the dry-run evidence ledger.** It must have zero entries for:
    - host 02;
    - hosts 09/13/14/15 (all reads routed to 03);
    - `*-completion.jsonl`;
    - heldout paths.

    The record and decoder hashes must equal the inventory and proof pins.
12. **Retained sources.** Retained-original copies on 03, A15 copies on 03/04, the owned queue on 04/08 and the bundle/checkpoints stay unchanged through A2. Leased hosts and 02 are **not** required, which replaces A15 r2 item 11.
13. **APPROVE_A1** binds:
    - `execution_plan_sha256`;
    - `freeze_sha256` bd5b7643;
    - `file_layer_review_sha256` (A18);
    - all 24 `assembly_sha256`;
    - `a18_bindings`;
    - `evidence_recovery_sha256`;
    - `evidence_recovery_approval_sha256`.

    The plan has `tier2_enabled=false` and `heldout_opening_authorized=false`.
14. **Then the body seal**, in one process with a fresh session. A2 follows the seal. B stays blocked, and timing stays unadmitted.

## Summary (under 250 words)

**REQUIRED CHANGES (minimal).** Package 34e0c6b2, draft 329b3c91 and delta 89faa69f hash-match. All 346 snapshot files match, both locally and on 04, and all 334 A17 members are byte-identical. A12–A17 freezes and approvals are unchanged, and the diff covers exactly the 12 new files.

The design is sound:
- Each of the 1,536 matches has exactly one admissible source.
- The 61 02 sources are blocked by six independent guards.
- The recovery is bound to A16 contract 3b3ebc8f.
- Leased reads without a route are refused.
- Relocated bytes are checked against the original pins: real one-byte changes were rejected in all 4 member kinds.
- R16 needs all four PASSes plus the dense stress. On real files, the selection reproduced eb5d996b and the four routed PASS reports matched their hashes.
- Clocks, heldout data and selection are untouched.

Two minimal changes are required:
- **R18-1:** `Routes` accepts two sources with one destination, and the routed `hashes()` then verifies only the last pin. Refuse duplicate destinations. The pinned manifest has 0 duplicates, so no data is affected.
- **R18-2:** The existing suite kills only 1 of my 7 mutants (02 admission, retired filter, first-wins, receipt pin, R16 PASS, 02 route). Adopt `test_rev_a18.py` e23fae36 and move the mid-file `unittest.main()` (as written, 17 of 47 tests are skipped when the file is run directly).

A diff-only check of r2 is enough. Then follow the §8 checklist; the coordinator must verify items 5, 9 and 11 mechanically.
