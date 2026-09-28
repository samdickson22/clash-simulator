This fixed comparison applies weighted-row sampling directly to both existing
margin architectures. The numeric model retains 425 inputs and 14,721 parameters;
the semantic model retains 809 inputs and 27,009 parameters. Both start exactly
at current tower margin. No auxiliary termination predictor enters either model.

Sampling draws the fitting-row count per epoch with replacement proportional to
the unchanged margin loss weights. Minibatches use mean absolute residual error.
The expected loss and gradient before clipping match the old objective. All
architecture, initialization, optimizer, clipping, batch-size, epoch/update count,
seed, fold and data choices remain fixed. Repeated-row exposure and gradient
noise change, so this does not isolate clipping alone.

The full memory gate retains both audited feature matrices, evaluation buffers,
the maximal sampling buffer, and synthetic optimizer steps for both models.
The numeric prefix must hash exactly to the original numeric matrix. Each model
runs two seeds and four family exclusions, for sixteen fits in total. WDL
probabilities and priors reuse the matching globals models.

The root output contains a manifest and completion record, plus `numeric` and
`semantic` directories with 30 artifacts each. Review every fit and all slices
before freezing all sixteen evaluations on the previously opened diagnostic.
Preserve old models, sources, reports and data roles. No policy work or acceptance
is authorized by this comparison.

Use this directory first on `PYTHONPATH`, followed by `hog26_terminal_auxiliary`,
`hog26_semantic_margin`, `hog26_public_semantics`, `hog26_residual_margin`,
`hog26_scaling_fit`, `hog26_data_scaling`, `hog26_scalar_pilot`, `src` and the root.
Publish with `prepare_plan.py`, run `weighted_supervisor.py --mode memory`, publish
readiness with `weighted_experiment.py`, then run the supervisor with `--mode fit`.
The September 13 output prefix is `reports/hog26_weighted_margin_`.
