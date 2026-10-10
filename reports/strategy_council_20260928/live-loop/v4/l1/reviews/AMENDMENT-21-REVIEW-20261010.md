# Amendment 21 r1 review: narrowing the remote 03/08 lock scope

This is the independent reviewer's report for coordinator 0523ae6f, written 2026-10-10 from about 12:38Z to 13:00Z.

**How the review ran.** The review was read-only.
- **05 (nice 19):** all tests and models ran here, using Python 3.12.12 (`~/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu`). The package was copied into a scratch tree, `/tmp/sdicks02/a21-review/tree/l1`, whose siblings are symlinks to the real `l1`.
- **03 and 08:** only `uptime`, `/sys/block/*/queue/scheduler`, `find -printf %s`, and three `cat` reads of two real 03 records. These went over a reviewer-private ControlMaster, under nice 19 / ionice 3, and were streamed into memory on 05; nothing was written to disk.
- **01:** a ControlPersist stdio check, `head -c N /dev/zero|urandom`.
- **04:** never contacted. No running process, lock or file was touched.
- **Reviewer's own files:** this file and `reviews/a21-reviewer-artifacts/`. Nothing else was modified.

## Verdict: APPROVE_WITH_CONDITIONS

The adapter is correct:
- **Same inputs, same results.** For every success it produces exactly the A20/frozen bytes, rows and ledger. Every failure class still fails closed, with no evidence admitted.
- **No TOCTOU window.** The bytes that are hashed are the bytes that get parsed.
- **The 04-side 03/08 flocks still protect what they always protected:** cooperating 04-side readers and ops, and the one-stream-per-host load limit. They never coordinated with writers on 03 or 08.
- **The 30 s / 60 s bounds have more than 100× margin on real data.** The 60 s hash bound and the 30 s metadata bound are the frozen values unchanged; only the 30 s records bound is new.
- **Memory is small.**
- **Integration is exactly as claimed:** 3 changed files, 1 new file, A20 byte-identical, 19 scientific fields and 347 A18 pins unchanged.
- **I ran the full composed suite myself:** 289 tests, 288 pass, plus the one optional opt-out.

**The speedup is real but much smaller than the synthetic figures suggest.** The frozen-scope serial verifier keeps its full-context, blocking-priority hold on the 03 lock, and it now sets the ceiling. My recalibrated model puts A19 at about 2.2 serial-equivalents, against about 0.8 today. That makes a fresh A1 take about **4–7 h (central about 5.5–6 h), not 2 h.** It still beats the alternatives:
- the current attempt, about 14 h remaining;
- the serial fallback alone, finishing around 02Z Oct-11 or later.

So a fresh A21 attempt is worth launching.

**The conditions are about freeze and deployment content (C1–C3), not code defects.**

## 1. Bytes and pins

| Item | Result |
|---|---|
| Manifest 78e2a8b5…, plan 327c958d…, draft 26b56a67…, adapter a1637caf…, test receipt a1ef9260…, synthetic measurement e13baf24…, candidate authority check 22ed6208… | All match. All 61 `files_sha256` entries verify. |
| `check_review.py --manifest-sha256 78e2a8b5…` | **PASS**: held base package 7efbcbd1… / plan 0fe6fe3a…, 19 original fields unchanged, 347 frozen pins, 12 runtime files. Changed files: exactly `a19_authority.py`, `a19_launcher.py`, `a19_worker.py` and `a21_io.py`. |
| My own diff against `amendment19-a20-review-r2-candidate/composed-runtime` (the held A19+A20 r2 that is running) | 8 files byte-identical, including **`a20_io.py` da583414…**. The authority diff contains only: (1) the source set now includes `a21_io.py`, (2) a call to `authenticate_a21`, (3) the new output parent. The launcher and worker change one import line each. |
| Plan JSON delta, 0fe6fe3a → 327c958d | Only additions or changes: `operational_body_verification.remote_io_lock_scope` (new), `required_execution_authority` (text), and `source_files_sha256` (3 changed, 1 added). |
| `check_candidate_authority.py` (rerun) | PASS, with 2 frozen-authenticator calls. Hardware and scientific authentication are stubbed, as the README discloses. |
| A18 routing `evidence_transport_a18_v4.py` | a172fdc2… (A18-r2 copy). This matches `ROUTING_SHA` and the plan pin. |

