# ML for Clash-Royale-like games: what is proven, what we have, what is new (2026-10-01)

Five web-research subagents (architecture; training paradigms and budgets; search and privileged
distillation; human data and offline RL; PPO stability, evaluation and sim-to-real) read the primary
papers this session. Tags in their reports: [read] vs [memory]. This file is the coordinator's
synthesis; claims about our own code were checked in `src/clasher/rl/model.py`,
`structured_obs.py`, `oracle_planner.py` and `strategy.md`.

## 1. Headline

No model-free RL success in this game class used fewer than about 3e8 decisions (Gym-uRTS, perfect
information, vs scripts); most used 1e9-1e13. Our runs are 5e6 decisions (about 4,200 matches) at
about 60 decisions/s per run, so the smallest proven budget is about two months per run on this Mac.
Every success below 1e8 decisions replaced on-policy RL with (a) a search oracle distilled by DAgger
or (b) human/offline data. The only strong published Clash Royale result is (a): Supercell/Aalto
(arXiv 2012.12186), 300 battles of a full-state planner, follower beat the production human-BC bot
(76M frames) 71.4%. Our approved strategy makes PPO the main path and the oracle and human data
optional; the evidence says the main path is the unprecedented one.

## 2. Experience budgets (decisions/steps unless noted)

| System | Method | Experience | Result |
|---|---|---|---|
| OpenAI Five | self-play PPO | ~1e13 frames, 80k-173k CPUs | beat world champions |
| AlphaStar | human BC + league, KL to BC | ~2e11 per agent | Grandmaster |
| ROA-Star / SCC | BC + league | 5e10 / 4e9 | pro level |
| Honor of Kings 1v1 | dual-clip PPO self-play | ~500 human-years/day, 48 GPUs | 99.8% vs top humans |
| ByteRL, DouZero, PerfectDou, AlphaHoldem, DeepNash | self-play variants | 2.5e9-1e11 | top bots / expert humans |
| RAISocketAI (microRTS) | PPO self-play + scripts | 1.5e9 | competition winner |
| Gym-uRTS | PPO vs scripts | 3e8 | 91% vs bots |
| Suphx | SL then self-play | 1.5M games | 10 dan |
| Metamon (Pokemon) | offline RL on reconstructed human replays + self-play | 475k replays -> 5M trajectories | top 10% ladder |
| Supercell CR follower | oracle tree search + DAgger (Q-regression) | 300 battles | 71.4% vs human-BC bot |
| Supercell CR human-BC | BC, 4000+ trophies | 76M frames | production bot |
| **Clasher pilot** | PPO from scripted clone | **5e6 per run** | 1 of 3 seeds improved |

## 3. Architecture

| Component | Evidence | Clasher |
|---|---|---|
| Full legal-action masking | microRTS 0.73-0.82 vs 0.0-0.32; every strong system | have |
| Attention over entities | AlphaStar ablation +35 points | have |
| Pointer/target attention for the action target | AlphaStar +29, Tencent 1v1 | have (tile keys x card query, cross-attention to entities) |
| Entities scattered onto the map + conv/ResNet path, spatial position head | AlphaStar +16; Supercell's own bots; all grid-game winners | **missing** (tiles attend to entities; no conv path) |
| Privileged (full-state) critic | AlphaStar 22% -> 82%; Tencent 5v5; PerfectDou | have |
| Explicit timing/no-op treatment (delay head, time-to-next-action target, no-op down-weighting) | AlphaStar +7; TStarBot-X 68 -> 85%; KataCR 22 -> 195 actions/game | **partial**: separate play/wait factor, per-tick decision, no delay target, no rebalancing; `event_policy.py` is planned but not integrated |
| Recurrent memory (LSTM) | mixed: helps Tencent RL; hurts AlphaStar-Unplugged BC (70 vs 84 memoryless); absent in Supercell, DeepNash, JueWu-SL, microRTS, Generals | have LSTM(256) + history slots; LSTM is the least-supported part and forces 2-sequence minibatches |
| Transformer memory | pays only at 1e10+ frames; less sample-efficient than LSTM on short memory | not used (correct) |
| Model size | 0.2-5.4M at small budgets; 17-159M only with billions of frames | 2.6M (in range) |
| Half-tile placement | no source tests it; both CR papers use 18x32 tiles | 576 tile centres; open question |

## 4. Training style

Proven building blocks, in the order the evidence supports for a small budget:
1. **Human BC as the starting policy.** AlphaStar supervised: top 16% of ladder; JueWu-SL: High King;
   Supercell production bot. Needs: skill filtering, resampling near actions (JueWu: 21% without),
   time-to-next-action target, wide pre-train then narrow fine-tune (AlphaStar Unplugged 65 -> 84 -> 89%).
   One-step advantage-weighted BC modestly beats BC; Q-learning and return conditioning do not.
