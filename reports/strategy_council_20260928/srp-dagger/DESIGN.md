# SRP DAgger pilot

One iteration, 40 complete games, two single-threaded workers at nice 10. All new
code and training artifacts stay in this directory. Evaluation cells go in the
existing human-prior-p16/evaluation directory under distinct srp-dagger names.
Use the workspace Python engine and repo .venv. No engine or shared learner edits.
The coordinator found two workspace data values that differ from admitted P16
values. The entire old cohort, fit and evaluations are archived and excluded.
The replacement pilot waits for GAMEDATA_CANONICAL_READY, verifies the canonical
data, then collects all 40 games with `backend="native"`. Future collection also
defaults to native. The live game and student builders still use the workspace
engine. Native sources and extension are pinned to verified receipts. One full
game is played with each backend on canonical data before collection; both QA
copies are excluded from training and cost-per-game estimates. Initial and final
evaluations both use canonical data and fresh receipts.

## Collection

Initialize the stochastic public recurrent student from v7r4h seed 2902 at 1M.
Use five-tick decisions, level 11, full 6001-tick horizon, both seats, balanced,
pressure and defense public scripts. Sample opponent decks from training.json.
Use 14 Hog 2.6 games and 26 training-pool games. Seeds start at 880031, separate
from evaluation. Execute the teacher action with probability 0.5, otherwise the
student action. Advance student recurrence at every boundary with the previously
executed action and zero previous reward.

Query privileged srp_xm at EVERY playable student boundary, including wait labels.
Its search settings are horizon 160, rollout interval 10, samples 16, script top 4,
balanced public continuation and StrategyBot balanced opponent model. Root actions
must satisfy both engine and public masks. Qualification used plan_every=2 as an
execution cadence. Here the explicitly requested every-boundary labels use cadence
1 on the same five-tick grid; record this difference and measure its cost.
Collect candidate IDs and values by wrapping _rollout locally, without repeating
search or changing tie order. These privileged targets never enter policy inputs.

Reuse the eval environment and deck setup, dagger_behavior actor, public packet
and mask builders, PublicPolicySequence and ScriptedGameDemonstration NPZ schema.
Keep forced-wait rows as recurrent context and a final unsupervised terminal row.
Supervise only queried legal labels. Keep executed actions separately from labels.
Publish complete games atomically; resumptions skip only validated complete games.

## Fit

Aggregate complete games, split by game with a fixed seed, 32 training / 8 held out.
One fit of three epochs, AdamW learning rate 1e-5, CE on teacher actions including
wait, plus 0.1 KL(student || frozen initial student). Use the existing full-prefix BC recurrence helper with chunk 64 and complete
tail coverage. Reconstruct both states from the full executed history before each
chunk. The TBPTT README has passing tests but does not declare readiness and its
A/B acceptance is still open, so the requested fallback applies. The frozen initial policy is replayed through each complete training game once;
its reference logits are cached on the same executed history. The first optimizer
batch checks that initial student-to-reference KL is near zero. Full recurrent held-out replay supplies CE and top-1 agreement each epoch.

The shared fitter's anchor helper computes KL(initial || student) and resets the
anchor at chunk boundaries. A small local fitting loop will reuse its loaders,
sequence inputs, full-prefix reconstruction and checkpoint format while implementing the requested
KL direction and correct anchor recurrence. No shared fitter changes are needed.
Use two Torch threads for the sole fit process after collection finishes.
Predeclare three epochs and evaluate the final checkpoint, without evaluation-based
selection. Save per-minibatch loss and KL, plus per-epoch train/held-out metrics.

## Evaluation and evidence

Import human-prior-p16/scripts/run_eval.py, selecting the workspace runtime in the
local adapter. Keep its 770031 seed base, six cells and 32 games/cell. Run both
initial and final students, stochastic, with identical seeds and decks. No traces
are necessary. Report per-cell wins and pooled match-score differences with a
95% paired bootstrap and two-sided paired sign-flip test over the 96 seat pairs.
This compares both students against scripts, not head-to-head student games.

Before the full collection, validate a complete first game and source/runtime
identities. Record hashes, commands, process IDs, planner process_time, game counts,
labels, mixture fraction, illegal-label counts and artifact sizes. Estimate a
300-game iteration from observed calls/game and core-s/call, with a separate
200-calls/game reference. Keep all outputs below 2 GiB and at most two heavy jobs.
The teacher remains privileged. A 40-game one-seed pilot cannot establish broad
policy improvement or hidden-state inference quality.
