# Smooth overlapping margin experts

This comparison follows the training-only boundary audit: hard phase switching changed predictions substantially at identical public states. Its configuration was recorded in `hog26_overlap_margin_training_hypothesis_20260913.json` before reading phase transfer feedback. Opened diagnostic results do not choose the data, features, weights or settings here.

Train24 fresh regressors: three experts, two fixed seeds and four whole-family folds on the same6,144 complete training games. Keep the814 public features and native HGB absolute residual learner/settings. Public-clock weights form triangular hats centered at1/6,1/2 and5/6, with endpoint hats constant beyond their centers. Each expert trains on every fitting-family row with positive gate weight, multiplying the original margin objective weight by that gate and normalizing to mean one. Native unweighted binning is retained.

At inference, clip each expert's current-plus-residual prediction to[-1,1] and take the public-clock convex combination. The gate is continuous for fixed head values. The tree heads can still jump; this does not prove forecast continuity, calibration or action ranking. Overlap also changes fitting support, weight scale and binning, so the experiment does not isolate a single cause.

The matching reviewed global checkpoint supplies unchanged WDL probabilities. Exact review reloads every checkpoint and reproduces every prediction byte and point report. It then reuses the identical WDL/bootstrap baseline statistics from the hard-phase reference while recomputing margin MAE/gain intervals using the original scenario draws. Five tests cover gate behavior and full bootstrap equality, including ties and undefined AUC. Actual training controls reproduce all240 reference slice/distribution/seed dictionaries exactly and verify changed-margin equivalence on all22,415 late states and325 late representatives.

Scientific review retains every original slice and both distributions, with paired comparisons against current margin, the previous full-training tree and the hard-phase model. No reserved or opened diagnostic row enters fitting.

Run supervisor modes `pin`, `memory`, `run`. Pinning requires the previous diagnostic's completed exact review as an execution prerequisite only. Memory tests each largest expert population using actual public inputs and synthetic residual targets, plus full routed inference. Fitting requires2GiB headroom under the shared18GiB guard. Eight OpenMP threads are limited to fitting; two exact reviewers run concurrently at one thread each under one aggregate guard. Signal cleanup stops only owned workers and preserves outputs.

All paths are exclusive. Once pinned, all Python files in this directory are immutable. Source-bound statistic proof files remain unchanged. No model acceptance or policy update is authorized.
