This directory prepares the complete 6,144-game training corpus for separately
gated fitting. It does not read combined training arrays until the 4,608-game
parallel expansion is complete and its preserved sequential prefix passes exact
array comparison. Original training and extension inventories must remain exact.

The authority check independently reconstructs all three source fingerprints,
opening schedules, initial hands and public mask metadata. It rejects overlapping
relative-deal clusters, missing games, changed bytes and rejected actions. Every
game is audited again before its public arrays and terminal targets are exposed.
Only the nine declared public arrays enter feature construction.

After full completion, `prepare_cache_plan.py` freezes the extraction source and
input inventory. `cache_supervisor.py` runs `build_cache.py` under the shared lock
and 18 GiB guard. It streams the unchanged 809 public features to an owned file,
preserves every row, checks both original 1,536-game prefix hashes, and verifies
random batch reads. Labels and game metadata are stored separately. This is an
extraction audit, not training readiness or model acceptance.

`cache_reader.py` maps the verified file read-only. Scenario hashes are encoded in
lexicographic order to preserve bootstrap grouping while avoiding repeated long
strings on every row. Future training must copy selected batches before giving
them to mutable tensor operations and must pass its own full-size memory gate.

`fast_weights.py` computes the existing weighting formula with indexed groups.
Its synthetic checks require exact equality with the original formula, including
shuffled rows. `probe_existing_weights.py` verifies all four existing training
folds before this optimization is used in a larger experiment.

Use this directory, `hog26_streamed_features`, `hog26_parallel_expansion`,
`hog26_parallel_collection_probe`, `hog26_training_expansion`,
`hog26_data_scaling`, `hog26_terminal_auxiliary`, `hog26_semantic_margin`,
`hog26_public_semantics`, `hog26_residual_margin`, `hog26_scalar_pilot`,
`src` and the root on `PYTHONPATH`. Preserve all Python here once the extraction
plan is published; future fitting code belongs in another directory.
