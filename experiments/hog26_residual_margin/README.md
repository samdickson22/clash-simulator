# Public numeric residual margin baseline

This new baseline follows the completed fixed scaling study. The entity/history
model failed WDL transfer and did not beat the current-margin baseline on late
representatives even in its fitting data. The tree learned useful corrections but
still failed late representative and subgroup requirements. This experiment
tests a small residual predictor using the tree's existing public numeric inputs.
It is a new baseline comparison, not an isolated causal ablation.

The model has 425 inputs, two 32-unit GELU layers, and one linear residual output.
Its 14,721 parameters include a zero-initialized last layer. Before fitting, every
prediction therefore equals the public current-margin baseline. Prediction adds
the learned residual in float64 and clips terminal margin to `[-1, 1]`. There are
no time caps, endpoint overrides, or outcome-dependent switches.

Features preserve the existing numeric summaries and same-game global lags at
1, 5, and 20 decisions. The four hand slots retain the declared eight learner
cards plus the empty token. Client aliases resolve through the existing typed
vocabulary. Other hand columns must be zero; an unexpected visible learner card
refuses. Counts are divided by the fixed capacity 128, an exactly reversible
binary scaling. Entity identity embeddings and learned recurrence are absent.

The data remains the original 384 plus extension 1,152 complete games, with four
whole-family folds of 1,152 fitting and 384 excluded games. Both fixed seeds run
30 epochs with 512-row batches, AdamW at 0.0003, weight decay 0.0001 and gradient
clipping at 1.0. The margin weights are unchanged from the scalar comparison.
The matching saved globals fit supplies WDL probabilities. Those probabilities
are reference evidence, not another independently trained classifier.

The strict plan pins this directory's Python files, dependencies, data authority,
reference artifacts, feature layout and runtime. Do not edit these Python files
after publishing the plan while memory auditing, fitting, or subsequent source
verification is outstanding. Put later evaluation code in a separate directory.
Preserve failed reports and outputs; revisions need distinct artifacts.

Before fitting, run the full-corpus feature and memory probe. It validates all
input games, builds the actual feature matrix, prepares every fold's weights,
allocates full-size evaluation buffers, verifies exact baseline initialization,
and performs a maximal synthetic optimizer step. It saves no outcome model.
Readiness requires the exact successful report and source hashes. The fitter
rebuilds the features and requires their full matrix hash to match the probe.

Run from `/Users/sam/.codex/worktrees/clasher-event-policy` with:

```sh
export PYTHONPATH='experiments/hog26_residual_margin:experiments/hog26_scaling_fit:experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.'
```

Publish the plan after checks pass:

```sh
/Users/sam/Desktop/code/clasher/.venv/bin/python \
  experiments/hog26_residual_margin/prepare_plan.py \
  --output reports/hog26_residual_margin_frozen_plan_20260912.json
```

Use `residual_supervisor.py --mode memory` for the guarded probe. Then inspect its
completion and publish readiness with `residual_experiment.py --mode readiness`,
supplying `--plan`, `--memory-report` and a new `--output`. Only after that review
use `residual_supervisor.py --mode fit`. The supervisor keeps the shared experiment
lock, writes live state, refuses existing output and stops its own worker above
18 GiB RSS.

The final fitting output must have 30 files and an eight-fit completion record.
Review all seeds, folds, phases, families, seats, styles, joint slices and both
distributions before a separately frozen inference-only evaluation of all eight
fits on the already opened diagnostic. Keep existing calibration, draw, coverage
and counterfactual-ranking gates. This experiment cannot authorize reserved
collection, search, PPO, self-play learning, policy updates or promotion.
