# Live loss analysis: s74 (6W–12L) vs s73 (11W–7L), same -res-wint stack

Bot lead, live-diag (exploration tier). Written 2026-10-17T17:59Z (`date -u`). Read-only on the live run dirs; no game bytes, video or screenshots here.
Opponent names and tags aren't recorded; only decks and levels are.

## Verdict

**The drop is matchup mix plus variance. Neither levels nor -wint play explains it.**

- **Levels didn't change between s73 and s74.** Opponent tower HP reads were King 9 (princess 2534 / King 4008) in 17/18 s73 battles and 18/18 s74 battles.
  The Battle Log agrees. Our towers are King 7 (2184 / 3528), so the King gap is +2 in 35/36 battles. That means **+16% princess HP and +13.6% King HP**
  for the opponent in both sessions. The mean card-level gap is also flat: s73 +1.09 (n=14) vs s74 +1.06 (n=18). Pooled, the level gap doesn't predict wins
  (Spearman −0.20, permutation p 0.29; logistic slope −0.30 ± 0.65 per level).
- **Where "mostly King 8" came from:** those rows are s69–s72 (1850 Battle Log: 22×L8, 1×L9; tower HP 2352 / 3768). So King 9 opponents arrived when we
  crossed 2,000, between s72 and s73. That is also when -wint started, so live data can't separate those two.
- **Matchup:** 9/18 s74 opponents ran P.E.K.K.A (s74 1–8), against 3/18 in s73 (s73 2–1). Without PEKKA the two sessions match: s73 9–6 (0.60) vs s74 5–4 (0.56).
  PEKKA vs no-PEKKA:
  - s73+s74: 3/12 vs 14/24 (Fisher p 0.083).
  - Adding the s69–s72 Battle Log rows: 6/20 vs 24/39 (p 0.029).

  This split was chosen after looking at the data, so treat it as a strong lead, not a finding. With s73's PEKKA share, s74's own per-group rates give
  9.1 expected wins instead of 6. Most s74 PEKKA decks are bridge-spam: PEKKA + BattleRam/HogRider + Barbarians/Wizard/Skeleton Dragons/Witch.
- **Play metrics are flat between sessions** (all s74−s73 bootstrap CIs span 0):
  - Reaction (enemy card → our next play): p50/p90 2.62/8.08 s in s73 vs 2.63/7.57 s in s74. Enemy card → next searched decision: 0.5/1.42 s in both.
  - Elixir: per minute 25.8 vs 24.8. HUD elixir ≥ 9 for 0.4% of time in both; leak ≈ 0. The bot almost never sits at full.
  - Fireball 1.56 vs 1.56 and Zap 3.7 vs 3.3 per battle.
  - -wint: timed waits 100.7 vs 93.4 per battle, interrupted 36.7 vs 31.9, WAIT share 0.78 vs 0.78.
  - Win-condition pushes: 35 vs 35. Undefended at contact 7/21 vs 9/23. The existing live_metrics Giant rule gives 0 vs 1 undefended.
- **-wint in PEKKA games:** 3/12 with -res-wint (s73+s74, King 9) vs 3/8 with -res/-mk1a1 (s69–s72, King 8), Fisher p 0.64. Level differs too, so this
  doesn't implicate -wint. Interrupt counts in PEKKA games (36.8/battle) are close to non-PEKKA games (33.0).
- **What does differ in PEKKA games:** undefended win-condition pushes are 0.58/battle vs 0.38 without PEKKA, mostly HogRider (4 of 10 undefended in PEKKA
  games vs 7/27 elsewhere). Tower deaths involve PEKKA plus Barbarians/BattleRam/Hog. That is a deck-matchup weakness (our only PEKKA answers are
  MiniPekka, Cannon kiting and Bats/Archers), not a session-specific play change.
- **Variance:**
  - 11/18 vs 6/18 gives Fisher two-sided p = 0.18. Power at α .05 with 18+18 is 0.16 for a true Δ of 0.20, 0.36 for 0.30, 0.61 for 0.40 and 0.83 for 0.50.
    Only a ≥ 0.45 true swing is reliably detectable.
  - At 2,000+ the -wint record is 18–19 (0.49), and P(≤ 6/18 | p 0.49) ≈ 0.14. At the pre-2,000 lifetime rate since s63 (60–39, 0.61) it would be 0.018,
    but that rate came against King 8 opponents.
  - The losses were closer in s74: 7/12 lost by one crown (s73 3/7). Six of the 12 s74 losses were three-crown losses (s73 3/7).
  - The deciding crown came in the last 60 s or overtime in 7/12 s74 losses and 5/7 s73 losses. The deciding tower fell from ≥ 90% HP within 30 s in
    3/12 s74 losses and 1/7 s73 losses.

