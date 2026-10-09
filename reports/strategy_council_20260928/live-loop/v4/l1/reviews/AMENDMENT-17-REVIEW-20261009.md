# Amendment 17 — independent review (evidence recovery)

Reviewer: independent Claude reviewer for coordinator 0523ae6f, 2026-10-09. The review was read-only. Tests and mutants ran on 127x04 under nice 19 in `/tmp/a17rev`, which has since been removed. The actual 08 stress files were reopened read-only on 127x08. 127x02 was still unreachable at review time (`No route to host`, rc 255).

## Verdict: REQUIRED CHANGES

All four changes are small, and none needs the 08 stress to be re-run. After R17-1 to R17-3, a short code-only delta review is needed. After that, A17 can be frozen, and APPROVE_EVIDENCE_REPLACEMENT is gated by the mechanical post-run check in §5.

## 1. Bytes

| Item | Recomputed | Status |
|---|---|---|
| Review package | 7e773ec2…e562 | match |
| Draft | d9fa01eb…6e8e6e | match |
| Delta | 518bf690…64f4 | match |
| Snapshot manifest | d5635020…a3df | match |
| Test receipt | a8d7b27b…7497 | match |
| A16 contract | 3b3ebc8f | match |
| Overlay | 96519baf | match |
| Worker | 70e8deaf | match |
| Precommit | 151771eb | match |
| Old qualification copy | 40828251 | match |
| Retired 02 stress `pass.json` copy | 9f6b1ca4 | match |

- **Snapshot:** 332 files on disk, and all 332 match the manifest. The delta's new and unchanged lists together cover exactly the manifest, with no extra or missing file.
- **A16 continuity:** all 324 "unchanged" entries equal the A16 snapshot manifest `2ced1534`, with no hash differences and no omissions.
- **Frozen records:** the A12, A15 and A16 freeze, approval and delta records and the A16 review are unchanged in git and match their pins:
  - `16-FREEZE` cae72ebd
  - supplement 3e5c04b8
  - `16-FILE-LAYER` approval 730c86e8
  - `16-delta` eafa80ff
  - `12-FREEZE` bd5b7643
  - `15-FREEZE` 33e3a071
  - A16 review 4e486c2c
- **Nit:** 5 files appear in both `new_files_sha256` and `unchanged_a16_files_sha256` with identical hashes:
  - `assembly_relocation`
  - `epoch_admission_session`
  - `queue_audit_io`
  - `queue_output_audit_a16`
  - `vectorized_producer_contract_a16`

  This is intended, because `verify_file_layer_delta` requires them in `new_files`. Only the label is wrong; no change is needed.
- **Assembly diff:** `epoch_assembly_a17_v4.py` differs from the A16 version only in the qualification call, `verify_replacement_evidence` instead of `verify_qualifications`. Production authentication, production audits, population, scoring and clock code are untouched.

## 2. Guarantees preserved

**Qualifications.**
- The unchanged A16 `verify_qualifications` runs on a deep-copied view in which only `qualification_receipts` differs. That keeps:
  - the worker name and SHA;
  - all 27 contract source pins;
  - live `io.hashes`;
  - the retained-original origin and reference-copy receipts;
  - the nine branches with a raw line-by-line byte comparison.
- `load_recovery` also requires:
  - exactly the three `CELLS`, with no duplicates or extras;
  - frames and `reference_origin` identical to the old receipt copy 40828251;
  - no 02 host and no OLD_QUAL SHA.
- The population is the same.

**Stress.** I independently reopened the 08 run.
- **Pins:** `pass.json` c273fc26, complete 02eef314, telemetry 4668cf65, plan 09c07244, driver 30b3c773.
- **Plan:** 72 pins, including all 27 contract sources. The qualifier is eba6349d, the same as the snapshot.
- **Cell:** e1/708 with 2416 frames. The reference origin is 04 `epoch-capture-r1/epoch-01`, inventory e2d729d7 and manifest 28a8e544, identical to the retired 02 stress plan.
- **Reference copy:** d5272f92, with its record SHAs equal to the retained original.
- **Output:** the worker is 70e8deaf and the clock is `INVALID_RECORD_ONLY`.
- **Streams:** all 9 are byte-identical, 2416 rows each, with `source_seq` contiguous and no `available_timestamp_ms`.
- **Load:**
  - 34 samples over 335 s of a 345 s run. The first sample came 0.2 s after launch.
  - Lane counts were 5–8 (minimum 5), and every sample was ≥4.
  - Lanes are child processes of the identity-checked 08r3 production controller running `whole_match_capture_vectorized_v4.py`, so they are real vector production lanes.
- **Precommit:** the "two distinct hosts" condition still holds, now 08 + 04. The sampling interval is 10 s, against 15 s in the precommit; that is denser, so it's conservative.

## 3. Scope closure and 02 exclusion

- **What the recovery record can change:** only `replacement_qualifications`, restricted to the three cells, and `replacement_stress`, restricted to host 08 and cell (1, 708). The A14 proof, overlay, queue plans and production provenance are all read from the unmodified contract.
- **02 evidence:** 02 hosts and the OLD_QUAL receipt are refused. The worker refuses a pre-existing output directory (line 68) and `--resume-from` (line 63). So a passing qualifier receipt implies a fresh capture, unless someone forges it by hand; §5 checks for that.
- **Approval binding:** the approval must bind the recovery SHA, the contract and timing=false. The recovery record can't approve itself, because that would need a self-hash.
- **A1 binding:** A1 binds `evidence_recovery_sha256` for all 24 epochs. It binds the approval receipt only transitively, through the authority plan → execution plan (see R17-3).

