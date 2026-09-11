# Scalar pilot model comparison

This directory implements the predeclared training-family comparison. It does not authorize policy updates or final model acceptance.

Use the corrected pilot at `datasets/derived/hog26_scalar_pilot_seed1279261_20260911`, its `hog26_scalar_handfixed_frozen_plan_20260911.json` plan, and its matching preflight pin. The earlier seed1279221 pilot is rejected because hand aliases were unresolved. Do not fit it or repair its observations retrospectively.

`run_comparison.py` refuses partial collections. Before fitting it checks every game against the complete manifest, source and resource pins, independently reconstructed opening, exact metadata, public vocabulary, learner seat, label definition, and per-game audit. The model receives only the nine public fields listed in `PublicSequence`; metadata, labels, actions and success remain outside model inputs.

Run from the research worktree with `OMP_NUM_THREADS=1` and `PYTHONPATH=experiments/hog26_scalar_pilot:src:.`. Execute `--model globals` first, then `--model tree` with `--globals-output` pointing to the completed global run, and `--model entity`. All runs use the same frozen comparison JSON, complete corpus, collection plan and preflight pin. Output directories must be new.

The fixed comparison has two neural seeds, four whole-family exclusions and 30 epochs. The tree uses one seed and 100 iterations. It is a diagnostic comparison, with no epoch selection, calibration fitting, hyperparameter sweep or promotion. If natural draws are absent, draw learning remains inconclusive.

Tree sample weights have mean one over fitting rows, matching the earlier reference implementation while preserving the planned relative phase and representative weights. Neural losses use fixed expected-batch normalization. Cropping universally masked trailing entity storage leaves visible inputs and predictions unchanged.

The source-hashed synthetic benchmark verifies full-game backpropagation for two 750-step games at 128 entities. Model and training source changes require a new benchmark before fitting. See the tests for causality, padding, resets, excluded-label isolation and independent corpus-audit checks.
