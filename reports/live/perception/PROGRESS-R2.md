# LIVE perception round 2 (exploration tier), PROGRESS

Owner: `live-perc-r2-owner-r1` (parent: LIVE LEAD). Started 2026-10-15 10:28Z. Metric: Δ win rate of PERC-emp vs perfect
sight (fast tier, it5s2, v1 + R3a × 300, our engine); round 1 = R3a −0.137, v1 −0.113.
Code: `live/perception/` on 05 (`live/lead` worktree), synced copy on 01 at `/mpac/sdicks02/repos/clasher-live-r2/`.
Job dir (01 and 05): `/mpac/sdicks02/jobs/clasher/live-perc-r2-20261015/`. **Heldout never opened** (HeldoutGuard in every loader).

## GPU grant
127x01 A6000 from 2026-10-15T10:38:03Z, up to ~20:30Z. ≤16 loader cores, nice. **Tell the LIVE LEAD when done.**

## Log
- 10:28Z start; ff `live/lead` to origin/main (2d060b451).
- Diagnosis (CPU, 05) on the round-1 val dump: `diag/spells.json`, `diag/units.json` (scripts `live/perception/r2/diag_*.py`).
  Spells: 178/353 caught; 32% head evidence below thr .6, 9% no peak, 6% late, 1% wrong card. Units: 51% of misses merged
  peaks, 21% displaced 1-2 tiles, 23% below thr, 5% nothing; SkeletonArmy = 21% of all misses.
- Royal Ghost: train rich snapshots (4,613): stationary-on-target after deploy = visible 87%, moving 27%, deploying 0%.
- Ablation arms `PERC-emp-x<part>` (bot/live/perc.py, empirical.py) + test; command sent to the LEAD.
- 10:3xZ labels-r2 (`dense_labels.py --r2`: fx:<spell> effect identities, stationary-Ghost positives), 577 matches, 01.
- **10:41Z ft-r3 RUNNING** on 01 (`finetune3.py`, python main PID 3037297, 4.2 h, ~1.27 steps/s, est 18k steps).
  Init ft-r2/final (cba64d2a). Effects + count head (body_box[2:4]) + Ghost + event grad into backbone (last 4 frames)
  + spell share .6. 05 mirror loop PID 3093311 (`mirror-ft3.sh`, every 15 min).
- 10:45Z restarted ft-r3 with `--max-steps 36000`: the step-150 rate estimate was taken during warmup (1.27 st/s vs 3.4 real),
  so the cosine would have ended after ~1.5 h.
- 10:58Z restarted again: loaders stalled (GPU 0%). Cause: on loaded 01 numpy's THP madvise sends every multi-MB alloc into
  direct compaction (18 MB fill 7-47 s). `NUMPY_MADVISE_HUGEPAGE=0` (now in detach.sh) -> 0.02 s. Told the LEAD (bot lead's
  numpy jobs on 01 likely affected).
- 11:04Z ft-r3 epoch 1: count decode recall .76 -> .89 but precision .33. `r2/decode_grid.py` (6 val matches, 180 frames):
  every count decode over-detects; the count map is biased high on empty cells (their loss weight was 0.05).
- **11:11Z ft-r3b RUNNING** (PID 3200394): init ft-r3/epoch-2.pt, count loss with weight 1 on empty cells, 33k steps,
  4 h cap. 05 mirror PID 2284697 now mirrors ft-r3b. ft-r3 epoch-1/2 kept (01 + 05).
- 11:52Z decode grid on ft-r3b epoch 6 (6 val matches, 180 frames, id x owner <= 1 tile, thr .4): peaks only P/R/F1
  .871/.767/.815 (swarm R .684); **window-sum count decode (r1, cmin .9, floor .2, MULTI_BODY cards only) .830/.816/.823
  (swarm R .782)**. Now the v2 default in `common._count_extras` (verified identical to the grid variant).
- Pipeline smoke on CPU with ft-r3b epoch 1: export (parity 0.0), LivePerception, 1-match dump with labels-r2 (effects in
  the tracker vote stream, Ghost predicted), eval_val/export now accept live-dense-v2 (they gated on v1: would have
  scored v2 as T7-format; fixed).
- 12:2xZ LEAD ablation (ABLATION.md): units are the lever (xunits +.06/.07; misses +.04/.05, phantoms +.02/+.08),
  spells ~0. Re-prioritised: units recall AND phantoms; no more GPU on spells.
