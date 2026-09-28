This fixed experiment appends public body statistics and crown proximity summaries
to the previous numeric residual model. The input has 809 columns, including the
unchanged 425 numeric columns. Two hidden layers of width 32 give 27,009 parameters.
The final layer starts at zero, so the initial prediction equals current tower
margin. The model fits terminal-minus-current margin on the same 1,536 training
games, four family folds and two seeds for 30 epochs.

This directory is separate from the completed numeric residual study. Once its
plan is published, preserve all Python files and pinned dependencies. The plan
requires the full public-only feature audit, then a resident memory probe with a
synthetic optimizer step, before training. The supervisor holds the shared lock
and enforces the existing 18 GiB limit. It never launches fitting automatically
after the memory probe.

WDL probabilities reuse the matching globals models. Compare margin results with
both the numeric residual model and tree across every recorded slice and both
distributions. Additional parameters and different initialization mean this is
not a pure causal test of added information. After all eight fits are complete
and audited, freeze a separate evaluator for all eight models on the already
opened diagnostic. No reserved data, policy updates or acceptance are authorized
by this experiment.

Run from the worktree with the shared Python environment and:

```sh
export PYTHONPATH='experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:experiments/hog26_scaling_fit:experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.'
/Users/sam/Desktop/code/clasher/.venv/bin/python experiments/hog26_semantic_margin/prepare_plan.py
/Users/sam/Desktop/code/clasher/.venv/bin/python experiments/hog26_semantic_margin/semantic_supervisor.py --mode memory
```

Review the memory report, publish readiness with `semantic_experiment.py --mode
readiness`, and then run the supervisor with `--mode fit`. Outputs use the
`reports/hog26_semantic_margin_` prefix. Existing outputs refuse overwrites.
