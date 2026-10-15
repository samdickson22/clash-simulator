# LIVE perception round 2 (exploration tier), RESULTS

Owner: `live-perc-r2-owner-r1` (parent: LIVE LEAD), 2026-10-15. **Final.** Log: [PROGRESS-R2.md](PROGRESS-R2.md). Round 1: [RESULTS.md](RESULTS.md).
Exploration tier: no preregistration; thresholds, filters and epochs were chosen on validation (even half where stated).
Every number is on the **validation split** (64 matches, registered split sha `3edbd25b…`). **Heldout was never
opened**: every loader goes through `live/perception/common.HeldoutGuard`, and `retruth.py`/the fits refuse non-validation dumps.
Renderer domain only; the official-client domain gap is still unmeasured.

**Metric:** Δ win rate of `PERC-emp…` (empirical noise fitted on val) vs perfect sight. Fast tier it5s2, our engine, v1 + R3a × 300.

## TL;DR

1. **No measurable win-rate gain from round 2.**
   - The LEAD's sim: 2,400 games, 0 errors; [ABLATION.md](ABLATION.md) Follow-up 2.
   - Every round-2 decode and model contrast is within noise of the deployed round-1 model at threshold .5.
   - **The deployed perception stays round 1 at `unit_threshold=.5`, with no filter** (LEAD decision). That threshold
     change is round 2's one shipped win: +0.02/+0.02 vs .4 in the LEAD's threshold test.
