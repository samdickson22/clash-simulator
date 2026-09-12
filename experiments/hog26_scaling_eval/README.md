# Scaled-model diagnostic evaluation

Evaluate all20completed1536-game model fits on the existing384fresh-seed games.
No retraining, calibration fitting or selection occurs. This corpus was already
opened to diagnose the384-game pilot, so results remain diagnostic only.

Before opening diagnostic data, pin_fits requires complete globals/tree/entity
runs with the declared seeds, matching1536-game training inventories, source
hashes and vocabulary. Checkpoints, manifests and evaluation source are pinned
before predictions. Original fitting priors come from the exact384+1152training
completion manifests; diagnostic labels never contribute to the priors.

The evaluator preserves the previous transfer metrics, phase/representative
rules and paired-scenario bootstrap. Each fold reports288fresh seen-family
games separately from96fresh excluded-family games. All seeds/folds are retained.
Existing models and completed diagnostics are not overwritten.

Run evaluate_scaling.py with the original fresh-seed diagnostic --data, --plan,
--preflight and a new --output path. Add this directory, hog26_seed_transfer,
hog26_scalar_pilot and the repository src/root to PYTHONPATH. The expected
scaled fit directories are reports/hog26_scaling_{globals,tree,entity}_comparison_20260912.
This preparation has not been run against scaled models, which do not yet exist.
