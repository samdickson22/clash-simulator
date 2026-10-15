# Noise-robust decisions: results (bot lead worker, exploration)

Status: IN PROGRESS. Numbers are from completed or interim screens, each labelled with its n. Design: DESIGN.md.
Log: PROGRESS.md.

## 1. Screens (ours engine, HEADLINE cases 0–299, PERC-emp = empirical-val.json, unit threshold 0.4)

**Screening player.**
- `LIVED-K4L-R-gs-rw-fc` is the deterministic twin of LIVE-K4L-R-gs-rw-fc-w200-t4-p4: unbounded, serial.
- Every arm is paired per case with `PERC-emp:` on the same player. The perfect-sight column pairs with the player
  without PERC.

(tables filled from bot/noise/report.py at the end of each wave)

## 2. Diagnostics

- **Raw perceived units vs truth** (60 game-seats, cases 1000–1029; `bot/noise/tune.py`):
  - recall .69, i.e. 1.6 missing per poll, mostly swarm bodies;
  - 0.10 phantoms per poll;
  - 2% wrong body.
- **Opponent elixir in the K4L root** (bel1): mean error +1.7–1.9 vs R3a, −0.3 to −1.5 vs v1; mean |error|
  1.8–2.5.
- **Oracle decomposition** (orc1, 28 games, 3,183 K4L decisions). Agreement with the true-sight twin's action
  (base 61.9%):
  - true units +5.5 pp;
  - true opponent elixir +1.1 pp;
  - true opponent belief sample +1.9 pp;
  - both +16.4 pp.

## 3. Proposed hooks for the LIVE LEAD

(see end of run)

## 4. Fresh bank

Not yet pre-registered.
