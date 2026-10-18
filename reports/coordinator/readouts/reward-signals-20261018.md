# Reward signals: Hasty-CR, ClashAI, and Clasher

Research date: 2026-10-18. Requested by Sam through coordinator `b4f05b1c-9d3a-4e38-a58a-98ab4407fa25`. Read-only research; no external code executed, network fetch, training, evaluation games, or running-job changes.

## Answer to Sam

**Partly correct for their newer RL stages, incorrect as a description of their whole training pipelines.** ClashAI uses human-action imitation plus an auxiliary final-crown predictor, then terminal win/draw/loss PPO. Hasty's older PPO explicitly rewards tower damage and crowns as well as winning; its newer RoyaleSim self-play uses only the match result, but its memory bot loads a human-imitation checkpoint with a 10-second tower-swing auxiliary head. Our **HP1 run already uses terminal win/draw/loss only**, from a human v2 init. Even our earlier rl5-v10 is outcome-trained PPO after search distillation. The specific remaining hand-made objective is K4L's 8-second search leaf and the targets inherited when students imitate that search. See source evidence below.

**The evidence supports a heuristic bottleneck hypothesis, not a demonstrated strength ceiling.** Search still beats the available policy-only students on strong paired tests; outcome-fitted leaf replacements have repeatedly lost. The clean next comparison is the existing human-init, outcome-only HP1 run against its init, the distilled student, and search on matched cases—not changing HP1's reward to a signal it already has.

## Source identity and citation convention

All SHAs and times below were read from commands in this research turn:

- **C:** Clasher `origin/main` = `977e9f2814bfb15707716ba1c4a51c859fc660d5`, examined in detached scratch worktree `/tmp/clasher-reward-signals-20261018`. Clasher relative paths below refer to that snapshot unless stated otherwise. Initial local clock: `2026-10-18T03:15:25-07:00`; later UTC receipt: `2026-10-18T10:18:04+00:00`.
- **H:** `/mpac/sdicks02/tmp/hastycr-research/repo`, HEAD `ac4ef71194167e97f34550fc91c026b6d707a0cd`.
- **A:** `/mpac/sdicks02/tmp/clashai-research/repo`, HEAD `8d4053dfea1be589c4b487154ed2da1b98d6aa9e`. Existing public clone; no new clone needed.
- **J:** `127x01:/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018`. SSH read clock `2026-10-18T10:16:06+00:00`; `source-commit.txt:1` pins `bf9c566784b01994862aff36882f202a4dea68f3`. Actual source bytes, not only current main, were checked: `source/bot/rl/learner.py` SHA256 `9735807daf3b83436b5c61150629c94c1f750523232d1f75a82ecadc33842f1b` (identical to C); `source/bot/rl/actor.py` SHA256 `2c15e7f64d268711a659b1e82a907630c9a93371482c0193dbfd6879f7a9d7c4` (different line offsets from C).
- **W:** shared workspace `/mpac/sdicks02/repos/clasher`. Its already-collected coordinator readouts are cited for final HZ1/PF1/NS2 results; those files were present in W but absent in the pinned C snapshot. They are secondary research inputs, not newly rerun experiments.
- Earlier notes: `C/reports/hastycr_deepdive_20261017.md`, `C/reports/clashai_deepdive_20261008.md`. The compressed old-coordinator archive was searched locally: `/mpac/sdicks02/clasher-archive/old-coordinator-0523ae6f-20261018/messages.jsonl.gz`, decompressed lines **340–356** contain the ClashAI deep-dive assignment/result and line **44974** explicitly describes imitation plus terminal-reward PPO. Archive prose is a navigation aid; A's source is the primary evidence below.

Citations such as `H/sim/env.py:234–243` mean that file at the above local root and pinned SHA. Recommendations and causal interpretations are labeled separately from measured findings.

## 1. Hasty-CR: distinguish four stages

### Older rule brain and its behavior clone

