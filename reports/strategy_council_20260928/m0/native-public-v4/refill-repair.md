# Sparse native hand during refill

The opened development branch at tick 100 exposed a serialization defect: owner 1's native HUD contains hand slots 1, 2, 3 while slot 0 is refilling. The coordinator recorded its continued absence through tick 110 and its return at tick 111. The failed attempt remains intact. This repair makes no change to card refill physics.

The native adapter now accepts sparse lists of distinct integer hand indexes 0..3, writes each card to its original slot and leaves absent slots at ID 0/confidence 0. It reads the visible next card only from the explicit `nextCard` source and retains it in slot 4. Public masks forbid absent hand slots. The independent reference checker now builds the same fixed five-slot expectation rather than compacting a sorted list and requiring confidence 1 everywhere. Missing or malformed hand data, duplicate/out-of-range/untyped slot indexes, unsupported card IDs and missing next-card data still fail.

`tests/fixtures/native_hand_refill_15_535_86.json` preserves the actual ordinary snapshots at ticks 100, 110, 111 and their source hashes. The test uses the exact full capture ruleset, bundled losslessly as `native_gamedata_15_535_86_daa58b28.json.gz` and checked against SHA256 `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3` when decompressed. No production or test-only gameplay-stat overrides are applied.

The pinned native profile differs from workspace defaults for two cards in the 16-card scope: Goblins base damage 49/scaled 125 instead of 47/120, and IceSpirit base HP 84/scaled 215 instead of 90/230. Only IceSpirit is among the visible bodies in these frames. This ruleset difference is separate from the refill repair and must remain explicit when relating reference admission to a learning configuration.

Validation: 85 focused tests passed in 3.05s, including 11 new cases. The real frames preserve slots 1–3, the original next-card slot and zero-confidence empty slot 0; the returning slot 0 at 111 has its actual card identity and confidence 1. That card remains unaffordable at 2.9758 elixir, so the test does not incorrectly demand a legal play. Archive round-trip, checker corruption detection and malformed-HUD rejection are covered. The old test treating any shortened hand as malformed now tests an actual out-of-range index instead. Focused diff check passed.

No native requests, emulator changes, native reader/probe edits, training or acceptance collection were performed by this repair. Only adapter/checker/test source changed; the coordinator owns the new development attempt.