## Proposed sim test (not run): the PEKKA matchup

The bot lead's level-paired design (s74 levels vs s73 levels) would test a difference that doesn't exist: both sessions were King 9 with the same card
gap. I propose the matchup test instead.

- **Arms:** `…-mk1a1-res-wint` (live) vs `…-mk1a1-res` (the pre-wint live player), paired on the same cases. Sam's live deck.
- **Opponent:** LIVE-K4CW-r16 (rl5 v10 pin), deterministic, in the deployed full-pool runtime (live16402b-r3), piloting real Battle Log decks.
  - PEKKA set: the 19 fully logged PEKKA decks from the s70/s72/s73/s74 Battle Logs (pool v2.1 has none, so add these rows as pool v2.2). s72-m07 is excluded: its PEKKA is perceived only.
  - Control set: the 12 most recent no-PEKKA s73/s74 decks.
- **Levels, two rows:**
  - Primary: L16 both sides, per the standing play-eval rule.
  - Secondary (account level): our real levels (Valkyrie 6, Archers 8, Bats 7, Cannon 7, Fireball 6, Zap 6, MiniPekka 7, Giant 7; King 7) vs each
    opponent's Battle Log card levels with King 9 towers.
- **n:** 100 paired cases per deck set per level row, i.e. 2 arms × 2 deck sets × 2 rows × 100 = 800 games. Fresh BASE drawn and committed before any game.
- **Precondition:** a 3-case smoke showing K4CW plays PEKKA/BattleRam/HogRider decks with 0 errors in the full-pool runtime.
- **Pre-registered predictions** (bootstrap 95% CI over cases):
  1. **Matchup (primary):** -res-wint scores at least 0.10 lower on PEKKA decks than on control decks in the account-level row.
  2. **Play:** Δ(-res-wint − -res) on PEKKA decks is ≥ −0.03 in both rows, i.e. -wint isn't what loses these games. If the CI on that Δ is entirely below 0,
     -wint is implicated and -res goes back live.
  3. **Mechanism:** undefended HogRider/BattleRam contacts per battle are higher on PEKKA decks for both arms.
- **If (1) holds:** the lever is the deck (Sam picks it) or matchup-specific search/leaf work, not the -wint timing.

## Data and methods

- **Runs:** 127x05 `scratch/live-loop/runs/s73|s74/m01–m18`. Context rows: s69/s70/s72 battles that have Battle Log rows.
  - All 36 s73/s74 battles have an identical config fingerprint: player, fast model, manifest sha, x1h model, hand, owner, true-ids, session settings and
    client version.
  - Outcomes come from the babysitter audit tallies (`evidence/<sid>-r3/audit-tally.json`), with crowns taken from the corrected Battle Log reads.
- **Battle Logs (sha256 computed 2026-10-17T18:00Z, at the final read):**
  - s74 `opponent-decks-20261017-s74-royal-arena.jsonl` = `b0b96bc03cccb35afbc2dc9a4bf41282d7964a7513549ca5a6c338eafbe98ec1`
  - s73 `opponent-decks-20261017-s73-royal-arena.jsonl` = `4d8f912dc0884985dc5079ed72fe4f348b7bbe1f75b9dc9f4d2c756db7f3261c`
  - s69–s72 `opponent-decks-20261017-1850.jsonl` = `0780bd555b9355facb1f85dc254e575fe7f2e314743e0357c0ce0a76dd9f47ce`

  These are the final metadata re-issues: framed evo/hero icons are now LOW confidence, with bases, forms and levels unchanged. The receipts are under scratch/live-loop/evidence/. Earlier reads (s74 69f5967f…, a9c40d82…) produce identical tables. Nothing here filters on confidence.

  Four s73 rows are still clipped (m01, m04, m07, m10). Their archetype and PEKKA flag come from the perceived opponent card set, and none of the four
  perceived sets contains PEKKA.