## 2. Scientific identity and TOCTOU (question 1)

**Code reading.** `snapshot()` holds `one(host)` across:
1. `_capture()`, which spawns Popen and then requires stdout EOF, stderr EOF, the child's exit, and `returncode==0`;
2. the expected-SHA check;
3. a guard.

Only after unlocking does it yield the private `Snapshot`.

- **`records()`** wraps those exact chunks in `ChunkReader → BufferedReader → GzipFile`. It yields, checks `read(1)` for unconsumed records, and only then calls `note`.
- **`read()`** calls `note` before `json.loads(blob())`, which is the frozen order.
- **`hashes()`** runs the frozen remote script byte-for-byte (the same `replace('PINS',repr(pins))`). It requires exit 0 before unlocking, then parses the reply and checks the count, then calls `note` on the original pins.
- **Unsupported hosts, non-local 04 and local-04 hashes** go through the saved A20-style whole-context path.
- **Ordering with A18:** `io_locks` is still installed below `routed()`, so leased routes resolve to 03 before A21 sees them.

**The hashed bytes are the parsed bytes.** `Snapshot.append(b)` charges the budget, updates the SHA with `b`, and copies the same `b` into the chunks. `ChunkReader` reads only those chunks, and `blob()` joins only those chunks. Nothing re-opens the file or the remote, so no remote change after the SHA check can reach the parser.

**Differential tests** (`test_rev_a21.py`, **12/12 PASS**, `reviewer-tests.log`). Each compares A20, which uses the frozen remote whole-context path through the pinned `queue_audit_io_v4` 1df4d0c1…, with A21. SSH is replaced by exact local children.

| Class | Result |
|---|---|
| Valid input, empty, not-gzip, truncated, truncated trailer, CRC flip, ISIZE flip, body flip, trailing garbage, two members, zero padding, **with the pin of those bytes**, on 03 and 08 | Identical outcome: the same rows, or the same exception class. The ledger is identical, and empty on every failure. |
| The same corruptions with the **good** pin | Neither scope ever admits them. A21 always raises `ValueError` (SHA) before gzip; frozen can raise gzip first. No caller branches on exception type (the A20 review checked this). |
| Partial consumer, consumer exception | Identical, with no ledger entry and the budget released. |
| Random 1–700-byte pipe dribble | The joined chunks equal the source bytes and the SHA, and the reads are coalesced into at most size/64 KiB + 1 chunks. |
| SSH exit 255 **after a complete correct stream**; half the stream then exit 255 | Both fail with no ledger entry. A21 raises `CalledProcessError` before yielding anything. The exact child is reaped and the lock is free. |
| Never-ending stream | A21 fails closed at the bound (bytes or time) **before yielding anything**. The child is reaped and the lock and budget are released. |
| Child exits 0 but a detached grandchild holds stderr | `TimeoutError` at the bound, fail-closed, lock released. **On the fleet this case does not occur:** on 01 (OpenSSH 8.2p1, the fleet build), the ControlPersist master-creating client reached stdout and stderr EOF at 0.378 s (`remote-size-scan.json`). The frozen `raw()`, which uses `communicate`, already depends on the same property. |
| Slow but steady stream | The bound covers the whole transfer, not idle time. With the bound raised to 30 s, it ends with the same `BadGzipFile` as A20. |
| Audit left/right pair on one host (the production nesting at `epoch_assembly_a18_v4.py:275`) | Identical rows and ledger. The 03 lock is **free** inside the pair under A21 but held under A20. The two snapshots share one aggregate budget, and the pair fails closed at one byte under that budget. |
| Remote `hashes()`, good pins and bad pins | Identical success ledger. Bad pins give the same `CalledProcessError` with no ledger entry. |
| **Local 04** records over every corrupt class, plus local 04 `read()` | Identical to A20. This matters because **A21 replaces `a20_io.io_locks` at runtime**: only `authenticate_a20` from A20 still runs (see C3). |

