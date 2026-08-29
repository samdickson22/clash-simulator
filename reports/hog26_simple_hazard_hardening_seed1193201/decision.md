# Hard-opponent stage: no promotion

The hardening stage is rejected as a policy promotion.

The run was numerically stable for all eight updates at LR `5e-6`, anchor KL
coefficient `0.2`, and stored-gate PPO.  Its deliberately difficult on-policy
mix finished 29-29 after recovering from early losses.  The small paired screen
was positive (candidate 2-10 versus parent 0-12, +0.25 crown/game).

The expanded matched seven-opponent matrix evaluated 56 games per arm:

- candidate: 30-26, crown margin +0.232143/game
- parent: 31-25, crown margin +0.250000/game
- delta: -1 win, +1 loss, -0.017857 crown/game

The candidate gained one bridge-pressure win, tied spell-control, random,
slow-push, and split-lane, and lost one win each against balanced and
reactive-defense.  This repeats the prior stage's pattern: PPO transfers a small
amount of performance between fixed bots without increasing aggregate skill.

Do not continue or promote this lineage.  Stored-gate PPO remains the correct
implementation for any future recurrent-hazard training, but further static
curriculum/anchor tuning is rejected as the immediate route.  The next learning
signal must change: outcome/value-ranked counterfactual spatial targets or
stronger human/oracle supervision, followed by the same free-running gates.

Evidence:

- `development_screen/update_000008/summary.json`
- `promotion_update_000008_seed1193301/summary.json`
