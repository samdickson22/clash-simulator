# Overlap boundary components

This training-only audit is pinned before inspecting the overlapping model's results. It retains observed adjacent crossings of the three fixed gate centers and the two former phase boundaries.

At each crossing, it separates the forecast change into a gate contribution with head values held fixed and a head-prediction contribution with the later gate held fixed. It verifies their sum against the actual reviewed forecast change and checks the fixed-head bound of6 times normalized clock advance. It also reports actual changes from the hard-phase model, previous full-training tree and current-margin baseline.

Every reconstructed blended prediction must match the exact reviewed OOF bytes. Model files are checked through the scientific review and per-fold checkpoint hashes. No outcome target selects or scores a crossing. This describes predictor behavior; it is not an environment-action counterfactual, calibration result or ranking gate. The tree heads can still jump despite continuous weights.

Run `audit_boundaries.py --pin` before inspecting model results. Run `supervise.py` only after the overlapping comparison and exact/scientific reviews complete and release the shared lease. Both Python files become immutable at pinning; all output paths and failures are preserved.
