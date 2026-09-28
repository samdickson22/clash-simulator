# Expanded public outcome comparison

This experiment fits a tree W/D/L classifier and an absolute-error residual margin regressor to the audited 6,144-game training corpus. The unchanged GlobalWDL model provides a probability baseline. Both use seeds 1279501 and 1279502 with the existing four held-family folds.

The candidate uses the frozen 809 public features plus five current tower-health aggregates. No terminal flag, time to the actual endpoint, or auxiliary termination prediction enters the model. Trees retain the original mean-one fitting weights; the globals baseline retains uniform batches and importance weights.

The column-contiguous fitting matrix preserves public feature values. Synthetic checks establish exact globals parameter updates against the original trainer and exact tree predictions across storage layouts. The full-size actual-loss memory probe uses synthetic targets only. Production keeps the 18 GiB process guard.

Run `prepare_plan.py` only after the independent cache review and memory receipts pass. Its published source pins make this directory immutable. `supervisor.py` then runs all 16 fold bundles (24 estimators) and four exact checkpoint/metric reviews. Each review retains both evaluation distributions, every slice and 2,000 whole-scenario bootstrap replicates.

The comparison changes training support, candidate representation and architecture together. It does not isolate the causal effect of more data. There are no natural draws in this corpus, and no model is accepted by this experiment alone. Opened diagnostic evaluation requires a separate plan after the complete fitting review; reserved data roles and calibration/ranking gates remain unchanged.
