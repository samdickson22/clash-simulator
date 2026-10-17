# SC1 spell-chip / spell-hold option value: RESULTS (exploration)

Owner: cycle-model owner, for the BOT LEAD. Live trigger: s78-m14, where the search cast Zap on pure tower chip (36
damage, no enemy units), beating WAIT by 0.0009; an enemy Wizard arrived ~2 s later.

## Measurement (no new games; BN1 clean res-wint, 200 L16 games vs K4CW-r16 + R3a; job dir bot-cycle/sc1/measure.py)

**Rule:** "tower-only" = our Zap/Fireball with no enemy troop or building within 2.5 tiles of its target at the last
poll before execution, aimed within 4 tiles of an enemy tower.

**Per game:**
- **Casts:** Zap 5.19, Fireball 1.54.
- **Tower-only:** **1.01** (Zap 0.80, Fireball 0.22); K4CW 1.08, R3a 0.94. 123/200 games have at least one; cast-tick
  quartiles 1292 / 2902 / 3837.
- **Empty:** a further 0.42 per game hit no unit and aren't near a tower.
- **What follows:** after ~75% of tower-only casts, an enemy troop is played within 5 s while the spell is out of hand.
- **Margins:** not logged in sim rows; live s78-m14: 0.0009 over WAIT.
- **Descriptive only:** games with tower-only casts win 0.81, without 0.68 (confounded: the bot chips when ahead).

Systematic by the BOT LEAD's bar (≥ 0.5 per game), so the A/B follows.

## A/B SC1-AB: pre-registration (written 2026-10-17T20:20:49Z, before any game)

**Term** (bot/search/spellhold.py, token `sh<N>`, λ = N/1000, default OFF):
- Every root play of a spell (a card with no Troop/Building body in R.config) pays λ × cost(card), whatever it targets.
  This is a spell-in-hand option value; a wait keeps it.
- It composes with `res` in core.reserve. There are no per-card or target rules.
- Fireball (4) holds twice Zap's (2) value by construction. That is noted in advance and not tuned after results.

**λ values** (fixed now, the BOT LEAD's anchor to -res's 0.015 per elixir): **0.005** (`sh5`) and **0.015** (`sh15`).

**Bank:** SC1 base 153589845884221 (os.urandom, drawn 2026-10-17T20:20:49Z).
- 100 cases each vs LIVE-K4CW-r16-fp and R3a = 200 paired per arm.
- Pool v3 decks per live-diag's driver option (non-PEKKA strata allowed), L16, RoyaleSim.

**Arms:** `res-wint` (control), `res-sh5-wint`, `res-sh15-wint`.

**Default-off parity first:** 10 cases, new tree vs the previous tree, `res-wint`, identical command_sha256.

**Readout:**
- **Primary:** each sh arm − control, paired, normal 95% CI.
- **Also:** tower-only casts per game per arm (measure.py), reaction p50/p90, undefended share, elixir at the enemy's
  cross (l16_report).
- **Decision:** report as measured. A λ is a ship candidate only if its Δ > 0 with CI lower bound > −0.03 and
  tower-only casts drop. The final call is the BOT LEAD's.

**Amendment (2026-10-17T20:22Z, before any game):** run details.
- **Driver:** live-diag's frozen cadence-sc1 copy (l16_cadence.py 389119a2…, run-l16-cadence.sh d16f057b…), which passes
  `sh<N>` through to the factory.
- **wint flavour:** the driver's facade `wint` (bot.livediag.variants.Interruptible), as in BN1 and DD1.
- **Decks:** pool v3 uniform over all 148 rows (`--pool …/battlelog-pool-v3.jsonl` a1156a4c…, `--vocab …/vocab-full.json`
  f588168f…), no strata.
- **Opponents:** `--opponents LIVE-K4CW-r16-fp,R3a`.
- **Source tree:** main 57c041f97 on 04/08.
- **Parity:** `res-wint` on 57c041f97 vs its parent 9095e1baa (differs by exactly the 5 SC1 files), 10 cases vs R3a on
  base 4246 with the same pool/vocab flags.
- **Split:** 04 shard 0/2 at 24 workers, 08 shard 1/2 at 16 workers (PEKKA-1 shares both hosts).

