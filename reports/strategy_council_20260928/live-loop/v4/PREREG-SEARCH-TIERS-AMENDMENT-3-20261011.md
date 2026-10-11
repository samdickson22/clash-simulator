# TIERS Amendment 3: outcome-blind state-loading repair (E4-v3 memory)

Independent GPT-6.1-Sol review: **APPROVE** in round 4 of 4 (rounds 1–2 REJECT, round 3 APPROVE_WITH_CONDITIONS, every finding addressed); see the [review record](TIERS-AMENDMENT-3-REVIEW-SOL.md). Status: candidate pending adoption by the T1 worker and the coordinator.

Prepared 2026-10-11 on 127x05 by the E4 loading-repair implementer (coordinator thread 0523ae6f, assignment about 20:36Z). Branch `worker/e4-amendment3-loader-20261011`, parent `3cd0e58bd7ed1416e393f3d85ccfc4c653f86bad`. This is an operational repair of how replay states are held in memory. It changes no hypothesis, arm, seed, tier, slot count, warmup, OP-6 guard, 24 GiB floor, budget, threshold, gate or outcome handling. Preparation used public corpus fixtures, unit tests and offline single-process measurements only: no reporting outcomes, no timing run, no ssh to 01/03/04/08, no Mac access.

## Cause and measurements

`TierBackend.__init__` (`tier_backend.py` b04d201d) ran `pickle.loads((bundle/"states.pkl").read_bytes())`, kept every row in `by_id`, and kept a policy input for every row. The END fixture is 1,325 rows: T1's public 1,200 plus the separate golden125, SHA `0addf7c0…`, 11.65 GB. T1's receipt [`END-offline-backend-memory-01-20261011T2033Z.json`](../../../explore/t1/receipts/END-offline-backend-memory-01-20261011T2033Z.json) measured one backend on 01 at RssAnon 12,305,870,848 B (11.46 GiB), VmRSS 11.78 GiB and VmHWM 24.3 GB. The frozen reference spawns 11 independent backends (reference slot plus ten `FleetBackground` slots), which need at least 135.4 GB of anonymous memory, against a host MemTotal of 134.9 GB. With the frozen 24 GiB floor, 01 is short by at least 26.2 GB. On the Mac (24 GiB unified), the main backend plus D6's two sequential `forward_worker` backends need at least 23 GiB steady and about 34 GiB at peak.

Measured offline on 05 with the same fixture objects (nice 19, core 63, OMP/OPENBLAS/MKL=1, one process each):

| One TierBackend | RssAnon | VmRSS | VmHWM (peak) | Construction |
| --- | --- | --- | --- | --- |
| Before (`tier_backend.py` b04d201d) | 11.30 GiB | 11.38 GiB | 22.24 GiB | 30.2 s |
| After construction (Amendment 3) | 0.37 GiB | 0.46 GiB | 0.75 GiB | 33.6 s |
| After a 1,325-state lookup + admission probe | 0.41 GiB | 0.49 GiB | 0.87 GiB | |

Eleven amended backends need about 4.5 GiB resident, or at most 9.6 GiB if every backend hit its peak at once. With the 24 GiB floor that is about 34 GiB of 125.6 GiB, against the earlier shortfall. Receipts: [`receipts/amendment3-loader-20261011/`](mac-e4-package/e4v3/receipts/amendment3-loader-20261011/).

## Design

