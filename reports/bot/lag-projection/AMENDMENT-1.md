# LP1 amendment 1 (play-quality owner, before any LP1 outcome game)

Pins the treatment the preregistration (PREREG.md, fa07883e4; BASE 202492701121077) left to the Opus adapter.

**Projection semantics (bot/search/lagproj.py, token `LP26`).** Scoring is unchanged: the rollouts already apply our
action after the 27-tick command delay, so re-projecting the root would double-count lag. What is not lag-aware is the
candidate list: the scripted ranks and the R3a proposals rank tiles on the decision-time board. LP26 keeps every current
candidate and appends the same proposers' picks on a projected packet: the planner's root (R.root; own HUD as the
opponent record, its own rng) stepped 26 ticks with no new commands, surviving bodies' positions and HP written back,
dead bodies removed. Affordability, hand slots and the action mask are the decision-time ones. No hidden state.

**Arms:** `res-lb-wintp` (plain, live serial twin) and `res-lb-LP26-wintp`. Physical command delay 27 both arms.

**Pins:** driver bot.livediag.l16_cadence (`--own-deck`, `--pair-opponents`), runner bot/pq/l16.sh, runtime
live16402b-r3; own deck HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie; pool v3.2
(`/mpac/sdicks02/jobs/clasher/bot-cycle/lvg2/battlelog-pool-v3.2.jsonl`, sha256 01732d23…) 53 King-9 rows with
logged levels (no Goblin Hut); vocab-full.json. Seeds BASE+10000+i, i=0..149, the same for both opponents
(`--base 202492701131077 --pair-opponents`). Rows L16 and account (ours as RF1's account row; opponents logged levels).
1200 games. Readout and metrics as reports/bot/pq/RF-PREREG.md, plus CPU-ms per decision and LP candidates added per
decision. Prediction unchanged: LP − plain > 0 vs K4CW-fp; ship rule as RF1 (pooled 300 pairs vs K4CW-fp).
