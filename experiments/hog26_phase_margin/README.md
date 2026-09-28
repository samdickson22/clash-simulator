# Public-phase margin comparison

The focused early assay improved with early-only fitting of existing features, while adding entity history worsened its overall outcome error. This separate full-phase comparison tests three fixed margin regressors routed by the existing public clock. It retains the 814 public features, original family folds, two matched seeds, absolute residual loss and tree settings. It introduces no private-style routing or entity-history input.

Each regressor receives all fitting rows in its existing early, middle or late phase. Original 50/50 uniform/representative margin weights are restricted to the phase and normalized to mean one. Predictions add public current margin and clip to [-1, 1]. The clock boundaries remain 1/3 and 2/3, with the right-hand phase selected at equality. Early and middle fit bin subsampling can vary with seeds; late has fewer than 200,000 rows and duplicate seed fits may be identical.

The same reviewed global model supplies WDL for each seed/fold. Exact review reloads all 24 new regressors and all eight unchanged globals, reproduces every prediction byte and point report, and creates held-family OOF reports using every original slice and both distributions. Scientific review preserves paired scenario intervals against current margin and the original full-training tree margin, with WDL held constant.

Three experts change capacity, phase allocation, weight scale and per-phase binning. The experiment does not isolate a single cause. Routing can be discontinuous at boundaries; model acceptance and counterfactual ranking remain separate gates. Sparse late support and absent natural draws remain explicit limitations.

The supervisor modes are `pin`, `memory`, then `run`. Pinning validates the entire reference hash chain and exact public-clock routing on all 2,465,152 rows. Memory exercises the largest fitting population for each phase with actual inputs, synthetic residual targets and full routed inference. Production needs 2 GiB headroom under the shared 18 GiB guard. Eight OpenMP threads are limited to fitting; inference and scoring restore one thread.

All output paths are exclusive and failures are preserved. Once pinned, no Python source may change or be added in this directory. No opened or reserved diagnostic data is accessed by this comparison, and no model or policy promotion is authorized.
