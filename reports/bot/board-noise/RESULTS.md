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
