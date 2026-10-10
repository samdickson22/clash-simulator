# Amendment 20 r1 review: narrowing the 04-local I/O lock scope

This is the independent reviewer's report for coordinator 0523ae6f, written 2026-10-10 from 04:37Z to about 05:00Z.

**How the review ran.** The review was read-only.
- **05 (nice 19):** all tests and models ran here, using Python 3.12.12 (`~/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu`).
- **04:** only `ps`, `/proc`, `sha256sum`, `find -printf` and two `scp` reads of real decoder records, all under nice 19 / ionice 3. Nothing was written on 04, no lock was taken and no signal was sent. The seal child 2499719 was not disturbed.
- **Scratch on 05:** `/tmp/sdicks02/a20-review-data` holds the two record copies for the reviewer tests. `/tmp/sdicks02/a20-suite*` holds a suite rerun.
- **Reviewer's own files:** this file and `reviews/a20-reviewer-artifacts/`. Nothing else was modified.

## Verdict: APPROVE_WITH_CONDITIONS

The adapter is correct and does what it claims:
- **Same inputs, same results.** For every input class I tried, results are byte- and semantically identical to the A19 r5 whole-context path.
- **No TOCTOU window.** The parser consumes the very `bytes` object that was hashed under the lock.
- **The lock still does its job.** Its only real function on 04 is coordinating readers, and no writer or retention process uses it.
- **Memory is negligible.**
- **It is the speed lever the r4 review asked for.** My model puts A19+A20 at about 6.8 serial-equivalents during verify-then-retire, against 1.2 under the frozen scope, so A1 parallel plausibly finishes in about 2–2.5 h against about 13.7 h for serial.

**What blocks the freeze.** The composed package's own authority tests were never run against the composed bytes, and they fail there (C1). A diff-only re-check after C1, plus C2 if the cap is raised, is sufficient.

## 1. Bytes and pins

| Item | Result |
|---|---|
| Package manifest 2bd384ea… | `check_package.py --manifest-sha256 2bd384ea…` **PASS**: 19 original fields unchanged, 347 A18 pins, 11 runtime files, plan eca06114… (`check-package.log`) |
| Draft 6b027d79…, plan eca06114…, adapter da583414…, pins d8f32c8c…, diff d35105e8…, receipt 0c69a936…, measurement 874f381f… | all match |
| Seven unchanged A19 files (kernel, reduce, common, a2, resources, pool, handoff) | byte-equal to r5 |
| Changed files | `a19_authority.py`, `a19_launcher.py` and `a19_worker.py` (one import line each in the launcher and worker), plus the new `a20_io.py`. The diff contains nothing else. |
| Frozen I/O module under the adapter | `queue_audit_io_v4.py` 1df4d0c1… is A18-pinned (`source_files_sha256`), and the tests load that exact file. The l1-root copy a8883016… is an older, unpinned file. |
| Live serial path on 04 | `run_stage.py` 8c3c0523… and `supervise.py` 884f0304… are unchanged. The seal child's open lock is `/mpac/sdicks02/jobs/clasher/v4-queue-independent-verifier-20261009-r1/proofs/127x04.io.lock`, the same path as A20's `LOCK_ROOT`. |
| Author A20 suite rerun | 63/63 PASS (0.12 s). These are about 22 unique methods; `BufferBudget` and `Routing` re-run the 15 `LocalIO` tests. |
| Synthetic re-measure | Median lock fraction 0.99973 → 0.01119, wall 0.976 → 0.982 s, all 8 digests equal (`synthetic-lock-remeasure.json`). This reproduces the author's figures. |

## 2. Scientific identity (question 1)

**Code reading.** For a local 04 record, `records()`:
1. calls the same `io.safe()` (owned roots and journal refusal) and `is_symlink()` refusal, inside the same host lock;
2. reads at most `budget+1` bytes from one open fd;
3. checks `sha256(blob)==expected` **before unlock and before yield**;
4. runs the identical `gzip.GzipFile` over `BytesIO(blob)`;
5. keeps the trailing `read(1)` check for unconsumed records;
6. calls `note()` only after success.

The metadata `read()` follows the frozen order exactly: `raw`, SHA, pin check, `note`, then `json.loads`. Only the parse moves out of the lock. `hashes()` and every non-04 or remote call go through the saved whole-context path.

**The A18 routing composition is right.** `io_locks` is installed first, in the worker and launcher. `routed()` then saves the A20 functions and calls them with the routed destination host. Leased routes resolve to 03, so they keep the full lock.