- **Script:** `bot/livediag/loss_s74_vs_s73.py` (sha256 `a160c22216f9ac34f6b6790f36a2465c10f0b7090ba8a92ccd776bf99f27fc30`; pure python3, PYTHONHASHSEED=0, about 12 s on 05). The tables below are its
  `tables.md` (sha256 `8053e4a862c3aaaba36f82c75e61fe7e562367b5faae3e53b761381c88410c63`). The docstring gives the metric definitions.
  - The Giant rule is `bot.livediag.live_metrics.analyse`, unchanged.
  - The win-condition push rule is the same rule applied to detector source cards.
  - Reaction follows l16_report: enemy play → our next play. Live enemy plays use a deploy-episode proxy.
  - The repo has no elixir-traded metric (live has no kill truth). I report our spend, the opponent's committed elixir (proxy) and the spend share instead.
- **Caveats:**
  - Perception-based proxies: owner flips (own Bats) add spurious enemy episodes in both sessions alike.
  - HUD elixir never reads above about 9.2 (no plateau), so "leak" is ≈ 0 by construction. The ≥ 9 share is the better signal and is 0.4% in both sessions.
  - Tower death times match the babysitter's tower-transition files exactly, and those were video-checked against rubble frames. I did no new video
    inspection.
  - Game-ending kills (king, or a last-second princess) leave no dead frames, so they're dated at end of battle.