The original neural clone imitates the **hand-written brain's action**, not winning actions selected from games. `H/sim/clone.py:1–26,64–85` describes/runs that teacher; its loss is masked action cross-entropy. The returned value output is unused in that loss (`H/sim/clone.py:164–178`). This explains the initially random PPO critic; their README explicitly documents that problem (`H/README.md:179–182`).

The brain itself ranks legal candidate actions by hand-written, tunable feature scores:

- Base score by action family; defense adds threat and river-depth terms, repeated-answer/contained-defense penalties. Other actions add remaining-elixir surplus and a threatened-reserve penalty. Hog additionally gets `2 * elixir_multiplier + 6 * (1 - weakest_enemy_tower_HP_fraction)` (`H/scripts/brain/policy.py:1399–1438`).
- Example config weights: Cannon defense 55, kite 54.5, spell defense 55.5, swarm 56, single defense 46, Hog counterpush 52, Hog punish/push 44, spell value 30, cycle 8; threat 2, depth 2.6, surplus 1.2, unanswered −25, contained defense −60 (`H/scripts/brain/config.example.json:97–123`). These are example-config values, not proof of any unshipped live config.
- Its contextual-bandit adjustment is also **shaped**: `killed_enemy_elixir + 35 * tower_fraction_dealt - card_cost - 45 * tower_fraction_taken`; a running mean is scaled by `n/(n+4)` and clamped (`H/scripts/brain/experience.py:68–81,229–235,246–248,260–267`). Policy defaults for the scale/limit are 1.2/14 (`H/scripts/brain/policy.py:1316–1329`). This is distinct from PPO and from pro imitation.

### Older simulator PPO: explicitly dense tower shaping

Default reward weights are:

```
per-step: +10 * decrease(sum enemy tower HP fractions)
          -10 * decrease(sum own tower HP fractions)
          -0.01 per illegal action; 0 step cost
terminal: +3 * own crowns - 3 * enemy crowns
          +10 win / 0 draw / -10 loss
optional net-elixir-trade term: coefficient 0 by default
```

Weights: `H/sim/env.py:234–243`; damage computation: `:495–509`; terminal computation: `:527–539`; illegal/terminal application: `:443–490`. This is emphatically **not** sparse win/loss training. The optional elixir coefficient exists, but its default is off; existence alone does not show a specific run enabled it.

The old PPO value target is the **GAE lambda-return for this shaped reward**, not a pure win label: `delta = reward + gamma * next_value - value`, `returns = advantage + value`; value MSE against those returns (`H/sim/train_ppo.py:490–498,507,538`). Defaults are gamma 0.997, lambda 0.95 (`:67–68`).

### New pro-imitation transformer: actions plus two value labels

The labels are recorded pro **WAIT/card-slot** and **placement tile**. Gate CE and tile CE have unit coefficients. Total loss is:

```
gate_CE + tile_CE + 0.5 * (MSE(predicted_10s_swing, actual_10s_swing)
                         + BCE(predicted_win_logit, recorded_match_result))
```

See `H/sim/model_tokens.py:84–120,130`. The 10-second label is net enemy-minus-own tower-fraction damage over the following 200 ticks; each tower is normalized by its own maximum HP (`H/tools/rs_rows.py:43,87–96,251–263`). The match-result label is 1 win, 0 loss, 0.5 draw from the replay (`:197–198`). Thus the auxiliary value has **both short-term tower damage and final outcome** supervision. A value head present in an imitation model does not mean its actions were trained by RL.

Optional AWR reweights the imitation losses by `exp((10s_swing - predicted_swing)/beta)`, clipped at 5; default beta=0 makes all weights 1 (`H/sim/model_tokens.py:94–119`; `H/sim/train_tokens.py:127–128`). Their recorded bigger-model training command uses that default (`H/docs/PROGRESS_2026-10-09.md:384–386`).