**Differential tests** (`test_rev_a20.py`, 25/25 PASS, `reviewer-tests.log` adcdb26b…). Each compares the frozen A19 r5 `io_locks` against A20 over the pinned `queue_audit_io_v4`:

| Class | Result |
|---|---|
| **Real 04 decoder records** (16.1 MB current seal file and 31.3 MB largest file, from 04) | Identical raw lines, parsed rows and ledger `{(127x04,path): pin}` |
| Truncated, CRC flip, ISIZE flip, body flip, trailing garbage, not-gzip, empty, two members, zero padding, **with the pin of those bytes** | Identical outcome: same exception class and message, or the same rows, and the same ledger |
| The same corruptions with the **expected (good) pin** | Neither scope ever passes or notes evidence. A20 always raises `ValueError('Compressed record SHA differs')`; the frozen path can raise a gzip error first. No A18 or A19 code branches on exception type (I grepped every `io.records`/`io.read` caller; the pool, launcher and handoff treat any `BaseException` as failure). |
| Consumer raises, or exits after one line | Identical outcome and ledger |
| Ledger conflict (same key with a different pin) | Identical `Admission evidence changed` |
| Symlink, journal, missing file, bound to 1 byte | Fail closed with no ledger entry (author tests, rerun) |

**TOCTOU.**
- **Snapshot is the hashed object.** A test asserts that the object passed to `sha256` **is** the object given to `BytesIO`. The mutant that re-opens the file for parsing fails this test, and the mutant without the SHA check fails 9 tests.
- **Writer changes during the locked read fail closed.**
  - The file grows past the budget between `fstat` and `read`: `exceeds512MiB`, no ledger entry.
  - The file is truncated after `fstat`: SHA mismatch.
- **Changes after the snapshot can't reach the parser.** An atomic `os.replace` plus `unlink` mid-parse leaves the parsed rows equal to the authenticated snapshot.
- **Residual, unchanged from the frozen code.** The `is_symlink()`-then-`open()` pair is not `O_NOFOLLOW`. A symlink swapped in at that instant would still have to produce bytes with the expected SHA.

**The 512 MiB limit is not reachable on real data.** All 6,608 `.gz` files under 04's `/mpac/sdicks02/repos/clasher-v4-cache` total 36.0 GB. Their median is 1.84 MB, p99 24.5 MB and maximum **31.3 MB**. There are no `.gz` files over 100 MB under 04's `jobs/clasher` or `v4-archive`. So the fail-closed bound has at least a 16× margin, and the nested `left`/`right` audit pattern buffers at most about 63 MB.

**Conclusion.** For any input that the frozen path accepts, A20 accepts it with identical bytes, results and ledger. For any input the frozen path rejects, A20 rejects it too, sometimes earlier and with a different exception, and writes no ledger entry. The serial path is unchanged.

## 3. What `127x04.io.lock` protects (question 2)

I enumerated every holder of a `proofs/<host>.io.lock` in the repo and live on 04:

| Holder | Lock taken | Role |
|---|---|---|
| Serial seal/verify `run_stage.py lock()` | 04, 03, 08 | Reader (frozen whole-context scope, blocking flock) |
| A19 `io_locks` | 04, 03, 08 | Reader (LOCK_NB poll every 0.2 s) |
| `queue_independent_verifier_locked_v4`, parallel-verifier ops | owner host | Reader |
| `verified_capture_retention{,03}_v4` (**live:** pid 2296629, running about 18 h 48 min) | **source host only**, one of `{09,13,14,15}` | Copy, then delete leased streams. It never takes 04 or 03. |
| `capture_free_floor_monitor*`, `admission_quiet_v4`, `t6t7_release04`, `archive_release_r16` | capture hosts | Queue control and recovery ops. None is running now. |

**What the lock means on 04.** It coordinates reader contention, the I/O rate and a few cooperating ops. **No writer or retention process cooperates through it on 04**, and identity has always come from expected SHAs plus owned-copy receipts.

**Why narrowing is safe.**
- A20 holds the lock for the whole read and hash, so any cooperating op is still linearized at the same point: the reader gets the complete pre-op bytes, or the complete post-op bytes and then a SHA failure.
- After unlock, the reader holds a private, immutable snapshot, so later relocation or deletion cannot be observed.
- The only property lost is cross-file atomicity for nested 04 calls made inside a 04 stream: two holds instead of one. Every records call is SHA-pinned, so that can't change results.