## Per battle
| battle | res | crowns | Δtr | dur s | OT | archetype (src) | lvl gap | King gap | plays | elixir/min | FB | Zap | elixir≥9 share | waits | interrupted | react p50/p90 s | win-con pushes / undefended | deciding crown (t, phase, push s, attackers) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s73-m01 | W | 1-0 | 32 | 174.8 |  | swarm-spam (p) | None | 2 | 30 | 24.72 | 1 | 4 | 0.0104 | 91 | 39 | 2.42/6.46 | 0/0 | pl 94.5s ph1 57.6s Valkyrie/Bats/Bomber |
| s73-m02 | W | 2-1 | 29 | 270.9 | Y | hog-cycle (b) | 1.25 | 2 | 53 | 30.35 | 4 | 3 | 0.0019 | 137 | 53 | 3.03/7.26 | 7/1 | pl 270.9s ph3 Nones Bats/Valkyrie/Archers |
| s73-m03 | L | 0-2 | -30 | 175.8 |  | giant-beatdown (b) | -1.125 | 0 | 29 | 25.59 | 3 | 4 | 0.004 | 98 | 34 | 3.94/8.79 | 5/2 | pr 92.9s ph1 64.7s SkeletonDragons/Giant/Wizard |
| s73-m04 | L | 1-3 | -1 | 177.6 |  | hog-cycle (p) | None | 2 | 30 | 24.33 | 2 | 4 | 0.0023 | 94 | 42 | 2.63/8.76 | 3/1 | kc 177.6s ph2 30.0s Pekka/MegaMinion/MiniPekka |
| s73-m05 | W | 1-0 | 30 | 230.1 |  | swarm-spam (b) | 1.375 | 2 | 43 | 27.65 | 1 | 7 | 0.0027 | 116 | 47 | 2.32/6.66 | 0/0 | pl 230.1s ph2 Nones Giant/MiniPekka/Bats |
| s73-m06 | W | 3-2 | 30 | 192.7 |  | giant-beatdown (b) | 1.5 | 2 | 32 | 24.91 | 0 | 3 | 0.0021 | 100 | 29 | 2.92/6.47 | 1/0 | kc 192.7s ph2 Nones Giant/Archers/MiniPekka |
| s73-m07 | W | 2-1 | 31 | 176.0 |  | hog-cycle (p) | None | 2 | 27 | 26.59 | 3 | 2 | 0.0034 | 87 | 26 | 2.73/7.69 | 4/2 | pl 176.0s ph2 30.0s Giant/Bats/Cannon |
| s73-m08 | L | 0-1 | -28 | 176.0 |  | control/no-wincon (b) | 2.25 | 2 | 26 | 25.91 | 1 | 2 | 0.0034 | 82 | 18 | 2.72/6.77 | 0/0 | pl 150.4s ph2 115.3s MiniPekka/GoblinCage/Barbarians |
| s73-m09 | L | 0-1 | -29 | 175.9 |  | hog-cycle+barrel (b) | 0.75 | 2 | 30 | 24.55 | 2 | 4 | 0.0035 | 85 | 16 | 2.22/12.73 | 3/0 | pr 175.9s ph2 Nones HogRider/Goblins/Barbarians |
| s73-m10 | W | 3-1 | 32 | 163.7 |  | control/no-wincon (p) | None | 2 | 27 | 24.56 | 1 | 3 | 0.005 | 93 | 35 | 3.43/11.62 | 0/0 | pl 161.3s ph2 68.8s Valkyrie/Archers/Bats |
| s73-m11 | W | 2-0 | 30 | 176.1 |  | swarm-spam (b) | 0.875 | 2 | 30 | 25.89 | 0 | 5 | 0.0023 | 94 | 41 | 2.32/7.46 | 0/0 | pr 134.1s ph2 91.0s Archers/Valkyrie/Bats |
| s73-m12 | W | 1-0 | 30 | 239.0 |  | pekka-bridge-spam (b) | 0.5 | 2 | 42 | 27.36 | 4 | 4 | 0.0017 | 132 | 54 | 2.42/6.46 | 4/0 | kc 239.0s ph2 30.0s MiniPekka |
| s73-m13 | W | 1-0 | 30 | 175.9 |  | giant-beatdown (b) | 1.625 | 2 | 27 | 24.9 | 1 | 2 | 0.0058 | 80 | 13 | 3.53/8.58 | 1/0 | pl 161.1s ph2 55.4s Bats/MiniPekka/Minions |
| s73-m14 | W | 1-0 | 30 | 176.0 |  | pekka-control (b) | 0.75 | 2 | 29 | 25.23 | 0 | 4 | 0.0034 | 102 | 39 | 2.33/6.98 | 1/0 | pl 79.0s ph1 33.8s  |
| s73-m15 | L | 1-2 | -30 | 205.3 |  | hog-cycle+barrel (b) | 1.625 | 2 | 36 | 26.31 | 1 | 4 | 0.0034 | 100 | 26 | 3.53/7.86 | 5/1 | pr 205.3s ph2 Nones Skeletons/Goblins/Bats |
| s73-m16 | L | 1-3 | -29 | 242.6 | Y | swarm-spam (b) | 1.75 | 2 | 46 | 27.7 | 0 | 8 | 0.0017 | 144 | 82 | 2.64/8.18 | 0/0 | kc 242.6s ph3 Nones Goblins/Bats/SpearGoblins |
| s73-m17 | L | 1-3 | -29 | 101.4 |  | pekka-bridge-spam (b) | 1.25 | 2 | 14 | 21.3 | 1 | 2 | 0.007 | 53 | 17 | 3.24/10.3 | 1/0 | kc 101.4s ph1 Nones Barbarians |
| s73-m18 | W | 2-1 | 30 | 213.2 |  | giant-beatdown (b) | 0.875 | 2 | 35 | 27.3 | 3 | 2 | 0.0019 | 124 | 50 | 2.12/6.57 | 0/0 | pl 213.2s ph2 Nones Giant/Bats/MiniPekka |
| s74-m01 | L | 2-3 | -29 | 121.6 |  | pekka-control (b) | 1.25 | 2 | 17 | 20.73 | 1 | 2 | 0.0067 | 63 | 23 | 5.95/9.6 | 1/0 | pl 87.7s ph1 68.2s Giant/SkeletonDragons/MiniPekka |
| s74-m02 | W | 1-0 | 30 | 176.0 |  | log-bait (b) | 1.25 | 2 | 28 | 24.55 | 2 | 3 | 0.0035 | 91 | 29 | 2.12/7.99 | 0/0 | pr 137.6s ph2 120.1s Bats/Valkyrie/Barbarians |
| s74-m03 | W | 1-0 | 30 | 176.0 |  | giant-beatdown (b) | 1.0 | 2 | 27 | 24.89 | 1 | 1 | 0.0035 | 86 | 14 | 3.42/7.87 | 2/0 | pr 153.5s ph2 129.7s Bats/Valkyrie/MiniPekka |
| s74-m04 | L | 1-3 | -30 | 211.8 |  | pekka-bridge-spam (b) | 1.375 | 2 | 37 | 27.76 | 2 | 5 | 0.0029 | 109 | 40 | 2.32/9.81 | 4/2 | kc 211.8s ph2 Nones Barbarians/SkeletonDragons/HogRider |
| s74-m05 | L | 1-2 | -30 | 176.2 |  | pekka-bridge-spam (b) | 1.375 | 2 | 30 | 24.51 | 1 | 4 | 0.0017 | 103 | 53 | 2.53/7.16 | 1/1 | pr 168.4s ph2 100.1s Goblins/Barbarians/HogRider |
| s74-m06 | L | 1-3 | -29 | 234.6 |  | pekka-control (b) | 0.625 | 2 | 42 | 27.62 | 1 | 4 | 0.0021 | 128 | 40 | 2.94/7.07 | 1/0 | kc 234.6s ph2 30.0s Pekka/Valkyrie/BabyDragon |
| s74-m07 | W | 3-1 | 30 | 150.7 |  | control/no-wincon (b) | 0.875 | 2 | 24 | 24.28 | 0 | 4 | 0.0034 | 78 | 36 | 2.93/10.5 | 0/0 | pl 149.7s ph2 113.7s Giant/MiniPekka/Archers |
| s74-m08 | W | 1-0 | 30 | 200.6 |  | hog-cycle (b) | 1.0 | 2 | 35 | 26.92 | 1 | 4 | 0.0035 | 96 | 26 | 2.03/5.95 | 9/1 | pr 200.6s ph2 Nones MiniPekka/Bats |
| s74-m09 | L | 1-3 | -30 | 302.0 | Y | pekka-bridge-spam (b) | 1.125 | 2 | 62 | 31.59 | 5 | 6 | 0.001 | 153 | 53 | 2.23/5.66 | 4/2 | kc 302.0s ph3 Nones  |
| s74-m10 | W | 1-0 | 30 | 180.9 |  | control/no-wincon (b) | 0.875 | 2 | 30 | 24.88 | 3 | 4 | 0.0034 | 86 | 18 | 3.53/9.69 | 0/0 | pr 180.9s ph2 Nones Bats/MiniPekka/Skeletons |
| s74-m11 | L | 1-3 | -30 | 108.1 |  | hog-cycle (b) | 1.5 | 2 | 15 | 19.42 | 0 | 3 | 0.0028 | 58 | 21 | 3.73/7.17 | 3/1 | pr 89.8s ph1 61.5s Barbarians/BattleRam/Valkyrie |
| s74-m12 | L | 1-2 | -29 | 175.9 |  | pekka-bridge-spam (b) | 1.125 | 2 | 29 | 23.87 | 3 | 3 | 0.0098 | 90 | 35 | 2.12/7.87 | 4/0 | pr 169.0s ph2 131.1s Minions/Pekka/Goblins |
| s74-m13 | L | 0-1 | -29 | 176.1 |  | pekka-bridge-spam (b) | 1.25 | 2 | 27 | 24.53 | 2 | 3 | 0.0029 | 93 | 33 | 2.82/9.48 | 2/1 | pr 102.3s ph1 67.6s Barbarians/BattleRam/Goblins |
| s74-m14 | L | 0-1 | -28 | 176.2 |  | ram-bridge-spam (b) | 1.25 | 2 | 27 | 24.52 | 0 | 1 | 0.0133 | 92 | 34 | 4.74/8.87 | 1/0 | pr 49.4s ph1 24.5s Barbarians/MegaMinion/BattleRam |
| s74-m15 | L | 0-1 | -14 | 176.2 |  | control/no-wincon (b) | 1.375 | 2 | 28 | 24.18 | 3 | 3 | 0.0023 | 97 | 40 | 2.92/6.96 | 0/0 | pr 45.5s ph1 17.3s Minions/MiniPekka/Skeletons |
| s74-m16 | L | 1-3 | 0 | 163.1 |  | pekka-bridge-spam (b) | 0.75 | 2 | 26 | 24.29 | 0 | 2 | 0.0031 | 79 | 24 | 3.03/6.76 | 2/0 | kc 163.1s ph2 Nones Pekka/HogRider/MegaKnight |
| s74-m17 | L | 0-1 | 0 | 176.1 |  | log-bait (b) | 0.5 | 2 | 29 | 24.88 | 2 | 3 | 0.0029 | 89 | 24 | 2.22/4.85 | 0/0 | pr 170.1s ph2 137.5s Goblins/SkeletonDragons/SpearGoblins |
| s74-m18 | W | 1-0 | 30 | 176.4 |  | pekka-bridge-spam (b) | 0.5 | 2 | 29 | 23.82 | 1 | 5 | 0.0017 | 91 | 31 | 2.33/7.28 | 1/1 | pr 140.4s ph2 128.3s MiniPekka/Skeletons/Giant |

