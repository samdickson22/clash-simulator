# Oracle planner qualification as a player (2026-10-01 to 10-02)

Scope: evaluation games and cost measurements only. Nothing was fitted, no labels were generated,
nothing was distilled. All games ran on the frozen admitted runtime
`m0/runtime-snapshots/pilot-runtime-v4`, 16 pilot cards at level 11, development holdout decks and
the Hog 2.6 deployment deck. Acceptance decks were never loaded.

Every planner here is PRIVILEGED. It forks the true `BattleState`, so it sees the opponent's hand,
elixir and card cycle. The fork also carries a copy of the engine's random generator, so its
simulations see the real future random draws. Its scores are not a fair contest with a
public-information policy. They measure how strong a teacher it could be.

## 1. Result in brief

| question | answer |
|---|---|
| Stock `FixedDepthThompsonOracle` (defaults: depth 10, 48 simulations, 96 samples) | **Fails.** 1 win in 47 holdout games (0-0-42 over the 21 complete seat pairs). No better than the random-candidate control (4/96). |
| Same class with the legacy script's settings (`stable_root_candidates=True`, `defense-v2`, depth 6, 32 sims, 64 samples) | **Fails** the 64-game screen: 7-0-57, score 0.109 [0.03, 0.20]. Hog 2.6: 1-0-47. |
| Same class with a Supercell-style no-more-deploys leaf (my subclass, 8 s rollout) | **Fails** the 64-game screen: 26-0-38, score 0.406 [0.28, 0.53]. On the same matchups it is level with the public seed-2903 1M checkpoint (paired difference -0.03 [-0.14, +0.06]). Hog 2.6: 2-0-46. |
| A different design written for this task: one-step lookahead with scripted continuation (`ScriptRolloutPlanner`, "srp") | **Passes** the 64-game screen: 60-0-4, score 0.938 [0.86, 1.00], and 18-0-2 against the strongest script (defense). Hog 2.6: 58-0-6, 0.906 [0.81, 0.98]. Against the seed-2903 1M checkpoint: 23-0-1. With the opponent modelled by a different code family (StrategyBot) instead of the public script, it still scores 54-0-10, 0.844 [0.73, 0.94]. |
| Cost of the passing design | 3.5 core-seconds per planner call. About 100 calls and 6 core-minutes per game as a player. |
| 256-game confirmation | Not warranted for the repo planner in any tested configuration. Warranted for srp, at about 25 core-hours. Decide first which opponent model to confirm (section 7). |
| 300 DAgger-labelled battles at the srp budget | About 120 core-hours to label every playable decision of one seat. About 60 at one label per 0.5 s (section 4.4). |

How the strategy bar ("at least +0.05 match score with a 95% interval above zero") is read here:
pooled match score against the scripted pool of at least 0.55, with the 95% interval entirely above
0.5. The interval is a bootstrap over matchups, with both seats of a matchup resampled together. The
screen cells and this rule were written into PROGRESS.md before the repo-planner screen games were
played. The srp and srp_xm screens came later: that design was chosen after the repo-planner pilot
games had failed. They use the same cells and the same rule. The bar can also be read as a paired
advantage over the strongest current arm (the seed-2903 1M checkpoint) on identical matchups. srp
passes that reading too: +0.50 [+0.34, +0.66] on holdout and +0.81 [+0.67, +0.94] on hog26.

## 2. Setup and fidelity checks

- The harness `oq_lib.play_game` mirrors `clasher.rl.eval.evaluate`:
  - the same env construction (`_make_evaluation_envs`, decision interval 5 ticks, max ticks 6001,
    council public contract 4);
  - the same matchup seeds (`seed + (game // 2) * 1009`), with seat = `game % 2`;
  - the same deck sampling (`_sample_paired_ordered_decks`). The candidate deck comes from
    `roles_v2/development.json` or `pilot/hog26-deployment.json`, the opponent deck from
    `roles_v2/training.json`;
  - the same public-script opponent call on the projected public packet.

  The cell seeds are the pilot's one-million diagnostic seeds. So game `g` of a cell is the same
  matchup and seat that the pilot policies played.
- Parity check (`oq_check_harness.py`). I replayed the seed-2903 1M checkpoint through the harness.
  It reproduced 6 of 6 pilot diagnostic games exactly: outcome, end tick and all six tower HP values.