- **Converter (`convert_states.py`, one-time, Linux).** Each row of the pinned fixture is written, in the original order, as `pickle.dumps(row, protocol=5)` into `states-rows.bin`. `states-rows.json` records each row's offset, length, raw SHA-256 and canonical digest, plus the source `states.pkl` SHA. After writing, every row is re-read from disk through the backend's loader and must equal the original object, by canonical digest and by exact structural equality (`deep_equal`). `--expect-fingerprint` makes the run fail before any index exists unless the ordered fingerprint matches the reviewed one. The index is written with `source.verified: false`. Only a `--states` run, which unpickles the very file whose SHA it checked, atomically replaces it with the verified index, and only after every disk check and an input re-hash pass. A failed or interrupted conversion therefore never leaves an admissible index.
- **Loader (`state_rows.py`).** `StateRows` admits an index only if `states.pkl`, `states-rows.json` and `states-rows.bin` are all pinned in `tiers-pins.json` `files`. It also requires the index's source to equal the pinned `states.pkl`, `source.verified` to be true, and offsets to be contiguous with the container size. Each `load()` is a `pread` of one row whose SHA-256 must match before it is unpickled. `Rows` streams the fixture in order. `ById` is a `dict` subclass: a hit is the built-in `dict.__getitem__`; a miss loads that one state and drops the previously cached one.
- **`tier_backend.py` (constructor and `close()` only).** Construction streams every row once, running exactly the old per-row `validate_row` / `policy_input(verify=True)` work, including D1 exactness. It retains policy inputs only for `sets.agreement`, the only ids `infer()` is given by `measure_tiers` and K4S, or for all rows in a Linux dry run. `dry_opening_orders` is single-pass with the same result and error. In production profiles, openings are accumulated in the same pass. On a constructor failure, and in `close()`, the descriptor is released. `validate_bundle` additionally requires the two new files to be pinned. Every method that runs inside a decision (`work`, `_work`, `prepare_work`, `configure`, `policy_input`, `golden`, `belief_result`, `infer`) is byte-for-byte unchanged.
- **`prepare_bundle.py`.** It takes `--state-rows DIR`, copies the two files beside the copied `states.pkl` and SHA-binds them through `StateRows`. Staging, including Mac staging, never unpickles the corpus.
- **Byte-identical, with SHA unchanged:** `measure_tiers.py` 6066228b, `fleet_reference.py` c767a6e0, `replay_load.py` 1d0e12cc, `corpus_contract.py` e62b6df5, `receipts.py` 839a43be, `telemetry.py` 808d6fab, `spec-pins.json` 823d2e1d, and every kernel and scorer file. The frozen `states.pkl` stays pinned and byte-identical as the fixture's identity.

Options considered: (a) loading only each process's own ids saves little, because the reference and every background slot use 1,200 of the 1,325 states. (c) An mmap-backed format would let timed code fault pages in from disk, because `_work` reads row arrays inside the timer. (d) Parent load before fork: spawn is used, and reference counting defeats copy-on-write. Chosen: (b) per-state files with a SHA index, loaded on lookup, before every timer.

## Fixture identity

**Bytes are not reproducible.** Every public row holds `policy_rng_state`, a `torch.Tensor`. Torch pickles it through its legacy `torch.save`, which keys each storage by `str(storage._cdata)`, a memory address (`torch/serialization.py` line 1072 in the 05 environment). Pickling equal rows in two processes therefore gives different bytes, as reproduced in [`redump-diagnosis.log`](mac-e4-package/e4v3/receipts/amendment3-loader-20261011/redump-diagnosis.log). As a result:
- no re-dump can reproduce `0addf7c0`, nor the public `282b0877`;
- T1's `corpora.json` per-state SHAs record its capture process's bytes and cannot be re-derived from the objects (0 of 1,200 reproduce; ids and order do match);
- the golden125, which has no tensors, re-dumps byte-identically to `8b188918`.

**What is compared instead.** Row identity is the address-independent canonical digest. It covers types, values, float bits, in-row object aliasing, and each NumPy array's or tensor's dtype, shape, strides, bytes and backing-buffer sharing.

**05 evidence:**
- **Reconstruction (`conversion-05-reconstruction-r4.json`).** From T1's public file (`282b0877`) plus the golden file (`8b188918`), assembled as public + golden like T1's END script: 1,325 rows, all canonical-digest-equal and deep-equal on re-read. Order and ids are equal, and the ids equal T1's inventory. 63,450 arrays and tensors, none sharing a backing buffer. Ordered fingerprint `c09142b97ecc147efa635036a69508e16fe647347749e052d321048910040901`. Its index is `verified: false` and cannot be used in a bundle.
- **Verified `--states` run (`conversion-05-verified-states-r4s.json`).** Run on an independent 05 re-dump `states.pkl` (`a7c5cc24…`, different storage keys), with `--expect-fingerprint`: PASS with the same fingerprint `c09142b9…`. The fingerprint is therefore process-independent.
- **Old versus new backends (`equivalence-old-vs-new.json`).** The real b04d201d and Amendment 3 backends, on that verified bundle, with the frozen native kernel:
  - 1,325 ordered states equal, 33 openings equal, and all 1,200 policy inputs equal;
  - 15 sampled checks bit-exact: three golden rows (golden in K0c/K1/K2/K4, belief with and without deadline, zero-budget) and twelve speed decisions (three per tier), including the forward record and the root digest;
  - 54 checks that no call mutates a row;
  - the suspended-transaction totals are equal.