2. **The phantom proxy over-predicted.**
   - It forecast +.017 (filter on r1) and +.022 (r2 + filter) pooled. The sim measured −0.050/+0.020 and −0.047/−0.003
     (R3a/v1).
   - The proxy priced phantoms by rate only. The filter removed the near-harmless near-duplicate phantoms, and the ones
     it left are farther from real units (median 0.22 → 1.31 tiles). It also raised wrong-card detections from 3.9% to
     6.0%. See [Why the proxy missed](#why-the-proxy-missed).
3. **The retrain (`ft-r3b`) didn't move the unit precision/recall frontier.** At a plain threshold it ties round 1.
4. **What r2 is good for:** groundwork.
   - Royal Ghost detection: recall .78 vs .16, under all-Ghost truth.
   - Spell-effect detections; opponent spells caught .61 vs .50.
   - A switchable count head.
   - `unit_filter.py`, available but off.
   - Fixed tooling: v2 export/eval, `NUMPY_MADVISE_HUGEPAGE=0`, the common-truth re-scoring.

## Diagnosis (round-1 val dump, deployed stack)

Scripts are in `live/perception/r2/`; outputs in `JOB/diag/`.

**Opponent spells** (`diag_spells.py`, 353 events):
- 50% caught (≤1 s, right card);
- **32% had head evidence below the .6 threshold** (spread evenly over .2–.6);
- 9% had no peak, 6% were late, 1% were the wrong card.

So it's a discrimination problem, not a tracker one.

**Units** (`diag_units.py`, owner-only, ≤1 tile, thr .4; 73k misses, recall .811):
- **51% merged same-card peaks**, 21% displaced 1–2 tiles, 23% below threshold, 5% nothing;
- SkeletonArmy alone is 21% of all misses;
- recall is .85 with no same-card neighbour within 1 tile, .54 in crowds.

**Phantom units** (`diag_fp.py`, thr .4, .38/frame):
- 44% displaced 1–2 tiles from a true unit, **33% duplicate splits** next to a matched detection;
- 16% far, 4% owner flips, 3% ahead of deploy, 1% lingering after death.

**Royal Ghost** (train rich snapshots, 4,613 samples):
- stationary on its target after deploy → visible 87%;
- moving → visible 27%;
- deploying → always invisible.

## What was trained: ft-r3b (`live/perception/finetune3.py`, live-dense-v2)

- **Init:** ft-r2/final (`cba64d2a…`).
- **Run:** ft-r3 epoch 2 → ft-r3b, 33,000 joint steps on 127x01 A6000, ~3.2 h, ~2.6–3.4 steps/s.
- **Labels:** `dense_labels.py --r2`.
- **Changes vs round 1:**
  1. **Effect identities** `fx:<spell>` (12 channels): spell areas and projectiles are frame-level positives (never units;
     `dec['effects']`, and they join the tracker's vote stream).
  2. **Royal Ghost positives** while stationary after deploy; ignore otherwise.
  3. **Count head** in the previously unused `body_box[2:4]`: bodies per half-tile cell per owner. Decode: window-sum
     extras for multi-body cards only (`common.MULTI_BODY`), flagged `counted`.
  4. **Event loss reaches the backbone** through the newest 4 frames of each window (round 1: frozen). Spell endpoint
     share .5 → .6.
- **Lost restarts.** ft-r3 was restarted twice:
  - the auto step estimate came from warmup;
  - **numpy's transparent-huge-page `madvise` stalled every multi-MB allocation on loaded 01 for 2–47 s**.
    `NUMPY_MADVISE_HUGEPAGE=0`, now set in `detach.sh`, fixed it.
  - ft-r3b restarted from ft-r3 epoch 2 with the count loss's empty-cell weight .05 → 1. At .05 the counts were biased
    high next to every body.

### Full validation, frame metrics (`eval_val.py --truth dense --stride 2`, round-1 labels, 53,388 frames)

| metric | r1 ft-r2 (cba64d2a) | **r2 ft-r3b (ea104903)**, no extras | r2 + count extras |
|---|---:|---:|---:|
| units id×owner ≤1 tile, thr .4: P / R | .907 / .774 | .892 / .788 | .870 / .826 |
| same, thr .5 | .955 / .738 | .945 / .750 | .918 / .789 |
| units owner-only ≤1 tile, thr .5: P / R / FP | .984 / .760 / 4,789 | .978 / .776 / 6,819 | .950 / .817 / 16,585 |
| hand accuracy per slot | .9885 | .9887 | |
| elixir MAE | .0643 | .0637 | |

At a plain threshold r2 sits on r1's precision/recall curve (more recall, more phantoms).

### Unit decode selection

Common truth: all-Ghost labels for both dumps (`--ghost-all` + `retruth.py`). The empirical fit's matching is owner-only,
≤1 tile. Proxy = .230·recall − .128·phantoms/frame, linear in the ablation endpoints.
- **Earlier version:** visible-Ghost-only truth charged r2's correct Ghost detections (0.048/frame) as phantoms and never
  charged r1's blind spot. It was replaced before the sim.
- **Filter grid:** `r2/filter_sweep.py`, 100 + 29 configs. Selected on the even half; the odd half confirms.

| arm (sim name) | decode | recall | phantoms/frame ours + opp | Ghost recall | proxy all (odd) |
|---|---|---:|---:|---:|---:|
| r1 deployed before today | thr .4 | .811¹ | .381¹ | — | .138¹ |
| `PERC-emp-sr1u50` (new default) | r1, thr .5 | .750 | .091 | .16 | .161 |
| `PERC-emp-sr1f` | r1 + filter | .804 | .059 | .42 | .178 (.177) |
| `PERC-emp-sr2u55` | r2, thr .55 (r2's plain best) | .742 | .069 | .59 | .162 |
| **`PERC-emp-r2`** | **r2 + filter, no count extras** | **.827** | **.061** | **.78** | **.183 (.181)** |

¹ Round-1 truth without Ghost.

Count extras lower the proxy at every threshold (`diag/unit-sweep-r2.json`). Per-group thresholds (single-body vs multi-body
cards) gave nothing (`diag/unit-sweep-r1-group.json`).

**Per-card recall / phantoms per 1,000 frames** (common truth; `diag/pcg-*.json`):

| card | n | r1 thr .5 | r1 + filter | r2 + filter |
|---|---:|---|---|---|
| SkeletonArmy | 30646 | 0.48 / 4.6 | 0.50 / 2.9 | 0.55 / 3.0 |
| GoblinGang | 24767 | 0.57 / 7.1 | 0.64 / 1.8 | 0.67 / 1.7 |
| Minions | 24558 | 0.67 / 4.4 | 0.71 / 1.6 | 0.75 / 1.8 |
| Goblins | 24430 | 0.68 / 4.3 | 0.75 / 3.4 | 0.78 / 3.8 |
| Skeletons | 14082 | 0.65 / 4.1 | 0.72 / 3.5 | 0.76 / 4.2 |
| Bats | 17360 | 0.79 / 1.5 | 0.80 / 3.0 | 0.82 / 2.6 |
| MinionHorde | 9202 | 0.62 / 5.6 | 0.68 / 0.3 | 0.72 / 0.5 |
| Wallbreakers | 8748 | 0.66 / 1.7 | 0.72 / 2.5 | 0.71 / 1.9 |
| GoblinBarrel | 6110 | 0.47 / 2.4 | 0.53 / 1.3 | 0.66 / 1.6 |
| Archers | 18420 | 0.80 / 1.2 | 0.82 / 1.0 | 0.83 / 1.2 |
| Knight | 8360 | 0.83 / 2.6 | 0.93 / 1.3 | 0.92 / 0.9 |
| HogRider | 7101 | 0.78 / 1.8 | 0.88 / 0.8 | 0.88 / 1.0 |
| Ghost | 6908 | 0.16 / 0.0 | 0.42 / 0.0 | 0.78 / 3.5 |

Swarms remain the weak point: SkeletonArmy is .55.

### Play events (deployed body-fused tracker thr .6 / hold 500, `diag_spells.py`, ≤1 s, ≤2.5 tiles)

| | r1 | r2 |
|---|---|---|
| opponent spells caught / 353 | 178 (.50) | **214 (.61)** |
| spells below threshold / no peak / late | 112 / 33 / 22 | 103 / 20 / 9 |
| opponent troops caught / 1018 | 899 | 928 |
| emitted opp spell FPs / troop FPs | 31 / 30 | 37 / 19 |
| fitted event recall (≤1.5 s) / spurious per min | .834 / .59 | .864 / .53 |

The `fx:` effect votes for sub-threshold spell tracks (`EventTracker(effect_cross=…)`) are implemented but not tuned or
deployed. Spells are worth ~0 in win rate (ABLATION.md). Round-2 event gains therefore don't show in the sim either.

## Win rate (LEAD sim on 127x04, 2,400 games, 0 errors, code f0eabd1d; ABLATION.md Follow-up 2)

Fast tier it5s2, our engine, v1 + R3a × 300 cases, same base. Perfect sight = the earlier `LIVE-fast-it5s2` rows.

| arm | proxy | vs perfect: R3a | vs perfect: v1 | vs sr1u50: R3a | vs sr1u50: v1 |
|---|---:|---|---|---|---|
| `sr1u50` (deployed: r1, thr .5) | .161 | −0.080 [−0.137, −0.020] | −0.073 [−0.123, −0.023] | — | — |
| `sr1f` (r1 + filter) | .178 | −0.130 [−0.190, −0.073] | −0.053 [−0.107, +0.000] | −0.050 [−0.110, +0.010] | +0.020 [−0.037, +0.077] |
| `sr2u55` (r2, thr .55) | .162 | −0.090 [−0.153, −0.027] | −0.083 [−0.130, −0.037] | −0.010 [−0.070, +0.050] | −0.010 [−0.063, +0.043] |
| `r2` (r2 + filter) | .183 | −0.127 [−0.187, −0.067] | −0.077 [−0.127, −0.027] | −0.047 [−0.107, +0.013] | −0.003 [−0.057, +0.053] |

r2 vs sr1f: R3a +0.003 [−0.063, +0.067], v1 −0.023 [−0.077, +0.030].

**Reading.**
- Nothing beats `sr1u50` measurably. Both filter arms lean negative against R3a.
- At 300 cases per opponent the 95% CI half-width is about ±0.06. The proxy's forecast gains (+.02) were below what this
  run can resolve either way.
- So this is "no gain shown", not "proven harmful". It is enough to keep the simpler deployed setting.

## Why the proxy missed

The proxy (`r2/unit_sweep.py`) was .230·recall − .128·phantoms/frame. It was linear in two ablation endpoints (remove
all misses / all phantoms), and it predicted the .4 → .5 threshold step well (+.023 forecast, +.02/+.02 measured).

For the filter it predicted +.017, while the sim gave −0.050/+0.020. The sim doesn't see the filter itself. It replays
only the fitted per-component statistics, so the miss must come from components the proxy left out.

| fitted component (`empirical-val-*.json`) | r1u50 | r1f | r2u55 | r2 |
|---|---:|---:|---:|---:|
| recall (proxy term) | .750 | .804 | .742 | .827 |
| phantoms / frame (proxy term) | .091 | .059 | .069 | .061 |
| **P(hit \| miss)**: miss persistence | **.288** | **.288** | .297 | .320 |
| P(hit \| hit): mean hit run, frames | .906: 10.6 | .932: 14.7 | .899: 9.9 | .935: 15.5 |
| right card when detected | .961 | **.940** | .969 | **.944** |
| position error > .5 tile | 1.6% | 2.8% | 1.2% | 1.7% |
| **phantom distance to a true unit, median** | **0.22 tiles** | **1.31** | 0.22 | **1.39** |

1. **Miss persistence is not the cause.** P(hit | miss) is identical with and without the filter (.288 for r1), so mean
   miss runs are unchanged (3.5 frames). The filter only lengthens hit runs.
   - The sim also draws phantom units independently every frame (Poisson). So it **cannot** price longer-lived phantoms,
     even though hysteresis does make real phantoms stickier.
   - Phantom persistence may well matter live, but it isn't what this sim measured.
2. **Phantom placement.**
   - At a plain threshold, most phantoms are near-duplicates sitting on a real unit (median 0.22 tiles). In the sim they
     are drawn near a true unit, close enough to barely change the board.
   - The filter's owner-level NMS removed exactly those. The phantoms left are 1.3 tiles away: fewer per frame, but each
     one more misleading.
   - The proxy priced every phantom the same.
3. **Card confusion.** Hysteresis keeps detections down to score .25. These carry more wrong cards: 3.9% → 6.0% of
   detections, +54% relative. That is a component the ablation never isolated (no `xconf` arm was run).
4. **Noise.** The forecast is +.017 pooled; the measured value is −.015 pooled (R3a and v1 averaged). The pooled paired SE
   is about .021 (CI half-width ±.06 per opponent), so the gap is about 1.5 SE. The proxy is contradicted at the margin,
   not strongly refuted.

**What a better proxy needs:**
- **Phantoms weighted by distance to the nearest true unit**, near-duplicate vs displaced vs far. The ablation could
  split `xfp` into near-phantom and far-phantom arms.
- **A card-confusion term.** Run the existing `-xconf` arm, and price wrong-card detections next to misses.
- **Position error**, plus per-card or per-role weights: a missed or mis-placed SkeletonArmy is not a missed Knight.
- **Temporal structure in the sim itself.** Fit phantom persistence (a Markov chain per phantom track) and hit/miss
  persistence per card. Then filters that trade rate for persistence are priced the way live play would price them.
- **More games per arm**, or a pooled multi-arm design. Resolving ±0.02 pooled needs roughly 4–5× the 300 cases per opponent.

## Deployment

- **Deployed (LEAD decision, 2026-10-15):** `LivePerception(export-final)` (round 1, ft-r2 `cba64d2a…`) with
  `unit_threshold=.5` (the default in `infer.py`). No unit filter. Count extras don't apply to round 1.
- **Available, off:**
  - `unit_filter=dict(hi=.45, lo=.25, nms=.6)`;
  - the round-2 export `JOB/export-r2` (Royal Ghost, spell effects in the tracker votes, `count_extras=` switch);
  - `EventTracker(effect_cross=…)`.
- **Latency** (export-r2, `latency.json`):
  - A6000: frame 1.9 ms, event head 2.0 ms;
  - 01 Threadripper, 4 threads: frame 60 ms, event head 64 ms;
  - decode + record 8 ms.
  - Parity: max abs error 0.0, 64/64 identical decisions.

## Files

| artifact | path (127x01 and 127x05), `JOB = /mpac/sdicks02/jobs/clasher/live-perc-r2-20261015` | sha256 |
|---|---|---|
| ft-r3b final (live-dense-v2) | `JOB/ft-r3b/final.pt` | `ea1049034a41c76505315c753680b0c68ab054d1ef1687c5cb9fa8de9dd42d01` |
| TorchScript frame / event | `JOB/export-r2/{frame,event}.pt` | `8bb9bab39c3485d994ab950a195d234205a0e7ff01bb03f9dea40f64920bf8b5` / `26115c7a59d593ea5148613c567789aa9ab892bf5b13e4b767593e6f3b38e1b3` |
| ft-r3 epochs 1–2 (first attempt) | `JOB/ft-r3/` | |
| labels | `JOB/labels-r2` (01: train+val), `JOB/labels-ghostall` (01: val only, evaluation truth) | |
| full-val dumps | `JOB/dump-r2` (visible-Ghost truth), `JOB/dump-r1-gall`, `JOB/dump-r2-gall` (common truth) | |
| evals | `JOB/eval/{r2-dense-s2,r2-dense-s2-nocount,ev-r2-s2}` | |
| diagnosis / sweeps | `JOB/diag/*.json` | |
| fitted noise | `bot/live/empirical-val-{r1u50,r1f,r2u55,r2}.json` (r1u55 is the earlier visible-Ghost-truth fit, superseded) | |

## Reproduce

```bash
# 127x01; P = <checkout>/live/perception; NUMPY_MADVISE_HUGEPAGE=0 (detach.sh sets it)
python $P/dense_labels.py --r2 --out $JOB/labels-r2 --workers 12
python $P/finetune3.py --init <ft-r2>/final.pt --labels $JOB/labels-r2 --out $JOB/ft-r3 --hours 4.2 --max-steps 36000   # epoch 2 ->
python $P/finetune3.py --init $JOB/ft-r3/epoch-2.pt --labels $JOB/labels-r2 --out $JOB/ft-r3b --hours 4 --max-steps 33000
$P/r2/post_train.sh $JOB/ft-r3b/final.pt r2              # export + eval_val (+/- counts) + eval_events + 3-shard GPU dump
python $P/dense_labels.py --r2 --ghost-all --splits validation --out $JOB/labels-ghostall
python $P/r2/retruth.py <r1 dump> $JOB/dump-r1-gall $JOB/labels-ghostall    # and dump-r2 -> dump-r2-gall
python live/perception/r2/filter_sweep.py $JOB/dump-r2-gall OUT.json [--grid edge]
python -m bot.live.empirical fit --dump $JOB/dump-r2-gall --out bot/live/empirical-val-r2.json --fusion '<LIVE_DEFAULT>' \
    --vocab $JOB/export-r2/vocab.json --unit-filter '{"hi": 0.45, "lo": 0.25, "nms": 0.6}' --no-count-extras
```

## Caveats

- **Renderer domain only.** The official-client gap is unmeasured.
- **Selection on validation.** The filter was picked on the even half; the odd half agrees within .002 proxy. The proxy
  agreed with the u50 test but over-predicted the filter (see Why the proxy missed).
- **The sim's empirical noise is per card plus a Markov hit model.** It doesn't reproduce the filter's exact temporal
  structure beyond the fitted P(hit | hit/miss).
- **The Ghost visibility rule is a heuristic** (87% / 27% from rich snapshots). An official-client capture should
  re-check it.