- Purity check (`oq_check_purity.py`). srp and roll_pm planned at every playable decision, then
  played no-op. Each game came out identical to the never-play control (same end tick, same tower
  HP). Forking, and calling the script on forked states, does not disturb the real game or the
  opponent.
- The planner seat acts on the same 0.25 s decision grid as the learner. When the seat has no
  playable action, the harness returns no-op without calling the planner (the planner could only
  return no-op anyway). So "planner calls per game" counts playable decisions only.
- Engine legal mask versus learner mask. The engine accepts some placements that the learner's
  public action mask forbids. In the pilot games these were 7-10% of planner or random placements,
  and none of them failed. A teacher that plays such moves produces labels the student cannot
  select. So all screen players restrict the planning seat's root candidates to actions that are
  both engine-legal and in the public mask (`mask_public`, suffix `_pm`). Effect on strength over the
  12 common pilot games: 5 wins to 3 (legacy) and 7 to 5 (rollout leaf), within noise.
- Machine: Apple M4 Pro, 12 cores (8 performance + 4 efficiency), 24 GB.
  - While I ran, the load average was 9-28 (pilot training, evaluations and human-prior fits). My
    workers ran under `nice -n 10`, at most 5 at a time. Swap stayed between 0.4 and 5.7 GB.
  - The CPU times below are `process_time` under that contention. An idle machine should be
    somewhat faster.
  - The Mac slept from 2026-10-02 02:36Z to 23:03Z with my workers suspended. Each game is
    deterministic given its spec, so the sleep changes only a few games' wall times, not their
    results or CPU times.

## 3. What the repo planner does

`src/clasher/rl/oracle_planner.py::FixedDepthThompsonOracle` (284 lines; byte-identical in the
snapshot and in the working tree).

Search structure. `select_actions(battle)` builds a fresh dictionary tree on every call, so nothing
carries over between decisions. It runs `num_simulations` (48) simulations. Each simulation:
- forks the state once and descends `plan_depth` (10) plies;
- at each ply, looks up the node by a state key. Each seat then Thompson-samples one action from its
  candidate set independently (one Beta(1,1) prior per arm, one `rng.beta` draw per candidate per
  ply). The two actions are applied in random order and the engine advances
  `decision_interval_ticks`;
- at the end, backs the leaf value p (for seat 0) up the path. Every visited node adds p to alpha
  and 1-p to beta for seat 0's chosen arm, and the reverse for seat 1.

Opponent. The opponent is the second bandit in every node (decoupled Thompson sampling, as in the
Supercell paper), acting on the true hidden state. It does not model any actual opponent.

Leaf evaluation. `reward_model.reward_win_prob_p0` returns sigmoid(2.5 x potential). The default
`objective-v1` potential is 0.55 crowns + 0.25 princess-tower damage + 0.10 king damage + 0.10
tiebreak edge - 0.20 early-king penalty. The value is an exact 1, 0 or 0.5 only if the game ended
inside the search. So the leaf is a static tower-state score, not a rollout. `defense-v2` adds 0.08
board value and 0.12 tower danger.

Candidates (`oracle_sampling.sample_action_subset`). If a seat has more than 96 legal action ids, the
sampler keeps no-op plus 95 ids drawn uniformly without replacement from all legal (hand slot, tile)
pairs. A playable seat has about 500 legal ids on average (up to 1,289 measured). Because sampling is
uniform over ids rather than per card, cards with more legal tiles (spells) get more candidates, and
waiting is one arm in 96. With the default `stable_root_candidates=False`, the root set is drawn
again in every simulation and once more for the final choice.

Final choice. By default, the highest posterior mean over a fresh candidate draw, where arms that
were never simulated count with the prior mean 0.5. With `stable_root_candidates=True`: a fixed root
set, and the highest posterior mean among visited arms only.

State key. The key holds tick, time, the double/triple/overtime flags, both elixirs x10, the six
tower HPs, and a sorted tuple of up to 96 live entities as (kind, owner, x*2, y*2, HP fraction*20).
It leaves out hands and the card cycle. Below the root, a node is reached again only if the same
joint action sequence is sampled again. With about 96 x 96 joint actions per ply that is rare. I
measured it: a default call creates about 357 distinct nodes for 480 node visits, and about 15
non-root nodes get a second visit (`cost/diag.json`). So below the root, both seats in effect play
uniformly random candidates, which means "deploy something at once whenever anything is affordable".

