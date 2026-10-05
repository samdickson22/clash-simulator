# How other Clash Royale bots train (landscape scan, 2026-10-01)

Sources: our earlier reviews (clashai.md, hasty-cr.md) plus a web scan (subagent, 2026-10-01).
Headline: the strongest documented bot is Supercell's own production bot (behaviour cloning on
76M frames of 4000+ trophy replays, heads: deploy-now / card / position / value). An oracle-search
agent distilled with DAgger beat it 71.4% (Boney et al., arXiv 2012.12186). Model-free Q-MC lost
85% to the BC bot; DQN was unstable. No public project shows strong ladder play.

| Project | Environment | Method | Best reported result |
|---|---|---|---|
| Supercell / Aalto (arXiv 2012.12186) | Supercell engine | Human BC (production); oracle tree search -> DAgger follower | follower 71.4% vs Human-BC; Human-BC 85% vs Q-MC |
| itzik123/ClashRoyaleAi | own C++ sim, 132 cards | recurrent PPO (CNN+LSTM), 1-ply utility teacher, PFSP | lookahead 0.625 -> 0.944 vs heuristic; distillation only +0.045 |
| vegetableleaf/ClashAI | native libg sandbox + live | BC on IL_Replay, transformer, search teacher | engine 74% vs ghosts -> 35% live (n=37); all RL null |
| hastylmao/Hasty-CR | own Python sim | BC from rule bot -> PPO, value warm-up, target-KL, league | 93% (56/60) in own sim vs its BC teacher; no live result |
| KataCR (arXiv 2504.04783) | real game, YOLO | offline RL (StARformer), time-to-next-action target | ~5-10% vs top built-in AI |
| SEAT (IJCAI-19) | clone | Q-learning + placement heatmap | 70-90% vs rule bots, n=10 |
| JueWu-SL (Honor of Kings) | analogue | pure SL on top-1% players, scene-based resampling | High King level |
| AlphaStar (StarCraft) | analogue | human BC -> league RL with KL to BC policy | Grandmaster |

Lessons: (1) human BC is the strongest plain cold start; (2) search on a simulator gives large
gains, naive argmax distillation gives small or negative ones; (3) separate "when" head and
timing-data rebalancing; (4) reward near win/loss + tower HP; (5) paired seeded evaluation;
win rate vs untrained copies or ghosts overstates strength.
Data: RoyaleAPI says its replays may not be shared; IL_Replay states no license.
Full per-project notes: subagent report in the 2026-10-01 coordinator transcript.
