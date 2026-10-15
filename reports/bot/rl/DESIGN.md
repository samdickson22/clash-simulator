# Bot RL: PPO fine-tuning of the best student (exploration tier)

Owner: bot lead (RL sub-agent). Exploration only: no prereg, no sealing. Code is in `bot/rl/`; progress is in
[PROGRESS.md](PROGRESS.md).

**Goal.** Push student it5s2 past the ExIt plateau (about 0.88 vs v1 and 0.66 vs R3a) using game outcomes rather
than teacher imitation.

**Algorithm.** Asynchronous PPO with lag ≤ 1 policy version, a KL anchor and a separate critic.
- **Init and reference:** both are it5s2 (`clasher-bot-runtime/students/it5s2-step001200.pt`, τ0 = 0.5375).
- **Loss:** `L = −clipPPO(ε 0.2) + β_KL · KL(π_θ ‖ π_it5s2)`, with β_KL = 0.05 as in the human-prior pilot. The KL
  is analytic over the gate, card and tile heads of the training distribution defined below.
- **Optimizer:** policy lr 1e-5, critic lr 1e-4, 3 epochs of 2,048-row minibatches per update, grad clip 1.
- **Critic:**
  - A separate copy of the it5s2 trunk with a new value head. It is trained only by value MSE, so the policy trunk
    is never pulled by the value loss.
  - It also gets a training-only opponent-id embedding. That is not a fair-information issue: the critic is never
    deployed.
  - **Warm-up:** the first 3 updates train only the critic on Monte-Carlo outcomes. The policy stays at it5s2.
    After that, the advantage is the Monte-Carlo outcome − V(s), i.e. GAE with γ 1 and **λ 1**. λ 0.95 was dropped: after warm-up the critic still explained only about 0 to 12% of the outcome variance on new batches, so short-horizon GAE would have been mostly critic noise.
- **Reward:** the terminal outcome only (win +1, draw 0, loss −1). There's no tower-damage shaping: it drifted
  ClashAI's gate.

**Train/serve parity, and gate handling.** Deployed decoding is: play iff p = P(play) ≥ τ, then the top-1 legal
(card, tile). During training the policy is stochastic, but around the same threshold:
- **Gate:** play with probability q = σ((logit p − logit τ0)/κ), with **κ = 0.1** (0.5 and 0.2 overspent: 42–49 plays per game, explore score vs v1 0.59 and 0.71; PROGRESS.md).
  - The mode of q is exactly the deployed gate.
  - Sampling the raw p cost 24 pp by overspending; q only explores near the decision boundary.
  - The actor logs plays per game, so drift in the explore play rate is visible.
- **Card and tile:** card ~ softmax(card/T), tile ~ softmax(tile_card/T), with **T = 0.1** (r1 used 0.3). The deployed decode
  is the T = 1 argmax.
  - Measured (`bot.rl.test_rl`): when the policy plays, a T = 1 sample equals the deployed top-1 only 11% of the
    time, against 43% at T = 0.3 and 67% at T = 0.1. The tile head is diffuse over neighbouring tiles.
- **Shared code:** the actor (CPU) and the learner (GPU) compute these log-probabilities with the same function
  (`bot/rl/dist.py`).
- **Parity tests:**
  - deployed-mode RL actions equal `StudentPlayer` bit for bit;
  - the learner's log-probs on the stored features equal the actor's (ratio ≈ 1 at epoch 0).
- **Which polls are transitions:** only polls where the seat can act and at least one play is legal. All other
  polls are forced WAITs. That leaves about 55 decisions per game (measured), not about 700 polls.
- **Snapshots:** every snapshot is written in student-checkpoint format, so evaluation plays it through the
  unchanged `student:<ckpt>@τ` path.
- **Threshold:** RL owns the gate, so the deployed threshold stays τ0 (the mode of the training policy).
  - Before each eval, the on-policy plays per game at τ0 is measured.
  - If it drifts outside 37.8 ± 3, the rate controller (`bot.exit.calibrate --mode rate`) is run and the snapshot is
    also evaluated at the recalibrated τ.

**League.** The learner always plays one seat, `x4s_setup(g, RL_BANK)`. RL_BANK is a fresh urandom bank, checked
disjoint from HEADLINE and TRAIN1. Opponents are drawn by a hash of g:

| opponent | share |
|---|---:|
| v1 | 30% |
| R3a | 25% |
| it5s2 (frozen) | 20% |
| own snapshots (uniform over past snapshots; it5s2 until the first exists) | 15% |
| K4C-r16 (≈ 2× the cost per game) | 10% |

**Engine and throughput.** Our Python match loop, `bot.players.ours.play_match`, with the same 5-tick polling,
27-tick lag and capacity-1 channel as HEADLINE.
- **Cost:** existing evals cost 50–55 CPU s per student-vs-v1/R3a game, of which engine stepping is only about 7 s
  (521 ticks/s × 3,600 ticks). The rest is the two policies' per-poll observe, D1 and forward.
- **Why not RoyaleSim or the Rust core:** neither would give more than about 1.15× from faster stepping, and
  RoyaleSim needs the adapter. The real lever would be batched GPU inference across games, which is days of work.
- **Expected throughput:** at 48 workers, about 50 games per minute, or about 3,000 games and 165 k transitions per
  hour (about 55 decisions per learner seat). That's roughly 20 PPO updates per hour at 160 games per update. That
  is small next to ClashAI's 24 M decisions, so expect small effects.
- **Hosts:** the learner holds up to 16 GB of the 04 GPU directly (8 GB OOMed), as a persistent process. Actors run on 04 CPU under
  a `cpu_job.sh` lease. Evals run on 08 (our engine) and 04 (RoyaleSim, which also has the rext-bc weights).

**Evaluation (decides everything).** Every 10 updates, the snapshot is evaluated the way it is deployed:
- `bot.eval.headline` vs v1 and R3a on HEADLINE cases 0–299, paired per case against it5s2's existing games
  (`$J8/ce-it5s2`);
- curves of training win-rate by opponent, KL to it5s2, explore plays per game, and deployed plays per game.

The best snapshot is then confirmed on fresh cases 300–599 (paired vs `$J8/conf-300`) and in RoyaleSim vs v1, R3a
and rext-bc (paired vs `$J4/rsim-it5s2`).

**Collapse rule:** stop early if training win-rate rises while the paired eval Δ vs it5s2 is below −0.05 on two
consecutive snapshots, or if the KL exceeds 0.5 nats per transition.