## Session aggregates (mean per battle; pooled reaction quantiles)
| metric | s73 | s74 | s74−s73 95% CI (bootstrap) | s73+s74 wins | s73+s74 losses |
|---|---|---|---|---|---|
| dur_s | 191.278 | 181.028 | (-35.256, 15.767) | 191.118 | 181.711 |
| plays | 32.556 | 30.111 | (-8.444, 3.889) | 32.235 | 30.526 |
| elixir_spent | 83.444 | 76.611 | (-22.5, 9.778) | 82.941 | 77.421 |
| elixir_per_min | 25.842 | 24.847 | (-2.519, 0.489) | 25.812 | 24.926 |
| enemy_elixir_proxy | 153.5 | 131.944 | (-54.833, 12.111) | 147.235 | 138.684 |
| spend_share | 0.361 | 0.372 | (-0.017, 0.039) | 0.368 | 0.365 |
| fireball | 1.556 | 1.556 | (-0.833, 0.889) | 1.529 | 1.579 |
| zap | 3.722 | 3.333 | (-1.389, 0.611) | 3.529 | 3.526 |
| elixir_mean | 2.783 | 2.762 | (-0.17, 0.118) | 2.825 | 2.726 |
| elixir_ge9_share | 0.004 | 0.004 | (-0.001, 0.002) | 0.004 | 0.004 |
| elixir_leaked | 0.0 | 0.016 | (0.0, 0.048) | 0.0 | 0.015 |
| search_wait_share | 0.777 | 0.779 | (-0.01, 0.014) | 0.775 | 0.781 |
| timed_waits | 100.667 | 93.444 | (-21.0, 6.833) | 99.059 | 95.263 |
| timed_wait_mean_s | 1.892 | 1.894 | (-0.016, 0.022) | 1.894 | 1.893 |
| waits_interrupted | 36.722 | 31.889 | (-14.222, 4.167) | 34.118 | 34.474 |
| wincon_pushes | 1.944 | 1.944 | (-1.389, 1.444) | 1.765 | 2.105 |
| wincon_contact | 1.167 | 1.278 | (-0.889, 1.056) | 1.0 | 1.421 |
| wincon_undefended | 0.389 | 0.5 | (-0.333, 0.556) | 0.294 | 0.579 |
| wincon_wait_at_cross | 1.5 | 1.444 | (-1.0, 0.889) | 1.118 | 1.789 |
| giant_pushes_lm | 0.611 | 0.389 | (-0.889, 0.444) | 0.647 | 0.368 |
| giant_undef_lm | 0.0 | 0.056 | (0.0, 0.167) | 0.0 | 0.053 |
| elixir_cross_p50 | 2.95 | 2.542 | (-1.594, 0.896) | 2.651 | 2.775 |
| def_minus_cross_p50 | -0.055 | -0.175 | (-2.4, 2.183) | -0.263 | -0.04 |
| react_play p50 / p90 (s; n) | 2.62 / 8.08 (n=1036) | 2.63 / 7.57 (n=708) | | 2.52 / 7.57 | 2.72 / 8.18 |
| react_search p50 / p90 (s; n) | 0.5 / 1.42 (n=1044) | 0.5 / 1.42 (n=715) | | 0.5 / 1.42 | 0.5 / 1.42 |