The author's 32 A21 tests cover the rest: unlocked consumption with private bytes, a guard abort, the stderr bound, script and reply bounds, symlinks, journals, wrong host, concurrent threads, restoration, the memory boundary, and the original-route ledger.

**Conclusion.** Every success A20 produces, A21 produces with identical bytes, rows and ledger. Everything A20 rejects, A21 rejects too, sometimes earlier and with a different exception class, and never admits evidence. As the draft states, A21 can also newly reject two things A20 would not: a transfer slower than 30 s and a snapshot over 512 MiB. Neither is reachable on today's data (§3, §5).

## 3. Timeouts (question 2)

| Bound | Frozen value | A21 value | New? |
|---|---|---|---|
| Remote metadata `read()` | `subprocess.run(…, timeout=30)` | 30 s from Popen | No |
| Remote `hashes()` | `subprocess.run(…, timeout=60)` | 60 s from Popen | No |
| Remote `records()` | **No bound while streaming**; `proc.wait(timeout=30)` only after consumption | **30 s whole transfer** | Yes |

**Real data.**
- **03 archive** (the A18 destination): 9,612 records, median **8.3 MB**, p99 27.5 MB, max **36.8 MB**.
- **08:** 1,629 records, median 9.5 MB, max 31.5 MB.
- There is no `.gz` over 256 MiB on 03.
- **Measured from 05 over the LAN to 03,** with 03 at load 58: 8.3 MB took 0.058–0.063 s and 36.8 MB took 0.226–0.25 s (about 150 MB/s), with a mux session costing 0.011 s and the first master 0.35 s.

So the records bound has **at least 120× margin** at the largest file. A failure needs a stall or partition on 03/08, not a large record.

**Fail-closed order.** The guard and the bound are checked on every loop iteration. On a timeout:
1. `TimeoutError` is raised;
2. `_cleanup` terminates the **exact** mux-client child (5 s, then kill, then 5 s) and closes its pipes; no shared master or other job is touched;
3. `one()` unlocks;
4. the `Snapshot` is closed and its budget released;
5. no `note` is written;
6. the worker exits nonzero;
7. `run_pool` writes `failure.json` (the error repr plus completed, active and pending epochs) and terminates the other owned workers, writing `exit.json` with `reason='retained pool abort'`;
8. the serial verifier is untouched.

`CalledProcessError` keeps 4 KiB of stderr.

**Cost.** A timeout fails the whole attempt: there is no retry, and a new attempt needs new approvals. That is safe but expensive. The probability is low given the margin.

**The bound also protects the serial verifier.** Under the frozen scope, a hung remote stream would hold `127x03.io.lock` forever and block the serial verifier. A21 caps every A19 hold at about 30 s. **Keep 30 s.** Changing it would mean a new adapter SHA and another review round, for no measurable gain (R2 adds a preflight check instead).

## 4. What the 04-side 03/08 flocks protect (question 3)

`LOCK_ROOT` is on 04's local NVMe (`/mpac/…/proofs`). So `127x03.io.lock` can only coordinate processes on **04**. The A20 review enumerated these: serial `run_stage` (on 04, 03 and 08), the queue verifier, A19, and the occasional queue or archive ops. The lock does three jobs:

1. **It limits remote load:** at most one 04-originated stream per remote host. A21 keeps this. The bytes per epoch are unchanged; they just arrive in bursts at link speed (about 150 MB/s, plus 03 sshd crypto for about a core while a burst runs) instead of being paced by the consumer.
2. **It linearizes against cooperating 04-side ops.** A21 holds the lock across the whole transfer, the exit and the SHA. A cooperating op therefore sees the same before-or-after cut, and A21 then holds immutable private bytes.
3. **It is not writer coordination on 03 or 08.** Nothing on 03 or 08 can take a flock on 04's disk. G, retention03 and the archive writers on 03 have never been serialized by it. Identity has always come from SHA pins plus owned-copy receipts, and a remote change mid-transfer still gives a SHA mismatch.