- **Cross-row sharing.** The original single pickle shared some objects across rows: 75 rows share frozen `PublicEvent` dataclasses and their `__dict__`, and 1,199 share `numpy.bool` scalars. Each per-state row now has its own copies. These are immutable values; no audited consumer mutates rows or keys a cache by row identity (the `history_cache` / `prepared_work` keys are id strings).

**Binding to `0addf7c0` (coordinator rule 8059).** T1 runs `convert_states.py --states <01 bundle>/states.pkl --states-sha256 0addf7c0… --assembled-sha256 0addf7c0… --expect-fingerprint c09142b97ecc147efa635036a69508e16fe647347749e052d321048910040901` on 01. The resulting `states-rows.{json,bin}` are the authoritative END container set, copied byte-identically to every host that uses that fixture. Container SHAs are process-specific by construction, so independent conversions are not interchangeable.

## Timing semantics

Nothing that is timed changed. Every caller looks a state up before its timer:
- `measure_tiers.decisions` / `deadline_corpus` and the `fleet_reference` deadline loops call `prepare_work(by_id[x])` before `entered`. The second `by_id[x]` after `entered` is a built-in dict hit, as unit-tested in `TimedRegionTests`.
- Speed, warmup and `FleetBackground` loops evaluate `by_id[x]` as the argument of `work()`, whose timer starts inside `_work`.
- `forward_worker` and `student_agreement` use inputs retained at construction.

Fleet lookups happen inside `guarded_block`, so the OP-6 guard still covers them.

Disclosed residual differences, all outside timers:

1. **Pre-arrival load time.** On 05, a lookup (`pread`, SHA-256, unpickle) takes median 1.8 ms, p90 16 ms, p99 0.22 s and max 0.31 s. Rows are heavy-tailed (median 2.05 MB; 89 rows above 20 MB; max 139.7 MB). Before, the same lookup cost about 1 µs. Admission (`prepare_work`) is unchanged: median 0.7 ms, p99 40 ms.
   - **D7/D8 decisions.** The load runs after the previous return and before `wait_until(due)`. A large state can make `entered` later than `scheduled`. The 200 ms budget still starts at `entered`, but `receipts.gc_summary` counts a late poll only when a GC event spans the scheduled instant.
   - **D8 GC labels.** GC triggered while loading the first state of a freeze variant is labelled with the previous trace context.
2. **Heap and GC.** A backend no longer holds about 11 GiB of fixture objects, so full collections traverse far fewer objects and per-state allocation and freeing adds collections outside timers. In-timer GC pauses are therefore not comparable with any pre-Amendment-3 receipt.
3. **Background duty cycle.** Fleet background slots spend their load time unpickling on their own pinned cores rather than searching. They stay CPU-busy; the frozen MHz comparison gate still applies.
4. **I/O and disk.** Bundles carry `states.pkl` plus `states-rows.bin`, about 2 × 11.65 GB for END. `validate_bundle` hashes both at session start and end. Eleven concurrent constructions stream the same container through the shared page cache, which is file-backed and reclaimable. Construction is about 34 s per backend, well within the 600 s readiness limit.
5. **Invalid fixtures.** For an invalid fixture, the order in which fail-closed errors are raised can differ. Accepted fixtures behave identically.

## Conditions for adoption (proposed)

1. **Same bytes everywhere.** END reference, A6 smoke, pooling and every Mac session use the Amendment 3 `tier_backend.py`, `state_rows.py`, `convert_states.py` and `prepare_bundle.py`, with `measure_tiers.py` unchanged at 6066228b. Mixed b04d201d / Amendment 3 populations cannot be pooled. Any reference or smoke prepared on b04d201d is void and is re-prepared, never patched.
2. **END regeneration.**
   - Convert on 01 exactly as above, with the fingerprint required.
   - Add `states-rows.json` and `states-rows.bin` to the 01 and 08 bundles; 08 receives byte-identical copies.
   - Regenerate `files`, `measurement_files` and `tiers-pins.json`, then repeat both C3 preflights and the offline one-backend memory check before A6.
   - The new manifest SHAs replace ac1da9c6 (01) and afd62c6f (08).