## Win-condition pushes (pooled, by session)
- s73: pushes 35, reached contact 21, undefended 7 (0.33 of contacts), timed wait active at cross 27, def−cross p50 -0.2 s, elixir at cross p50 2.85; by card {'HogRider': 24, 'BattleRam': 4, 'Giant': 4, 'Pekka': 3}
- s74: pushes 35, reached contact 23, undefended 9 (0.39 of contacts), timed wait active at cross 26, def−cross p50 -0.9 s, elixir at cross p50 1.34; by card {'HogRider': 13, 'BattleRam': 12, 'Pekka': 6, 'Giant': 4}

## Archetype W/L per session
| archetype | s73 W-L | s74 W-L |
|---|---|---|
| control/no-wincon | 1-1 | 2-1 |
| giant-beatdown | 3-1 | 1-0 |
| hog-cycle | 2-1 | 1-1 |
| hog-cycle+barrel | 0-2 | 0-0 |
| log-bait | 0-0 | 1-1 |
| pekka-bridge-spam | 1-1 | 1-6 |
| pekka-control | 1-0 | 0-2 |
| ram-bridge-spam | 0-0 | 0-1 |
| swarm-spam | 3-1 | 0-0 |

## King level and tower HP (start-of-battle HP reads, median of the first 40 perception rows)
| session | battles | opp King (Battle Log) | opp princess HP | opp King HP | our princess / King HP | W-L |
|---|---|---|---|---|---|---|
| s73 | 18 | {9: 17, 7: 1} | {2534: 17, 2184: 1} | {4008: 17, 3528: 1} | {(2184, 3528): 18} | 11-7 |
| s74 | 18 | {9: 18} | {2534: 18} | {4008: 18} | {(2184, 3528): 18} | 6-12 |
| s69 (context, Battle Log rows only) | 6 | {None: 6} | {2352: 6} | {3768: 6} | {(2184, 3528): 6} | 2-4 |
| s70 (context, Battle Log rows only) | 8 | {None: 8} | {2352: 7, 2534: 1} | {3768: 7, 4008: 1} | {(2184, 3528): 8} | 6-2 |
| s72 (context, Battle Log rows only) | 9 | {None: 9} | {2352: 9} | {3768: 9} | {(2184, 3528): 9} | 5-4 |

