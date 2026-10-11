# Sol diff-only check: TIERS Amendment 4 erratum E1 (test portability)

Reviewer: gpt-6.1-sol (high), via T3 `delegate_task` `macreg-a4-sol-erratum-e1`. It was requested about 23:21Z and had completed by 23:24Z on 2026-10-11.

Scope: the `tests/test_stage_nocopy.py` change (`f75cd3a3…` → `b540df82…`), plus the erratum record in the A4 md and json.

## Sol's text (verbatim)

VERDICT: APPROVE

1. **The diff exactly matches the test change.**
   - `/tmp/macreg-erratum.diff` is the test change and nothing else.
   - On Linux the test requires `hardlink` and equal inodes. On Darwin it requires `apfs-clone` and different inodes.
   - The method in the receipt must match the method from `verify_bundle`.
   - The byte-identity and fail-closed assertions remain intact.
2. **The helper is unchanged.** `stage_nocopy.py` is byte-identical to `94df513d`; both SHA-256 values are `96abd8474d6410d6ba4342889e18d5caed5b455417535d44440d676041f653c7`.
3. **Only permitted files changed.** The baseline comparison found changes only to the test, the record generator, PROGRESS.md and the unit-test receipts. `errata.json` is the only new source record.
4. **The records are accurate.**
   - E1's before, after and helper hashes are correct.
   - The JSON errata entry matches `errata.json`.
   - The note and all 19 source hashes match the current files.
   - The prior review is preserved, and the status is ADOPTED.
   - The Mac receipts support the stated diagnosis.
5. **Tests pass.** Both requested suites passed 38/38 with no skips, on Python 3.8 and 3.12, under `nice -n 19 taskset -c 62`. The Darwin assertions were reviewed statically against the Mac evidence supplied.