3. **Supplementary all-cause poll check (A3-P).** This is outcome-blind and computed from existing receipts only, with no code change. For every Mac tier and variant, using the poll rows in `decisions-tiers.jsonl` and `gc-freeze.jsonl` (`scheduled`, `entered`), report:
   - the rate of opportunity polls with `entered − scheduled > 25 ms`, whether or not a GC event overlapped;
   - the maximum lateness.

   A tier is Mac-feasible only if it passes the frozen GC/poll gate and also this all-cause check at the same thresholds (at most 1 %, and a maximum of at most 50 ms). An A3-P failure makes that tier **infeasible**, exactly like a failed frozen gate: the completed session and all its gate inputs are retained, and it is **not** a technical failure and grants **no repeat** (frozen Addendum §F excludes failed gates from technical failures). Fleet references have no scheduled polls and are unaffected.
4. **Mac bundle.** A Mac `states.pkl` that differs from the END fixture (golden125 + agreement2000 + packets1000 + speed 4×300) is converted once on Linux with `--states`, under its own reviewed fingerprint. The Mac stages it with `prepare_bundle.py --state-rows`; the Mac never converts. Per the Mac-session plan (48600567), the Mac runtime is re-staged from the Amendment 3 commit. Because `build_tiers.sh` binds `build-tiers.json` to the new `tiers-pins.json` SHA, the arm64 native build follows the new bundle in the same session.
5. **K4S companion (coordinator-owned).**
   - The K4S Mac manifest 8bb20a75 pins `tier_backend.py` b04d201d under `reused_readonly`, so it must be re-pinned to the Amendment 3 SHA, and `state_rows.py` added, under independent Sol review. The K4S END, pool and Mac declarations that consume a TIERS bundle must reference the regenerated bundle and manifest SHAs.
   - FROZEN-K4S 416f6e51 pins no e4v3 file.
   - Separately, `K4SBackend.__init__` (`k4s_backend.py`) still runs `pickle.loads(read_bytes())` on its own 300-state K4 corpus: about 2.8 GB on disk, about 3 GiB resident, about 6 GiB at peak. That is K4S's own memory and is not changed here.

The original [TIERS freeze record](PREREG-SEARCH-TIERS-FREEZE-20261010.json) (`47aba25e…`) and [Amendment 2](PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json) (`46d8c4be…`) are unchanged. The [amendment record](PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json) binds this note, the source hashes and the receipts. Amendment 3 does not authorize END, A6, outcome release or a Mac session; the T1 worker and coordinator decide adoption.

## Source changes

| File | Before SHA-256 | After SHA-256 |
| --- | --- | --- |
| `e4v3/tier_backend.py` | `b04d201de7a95a36669e5c11898a297ba8f324d1a658f2987ec5ba244671add7` | `02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d` |
| `e4v3/prepare_bundle.py` | `ad36c2020ab59ccafd91b3dbb03329a3fe1c2bb3b79d8b3d94b557d3daa6138e` | `a1c59fa3f9d546eaf212ef63fa3b3126bc039f4a86de384761832009e3cbe1bb` |
| `e4v3/state_rows.py` (new) | none | `3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755` |
| `e4v3/convert_states.py` (new) | none | `7ce306835410792534d9290e91001312d96babc8853925cd20b3ea7037520267` |
| `e4v3/tests/test_state_rows.py` (new) | none | `5888b1fb820c85327a0b68a945b00ea8f592536b9b4cd4f6175ad4ef8bf04477` |
| `e4v3/README.md` | `bb1471641598237915c17b8b4c0cc09027c34c9b56f52adc6912594a4a59ebfc` | `c9d20e21db673669ca044edfa5b56421a908a2e1d1ef19a566778a3529c521b3` |
| `e4v3/FLEET-INPUT-SCHEMA.md` | `1579ae2551bc54ace12ab6cd3b5c414ab6e84b46f84f6426a2bdec16725b1e5c` | `e5b51de9b9ebd1f00f1936963b1116bec586999b7e93e8379e8de4a085c9fb96` |

Tests: 91 pass on Python 3.8.10 (2 torch-only tests skipped) and 91 pass on Python 3.12.12 (torch 2.10.0+cpu, numpy 2.2.6). Before this change there were 70 tests; there are 21 new `test_state_rows` tests. Logs are in the receipts directory.
