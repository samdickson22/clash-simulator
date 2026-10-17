# Board-noise knockout BN1 (own units shown as ENEMY on the planning board): RESULTS (exploration)

Owner: cycle-model owner, for the BOT LEAD; answers the LIVE LEAD's question whether owner model v1.4c is worth shipping.
Code: bot/livediag/board_noise.py (+ board_noise_runs.json, test_board_noise.py). The driver token comes from live-diag.

## Pre-registration (written 2026-10-17T18:52:38Z, before any game)

**Injection.** BoardNoisePlayer relabels own troops as ENEMY (entity columns 2/3) in OUR player's packets only
(view.info.packet and view.reserved.packet). The engine, the opponent, the play streams and the hand are untouched.
- **Rates:** the translator owner's measured runs (BOARD-OWN-AS-ENEMY.json 60d51fd6…, 13 adjudicated live battles; a
  lower bound because cards in both decks are excluded):
  - v1.1: 193 runs, 14.8 per battle (Bats 66 runs / 167 records, Valkyrie 49, Archers 40, MiniPekka 29, Giant 9);
  - v1.4c: 170 runs, 13.1 per battle (Bats 46 / 54 records).
- **Per battle:** K = the run count of one of the 13 battles drawn uniformly (×3 for the x3 arm). K (card, length) runs
  are drawn from the pooled list, each starting at a uniform tick in [3 s, 180 s). A run anchors on an own troop of that
  card (our half first), lasts `length` polls (one record ≈ one 0.25 s poll) and relabels round(units_per_record) units
  nearest the anchor.
- **Seeding:** from (arm, case seed, seat), so the arms stay paired.

**Bank:** BN1 base 173067968800252 (os.urandom, drawn 2026-10-17T18:52:38Z). Cases 100 per opponent (LIVE-K4CW-r16 and R3a) = 200 paired per arm.
Driver default decks (Sam's s62 vs Battle Log), cards and towers at L16, RoyaleSim.

**Player:** `res-wint` (the -res + wint facade, the RESUME live player).

**Arms:**
- clean: `res-wint`;
- v1.1 rate: `res-wint-bnv11`;
- v1.4c rate: `res-wint-bnv14c`;
- 3× v1.1: `res-wint-bnv11x3`.

**Parity:** with no token, the driver is unchanged. I check 10 cases of new driver copy vs old copy, and `bnoff` vs no
token, by identical command_sha256.

**Readout (paired, normal 95% CI):** clean − v1.1, clean − v1.4c, clean − 3×, and v1.4c − v1.1 (the recovery).
- **Decision rule:**
  - If clean − v1.1 ≤ +0.03 with a CI including 0, and the 3× arm is also within noise: report "board-state owner
    accuracy ≈ 0 → park v1.4c".
  - If clean − v1.1 > 0 with a CI lower bound > 0: report the size and v1.4c's recovery, (v1.4c − v1.1) / (clean − v1.1).
- **Also reported:** reaction p50/p90 and undefended share (bot.livediag.l16_report), runs applied/dropped per battle,
  flipped unit-polls, and plays made while a phantom was shown with the deploy within 4 tiles of it (count and elixir).

## Readout (2026-10-17T20:15Z; all 800 games done 20:13Z, 0 errors)

Job dir bn1/main-s0 (04) + main-s1 (08), copied to 05: bn1/readout.json (fc092a3c…) and live-diag's l16_report
bn1/l16_report.json (2bc58ee0…); the two agree. Paired by (opponent, index); normal 95% CI.

**Default-off parity** (04, base 4245, 10 cases vs K4CW): cadence-bn `res-wint` == cadence-v2 `res-wint`, 10/10
identical command_sha256. cadence-bn `res-wint-bnoff` == `res-wint`, 10/10. PASS.

| arm | pooled win (n 200) | vs K4CW-r16 (n 100) | vs R3a (n 100) |
|---|---|---|---|
| clean (`res-wint`) | 0.760 | 0.58 | 0.94 |
| v1.1 rate | 0.725 | 0.57 | 0.88 |
| v1.4c rate | 0.740 | 0.57 | 0.91 |
| 3× v1.1 | 0.705 | 0.53 | 0.88 |

| comparison | pooled Δ [95% CI] | K4CW | R3a |
|---|---|---|---|
| **clean − v1.1** | **+0.035 [−0.026, +0.096]** | +0.01 [−0.09, +0.11] | +0.06 [−0.01, +0.13] |
| clean − v1.4c | +0.020 [−0.037, +0.077] | +0.01 [−0.09, +0.11] | +0.03 [−0.03, +0.09] |
| clean − 3× v1.1 | +0.055 [−0.017, +0.127] | +0.05 [−0.08, +0.18] | +0.06 [−0.01, +0.13] |
| v1.4c − v1.1 (recovery) | +0.015 [−0.052, +0.082] | | |

**Against the pre-registration:** neither clause applies cleanly.
- clean − v1.1 = +0.035 is just above the +0.03 "≈ 0" threshold, but its CI includes 0, so it isn't a CI-clear cost
  either.
- The 3× arm is within noise (CI includes 0).
- Reading: **a small cost, ~2–4 pp, that grows with the dose and is not significant at n = 200**: v1.4c +0.020 < v1.1
  +0.035 < 3× +0.055.
- v1.4c's point-estimate recovery is (0.035 − 0.020) / 0.035 ≈ 0.43, about 1.5 pp, well inside the noise.

**Behaviour (l16_report):**

| metric | clean | v1.1 | v1.4c | 3× v1.1 |
|---|---|---|---|---|
| reaction p50 / p90 (s) | 1.75 / 7.0 | 1.75 / 7.0 | 1.75 / 7.0 | 1.75 / 7.0 |
| Giant reaction p50 / p90 (s) | 1.5 / 6.5 | 1.5 / 6.5 | 1.5 / 6.0 | 1.5 / 5.5 |
| undefended share | 3.0% | 2.5% | 4.1% | 4.0% |
| elixir at the Giant cross, p50 | 4.07 | 3.84 | 3.84 | 3.70 |

- **Elixir:** less is banked as the noise rises; the bot spends against phantoms.
- **Undefended share:** moves without a monotone pattern (noise).

**Injection per game:**

| | v1.1 | v1.4c | 3× v1.1 |
|---|---|---|---|
| runs applied | 12.8 | 11.7 | 38.6 |
| runs dropped (no own unit of that card) | 2.0 | 2.1 | 5.7 |
| flipped unit-polls | 21.0 | 12.5 | 54.0 |

- **Measured live, for comparison:** 25 records/battle for v1.1 and 16 for v1.4c, so the sim matches the measured
  dose.
- **v1.1 card mix:** Bats 4.9, Valkyrie 2.9, Archers 2.9, MiniPekka 2.0, Giant 0.1.
- **Plays made while a phantom was shown, deploying within 4 tiles of it:** 0.35 per game (~1.0 elixir) for v1.1, 0.35
  (0.9) for v1.4c, 0.84 (2.3) for 3×.

**Caveats:**
- The measured rates are a lower bound: cards in both decks are excluded (e.g. Bats in mirror battles).
- The model is a relabel of whole runs; per-record flicker within a run isn't modelled.
- RoyaleSim at L16; one bank.
- The other row flag is "unmapped public rows" (the SpearGoblin_Dummy unit), shared by every arm as in all L16 runs.
