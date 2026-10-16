# Live-gameplay diagnosis: slow defence, few spells, odd Cannons (bot lead, exploration tier)

Question (Sam, ~16 live ladder sessions of LIVE-K4L-R-gs-rw-fc-w200-t4-p4, rl5 v10 fast tier e188e2ae @0.5375):
(a) slow reactions / late Cannon vs Giant, (b) rarely casts spells, (c) Cannon in the wrong lane or across the bridge.
Policy (visible in sim) or live input/output (only live)?

**Answer: all three are POLICY.** They show in sim with the same player and deck, and the live inputs (hand, packet
timing, tile mapping) are sound. Mis-taps (~8–10% of taps play a different cheap card) are a separate live I/O
issue that the LIVE LEAD owns (tap guard from s44).

Code: `bot/livediag/` (live_metrics.py, sim_diag.py, root_scores.py, variants.py, sim_report.py). Data:
`/mpac/sdicks02/jobs/clasher/bot-livediag/` on 05 (live copies), 03/04/08 (sim). Resume: PROGRESS.md.

## 1. Live logs (75 sessions on the e16 deck; clean subset s29–s33 + s41: 24 sessions)

| metric | all e16 | clean |
|---|---|---|
| decisions by source | search 96.3%, fast-disabled 3.6% (stall guard), fast-error 0.1% | search 100% |
| 200 ms cutoff fired | 1 of 7,488 search decisions | 0 |
| search wall ms (per-session p95, median / max) | 54 / 122 | 55 / 91 |
| search WAIT share | 0.68 | 0.68 |
| plays per battle, Giant / Fireball | 0.37 / 0.48 | 0.54 / 0.50 |
| perceived in hand, Giant / Fireball (share of frames) | 0.90 / 0.89 | 0.92 / 0.88 |
| tracker card ≠ HUD card in the tapped slot | 10.9% | 10.7% |
| Giant pushes on our half / undefended before tower contact | 133 / 14% | 37 / 14% |
| first defence − Giant cross (s, p25/p50/p75) | −4.1 / −0.8 / +2.5 | −3.4 / −0.9 / +2.1 |
| elixir at Giant cross (p25/p50/p75) | 2.0 / 3.0 / 4.0 | 1.8 / 2.9 / 4.0 |
| gap after a search WAIT: 10 / 20 / 40 ticks | — | 134 / 174 / **1418 (82%)** |

- The fast tier never chooses a live move, and the deadline never binds. Every play is a completed search's choice.
- `stats: null` rows (61k) are off-cadence polls or `can_act` false. They are not decisions.
- **Hand: the bot knows it holds Giant and Fireball.** The loop owner checked 10,679 trusted HUD reads: the tracked hand
  holds Giant 99.2% of the time and Fireball 99.8%. It chooses not to play them.
- **Timing:** the packet trails perception by about 0.15 s (s41–s42, LIVE LEAD). Packet → our next play has a median of 3.25 s,
  about 1.5 s of which is search WAITs taken with elixir available (loop owner, 331 enemy plays).
- **Cannon (87 classified by the loop owner; 102 / 275 by me):** 57 of 87 are in the threat lane, 20 have no threat on our half, 5 are centre pulls,
  2 are wrong-lane (one against air) and 2 are pocket Cannons while a fight runs elsewhere. All 20 Cannons at y ≥ 15 are legal pocket placements:
  the enemy princess tower on that side was already down. The screen↔tile mapping is exact (median error 0.07–0.45 tiles).
- The pre-s44 Fireball counts may include a few false "5-HP king" Fireballs (fixed at s44, LIVE LEAD). This is minor.

## 2. Sim with the live deck (RoyaleSim 15.535, r1-total runtime)

Setup (`bot/livediag/sim_diag.py`): the e16 deck vs the mirror plus the 4 most frequent human-prior Giant decks; opponents
R3a, v1 and rext-bc; 34 cases each; our seat alternates. K4C-r16 is read on decks 1–4 only, because its frozen belief raises on
the mirror deck (24 errors).

