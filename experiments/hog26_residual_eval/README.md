# Residual model review and opened diagnostic

This directory is separate from the frozen residual fitting source. The authority
checker requires all eight completed fits, exactly 30 artifacts, valid prediction
arrays, matching plan/readiness/feature authority and unchanged source. It also
checks that fold probabilities and OOF probabilities/priors exactly match the
existing globals references.

Run `review_residual.py --output <new-review.json>` first. Read and interpret all
folds, phases, families, seats, styles and joint slices in both distributions.
The review contains existing clustered intervals and point changes against the
scaled tree. It does not grant acceptance.

Then use `evaluate_residual.py --mode pin --fitting-review <review.json> --pin
<new-pin.json>` to freeze the checkpoints, completed review, evaluator sources,
reference predictions and diagnostic authority before prediction. The default
supervisor expects `reports/hog26_residual_margin_evaluation_pin_20260912.json`.
Do not edit these Python files after pinning while evaluation remains outstanding.

`supervise_residual_eval.py` runs all eight fits under the shared experiment lock
and 18 GiB RSS guard. The same 384 opened diagnostic games remain separate from
fitting. Every fit reports 288 fresh seen-family and 96 fresh excluded-family
games, all slices and both distributions. Its WDL probabilities are unchanged
globals references.

Every nonempty slice also gets a paired margin-MAE reduction interval against
the matching scaled tree fold, using 2,000 paired-scenario cluster draws and seed
1279511. Positive means lower residual-model error. The paired point must match
the published difference. Only the margin result is retained from the shared
paired-error helper; it receives identical globals probabilities for both inputs.
There is no new classifier comparison hidden in that calculation.

Final output must contain 18 files: one manifest, eight prediction archives,
eight reports and one eight-fit completion record. Preserve all partial outputs
on failure. Missing outcomes and sparse late coverage stay inconclusive; opened
diagnostics cannot authorize reserved collection, policy updates or promotion.

Required import path:

```sh
export PYTHONPATH='experiments/hog26_residual_eval:experiments/hog26_residual_margin:experiments/hog26_scaling_review:experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_scaling_fit:experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.'
```
