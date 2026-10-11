# PREREG-K4S END reference runbook (r3 §4.5 (a)–(c); delta 8)

**Status:** written and logic-tested (`test_end_reference.py`). **Not executed.**
- The frozen T1 K4 speed corpus (`K4-states.pkl`, sha256
  `a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8`, T1 inventory `81f2483e`) is stored only under
  T1 job directories (`t1-20261010-r1/corpus-reviewed-03-r1/built-corpora` on 03 and
  `corpus-publication-staging-r1` on 05). The prep worker may not read those directories.
- The coordinator must authorise one SHA-verified, read-only copy into the K4S job before END.
- END runs only after the committed reporting-completion receipt.

## Inputs
1. **TIERS fleet-reference bundle.** Build it with the frozen e4v3 `prepare_bundle.py` (profile `fleet-reference`,
   unchanged bytes) from the same staged K4S runtime. `TierBackend` checks every pin.
2. **Corpus:** `K4-states.pkl` at the sha256 above. `K4SBackend` refuses any mismatch and validates every row with
   the TIERS `corpus_contract`.
3. **Kernel:** `reports/explore/k4s-confirm/sdefault.py` with scorer `anchor_x.py`, the frozen K4S bytes.

## Per host (every host with counted blocks; slot 0 is the reference slot)
1. Load profile. Start the background corpus loop on slots 1–10 (8 with a console user) at nice 10:
   `end_reference.py --mode background --cores <slot cores> --stop $JOB/END-STOP …`
2. Reference. Run on slot 0 (cores 0–4) at nice 10:
   `end_reference.py --mode reference --cores 0,1,2,3,4 --out $JOB/end/raw-$HOST.json …`
   It makes 3 repeats over 300 states. Each repeat runs no-deadline K4 and K4S, then K4S at
   200/180/160/140/120 ms with the 1/c poll charge. MHz is logged at 1 Hz.
3. Touch `END-STOP` and verify that no owned processes remain.
4. The T1 OP guards apply as in reporting. The supervisor census and interference meters are recorded, and SSH-
   or DBus-flagged reference work is rejected.

## Pooling and recheck
- Pool with `end_pool.py --raw raw-*.json --out end-reference.json`.
- Each host's ratio to the pool must lie in [0.95, 1.05] inclusive, or the pool fails closed. One mechanically
  classified repeat is allowed. After that, re-run, or the coordinator declares the ratio unavailable (r3 §4.5).
- An independent re-check recomputes `end-reference.json` from the raw files (T1 `check_reference.py` pattern).
  Its sha256 goes into `end_recheck_sha256`.
- The pooled file is the fleet input of the K4S Mac script (`mac/K4S-MAC-PROCEDURE.md` §3, contract
  `clasher.k4s.mac-fleet-reference.v1`).