**Lock ordering.** The 04 lock is never held across a `yield` (test `test_04_never_held_across_a_yield`), so A20 removes A19 from any 04→X wait cycle. No production caller nests records from different hosts: the audit `left`/`right` pairs use the same host. Retention takes no 04 lock, so it can't race in a new way. No writer lock is removed.

**One wording correction.** Draft §1 should list the holders above. "Not the cache-writer lock" is true for 04, but the lock *has* served queue-recovery ops on capture hosts (R1).

## 4. Memory (question 3)

| Quantity | Value |
|---|---|
| Live seal child (same loop) | PSS 0.88 GB, VmHWM 1.19 GB |
| A20 private buffer per process, real data | ≤ about 31 MB per open record, ≤ about 63 MB for a nested pair |
| A20 worst case by design | 512 MiB × 13 (12 workers + controller) = 6.98 GB |
| `read(budget+1)` allocation | Virtual only: peak RSS 79 MB while reading 31 MB with a 512 MiB request (`real-record-split.json`). `BytesIO(bytes)` shares the buffer without copying. |
| A19 owned PSS at 12 workers, estimate | about 13 × 1.2 GB ≈ 15.6 GB, plus at most 0.8 GB (real) or 7 GB (worst case) of buffers: **≤ 23 GB, below the 48 GB cap** |
| 04 MemAvailable at 04:40Z | 112.6 GB (about 105 GiB), so O3's ≥ 80 GiB at launch is met today |

No policy change is needed. The 48 GB cap and the 28 GiB floor stay as they are.

## 5. Integration and authority (question 4)

**Composed full suite (my run).** I ran the A19 r5 suite with the composed 11-file runtime overlaid, plus the A20 tests (`build_and_run_composed_suite.sh`, `composed-full-suite.log` 932f455f…).
- **208 tests ran: 201 pass, with 5 failures and 2 errors, all in `test_a19_authority.AuthorityTests`.**
- The cause: the r5 fixture pins only `a19_*.py` and carries no A20 records, so every case stops at `Complete operational source set`. This is a gap in the package's test coverage, not a security defect, but the author's receipt says the composed suite was not run, and in fact it does not pass.
- Every non-authority A19 test passes on the composed bytes, including the STOP-race, handoff, real-lock, PSI and kernel tests.
- **Reproduced** by rerunning `build_and_run_composed_suite.sh` from a `/tmp/sdicks02` scratch tree: 208 ran, with the same 5 failures and 2 errors and nothing outside `test_a19_authority`. One test, `test_inventory_permission_error_on_smaps_propagates`, skips there because its cwd is outside the repo; it passes in the logged run.

**My end-to-end composed authority tests** (`ComposedAuthority`, 8/8):
- A fully valid A19+A20 request passes the composed `authenticate()`, and both frozen plan authentications are called.
- Each of the following is rejected:
  - an op approval bound to another A20 freeze;
  - an A20 freeze or approval bound to the base r5 plan;
  - a base-r5-style request missing `a20_freeze`, `a20_approval` or `a20_amendment`;
  - an A19 freeze whose source map lacks `a20_io.py`;
  - the base r5 output parent;
  - `valid_until_utc=2026-10-13T04:00Z` (current cap).

**Base r5 authority cannot authorize the composed bytes, and the reverse also fails.**
- The composed authority requires the A19 freeze map to equal the 11-file pins, which include `a20_io.py`, and also requires the A20 freeze and approval bound to the combined plan.
- Base r5 code requires the source set to equal `a19_*.py`, so a plan pinning `a20_io.py` fails there too.

**Deployment hazard.** The composed authority globs `CODE_ROOT/*.py`. Copying `a20_io.py` into the r5 deploy directory would break r5, and mixing files would break both. Deploy the composed runtime to a new directory (C3).

## 6. Expected real speedup (question 5)

**Inputs.**
- The r4 probe (`probe-04-lock-occupancy.json` ce6d389d…) measured one verifier at 04 = 0.534 (157 acquisitions per 300 s), 03 = 0.108 (24), 08 = 0.026 (6), CPU 0.987. The three holds are disjoint: the sum, 0.668, equals the any-lock fraction.
- On real 04 records, A20's locked part (open, read, SHA) is **≤ 2.0%** of the work the frozen scope held under the lock: 16 ms / 0.80 s and 30 ms / 1.57 s, warm cache, counting only gunzip and `json.loads`. Consumer scoring would lower this further.