**Default-off parity (2026-10-17T20:31Z): PASS.** `res-wint` on 57c041f97 vs its parent 9095e1baa, 10 cases vs R3a on base 4246 with
the pool/vocab flags: **10/10 identical command_sha256**, 0 errors (job dir sc1/par-old, sc1/par-new on 04).
- Deviation, noted: the brief said parity BEFORE any game; it ran in parallel with the A/B (both launched 20:22Z).
- The BOT LEAD's rule: any difference would have invalidated the bank. There is none, so the bank stands as registered.

## SC1-AB readout (2026-10-17T21:39Z; 600 rows, 0 errors; job dir bot-cycle/sc1/main-s0 on 04, main-s1 on 08)

**Primary: score (win 1, draw .5), each arm − res-wint, paired over the same 200 cases, normal 95% CI.**

| arm | vs K4CW-r16-fp (100) | vs R3a (100) | pooled (200) |
|---|---|---|---|
| control res-wint | 0.550 | 0.860 | 0.705 |
| sh5 (λ 0.005) | +0.040 [−0.071, +0.151] | +0.040 [−0.043, +0.123] | **+0.040 [−0.029, +0.109]** |
| sh15 (λ 0.015) | −0.040 [−0.167, +0.087] | −0.030 [−0.116, +0.056] | **−0.035 [−0.112, +0.042]** |

l16_report's bootstrap CIs agree: sh5 +0.04 [−0.03, +0.11], sh15 −0.035 [−0.115, +0.04].

**Spell use and the other registered metrics.** Per game; control → sh5 → sh15.
- **Tower-only casts (measure.py):** **0.93 → 0.685 → 0.445**.
  - Zap 0.74 → 0.575 → 0.355; Fireball 0.19 → 0.11 → 0.09.
- **But every spell cast drops, not just chip:**
  - Zap 5.27 → 3.05 → 1.78; **Fireball 1.60 → 0.44 → 0.28**.
  - Casts on a swarm (behaviour_diag (a)) 4.17 → 2.08 → 1.17.
  - Swarm response (e) 33.6% → 18.1% → 11.3%.
  - Lethal missed windows (b) 0.70 → 0.89 → 1.44.
- **Reaction p50/p90 (s):** 1.75/7.0 → 2.0/7.5 → 2.0/7.5.
- **Undefended share of enemy Giant pushes:** 0.075 → 0.074 → 0.060.
- **Elixir at the enemy's cross (p50):** 3.84 → 4.04 → 4.25.
- **Plays per battle:** 39.2 → 35.5 → 35.6.

**Decision by the pre-registered bar** (Δ > 0, CI lower bound > −0.03, tower-only casts drop):
- **sh5 meets it, just:** lower bound −0.029; tower-only −26%.
- **sh15 does not:** Δ < 0.

**Owner's reading (the BOT LEAD decides):**
- sh5 is a borderline pass on one bank.
- It works by suppressing spell use in general: Fireball −73%, swarm responses roughly halved.
- That runs against the live complaint that the bot misses obvious spells. The small gain may come from the banked
  elixir (+0.2 at the cross), not from less chip.
- Per the RL-snapshot lesson, I would not ship it on this bank. If wanted, run a fresh-bank replication of sh5
  (new base, 200 pairs) first.
- A better-founded option value would scale with how likely the opponent's remaining cycle is to give the spell a
  target (belief-based). That is not proposed for running now.

## Add-on 1: behaviour diagnostics (bot/livediag/behaviour_diag.py; main c7120d491 + cf56cbf93)

**Method.**
- Definitions and thresholds are in the module docstring, fixed before any corpus run. The only data seen before was
  one smoke game, s79-m05.
- Unit values, unit HP and spell radius/damage come from the runtime config (bot/livediag/cardtable.py). Its first
  run halved every unit value: the config lists each unit template twice. That was fixed before any corpus run.
- **Sim:** the SC1 bank (pool v3 decks, so our deck varies).
- **Live:** s73–s78, 71 battles, read-only on 05. The detector is sparse, so live board counts are lower bounds.
- **Human:** IL_Replay, 252,238 Path-of-Legend games on 04; internal eval only, no data committed. These are play
  sequences only, so (a)–(c) can't be computed for humans.

