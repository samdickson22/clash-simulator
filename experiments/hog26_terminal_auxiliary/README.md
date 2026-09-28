This auxiliary experiment tests whether the existing public representation can
predict actual termination in the next decision interval under the frozen
collection policy. It does not change or accept an outcome model.

The target audit checks that every complete training game has exactly one
positive row: its terminal tick follows the last predecision row by at most one
decision interval. Terminal timing and final-row membership are labels only.
Inputs are the exact 809 public columns from the completed semantic study.

The model has two 32-wide GELU layers and one Bernoulli logit. Its final weight
starts at zero and its bias at the logit of the fitting-weighted terminal
frequency. Training uses the same four family folds, two seeds, 30 epochs,
512-row batches, AdamW settings and phase-balanced mixture weights as the margin
study. Probabilities therefore target that mixture; both evaluation distributions
are reported separately. There is no threshold selection or epoch selection.

Five tests cover prior initialization, exclusion of held-out targets from fitting,
binary metrics and cluster duplication, refusal without memory readiness, and
rejection of ambiguous termination labels. The frozen plan requires a fresh
full-resident feature/label audit and synthetic BCE optimizer step. The supervisor
holds the shared lock and enforces the 18 GiB memory guard.

Only the existing 1,536 training games are used. All eight fits and every phase,
seat, style and family slice must be reviewed, including empty slices. No opened
diagnostic evaluation, reserved collection, policy update, or outcome prediction
change belongs to this auxiliary test.

Use the shared Python environment with this directory, `hog26_semantic_margin`,
`hog26_public_semantics`, `hog26_residual_margin`, `hog26_scaling_fit`,
`hog26_data_scaling`, `hog26_scalar_pilot`, `src` and the root on `PYTHONPATH`.
Publish the plan with `prepare_plan.py`, run `terminal_supervisor.py --mode memory`,
review the memory evidence and publish readiness with `terminal_experiment.py`,
then run the supervisor with `--mode fit`. All output paths use the
`reports/hog26_terminal_auxiliary_` prefix and refuse overwrites.
