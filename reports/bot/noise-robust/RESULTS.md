# Noise-robust decisions: results (bot lead worker, exploration)

Status: IN PROGRESS (r4: revealed-set fix screened; fresh bank section 6 pre-registered 23:10:27Z). Numbers are from completed or interim screens, each labelled with its n. Design: DESIGN.md.
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

## 4b. Fresh-bank verdict (computed by the bot lead at 2026-10-15T20:31Z; the worker was cut off by a T3 restart)

Data: 127x03:/mpac/sdicks02/jobs/clasher/bot-noise/fb1/{a,b,d}, cases 0–599 vs R3a and v1, 4,800 games, 0 errors,
0 duplicates. Bootstrap: 4,000 resamples, seed 0, paired by (opponent, index), as pre-registered.

| comparison | pooled (R3a + v1) | R3a | v1 |
|---|---|---|---|
| **noisy (sr1u50) C − B, primary** | **+0.015 [−0.013, +0.042]** | +0.033 [−0.008, +0.075] | −0.003 [−0.038, +0.032] |
| perfect sight C − B | +0.008 [−0.013, +0.028] | 0.000 [−0.035, +0.033] | +0.015 [−0.008, +0.038] |

Win rates (n = 600 each): noisy B 0.630 / 0.880, noisy C 0.663 / 0.877; perfect sight B 0.832 / 0.945, C 0.832 / 0.960.

**Verdict: NOT CONFIRMED.** The primary CI includes 0, so LIVEMR-K2-D is not adopted and the timing run is moot.

**Noise gap of the live search bot on this unselected bank:** PERC-emp-sr1u50:K1 − K1 = **−0.202 [−0.245, −0.162]** vs
R3a and **−0.065 [−0.095, −0.035]** vs v1. This is the best estimate of what deployed perception costs K4L.

## 5. Evidence-ranked opponent revealed set (r3/r4)

**Problem** (aud1, HEADLINE 0–99, 194 games): the deployed translator's opponent card set is first-come, the first
8 distinct cards of accepted plays. Under sr1u50 it holds a card the opponent never played in 164/194 games. A true
card is then locked out (its plays and units are dropped) in 124/194 games.

**Fix:** bot/noise/livefix/revealed.py `RevealedSet`. It is one object for play acceptance and the board sanitizer,
and it evicts weakly evidenced cards. Proposed bot/live patch: reports/bot/noise-robust/revealed-set.patch.

### 5a. Screen scr1 (K4L twin `LIVED-K4L-R-gs-rw-fc`)

HEADLINE cases 0–299 × R3a/v1; 3,000 games, 0 errors. Each arm is paired with the baseline
`AUD:PERC-emp-sr1u50` by (opponent, index): 95% bootstrap, 4000 resamples, seed 0. The arms ran r3's code (see 5d).

| arm − baseline | R3a (n=300) | v1 (n=300) | pooled (n=600) |
|---|---|---|---|
| **fix** PERCRe2b10 | +0.013 [−0.017, +0.047] | +0.030 [+0.000, +0.060] | **+0.022 [+0.000, +0.043]** |
| oracle revealed set (diagnostic, reads truth) | +0.020 [−0.040, +0.080] | +0.043 [−0.003, +0.090] | +0.032 [−0.005, +0.070] |
| reseeded baseline PERCs1 (noise-only control) | +0.007 [−0.057, +0.077] | −0.013 [−0.063, +0.037] | −0.003 [−0.043, +0.037] |
| perfect sight | +0.203 [+0.143, +0.267] | +0.083 [+0.040, +0.130] | +0.143 [+0.107, +0.182] |

Mean score of the baseline: 0.617 (R3a), 0.857 (v1).

**Translator audit per game** (baseline → fix):
- games with a wrong card in the final set: R3a 0.87 → 0.76, v1 0.78 → 0.55;
- true opponent unit-records dropped by the sanitizer: R3a 17 → 1, v1 40 → 2;
- true cards missing from the final set: R3a 0.67 → 0.44, v1 0.97 → 0.62.

The oracle revealed set is worth only +0.032 of the +0.143 perfect-sight gap, so the lock-out is a minor part of
the noise gap on this screen. The fix recovers about 2/3 of the oracle's value.

### 5b. Clean-channel no-op check (floorchk)

Setup: `-xunits-xev-xhud`, cases 0–14 × R3a/v1. Fix vs baseline: **30/30 identical command hashes**, Δ 0.000.

### 5c. Fast tier (scr1f, `LIVE-fast-it5s2`)