| per game | sim control | sim sh5 | sim sh15 | live s73–s78 | human |
|---|---|---|---|---|---|
| (a) spell casts / on a swarm share | 6.87 / 0.61 | 3.49 / 0.60 | 2.06 / 0.57 | 5.13 / 0.51 | – |
| (a) tower-only casts | 0.93 | 0.685 | 0.445 | 1.30 | – |
| (b) missed windows, value rule (affordable / short) | 7.3 / 4.2 | 7.4 / 3.9 | 9.6 / 4.2 | 5.9 / 6.7 | – |
| (b) lethal missed windows (affordable / short) | 0.70 / 0.67 | 0.89 / 0.75 | 1.44 / 1.14 | 0.11 / 0.47 | – |
| (c) our elixir at an enemy push on our bridge, mean | 3.87 | 4.09 | 4.21 | **2.64** | – |
| (d) Giant at the bridge / mid / behind the King | .72 / .25 / .03 | .74 / .24 / .02 | .68 / .29 / .03 | **.84 / .11 / .05** | **.62 / .19 / .19** |
| (d) elixir at the Giant play | 7.15 | 7.34 | 7.37 | 6.35 HUD (6.52 by accounting) | **9.04** (accounting) |
| (e) swarm response (small spell ≤ 6 s after an enemy swarm play) | 0.336 | 0.181 | 0.113 | 0.307 | 0.262 |

**Ours vs human:**
- **Spells on swarms:** we respond to swarm cards as often as top humans do (31% live vs 26%). Aggregate spell
  under-use is not visible.
- **Giant timing:** humans play Giant behind the King 19% of the time, at ~9 elixir. They bank before committing.
  We play it at the bridge 84% of the time, at ~6.5.
- **Elixir under pressure:** live, we meet enemy bridge pushes with 2.6 elixir.

These point at banking and commitment timing rather than at spell choice.

## Add-on 2: proposer vs scorer at missed windows (18 live positions)

**Positions:**
- All 8 live lethal missed windows (s73–s78).
- 10 value-rule windows: a seeded sample (seed 20261017), one per battle.

**Method:**
- Each position is replayed with live-diag's trace tool through the s79 tree (`...-w2000-...-res-lb-wint`, as for
  s79-m05).
- A trace copy dumps every input candidate and every scored candidate (job dir sc1/ps/).
- Each position is classified at its first decision where the spell is affordable.

| outcome | positions | notes |
|---|---|---|
| scorer veto (spell rolled out, lost) | **9** | gaps to the chosen action 0.0007–0.034, median 0.0065; in 3 the spell is cast ~1 s later (window rule 1 s) |
| pre-filter cut (spell proposed, not among the 12 rolled-out plays) | 6 | the native coarse scan ranked it out |
| replay casts the spell | 3 | the s79 tree differs from the tree that played s73–s78 |
| proposer gap (affordable spell not proposed) | 0 | proposals of 35–40 always include it |

**Reading:**
- Vetoes are the plurality, and they are close calls.
- The pre-filter is the second cause.

**PROPOSAL (not run): prior tie-break, pre-registered the same way as SC1.**
- **Term:** every root play's score += λ · log π_prior(a).
- **Prior:** π_prior is the learned policy the live stack already loads (student f1a2 softmax over root actions),
  floored at 1e-4.
- **Scope:** the brief says "for spells". I'd recommend applying it to all root plays. A spell-only term is a class
  rule, and SC1 shows spell-only terms move overall spell frequency.
- **Arms:** `pt2` (λ 0.002) and `pt5` (λ 0.005), vs res-wint. The λ values are scaled to the median veto gap
  (0.0065) over typical 1–3-nat log-prior differences.
- **Bank and procedure:** L16, pool v3, vs K4CW-r16-fp + R3a, 100 cases each. Fresh base drawn at launch;
  10-case default-off parity BEFORE any game.
- **Readout:** paired Δ CI; swarm response; lethal missed windows; tower-only casts; elixir at the cross.
- **Pre-filter:** in the same run, also log whether the scanned top-12 contains the prior's top-3. That measures the
  pre-filter share without a second term.

## Add-on 3: Sam's "obvious Fireball" (s79-m05; live-diag's trace + replays in job dir sc1/sam/)