Their optional newer search also is not pure win evaluation: 3-second rollout tower swing **plus predicted 10-second swing plus 0.05 * policy log-probability** (default top-2 cards × 3 tiles; no follow-up plays in the forks): `H/tools/rs_eval.py:380–391,479–497`. Public-rebuild search was only about +5 pp, inside noise; stacking it with delay look-ahead scored 41.7% versus 47.0% for look-ahead alone, so the recorded live configuration omitted search (`H/docs/PROGRESS_2026-10-09.md:288–305`).

### New RoyaleSim self-play: sparse outcome PPO, after imitation

`H/tools/rs_selfplay.py:26–29,175–182,228–232,265–268` uses one final return **1 win / 0.5 draw / 0 loss** for every recorded decision, advantage `return - sigmoid(win_head)` normalized over rows. No tower/crown/elixir shaping is added. It optimizes clipped PPO plus KL to the imitation reference and `0.5 * BCE(win_head, return)` (`:318–330`). This stage updates the **win head** (`value[:,1]`), not an explicit MSE target for the 10-second head. It is outcome-only RL but still has a human-policy KL prior.

**Which stage produced the memory bot / “10k bot”?** The committed memory loop names `runs/tokens/rs_big_hog/best.pt` (`H/scripts/gamestate/live_play.py:1–4`), which is the **pro-imitation** model documented in `H/docs/PROGRESS_2026-10-09.md:365–374`. It adds a 9.5-elixir cap rule and Cannon lane guard (`H/scripts/gamestate/live_play.py:24–25,540–564`). There is no committed evidence here that the default live checkpoint is a self-play PPO result, nor a substantiated Hasty 10k-trophy record: the repository's recorded older ladder result is W14/L118/D72 (`H/docs/RUN_JOURNAL.md:1277–1279`), and its README says no trained policy has beaten a human (`H/README.md:389–390`). **The ~10–11k memory-bot account belongs to the ClashAI evidence**, not a demonstrated Hasty result (`C/reports/clashai_deepdive_20261008.md:59–70`). This does not rule out uncommitted later Hasty results.

## 2. ClashAI: human imitation, outcome PPO, unsuccessful heuristic search

### Imitation and value target

Generalist action loss: pro placement-cell CE + pro hand-card CE on PLAY rows; play/wait gate BCE on all rows; `0.5 * wait-for-card CE` on WAIT rows; `0.5 * final_crown_difference CE` on all rows (`A/pipeline/train_gen.py:1–9,98–105`).

The seven-class value label is `clip(own_final_crowns - enemy_final_crowns, -3,3)+3` (`A/pipeline/train_s1.py:44–49`, the Rows base used by the generalist; `A/pipeline/eval_gen.py:28–42`). Crown labels are the **real replay result**, not simulated leaf scores (`A/pipeline/dataset.py:19,72–74,186`). This is human-action supervision plus auxiliary outcome prediction, not action learning exclusively from wins/losses.

### PPO reward and critic

- Terminal reward is **+1 win / 0 draw / −1 loss** (`A/pipeline/rl_royale.py:171–172`), assigned only to the last contributing decision row (`:729–738`); there is **no extra terminal crown-margin reward** in this helper.
- Original `match_loo` estimates advantage by subtracting the mean return of the other rollouts for the same matchup (`:175–180,1109–1117`). Later GAE computes per-decision advantages and `return = advantage + value` (`:742–759,1336–1368`). Defaults are gamma .999 per retained decision row, lambda .95; default shaping is `none` (`A/pipeline/rl_royale.yaml:51–75`). These are defaults/algorithm definitions, not a claim that every run used an untouched YAML.
- The imitation crown head is reused as scalar critic **P(positive crown difference) − P(negative crown difference)**, not expected crown count (`A/pipeline/rl_royale.py:721–726`). GAE then fits that scalar to lambda-returns using clipped squared value loss, coefficient .5 by default (`:1458–1462`; YAML `:62–65`). The original match-LOO mode does not imply an RL critic fit.
- PPO also applies gate/card/cell KL penalties to a frozen reference (`A/pipeline/rl_royale.py:1450–1457`). Their README reports a KL-free run degenerated (`A/README.md:299–301`).