**Narrowing cannot race a remote writer in any new way.**

**Lost property.** Nested same-host calls are no longer atomic across files: the audit pair now takes two holds. Every records call is SHA-pinned, so this can't change results. O8 (no queue, archive or recovery op takes these locks during the attempt) still applies.

**Lock ordering improves.** A21 never holds any host lock across a `yield`, and never holds two host locks at once. That removes A19 from every wait cycle with the serial verifier.

**`ionice -c 3` does nothing here.** The NVMe scheduler is `none` on both 03 and 08. This is not a regression, since the frozen command has the same flag.

## 5. Memory (question 4)

| Quantity | Value |
|---|---|
| Snapshot budget | 512 MiB **per installation** (one per worker plus the controller), shared across 03/04/08 and across records, read and hashes |
| Worst case by design | 13 × 512 MiB = **6.98 GB** of snapshots, plus at most 512 MiB per process for a `blob()` join during metadata JSON (real metadata is kilobytes) |
| Real data | Largest nested pair ≈ 2 × 36.8 MB = 74 MB per worker, so ≤ 1 GB across 13 processes. `ChunkReader` makes no second compressed copy, and the author's tracemalloc test shows 8.54 MB peak for an 8 MiB snapshot. |
| Observed A19 owned PSS upper bound (first wave, 7 workers) | 0.51–2.58 GB, so about 4.5 GB at 12 workers |
| Total | About 5.5 GB real and ≤ about 30 GB at the design worst case, both **under the 48 GB A19 cap**. 04 MemAvailable was 127–130 GB during the first wave. |

The worker guard (`scan=False`) is called once per 64 KiB inside the lock. It costs microseconds plus a sub-millisecond `/proc` meminfo/PSI snapshot at most once a second, so it does not lengthen holds materially. The controller guard does scan, but the controller does almost no remote I/O. No policy change is needed.

## 6. Integration and the full suite (question 5)

**Full composed suite (my run).** I ran the README's command in the scratch tree under nice 19, using 3.12.12: **289 tests ran in 220.7 s, OK, 2 skipped** (`composed-full-suite.log`).
- One skip is the optional real-record opt-out.
- The other, `test_inventory_permission_error_on_smaps_propagates`, needs its cwd inside the repo. **I reran it from the repo root and it passed.**

So the result is 288 pass plus 1 optional skip, which reproduces the receipt. The authority tests now use the composed fixtures, which closes the gap that A20's C1 found.

**My tests** (§2): 12/12 PASS.

**The synthetic `hashes` figure, 163 → 31 ms, is an artifact.** `measure_lock.py` patches `json.loads` to burn CPU, so the reply parse looks expensive. In production that parse is trivial, and the whole remote hash runs under the lock in both scopes. **A21 does not shorten production `hashes()` holds.** The records and read figures show where CPU moved, but the hold in production is set by transfer time (§7), not by 7 ms.

## 7. Expected real speedup (question 6)

**My A20 review model was miscalibrated, and I am correcting it.** It used a probe of the 04-heavy seal child (03 hold 0.108). But **23 of the 24 epochs route most entries to 03.** I counted the assemblies in `a1-parallel-20261009-r5/final-packet`: epoch 1 is all on 04, and epochs 2–24 are mostly 03, with some 08 and 04.

**Owner data.**
- **First wave:** each A19 worker on epochs 3–7 held 03 about 10% of the time and *waited with the lock fd open* 80–98% of the time. Held 03 ÷ (held + unlocked) was 0.47–0.74.
- **12:16–12:40Z:** worker CPU was 5.7–16% per worker, about 0.55 cores in total. The serial verifier used about 0.72 cores and has blocking priority. The 03 lock is saturated.

**My split on real 03 records** (`remote-split-03.json`):