## 4. Required changes

- **R17-1 (durability, blocking).** The allowed replacement hosts are only 127x09 and 127x13. Those are roader hosts on lease, with the lease ending 2026-10-11T05:30Z and reclaim possible on 30 minutes' notice. `io.read` reopens the evidence at A1 assembly time, so this repeats the exact failure that caused A17: single-copy evidence on a host we don't control.
  - **Fix:** add an owned host that is already in `io.HOSTS` (127x08, or 04) to the closed set, and run the qualifications on 08 after closure.
  - **Fallback:** if they must run on 09 or 13, the coordinator records that the approval lapses if A1 assembly hasn't completed before the lease ends.
- **R17-2.** `verify_stress` must check `c['source_sha256']` against the plan pins and pin the qualifier, matching A16 lines 41–42. The 08 run already satisfies this, so no re-run is needed.
- **R17-3.** A1 must also bind `evidence_recovery_approval_sha256`, and that value must be equal across all 24 authorities. Today the binding is only transitive.
- **R17-4.** Add tests for guards that currently have none. My mutants on 04 ran against a baseline of 86/86 OK; 2 of 9 were killed (M3 host 02, M6 A1 binding). The surviving guards and the tests that kill them:

  | Mutant | Guard removed | Killing test |
  |---|---|---|
  | M2 | OLD_QUAL exclusion | old receipt on host 09 refused |
  | M5 | stress identity check, so any e1 match would pass | other e1 cell refused |
  | M8 | approval–contract binding | approval for another contract refused |
  | M4 | plan worker pin | plan worker changed |
  | M1 | extra-cell check (still fails closed, on KeyError) | extra out-of-scope cell refused |

  I wrote these 7 tests and ran them: they pass on the original code (49/49) and kill M1, M2, M4, M5 and M8. M7, a worker leak through the view, survived. It's equivalent under the test fixture; add an assertion that the view equals the contract apart from `qualification_receipts`.

## 5. Post-run check before APPROVE_EVIDENCE_REPLACEMENT

The coordinator runs this mechanically and records a receipt. A follow-up review is needed only if any item fails or deviates.

1. **Receipt and host:** each replacement receipt is on an allowed host (per R17-1), its SHA ≠ 40828251, and its plan SHA ≠ 0f920ca0. The output paths are new, not the retired `…-02r1` paths, and `started_unix` is after the host-loss receipt (≥09:37Z).
2. **Cells:** exactly e7/738/444, e15/748/796 and e1/708/2416 across the receipts. Each `reference_origin` equals the cell in 40828251.
3. **Worker and sources:** the plan worker is 70e8deaf, all 27 contract source pins match, the qualifier is eba6349d, and `io.hashes` passes on the host.
4. **Reference copies:** an `audit_reference_copies` receipt exists for each host:reference, with its origin equal to the retained original and its `record_sha256` equal to the inventory `files_sha256`.
5. **Recovery record:**
   - schema, policy, `timing_admitted=false` and `scientific_semantics_changed=false`;
   - `retired_stress` 9f6b1ca4;
   - `retired_qualifications` equal to the contract list;
   - the host-loss receipt (02, rc 255);
   - `replacement_stress` set to 08 `pass.json` c273fc26 plus plan, telemetry and complete as in §2.
6. **Actual-file dry run:** `verify_replacement_evidence(producer_contract(authority), authority, …)` on the real files, run on 04 with nice, exits 0. That rehashes and re-compares 27 + 9 raw streams. Record its log SHA.
7. **Durability:** the evidence host is owned, or the lease lapse condition from R17-1 is recorded.

APPROVE_EVIDENCE_REPLACEMENT then binds the recovery SHA, contract 3b3ebc8f and `timing_admitted=false`, and A1 binds both the recovery SHA and the approval SHA.

## Summary (<200 words)

The A17 bytes are exactly as claimed. All 332 snapshot files match. The 324 A16 files are unchanged against A16 manifest 2ced1534, and the A12, A15 and A16 freeze records and review are unchanged. The only code change is the qualification call, and it reuses the unchanged A16 byte-exact verifier through a view that swaps only the qualification receipts. The scope is closed: the three named cells, and stress only at 08/e1/708. 02 hosts and receipt 40828251 are refused.

I reopened the 08 replacement stress myself:
- the frozen 70e8deaf worker;
- the same 04 retained original as the retired 02 stress;
- all 9 streams byte-exact over 2416 rows;
- 34/34 telemetry samples at ≥4 real vector production lanes, minimum 5.

**REQUIRED CHANGES:**
1. **R17-1:** the replacement hosts 09 and 13 are leased roader hosts (lease to 10-11 05:30Z), which repeats the 02 single-copy failure. Allow owned 08 (or 04), or tie the approval's validity to the lease.
2. **R17-2:** the stress check must verify the 27-file source closure. The existing run already satisfies it.
3. **R17-3:** A1 must bind the approval-receipt SHA directly.
4. **R17-4:** the guards for M2, M5, M8, M4 and M1 have no tests; they survive mutation. I wrote 7 tests that kill them.

After that comes a short delta review, then the §5 mechanical post-run check, which ends in the actual-file `verify_replacement_evidence` dry run, before APPROVE_EVIDENCE_REPLACEMENT.