## Level gap (Battle Log rows with >= 6 opponent levels)
- s73: n=14, mean card-level gap 1.089, King gap mean 1.857; W 1.094 vs L 1.083
- s74: n=18, mean card-level gap 1.056, King gap mean 2.0; W 0.917 vs L 1.125
- pooled n=32: Spearman(level gap, win) = -0.196, permutation p = 0.287; logistic slope -0.30 ± 0.65 per level (Wald z -0.47)

## Losses: deciding crown
- s73: losses 7; deciding crown in last 60 s / overtime 5; deciding tower fell from >= 90% HP within 30 s (one push) 1; three-crown losses 3; one-crown margin 3
- s74: losses 12; deciding crown in last 60 s / overtime 7; deciding tower fell from >= 90% HP within 30 s (one push) 3; three-crown losses 6; one-crown margin 7

## Opponent deck contains P.E.K.K.A (Battle Log deck; perceived set if clipped)
| group | s73 W-L | s74 W-L | s69-s72 context W-L (pre-wint, King 8) |
|---|---|---|---|
| PEKKA | 2-1 | 1-8 | 3-5 |
| no PEKKA | 9-6 | 5-4 | 10-5 |
- s73+s74: PEKKA 3/12 wins vs no-PEKKA 14/24; Fisher two-sided p = 0.083 (post-hoc split: treat as a lead, not a finding)
- PEKKA opponents: s73 3/18 vs s74 9/18 (Fisher p = 0.075)
- with the s69-s72 Battle Log rows: PEKKA 6/20 vs no-PEKKA 24/39; Fisher p = 0.029
- PEKKA decks, -res-wint (s73+s74, King 9) 3/12 vs pre-wint -res/-mk1a1 (s69-s72, King 8) 3/8; Fisher p = 0.642
- counterfactual: s74 with s73's PEKKA share (3/18) at s74's own per-group win rates -> 9.1 expected wins (actual 6); no-PEKKA win rate s73 0.60 vs s74 0.56

| metric (mean per battle) | PEKKA s73+s74 | no-PEKKA s73+s74 | PEKKA s69-s72 (pre-wint) |
|---|---|---|---|
| dur_s | 187.842 | 185.308 | 143.037 |
| plays | 32.0 | 31.0 | 21.375 |
| elixir_per_min | 25.218 | 25.407 | 21.767 |
| spend_share | 0.366 | 0.366 | 0.317 |
| fireball | 1.75 | 1.458 | 1.0 |
| zap | 3.667 | 3.458 | 2.125 |
| timed_waits | 99.667 | 95.75 | 0.0 |
| waits_interrupted | 36.833 | 33.042 | 0.0 |
| search_wait_share | 0.784 | 0.775 | 0.765 |
| wincon_pushes | 2.167 | 1.833 | 1.875 |
| wincon_contact | 1.5 | 1.083 | 1.625 |
| wincon_undefended | 0.583 | 0.375 | 0.25 |
| elixir_cross_p50 | 3.301 | 2.157 | 2.546 |
| react_play p50 / p90 s | 2.52 / 7.28 | 2.72 / 8.08 | 2.83 / 9.2 |
| react_search p50 / p90 s | 0.5 / 1.31 | 0.5 / 1.51 | 0.82 / 1.72 |
- PEKKA s73+s74 win-condition pushes: 26, contact 18, undefended 7; by card HogRider 10/4u, Pekka 8/2u, BattleRam 6/1u, Giant 2/0u
- no-PEKKA s73+s74 win-condition pushes: 44, contact 26, undefended 9; by card HogRider 27/7u, BattleRam 10/2u, Giant 6/0u, Pekka 1/0u
- PEKKA s69-s72 win-condition pushes: 15, contact 13, undefended 2; by card Pekka 11/1u, BattleRam 2/0u, HogRider 2/1u