| Record | Consumer CPU (gunzip, json.loads, checks, SHA) | A21 transfer | Retained fraction *r* |
|---|---:|---:|---:|
| 8.3 MB median | 0.357 s | 0.060 s | about 0.14 |
| 36.8 MB maximum | 1.97 s | 0.23 s | about 0.10 |

Mux setup costs 0.011 s. A remote hash batch costs 0.036–0.052 s and is unchanged by A21. Per entry (9 records, 1 hash, 2 reads), *r* ≈ 0.18–0.2.

**Model.** `model_a21_speedup.py` is a time-stepped flock simulation. Work is per-process; serial keeps the full scope and is served first; A19 polls every 0.2 s. Its fraction of work under the 03 lock is *q*. Results are in `model-a21-speedup.jsonl`; rates are in serial-equivalents.

| Scenario, 12 workers | Serial | A19 | 03 lock utilization |
|---|---:|---:|---:|
| A20 today, q = 0.63–0.75 | 0.62–0.65 | **0.67–0.92** | 0.97 |
| **A21, q = 0.70, r = 0.18 (central)** | **0.92** | **2.2** | 0.92 |
| A21, q = 0.5–0.75, r = 0.12–0.30 | 0.85–0.97 | 1.4–5.4 | 0.81–0.95 |
| A21, 6 workers, central | 0.94 | 1.7 | 0.88 |
| A21, no serial (after supersession; never during A1) | n/a | 5.1–7.0 | 0.73–0.77 |

**Model check.** The A20-today rows give 0.67–0.92 serial-equivalents. At 12.7 serial-equivalent hours for A1, that is 1.3–1.7 epochs/h; the owner observed 1.07–1.8 epochs/h.

**Answer.**
- **Today:** A1 = 12.7 serial-eq h; the current attempt runs at about 0.8 and has 1/24 epochs done, so about 14 h remain.
- **A fresh A19+A20+A21 attempt:** 12.7 / 1.4–3.5 ≈ **3.6–9 h, central about 5.8 h**, with the 03 lock as the bottleneck (so throughput-limited, not a two-wave tail).
- **Serial:** it speeds up to about 0.9, but having started verifying around 11:33Z at about 0.65, it would not finish before about 02Z Oct-11.

So the replacement plausibly finishes A1 within the Oct-11 12Z allocation and many hours sooner than either alternative. That holds if O7/R2 pass. It is **not** "a few hours" in the 2–2.5 h sense: the remaining ceiling is the serial's frozen full-context, blocking 03 hold, which A21 cannot touch.

The next lever would be the owner's pre-staging or route alternative, so that A19 reads 04-local copies; the model puts that near the no-serial rate of about 5–7. It needs its own A18-route amendment and is not proposed here.

## 8. Conditions

### Before freeze (diff-only re-check, no code change)

- **C1 (blocking): record content.** Issue the A21 freeze and approval with **exactly** the key sets in §9. `authenticate_a21` rejects any extra key, including `template_only` and review SHAs. In the A19 freeze, set `final_combined_package_manifest_sha256` to 78e2a8b5… (currently `<PENDING>`) and add `a21_review_sha256`. Drop `template_only` from the A19 and A20 records.
- **C2 (blocking): deployment.** Deploy the 12 files plus the pinned auxiliaries into the **new** directory `/mpac/sdicks02/jobs/clasher/v4-a19-a20-a21-combined-r1/code`. **Never copy `a21_io.py` into the running `v4-a19-a20-combined-r2/code`.** Every new worker in the running attempt re-runs `authenticate()`, whose exact `*.py` glob check would then fail on each new epoch. The request's `verification_plan`, `a21_amendment` and script paths must point at the new directory. The base and composed runtimes must never run concurrently.
- **C3 (recommended, in the freeze record): erratum.** In the rebound A20 freeze (which allows extras), add a note: *"`a20_io.io_locks` is not installed in plan 327c958d; local-04 semantics are re-implemented in `a21_io` (A21 review §2, differential test 11); `authenticate_a20` remains enforced."* Also record that the synthetic `hashes` figure is not a production saving (§6), and that the expected rate is about 2–3×, not about 20× (§7).

