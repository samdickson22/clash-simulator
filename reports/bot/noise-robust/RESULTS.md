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

## 4. Fresh bank (PRE-REGISTERED 2026-10-15T18:14:25Z, before any game)

**Bank and stats.**
- BASE = **919328127031168**, from `int.from_bytes(os.urandom(6), 'big') << 4`, drawn 2026-10-15T18:14:25Z.
- Cases: x4s_setup(i, BASE), i = 0..599, vs R3a and vs v1. Engine: ours (bot/noise/run.py, the HEADLINE protocol).
- Noise: **`PERC-emp-sr1u50`**, the deployed reference per the LIVE LEAD 16:39Z.
  - stats bot/live/empirical-val-r1u50.json, sha256 c84464ba28b5504cb28c9f3bd536b17792656c5677b9c6fd506ee7d9291442cf
  - perc.py 6e1656f1…, empirical.py 94df10a8… (main 5c1d37e7)
  - runtime pins r1-total

**Arms.** These are deterministic twins: no deadline, so every search completes, as on the Mac, where the 200 ms
deadline does not bind for K4L.
- **C** = `LIVEMR-K2-D`: K4L-R-gs-rw with K=2 learned samples, sample 1 from its own determinized root (an
  independent opponent belief sample).
- **B** = `LIVEMR-K1`: K4L-R-gs-rw, bit-identical to LIVED-K4L-R-gs-rw-fc on the screen.
- The pooled live form `LIVE-MRK<n>-D-w<ms>-t4-p4` is bit-identical to its serial twin when the deadline does not
  bind (command hash 4a18597e…, K3-D, case 1500).
- **Noisy:** PERC-emp-sr1u50:C vs PERC-emp-sr1u50:B.
- **Perfect sight:** C vs B.

**Why K2-D.** It is the only screen variant with a positive point estimate on every noise version and opponent:

| screen | Δ(C−B) |
|---|---|
| PERC-emp R3a | +0.076 [−0.015, +0.168] (n=131) |
| sr1u50 R3a | +0.027 [−0.042, +0.092] (n=261) |
| sr1u50 v1 | +0.014 [−0.041, +0.064] (n=295) |
| PERC-emp v1 | +0.000 (n=170) |

It was selected among ~6 multi-root variants and ~5 filters, so the screen carries a winner's curse.

**Decision rule.**
1. **Primary:** the pooled (R3a + v1, 1,200 paired cases) Δ = mean score(C) − score(B) under PERC-emp-sr1u50,
   paired by (opponent, index), with a 95% bootstrap CI (4000 resamples, seed 0).
   - **CONFIRMED** iff the CI lower bound > 0. Otherwise NOT CONFIRMED (null or negative).
   - Δ vs R3a alone (the coordinator's primary metric) is reported with its CI, but is not the claim test.
2. **Perfect sight:** the pooled Δ(C−B) is reported with its CI. Adoption needs a point estimate ≥ −0.01.
3. **Timing** (separate run): `LIVE-MRK2-D-w200-t4-p4` and `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` on quiet pinned 4-core
   groups on 03 (SMT siblings idle). Adoption needs fleet p99 ≤ 400 ms. p50/p95/p99, the default share and the Mac
   projection (÷2.8) are reported.
4. **Also reported from the same games:** the K4L gap on the fresh bank, PERC-emp-sr1u50:B vs B.
