# Rejected configuration-only pilot

This lineage is rejected at update 2 because the launch command omitted the
prior competence run's explicit `--no-lr-anneal` contract.  The trainer default
therefore decayed the learning rate from `1e-5` to `9.29e-6` at update 2.

The behavior evidence is encouraging but not attributable as a clean A/B:
placement cadence was 6.2% then 7.8%, PPO KL stayed below the stop threshold,
and the first completed episode was a win.  Preserve update 0-2 for audit only;
do not continue or promote them.  Restart from the retained parent with the
identical fixed learning-rate schedule and only the predeclared hazard-gated
temperature change.
