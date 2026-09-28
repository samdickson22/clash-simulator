This comparison changes the sampling estimator of the completed auxiliary
termination experiment. Each epoch draws the fitting-row count with replacement,
with probability proportional to the original loss weights. Each minibatch uses
ordinary mean Bernoulli loss. The expected unclipped loss and gradient are the
same as the original importance-weighted objective.

Architecture, fitting priors, initialization, optimizer, clipping threshold,
batch size, 30-epoch update count, two seeds, four family folds, data and metrics
remain fixed. Replacement sampling changes repeated-row exposure and gradient
noise, so the comparison cannot isolate clipping from all other sampling effects.

The preceding exact replay reproduced the original checkpoint and found that
late representative examples retained much less of their weighted logit
derivative after clipping than nonterminal examples. That observation motivates
this fixed test; it is not an acceptance result.

Before fitting, the frozen plan requires a fresh full-resident memory check that
also allocates and exercises the largest 474,642-draw sampling buffer. The shared
supervisor enforces the existing 18 GiB guard. Preserve all source after publishing
the plan. Run all eight fits and review every slice, comparing against both the
original sampler and the fitting-only phase reference. No existing outcome model
changes, opened diagnostic access, reserved collection or policy work is included.

Use this directory first on `PYTHONPATH`, then `hog26_terminal_auxiliary`,
`hog26_semantic_margin`, `hog26_public_semantics`, `hog26_residual_margin`,
`hog26_scaling_fit`, `hog26_data_scaling`, `hog26_scalar_pilot`, `src` and the root.
Publish with `prepare_plan.py`; use `sampled_supervisor.py --mode memory`, publish
readiness through `sampled_experiment.py`, then run the supervisor with `--mode fit`.