### Before launch (operational)

- **O1–O9 apply unchanged**, with **O7 extended to the routed 03 and 08 records and metadata.** Record the maximum file size and the maximum nested pair per host, and require both under 512 MiB; today they are 36.8 MB and 31.5 MB. Add `max_remote_compressed_bytes_observed` `{127x03, 127x08}` to the operational approval as an extra.
- **O10: prior attempt's owned-exit receipt.** It must show all of the following:
  - the STOP provenance;
  - controller and 7+ worker identities, each with an `exit.json`;
  - the attempt's `failure.json` SHA;
  - the observer exit;
  - no live process with those identities;
  - **every `-a19-r*` ControlPath master** under `v4-a1-parallel-r2/sockets` has exited, through ControlPersist expiry or `ssh -O exit` on the owned socket path. The new attempt's ownership regex and its shared socket paths would otherwise count or reuse the old masters.
  - It must say that partial results are not merged.
- **O11: first-wave check.** Record per-lock hold fractions. Expect 03 still at about 0.9 or more, mostly serial, with A19 at about 1.5–3 serial-equivalents. Below about 1.2 means the model is wrong, so report to the coordinator. There is no automatic action.

### Recommendations

- **R1.** Leave A2 as it is. `completed_parallel_prerequisite` requires the same `verification_plan` **and** the same `operational_approval` descriptors, with `SERIAL_VERIFY_SUPERSEDED`, so a receipt from the A19+A20 attempt cannot satisfy A21's A2.
- **R2 (optional preflight).** One owner-run timed read from 04 of the largest admitted routed record on each of 03 and 08, through the pinned wrapper, should finish in ≤ 3 s. That is 10× inside the bound. If it is slower, the link is degraded, so don't launch.

## 9. Exact fields (question 7)

Throughout this section:
- *P* = `327c958dda9fa9a2dd6778e128590f91c3c35ed744d332ac2bedf8e3313aacaf`
- *B* = `0fe6fe3a1a864811e33e4b8358feea9157b4578771f2ff92237700b366ccfe72`
- *S* = the 12-file map in `source-pins.json` 9ae10990…
- *X* = the plan's `remote_io_lock_scope` object exactly: 17 keys, including `adapter_sha256` a1637caf… and `transfer_timeout_seconds` 30.

**Every SHA is the SHA of the issued bytes, never of a template.**

**A21 freeze.** It has exactly these 6 keys, and must be byte-value equal to `dict(common, decision='FROZEN')`.

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | *P* |
| `base_combined_plan_sha256` | *B* |
| `adapter_sha256` | `a1637caf0636d1e6462a08c0679f5a9806e5827db982ec98d0d60d24531e4b22` |
| `amendment_sha256` | `26b56a676c38194a94ea871dacb5a5f8a54d11ff30c554a188ab409138594517`, rehashed from the deployed draft |
| `remote_io_lock_scope` | *X* |

**A21 approval.** It has exactly these 11 keys, and is compared with `==`.
- `decision=APPROVE_REMOTE_IO_LOCK_SCOPE`
- `a21_freeze_sha256` = the issued A21 freeze's SHA
- `execution_plan_sha256`, `base_combined_plan_sha256`, `adapter_sha256`, `amendment_sha256` and `remote_io_lock_scope`, equal to the freeze
- `authorized_stages=["a1-verify","a2-build-bounds","a2-verified-bounds"]`
- `serial_runner_changed=false`, `B_authorized=false`, `heldout_opening_authorized=false`

There is no `hosts` key.

**Rebound A20 freeze** (extras allowed).
- Enforced: `decision=FROZEN`, `execution_plan_sha256=`*P*, `base_a19_plan_sha256=7d2a92bc06315c7a1fcabc2636c9818cec1784446ee35fd6b9b5399c28f4fc12`, `adapter_sha256=da583414af5554417cd58b2f199f6466fa54cd731163ec62540afc1ec12bc7f0`, `amendment_sha256=6b027d792f5a3baa2524725db34a05f3a23798c88fef363e39737064da36fc15`.
- Extras: `a20_review_sha256=c1e50fa4…`, `r1_erratum`, `source_pins_sha256=9ae10990…`, plus the C3 note.

