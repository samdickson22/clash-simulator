# Tower gap: why the sim kills towers that survive in real matches

Status: complete (2026-10-03). Inputs:
- the 41,651 S117 perspectives the engine-v2b extraction had finished at the time (the extraction is still running);
- 1,800 paired re-sims: 300 random perspectives, one per match, times 6 variants. All 1,800 finished with 0 errors.

## Short answer

The main cause is **divergence of the open-loop replay**. The recorded human defence was a response to the real
board, not the simulated one. Two things turn that into cuts:

1. the **overtime constraint**: 74% of matches went to overtime, so the real game had level crowns at 180 s,
   almost always 0-0;
2. an **asymmetric cut rule**: a sim overshoot is a hard cut, while an undershoot is only flagged.

Levels, evo/hero forms, spells and tower troops are not the cause.

How the replay's tower outcome compares with the real one at the same moment (t = 180 s, every sampled side, no
conditioning on outcome):

| | real towers down per side | sim towers down per side |
|---|---|---|
| all sides | 0.21 | 0.31 |
| overtime matches | 0.04 | 0.24 |
| matches decided in regulation | 0.83 | 0.59 |

- Across all sides the sim kills more towers by 180 s: **+0.105 crowns per side (95% CI +0.05 to +0.16)**. The sim
  overshoots on 16.6% of sides and undershoots on 6.7%.
- The sim's tower outcome is only weakly tied to the real one. It overshoots where real had no kills and
  undershoots where real had kills (regulation-decided matches: 27% undershoot vs 11% overshoot).
- At the end of the match, undershoot is common too: 43% of perspectives that reach the end uncut carry
  `unreproduced_real_kill`.
- Because the corpus is mostly overtime matches, the noise appears almost entirely as "sim kill of a standing tower".
- Pre-180 s kills in overtime matches cost **14.25 of the 18.15 points** this cut costs in the corpus.

## 1. Who loses which tower, when, and to what

**Corpus view** (41,651 perspectives; data/q1_q2_stats.json):
- Retention is 74.55%.
- The sim-kill cut is the first contradiction in 43.9% of perspectives and costs 18.15 of the 25.45 lost points.
  sim_game_over costs 3.1 points; every other cut costs 1.8 points or less.
- **Slot:** Princess towers 97.6%, King towers 2.4%.
- **Side (own vs opponent):** 60% own and 40% opponent overall, but this is selection:
  - where both perspectives of a match are extracted, the split is 50.1/49.9;
  - single-perspective matches are the reason: the side with the in-scope C56 deck is the one losing towers;
  - by seat, the team (replay owner) is 54.5% and the opponent 45.5%.
- **Time:**
  - median 153 s (p10/p90 70/230 s), which is 62% of the playable match;
  - 46% of kills fall in 120-180 s;
  - **61% are before 180 s in a match that really went to overtime.**
- **Real state of the tower the sim killed** (at the real end):
  - the owner's weakest standing Princess tower had a median of 40% HP left;
  - 33% were below 25% HP, and 4% were untouched.

