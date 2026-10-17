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
