# WINT-ACC1: is -wint worse at account levels? Pre-registration (bot live-diag; written before any game)

Origin: PEKKA-1 (RESULTS 14) flagged, outside its pre-registration, that at account levels res-wint was below res in both strata.
The test was ordered by the BOT LEAD on 2026-10-17. Live plays at account levels.

**BASE = 157708954493651.** Drawn with os.urandom(6) at 2026-10-17T21:08:44Z, before any WINT-ACC1 game.

## Design
- **Arms, paired on every case.** These are the LIVE names: live has run -lb since s79.
  - `res-lb` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb (the revert target);
  - `res-lb-wintp` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint, through lopp_fast.make_live_lopp '-wint'.
  - Both are serial twins, deadlines cleared. With no worker pool, -lb is a no-op by construction (balanced_chunks acts only on the p<P> pool). On the live pool path it is value-identical (416/416 identical actions; RESULTS 12), so these arms equal -res / -res-wint.
- **Opponents:** LIVE-K4CW-r16-fp (bot/livediag/k4cw_fp.py; calibrated +0.033 [-0.080, +0.147] vs K4CW-r16) and R3a.
- **Own deck:** Sam's live deck (Valkyrie, Archers, Bats, Cannon, Fireball, Zap, MiniPekka, Giant).
- **Levels: account row only.**
  - Ours: Valkyrie 6, Archers 8, Bats 7, Cannon 9, Fireball 6, Zap 8, MiniPekka 7, Giant 7; King 7 (current, BOT LEAD 2026-10-17).
  - Opponent: each Battle Log row's logged card levels, with its logged King level.
- **Decks: pool v3.1** (battlelog-pool-v3.1.jsonl sha256 2cff0819…). The rows are drawn uniformly by index, so duplicate rows keep their observed frequency. Eligible rows are fixed before launch (pools/wintacc1-rows.json sha256 d6ff4a44…):
  - only rows with complete logged card levels and a logged King level, which the account row needs. That excludes all 91 v1 rows, which have no level log;
  - only logged opp_king_level == 9, i.e. today's ladder (the BOT LEAD's "King 9"). That excludes 17 King 8 rows and 1 King 7 row from the s69-s72 logs at ~1850 trophies;
  - **every Goblin Hut deck excluded** (decided before launch). Its RoyaleSim SpearGoblin_Dummy bodies have no translator counterpart (CARD LEAD vocab fix pending).
  - Result: **43 rows (31 distinct decks; 20 of the rows have a P.E.K.K.A)**, from s70 (1), s73 (9), s74 (12), s75 (4), s76 (7), s77 (1) and s78 (9).
  - Indices: 92, 108-114, 116, 118, 119, 122-131, 133-141, 143, 144, 146, 148, 149, 151, 152, 154-159.
- **Cases:** 300 per opponent. The deck is drawn uniformly from the 43 rows (rng keyed by the case seed); seat alternates.
  - seed = BASE + opponent_index * 301 + i (one stratum, not paired across opponents).
  - Total 2 arms x 300 x 2 opponents = 1,200 games.
- **Code:**
  - driver cadence-pk1/l16_cadence.py sha256 174b70bb… (read-only; the PEKKA-1 copy);
  - source tree: a full archive of main 7df775763 (clasher-bot-livediag-par-7df775763; lopp_fast 45070185, k4cw_fp a8dac0a6);
  - vocab: vocabv3/vocab-full.json (f588168f…).
- **Hosts:** --shard K/4. 127x08 runs shards 0-2 at 8 workers each; 127x04 runs shard 3 at 8 workers (04 has an active user). cpu_job, nice, <= 110 load.

## Pre-registered
- **Primary:** delta = score(res-lb-wintp) - score(res-lb) vs LIVE-K4CW-r16-fp, paired by case. Bootstrap 95 % CI over cases: 10,000 resamples, seed 0.
  - If the CI lies entirely below 0: -wint is implicated at account levels. Recommend that the LIVE LEAD revert to `...-mk1a1-res-lb`.
  - If the CI includes 0: -wint stays.
- **Secondary (no decision attached):**
  - the same delta vs R3a;
  - per opponent x arm: score with CI, reaction p50 / p90, timed-wait interrupts per battle, our elixir when an enemy unit crosses the river (l16_report's elixir_cross), undefended share.
- **Mechanism look.** Is -wint spending elixir into enemy plays it can't profitably answer when outmatched by levels? Measured per battle:
  - elixir spent within 3 s after an enemy play;
  - the tower damage taken / dealt in those exchanges;
  - both by arm.
- No early stopping. All rows are read together once complete.
