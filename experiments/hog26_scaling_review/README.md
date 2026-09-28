# Fixed scaling comparison review

These scripts read completed artifacts. They do not fit models, choose epochs,
change corpus roles, or establish acceptance. The running fitting implementation
is in `experiments/hog26_scaling_fit` and must remain pinned.

Run from `/Users/sam/.codex/worktrees/clasher-event-policy` with
`/Users/sam/Desktop/code/clasher/.venv/bin/python`.

`review_completed.py` requires the requested stages to have completion files,
exact file inventories, matching training authority, and valid prediction arrays.
It preserves all out-of-fold slices and their existing clustered intervals. It
also records every fold's fitting and excluded errors, and changes from the
original 384-game comparison. Those cross-corpus changes are point estimates on
different populations, not paired scaling-effect intervals.

After all three stages complete:

```sh
/Users/sam/Desktop/code/clasher/.venv/bin/python \
  experiments/hog26_scaling_review/review_completed.py \
  --output reports/hog26_scaling_completed_comparison_review_20260912.json
```

Read and interpret that report before running the inference-only evaluator in
`experiments/hog26_scaling_eval`. Also run the `fit_authority.pin_fits` check from
the September 12 handoff. The all-state and representative distributions both
matter. Missing coverage and subgroup regressions cannot be hidden by pooled
improvement. Preliminary stage reviews do not satisfy the full review requirement.

After interpreting the full fitting review, the evaluator can run through
`run_evaluation_supervised.py`. This wrapper acquires the existing experiment
lock, rechecks the review and fitting authority, refuses existing output, and
retains the 18 GiB process-group memory guard. It updates the shared supervisor
state and requires the exact 20-fit completion contract. Do not launch it while
fitting is active.

After the evaluator has completed all 20 scaled fits, run:

```sh
env OMP_NUM_THREADS=1 \
  PYTHONPATH='experiments/hog26_scaling_review:experiments/hog26_seed_transfer:experiments/hog26_scalar_pilot:src:.' \
  /Users/sam/Desktop/code/clasher/.venv/bin/python \
  experiments/hog26_scaling_review/review_transfer.py \
  --fitting-review reports/hog26_scaling_completed_comparison_review_20260912.json \
  --output reports/hog26_scaling_seed_transfer_review_20260912.json
```

This review requires the full fitting review, all original and scaled diagnostic
outputs, identical cohort audits, and unchanged pinned resources before corpus
access. It retains every model, seed, fold, distribution, and slice. Each fit must
have 288 fresh seen-family games and 96 fresh excluded-family games.

`paired_errors.py` computes paired scenario-cluster intervals for direct NLL,
Brier, and margin MAE reductions on identical diagnostic rows. Positive values
mean the scaled model has lower error. The comparison uses model NLL directly
because each model's prior gain uses a different training prior. Other metric
changes are point estimates. These are percentile intervals for individual
comparisons, not simultaneous intervals. Overlapping folds are not independent
replications. Fixed epochs with more games also increase optimizer updates.

Six synthetic tests cover identical predictions, sign reversal, repeated-row
invariance, constant margin improvement, empty slices, invalid probabilities, and
float32 checkpoint log-loss precision. Each computed paired point change must
match the corresponding published metric difference before intervals are reported:

```sh
env PYTHONPATH=experiments/hog26_scaling_review \
  /Users/sam/Desktop/code/clasher/.venv/bin/python -m pytest -q \
  experiments/hog26_scaling_review/test_paired_errors.py
```

Both review commands refuse existing output paths. Preserve prior reports if a
review fails. A revised report needs a distinct output path. The opened 384-game
diagnostic never becomes training or untouched acceptance evidence.

The additional paired analysis is frozen by
`reports/hog26_scaling_paired_diagnostic_review_plan_20260912.json`, including
every Python source in this directory. Both the inference supervisor and paired
review verify that pin. Do not edit these Python files after the plan is published
while the diagnostic and paired review remain outstanding. Preserve the plan and
outputs if a defect requires a separately documented revision.
