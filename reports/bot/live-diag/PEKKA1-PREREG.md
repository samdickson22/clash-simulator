# PEKKA-1: the P.E.K.K.A matchup, pre-registration (bot live-diag; written before any game)

Origin: reports/bot/live-diag/LOSS-S74-VS-S73.md, the proposed sim test (BOT LEAD 2026-10-17). Changes from that proposal,
ordered by the BOT LEAD:
- opponent LIVE-K4CW-r16-fp for BOTH strata;
- pool v3 strata (s69-s76 Battle Logs);
- our account levels as of 2026-10-17 (Zap 8).

**BASE = 269612102058988.** Drawn with os.urandom(6) at 2026-10-17T19:24:44Z, before any PEKKA-1 game.

## Design
- **Arms (paired on every case):**
  - `res-wintp`: the live LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint through lopp_fast.make_live_lopp, deadlines cleared (serial twin);
  - `res`: the pre-wint live player.
- **Own deck:** Sam's live deck (Valkyrie, Archers, Bats, Cannon, Fireball, Zap, MiniPekka, Giant).
- **Opponent:** LIVE-K4CW-r16-fp (bot/livediag/k4cw_fp.py, main 7df775763). Calibrated vs K4CW-r16 at +0.033 [-0.080, +0.147], 150 paired, hand-chosen base 0x7A3000.
- **Pool:** battlelog-v3 (pools/battlelog-pool-v3.jsonl sha256 a1156a4c…; v1 rows byte-identical). Rules: null-identity rows dropped, forms mapped to base, card support against the full-scope runtime vocab (vocabv3/vocab-full.json sha256 f588168f…), ElectroWizard held until live16402d.
- **Strata** (pool row indices; pekka1-strata.json sha256 f95e470e…):
  - **PEKKA** (20): every fully identified P.E.K.K.A deck from s70-s76:
    - indices 91, 92, 97, 104, 105, 109, 112, 119, 121, 124, 125, 127, 130, 131, 133, 137, 138, 139, 141, 144;
    - runs s70-m08, m07, m01; s72-m06, m05; s73-m17, m14; s74-m18, m16, m13, m12, m09, m05, m04, m01; s75-m04; s76-m01, m02, m04, m09.
    - The analysis named 19 P.E.K.K.A rows in s70-s74. Four of them (s72-m03, s72-m04, s73-m12, s74-m06) have one unidentified slot and are dropped by the pool rule. s75 / s76 add 5.
  - **Control** (12): the newest fully identified no-P.E.K.K.A decks, s76 first:
    - indices 140, 142, 143, 145, 146, 147, 134, 135, 136, 120, 122, 123;
    - runs s76-m03, m06, m07, m11, m12, m13; s75-m01, m02, m03; s74-m17, m15, m14.
- **Cases:** 100 per stratum. Each case draws its deck uniformly from its stratum (rng keyed by the case seed); seat alternates.
  - seed = BASE + stratum_index * 101 + i.
  - The same cases (seed, deck, seat) are used in both level rows.
- **Level rows:**
  - **L16 (primary):** both sides level 16, towers 16 / 16.
  - **Account (secondary):** our levels Valkyrie 6, Archers 8, Bats 7, Cannon 7, Fireball 6, Zap 8, MiniPekka 7, Giant 7; King 7. Each opponent at its Battle Log row's logged card levels, King = the logged opp_king_level (9 in every row).
- **Size:** 2 arms x 2 strata x 100 x 2 rows = 800 games.
- **Hosts:** 08 runs the L16 row and 04 runs the account row, each <= 24 workers, cpu_job, nice.
- **Code:** driver cadence-pk1/l16_cadence.py sha256 174b70bb… (read-only); source tree clasher-bot-livediag-cadsrc12 (lopp_fast c776f856, k4cw_fp a8dac0a6).
- **Precondition: met.** A 3-case smoke (s74-m04 PEKKA + Witch + SkeletonDragons + BattleRam + Hog, s74-m12 PEKKA + BattleRam + Guards, s76-m03 Hog) gave both arms x both rows = 12 games with 0 errors, 0 issues and 0 unmapped rows.

## Pre-registered predictions (bootstrap 95 % CI over cases, 10,000 resamples, seed 0)
1. **Matchup (primary):** in the account row, -res-wint scores at least 0.10 lower on PEKKA than on control.
   - Statistic: score(PEKKA) - score(control), with a CI from independent bootstraps of the two strata.
   - Holds if the point estimate is <= -0.10. Report the CI too.
2. **Play:** in both rows, delta(-res-wint - -res) on PEKKA is >= -0.03.
   - If that delta's CI lies entirely below 0 in either row, -wint is implicated.
3. **Mechanism:** undefended Hog / Battle Ram pushes per battle are higher on PEKKA than on control, for both arms.
   - Undefended (sim proxy, from the per-play truth log): an accepted opponent HogRider or BattleRam play with no accepted play of ours in the next 5.0 s (100 ticks).
   - Reported per stratum x arm x row as the mean per battle and the share of such plays.

Also reported per stratum x arm x row:
- reaction p50 / p90 (enemy play -> our next play, l16_report's definition);
- the undefended share;
- the score with its CI;
- errors / unclean rows;
- the deck composition actually drawn.

No early stopping. All 800 rows are read together once complete.