They **did try shaping**: `Phi = .3 * (own - enemy summed tower-HP fractions)/3 + .3 * crown_difference/3`, `F = gamma*Phi(next)-Phi(now)`, terminal Phi=0. The implemented residual critic is `V_eff = Phi + 1.5*v_net`; its target is `(lambda_return - Phi)/1.5` (`A/pipeline/rl_royale.yaml:67–75`; `A/pipeline/rl_royale.py:1336–1354`). R1 was the win/loss-only baseline and R2 the tower/crown-potential experiment (`A/scratchpad/gauntlet/L69/reward_plan.md:30–46`). **Their recorded verdict is negative: shaping drifted the gate away from pros and did not establish an improvement** (`A/README.md:91,299–301`). It would be inaccurate to describe the repository as never using heuristics.

### Search was tried, with a hand-made evaluator

S0: WAIT plus top-4 cards × top-3 cells, **12 seconds / 240 ticks**, one rollout per candidate, on RoyaleSim with 26-tick lag/look-ahead. Original rollout leaves our side idle after the candidate; the opponent uses a generalist self-model (`A/pipeline/search_s0.py:22–50`). Its evaluator is:

```
enemy_tower_fraction_destroyed - own_tower_fraction_lost
- 0.061 * own_elixir_spent
+ change(own_board_value - enemy_board_value)
+ 1.0 * net_crowns_taken
```

See `A/pipeline/search_s0.py:52–66,236–246`. The board valuation is an additional heuristic, not a learned terminal value. Forks included the true opponent hand; they disclosed that optimism (`A/HANDOFF.md:5635`).

Results (`A/HANDOFF.md:5636–5638`):

- S0, 12 seeds × 2 opponents × 5 arms =120 matches: search minus plain **−1 win vs generalist, +2 wins vs S1**; tower-HP differences −45/−165, t≈−.04/−.20. Null, small sample; controls were clearly worse, so not evidence of equivalence.
- Follow-up, own policy continues in rollouts, 24 seeds per opponent: **−2 wins vs generalist; −7/24 wins vs S1**. Against S1, tower-HP delta −1,805, t=−3.16. Their opponent model was wrong for S1, but search was still null against the generalist whose policy it modeled exactly.
- They recommended validating the 12-second scorer against played-out outcomes before deeper search; decision-time search stayed parked (`A/HANDOFF.md:5638`; `A/README.md:295–297`).

**What made the high-trophy memory bot?** Committed records put initial generalist imitation live before later PPO models (gen_v1: 40/59/2; later league/R1/R1e roughly 51%; `C/reports/clashai_deepdive_20261008.md:61–67`). This is **human BC, then modest PPO, memory state and live engineering**, not a demonstrated from-scratch sparse-reward climb. The account was already near 10k, and bot-attributed trophy gain is not cleanly established (`C/reports/clashai_deepdive_20261008.md:16–31`). Search is not the successful live stage.

## 3. Clasher

### (a) K4L: exact 8-second leaf

K4L's rollout defaults to **160 × 50 ms =8 seconds**, and ends by calling `native.evaluate(sim, seat, elixir_weight)` (`C/bot/search/lopp.py:161–162,219–227`; core setup `C/bot/players/search.py:96–102`). Default elixir_weight=1 (`C/src/clasher/rl/c56_rollout_planner.py:27–32`). The native formula is `C/engine-rs/src/leaf.rs:170–187`:

```
phi(seat 0) = clip( .55*C + .25*P + .10*K + .10*T - .20*E
                   + .08*B + .12*D, -1.5, 1.5)
              + .08 * elixir_weight * (elixir0 - elixir1) / 16
phi(seat 1) = -phi(seat 0)
terminal    = +2 win / 0 draw / -2 loss
```

The elixir term is therefore **+.005 per extra elixir** at its default, outside the clip. Exact constituent definitions:

- **C (crowns)** = `(alive_princess_towers0 - alive_princess_towers1)/3`. Nonterminal crown advantage is encoded by surviving princess towers; terminal winner handling overrides the formula (`leaf.rs:77,91,170–176`).
- **P (princess damage pressure)** = `(1 - mean_princess_HP_fraction1) - (1 - mean_princess_HP_fraction0)`. Each side averages its two princess slots; a destroyed slot is 0, not excluded. Normalizer is `self.meta.bodies["Tower"].hp` (`:47–75,92`).
- **K (king pressure)** = `w1*(1 - king_fraction1) - w0*(1 - king_fraction0)`. King normalizer is metadata KingTower HP. Weight per side: 0 with two princess towers and sleeping king, .05 with two and active king, .25 with one princess remaining, .60 with none (`:70–93`).
- **T (tiebreak)** = difference of each side's minimum **positive surviving crown-tower HP**, converted to integer millihitpoints, divided by `max(metadata_princess_HP,metadata_king_HP,1)*1000`. Includes king. Missing side minimum is 0 (`:94–103`; rounding ties-even: `C/engine-rs/src/lib.rs:34–35`).
- **E (early king damage)** = enemy king missing-HP fraction while both enemy princesses survive, minus the equivalent for us. It is multiplied by **−.20**, so premature damage to the opponent king is explicitly penalized (`leaf.rs:104–105,179`).
- **B (board)** = `clip((sum_remaining_value0 - sum_remaining_value1)/16,-1,1)`, over live troops/buildings excluding crown towers (`:21–26,106–114`). Per body, `remaining_value = (.75*elixir_share + .25*intrinsic)*clip(current_HP/max_HP,0,1)`, where share is C56 leaf metadata or `card_cost/body_count`; if share≤0 it becomes intrinsic. `intrinsic = .25 + .80*clip(sqrt(max_HP/1000),.25,2) + .35*clip(DPS/180,0,2)`; DPS uses damage divided by max(attack interval in seconds,.25) (`:28–45`).
- **D (danger)** = `clip((danger_to_side1 - danger_to_side0)/8,-1,1)`. For each enemy body, find the nearest surviving friendly tower, estimate ETA to attack range (distance minus range, divided by speed, with charge/slow/haste rules), then add `remaining_value * exp(-min(ETA,30)/4) * (.60 + .40*(1 - tower_HP_fraction))`. Out-of-range stationary buildings contribute 0 (`:115–167`). This is a hand-made proximity/threat term.

No term in this function values **holding a particular card, cycling to an answer, hidden future threats, or the option to spend later**. Their effects can enter the simulated 8-second future, but unspent hand cards themselves add no leaf value. That is a direct observation about the function, not proof that every misplay comes from it.

The live `-res` variant adds a **separate root penalty**, not an RL reward or part of leaf.rs: subtract `.015 * max(0, R-(root_elixir-card_cost))/R` from plays when no enemy troop/building is on our half; R is the deck's cheapest ground-hitting troop/building cost (`C/bot/search/reserve.py:1–16,19–27,40–51,93–97`). Timed-wait bonuses and this penalty also mean deployed root ranking is not leaf phi alone (`C/bot/search/lopp.py:339–340`).

### (b) Running HP1 RL: already outcome-only, human-init, no heuristic leaf target

Verified both registration and actual 01 files. `J/run/learner.json:4,17–21,42` gives v2 init, KL coefficient .05, gamma1, lambda.95, exploration kappa/T=.1/.1, calibrated gate threshold .019753086419753086. The actual actor maps match winner to **+1 win /0 draw /−1 loss** (`J/source/bot/rl/actor.py:316–319`). No crown margin, tower damage, elixir, unit, or leaf-phi reward is added.

The actual learner (same bytes as C) fills every row with the outcome label, then uses it **only as terminal reward on the last row** for GAE; earlier rewards are 0 (`C/bot/rl/learner.py:95–99,112–125`). Value training:

- First 3 updates: critic-only Monte Carlo outcome MSE; policy frozen.
- Later: `A = GAE(gamma=1,lambda=.95)`, `target = A + V_old`, then critic MSE against that target (`:230–264`; warmup count `J/run/learner.json:10–11`). Thus the post-warmup value target is a bootstrapped lambda-return to the **match result**, not directly phi or tower HP.
- Separate critic trunk plus training-only opponent embedding; tanh scalar value (`J/source/bot/rl/learner.py:49–57`). Policy loss is clipped PPO plus **.05 KL to frozen human v2**, not to a search teacher (`C/bot/rl/learner.py:268–276`; `J/run/learner.json:4,17`). KL is a prior/regularizer, not a shaped environmental reward.

Actual launcher mixes half RoyaleSim Sam-deck L16 and half our-engine full-pool L16; league K4CW-fp20%, R3a20%, f1a2 20%, rl5 10%, v1 10%, self20% (`J/source/bot/rl/hp1_run.sh:26–37`; `C/reports/bot/hp1/RL-PREREG.md:41–58`). Search-generated **opponent behavior** does not make the learner's targets search scores.

At this snapshot there is already an encouraging **selection-only** DEV result: HP1 v10 minus v2 = +.1167 vs strong on Sam, +.15 vs R3a, +.1333 on DD1; n60 each, mean+.1333. G-B confirm is running and incomplete in the pinned report (`C/reports/bot/hp1/RL-RESULTS.md:112–128,160`). SSH also confirmed ongoing training: `J/run/train.jsonl:32` was update32/version29 at `2026-10-18T10:13:29Z`. **Neither training score nor DEV selection establishes a held-out gain or superiority to search.** No job was modified for this research.

### (c) Earlier ExIt, rl5-v10, and f1a2 are not the same kind of target

**ExIt / it5s2:** loss trains the **softmax of the search teacher's root scores**, T=.003, gate/play decomposition, timed waits folded into WAIT, then calibrates student play rate to the teacher (`C/bot/exit/train.py:6–19,142–155`). The label recorder explicitly saves chosen root action, candidates, and complete style scores (`C/bot/exit/label.py:3–17,73–95`). These are search-policy targets, not outcome-based policy gradients. The student therefore inherits the teacher's finite horizon, leaf priorities and candidate/rollout limitations; it is not directly regressing leaf phi but imitating actions ranked by it.

**rl5-v10:** it5s2 → RL r4 → v29 → RL r5 v10; documented checkpoint SHA256 `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19` (`C/reports/bot/exit/PROGRESS.md:1106–1108`). Its reward already was **terminal +1/0/−1 with no tower shaping** (`C/reports/bot/rl/DESIGN.md:6–22`). Actual old-run receipt read on01, `/mpac/sdicks02/jobs/clasher/bot-rl-r5/learner.json:4,14–19`, confirms init v29, policy lr3e-5, KL .01, gamma1 and **lambda1**. Consequently the value target is Monte Carlo match outcome after GAE cancellation, unlike HP1's lambda.95 bootstrapping. Search is the inherited **init/anchor lineage**, not the RL target. F9 reported mean +.059 [.031,.087] over it5s2; subsequent comparisons have caveats and flattening (`C/reports/bot/exit/PROGRESS.md:1091–1109,1511–1517`).

**f1a2:** another search-distillation stage initialized from extended rl5-v10, mixing G1 full-pool labels and the older corpus 1:1 (`C/reports/bot/fullpool/PROGRESS.md:298–305`; same ExIt objective above). Thus a model can first escape some teacher behavior through outcome RL and then be pulled toward search again by later supervised refitting. Calling all these models “RL students” conceals that distinction.

## 4. Assessment: what the results support and do not support

### Evidence consistent with a heuristic limitation

