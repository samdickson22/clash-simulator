# Excluded scalar draw feasibility

The current natural training corpus has no draws, so its empirical draw prior is zero and the legacy representative gate refuses it. The protocol's old training draw controls used the earlier tensor backend. This probe checks the existing scalar backend's frozen-policy mirror mode before proposing new training controls.

Four physical runs are fixed: mirror seeds1281001 and1281002, an exact replay of the first, and a no-op terminal control at1281003. Both decks have the same fixed Hog order. The unchanged policy acts deterministically on both sides; only the final control overrides both actions to no-op. No physics, winner rule, RNG, weights or projection source is changed.

Keep every outcome, including non-draws. Capture one actor view per physical run, verify complete raw archives and the public814-feature encoder, and require exact replay results/arrays apart from case metadata and elapsed time. The replay is not an independent game.

All four runs are excluded from fitting, selection, calibration and final evidence. No-op results cannot establish natural-draw calibration or silently replace the declared frozen-policy mirror controls. No training follows automatically.

Run supervisor modes `pin` then `run`. All three Python files become immutable at pinning; outputs are exclusive and the shared18GiB guard applies. The failed natural-rule screen remains preserved unchanged.
