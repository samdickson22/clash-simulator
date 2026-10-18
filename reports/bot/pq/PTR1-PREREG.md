# PTR1: fresh-bank replication of the PT1 prior tie-break on the live configuration. Pre-registration (play-quality owner)

Registered before any PTR1 game. BASE **1962852923111632**, drawn on 127x04 at 2026-10-18T08:52:10Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint; disjoint from PT1's 68725711644388+[0,400]).

## Why
PT1 (reports/coordinator/readouts/pt1-20261018.md; source 68816487f; old Giant/MiniPekka deck) passed its candidate gates:
λ=.005 L16 pooled +.093 [+.045, +.140], account +.128 [+.071, +.184], vs K4CW-fp L16 +.170 [+.083, +.257]; idle plays
−5.9 pp, win-condition dumps −3.1 pp, elixir at the enemy win-con crossing +1.5. Its rule requires a fresh-bank replication
before any live change. Coordinator 2026-10-18: run it on the LIVE configuration (top priority).

## Change
Token `pt<N>` (bot/search/priortb.py, unchanged; λ = N/1000): every scored root key (plays, WAIT, timed waits) gets
λ·log max(π(a), 1e-4), π = the live fast tier's own policy at the same poll (f1a2 in this driver, as in PT1).
This commit only lets the L16 driver accept the token.

## Design
- Live configuration: live Hog deck (HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie), WITH
  RF (shipped). Arms (serial twins, paired on every case): `res-lb-RF-wintp` (reference), `res-lb-RF-pt5-wintp`
  (**primary**, λ=.005), `res-lb-RF-pt2-wintp` (secondary, λ=.002).
- Opponents: LIVE-K4CW-r16-fp (strong, primary), R3a, HPv2 (the v2 human policy alone; human-like row). 200 paired cases
  each per row. Pool v3.2 53 King-9 rows (no Goblin Hut), vocab-full. Rows L16 and account (ours Skeletons 7, Archers 8,
  Valkyrie 7, Cannon 9, Fireball 7, Zap 9, ElectroSpirit 8, HogRider 8, King 7; opponents logged levels). 3600 games, 04/08,
  tree = this commit, bot/pq/l16.sh, default lopp models (k1a1).

## Prediction and ship rule (primary λ=.005; λ=.002 reported the same way, secondary)
Prediction: pt5 − RF > 0 vs K4CW-fp. Ship: vs K4CW-fp pooled over both rows lower 95% bound ≥ 0; neither K4CW row point
below −0.02; HPv2 pooled point ≥ 0; the play-quality metrics (idle share, wincon spend, Hog-crossing elixir, barrel answers,
wrong lane, spell hits) not worse beyond ~2 SE. If pt5 fails and pt2 passes the same rule, pt2 is reported as an
exploratory candidate only (secondary arm), not a ship. Readout with the RF1 scorer, per row and opponent, plus CPU-ms.