**Rebound A20 approval.**
- `decision=APPROVE_LOCAL_IO_LOCK_SCOPE`
- `a20_freeze_sha256` = the new A20 freeze's SHA, which must also equal the request's `a20_freeze.sha256` and the operational approval's `a20_freeze_sha256`
- `execution_plan_sha256=`*P*, plus the same `base_a19_plan_sha256`, `adapter_sha256` and `amendment_sha256` as the freeze
- `hosts=["127x04"]`, `authorized_stages` = the three stages
- `serial_runner_changed=false`, `B_authorized=false`, `heldout_opening_authorized=false`

**Combined A19 freeze.**
- Enforced: `decision=FROZEN`, `execution_plan_sha256=`*P*, `source_files_sha256=`*S*, `amendment_sha256=2b09f87a742a072bcb411708a332331c9463669efb2465903c54b6a0efea3839`.
- Extras: `final_combined_package_manifest_sha256=78e2a8b5cb5240bc498bd637d767ec774c76b3c1f5fd56a4f0034e3f7ed2b5f1`, `a21_review_sha256=<this file>`, plus the template's `a20_review`, `r5_recheck` (90762bcb…), `review_response`, `base_r5_package`, `incorporated_amendment` and `source_pins` values.

**Revised `APPROVE_A1`.** It has exactly 8 keys.
- `decision=APPROVE_A1`
- `execution_plan_sha256=`*P*
- These six must be canonically equal to 19401ce4…:
  - `freeze_sha256` bd5b7643…
  - `file_layer_review_sha256` ff45e9ed…
  - `assembly_sha256` (24-entry map)
  - `evidence_recovery_sha256` 1adf50de…
  - `evidence_recovery_approval_sha256` 64b1ebe4…
  - `a18_bindings` (6-entry map)

The template's values are correct.

**Execution allocation** (`clasher.v4.execution-allocation.v1`; procedural, not code-enforced).
- `decision=APPROVE_EXECUTION_ALLOCATION`, `issuer=coordinator`
- actual `issued_utc` and `valid_from_utc`; `valid_until_utc` ≤ 2026-10-11T12:00:00Z
- host 127x04, worker CPUs 0–11, control CPU 47, reserved siblings, forbidden CPUs {52, 116}, the memory, disk and process caps
- fresh G/R3 vacancy and O1–O3 SHAs
- `previous_parallel_owned_exit_receipt_sha256` (O10)
- `existing_serial_fallback_unchanged=true`, `no_new_clasher_launches=true`
- A2 separate, B and held-out false

These are the template's values.

**`APPROVE_PARALLEL_BODY_VERIFICATION`.** Code enforces:

| Key | Value |
|---|---|
| `a19_freeze_sha256` | the A19 freeze SHA |
| `execution_plan_sha256` | *P* |
| `original_execution_plan_sha256` / `original_approval_sha256` | 68e24722… / 19401ce4… |
| `source_files_sha256` | *S* |
| `amendment_sha256` | 2b09f87a… |
| `handoff_policy` | `verify-then-retire` |
| `exclusive_physical_cpus` / `excluded_siblings` | `[0..11,47]` / `[64..75,111]` |
| `no_new_clasher_launches` / `x5_actual_exit_required` | `true` / `true` |
| `authorized_stages` / `hosts` | the three stages / `["127x04"]` |
| `seal_root` / `seal_binding` | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` / `authenticated-r4-exit-then-pin-actual-bytes` |
| `B_authorized` / `heldout_opening_authorized` | `false` / `false` |
| `a20_freeze_sha256` | A20 freeze SHA |
| **`a21_freeze_sha256`, `a21_approval_sha256`** | A21 freeze and approval SHAs |
| `valid_until_utc` | ≤ the allocation's, and ≤ the code cap 2026-10-13T04Z |
| `output_parent` | `/mpac/sdicks02/jobs/clasher/v4-a19-a20-a21-verification-r1` |
| `allow_serial_verify_handoff` | `true` (enforced by the launcher) |

These operational-approval fields are **procedural, not enforced by code**, so the coordinator must check them before issuing:
- `execution_cap_authority_sha256` (the actual allocation file)
- `previous_parallel_owned_exit_receipt_sha256` (O10)
- `issued_utc`
- the G/R3 vacancy, O1–O3, O7 and O9 SHAs
- `min_mem_available_at_launch_bytes=85899345920`
- `max_local04_compressed_bytes_observed` plus the new `max_remote_compressed_bytes_observed`
- `x5_supervisor_exit_required`, `r3_worker_exit_required`
- `body_seal_sha256`, `seal_exit_sha256`, and the O2/O4 receipts

**The request.**
- `verification_plan` = {new-dir `execution-plan.json`, *P*}, `amendment` = A19 r5 draft 2b09f87a…
- `a20_freeze`, `a20_approval` and `a20_amendment` (6b027d79…), plus `a21_freeze`, `a21_approval` and `a21_amendment` (26b56a67…, at the new-dir path); every descriptor must be a `{path, sha256}` pair matching the actual bytes
- `stage_approval=null` for a1-verify

**A2 later.** Each A2 stage needs its own `APPROVE_A2` with `verification_execution_plan_sha256=`*P*. Its prerequisite is either the genuine serial `seal-verification.json`, or the `verified.json` from **this** plan **and this** operational approval, with serial supersession. Nothing in A21 confers B or held-out authority.

## Summary

**APPROVE_WITH_CONDITIONS.**
- **Identity:** for every success, A21 gives the A20/frozen bytes, rows and ledger, and every failure class still fails closed. The parsed bytes are the hashed bytes. Tested over 12 adversarial classes, plus 289 inherited tests that pass.
- **Bounds:** 30 s and 60 s give at least 120× margin on real 03/08 records (max 36.8 MB at about 150 MB/s). Only the records bound is new, and it also protects the serial verifier from hung holds.
- **Lock:** its purpose is unchanged, and it never coordinated with remote writers.
- **Memory:** ≤ about 7 GB worst case, below the 48 GB cap.
- **Speedup:** about 2.2 serial-equivalents against about 0.8, so a fresh A1 takes about 4–7 h. That is not 2 h, because the serial verifier's blocking, full-scope 03 holds now set the ceiling; my A20 model was wrong on this point.
- **Conditions:** C1 (exact record keys), C2 (a fresh deploy directory, never touching r2) and O10 (an owned-exit receipt that includes the ControlPath masters).

## Reviewer artifacts (`reviews/a21-reviewer-artifacts/`)

| File | SHA-256 |
|---|---|
| `test_rev_a21.py` (12 tests) | `48d93eb3d6cb188fb92a5f027e624cd4aec51a3f9265047ff269ba878e247053` |
| `reviewer-tests.log` (12/12) | `7705b18b92fe5d1684de88b0d11a6bc340a670fa07ad10ba50ed8b61f251cf8a` |
| `composed-full-suite.log` (289, OK, 2 skipped) | `f66556e45edc61f9d789bc5b5f61b6b876aa08cc2551d431f1372784476f5df0` |
| `measure_remote_split.py` / `remote-split-03.json` | `0a996a735be569ffa37d6f6bf615e1ea5ae5036bd9aa50b1540050d4d332ac43` / `414e073b747b5d1002135c19d51b34ac816d2bf703bbd8624d4be1cc58a39720` |
| `remote-size-scan.json` (03/08 sizes, schedulers, ControlPersist stdio check) | `8868241b5935b2c311c17963be84494a85715a7f305b5f2f20c89e964b2459da` |
| `model_a21_speedup.py` / `model-a21-speedup.jsonl` | `517a255880c68f450bcafa8106c22441acfd11abce17f771ac55749f0a56d33b` / `deab2cb5879dc49079872bbee8e7e4911321b6f40e9454a6c4ba7468968113d5` |