**Position (Sol read of the screenshot; I did not look at it):**
- 2:05 left; towers ours 1557/2184, theirs 2534/720.
- Enemy: Goblin Hut L7, 3 Barbarians L7 (one nearly dead), 3 Spear Goblins L7 and 2 Archers L8 at our right bridge.
- Our Cannon L9 is on the board at 0.77 HP. Our elixir is 1.
- Hand (log): Bats, Valkyrie, Giant, Fireball.
- Corrections to the brief: it is a Goblin Hut, and there is no Valkyrie or Mini P.E.K.K.A on the board.

**Trace check:**
- The control replay with my sh-capable copy of live-diag's s79 tree reproduces live-diag's trace exactly; every
  root score is identical.
- Fireball was never affordable while the push was on the board (elixir ≤ 3.13).

**What each SC1 arm chooses (root scores):**

| tick | res-wint (control) | sh5 | sh15 |
|---|---|---|---|
| 930 (3.13 elixir) | Cannon (8,13) −0.0218; WAIT −0.0305 | same | same |
| 1090 (2.95 elixir; 2:05) | Bats (14,9) −0.0101; best wait −0.0309 | same | same |
| 1170 (2.39 elixir) | Zap (14,10) −0.0698; best wait −0.0699 | **WAIT** −0.0699 (Zap −0.0798) | **WAIT** −0.0699 (Zap −0.0998) |

SC1 cannot produce this Fireball. It only charges spell casts, so it removes the Zap.

**Counterfactual "banked at 930":** live perception with +3 elixir from n590, Cannon kept in hand, our Cannon removed;
enemy positions as logged. This is an input edit, so only each decision's scores are meaningful.
- **When Fireball is chosen:** it becomes affordable at 990 (4.19 elixir), and the control picks it once (1030:
  0.0583 vs Valkyrie 0.0510).
- **Otherwise Valkyrie wins**, at 980–1020 and from 1040 on. The Fireball gap is 0.024 / 0.005 / 0.005 / 0.003.
- **sh5 never picks Fireball** (−0.020 each). sh15 drops it from the rolled-out set.
- **Holding isn't the bot's own choice:** given the same 3 elixir, it plays Cannon again at 940–970.

**The search's own values say banking was right:**
- At 990–1000 the banked state's best score is about +0.04 (Valkyrie 0.040 / WAIT 0.040). The live Cannon line at
  the same ticks is −0.007 / −0.011. That is about +0.05 for holding.
- Yet at 930–970 the search rated Cannon above waiting by 0.003–0.019.
- So the WAIT root value under-reads holding: the timed-wait rollouts don't hold and then play the 4-elixir answer.

**Levels:**
- The live session plans everything at level 11 (no levels configured).
- In the config, an L11 Fireball (688) does not kill an L11 Barbarian (716 HP). In the game, our L9 Fireball (~569)
  kills L7 Barbarians (~489).
- **Probe:** a trace copy with bot/live/levels.py LevelRoot on K4L-R's root. Relative levels: ours 11, own towers 9,
  enemy troops 9 (Archers 10), enemy towers 11.
- **At 930 on the real log the bot WAITS** (−0.0032; the Cannon is not in the top 4) instead of playing Cannon.
- In the banked counterfactual it still prefers Valkyrie at 990–1020, Fireball at 1030.
- Limits: one position; LevelRoot scales only board bodies.

**Perception gaps in this position (for the LIVE LEAD and the translator owner):**
1. The enemy Goblin Hut is in the packet as a SpearGoblin **troop** (token 315, kind Troop) at (11.6, 22.0) all
   battle. The planner doesn't know there is a building spawning Spear Goblins.
2. Our Cannon, on the board in the screenshot, is absent from the packet at 1070–1090. The Bats decision was planned
   without it.

**Answer to live-diag's question ("bank ~2.8 s for the Fireball?"):**
- In-model, banking at 930 was worth about +0.05. The payoff is Valkyrie ≈ Fireball (within 0.005), not
  specifically Fireball.
- The lever is how the root values holding, not a spell term:
  - (a) a level-aware root; the one-position probe flips 930 to WAIT;
  - (b) a "bank for card X" root action (wait until X is affordable, then plan X), so the rollouts value holding.
- Both are proposals for the BOT LEAD and LIVE LEAD, not run.
