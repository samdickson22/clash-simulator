# Training-only natural-rule screen

This screen separates failures of the declared natural-game rules from relative changes between model designs. It does not grant acceptance or permission to use reserved outcomes.

For each whole-family held-out fold and seed, it compares three margin forecasts paired with the same globals probabilities: the original joint tree, hard-phase experts and overlapping experts. It retains both the protocol's development opponent subset and all six training styles. All predictions come from completed exact OOF reviews; no model is fitted or selected here.

Representative rows go through the actual `scripts.hog26_public_slice_gates.evaluate_slices` function, with the matching fold's training-only prior. Full-phase rows use that module's original weighted outcome metrics and paired-cluster interval functions, with explicit equal-game-within-phase aggregation and unchanged thresholds. This uses the protocol's difference-of-win/loss-probability AUC definition, not the conditional-win-ratio score in research reports. Scalar terminal labels retain their stored precision.

The scope is limited to these natural-slice numerical checks. It does not test controlled draws, fresh validation families/seeds, one-time calibration, the reserved original-deck challenge or action ranking. Empty or under-supported slices remain failures. Metric failures and coverage failures are reported separately.

The duplication test verifies that extra rows cannot manufacture game mass or cluster coverage. Run `supervise.py --mode pin`, then `--mode audit`. All five Python files become immutable at pinning, and outputs are exclusive. No reserved dataset is read.