1. The leaf prices immediate tower pressure and surviving deployed bodies but has no explicit hand/option value. The bot progress report connects cheap bridge spending and Giant/Fireball hoarding to this mechanism, and records **reserve +.18 [.07,.30] vs K4C-r16** on 100 paired cases (`C/reports/bot/PROGRESS.md:74–78`). This is a useful intervention on resource allocation, not a controlled proof that the leaf is the sole cause.
2. **Human v2 can beat a newer distilled student.** HP1 S0: H−f1a2 **+.14 [.02,.26] vs R3a**, **+.06 [−.06,.18] vs K4C-r16**, 100 paired cases each (`C/reports/bot/hp1/S0-RESULTS.md:23–41`). The strong row is unresolved; this supports testing a human prior rather than claiming it already beats search. V2 also has much more Zap/Giant/Arrows/Tornado/Bats coverage than old v1, so data coverage is a competing explanation (`C/reports/bot/hp1/DESIGN.md:20–32`).
3. ClashAI's tower/crown shaping drifted its gate, and Hasty's bandit comments explicitly document how a low tower-chip weight taught the wrong preference (`A/README.md:299–301`; `H/scripts/brain/experience.py:68–80`). Hand pricing can fail. Those are evidence about particular systems, not proof of the same causal effect here.

### Evidence against calling it a demonstrated cap or removing search now

1. **PF1, account levels, 150 pairs/opponent:** search scored .3933 vs strong; rl5-only .1667, f1a2-only .1800. Policy-minus-search **−.2267 [−.3067,−.1467]**, **−.2133 [−.2933,−.1333]**. Against R3a, gaps −.3667/−.3133 also clearly negative (`W/reports/coordinator/readouts/pf1-20261018.md:12–18`). These are account-level results with the live fast decode, not a general L16 claim.
2. **NS2, L16, 300 pairs/opponent:** search−rl5-only vs literal K4C-r16 **+.11 [.04,.18]**, primary superiority criterion met. Search−f1a2 **+.1767 [.1133,.2367]**; weak-row search−rl5 intervals individually include 0 (`W/reports/coordinator/readouts/ns2-20261018.md:34–47`). K4C-r16 here differs from PF1's LIVE-K4CW-r16-fp. Search using this heuristic is still a measured improvement over current fast policies.
3. **HZ1: longer horizon did not cure it.** Relative to8s,12s lost **15pp [5.75,23.75]** vs strong;16s lost **24.25pp [14.75,33.50]**;5s point estimate also negative. 200 paired strong cases/arm; sensitivity excluding the declared GoblinHut mapping gap kept negative strong signs (`W/reports/coordinator/readouts/hz1-20261018.md:9–25`). Longer rollouts also change how much we trust continuation/opponent modeling; this experiment does not isolate the leaf from rollout-model error or prove that game strategy cannot be learned.
4. **Learned leaves have failed repeatedly.** The earlier genuine outcome-fitted leaf achieved held-out AUC roughly equal to phi but pure-V online search lost28–43pp in cited screens, learned near-zero board weight and **negative elixir weight**; a25% blend was null (`C/reports/bot/value-search/PROGRESS.md:21–34`; actual outcome-label design `C/bot/value/fit.py:1–10`). Later four designs—state value, realized sibling change, MC change with aggregate features, MC body-set model—lost to phi on clean held-out sibling pairs; best cited body-set pair accuracy .593 vs phi .612, and phi agreed80% with MC pairs >3SE. Learned hold-back/receding-horizon arms lost on two confirmations (`C/reports/bot/PROGRESS.md:142`). Not all later targets were pure outcomes: several used 30-second crown/HP margin (`C/bot/fullpool/leaf_value.py:8–18`). Neither failure proves every future outcome-trained value will fail; neither supports “replace phi with a trained net” without a decision-level test.
5. Our own rl5 outcome PPO already improved on an ExIt init, and the current HP1 DEV screen is positive. Conversely, later rl5 continuations flattened on F10 (`C/reports/bot/exit/PROGRESS.md:1091–1108,1511–1517`). This is inconsistent with a strict inability to improve beyond search supervision, but also insufficient to promise that changing reward alone solves strength.