HEADLINE cases 0–299 × R3a/v1: 0–149 on 03 and 150–299 on 04 (04 dir scr1f-hi04), 2,400 games, 0 errors. The 115
overlapping games (03 ran slightly past 149) have identical command hashes and scores on both hosts. Same pairing
and bootstrap as 5a.

| arm − baseline | R3a (n=300) | v1 (n=300) | pooled (n=600) |
|---|---|---|---|
| **fix** PERCRe2b10 | +0.010 [−0.020, +0.043] | +0.020 [−0.010, +0.053] | **+0.015 [−0.007, +0.037]** |
| oracle revealed set | +0.010 [−0.047, +0.063] | +0.027 [−0.020, +0.073] | +0.018 [−0.018, +0.055] |
| perfect sight | +0.080 [+0.020, +0.140] | +0.073 [+0.023, +0.123] | +0.077 [+0.037, +0.115] |

Mean score of the baseline: 0.580 (R3a), 0.810 (v1).

**Translator audit** (baseline → fix):
- true opponent unit-records dropped: R3a 23 → 1, v1 49 → 2 per game;
- games with a wrong card: R3a 0.87 → 0.72, v1 0.79 → 0.51.

### 5d. Defect fixed after the screen (r4)

An eviction rebuilt the opponent mirror up to the record tick. A lagged opponent event later in the same record
then raised 'public time moved backwards'. PercPlayer turned that into a WAIT and lost the record's remaining
events. A live session would have got the exception. Fix: rebuild up to the stream guard's time. Regression tests
fail on the old code and pass on the fix. The fresh bank (section 6) runs the fixed code.

## 6. Fresh bank for the revealed-set fix (PRE-REGISTERED 2026-10-15T23:10:27Z, before any game)

**Bank and stats.**
- BASE = **4405930208510496**, from `int.from_bytes(os.urandom(6), 'big') << 4`, drawn 2026-10-15T23:10:27Z. It is
  not 919328127031168 (section 4).
- Cases: x4s_setup(i, BASE), i = 0..599, vs R3a and vs v1, through bot/noise/run.py on the ours engine.
- Noise: `PERC-emp-sr1u50`, stats bot/live/empirical-val-r1u50.json, sha256
  c84464ba28b5504cb28c9f3bd536b17792656c5677b9c6fd506ee7d9291442cf.
- Runtime pins: r1-total.

**Code** (main at this commit; sha256):

| file | sha256 |
|---|---|
| bot/noise/livefix/revealed.py | 63e2277a2ebff25c3363833a3d517b2f094d428f6df6ae69029ba250f5fd54dc |
| bot/noise/livefix/resync.py | 2e6a697a895d7621fe4a94736199b5eb7c2167d620657191daa0cfeca34aed14 |
| bot/noise/livefix/translate.py | c071f732e433ac088b4cc9eeceb5fcefca6a14e63d1fce530a7cef968d4c5e75 |
| bot/noise/revfix.py | b2edfe8a03227c2cf5927e4304670e0f432db6a216784749ee42f86f84039f2e |
| bot/noise/audit.py | dc3ce86d67d872d82f8964a129e7f856d9857f45564fadc89983d65fcd08af52 |
| bot/live/perc.py | 6e1656f1… |
| bot/live/empirical.py | 94df10a8… |
| bot/live/translate.py | 5361deb0… |
| bot/live/resync.py | 77e177f8… |
| proposal patch reports/bot/noise-robust/revealed-set.patch | 90835df8a1e3cdb6250bf1c61b20c1142653946f8392384b6c72830299f7653a |

**Arms** (same noise stream, same player):
- **F** = `AUD:PERCRe2b10-emp-sr1u50:LIVED-K4L-R-gs-rw-fc` (the fix);
- **B** = `AUD:PERC-emp-sr1u50:LIVED-K4L-R-gs-rw-fc` (the deployed translator).

AUD is a read-only audit wrapper.

**Decision rule.**
1. **Primary:** the pooled Δ = mean score(F) − score(B) over R3a + v1, 600 cases each, paired by (opponent, index),
   with a 95% bootstrap CI (4000 resamples, seed 0; bot/noise/report.py pooled row).
   - **CONFIRMED** iff the CI lower bound > 0. Otherwise NOT CONFIRMED.
2. **Also reported:** Δ vs R3a alone, with its CI (LIVE LEAD requirement d), and Δ vs v1 alone. Neither is the
   claim test.
3. **Also reported:** perc_errors per arm (it must be 0 for F), evictions, and dropped true unit-records.

**Hosts:** cases 0–439 run on 03 (80 workers), 440–599 on 04 (`bot/exit/cpu_job.sh 30`). The results are merged by
(arm, opponent, index).