| player | games | pool | Giant / game | Fireball / game | Giant in hand | Fireball in hand | gap after WAIT = 40 ticks | undefended Giant pushes | reaction s (p50 / p90) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| LIVE-K4L-…-w200-t4-p4 (wall, contended 04) | 44 | 0.78 | 0.27 | 1.32 | 0.97 | 0.83 | 79% | 5% | 2.9 / 7.4 |
| LD-K4L-R-gs-rw (deterministic twin; ab1 base) | 61+ | 0.93 | 0.39 | 1.03 | 0.95 | 0.88 | 82% | 6% | 2.9 / 7.7 |
| K4C-r16 (previous best bot) | 78 | 0.90 | 0.28 | 0.97 | 0.95 | 0.85 | 81% | 13% | 3.2 / 7.9 |
| rl5 v10 alone (fast student) | 102 | 0.78 | **0.07** | 1.20 | 0.97 | 0.85 | — (5-tick polls) | 6% | 2.9 / 8.4 |
| R3a alone | 102 | 0.69 | **2.00** | 1.72 | 0.70 | 0.81 | — | 3% | 3.2 / 8.7 |

- **Giant hoarding is policy and is shared by search and student.** Search (K4L, K4C) plays Giant 0.3–0.4 times a game
  and holds it in 95–97% of frames, as live does. The RL student plays it 0.07 times a game. Only R3a, the human-prior
  imitation policy, plays Giant normally.
  - **Note for the bot lead:** the full-pool student inherits the same teacher, so a teacher fix needs relabelling. That decision is yours.
- **The 2 s timed WAIT is policy.** It shows identically in sim (79–82% of post-WAIT gaps are 40 ticks).
- Fireball: sim search casts about 1 a game vs 0.5 live. The live shortfall is partly opponent-dependent: humans clump less vs
  bots, and some live Fireballs are perception-limited. Either way it is low for search and the student alike vs R3a's 1.7.
- Reaction times match live: median ~2.9 s in sim vs 3.25 s live.

## 3. Live roots: why it waits and why it skips Giant / Fireball (`bot/livediag/root_scores.py`)

Method: replay live s30/s31/s33/s41 through the deployed LiveSession + LiveTranslator with the deterministic twin and the rl5
fast tier, logging every search decision's candidate cards, R3a proposals and work-set scores.

- **Opening:** at tick 90, elixir ~9.2, hand Fireball/Giant/MiniPekka/Minions in every battle:
  - Giant has 8 candidates, 4 of them R3a proposals. Fireball has 7 candidates and 0 R3a proposals.
  - **Neither survives the balanced coarse scan into the top-8 learned work set.**
  - The search plays MiniPekka at the right bridge (action 1418), then Minions or Archers at ticks 100–110. That is about 9 elixir in about 1 s.
- **Then it starves:** from tick 150 to 330 it sits at 1–3.5 elixir with {Giant, Fireball, plus 4-cost cards}, often with zero affordable
  candidates. It then picks 2402, the 40-tick timed wait, which beats plain WAIT only by the bonus
  `oppmodel._bonus` = +0.01·sqrt(ticks/20)·(1 − elixir/10), i.e. +0.005–0.007 at 3 elixir.
- **Command delay is not the cause.** On 18 enemy-on-our-half roots (s41-m03), the defence set was re-scored at our command delay
  of 5/10/20/27/40 ticks. The preferred action flips in 2 of 18, both near-ties or tile changes.
- **Cannon vs air:** the native rollout config has Cannon `can_air: False, can_ground: True`, which is correct. It is not a fidelity bug.
  The 2 air-threat Cannons (2/87) are rollout-value choices.

## 4. Level mismatch: null (L11 vs true levels at the same roots)

Method (`root_scores.py --levels`, `root_report.py`):
- 359 live roots with an enemy on our half or a Giant visible, from 8 sessions (s30-m01/m02, s31-m04, s33-m04, s41-m01…m04).
- Each root's defence set was scored with K4L-R's scorer on two roots:
  - the frozen L11 root;
  - `bot/levels/root.ExactLevelRoot` with the account's levels (profile.OWN_LEVELS, towers 6/6), the fair opponent estimate and the level leaf native.
- Both roots use the same opponent sample. Where the search's sample held a card with no level export (Earthquake), both roots were rebuilt on a re-drawn sample.

