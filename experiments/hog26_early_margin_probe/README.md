# Focused early-margin assay

This training-only diagnostic asks whether public entity history improves held-family terminal-margin errors at the existing early representative of each of 6,144 games. Eight fixed absolute-error regressors compare the same 814 current/public-lag features with 911 features including audited entity history, across four whole-family folds. The learner uses one fixed seed; duplicate seeds provide no independent replication at this sample size with full feature selection and binning.

Every game contributes one point and equal weight. Targets are terminal margin minus current public margin; predictions add current margin and clip to [-1, 1]. Style labels only identify report slices. No private policy label or endpoint indicator enters a feature matrix.

The exact review reproduces every checkpoint prediction and fitting/excluded point report, then retains all 29 groups and seven paired comparisons with scenario bootstrap intervals. References are current margin and both previously reviewed full-training tree OOF predictions on these identical points. Comparing focused base with focused history isolates added features under this learner. Comparing either with full-training references also changes phase/sample allocation and binning and cannot isolate one cause. Intervals are unadjusted diagnostics.

The shared-lease supervisor pins all source and data authorities, exercises the full 6,144 × 911 matrix with synthetic regression targets under an 18 GiB guard, and then permits fit and exact review. Run its modes in order: `pin`, `memory`, `fit`, `review`. Outputs are exclusive and preserved. Once pinned, Python files in this directory must not change or be added.

This assay is not a full-phase model candidate and cannot authorize acceptance, policy updates, search, or reserved-data use.
