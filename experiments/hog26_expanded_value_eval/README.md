# Expanded model seed-transfer diagnostic

This is inference-only preparation for the already opened 384-game seed-transfer corpus. It does not authorize access to reserved selection, calibration or final cohorts.

The evaluator refuses to read diagnostic games until a separate published pin verifies the complete expanded fitting review and all model resources. All eight globals and eight paired-tree folds are evaluated. For each fold, 288 fresh games share its fitting families and 96 belong to its excluded families. Both evaluation distributions and every slice remain visible.

Expanded globals are compared with the old scaled globals at the same seed and fold. Expanded trees are compared with expanded globals at the same seed and fold and with the old scaled tree at the same fold. Every comparison uses identical diagnostic rows and a paired whole-scenario bootstrap.

After the full scientific fitting closeout, run `evaluate.py --mode pin`, then `supervise.py --mode evaluate`, then `supervise.py --mode review`. The review checks all 36 artifacts and independently reproduces checkpoint predictions, point metrics and paired intervals. The published pin freezes every Python file in this directory.

Synthetic tests cover refusal before data loading and prediction equality across an inference batch boundary. They do not establish real diagnostic success. No candidate is accepted by these scripts, and no model fitting or policy update occurs here.

The evaluation pin also follows the full completion-to-review-to-checkpoint hash chain. A changed checkpoint after review is rejected rather than newly fingerprinted as approved evidence. This gate is covered by a synthetic regression test.