**Killing damage** (re-sim, 121 kills, damage attributed by stack walk):
- By damage type: troops 65%, projectiles 27%, everything else small.
- Spells deal 4.6% of the killing damage, and no kill is spell-majority.
- Top sources (mean share of the killed tower's damage): Hog Rider 8.5%, Angry/Elite Barbarians 8.2%,
  Mighty Miner 7.8%, Royal Hogs 4.4%, Royal Ghost 4.1%, Inferno Dragon 3.1%, Cannon Cart 2.7%, Dark Prince 2.2%,
  Royal Giant 2.2%.
- The top source of a kill deals a median 55% of the damage.
- Most common last hitters: Elite Barbarians 10, Mighty Miner 9, Hog 7.
- Pattern: a win-condition push that the real defence stopped gets through in the sim.

## 2. Associations

Side-level logit, n = 83,302 defender-sides with match-clustered SEs (scripts/q2_assoc.py). Outcome: this side's
tower is the first sim-kill contradiction.

| term | coef (95% CI) | reading |
|---|---|---|
| overtime match | +0.72 (0.68, 0.77) | mechanical: level crowns at 180 s |
| real towers lost 1 / 2 | -0.58 / -1.60 | mechanical: looser constraint |
| defender won the real match | +0.15 (0.04, 0.26) | winners' defence is not reproduced |
| level diff (attacker minus defender) | -0.34 per level (-0.54, -0.14) | but 98% of sides have equal levels |
| capped L11-vs-L11 modes | -0.01 (-0.34, 0.31) | **real L11 games fail just as often** |
| defender evo slots / attacker evo slots | -0.29 / +0.26 | wrong sign for "missing evo defence"; 91% of sides have exactly 2, so this is confounded |
| defender hero slots / attacker hero slots | +0.10 / -0.20 | in the direction of missing hero power, but small (OR 1.10 / 0.82) |
| mode (Ranked, Ladder vs 1v1 Battle) | n.s. | |

- **Tower troop:** every C56 payload uses Tower Princess, because tower-troop matches were excluded upstream. It is
  not a factor.
- **Cards** (presence dummies, cards with at least 1,500 sides). Attacker win conditions raise the odds:
  - Cannon Cart +1.26, Golem +0.89, Mighty Miner +0.84, X-Bow +0.79, Giant +0.77, Lava +0.75;
  - P.E.K.K.A +0.68, Mega Knight +0.65, Angry Barbarians +0.61, Royal Hogs +0.55, Hog +0.54.
  - Hunter in the defender's deck is the largest single effect (+1.41) and is a candidate engine-fidelity bug.
  - Spells are not among the risers.

## 3. Mechanism tests

Paired re-sims of the same 300 perspectives on a copy of the extraction runtime (tower-gap/runtime). The base
variant reproduces the extraction's cut tick and supervised rows for **300/300** perspectives.

Columns:
- **Retention** treats a sim kill as a cut.
- **Δ (95% CI)** is a paired bootstrap against base.
- **Crowns diff @180 s** is sim minus real per side.

| variant | retention | Δ pts (95% CI) | sim-kill cut rate | crowns diff @180 s |
|---|---|---|---|---|
| base (nominal L11, base forms) | 76.6% | 0 | 40% | +0.105 (+0.05, +0.16) |
| rel: real level differences kept | 76.8% | +0.2 (0.0, +0.6) | 40% | +0.099 |
| tower_real: towers at real L16, cards L11 | 89.3% | +12.7 (+10.2, +15.4) | 8% | **-0.056 (-0.09, -0.02): now undershoots** |
| evo2: evo/hero-slot cards +2 levels | 68.6% | -8.0 (-10.2, -5.6) | 55% | +0.223 (+0.17, +0.28) |
| spell_ctd: spells deal 0 to crown towers (upper bound) | 78.0% | +1.4 (+0.9, +2.1) | 35% | +0.079 |
| clamp: hold real-standing towers at 1 HP | 87.2% | +10.6 (+8.6, +12.8) | 0% | n/a |

What each test shows:
- **Levels:**
  - Uniform L16 equals uniform L11 within 0.4%: cards scale 1.598x and towers 1.592x.
  - The extended tower formula reproduces real L13-16 tower HP exactly.
  - Only relative levels can matter, and only 2% of sides are mismatched. Simulating real levels does nothing.
  - Absolute L16 is also unsupported for Earthquake/Poison crown-tower overrides in the engine.
- **Tower level matching:**
  - It works only by making towers 1.6x tougher than the attacking cards.
  - It overshoots into a significant undershoot, and it adds undershoot in regulation-decided matches (42% of
    those sides).
  - It also breaks the nominal-L11 observation. It is a fudge, not a fix.
- **Evo/hero as a stat stand-in:** a uniform +2 levels on evo/hero slots makes the overshoot worse. Evo slots in
  this meta mostly carry offence. Per-card evo modelling is not supported as the cheap lever.
- **Spells:** removing all spell tower damage closes only about 25% of the +0.105 excess and gives +1.4 points.
  The crown-tower reduction is not the problem.
- **What is left:** troop pushes that the replayed (open-loop) defence fails to stop.
  - A residual engine-defence gap on specific cards (Hunter, Cannon Cart) may add to it. Separating that from pure
    divergence needs native traces; it was not tested here.

## 4. Recommendation

**Cheapest fix: a replayer rule. No engine change.** Treat an overshoot the way an undershoot is treated:

1. When the sim would destroy a tower that the recording proves standing (same test as today), hold it at 1 HP and
   book the excess damage. resim.py `clamp` implements this as an in-process take_damage hook; production would put
   the same check in the replayer's step loop.
2. Keep supervising, and cut only once the booked overshoot on a tower exceeds **1.0x that tower's max HP**.
3. Flag every row after the first clamp (`tower_clamped`, `overshoot_frac`) and down-weight those rows
   (e.g. 0.5, as for evo/hero plays).

Expected retention: the paired sample gives the recovered share of its own 15.76 sim-kill points. The full-corpus
projection applies that share to the corpus's 18.15 lost points.

| overshoot threshold | sample retention | perspectives cut | full-corpus projection |
|---|---|---|---|
| 0 (today) | 76.6% | 40% | 74.5% |
| 0.5x | 82.3% | 21% | 81.1% |
| **1.0x (recommended)** | **84.9%** | **12%** | **≈84%** |
| 2.0x | 86.3% | 5% | ≈86% |
| ∞ (never cut) | 87.2% | 0% | ≈87% |

- The recommended threshold gains about **+9.7 points** (74.5% → about 84%).
- Never cutting is the ceiling, at about +12 points. The remaining loss there is mostly sim_game_over and the
  other cuts.
- When a tower is clamped, the median overshoot is 0.55x max HP (p75 1.05x).

**Data/observation contract:**
- **Levels:** stay observed and simulated at nominal L11. Real-level simulation was measured to change nothing,
  so no level channel or re-normalisation is needed. Keep storing the original levels as metadata.
- **New fields:**
  - per row: `tower_clamped` (bool) and `overshoot_frac`;
  - per perspective: clamp tick, max overshoot and the threshold used.
  - The schema/provenance string must say "towers proven standing in the recording are held at 1 HP".
- **What the actor sees after a clamp:** its tower at 1 HP where the real tower had more. That is counterfactual
  context, which is why those rows are flagged and down-weighted, and why the 1.0x threshold stops them at large
  overshoot.
- **Re-extraction:** needed, but it is replayer-only on the frozen engine at the same cost as today. It can ride
  along with the planned champion-subset re-extraction, or run as a full replayer-v5.1 pass.

**Not recommended:**
- Tower level matching: it overcorrects into undershoot.
- Real-level simulation: no effect.
- Uniform evo/hero boosts: harmful.
- A spell crown-damage change: +1.4 points at most.
- A margin based on real final HP: only 33% of killed towers ended below 25% real HP.

**Worth one native check each:** Hunter defending and Cannon Cart attacking (the largest card effects), and Elite
Barbarians (the largest share of last hits).

## Files

- scripts/dump_summaries.py, scripts/common.py, scripts/q2_assoc.py: summary statistics (data/q1_q2_stats.json).
- scripts/resim.py: instrumented re-sim with variants base, rel, tower_real, evo2, spell_ctd, clamp.
  - Output: data/resim300-w{0,1}.jsonl.
- scripts/analyze_resim.py: produces data/resim300_analysis.json (validation, attribution, @180 s, variants,
  clamp curve, projection).
- runtime/: copy of c56/data/runtime-engine-v2. The only change is the tower level range (1..16) in
  tower_scaling.py.
