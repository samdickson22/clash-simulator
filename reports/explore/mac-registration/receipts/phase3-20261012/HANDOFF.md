# TIERS Amendment 4: Mac registration inputs, hand-off to T1 (merge and seal) and the coordinator

The Mac registration inputs builder (T1's corpus-owner delegate) built these on 127x05 on 2026-10-12, after Phase 2 (`fa8e700a`). Everything ran on `runtime-a5`, which carries the A5 bytes (A4 errata E2/E3), at nice 19 on one core with `PYTHONDONTWRITEBYTECODE=1`. Nothing was timed, no outcomes were read, and no `games/` was touched.

**T1 merges and seals.** This package grants no seal and authorizes no reporting or Mac session.

## What T1 merges into the reviewed `registration.json`

| Field / file | Source | SHA-256 |
| --- | --- | --- |
| `sets` (golden 125, speed 4×300, agreement 2,000, packets 1,000) and `packet_schedule` (1,000 entries) | `mac-sets.json` (this directory; also `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/selection/mac-sets.json` on 05) | `72d83033051b2fae1bf53e1dca13e4570700374c1e66c161a948be6969e8ce50` |
| `student-reference.json` (2,000 agreement ids; the `TierBackend.infer(id,"cpu")` format) | 05: `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/reference/student-reference.json` (27,314,150 B) | `7a90fa7a16d38a568ed4b08a0ca971afde7ec9830a920f4e755e8901402fd165` |
| B.7 receipt `mac-sets-selection.json` (all checks true) | this directory | `f3b87ce58ca475e4a5a1901737afe7e54da73674c4b2b3abe6ea66c62a174f38` |

## Mac fixture: converted on Linux, staged by the Mac operator (A3 condition 4; `stage_nocopy.py` 166a1636)

| File | Path on 05 | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `states.pkl` | `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/assembly/states.pkl` | 20,710,108,933 | `afdbd237d65897816b2683335c823fdf2557fa1640256acc892ee967368684a7` |
| `states-rows.json` | `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/state-rows/states-rows.json` | 568,325 | `49cbe56ce9c3df18ae85616d09a481f5113cf7aa29bbed2c8aaca4fcb329f63d` |
| `states-rows.bin` | `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/state-rows/states-rows.bin` | 20,712,961,718 | `dc92bf459a337410b53cc5b2313286121542d7137b190493789126af6739b353` |

**Fixture identity:** the ordered canonical fingerprint **`0de6995803380052a0d1618107e6c6566f9afbd9e35901808e5b59f3f3e05e05`**, over 2,125 rows. These are the 1,325 END rows (prefix equal to END `c09142b9`) followed by 800 extra rows. The fingerprint is enforced by `convert_states.py --states --expect-fingerprint`, which returned PASS with `source_verified: true`, and all rows were canonical-digest-equal and deep-equal on re-read. The pickle bytes are process-specific; only the fingerprint identifies the fixture (Amendment 3).

## Evidence (this directory)

**Selection (B.1–B.4).** Receipt: `selection-stage.json`.
- **Pool:** 4,242 rows (K0c 1,275, S 1,156, K2 883, K4 928), 0 invalid. Retained equals counted in every capture, and counts and health equal `corpora.json`.
- **Lineage:** all 1,200 speed rows are canonical-digest-equal to END.
- **Packets:** 9 games, in this order: K0c-8, S-3, K2-10, K4-6, K0c-7, S-7, K2-7, K4-5, K0c-6. The last game is truncated at 43 rows.
- **Schedule:** 1,000 polls, last offset 1,459.5 s (mean gap 1.46 s). One D7 or D8 pass is therefore about 24.3 min, shorter than the proposal's 30–40 min estimate.
- **Agreement:** speed ∪ packets is 1,931 rows (overlap 269), plus a fill of 69 (K0c 22, S 20, K2 13, K4 14), for 2,000.

**Assembly and conversion (B.5).** Receipts: `assembly.json`, `fixture-digests.json`, `conversion-receipt.json` and `states-rows.json`.

**Independent reproduction.** Receipts: `independent-reproduction-comparison.json` and `repro-haiku/`.
- Haiku 5.5 (max effort) wrote its own code and had no access to the builder's code or outputs.
- Its packets, schedule, agreement, fixture ids, all 800 extra-row digests, fill quotas and fingerprint are **identical** to the builder's.

**Student reference and B.6 cross-check.** Receipts: `student-reference-receipt.json` and `student-cross-check.json`.
- Computed on 05 (CPython 3.12.12, torch 2.10.0+cpu, numpy 2.2.6, 1 thread).
- Against T1's pooled **A5** END S forwards (`end-a5-pooled-reference-r1/speed-reference.json` `fe534ec0…`, committed pool manifest `95774e86`), it **passes, 300/300 bit-exact**: max |Δgate| = 0 and max |Δlogit| = 0.

**Mac-profile memory check (blocking).** Receipts: `mac-profile-memory.json` and `child-{1,2}.json`.
- It **passes:**
  - the main process plus two sequential D6 children, each retaining exactly the 2,000 agreement inputs and running 2,001 forwards;
  - conservative summed VmHWM **2.88 GiB**, against a 6 GiB cap;
  - sampled concurrent peak 1.60 GiB;
  - per process: main 1.02 GiB, each child 0.93 GiB.
- These are Linux CPU RSS numbers and stand in for the Mac's footprint; the Mac session's own receipts remain binding.

## Notes

- **Phase 2:** the 32 captures stay on 05 under `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/captures/`. They are SHA-verified (`fa8e700a`) and will not be published.
- **The offline work bundle** (`reference/bundle`, manifest `work-bundle-tiers-pins.json`) is a builder artifact and is not for staging. The Mac stages through `prepare_bundle.py` via `stage_nocopy.py`, from a runtime re-staged from main `8799a0d6` or later (E2).