Fork. `BattleState.clone()` is `copy.deepcopy`, with the card catalogue shared through the memo. It
copies entities, players (hands, cycle, elixir), pending spells and the `random.Random` generator. I
measured 0.95 ms mean (0.55-1.9 ms) at 7-16 live entities. The 48 forks take about 3% of a default
call.

### Differences from the Supercell design (arXiv 2012.12186, sections III-IV and Table XI)

| | Supercell FDTS | repo default | consequence here |
|---|---|---|---|
| step and depth | 0.5 s x 50 = 25 s | 0.25 s x 10 = 2.5 s (interval taken from the eval config) | a troop needs 1 s to deploy and several seconds to reach anything, so the search sees almost no consequences |
| iterations | 4 x max(\|A1\|, \|A2\|), up to 1,028 | 48 for up to 96 arms | at most about one visit per root arm |
| candidates | 64 random positions for every legal card, plus Wait | 95 uniform (slot, tile) ids plus no-op | the card mix follows tile counts; waiting is 1% of arms |
| unaffordable cards | selectable, meaning "wait until affordable" | not selectable | the search never tries saving elixir for an expensive card |
| leaf | play on with no more deploys until only towers remain, then the terminal reward | static tower-HP potential, squashed to 0.5 plus or minus a little | arms differ by about 0.005 (measured), so the Beta(1,1) prior dominates |
| reward scale | win / draw / loss | sigmoid(2.5 x potential), typically 0.45-0.55 | Thompson sampling gets almost no signal |
| tree reuse | root moves to the chosen child between steps | rebuilt every call | nothing accumulates |
| final action | highest mean | highest mean, with unvisited arms at 0.5 eligible (default) | 45% of decisions return an action that was never simulated (measured) |
| both seats Thompson-sampled | yes | yes | same |

Measured root behaviour (`oq_diag.py`, 38 root decisions on real game states, `cost/diag.json`):

| config | root arms visited | max visits of one arm | spread of arm values (max - min) | returned action never simulated | returned no-op |
|---|---|---|---|---|---|
| default | 47 | 1.4 | 0.005 | 45% | 0% |
| greedy 1-ply (depth 1) | 47 | 1.4 | 0.003 | 45% | 3% |
| legacy (stable root, defense-v2, depth 6) | 29 | 2.1 | 0.016 | 0% | 0% |
| rollout leaf 8 s (`roll_raw` = `roll_pm` without the public-mask root) | 19 | 3.4 | 0.038 | 0% | 0% |
| rollout leaf + centred reward + elixir term (`roll_ctr`) | 20 | 3.6 | 0.168 | 0% | 13% |

## 4. Cost

### 4.1 Engine and fork (single process, `oq_cost.py`, 27 forked mid-game states, 7-16 live entities)

| quantity | value |
|---|---|
| raw `BattleState.step()`, no further deploys | 3,050 ticks/s |
| raw `BattleState.step()`, both seats deploying a random legal card every 5 ticks | 1,520 ticks/s |
| `SelfPlayBattleEnv.step` over three whole evaluation games (includes reward bookkeeping) | 1,350-1,640 ticks/s |
| `BattleState.clone()` | 0.95 ms mean, 0.91 median, 0.55-1.93 range |
| `legal_action_mask` for one seat | 0.41 ms |
| `reward_win_prob_p0` | 0.08 ms |
| planner state key | 0.007 ms |

The fork is cheap. A default call is mostly engine ticks (48 x 10 x 5 = 2,400 ticks) plus about 960
legal-mask calls.

### 4.2 Planner wall time per call, single core (same 27 states; in 57% of seat-states the seat had only no-op)