| | roots |
|---|---:|
| threat roots | 359 |
| **no affordable play at all** (elixir starvation) | **188 (52%)** |
| with a play | 171 |
| true levels flip WAIT↔defend | 25 (15%): 17 toward WAIT, 8 toward defend |
| our command delay 5/10/20/40 instead of 27 flips WAIT↔defend (noise floor) | 27 / 25 / 16 / 23 |

- Mean shift of (best defence − best wait) under true levels: −0.011.
- Assuming L11 does **not** make search think a tower tanks the Giant. If anything, true levels wait slightly more, at the
  single-sample noise floor. This agrees with the null level-aware win-rate pilot. **No level prior for this symptom.**

## 5. Fix A/B (interim; fresh bank 3568068836231360, drawn 2026-10-16T18:12:47Z before any game)

- **Setup:** paired per case vs `LD-K4L-R-gs-rw`, the deterministic serial twin of the deployed player. Same rl5 fast tier; the live
  search completes before its cutoff, so the twin makes the live moves.
- **Cases:** 68 per opponent, R3a / v1 / rext-bc, in sim_diag order (opponent order is R3a first, so the interim rows are mostly R3a).
- **Interval:** 95% bootstrap CI over cases within opponent, equal opponent weights.
- **Arms:** `bot/livediag/variants.py`.

Interim, 2026-10-16T18:30Z:

| arm | n | Δ pool [95% CI] | R3a | v1 | Giant / game | Fireball / game | gap after WAIT = 40 ticks |
|---|---:|---|---:|---:|---:|---:|---:|
| base LD-K4L-R-gs-rw | 106 | — (R3a 0.853, v1 0.947) | | | 0.35 | 0.93 | 82% |
| -wcap10 | 84 | −0.059 [−0.160, +0.048] | −0.118 | 0.000 | 0.08 | 0.77 | 0% |
| -wcapE | 97 | −0.025 [−0.089, +0.037] | −0.015 | −0.035 | 0.31 | 0.86 | 30% |
| -wint | 104 | −0.057 [−0.128, +0.008] | −0.059 | −0.056 | 0.31 | 1.02 | 58% |
| -h240 | 87 | +0.015 [−0.037, +0.074] | +0.029 | 0.000 | 0.43 | 0.77 | 78% |
| -gf | 29 | 0.000 [0, 0] (stopped) | 0.000 | | 0.38 | 0.97 | 81% |

- **Timed waits:** removing or interrupting them does not help in sim. The 2 s waits are a symptom of elixir starvation,
  not its cause: they are cheap banking when nothing is affordable.
- **-gf is identical to base on every case.** Giant and Fireball do get learned values (the work set grows from 12 to 13–14),
  but they never win. **The scorer itself ranks a back Giant or a banked Fireball below cheap bridge plays**, and pruning
  plays no part. -gf and -wint-gf were therefore stopped.
- **Running on the same bank and pairing:**
  - `-res`: elixir-reserve penalty 0.015·max(0, R − (elixir − cost))/R, applied to non-defensive plays.
    R = 3 is derived from the deck's cheapest ground-hitting unit.
  - `-h240-gf`;
  - `-ew30`: leaf elixir weight 3.0.
  - Final rows to follow. **The read is weighted on rext-bc** (human-imitation, closest to the ladder).
- **Deployment rule (bot lead):** deploy only an arm that wins on the pooled fresh bank and doesn't lose on rext-bc. If
  none wins, the honest answer is: the behaviour is policy, it costs little or nothing in sim, and the real fix is training.
  That means a teacher with a longer horizon or a reserve term, then relabelling the student. The full-pool student inherits the same teacher.

## Answer to Sam (as it stands)

- (a) Slow defence:
  - The bot opens by spending ~9 elixir in ~1 s on cheap bridge plays (MiniPekka at the right bridge).
  - It keeps spending on cheap cards, so when a Giant crosses it has ~3 elixir and a hand of Giant, Fireball and 4-cost cards.
  - It then waits in 2 s blocks.
- (b) Few spells: search's 8 s rollouts value a cheap chip play above Fireball and Giant. The RL student learned the same.
- (c) Cannons: mostly sensible. Pockets are legal, and a few wrong-lane or anti-air Cannons are rollout choices.
- None of this is a perception, latency, tile-mapping or level problem. All three show identically in sim.
  The mis-taps (~8%) are the one live I/O problem, and the tap guard (s44+) addresses them.
