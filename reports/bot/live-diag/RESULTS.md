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

## 5. Fix A/B: final on bank 1 (fresh bank 3568068836231360, drawn 2026-10-16T18:12:47Z before any game)

- **Pairing:** per case vs `LD-K4L-R-gs-rw`, the deterministic serial twin of the deployed player with the same rl5 fast tier.
  The live search completes before its cutoff, so the twin makes the live moves.
- **Cases:** 68 per opponent (R3a / v1 / rext-bc) × the live e16 deck vs Giant decks; n = 204 per arm; 0 errors.
- **Interval:** 95% bootstrap CI over cases within opponent, equal opponent weights.
- **Base scores:** R3a 0.853, rext-bc 0.985, v1 0.912; pool 0.917.

| arm | Δ pool [95% CI] | R3a | rext-bc | v1 | Giant / game | Fireball / game | elixir at Giant cross p50 | gap after WAIT = 40 ticks |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| base | — | | | | 0.36 | 0.89 | 2.95 | 83% |
| -wcap10 | −0.049 [−0.103, +0.005] | −0.118 | −0.029 | 0.000 | 0.08 | 0.71 | 2.73 | 0% |
| -wcapE | −0.010 [−0.054, +0.039] | −0.015 | 0.000 | −0.015 | 0.29 | 0.90 | 3.00 | 30% |
| -wint | −0.029 [−0.078, +0.015] | −0.059 | −0.029 | 0.000 | 0.28 | 0.88 | 2.86 | 59% |
| -h240 | +0.015 [−0.034, +0.064] | +0.029 | −0.015 | +0.029 | 0.38 | 0.74 | 2.89 | 79% |
| -h240-gf | +0.015 (identical to -h240) | | | | 0.39 | 0.77 | 2.86 | 79% |
| -res (λ 0.015, R = 3) | +0.015 [−0.034, +0.064] | +0.044 | 0.000 | 0.000 | 0.39 | 0.79 | **3.54** | 78% |
| -ew30 | −0.039 [−0.098, +0.015] | −0.074 | −0.015 | −0.029 | 0.62 | 0.83 | 2.79 | 82% |
| -gf | 0.000 (29 cases, identical; stopped) | | | | | | | |

**Read.**
- **Timed waits:** removing or interrupting them never helps in sim, and every such arm leans negative. The 2 s waits are a
  symptom of elixir starvation (cheap banking when nothing is affordable), not its cause.
- **-gf** is identical to base, and -h240-gf to -h240, on every case. Giant and Fireball do get learned values (work set 12 →
  13–14), but they never win. **The leaf value and horizon rank a back Giant or a banked Fireball below cheap bridge plays**,
  and pruning plays no part.
- **-res** is the only arm that moves the mechanism: elixir at the Giant cross rises 2.95 → 3.54, and it never loses on an
  opponent on bank 1. Its pooled CI spans 0.
- **BASE2 confirmation: NOT CONFIRMED.** Bank 2 is BASE2 = 580000520902944 (drawn 2026-10-16T18:53:30Z), 136 cases × 3 opponents, 408 paired games, 0 errors:

  | opponent | base | -res | Δ |
  |---|---:|---:|---:|
  | R3a | 0.882 | 0.853 | −0.029 |
  | v1 | 0.912 | 0.919 | +0.007 |
  | rext-bc | 0.993 | 0.963 | −0.029 |
  | **pool** | | | **−0.017 [−0.047, +0.015]** |

  Elixir at the Giant's cross rises 2.96 → 3.68. Banking more works mechanically but does not buy wins against these opponents. **Not deployed.**
- **rext-bc is saturated** with the live deck vs Giant decks (base 0.985), so it carries little signal here. R3a and v1 drive the deltas.
- **Deployment rule (bot lead):** deploy only an arm that wins on the pooled fresh bank and doesn't lose on rext-bc. Nothing qualifies yet.

### 5b. Against a STRONG opponent (bot lead: the sim pool is too weak to punish an elixir dump)

The opponent is `LIVE-K4CW-r16`: deterministic K4C-r16 with the live belief (the frozen K4C belief raises on our off-prior e16 deck). The opponent decks are
the Giant decks.

**BASE3** = 2390764269446208, drawn 2026-10-16T19:18:55Z before any game; 100 paired cases; 0 errors:

| | base LD-K4L-R-gs-rw | -res |
|---|---:|---:|
| score vs K4C-r16 | 0.41 | **0.59** |
| Δ [95% CI] | | **+0.18 [+0.07, +0.30]** (paired W/T/L 27/64/9) |
| elixir at Giant cross (median) | 3.46 | 4.43 |
| Giant / Fireball plays per game | 0.44 / 1.33 | 0.58 / 1.39 |
| undefended Giant pushes | 5.1% | 6.5% |
| reaction p50 | 2.65 s | 2.65 s |

- **Against an opponent that punishes the dump, the reserve term pays.** The weak pool (R3a / v1 / rext-bc at 0.88–0.99)
  hid it.
- This is the deploy case set by the bot lead: it wins vs the strong opponent and is neutral elsewhere (BASE2 pooled −0.017 [−0.047, +0.015]).
- The live A/B gate (§7) passes.
- A replication on BASE4 = 1870204031157424 (drawn 2026-10-16T19:31:33Z, 100 cases) is running.

### 5e. BASE5 (2439740075545088, drawn 2026-10-16T19:42:25Z): receding horizon and interrupt vs K4C-r16 (100 paired each, 0 errors)

| arm | score | Δ vs base [95% CI] | Δ vs -res | reaction p50/p90 s | Giant reaction p50 s | undefended Giant pushes | elixir at cross p50 |
|---|---:|---|---|---|---:|---:|---:|
| base | 0.51 | — | | 2.65 / 7.65 | 2.15 | 5.5% (3/55) | 3.30 |
| -res | 0.55 | +0.04 [−0.09, +0.16] | — | 2.65 / 7.65 | 3.65 | 5.0% (3/60) | 4.32 |
| -res-wint | 0.59 | +0.08 [−0.03, +0.19] | +0.04 [−0.08, +0.17] | 2.65 / 7.65 | 2.15 | 13.8% (9/65) | 3.82 |
| -res-rh | 0.47 | −0.04 [−0.16, +0.08] | −0.08 [−0.22, +0.06] | 2.65 / 7.15 | 2.65 | 10.2% | 3.61 |
| -rh | 0.28 | **−0.23 [−0.36, −0.10]** | | 2.65 / 6.65 | 3.15 | 10.8% | 2.88 |

**§5c (-res-rh) and §5d (-res-wint) verdicts.**
- -res-rh fails §5c.
- -res-wint fails §5d. Its Δ vs -res point estimate (+0.04) passes, but neither the overall reaction p50 (unchanged) nor the undefended share
  (13.8% vs 5.0%) improves. It does cut Giant reaction p50 by 1.5 s.
- So -res stays the live treatment. Package for an override or a later A/B: macsnap/pkg-wint.

**Reading.**
- Receding horizon alone costs −0.23 against the strong opponent. With the current scorer the committed timed waits ARE the banking, so per-tick play needs a
  learned hold-back term (option 2, now generated in -rh mode).
- -res vs base across three fresh strong-opponent banks: +0.18 / +0.08 / +0.04 (BASE3 / 4 / 5), mean ≈ +0.10.

### 5f. Plain wait arms vs K4C-r16 (BASE5; ~100 paired; 0 errors)

| arm (base 0.51) | n | Δ [95% CI] | reaction p50/p90 s | Giant reaction p50 s | undefended | elixir at cross p50 |
|---|---:|---|---|---:|---:|---:|
| -wcap10 | 97 | **−0.22 [−0.33, −0.10]** | 2.65 / 6.65 | 2.65 | 3.4% | 3.32 |
| -wcapE | 96 | −0.06 [−0.19, +0.05] | 2.65 / 6.65 | 2.15 | 4.2% | 3.00 |
| -wint | 100 | −0.06 [−0.19, +0.07] | 2.15 / 7.15 | 2.15 | 4.8% | 3.39 |

