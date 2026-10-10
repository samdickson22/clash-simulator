T1 corpus contract ruling recorded 2026-10-10T18:06:53Z.

The coordinator's committed-contract ruling (message coord-t1-corpus-contract-ruling-20261010-1, actual 2026-10-10T18:05:42.512Z) supersedes the earlier row-contract relay. E4 fleet review r2 efa54f44 and PREREG Amendment 1 §A1.3 govern: exactly 20 top-level fields, a committed posterior copy with `_pending=None`, and `belief_had_suspended_transaction`. Both platforms replay the full public-history update without suspended-progress credit. Tick remains `info.tick`; no `belief_resume` or top-level tick is implemented.

The excluded-game corpus candidate a51ea64cb878ca05bf38a8145174e6d2b9f46d7a already follows this contract. Static comparison of run.py's pre-poll capture fields and corpus_capture.py's returned fields equals corpus_contract.REQUIRED_ROW exactly (20/20). It preserves physical info.packet, reserved_packet, ordered pending reservations, d1_before/full d1_events/post-update d1, public sampled opponent, RNG witnesses, root bytes/digest and strata. Independent capture reconstruction runs after the live timer regardless of whether the live decision reached root, preserving eligible cutoff opportunities. corpus.py uses E4's unmodified validate_row and validate_capture_receipt before output admission.

Its existing six unit tests passed on01 before reporting, with no production games or corpora; source hashes still match that receipt. The corpus capture fix remains isolated and unadmitted pending independent confirmation. Production 300-state corpora will come only from qualification/smoke-class games in a separate reviewed capture namespace. This ruling requires no source change to the candidate and no change to the running sealed reporting job.

Committed authority SHA-256 pins:

- reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/corpus_contract.py: e62b6df5f4ad245a92f39a4546329dc13b183e881c9a58757f6c4a0f9ac6880c

- reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/FLEET-INPUT-SCHEMA.md: af0a5a50860794bbdd20753bc0e2f44503e7eb7e69210b3fc008494fa36c7bb4

- reports/strategy_council_20260928/live-loop/v4/PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md: b35bd4e5d8beaf8e89ade092bdf4fc607e067e562f7d9f378fb9c06367df2775
