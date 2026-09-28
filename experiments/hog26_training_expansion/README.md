This draft expansion adds 4,608 complete training games to the existing 1,536.
It keeps the same 32 training-family decks, six opponent styles, both learner
seats, fixed policy and simulator/public projection. Twelve new paired scenarios
per deck/style give 2,304 additional independent deal clusters. All scheduled
games and decisions are retained, regardless of outcome or duration.

The schedule rejects overlap with the original training corpus, its earlier
extension, opened diagnostic games and historical excluded preflights. The new
twelve-game preflight is excluded too. Reserved roles and calibration/ranking
requirements remain byte-for-byte equivalent to the original protocol.

Collection is disabled until preflight completes and `publish_plan.py` audits
its inventory, source/schedule metadata, actual terminal flags and action results.
The supervisor holds the shared lock, enforces 18 GiB RSS and writes distinct
attempt logs. Matching partial collections can resume explicitly; completed
outputs cannot be relaunched. No completion authorizes fitting.

Future combined-corpus loading and feature construction belong in a separate
directory. They must verify all 6,144 games and prove memory readiness without
truncating entities or trajectories. File-backed features may be needed. Do not
add future loader code here after preflight has frozen the collection sources.

Run from the worktree with the shared Python environment and
`PYTHONPATH=experiments/hog26_training_expansion:experiments/hog26_scalar_pilot:src:.`.
First run `expansion_supervisor.py --mode preflight`. After review, publish the
pin and plan with `publish_plan.py`, then run the supervisor with `--mode collect`.
All campaign outputs use `hog26_training_expansion` and the date `20260913`.