- Against the strong opponent, removing or interrupting the 2 s commitment loses: -rh −0.23 and -wcap10 −0.22. In the current scorer the timed waits are
  the elixir banking. Faster reaction does not buy wins until holding back is valued by the search itself.
- **Direction (Sam, 2026-10-16):** that is the option-2 learned term in -rh mode (TRAINING-FIX.md).

## 6. Handsync (tap guard, s44+) vs off (s41–s43)

Tool: `bot/livediag/handsync_cmp.py` on 12 battles off vs 10 battles on; Δ is on − off with a bootstrap 95% CI over battles.

| metric | off | on | Δ [95% CI] |
|---|---:|---:|---|
| reaction, enemy play (births proxy) → our next play: median s (per battle) | 3.80 | 3.71 | −0.09 [−1.41, +1.17] |
| reaction, mean s (per battle) | 4.16 | 4.03 | −0.13 [−1.05, +0.70] |
| search WAITs with elixir per enemy play | 0.58 | 0.58 | −0.01 [−0.21, +0.20] |
| plays per battle | 25.9 | 24.3 | −1.6 [−8.8, +5.5] |
| Giant pushes undefended before contact | 5 / 25 | 1 / 13 | −0.12 [−0.36, +0.08] |
| elixir at the Giant's cross | 2.82 | 3.12 | +0.30 [−0.58, +1.08] |

**Refusals.**
- The guard refused 87 of 330 tap attempts (26%): greyed 49, colour mismatch 33, empty 5.
- 16 of the 87 fell within 2 s of an enemy play while an enemy was on our half.
- The next play came a median 2.4 s after a refusal; only 5 of 84 replayed the guarded action.

**Verdict:** no measurable slow-down on this n. A ±1 s effect is not excluded.

## Answer to Sam (as it stands)

- (a) Slow defence:
  - The bot opens by spending ~9 elixir in ~1 s on cheap bridge plays (MiniPekka at the right bridge).
  - It keeps spending on cheap cards, so when a Giant crosses it has ~3 elixir and a hand of Giant, Fireball and 4-cost cards.
  - It then waits in 2 s blocks.
- (b) Few spells: search's 8 s rollouts value a cheap chip play above Fireball and Giant. The RL student learned the same.
- (c) Cannons: mostly sensible. Pockets are legal, and a few wrong-lane or anti-air Cannons are rollout choices.
- None of this is a perception, latency, tile-mapping or level problem. All three show identically in sim.
  The mis-taps (~8%) are the one live I/O problem, and the tap guard (s44+) addresses them.

## 7. PRE-REGISTRATION: live A/B, -res vs base (written 2026-10-16T19:20:49Z, before any -res live session)

Status: **gate PASSED** (§5b: +0.18 [+0.07, +0.30] vs K4C-r16). Gated on the strong-opponent sim check (§5; base vs -res vs LIVE-K4CW-r16 on BASE3 = 2390764269446208, drawn
2026-10-16T19:18:55Z, 100 cases). The gate passes unless -res is clearly negative there, i.e. it passes if the CI upper bound is ≥ 0
or the point estimate is ≥ −0.02. On a pass:
- **Arms:**
  - base `LIVE-K4L-R-gs-rw-fc-w200-t4-p4`;
  - treatment `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-res` (bot/search/reserve.py, λ .015, R = 3).
  - Fast tier rl5 v10 in both; everything else equal.
- **Live sequencing (LIVE LEAD, 2026-10-16):**
  - s50 = r3c, s51 = the new hand classifier (Archers↔Valkyrie fix). Both are **pre-A/B** and shared by both arms; neither is analysed as A/B.
  - From **s52**, sessions alternate per session, starting with -res at s52. If the full-pool bundle lands first, it goes in before s52 and the A/B runs on top of it.
- **Schedule (LIVE LEAD, 2026-10-16):**
  - The -res files ship in the s51 bundle; they are inert without the token. s51 is the base reference on the new hand model.
  - From **s52**, sessions alternate: **even = -res, odd = base**, about 10 each, through ~s71.
  - **The treatment may switch to -res-rh** (receding horizon) only if -res-rh beats -res vs K4C-r16 in sim BEFORE s52 starts. Otherwise the -res A/B
    finishes first and -rh waits.
  - Per-session analysis starts from s51 (s51 = base reference). Per-arm running totals go to the bot lead every ~4 sessions.
- **Assignment:** alternating ladder SESSIONS, about 10 per arm (~40 battles per arm). The LIVE LEAD sequences them: after one clean r3c
  session, or after full-pool if that bundle is ready first.
- **Arm attribution:** read only from each session's session-config.json `player` (and the manifest), never inferred.
- **Unit:** the battle. Included: sessions whose session-config player is one of the two arms, with the e16 deck, and battles with ≥ 100 logged
  decisions (the rule used in §1). Exclusions are listed with reasons.
- **PRIMARY (mechanism) metrics:** each is reported as a per-arm value and as treatment − base, with a bootstrap 95% CI over battles (4000 draws, seed 0).
  1. **elixir at the Giant's cross:** pooled over perceived enemy Giant pushes (live_metrics.analyse);
  2. **undefended Giant-push share:** pushes with no defence before tower contact over pushes (live_metrics.analyse);
  3. **reaction time:** enemy play (births proxy, handsync_cmp.births) → our next submitted play, per-battle median, then the mean over battles;
  4. **plays per battle;**
  5. **Giant and Fireball plays per battle.**
- **Expected direction from sim (bank 1, BASE2):** elixir at the cross up by ~+0.6, and Giant and Fireball counts about flat. The reaction-time and
  undefended-share effects in sim were ~0.