2. **Search oracle as teacher.** Full-state fixed-depth search with Thompson sampling, "no more
   deploys" rollout value, follower regresses the planner's Q-values on states the follower visits
   (DAgger). Soft or Q-based targets beat argmax (ExIt +50 Elo; Gumbel MuZero); naive imitation of a
   privileged expert fails (Suphx, ADVISOR), which explains both prior data points (itzik123 +0.045,
   ClashAI got worse). `oracle_planner.py::FixedDepthThompsonOracle` and
   `kl_regularized_candidate_target` already implement this design here; unused so far.
3. **RL fine-tune last**, with KL to the BC policy (AlphaStar 1020 -> 1400 Elo; VPT loses skills
   without it), critic-first then actor learning-rate ramp (PIRLNav), sample reuse near 1, large
   batches, shaped -> sparse reward, fixed opponent mix (mostly strongest available, plus scripts and
   loss-weighted past checkpoints).

## 5. What the evidence says about our PPO recipe (v7r2 collapses, v7r3 fix)

Ranked likely causes of the seed divergence:
1. Data per update: 8,192 decisions is about 7 match outcomes (OpenAI Five's smallest ablation 61k;
   DeepNash 768 games per update). Minibatches are 2 full sequences (256 correlated decisions), 64
   optimizer steps per update at lr 1e-4.
2. The play/wait decision is unprotected: at a 10% play rate a KL budget of 0.02 allows halving the
   play rate in one update. The two collapses are the two ends of this head.
3. Critic not ready (explained variance 0.16-0.67 after ~137 match outcomes) = PIRLNav failure mode.
4. Learning rate 1e-4 is high for a fine-tune at this batch size.
v7r3: KL anchor and longer critic warm-up are well supported; lambda 0.99 is weakly supported (128-step
rollouts cap it; raises variance). Missing: 8-16x more decisions per update, KL/anchor on the
play/wait head specifically, lower actor lr with a ramp. An anchor to a weak scripted policy also caps
the policy; it should point at a human-BC policy and be annealed.
Evaluation: 3 seeds cannot measure a collapse rate (2/3 gives a 95% interval of 9-99%); about 10 seeds
per arm are needed to show a fix; never report best-of-checkpoints on the selection games.

## 6. Proven elsewhere vs new ground

Proven: human BC at scale; oracle search + DAgger in Clash Royale; KL-regularised RL fine-tuning;
privileged critics; masking; entity attention; spatial heads; timing heads; leagues at 1e10+.

New ground for this project:
- A home-built simulator validated branch-by-branch against the real client (Tier A). No public
  project documents this; Supercell used its own engine.
- Full-match transfer from such a simulator to the real mobile client (Tier B). Nearest precedent:
  Rocket League (re-implemented physics, isolated tasks only) and community RocketSim bots.
- BC on states re-simulated from action-only logs under mismatched patches and a reduced card set
  (Metamon reconstructs replays but with correct dynamics; imitation degrades under dynamics mismatch).
- Multi-deck, multi-level generalisation (Supercell's follower and Hasty-CR used one fixed deck).
- Few-candidate (Gumbel-style) search on exact simulator rollouts instead of a learned model.
- Strong play from 1e6-1e7 model-free decisions: no precedent. This is the ground not worth breaking.
- Public strong ladder play: nobody has shown it.

## 7. Cost estimates for the oracle route (coordinator arithmetic, unmeasured)

Scalar engine: ~1,678 ticks/s single process (measured in hasty-cr.md). Reduced budget: 16 candidates
x 400-tick rollouts = 6,400 ticks = ~3.8 core-seconds per labelled decision. ~300 labels per game ->
~19 core-minutes per game; 300 battles -> ~95 core-hours (~8-10 h on 12 cores). Supercell's full
budget (~1,000 iterations x 25 s depth) would be ~5 core-minutes per decision, ~15,000 core-hours for
300 battles: not feasible without a faster simulator. State fork cost is unmeasured.

## 8. Recommended direction (needs a strategy decision; nothing here is launched)

1. Qualify the existing oracle planner as a player (paired games vs scripts and vs the seed-2903 1M
   checkpoint) and measure fork + rollout cost. Cheap; decides whether route 2 is viable on this Mac.
2. Human-BC warm start: reconstruct states (discard at first illegal replayed action; label with the
   recorded winner), wide-scope pre-train, narrow fine-tune, timing rebalancing. Needs the scope
   expansion decision (`scope-expansion/PLAN.md`).
3. Oracle DAgger with Q-regression/soft targets on student-visited states, reward loss kept.
4. PPO as the final stage only, with the fixes in section 5, anchored to the BC/DAgger policy.
5. Architecture changes worth testing first: timing target (integrate `event_policy.py`), a scatter +
   conv spatial path; test whether the LSTM earns its cost. Do not grow the model.

Sources: see the five subagent reports in the coordinator transcript (2026-10-01); key URLs:
arxiv.org/abs/2012.12186, 1912.06680, 1912.09729, 2011.12692, 2011.12582, 2308.03526, 2504.04395,
2504.04783, 2105.13807, 2402.08112, 2206.15378, 2203.16406, 2003.13590, 2007.12173, 1705.08439,
2206.11795, 2301.07302, 2405.00662, 2108.13264, 2205.05061; AlphaStar Nature paper (DeepMind PDF).