| budget | seconds per call (mean / median / max) |
|---|---|
| default: depth 10, 48 sims, 96 samples | 1.33 / 1.40 / 2.99 |
| legacy: depth 6, 32 sims, 64 samples, stable root, defense-v2 | 0.54 / 0.58 / 1.21 |
| greedy 1-ply: depth 1, 48 sims, 96 samples | 0.17 / 0.20 / 0.27 |
| cheap: depth 4, 16 sims, 32 samples | 0.17 / 0.18 / 0.34 |
| rollout leaf 10 s: depth 1, 32 sims, 32 samples | 2.19 / 2.26 / 4.01 |
| rollout leaf 10 s: depth 1, 64 sims, 32 samples | 4.22 / 4.43 / 7.82 |
| rollout leaf 8 s: depth 4 x 0.5 s, 64 sims, 32 samples | 5.57 / 6.08 / 14.1 |
| Supercell-like: depth 50 x 0.5 s, 257 samples, only 16 sims (7 states) | 7.23 / 5.50 / 15.9, i.e. 0.45 s per simulation |
| same with a rollout-to-end leaf | 7.92 / 8.54 / 11.5, i.e. 0.50 s per simulation |

At Supercell's iteration count (about 1,000), the last two rows come to 450-500 core-seconds per
decision.

### 4.3 Cost as a player (from the evaluation games; CPU = `process_time`)

| player | games | planner calls/game | core-s per call | planner core-s/game | total core-s/game |
|---|---|---|---|---|---|
| never play | 240 | 0 | - | 0 | 9 |
| random candidate | 240 | 0 | - | 0 | 6 |
| repo default | 42 | 38 | 3.52 | 133 | 136 |
| repo greedy 1-ply (pilot) | 12 | 40 | 0.39 (wall) | 15 | 23 |
| repo legacy settings, public root (`legacy_pm`) | 114 | 57 | 1.11 | 63 | 70 |
| repo + rollout leaf, public root (`roll_pm`) | 130 | 66 | 4.20 | 278 | 287 |
| srp_small (8 candidates, 5 s rollout) | 24 | 123 | 0.92 | 113 | 121 |
| srp | 172 | 99 | 3.52 | 349 | 356 |
| srp_xm (opponent modelled by StrategyBot) | 66 | 102 | 3.16 | 324 | 331 |
| seed-2903 1M checkpoint as player (for scale) | 48 | 0 | - | 0 | 9 |

In-game calls cost more than in the single-state benchmark of 4.2 (default 3.5 s versus 1.3 s). Two
reasons: in-game calls happen only at playable decisions, where candidate sets are full, and the
machine was loaded.

A planner that spends as soon as it can is "playable" in only 6-10% of decisions. That is why whole
games cost one to five core-minutes. srp waits more: it is playable in 22% of decisions and returns
no-op in half of its calls.

Inside an srp call: about 20 candidates, each with one rollout of about 155 ticks, make about 3,100
engine ticks (about 1-2 s at the rates above). The rest of the 3.5 s goes to about 590 script
decisions on forked states. I inferred that split from the totals; I did not profile it.

### 4.4 What 300 DAgger-labelled battles would cost

Assumptions, from the pilot: a student-driven battle has about 812 decisions (4,058 ticks / 5), and
the seed-2903 1M checkpoint is playable in 49% of them. Labelling every playable decision of one
seat is then about 400 planner calls per battle.

| teacher budget | core-seconds per label call | core-hours for 300 battles |
|---|---|---|
| srp (about 20 candidates, 8 s scripted rollout) | 3.5 | 117. About 60 at one label per 0.5 s. Scoring the student's own action adds one rollout per call, about 5%. |
| srp_small (8 candidates, 5 s rollout; weaker, 17-0-7 in 24 games) | 0.92 | 31 |
| repo planner + rollout leaf 8 s, 32 sims (`roll_pm`) | 4.2 | 140 |
| repo planner, legacy settings | 1.1 | 37 |
| repo planner, default settings through `imitation._collect_oracle_shard` (calls the planner at every decision, 812 per battle) | 1.3-3.5 | 90-240 |
| Supercell budget (depth 50 x 0.5 s, about 1,000 iterations) | 450-500 | about 15,000 |

On this Mac, the srp row is about a day of wall time with 5 workers, or half a day with 10. The
coordinator's earlier unmeasured estimate (3.8 core-seconds per label, 95 core-hours) is close to the
measured srp cost. Only the srp row buys a teacher that passed the screen. Playing the 300 battles
themselves (student policy plus scripted opponent) adds well under 1 core-hour.

## 5. Strength

Match score: win 1, draw 0.5 (no game was drawn). Score intervals: 95% percentile bootstrap over
matchups (10,000 resamples). Wilson intervals on win rates are in `summary*.json`. Raw per-game JSON
is in `games/<player>/`. Full per-cell tables: `tables.md` (regenerate with `python3 oq_tables.py`).