**Model.** `model_a20_speedup.py` is a time-stepped lock simulation calibrated to those numbers: serial uses a blocking flock and is served first, A19 workers poll every 0.2 s, and A20 shrinks only the 04 hold by `r`. Results are in `model-a20-speedup.jsonl`; rates are in serial-equivalents.

| Scenario | Serial | A19 aggregate | A1 wall (12.7 h work) |
|---|---:|---:|---|
| Frozen scope, 12 workers + serial | 0.68 | 1.20 | about 10.6 h for A19, and serial slows to about 19 h. This reproduces the r4 cap of about 1.9×. |
| **A20, r = 0.02, 12 workers + serial** | **0.93** | **6.81** | **about 1.9 h, plus epoch tail ≈ 2–2.5 h** |
| A20, r = 0.05, 12 workers + serial | 0.90 | 6.54 | about 2.0 h, plus tail |
| A20, 6 workers + serial | 0.94 | 4.14 | about 3.1 h |
| A20, 12 workers, no serial (A2) | n/a | 8.60 | about 1.5 h per 24-epoch verification (r4 estimate: 6.8 h) |

**Reading the model.**
- The binding lock moves to **03**, which keeps its whole-context scope: 0.108 × (0.93 + 6.8) ≈ 83% utilization. The 03 cap is about 1/0.108 ≈ 9.3 verifier-equivalents in total.
- Serial, which keeps the old scope during verify-then-retire, still holds 04 about 53% of the time. That costs each worker about 0.2–0.3 s of polling wait per second of work; it does not cap the aggregate.
- A20 also **reduces the harm to the serial fallback**: serial runs at about 0.93 instead of 0.68.

**Answer.** Yes, A19+A20 on A1 now plausibly beats serial by about 5×. 24 epochs over 12 workers means two waves, so the longest epoch sets the tail. The model is not a measurement, and the first-wave telemetry (R3/O5) remains the ETA authority.

## 7. Execution cap (question 6)

**Recommendation: yes, raise A19's code cap to 2026-10-13T04:00Z in the composed freeze.**

**Why it is safe.** A1/A2 admission reads files over local or SSH `raw`/`records`/`hashes` and does not use the 03/08 HTTP cache services (DEADLINE-REPORT item 4). The Oct-11 constant is therefore an approval ceiling, not a technical dependency.

**Why it is worth doing.** If A19 is not launched for A1, the serial A1 finishes around 21:30–22:00Z. A2 build plus verified bounds, each with its own approval, then has only about 6 h before Oct-11 04Z.

**The approval still sets the actual end.** The code cap is only a maximum, so the coordinator keeps the actual end in `valid_until_utc`.

**Exact change (condition C2):**
1. In composed `a19_authority.py` line 52, replace `datetime.datetime(2026,10,11,4,tzinfo=datetime.timezone.utc)` with `datetime.datetime(2026,10,13,4,tzinfo=datetime.timezone.utc)`. Change nothing else; the message string stays as it is.
2. Re-pin `a19_authority.py` in `source-pins.json` and in the plan's `operational_body_verification.source_files_sha256`. This gives a **new combined plan SHA**, which replaces eca06114… everywhere in §8. Regenerate the integration diff, delta and manifest.
3. Tests: flip `test_oct13_valid_until_rejected_by_current_cap` and `test_cap_constant_in_composed_source` in my file to "Oct-13 accepted, Oct-13 + 1 s rejected". Rerun the full composed suite.
4. Set the op approval's `valid_until_utc` to the coordinator's explicit **execution** allocation for 04, not merely the service renewal, and ≤ 2026-10-13T04:00:00Z. Bind that decision as the unenforced extra `execution_cap_authority_sha256`. If no such allocation exists at approval time, keep it ≤ 2026-10-11T04:00:00Z.
5. Guard semantics don't change: work past `valid_until_utc` hard-fails, and the serial fallback is untouched.

## 8. Conditions

### Before freeze (diff-only re-check)

- **C1 (blocking): composed tests.**
  - Update `test_a19_authority.py` fixtures to the composed shape: sources = `a19_*.py` plus `a20_io.py`, `local_io_lock_scope`, A20 freeze, approval and amendment, `a20_freeze_sha256` in the op approval, and the new output parent.
  - Alternatively, adopt my `ComposedAuthority` class.
  - Then rerun the **full composed** suite (A19 + A20 + reviewer tests) under 3.12.12 and nice 19. The receipt must bind the new source pins and state the full count.