- `r2/unit_sweep.py` (re-threshold the dump's >= .25 detections, exact empirical.fit matching; proxy from the ablation
  endpoints: 0.230*recall - 0.128*phantoms/frame). Round-1 dump: thr .4 recall .811 / phantoms .38 per frame (proxy .138);
  thr .5 .760 / .110 (.161); .55 .730 / .056 (.161). Per-group (single vs multi-body) thresholds: no gain.
- Fitted `bot/live/empirical-val-r1u50.json`, `-r1u55.json` (round-1 model, units re-thresholded); `empirical.fit
  --unit-threshold/--no-count-extras`; arm token `-s<name>`. LEAD runs PERC-emp (fresh) vs -sr1u50/-sr1u55 on 03 ~13:45Z
  (`/mpac/sdicks02/jobs/clasher/live-perc-thr-ours`).
- `r2/diag_fp.py` round-1 phantoms (thr .4): displaced 1-2 tiles 44%, duplicate split 33%, far 16%, owner flip 4%,
  early 3%, lingering 1%: mostly crowd localisation.
- LEAD threshold test (1,800 games): u50 vs fresh PERC-emp +.020/+.020 (n.s., matches proxy), u55 null/negative ->
  **LivePerception unit_threshold default .4 -> .5** (infer.py).
- **14:23Z ft-r3b done** (33k steps, final sha ea104903…). 14:25-14:41Z post_train.sh on GPU: export-r2 (parity 0.0),
  eval_val +/- counts, eval_events, 3-shard GPU dump (`dump-r2`). Copied to 05.
- Readout: r2 at plain thresholds sits on r1's P/R curve (proxy best .1585 vs r1 .161); count extras lower the proxy at
  every threshold. **GPU released 14:42Z** (told the LEAD; no processes of ours left on 01).
- `unit_filter.py` (hysteresis + owner-level NMS; also in LivePerception(unit_filter=) and empirical.fit --unit-filter),
  `r2/filter_sweep.py` (even-half selection): +.012-.017 proxy on both models.
- LEAD committed round-2 code at ba4e560e.
- **Ghost truth bias found before the sim**: visible-Ghost-only truth charged r2's correct Ghost detections (0.048 of
  0.094 phantoms/frame) and never charged r1's blind spot. Sim held. `dense_labels.py --ghost-all` (val, evaluation truth)
  + `r2/retruth.py` (verified identical with the original labels) -> `dump-r1-gall`, `dump-r2-gall`. Filter re-selected
  on even half: hi .45 / lo .25 / nms .6 (both models). Refit r1u50, r1f, r2u55, r2 on the common truth:
  recall/phantoms r1u50 .750/.091, r1f .804/.059, r2u55 .742/.069, **r2 .827/.061** (Ghost recall .16/.42/.59/.78).
  GO sent; LEAD runs the 4-arm sim on 127x04.
- RESULTS-R2.md drafted; win-rate section pending the sim.
- **LEAD sim** (127x04, 2,400 games, 0 errors, code f0eabd1d; ABLATION.md Follow-up 2):
  - vs sr1u50 (R3a / v1): sr1f −.050 / +.020, sr2u55 −.010 / −.010, r2 −.047 / −.003; r2 vs sr1f +.003 / −.023.
  - All within noise (±.06 per opponent).
  - **Decision: deployed perception stays round 1 at unit_threshold .5, no filter.** The filter and the r2 export stay
    available, off.
- The proxy miss, checked from the fitted JSONs:
  - P(hit | miss) is unchanged by the filter (.288 for both r1 fits), so it isn't miss persistence. The sim also draws
    phantoms independently each frame.
  - What the filter did change: surviving phantoms sit farther from real units (median 0.22 → 1.31 tiles), and
    wrong-card detections rose from 3.9% to 6.0%. The proxy priced neither. Write-up: RESULTS-R2 "Why the proxy missed".

## State: DONE (exploration tier, perception round 2)

- No processes of ours are running on 01 or 05. The 05 mirror loop exited after copying ft-r3b/final.pt.
- The GPU was released at 14:42Z.
- Artifacts: `/mpac/sdicks02/jobs/clasher/live-perc-r2-20261015/` on 01 and 05. Labels (`labels-r2`, `labels-ghostall`)
  are on 01 only.
- **Next perception lever (LEAD):** the official-client domain gap (needs emulator frames).
- **Sim work that would make decode tuning measurable:**
  - phantom-distance and card-confusion terms;
  - phantom persistence;
  - more cases per arm.