### 5.1 The 64-game screen cells (games 0-21 vs balanced, 0-21 vs pressure, 0-19 vs defense; pilot diagnostic seeds)

| player | holdout: balanced / pressure / defense (W-L) | holdout pooled: W-D-L, score [95%] | hog26: balanced / pressure / defense | hog26 pooled |
|---|---|---|---|---|
| never play | 0-22 / 0-22 / 0-20 | 0-0-64, 0.000 | 0-22 / 0-22 / 0-20 | 0-0-64, 0.000 |
| random candidate (planner's sampler) | 0-22 / 0-22 / 2-18 | 2-0-62, 0.031 [0.00, 0.08] | 0-22 / 0-22 / 0-20 | 0-0-64, 0.000 |
| repo greedy 1-ply (pilot, 12 games) | 0-4 / 0-4 / 0-4 | 0-0-12, 0.000 | - | - |
| repo default (42 games) | 0-14 / 0-14 / 0-14 | 0-0-42, 0.000 | - | - |
| repo legacy settings, engine mask (pilot, 12 games) | 1-3 / 4-0 / 0-4 | 5-0-7, 0.417 [0.08, 0.75] | - | - |
| repo legacy settings (`legacy_pm`) | 2-20 / 3-19 / 2-18 | **7-0-57, 0.109 [0.03, 0.20]** | 0-16 / 1-15 / 0-16 | 1-0-47, 0.021 [0.00, 0.06] (48 games) |
| rollout leaf, engine mask (`roll_raw`, pilot, 12) | 2-2 / 4-0 / 1-3 | 7-0-5, 0.583 [0.25, 0.92] | - | - |
| rollout leaf + centred reward (`roll_ctr`, pilot, 12) | 1-3 / 4-0 / 0-4 | 5-0-7, 0.417 [0.08, 0.75] | - | - |
| rollout leaf (`roll_pm`) | 11-11 / 9-13 / 6-14 | **26-0-38, 0.406 [0.28, 0.53]** | 0-16 / 2-14 / 0-16 | 2-0-46, 0.042 [0.00, 0.10] (48 games) |
| srp_small (24 games) | 8-0 / 7-1 / 2-6 | 17-0-7, 0.708 [0.46, 0.92] | - | - |
| **srp** | 20-2 / 22-0 / 18-2 | **60-0-4, 0.938 [0.86, 1.00]** | 20-2 / 22-0 / 16-4 | **58-0-6, 0.906 [0.81, 0.98]** |
| **srp_xm** (opponent modelled by StrategyBot) | 20-2 / 19-3 / 15-5 | **54-0-10, 0.844 [0.73, 0.94]** | - | - |
| *pilot: warm start, seed 2903 (public)* | 6-16 / 3-19 / 2-18 | 11-0-53, 0.172 [0.06, 0.30] | 0-22 / 6-16 / 0-20 | 6-0-58, 0.094 [0.02, 0.19] |
| *pilot: seed-2903 1M checkpoint (public)* | 11-11 / 11-11 / 6-14 | 28-0-36, 0.438 [0.27, 0.61] | 4-18 / 2-20 / 0-20 | 6-0-58, 0.094 [0.00, 0.22] |

Notes. The repo default was played on games 0-15 of each holdout cell. One game (defense, game 15)
was lost to a worker restart, so the table keeps games 0-13 of every cell (21 complete seat pairs).
Its one win, in balanced game 14, falls outside that range. On hog26, legacy_pm and roll_pm were stopped after 48 games (games
0-15) once their holdout screens had failed.

### 5.2 Other opponents (planner on holdout decks; opponent decks from `roles_v2/training.json`)

| player | vs seed-2903 1M checkpoint (stochastic) | vs StrategyBot balanced | vs StrategyBot bridge-pressure |
|---|---|---|---|
| never play | - | 0-0-24 | 0-0-24 |
| random candidate | - | 10-0-14, 0.417 [0.21, 0.62] | 8-0-16, 0.333 [0.12, 0.54] |
| seed-2903 1M checkpoint (as player) | - | 20-0-4, 0.833 [0.62, 1.00] | 19-0-5, 0.792 [0.58, 1.00] |
| repo + rollout leaf (`roll_pm`) | 15-0-1, 0.938 [0.81, 1.00] | - | - |
| srp | 23-0-1, 0.958 [0.88, 1.00] | 8-0-0 | 8-0-0 |

The checkpoint and StrategyBot both turned out to be weak discriminators. roll_pm, which fails
against the public scripts, also beats the checkpoint 15-0-1. Random play beats StrategyBot 42% of
the time. So the checkpoint games confirm that srp is not tied to the script family, but they cannot
rank planners. That is why I added srp_xm (section 5.4).

### 5.3 Controls and failure analysis

Controls, on the pilot's exact cells with 32 games per cell:
- never play: 0/96 holdout, 0/96 hog26 (always a three-crown loss, mean 1,308 ticks);
- random legal candidate from the planner's own sampler (`sample_action_subset`, 96): 4/96 holdout,
  0/96 hog26;
- greedy 1-ply (repo planner, depth 1): 0/12;
- repo planner default: 1/47.

Why the default fails (section 3): its leaf cannot tell candidates apart, half of its returned
actions were never simulated, and it never waits. It plays like the random control.

Why the rollout-leaf planner stalls at the scripts' level. Every planner of this family spends the
moment a card is affordable: roll_pm returned no-op in 0.3% of its calls. Against the defense script
its games typically reach tick 6001 at 0-0 and are lost on the tower-HP tiebreak, after dealing
100-700 damage in five minutes. The no-more-deploys leaf assumes the opponent never answers after
the root move, so attacks look better than they are. Supercell's planner covers this with 25 s of
two-sided tree search, unaffordable-card wait arms and about 1,000 iterations. We can afford 32-128
iterations. I timed larger budgets (4x simulations, 20 s leaf) but did not play them (section 8).

### 5.4 The design that passes: one-step lookahead with scripted continuation (srp)

`oq_lib.ScriptRolloutPlanner` lives in this directory (about 130 lines), not in `src/`. For each root
candidate of the planning seat it:
1. forks the true state;
2. plays the candidate, while the other seat plays the opponent model's move;
3. lets both seats follow their policies every 10 ticks for 160 ticks (8 s);
4. scores the end state with the `defense-v2` potential plus elixir counted as material (0.08/16
   per elixir, the same scale as board value).

The planning seat's continuation policy is always the balanced public script. The opponent model
is the balanced public script (`srp`) or StrategyBot balanced (`srp_xm`, a separate code family).
StrategyBot is not the one srp is scored against.

Candidates: the script's own choice, no-op, the script's next three ranked plays, and 16 uniformly
sampled legal placements, about 20 in total. Because the fork copies the random generator and both
continuation policies are deterministic, one rollout per candidate is exact under the model. There
is no bandit and no sampling noise. This is the classic rollout algorithm: one policy-improvement
step over a base policy. srp departs from the script's own choice in 46% of its calls (srp_xm: 48%).

Each candidate gets an exact value under the model, so soft or Q-regression targets
(`kl_regularized_candidate_target`) come for free. The repo planner's `select_actions` returns only
the argmax; its root statistics would have to be exposed first.

Does srp depend on modelling the opponent exactly? Evidence, from strongest to weakest:
- with an out-of-family opponent model (srp_xm) it still passes, at 0.844 [0.73, 0.94], against all
  three script styles;
- against the pressure and defense scripts, which differ from its balanced model (different elixir
  threshold and lane rule), it scores 22-0 and 18-2 on holdout;
- it beats the public checkpoint 23-0-1.

The exact model is worth about 0.09 match score (0.938 versus 0.844, same matchups). It is not the
source of the pass.

### 5.5 Self-review of srp for score-inflating bugs (2026-10-03, before the 256-game confirmation)

I re-read `ScriptRolloutPlanner` and the harness path it runs through, and added
`oq_selfcheck_srp.py`. It runs six checks, all PASS: phi antisymmetry and terminal values by seat;
phi rises when the opponent's tower HP drops; `select_action` leaves the real battle untouched
(entities, elixir, hands, cycle, engine RNG state); the decision is deterministic in (state, planner
seed); chosen actions are engine-legal and in the public mask, with no troop placed on the wrong
half by seat 1; shadow-planning srp_xm leaves the game identical to never-play. srp lives in this
folder, not in `src/`, so this is a self-check script rather than a test under `tests/`. Findings:

- Privileged information. srp uses the true full state, which the oracle is allowed. That covers
  the opponent's hand, elixir and cycle (read by the opponent model on the forked state) and both
  elixirs (in the leaf's elixir term). The one thing beyond the game state is the engine RNG, which
  the fork copies.
  - With the 16 pilot cards I found no RNG use that changes an outcome. The stun and knockback rolls
    are compared against chance 1.0, so they always succeed. The scatter and death-spawn radius
    draws belong to cards outside the pilot set. I did not check this exhaustively.
  - The real `env.step` also draws from the same generator (it shuffles action order), so the
    fork's random stream is offset from the real one anyway.
- The real opponent's move. srp decides before the harness computes the opponent's action, and it
  never calls the evaluated opponent's object. It predicts the opponent with its model:
  - in srp_xm the model is StrategyBot, a different code family from the evaluated public script;
  - in plain srp the model is the balanced public script, which is the exact opponent policy in the
    balanced cells. That is why the confirmation uses srp_xm.
- Leakage of the real future. Rollouts start from the current true state. Nothing from later real
  ticks is available when the action is chosen. The only "future" content is the RNG point above.
- Seat and side. The leaf is negated for seat 1 after the elixir term is added (checked
  numerically). Action ids are the per-seat canonical ids, decoded by the same action space as
  `env.step`. The side check found no wrong-half placements. One small modelling difference: the
  fork applies the planner's action before the opponent's, while `env.step` uses a random order.
  This is a noise source, not an inflation.
- Scoring. A terminal leaf is +-2, which outranks any potential: |defense-v2| <= 1.5 and the elixir
  term <= 0.05. A draw scores 0. Ties go to the first candidate, which is the script's own choice,
  so ties lean towards the base policy, not towards the search.
- Harness. 0 failed actions, 0 actions outside the public mask. On odd decisions srp is not called
  and plays no-op (`plan_every: 2`); this is a handicap, not an advantage. Harness parity (6/6 pilot
  games reproduced) and purity checks pass.

Verdict: I found no bug that inflates the score. The remaining advantages are the intended oracle
privileges: the true hidden state, plus the RNG copy, which is inert with these cards.

## 6. Comparison with the pilot numbers

All comparisons use the same cells, matchup seeds and seats as the pilot's diagnostic evaluation.
Pilot full cells (96 games per role): warm start 19/96 holdout and 11/96 hog26; seed-2903 1M
checkpoint 46/96 holdout and 8/96 hog26.

| player | holdout: paired score difference vs 1M checkpoint (64 games) | hog26: same (64 games) |
|---|---|---|
| srp | +0.500 [+0.344, +0.656] (0.938 vs 0.438) | +0.812 [+0.672, +0.938] (0.906 vs 0.094) |
| srp_xm | +0.406 [+0.266, +0.547] | not played |
| roll_pm | -0.031 [-0.141, +0.062] | -0.083 [-0.250, +0.062] (48 games) |
| legacy_pm | -0.328 [-0.484, -0.188] | -0.104 [-0.250, +0.021] (48 games) |
| repo default | -0.362 [-0.543, -0.191] (47 games) | not played |

Hog 2.6 is the pilot's weakest slice (8/96 for the checkpoint, 0/32 against the defense script).
The privileged srp wins it 58-0-6, 16-4 against defense.

## 7. Verdict, recommendation, caveats

Screen verdict against the strategy bar (holdout, 64 games, pooled over the three script styles):

| player | score | 95% interval | versus defense script (strongest) | hog26 | verdict |
|---|---|---|---|---|---|
| repo planner, default | 0.000 (42 games; 1/47 including the incomplete pair) | [0.00, 0.00] | 0-14 | not played | fail |
| repo planner, legacy settings (`legacy_pm`) | 0.109 | [0.03, 0.20] | 2-18 | 0.021 (48) | fail |
| repo planner + rollout leaf (`roll_pm`) | 0.406 | [0.28, 0.53] | 6-14 | 0.042 (48) | fail |
| scripted-continuation lookahead (`srp`) | 0.938 | [0.86, 1.00] | 18-2 | 0.906 [0.81, 0.98] | pass |
| same, opponent modelled by StrategyBot (`srp_xm`) | 0.844 | [0.73, 0.94] | 15-5 | not played | pass |

Recommendation.
1. Do not distil `FixedDepthThompsonOracle` in any tested configuration, and do not spend a 256-game
   confirmation on it. Its weakness is design, not budget: a 2.5 s horizon, a static leaf, about one
   visit per arm, unvisited arms eligible, and no way to wait. Reaching the Supercell budget would
   cost about 450 core-seconds per decision.
2. If the oracle route goes ahead, use the scripted-continuation lookahead as the teacher. Budget:
   about 20 candidates (script top-4 + no-op + 16 random), an 8 s horizon, script cadence 0.5 s in
   rollouts, a plan every 0.5 s: 3.5 core-seconds per call, about 6 core-minutes per game. The
   cheaper srp_small (8 candidates, 5 s horizon, 0.9 s per call) is clearly weaker, especially
   against the defense script (2-6). I do not recommend it without more games.
3. A 256-game confirmation of srp is warranted. It costs about 25 core-hours (6 core-minutes per
   game). Run it against the strategy's "same reacting pool and strongest scripted baseline", with
   the srp_xm opponent model (or both). srp_xm does not borrow the evaluated opponent's code, so it
   is the more defensible teacher claim.

Caveats that limit what the srp result means:
- It is not the repo planner, and it is new code: written and run in this task, with no unit tests
  and no review. The harness parity and purity checks pass, but they do not test the planner's own
  logic.
- With the default model, its rollouts use the same script family it is scored against. srp_xm
  shows the pass does not depend on that, but its 0.844 is the cleaner number.
- It reads the opponent's hand and elixir (through the opponent model's view of the forked state)
  and the future random draws. A student cannot. The strategy's warning stands: teacher strength
  does not establish student learnability.
- Strategy conditions 1 and 3 are untouched: there is no prospective admission of the
  search/candidate scope, and no reference checks on oracle-selected candidates. Both are still
  required before any label is generated.
- srp was not tuned, and its parts were not ablated (horizon, candidate count, elixir term),
  apart from srp_small (24 games) and the srp_xm opponent-model swap.

## 8. Not done or not verified

- The larger budgets of the repo planner with a rollout leaf (`roll_pm_s128` = 4x simulations,
  `roll_pm_h400` = 20 s leaf) were defined but not played: 1 game was played and is excluded. The
  failure analysis suggests that budget is not the bottleneck, but I did not verify that.
- srp_xm was not played on hog26 or against the checkpoint. srp against StrategyBot stopped at 8
  games per cell.
- No 256-game confirmation was run.
- Mixed card levels were not evaluated (nominal level 11 only, as in the pilot's diagnostic cells).
- A faithful Supercell configuration (depth 50, about 1,000 iterations, per-card positions,
  wait-until-affordable arms, tree reuse) was only timed, never played. One game would take about
  12 core-hours.
- The CPU figures were taken on a heavily loaded machine.
- The split of srp's per-call cost between engine ticks and script calls is inferred, not profiled.

## 9. Files

- `PROGRESS.md`: running log, exact commands, pre-registered screen definition.
- `oq_lib.py`: harness, `RolloutLeafOracle`, `PublicRootMixin`, `ScriptRolloutPlanner`.
- `oq_run.py`, `batches.json`: resumable workers, player configs and batches.
- `oq_selfcheck_srp.py`: srp self-check (six checks).
- `oq_check_harness.py`, `oq_check_purity.py`, `oq_cost.py`, `oq_diag.py`, `oq_probe.py`: parity
  check, purity check, cost benchmark, root-bandit diagnostic, action printout.
- `oq_report.py` (`summary.json`, `summary-screen64.json`), `oq_tables.py` (`tables.md`),
  `analysis_caps.json`: aggregation. The caps file drops incomplete seat pairs.
- `games/<player>/<player>__<role>__<opponent>__s<seed>__g<game>.json`: one file per game (spec,
  outcome, crowns, tower HP, decks, planner calls and CPU, placement trace). 1,131 games, 4.7 MB.
- `cost/cost.json`, `cost/diag.json`, `logs/`.

Player names. With the engine mask at the root (pilot): `noop`, `random96`, `greedy1`, `default`,
`legacy`, `roll_raw`, `roll_ctr`. With the public-mask root: `legacy_pm`, `roll_pm`, `srp`,
`srp_small`, `srp_xm`. Also `ckpt2903` (the seed-2903 1M checkpoint as the player).