- **C2 (if the cap is raised): the cap change** listed in §7. This yields a new plan SHA.
- **C3 (blocking): deployment.**
  - Deploy the 11 production files and the pinned auxiliaries into a **new** code directory, for example `/mpac/sdicks02/jobs/clasher/v4-a19-review-r5-a20-r1`. Never add `a20_io.py` to `v4-a19-review-r5`.
  - The launch command's script path must point at the new directory.
  - Never run base and composed concurrently (already in OPERATOR).

### Before launch (operational)

- **O1–O6 from A19 apply unchanged.**
- **O7 (A20 preflight).** Record the maximum compressed size over the admitted explicit 04 paths and require it to be < 512 MiB. Today the maximum is 31.3 MB.
- **O8.** No queue-recovery, quiet-admission, archive-release or other op taking `127x04.io.lock` may start during the attempt. This is already implied by `no_new_clasher_launches`. Retention03 (leased-host locks only) may continue.
- **O9 (first wave).** Record per-lock hold fractions for 03, 04 and 08 per worker. If 03 exceeds about 0.9 aggregate utilization, expect the model's ceiling, not 12×.

### Recommendations (non-blocking)

- **R1.** Draft §1 erratum: list the lock holders from §3 and the error-ordering note from §2. Put this in the freeze record rather than editing the draft, because the draft's SHA is bound.
- **R2.** In `test_a20_io.py`, `if __name__=='__main__':unittest.main()` sits above `class BufferBudget`, so running the file directly skips it. Discovery is unaffected.
- **R3 (future, separate amendment).** The same bounded-snapshot method for **remote 03** streams would lift the new 03 ceiling. A remote snapshot can also be SHA-checked before parsing.

## 9. Exact approval fields (question 7)

Throughout this section, *P* means the combined plan SHA: eca061149b2333c3a2bfea82442b91580f59bad1e1e5acae9fd5cae27b415d2e if the cap stays unchanged, otherwise the new SHA from C2. *S* means the 11-file `source_files_sha256` map from the final `source-pins.json`.

**A20 freeze.** Every key below is enforced by `authenticate_a20`.

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | *P* |
| `base_a19_plan_sha256` | `7d2a92bc06315c7a1fcabc2636c9818cec1784446ee35fd6b9b5399c28f4fc12` |
| `adapter_sha256` | `da583414af5554417cd58b2f199f6466fa54cd731163ec62540afc1ec12bc7f0` |
| `amendment_sha256` | `6b027d792f5a3baa2524725db34a05f3a23798c88fef363e39737064da36fc15`, rehashed from the deployed draft |
| Recommended extras | `a20_review_sha256=<this file>`, `source_pins_sha256`, `r1_erratum` (R1) |

**A20 approval.** The decision string **must** be `APPROVE_LOCAL_IO_LOCK_SCOPE`; a record reading `APPROVE_A20` is rejected by the code.

| Key | Value |
|---|---|
| `decision` | `APPROVE_LOCAL_IO_LOCK_SCOPE` |
| `a20_freeze_sha256` | SHA of the A20 freeze record |
| `execution_plan_sha256`, `base_a19_plan_sha256`, `adapter_sha256`, `amendment_sha256` | equal to the freeze |
| `hosts` | `["127x04"]` |
| `authorized_stages` | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` (must equal the plan's `stages` exactly) |
| `serial_runner_changed` / `B_authorized` / `heldout_opening_authorized` | `false` / `false` / `false` |

**Combined A19 freeze.**

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | *P* |
| `source_files_sha256` | *S* (11 files, including `a20_io.py`) |
| `amendment_sha256` | `2b09f87a742a072bcb411708a332331c9463669efb2465903c54b6a0efea3839` (A19 r5 draft, rehashed) |
| Recommended extras | A19 r2/r4/r5 review SHAs, `a20_freeze_sha256` |

**Revised `APPROVE_A1`.** It has exactly 8 keys.
- `decision=APPROVE_A1`
- `execution_plan_sha256=`*P*
- These six must be canonically equal to 19401ce4…:
  - `freeze_sha256` bd5b7643…
  - `file_layer_review_sha256` ff45e9ed…
  - `assembly_sha256`
  - `evidence_recovery_sha256` 1adf50de…
  - `evidence_recovery_approval_sha256` 64b1ebe4…
  - `a18_bindings`

**`APPROVE_PARALLEL_BODY_VERIFICATION`.** All the r5 fields apply, with these changes:

| Key | Value |
|---|---|
| `a19_freeze_sha256` | combined A19 freeze SHA |
| **`a20_freeze_sha256`** | A20 freeze SHA (new, enforced) |
| `execution_plan_sha256` | *P* |
| `source_files_sha256` | *S* |
| `amendment_sha256` | 2b09f87a… (A19 r5) |
| `original_execution_plan_sha256` / `original_approval_sha256` | 68e24722… / 19401ce4… |
| `authorized_stages` / `hosts` | the three stages / `["127x04"]` |
| `seal_root` / `seal_binding` | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` / `authenticated-r4-exit-then-pin-actual-bytes` |
| `handoff_policy` | `verify-then-retire` |
| `exclusive_physical_cpus` / `excluded_siblings` | `[0..11,47]` / `[64..75,111]` |
| `no_new_clasher_launches` / `x5_actual_exit_required` | `true` / `true` |
| `B_authorized` / `heldout_opening_authorized` | `false` / `false` |
| `valid_until_utc` | ≤ 2026-10-11T04:00:00Z, or ≤ 2026-10-13T04:00:00Z only with C2 plus an explicit execution allocation |
| `output_parent` | `/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r5-a20-r1` |
| Recommended extras | `allow_serial_verify_handoff=true`, `min_mem_available_at_launch_bytes=85899345920`, `x5_supervisor_exit_required=true`, `max_local04_compressed_bytes_observed` (O7), `execution_cap_authority_sha256` (C2) |

