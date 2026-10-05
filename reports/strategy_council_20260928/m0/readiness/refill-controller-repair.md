# Scripted controller refill repair

The paired development v5 attempt stopped at tick 100 after the adapter correctly represented an empty HUD slot as card ID 0/confidence 0. `PublicScriptedOpponent` still required confidence 1 in every slot, including empty ones.

The controller now exempts only explicit ID 0/confidence 0 slots from that requirement. It continues to skip empty slots, uses the public legality mask, and preserves all present-card indices. Uncertain nonempty cards, partial-confidence empty tokens, and uncertain own elixir still raise. Full-hand scoring, tie-breaking and recommendations are unchanged.

The regression uses the actual saved tick-100 refill HUD and pinned native gamedata. `tests/fixtures/native_hand_refill_levels_15_535_86.json` preserves the measured body-level readings from the same frame, with its source SHA linked to the existing HUD fixture. No card or body level was inferred from nominal level 11 to make the test pass.

Validation: 56 focused controller/native-refill/readiness tests passed; Ruff and targeted diff checks passed. Restoring the old confidence guard in memory causes all three recorded-refill regressions (balanced, pressure and defense styles) to fail with the original error. See `refill-controller-counterfactual.json`. No source rollback, native call, emulator operation, or evidence reset occurred.

The failed v5 attempt remains unchanged. Reprepare a new execution plan against stable source pins before another development run.
