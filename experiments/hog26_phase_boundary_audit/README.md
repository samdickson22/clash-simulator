# Phase-boundary audit

This inference-only training audit describes prediction discontinuity introduced by the fixed public-clock router. For each observed adjacent pair that crosses a phase boundary, it evaluates both adjacent experts at the identical last-before and first-after public states. Each expert excludes the entire family of the evaluated game.

The audit reproduces routed predictions against the exact reviewed OOF array and reports the switch size, actual adjacent prediction change, and current-margin change. It reads no outcome target for selection or scoring. Evaluating an expert outside its fitting phase is predictor extrapolation, not an environment-action counterfactual or a ranking test.

Pin `audit_boundaries.py --pin` before inspecting phase-model results. After the complete phase scientific review, run `supervise.py` under the shared experiment lease. All checkpoints are verified through the root scientific review, exact fold review, and artifact hashes. Both Python files become immutable at pinning. No model changes or acceptance decisions are made here.