**Inference:** the current search objective is incomplete and can transmit its preferences to students. Whether that is the dominant remaining limit is unproven; data/card coverage, delayed observations/actions, candidate quality, opponent modeling and learning credit assignment remain live alternatives. The findings above do not establish that Clash Royale is too complex for learned win-probability models, nor that successful systems learn from match results alone.

## 5. Concrete recommendations, ordered by information gained

These are proposed experiments/decisions, not changes made by this researcher.

1. **Finish/read the existing HP1 G-B first; keep its reward unchanged.** It already performs the requested clean outcome-learning test: human v2 → terminal ±1/0 PPO, with no search-distillation loss. DEV v10 is positive and a confirm already exists; creating another duplicate arm or changing the active reward would throw away that comparison (`C/reports/bot/hp1/RL-RESULTS.md:112–128`). Use registered matched v2/f1a2 comparisons, strong opponent separately, max-level Sam+DD1, with account-level row secondary (`C/reports/bot/hp1/RL-PREREG.md:65–105`). Before a policy-only deployment decision, require a direct paired comparison with **current search**, because PF1/NS2 currently favor search.
2. **Use pure terminal win/draw/loss as the primary objective.** Do not add tower HP, elixir, troop survival, “human-like” play counts or spell frequency as rewards to fix symptoms. Record these as diagnostics. A terminal crown-margin bonus is an optional *separate* ablation only: declare its coefficient first and still select on win/draw/loss. Crown bonuses change preferences among wins/losses and are unnecessary to make HP1 outcome-driven; ClashAI's crown predictor is auxiliary, not evidence that its PPO needs such a bonus. Hasty's shaped old PPO did not establish live superiority.
3. **Keep the human-init outcome policy free of compulsory search distillation during this comparison.** ExIt remains useful to compress a demonstrably stronger search teacher or supply candidates; it is not the right objective for testing whether the human-prior policy can escape that teacher. Do not re-label/re-distill the successful HP1 arm from today's heuristic teacher before judging it. If later using outcome-improved search, distill as a separate branch and test whether it beats both teacher and undistilled HP1. Evidence: ExIt explicitly copies teacher scores, f1a2 reintroduced them after rl5, and human v2 beats f1a2 on one paired S0 row.
4. **If HP1 stalls, first isolate credit assignment rather than invent a shaped reward.** Compare a frozen-start continuation with lambda1 (Monte Carlo outcome) against HP1's lambda.95, holding init/league/compute/KL/decode fixed. Old rl5 used lambda1 and the earlier design dropped .95 when its critic was weak (`C/reports/bot/rl/DESIGN.md:19–22`; actual old-run JSON above). Validate the critic against held-out *eventual outcomes* and within-root action ordering; HP1's reported training explained variance is against its bootstrapped lambda-return (`C/bot/rl/learner.py:241–245`), so a high number alone is not independent evidence of accurate rest-of-game values. This is a proposed diagnostic, not a diagnosis that HP1's critic has failed.
5. **Only reopen learned-leaf search with an outcome-ranking test the old models did not pass.** Sample roots with several legal actions; apply each through the measured 27-tick command lag; use paired, repeated continuations to terminal results against a fixed, varied strong league; train/rank on terminal outcomes with game/root-held-out splits. Compare phi, human-policy preference, outcome value and actual Monte Carlo action ordering within the *same root*. Require improvement on sibling ordering and an online paired strong+DD1 test before changing the leaf. Existing MC leaf work used short-horizon crown/HP margin and specific continuation models; that does not validate terminal win-value search (`C/bot/fullpool/mc_gen.py:6–18`; `C/reports/bot/PROGRESS.md:142`). A learned value of future policy performance can still be wrong on rollout leaves. Retain8s as the measured reference; do not assume longer horizons help after HZ1.

No running jobs, settings, checkpoints, code, external repositories, or their refs were changed. Only this readout is published.