### Losses to PEKKA decks: deciding crown and the opponent units within 6 tiles of that tower in the 20 s before
- s73-m17 1-3 (pekka-bridge-spam): king@end center at 101.4 s, phase 1, from >=90% HP within 30 s: False; attackers ['Barbarians']; our plays 14, MiniPekka 2, Cannon 2
- s74-m01 2-3 (pekka-control): princess left at 87.7 s, phase 1, from >=90% HP within 30 s: False; attackers ['Giant', 'SkeletonDragons', 'MiniPekka', 'Bomber']; our plays 17, MiniPekka 2, Cannon 3
- s74-m04 1-3 (pekka-bridge-spam): king@end center at 211.8 s, phase 2, from >=90% HP within 30 s: False; attackers ['Barbarians', 'SkeletonDragons', 'HogRider', 'BattleRam']; our plays 37, MiniPekka 7, Cannon 5
- s74-m05 1-2 (pekka-bridge-spam): princess right at 168.4 s, phase 2, from >=90% HP within 30 s: False; attackers ['Goblins', 'Barbarians', 'HogRider', 'Bats']; our plays 30, MiniPekka 4, Cannon 4
- s74-m06 1-3 (pekka-control): king@end center at 234.6 s, phase 2, from >=90% HP within 30 s: True; attackers ['Pekka', 'Valkyrie', 'BabyDragon', 'MiniPekka']; our plays 42, MiniPekka 7, Cannon 6
- s74-m09 1-3 (pekka-bridge-spam): king@end center at 302.0 s, phase 3, from >=90% HP within 30 s: False; attackers []; our plays 62, MiniPekka 10, Cannon 7
- s74-m12 1-2 (pekka-bridge-spam): princess right at 169.0 s, phase 2, from >=90% HP within 30 s: False; attackers ['Minions', 'Pekka', 'Goblins', 'Barbarians']; our plays 29, MiniPekka 2, Cannon 5
- s74-m13 0-1 (pekka-bridge-spam): princess right at 102.3 s, phase 1, from >=90% HP within 30 s: False; attackers ['Barbarians', 'BattleRam', 'Goblins', 'MiniPekka']; our plays 27, MiniPekka 5, Cannon 2
- s74-m16 1-3 (pekka-bridge-spam): king@end center at 163.1 s, phase 2, from >=90% HP within 30 s: False; attackers ['Pekka', 'HogRider', 'MegaKnight', 'DarkPrince']; our plays 26, MiniPekka 6, Cannon 4
- s70-m07 0-3 (pekka-bridge-spam): princess left at 97.4 s, phase 1, from >=90% HP within 30 s: False; attackers ['Barbarians', 'Pekka', 'BattleRam', 'MiniPekka']; our plays 14, MiniPekka 1, Cannon 1
- s70-m08 0-1 (pekka-control): princess right at 126.7 s, phase 2, from >=90% HP within 30 s: False; attackers ['Pekka', 'Goblins', 'Skeletons', 'MegaKnight']; our plays 28, MiniPekka 4, Cannon 4
- s72-m04 0-1 (pekka-bridge-spam): princess right at 119.8 s, phase 1, from >=90% HP within 30 s: False; attackers ['Pekka', 'SkeletonWarriors', 'Giant', 'GoblinCage']; our plays 28, MiniPekka 5, Cannon 4
- s72-m05 2-3 (pekka-bridge-spam): king@end center at 179.7 s, phase 2, from >=90% HP within 30 s: True; attackers ['Barbarians', 'SkeletonDragons', 'Pekka', 'Wizard']; our plays 31, MiniPekka 3, Cannon 5
- s72-m07 1-3 (pekka-control): king@end center at 103.7 s, phase 1, from >=90% HP within 30 s: False; attackers ['Barbarians', 'Pekka', 'MiniPekka', 'Bats']; our plays 14, MiniPekka 1, Cannon 2

## Variance
- Fisher exact two-sided 11/18 vs 6/18: p = 0.181
- power (alpha .05, 18 vs 18) for true win rates 0.37 vs 0.57 (Δ 0.20): 0.16
- power (alpha .05, 18 vs 18) for true win rates 0.32 vs 0.62 (Δ 0.30): 0.36
- power (alpha .05, 18 vs 18) for true win rates 0.27 vs 0.67 (Δ 0.40): 0.61
- power (alpha .05, 18 vs 18) for true win rates 0.22 vs 0.72 (Δ 0.50): 0.83