**The request.**
- `verification_plan` points to *P*, and `amendment` to the A19 r5 draft.
- It adds `a20_freeze`, `a20_approval` and `a20_amendment`, each a `{path, sha256}` descriptor. The A20 draft is rehashed.
- `stage_approval=null` for a1-verify.

**A2 later.** Each A2 stage needs a separate `APPROVE_A2`, as in r5, with `verification_execution_plan_sha256=`*P*. A20 confers no A2, B or held-out authority.

## Summary

**APPROVE_WITH_CONDITIONS.**
- **Identity:** results are byte- and semantically identical on real 04 records and on every corrupt, truncated, symlinked, oversized and budget class. The parsed snapshot is exactly the hashed object.
- **Lock:** the lock's reader-coordination purpose is preserved. No 04 writer or retention process uses it.
- **Memory:** ≤ 23 GB owned, below the 48 GB cap.
- **Speedup:** the model gives A19 about 6.8 serial-equivalents against serial's 0.93, so A1 takes about 2–2.5 h instead of about 13.7 h. The 03 lock becomes the ceiling.
- **Blocking:** C1 (the composed authority tests fail 7/208; they were never run by the author) and C3 (a separate deploy directory).
- **Recommended:** C2, raising the cap to Oct-13 04Z with one constant and a new plan SHA.

## Reviewer artifacts (`reviews/a20-reviewer-artifacts/`)

| File | SHA-256 |
|---|---|
| `test_rev_a20.py` (25 tests) | `4fec068b83cb9742b495fd836c943bb2eb9abff0b3a5c5ee5b4cc39d9f95e4d5` |
| `reviewer-tests.log` (25/25) | `adcdb26be7ae22acc37d2020dfcd3564d6f4593e4c2e911220e7e1222884c92b` |
| `composed-full-suite.log` (208: 201 pass, 7 authority failures) | `932f455fb2690ef33744e7237dd480c8ab61408722fd72937409c6d130d064f0` |
| `build_and_run_composed_suite.sh` | `a948ba8875a122e3ae1f3d3fadc9f401c615d6adc29ae7020c0e9e1705a87f30` |
| `author-a20-suite-rerun.log` (63/63) | `c7d61683b9379ae86d3facc9e51ffd3c9b8fb6b059f1834680be439b35abe2df` |
| `check-package.log` | `11e1c327f7617ac2e7c42a324bbb1ac420cca126ab1faac58eac1291f689df03` |
| `synthetic-lock-remeasure.json` | `1a0930a9d0ad57fe7066a479adb9c08bc41c8a4079783186dfb6c0e5ef62f4bb` |
| `measure_real_record_split.py` / `real-record-split.json` | `1410bfdb…` / `2d89e635f65597c2c18fa0bfab8b1fa75ab8b3d963fa7dc3fb162e359d254807` |
| `model_a20_speedup.py` / `model-a20-speedup.jsonl` | `698fb774…` / `fedbc161de468c75a752323992402ad30722372e53eed5391465adc724446ac2` |