- **SECONDARY:** win rate (wins/battles per arm, from the LIVE LEAD's battle results). At ~40 battles its SE is ≈ ±0.11, so it is descriptive only.
- **Reporting:** results are reported as sessions land, with no sealing. Tools: bot/livediag/live_metrics.py and bot/livediag/handsync_cmp.py, using the
  same metric code as §1 and §6.

### 5c. -rh decision rule (fixed 2026-10-16T19:44:55Z, before any BASE5 result was read)
-res-rh replaces -res as the live treatment only if, on BASE5 (2439740075545088) vs LIVE-K4CW-r16 with 100 paired cases, the paired
Δ(-res-rh − -res) has a 95% CI lower bound > 0, and the result lands before s53 starts (~20:20Z). Otherwise -res stays the treatment, and -rh is
reported for a later A/B.

### 7a. Pre-registered amendment (2026-10-16T19:50:50Z, before any A/B arm result)
- **Mid-A/B perception change.** YOLO v9a-e8 replaces e16 at about 21:00Z (around s55–s57); the arms keep alternating.
- **Stratification.** Each session's perception version comes from session-config `units_source`. The analysis is stratified e16 vs v9a: adjacent sessions are paired
  within the same version, and results are reported per stratum and pooled, with stratum as a blocking factor. The bootstrap resamples battles within
  each stratum, and the pooled Δ is the battle-weighted mean of the stratum Δs.
- **Full-pool restart.** If the full-pool bundle wins its gate and goes live, the -res A/B restarts on top of it as a NEW A/B with a fresh count;
  it is never pooled across that change.

### 5d. -res-wint decision rule (fixed 2026-10-16T20:02:02Z, before any -res-wint game)
Direction from Sam via the coordinator: holding back must be learned, and committed timed waits cost reaction time. The test is
-res-wint (-res, plus interrupting a timed wait when the enemy count on our half grows or a new enemy card event arrives) vs -res,
on BASE5 = 2439740075545088 vs LIVE-K4CW-r16, 100 paired cases. BASE5 did not select -res-wint, and it pairs with BASE5's -res games.
- **Rule:** -res-wint becomes the live treatment if the point estimate of Δ(-res-wint − -res) is ≥ −0.02 AND either reaction p50 (enemy play → our next play) or the
  undefended-push share improves vs -res.
- **Timing:** if it qualifies before s53 starts, it goes in at s53; otherwise at the next A/B restart.

### 7b. Pre-registered: the full-pool phase of the -res live A/B (2026-10-16T21:29:05Z, before any full-pool session)
- **Phases (never pooled):**
  - **C56 phase:** s53–s57; base `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` vs `…-res`. Reported as its own small A/B.
  - **Full-pool phase:** from about s58, after the 00:00Z ladder resume (the ladder pauses 22:00–00:00Z). The full-pool bundle is live: base `…-mk1a1` vs treatment
    `…-mk1a1-res`, alternating per session.
- **Arms:** read from session-config `player`. The phase comes from the name (`mk1a1` present = full pool), and the treatment from the `-res` token.
- **Perception strata:** from session-config `units_source`: e16, v9a, and v11b (the resume model). Blocked as in §7a, within each phase.
- **Primary metrics:** the same as §7, i.e. elixir at the Giant cross, undefended Giant-push share, reaction (births proxy) p50 **and p90**, plays per battle, and Giant and Fireball per battle.
  Win rate is secondary. Each is reported per arm and as treatment − base with bootstrap CIs, per phase and per stratum.

### 7c. Live running totals (C56 phase)

**Totals 1** (2026-10-16T21:29:39Z): v9a stratum, base s52 + s54 (8 battles) vs -res s53 + s55 (8 battles); s51 (e16) is a base reference only.
Δ -res − base, with 95% CI:
- elixir at cross: −0.40 [−1.11, +0.42]
- undefended share: −0.21 [−0.57, +0.11]
- reaction p50: −0.20 s [−1.09, +0.64]
- plays per battle: +0.6 [−8.5, +9.6]
- Giant per battle: −0.25 [−0.88, +0.38]
- Fireball per battle: +0.75 [+0.13, +1.38]

Early; win/loss per battle requested from the LIVE LEAD (session.json has no result field).

**C56-phase FINAL** (2026-10-16T22:06:36Z; s51–s57)
- v9a stratum: base s52/s54/s56 (12 battles) vs -res s53/s55/s57 (12 battles). s51 (e16) is a base reference only.
- -res − base [95% CI]:
  - win rate 0.58 → 0.50: −0.08 [−0.50, +0.33];
  - undefended Giant-push share 22% → 3%: −0.19 [−0.51, +0.09], with Giant pushes faced: base 12, -res 31;
  - reaction p50 3.71 → 3.12 s: −0.59 [−1.75, +0.33];
  - reaction p90 8.63 → 7.45 s: −1.17 [−3.02, +0.30];
  - elixir at cross 2.66 → 2.40: −0.27 [−1.02, +0.63];
  - plays per battle: +1.8 [−5.2, +8.8];
  - Giant per battle: −0.25 [−0.67, +0.17];
  - **Fireball per battle 0.33 → 1.33: +1.00 [+0.33, +1.83].**
- Not pooled with the full-pool phase (§7b).

### 5g. Learned hold-back (option 2), dev screen on BASE6 = 467516450769760 (drawn 2026-10-16T21:54:26Z), vs K4C-r16, 100 paired, 0 errors

| arm | score | Δ vs base [95% CI] | Δ vs -res | reaction p50/p90 s | Giant reaction p50 s | undefended | Giant / Fireball per game |
|---|---:|---|---|---|---:|---:|---|
| base | 0.39 | — | −0.16 [−0.28, −0.04] | 2.65 / 7.15 | 2.15 | 10.4% | 0.41 / 1.35 |
| -res | 0.55 | +0.16 [+0.04, +0.28] | — | 2.65 / 7.65 | 2.65 | 5.5% | 0.55 / 1.34 |
| -rh | 0.42 | +0.03 [−0.11, +0.17] | −0.13 [−0.26, +0.01] | 2.65 / 6.65 | 2.15 | 8.8% | 0.14 / 1.07 |
| **-rh-lc10** | **0.56** | **+0.17 [+0.04, +0.29]** | +0.01 [−0.12, +0.14] | 2.65 / **6.65** | **1.65** | 10.9% | 0.66 / 1.15 |
| -rh-lc30 | 0.53 | +0.14 [+0.00, +0.27] | −0.02 [−0.17, +0.12] | 2.65 / 6.65 | 2.15 | 7.0% | 0.86 / 1.16 |

- **The model:** leafcorr-h600-v1, sha256 beae23112857fbf4…, a ridge fit on 1,163 rh-mode binding roots with a 30 s margin target. CV corr is +0.11, and +0.19 on K4C rows.
- **Result:** per-tick play plus the learned hold-back term matches -res's strength with no committed timed waits, and has the fastest p90 and Giant reactions.
- **κ = 1.0 (lc10) picked on this dev bank. Confirmation on BASE7 = 1029667185899056:** base, -res and -rh-lc10, vs K4C-r16 and rext-bc, 100 paired each.
  Success (bot lead): -rh-lc10 beats base and -res vs K4C-r16 and rext-bc.

### 5h. Confirmation of -rh-lc10 on BASE7 = 1029667185899056 (drawn 2026-10-16T23:23:49Z): NOT CONFIRMED on win rate (100 paired per opponent, 0 errors)

| arm | vs K4C-r16 | vs rext-bc | reaction p50/p90 s | Giant reaction p50 s | undefended (~305 pushes) | elixir at cross p50 |
|---|---:|---:|---|---:|---:|---:|
| base | 0.51 | 0.97 | 3.15 / 7.65 | 3.15 | 11.5% | 2.96 |
| -res | **0.66** | 0.97 | 3.15 / 8.65 | 3.65 | 8.9% | 3.71 |
| -rh-lc10 | 0.55 | 0.97 | **2.65 / 7.15** | **2.65** | **5.5%** | 3.00 |

**Paired Δ [95% CI]:**
- **-rh-lc10 − base:** K4C +0.04 [−0.07, +0.15]; rext-bc 0.00 [−0.05, +0.05].
- **-rh-lc10 − -res:** K4C **−0.11 [−0.23, +0.01]**; rext-bc 0.00.
- **-res − base:** K4C **+0.15 [+0.05, +0.26]**; rext-bc 0.00 [−0.04, +0.04].

**Reading.**
- **-res confirmed again.** Across four fresh strong-opponent banks: +0.18 / +0.08 / +0.04 / +0.15.
- **-rh-lc10 meets the mechanism goals** (fastest reaction, fewest undefended pushes, more Giants), but it banks less than -res (elixir at cross 3.00 vs 3.71) and does not win more.
- **The dev-bank +0.17 was κ-selection plus bank noise.** The full-pool check was not run (rule: only if BASE7 confirms).

### 5i. Sum arms (-rh + -res + learned term), dev screen on BASE8 = 1961762772645584 (drawn 2026-10-16T23:59:02Z), vs K4C-r16, 100 paired, 0 errors

| arm | score | Δ vs base | Δ vs -res | reaction p50/p90 | Giant reaction p50/p90 | undefended | elixir at cross p50 |
|---|---:|---|---|---|---|---:|---:|
| base | 0.48 | — | −0.06 | 2.65 / 7.65 | 2.15 / 6.15 | 1.7% | 3.14 |
| -res | 0.54 | +0.06 [−0.05, +0.18] | — | 2.65 / 7.65 | 2.65 / 6.65 | 3.4% | 3.98 |
| -rh-res | 0.42 | −0.06 [−0.20, +0.07] | −0.12 [−0.27, +0.02] | 2.65 / 7.15 | 2.15 / 5.15 | 11.3% | 3.63 |
| -rh-res-lc10 | 0.56 | +0.08 [−0.04, +0.21] | +0.02 [−0.11, +0.14] | 2.65 / 7.65 | 2.65 / 6.15 | 5.3% | 3.71 |
| -rh-res-lc10v2 | 0.58 | +0.10 [−0.03, +0.24] | +0.04 [−0.08, +0.17] | 2.65 / 7.65 | 3.15 / 6.15 | 7.3% | 3.54 |
| **-rh-res-lc20v2** | **0.62** | **+0.14 [+0.00, +0.28]** | **+0.08 [−0.05, +0.20]** | 2.65 / 7.65 | 2.65 / **5.15** | 4.3% | 3.68 |

- **Hypothesis:** the constant reserve gives the banking, lc the timing, rh the reaction. It holds in direction. -rh-res alone is again worse, and adding the learned term recovers it, more so at κ = 2.
- **lc v2:** leafcorr-h600-v2.json (sha256 d4462feb92d0e085…), 2,144 rh-mode rows, CV corr +0.09 (+0.11 on K4C rows), with the v2 features adding nothing over v1.
- **Selection:** -rh-res-lc20v2 was picked among 4 sum arms on this dev bank, so it carries selection luck.
- **Confirmation:** BASE9 = 1096741294598848 (drawn 2026-10-17T00:42:38Z), base / -res / -rh-res-lc20v2 vs K4C-r16 and rext-bc, 100 paired each.

### 5j. Confirmation of -rh-res-lc20v2 on BASE9 = 1096741294598848 (drawn 2026-10-17T00:42:38Z): NOT CONFIRMED vs -res (100 paired per opponent, 0 errors)

| arm | vs K4C-r16 | vs rext-bc | reaction p50/p90 | Giant reaction p50/p90 | undefended (~300) | elixir at cross p50 |
|---|---:|---:|---|---|---:|---:|
| base | 0.42 | 0.97 | 3.15 / 7.65 | 3.15 / 8.15 | 12.1% | 3.11 |
| -res | **0.61** | 0.99 | 3.15 / 8.15 | 3.65 / 8.15 | 8.0% | 3.79 |
| -rh-res-lc20v2 | 0.54 | 0.95 | **2.65 / 7.65** | 3.15 / **6.65** | 7.5% | 3.86 |

**Paired Δ [95% CI]:**
- **lc20v2 − base:** K4C +0.12 [0.00, +0.24]; rext-bc −0.02 [−0.07, +0.03].
- **lc20v2 − -res:** K4C **−0.07 [−0.19, +0.06]**; rext-bc −0.04 [−0.09, +0.01].
- **-res − base:** K4C **+0.19 [+0.08, +0.30]**; rext-bc +0.02 [−0.02, +0.06].

**Reading.**
- **-res vs base on the strong opponent over 5 fresh banks:** +0.18 / +0.08 / +0.04 / +0.15 / +0.19.
- **Per-tick + learned hold-back (2 confirmations):** it reaches the mechanism goals (faster reaction, fewer or equal undefended pushes, equal banking), but wins 7–11 pp less than -res against K4C-r16. The dev-bank gains were selection luck both times.
- **Next lever:** a leaf state value (vl, the full-pool owner), screened on BASE10.

### 5k. Leaf state value (vl, full-pool owner's c56v0 mlp-d30, sha256 5aae9a08…), BASE10 = 1005103301668240 (drawn 2026-10-17T01:12:42Z), vs K4C-r16, 100 paired, 0 errors

| arm | score | Δ vs base | Δ vs -res | reaction p50/p90 | Giant reaction p50 | undefended | elixir at cross p50 |
|---|---:|---|---|---|---:|---:|---:|
| base | 0.43 | — | −0.19 | 2.65 / 7.65 | 3.15 | 0% (0/44) | 3.36 |
| -res | **0.62** | **+0.19 [+0.06, +0.31]** | — | 3.15 / 7.65 | 3.15 | 15.8% (9/57) | 4.11 |
| -vl25-rh | 0.36 | −0.07 [−0.19, +0.06] | −0.26 [−0.39, −0.13] | 2.65 / 7.15 | 2.15 | 9.1% | 2.89 |
| -vl50-rh | 0.37 | −0.06 [−0.18, +0.06] | −0.25 [−0.39, −0.11] | 2.65 / 7.15 | 2.15 | 11.4% | 3.07 |
| -vl50-res | 0.39 | −0.04 [−0.15, +0.08] | **−0.23 [−0.34, −0.12]** | 2.65 / 7.15 | 2.15 | 10.3% | 3.64 |

- **The v0 leaf value is not a lever.** It adds no banking in -rh mode, and on top of -res it erases -res's gain. That is consistent with its weak or wrong elixir signs (on-policy, weak-opponent data).
- **The full-pool v1** (roots vs K4C-r16) is to be screened the same way when it lands.
- **-res vs base on 6 fresh strong-opponent banks:** +0.18 / +0.08 / +0.04 / +0.15 / +0.19 / +0.19.

### 7d. Pre-registered amendment (2026-10-17T02:30:48Z): deck stratum
- **The change:** the live deck changes at an upcoming session boundary to Valkyrie, Archers, Goblins, InfernoTower, Fireball, Giant, MiniPekka, Skeletons
  (05:/mpac/sdicks02/jobs/clasher/bot-deckopt2/FULLPOOL-PLAN.json).
- **Counting:** the -res A/B count restarts at the swap.
- **Stratification:** stratum = deck (from session-config `deck`) × perception model (`units_source`), within each phase. Arms are never pooled across decks.
- **Metrics:** Giant-push metrics still apply; "Cannon placement" no longer does (the building is InfernoTower).
- **Sim work:** running sims finish on e16. New live-mechanism sims (cycle-rule follow-ups, leaf screens) use the new deck.

### Level setting (standing rule from Sam, 2026-10-17T02:44:50Z)
- **The rule:** evaluate play with every card at MAX level (16, per live16402c gamedata items.rarities) on both sides, and towers at max King level.
- **Everything in this report up to now ran at level 11 on both sides:** sim_diag/RoyaleSim 15.535 without level arguments, and ours_diag/our engine (all-L11).
  That covers §2, §5–5k and the cycle-rule sizing (BASE11). These finish as is.
- **New evals** use RoyaleSim with levels (RsimMatch levels/tower_levels). Any eval that cannot set levels says so.
- The Inferno deck swap is cancelled (§7d keeps the deck stratum in case Sam changes the deck).
- **2026-10-17T02:52:39Z live deck from s62 (Sam):** Valkyrie, Archers, **Bats**, Cannon, Fireball, **Zap**, MiniPekka, Giant (e16 with Bats/Zap for Minions/Musketeer).
  The -res A/B count restarts at s62, stratum deck 's62'. Spell metrics: Fireball and Zap per battle. New live-mechanism sims use this deck at level 16.

**Full-pool phase on e16 (s58–s61), closed by the s62 deck change** (2026-10-17T03:05:44Z): base s58/s60 vs -res s59/s61, 8 battles per arm over the v11b/v12a strata.
- **Win rate:** 3/8 vs 3/8.
- **Giant pushes:** base 17, -res 7, so the mechanism metrics rest on a handful of pushes and their CIs are degenerate.
- **Pooled reaction p50 Δ:** +0.01 s [−1.0, +1.0].
- **Read:** uninformative. The count restarts at s62 (deck stratum s62).

## 8. Cycle-rule sizing: opponent-play history noise (bot/livediag/history_noise.py)

**L11, our engine** (as recorded under the level rule); full-pool `K4L-R-gs-mk1a1`; e16 vs Battle Log decks; live16402b-r3.
BASE11 = 3438410878560224 (drawn 2026-10-17T02:09:16Z); 200 paired cases vs K4C-r16 (100 of them in ab15b) and 100 vs R3a; 0 errors.

- **Noise calibrated to live per play:** 24% cycle-dropped (live 435 / 1,788), phantoms ~7% (live ~8%), and ~3.9 hidden spells per (long, ~46-opponent-play) sim game.

| arm | vs K4C-r16 | vs R3a | Δ K4C [95% CI] | Δ R3a | pooled Δ |
|---|---:|---:|---|---|---|
| clean | 0.515 | 0.88 | — | — | — |
| spells (hidden spells + translator guards) | 0.465 | 0.91 | −0.05 [−0.125, +0.025] | +0.03 [−0.03, +0.09] | −0.01 [−0.06, +0.04] |
| live (+ phantoms) | 0.455 | 0.94 | −0.06 [−0.14, +0.025] | +0.06 [−0.01, +0.13] | 0.00 [−0.05, +0.05] |

- **Mechanism metrics** (clean → live): reaction p50 2.65 → 2.65 s, p90 7.15 → 6.65 s; undefended pushes 3.9% → 5.1%; elixir at cross 3.29 → 3.29.
- **Read:** the corrupted history costs about 5–6 pp against the strong opponent (not significant) and nothing against R3a. So a perfect cycle model is worth at most ~+5 pp vs strong opponents.
- **-res rows** (100 paired per opponent):
  - live noise: K4C **+0.10**, R3a +0.03, pooled +0.065 [−0.01, +0.14];
  - spells-only: K4C +0.08, pooled +0.045 [−0.015, +0.105].
  - So the sign reverses between the two players.
- **FINAL (L11):** the opponent-history corruption has no measurable cost. Averaged over the two players it is about +0.02 vs K4C-r16, inside bank noise.
  A belief-level cycle model is low priority.

**L16 cross-check** (RoyaleSim L16 both sides, deck-search driver, s62 deck vs Battle Log decks, full-pool twin
FP-LD-K4L-R-gs-rw-fc-c4-mk1a1). BASE13 = 1869282966218; 100 paired cases each vs LIVE-K4CW-r16 and R3a; 800 rows, 0 errors.
The "live" arm per game: 8.5 cycle drops, 3.5 phantoms and 2.2 hidden spells out of ~43 enemy plays.

| arm | K4CW | R3a | pooled Δ vs same player clean [95% CI] | undefended | elixir at cross | reaction p50 / p90 |
|---|---:|---:|---|---:|---:|---|
| base clean | 0.56 | 0.84 | — | 5.3% | 3.43 | 2.0 / 6.5 |
| base live | 0.56 | 0.81 | −0.015 [−0.09, +0.065] | 4.4% | 3.43 | 2.25 / 6.5 |
| res clean | 0.62 | 0.87 | (+0.045 [−0.03, +0.12] vs base clean) | 4.8% | 3.84 | 2.25 / 7.0 |
| res live | 0.54 | 0.84 | −0.055 [−0.13, +0.02]; K4CW −0.08 [−0.20, +0.04] | 6.5% | 4.23 | 2.5 / 7.0 |

- **Read:** base is noise-insensitive at L16, as at L11. -res may be noise-sensitive: under noise it banks more and leaves
  more pushes undefended, consistent with a reserve keyed on a mis-tracked enemy cycle. The CI includes 0 (and at L11 the sign
  was the other way), so it is a lead, not a result.
- **Replication** on BASE17 = 1817277929115 (rhcad-live on 08: base/res x clean/live vs K4CW, 100 paired). If res:live < base:live
  replicates, the BOT LEAD un-parks the cycle model for -res and the live -res A/B is read with that in mind.

### 5l. Leaf value v2 (fp2vn mlp-d30, sha256 0fbebb3c…), RoyaleSim L16 both sides, s62 deck, vs K4C-r16; BASE12 = 2855538918876336 (drawn 2026-10-17T03:20:05Z), 100 paired, 0 errors

| arm | score | Δ vs base | Δ vs -res | reaction p50/p90 | elixir at cross p50 | Giant / Fireball / Zap / Bats per game |
|---|---:|---|---|---|---:|---|
| base | 0.56 | — | −0.08 | 2.15 / 7.15 | 3.61 | 1.26 / 1.45 / 4.6 / 7.1 |
| -res | **0.64** | +0.08 [−0.02, +0.18] | — | 2.65 / 7.65 | 4.18 | 1.15 / 1.12 / 4.0 / 6.5 |
| -vl50-rh | 0.28 | −0.28 [−0.41, −0.15] | −0.36 [−0.48, −0.24] | 2.15 / 6.15 | 2.93 | 0.66 / 0.72 / 6.1 / 7.4 |
| -vl100-rh | 0.20 | −0.36 [−0.48, −0.23] | −0.44 [−0.55, −0.33] | 2.15 / 6.15 | 2.36 | 0.51 / 0.46 / 6.1 / 7.1 |
| -vl100-res | 0.35 | −0.21 [−0.34, −0.08] | −0.29 [−0.41, −0.17] | 2.15 / 7.15 | 3.38 | 1.56 / 0.69 / 4.9 / 6.6 |

- **The v2 leaf is strongly negative and dose-dependent:** it spends more and casts more Zaps.
- **Confounds:** fit at L11 on our engine with the full-pool player; used at L16 with the C56 LD twin and the s62 deck.
- **No confirmation was run,** so the deck-diverse requirement does not apply.
- **-res vs base:** positive again on the s62 deck at L16.

## 9. Decision cadence, search budget and the serial profile (RoyaleSim L16 both sides, s62 deck vs Battle Log decks)

### 9a. Cadence A/B (`-si<k>`, branch bot/live-diag-cadence @ b3fbb0d22); BASE15 = 28781868642366; 100 paired each vs LIVE-K4CW-r16 and R3a; 1,200 rows, 0 errors

The default SEARCH_INTERVAL is 10 ticks, so base = si10, si5 = 2x and si2 = 5x the nominal cadence.

| arm | K4CW | R3a | pooled Δ vs base [95% CI] | reaction p50 / p90 | undefended | decisions / game-s | CPU-s / game-s | CPU ms / decision |
|---|---:|---:|---|---|---:|---:|---:|---:|
| base | 0.49 | 0.83 | — | 2.0 / 6.5 | 6.5% | 0.60 | 0.19 | 323 |
| base-si5 | 0.47 | 0.89 | +0.02 [−0.055, +0.09] | 2.25 / 6.75 | 4.5% | 0.63 | 0.19 | 306 |
| base-si2 | 0.48 | 0.86 | +0.01 [−0.075, +0.095] | 2.5 / 6.85 | 7.0% | 0.72 | 0.19 | 258 |
| res | 0.56 | 0.85 | +0.045 [−0.035, +0.125] | 2.25 / 7.0 | 4.8% | 0.61 | 0.20 | 332 |
| res-si5 | 0.60 | 0.82 | +0.05 [−0.03, +0.13] | 2.25 / 7.25 | 3.8% | 0.66 | 0.22 | 333 |
| res-si2 | 0.57 | 0.82 | +0.035 [−0.05, +0.12] | 2.5 / 7.3 | 3.6% | 0.77 | 0.23 | 297 |

- **Null, for a structural reason.** A seat may act only when tick >= waits[actor] (bot/players/royalesim_match.py), and a
  timed wait from the search blocks re-decision until it expires. The bot is committed to timed waits most of each battle, so
  decisions per game-second barely move (0.60 -> 0.72 for a nominal 2 -> 10).
- **Live matches the sim.** LiveSession._poll applies wait_until in the same way (bot/live/translate.py:1037/1047,
  origin/main 2a0b72f76) and quantises polls to 5 ticks (line 997). Loop owner: live 0.63-0.69 searched decisions per game-s;
  after a WAIT the next search comes p50 2.02 s later; enemy card -> our next decision p10/p50/p90 0.00 / 0.90 / 1.72 s.
  The sim gives 0.15 / 0.65 / 1.65 s (l16_report enemy_to_decision).
- The real cadence test is rh (timed waits emitted as plain WAIT) x si, plus the interrupt arm wint. That is 9c.

### 9b. Profile: where the serial time goes (bot.search.lopp_time on 04, live names K4L-R-gs-rw-fc-w200-t4-p4-mk1a1, vs LIVE-K4CW-r16, e16bl, 3 games per arm, 1,310 decisions, 0 errors)

| arm | wall ms | prep (serial) ms | search ms | CPU ms | CPU / wall | learned keys | rollouts | incomplete at 200 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 92 | 28 | 63 | 133 | 1.45 | 5.9 | 21 | 7.5% |
| -K2 | 98 | 27 | 71 | 119 | 1.21 | 11.3 | 26 | 14.5% |
| -T12 | 88 | 27 | 61 | 122 | 1.37 | 6.8 | 21 | 11.9% |

- **Phases, base p50/p95 ms:** prep 25/58, native coarse 19.5/109, chunk wait 30/58, learned 26/46, ship 5.8/23, parse 2.8/7.
- **About half the wall** (prep plus the native coarse scan) runs on one core. Only the learned chunk fans out (60 ms pool CPU
  in a ~30 ms window). Average use is about 1.45 of 4 cores.
- **K2** doubles the learned keys for +6 ms of wall.
- **T12** adds only +0.9 learned keys, because most decisions have fewer than 8 coarse-scan plays. Mac live: candidates mean 8.8,
  p50 12 = 8 plays + 4 waits.
- **Mac live (s64 stepprof, 3,341 searched steps):** search wall p50 36.6 / p95 63 ms under the 200 ms cutoff.
- **Projected Mac 4-thread wall** (04 x 0.76): base ~37, K2 ~43, K2-T12 ~45 ms p50.

### 9c. Search budget A/B (K = learned samples per key, T = learned work-set size); BASE16 = 6076377206044; 100 paired each vs LIVE-K4CW-r16 and R3a; 1,600 rows, 0 errors

| arm | ref | pooled Δ [95% CI] | K4CW Δ | R3a Δ | undefended | CPU ms / decision (serial twin) |
|---|---|---|---|---|---:|---:|
| base | — | — | — | — | 8.9% | 285 |
| base-K2 | base | +0.015 [−0.07, +0.10] | +0.07 | −0.04 | 7.2% | 370 |
| base-T12 | base | −0.045 [−0.115, +0.025] | −0.07 | −0.02 | 6.2% | 309 |
| base-K2-T12 | base | +0.06 [−0.025, +0.14] | +0.06 | +0.06 | 5.9% | 419 |
| res | base | +0.08 [0.00, +0.165] | +0.14 [+0.01, +0.27] | +0.02 | 3.7% | 312 |
| res-K2 | res | +0.04 [−0.04, +0.115] | 0.00 | +0.08 | 4.4% | 403 |
| res-T12 | res | **−0.075 [−0.14, −0.01]** | **−0.14 [−0.23, −0.05]** | −0.01 | 2.6% | 334 |
| res-K2-T12 | res | +0.035 [−0.04, +0.11] | −0.02 | +0.09 | 6.2% | 458 |

- **T12 hurts**, most likely through selection noise: more marginal candidates scored by noisy learned rollouts. K2 halves the noise
  and K2-T12 recovers the loss. Decisions per game-s (0.59-0.61) and reaction are unchanged in every arm.
- **K2:** neutral to slightly positive, and cheap in live wall (9b). It needs a deck-diverse confirmation (DD1 row) before any change.

### 9d. Report-delay sweep (cadab-delay; BASE15 seeds; vs K4CW; 100 paired)

- **Setup:** enemy plays reported 8 or 14 ticks late (noise `none+vt8` / `none+vt14`).
- **Result:** every Δ vs the same player's clean arm is between −0.02 and +0.07, and all CIs include 0. Reaction and enemy->decision
  timing are unchanged.
- **Read:** up to 0.7 s of history lag is not a lever.

### 9e. Own-play sizing (ownsize; BASE14 = 33932972705806; 100 paired each vs K4CW and R3a; 1,200 rows)

| arm | base Δ vs base clean | res Δ vs res clean |
|---|---|---|
| own26 (uniform, 10.7 of ~41 own plays dropped) | −0.07 [−0.14, 0.00]; K4CW −0.10 | 0.00 [−0.065, +0.07]; K4CW −0.04 |
| ownbad80m10 (translator owner's clustered model, 3.5 dropped/battle) | −0.005 [−0.065, +0.055] | +0.055 [0.00, +0.11] |

- **Read:** at the measured clustered rate, own-side history corruption costs nothing. Uniform 26% drops would cost base ~7-10 pp vs
  K4CW. -res is robust to both.

### 9f. Per-archetype -res vs base (all L16 paired banks above, clean history, 800 pairs; scripts/arch_cut.py)

| archetype (sim vocab: 20 cards, no Hog/RoyalGiant/air/siege) | all | K4CW | R3a |
|---|---|---|---|
| Giant beatdown | +0.037 (n 535) | +0.091 [+0.015, +0.166] | −0.015 |
| building (2+ buildings) | +0.109 (n 46) | 0.000 (n 26) | +0.25 |
| BattleRam cycle | +0.085 (n 71) | +0.032 (n 31) | +0.125 |
| other | +0.074 (n 148) | +0.154 | −0.014 |
| ALL | +0.052 [+0.013, +0.090] | +0.092 [+0.030, +0.158] | +0.013 |

- **No cell is flagged** (Δ < −0.10 with n >= 20). The archetypes that matter live (Hog, Royal Giant, air, siege) are outside the sim vocab.

### 9g. rh x cadence and the interrupt arm (rhcad; BASE17 = 1817277929115; vs LIVE-K4CW-r16; 100 paired; 600 rows) — CLOSED: per-tick needs a learned hold-back

| arm | Δ vs res [95% CI] | enemy->decision p50 (s) | reaction p50 (s) | elixir at cross | plays/battle | decisions/game-s | CPU-s/game-s |
|---|---|---:|---:|---:|---:|---:|---:|
| res | — (0.65) | 0.65 | 2.0 | 4.68 | 42.5 | 0.61 | 0.255 |
| res-wint | +0.04 [−0.09, +0.17] | 0.15 | 1.5 | 4.14 | 43.9 | 0.70 | 0.279 |
| res-rh | −0.20 [−0.33, −0.06] | 0.15 | 2.0 | 3.68 | 46.3 | 1.60 | 0.49 |
| res-rh-si5 | −0.25 [−0.38, −0.12] | 0.15 | 2.0 | 3.32 | 49.5 | 2.95 | 0.82 |
| res-rh-si2 | −0.31 [−0.44, −0.18] | 0.05 | 2.0 | 3.17 | 50.6 | 7.2 | 1.48 |

- **Faster re-decision without committed waits loses, monotonically.** Each extra decision is a chance to spend (more plays, less
  elixir at the Giant cross). With the hand-made leaf, the timed wait is what banks.
- **Per-tick decisions need a learned hold-back.** The lc/vl arms did not supply one; the sibling-leaf work is the candidate.
- **wint** keeps the waits and re-decides on a new enemy card: 4x faster re-plan at +10% CPU, score null (base-wint vs base +0.01).
  It goes to the DD1 2x2 (res / res-K2 / res-wint / res-K2-wint, 400 paired, 8 own decks).
- **Determinism check.** res is bit-identical across hosts (100/100 command hashes, 03/04 vs 08).

**Noise replication (rhcad-live, same bank):** res:live vs base:live +0.13 [0.00, +0.26]. Live vs clean: base −0.05, res −0.10.
- With BASE13, noise costs res about −0.08 and base about −0.03.
- The "-res worse than base under noise" lead does not replicate; -res does lose more of its clean edge.

### 9h. Live-entry package for -K2 / -wint on the deployed full-pool tree ({now})

- **Package:** 05:jobs/clasher/bot-livediag/macsnap/pkg-fp (README).
- **Deployed tree:** rebuilt 220/220 from scratch/live-loop/fullpool-r1-tree + 5 stage files. Git 6ac3c95f6 differs in 27 files.
- **res-K2:** name only (the deployed lopp_fast parses K<n>).
- **-wint:** bot/search/interrupt.py (new) + bot/search/lopp_fast.py (make_live_lopp suffix).
- **Parity (deadlines cleared, L16, vs K4CW, 3 cases):**
  - deployed vs deployed + package identical for res and res-K2;
  - live port == the A/B'd facade for res-wint and res-K2-wint;
  - deployed == the 2x2 sim tree.
- **Mac baseline** (deployed res, live logs s72-m07/m08): decision p95 62-83 ms, all-step p95 47-50 ms.
- **Bench and pre-stop check:** bot/livediag/fp_mac_bench.py and fp_prestop_check.py (fleet-tested).

### 9i. DD1 deck-diverse 2x2: res / res-K2 / res-wint / res-K2-wint (L16, vs LIVE-K4CW-r16, 8 own decks x 50; DD1 base 3241892761760944; 1,600 rows, 0 errors)

| arm | score | Δ vs res [95% CI] | enemy->decision p50 (s) | undefended | decisions/game-s | CPU-s/game-s |
|---|---:|---|---:|---:|---:|---:|
| res | .603 | — | 0.65 | 3.5% | 0.61 | 0.260 |
| res-K2 | .650 | +0.048 [−0.018, +0.110] | 0.65 | 3.7% | 0.61 | 0.340 |
| res-wint | .610 | +0.008 [−0.055, +0.073] | 0.15 | 3.5% | 0.70 | 0.268 |
| res-K2-wint | .662 | **+0.060 [−0.003, +0.125]** | 0.15 | 4.2% | 0.69 | 0.348 |

- **Per own deck** (s62 / e16 / Inferno / BL1 / 28 / 30 / 64 / 76), Δ vs res:
  - res-K2: +.16 / +.10 / −.06 / −.12 / +.08 / −.02 / +.08 / +.16;
  - res-wint: +.02 / .00 / −.20 / .00 / +.10 / −.04 / +.12 / +.06;
  - res-K2-wint: +.24 / .00 / +.04 / +.04 / +.06 / −.04 / +.12 / +.02.
- **Ship rule** (CI lower bound > −0.02 and point > 0): res-K2 and res-K2-wint pass; res-wint qualifies on reaction (point >= 0).
- **RESUME (LIVE LEAD ruling): -res-wint ships** (K2 waits on the Mac bench). Next slot: res-K2-wint after the bench clears.

## 10. Live: s69 loss streak and the m07 king collapse (2026-10-17)

- **Opponents.** Same arena (pekkas-playhouse) and trophy band in s67-s69. Opponent towers at full HP read king 3,768 / princess
  2,352 vs our 3,528 / 2,184 (about +1 king level) in wins and losses alike. Card levels are not logged.
- **v3b true-ids.** The 28 new classes fired on 0-2 unit-frames per s69 loss (m07: 0), so v3b is not the cause.
- **Record.** v3a 14-9 vs v3b 4-5, Fisher p = 0.45. A >= 4-loss streak in 32 battles at a 39% loss rate has probability 0.36.
- **Mechanism stats** (scripts/s69_mech.py), s69 L vs s68 L: reaction p50 3.05 vs 3.03 s; elixir at cross 2.25 vs 2.21. Fewer plays
  (20 vs 30) only because of two ~80 s losses.
- **m07 king collapse (n585-626)** is elixir-bound. With hand Giant 5 / Fireball 4 / MiniPekka 4 / Zap 2:
  - elixir was 2.9-3.9 until n617;
  - MiniPekka was played at n624, 0.7 s after it became affordable (one 5-tick search WAIT at n619, fast tier proposing it);
  - the setup came 20 s earlier: Cannon (n325) and Archers (n409, to 0.3 elixir) into a Skeleton Army + Wizard push, nothing
    affordable until n510 (Valkyrie at once, lost to the MiniPekka).
- **Phi weights.** One full king is 0.06 phi with no princess left (0.10 x 0.60), vs 0.18 for a crown.
  - In m07 the kill fell inside the 160-tick horizon, so WAIT reached terminal −2 and the leaf weight was not the cause.
  - Slow last-tower chip is still cheap: about 2 elixir per 600 HP. That is a plausible learned-leaf input; sizing arm -kw proposed.
- **Correction (ab_live / handsync_cmp bootstrap).** Resamples with no Giant push gave NaN, which scrambled sorted() percentiles.
  Fixed by dropping non-finite draws. Only the C56 elixir-at-cross CI moves (pooled [−1.02, +0.79] -> [−1.20, +0.94]).

## 11. histnoise:v2 ranking, final (BASE19 replication + BASE20 confirmation; -res at L16 vs LIVE-K4CW-r16, pool v1)

BASE20: 400 paired cases, 4 arms; coverage 1600/1600. 236 duplicate rows from the host re-runs, 0 hash mismatches. 127x03 went
down mid-bank, so its 45 missing cases were re-run on 04 with --only and the same seeds. Rows on 04 under
bot-livediag/hv2csync/{hv2c-s0,-s1,-q1,-q3,-fill}. Readout 2026-10-17T17:40:10Z.

| arm | score | paired vs v2 (BASE20 alone, bootstrap 95 %) |
|---|---|---|
| clean | 0.640 | +0.073 [+0.008, +0.138] |
| v2 | 0.568 | -- |
| v2+xdrop (all troop other-drops removed) | 0.623 | +0.055 [-0.003, +0.113] |
| v2+xdropt (translator-side drops removed, detector-side 11/232 kept) | 0.574 | +0.006 [-0.050, +0.061] |

Pooled 600 (BASE19 200 + BASE20 400):
- v2+xdrop - v2 = **+0.063 [+0.015, +0.112]**;
- clean - v2 = +0.075 [+0.022, +0.130].

Reading:
- The measured stream noise costs about 0.07.
- Troop other-drops carry nearly all of it.
- The translator-only part is about 0 (the TOWER_PDOWN go). The detector-side part (xdrop 0.623 vs xdropt 0.574, about +0.05) is the lever, so improve detector / owner accuracy, not translator rules.

Deviation: BASE18-20 ran the r1 constant 31/233 for troop other-drops; r2 is 30/232 (0.4 pp, negligible). Future runs use r2.

## 12. Live latency tail on -res-wint (LIVE LEAD 2026-10-17; s74 m01-m18 live logs + fleet replay)

**Live, 2466 searches.** No w200 deadline hits except one rebuild cutoff (m11 n394). Per-battle poll-step p95 was 44-64 ms (rule: > 65 in two consecutive battles, or > 75 in one).
- Two fixed work shapes, never scaled by state:
  - 8 plays: 35 native + 11 learned rollouts, wall p50 40 / p95 70 ms;
  - waits only: 3 + 3, wall p50 24 / p95 60 ms.
- Board size drives the tail at the same work: with >= 8 units the 8-play shape reaches p95 86-129 ms.
- Belief rebuilds are 40 searches (1.6 %), wall p50 111 ms vs 37, and **25 of the 30 searches over 100 ms**. m11 n394 is a rebuild at 192 ms with completed 0, giving default-it5s2 (bot/fullpool/belief.py:65, no deadline; fixed by the CARD belief-robust thread).

**Fleet replay.** bot/livediag/tail_profile.py wraps the cleared bench's bench_run and adds the reduce_fast phase split; w2000, so no cutoffs.
- Waits-only searches: the 3-key learned batch on pool worker 0 is the critical path.
- With plays: the native scan over ~32 plays dominates.

**Tokens** (bot/search/lopp_fast.py, default off; staged for live as pkg-fp-tail on the deployed 42778eca, lopp_fast dd5789e0):

| token | change | value change | evidence |
|---|---|---|---|
| lb | one wait per worker; plays to the least-loaded worker | none (rw) | identical actions 416/416 (m05/m08/m07), 226/226 (m09), K2 386/386. Fleet: waits-only reduce p50 ~60 -> 33 ms |
| bS16u10 | >= 10 board units: native scan covers the first 16 plays | policy | busy p95 345 -> 182 ms (m05/m08/m07), 233 -> 166 (m09) |
| bT4u10 | >= 10 board units: learned set = top-4 plays + waits | policy | with bS: 168 / 150 ms |

Default-off parity, final file vs deployed: 416/416.

**Sim null**: L16, vs LIVE-K4CW-r16, pool v1, -res-wint vs each token, 300 paired. Bases 0x7A2000 / 0x7A2400 were hand-chosen before any game, not os.urandom. 0 errors.

| arm | paired vs -res-wint | games identical |
|---|---|---|
| bS16u10 | +0.010 [-0.047, +0.067] | 50/300 |
| bT4u10 | +0.007 [-0.037, +0.050] | 130/300 |

Sim boards are busier than live perception, so this exposure is conservative.

Readout 2026-10-17T19:00:56Z.

## 13. LIVE-K4CW-r16-fp calibration (bot/livediag/k4cw_fp.py)

-fp = LIVE-K4CW-r16 (LivePlayer search, wall_ms=None, r3a 16, cutoff default it5s2) with its two C56-only parts replaced:
- the FullPoolBelief prior instead of the LiveBelief over the C56 catalog (bot/live/player.py:94, :292-293);
- the f1a2 fast tier instead of it5s2 (fullpool_eval.py:157).
The runtime (live16402b-r3, full scope) and the extended R3a/v1 nets were already full scope. K4CW rollouts use the native scripted bots, so there is no learned rollout net to swap.

**Calibration**: -res at L16, Battle Log pool v1, 150 paired (same seed / deck / seat against both opponents, --pair-opponents). Base 0x7A3000 was hand-chosen before any game. 0 errors; 60 duplicate rows (01 shards re-run on 04) with 0 hash mismatches.

| | -res vs K4CW-r16 | -res vs K4CW-r16-fp |
|---|---|---|
| score | 0.587 | 0.620 |
| undefended pushes / game | 0.00 | 0.02 |
| our reaction p50 / p90 | 2.15 / 7.15 s | 2.15 / 7.15 s |

Paired (vs -fp) - (vs r16) = **+0.033 [-0.080, +0.147]**.

BOT LEAD ruling: use -fp for new full-pool claim banks, including both PEKKA-1 strata; add the old K4CW-r16 row only for comparisons to earlier results.

Full-scope translator vocab (bot/livediag/build_vocab_full.py, one measured build per card on live16402b-r3): 39 of 58 extra cards accepted, 19 rejected (report on 04: bot-livediag/vocabv3/vocab-full-report.json).

## 14. PEKKA-1: the P.E.K.K.A matchup (pre-registration PEKKA1-PREREG.md, f03c187fa + amendment 1 8da8c6fc5; read once, 2026-10-17T21:06:55Z)

Design: res-wintp vs res, paired; vs LIVE-K4CW-r16-fp; pool v3 strata (PEKKA 20 decks, control 12); 100 cases per stratum;
L16 row + account row (V6 A8 B7 C7 F6 Z8 MP7 G7 King 7 vs logged levels, King 9). BASE 269612102058988 (os.urandom).
800 rows, 0 errors, 0 unusable. 113 rows are flagged 'unmapped public rows', all of them the Goblin Hut's RoyaleSim
SpearGoblin_Dummy (5 Goblin Hut decks: s74-m16 in the PEKKA stratum; s74-m17, s76-m06, s76-m11 and s76-m13 in control).

| row | stratum | res | res-wint | delta (wint - res), paired |
|---|---|---|---|---|
| L16 | PEKKA | 0.61 [0.52, 0.70] | 0.71 [0.62, 0.80] | **+0.10 [-0.04, +0.24]** |
| L16 | control | 0.61 [0.51, 0.70] | 0.54 [0.44, 0.64] | |
| account | PEKKA | 0.19 [0.12, 0.27] | 0.12 [0.06, 0.19] | **-0.07 [-0.15, +0.01]** |
| account | control | 0.20 [0.12, 0.28] | 0.14 [0.08, 0.21] | |

Pre-registered predictions:
1. **NOT supported.** Account row, res-wint PEKKA - control = **-0.02 [-0.11, +0.07]**; the prediction was <= -0.10. In sim, PEKKA decks are not markedly worse matchups than the newest no-PEKKA decks. The account row is low for every deck (0.12-0.21): there the level gap (King 7 vs 9, cards about one level down) dominates.
2. **Holds at L16, fails at account.** At L16 the delta is +0.10 (>= -0.03). At account it is -0.07 (< -0.03), but its CI is not entirely below 0, so by the pre-registered rule -wint is not implicated. Not pre-registered, flagged for follow-up: at account levels -wint is below res in BOTH strata (control 0.14 vs 0.20).
3. **Holds for both arms and both rows.** Undefended Hog / Battle Ram pushes per battle: PEKKA 0.80-0.91 vs control 0.18-0.30. The cause is exposure: PEKKA decks bring 4.0-4.3 Hog / Ram plays per battle against about 1 for control, and the undefended share per push is similar (0.20-0.21 vs 0.17-0.25).

Reaction p50 / p90: res 2.15 / 7.15 s, res-wint 2.15 / 6.65 s in every cell.

Sensitivity (pekka1/*.json):
- without s74-m16 (pre-announced): P1 -0.04 [-0.13, +0.06]; P2 L16 +0.09, account -0.06; P3 unchanged;
- without all 5 Goblin Hut decks (post hoc): P1 -0.06 [-0.16, +0.05], 0 flagged rows; P2 / P3 unchanged.

## 15. WINT-ACC1: -wint at account levels (pre-registration WINT-ACC1-PREREG.md, e138453c4; read once, 2026-10-17T23:43:19Z)

Design: res-lb vs res-lb-wint (the live names), paired; account levels (ours V6 A8 B7 C9 F6 Z8 MP7 G7, King 7, vs each
row's logged levels, King 9); pool v3.1, 43 King-9 / full-level / no-Goblin-Hut rows; LIVE-K4CW-r16-fp and R3a, 300 cases each.
BASE 157708954493651 (os.urandom). 1,200 rows: 0 errors, 0 unusable, 0 flagged.

| opponent | res-lb | res-lb-wint | delta (wint - res), paired |
|---|---|---|---|
| LIVE-K4CW-r16-fp | 0.163 [0.123, 0.207] | 0.153 [0.113, 0.193] | **-0.010 [-0.06, +0.04]** |
| R3a | 0.540 [0.483, 0.593] | 0.517 [0.460, 0.573] | -0.023 [-0.087, +0.043] |

**Primary: the CI includes 0, so -wint stays** (no revert recommendation).

Secondary (l16_report, pooled over opponents; res-lb vs res-lb-wint):
- reaction p50 / p90: 2.25 / 7.0 s vs 1.5 / 6.5 s;
- elixir at the enemy's cross p50: 3.86 vs 3.84;
- undefended: 0.019 vs 0.044;
- decisions per game-second: 0.61 vs 0.70;
- interrupts per battle: 0 vs 38.9 (K4CW-fp) / 36.0 (R3a).

Mechanism look:

| opponent | arm | responsive spend (elixir within 3 s of an enemy play), per battle | our towers' HP at the end | theirs |
|---|---|---|---|---|
| K4CW-fp | res | 70.6 | 3410 | 6146 |
| K4CW-fp | wint | 64.3 | 3654 | 6249 |
| R3a | res | 65.1 | 4428 | 5353 |
| R3a | wint | 68.5 | 4434 | 5387 |

-wint does not spend more into enemy plays when outmatched by levels.

The PEKKA-1 account-row gap (-0.07) is not reproduced at this size with the current levels (Cannon 9).
