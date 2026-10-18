# KV1 results

Preregistration: [KV1-PREREG.md](KV1-PREREG.md). `l16` denotes L16; `acc` denotes the account row.

Readout generated 2026-10-18T09:07:12Z. Reference `res-lb-RF-wintp`; treatment `res-lb-RF-mkv2-wintp`.

**Ship: FAIL.** HPv2 pooled-positive criterion: FAIL; pooled K4CW lower-bound criterion: FAIL; neither-row-below−0.02 criterion: FAIL; pooled Hog/Barrel within-2-SE criterion: PASS.

Gated metrics worse beyond 2 paired SE: none. KV1 permits approximately 2 SE of worsening in Hog-crossing elixir and Barrel answers. The gate uses pooled all-three-opponent Hog elixir mean, share >=6, Cannon+3, and Barrel answer share. SEs retain LP2 paired-game influence definitions; all other standing metrics are descriptive for this preregistration.

## Data integrity

Raw rows: 2400; unique valid rows: 2400; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'l16': 1200, 'acc': 1200}`. Hosts: `{'127x04': 1200, '127x08': 1200}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw`. Completion and rerun history is in the appended run audit.

Exactly 200 paired cases per opponent per level row; 400 pairs per opponent pooled over L16/account. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | HPv2 treatment − reference, 95% CI | All three treatment − reference, 95% CI |
| --- | --- | --- | --- | --- |
| l16 | -0.0300 [-0.1100, +0.0450] (n=200) | -0.0250 [-0.0900, +0.0400] (n=200) | -0.0250 [-0.1050, +0.0600] (n=200) | -0.0267 [-0.0717, +0.0167] (n=600) |
| acc | -0.0350 [-0.1100, +0.0450] (n=200) | +0.0150 [-0.0600, +0.0950] (n=200) | -0.0100 [-0.0700, +0.0500] (n=200) | -0.0100 [-0.0533, +0.0333] (n=600) |
| pooled | -0.0325 [-0.0875, +0.0250] (n=400) | -0.0050 [-0.0575, +0.0450] (n=400) | -0.0175 [-0.0700, +0.0325] (n=400) | -0.0183 [-0.0483, +0.0117] (n=1200) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | HPv2 score | All-three score |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 600 | 0.760 | 0.850 | 0.450 | 0.687 |
| l16 | res-lb-RF-mkv2-wintp | 600 | 0.730 | 0.825 | 0.425 | 0.660 |
| acc | res-lb-RF-wintp | 600 | 0.520 | 0.605 | 0.285 | 0.470 |
| acc | res-lb-RF-mkv2-wintp | 600 | 0.485 | 0.620 | 0.275 | 0.460 |
| pooled | res-lb-RF-wintp | 1200 | 0.640 | 0.728 | 0.367 | 0.578 |
| pooled | res-lb-RF-mkv2-wintp | 1200 | 0.608 | 0.723 | 0.350 | 0.560 |


## Standing play-quality metrics (all three opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 505.2 | 1.500/5.750 | 3.26/3.14 | 0.003 | 0.060 | 0.558 | 0.261 |
| l16 | res-lb-RF-mkv2-wintp | 504.0 | 1.500/5.750 | 3.28/3.18 | 0.003 | 0.055 | 0.559 | 0.253 |
| acc | res-lb-RF-wintp | 498.4 | 1.500/5.500 | 3.27/3.16 | 0.003 | 0.059 | 0.563 | 0.262 |
| acc | res-lb-RF-mkv2-wintp | 507.0 | 1.500/5.500 | 3.27/3.16 | 0.003 | 0.053 | 0.558 | 0.263 |
| pooled | res-lb-RF-wintp | 501.8 | 1.500/5.750 | 3.27/3.14 | 0.003 | 0.060 | 0.560 | 0.262 |
| pooled | res-lb-RF-mkv2-wintp | 505.5 | 1.500/5.500 | 3.28/3.16 | 0.003 | 0.054 | 0.558 | 0.258 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 1172 | 3.127 | 2.964 | 0.033 | 0.305 |
| l16 | res-lb-RF-mkv2-wintp | 1190 | 3.141 | 3.000 | 0.032 | 0.321 |
| acc | res-lb-RF-wintp | 1153 | 3.130 | 2.928 | 0.033 | 0.293 |
| acc | res-lb-RF-mkv2-wintp | 1189 | 3.200 | 3.035 | 0.034 | 0.320 |
| pooled | res-lb-RF-wintp | 2325 | 3.128 | 2.964 | 0.033 | 0.299 |
| pooled | res-lb-RF-mkv2-wintp | 2379 | 3.170 | 3.000 | 0.033 | 0.320 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | Fireball | 1.088 | 653 | 616 | 0.472 |
| l16 | res-lb-RF-wintp | Zap | 5.340 | 3204 | 3186 | 0.584 |
| l16 | res-lb-RF-wintp | ElectroSpirit | 7.585 | 4551 | 4493 | 0.222 |
| l16 | res-lb-RF-mkv2-wintp | Fireball | 1.102 | 661 | 631 | 0.504 |
| l16 | res-lb-RF-mkv2-wintp | Zap | 5.402 | 3241 | 3227 | 0.567 |
| l16 | res-lb-RF-mkv2-wintp | ElectroSpirit | 7.712 | 4627 | 4567 | 0.236 |
| acc | res-lb-RF-wintp | Fireball | 1.067 | 640 | 592 | 0.486 |
| acc | res-lb-RF-wintp | Zap | 5.495 | 3297 | 3280 | 0.516 |
| acc | res-lb-RF-wintp | ElectroSpirit | 7.688 | 4613 | 4556 | 0.218 |
| acc | res-lb-RF-mkv2-wintp | Fireball | 1.112 | 667 | 628 | 0.514 |
| acc | res-lb-RF-mkv2-wintp | Zap | 5.572 | 3343 | 3321 | 0.532 |
| acc | res-lb-RF-mkv2-wintp | ElectroSpirit | 7.932 | 4759 | 4712 | 0.219 |
| pooled | res-lb-RF-wintp | Fireball | 1.077 | 1293 | 1208 | 0.479 |
| pooled | res-lb-RF-wintp | Zap | 5.418 | 6501 | 6466 | 0.550 |
| pooled | res-lb-RF-wintp | ElectroSpirit | 7.637 | 9164 | 9049 | 0.220 |
| pooled | res-lb-RF-mkv2-wintp | Fireball | 1.107 | 1328 | 1259 | 0.509 |
| pooled | res-lb-RF-mkv2-wintp | Zap | 5.487 | 6584 | 6548 | 0.549 |
| pooled | res-lb-RF-mkv2-wintp | ElectroSpirit | 7.822 | 9386 | 9279 | 0.227 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 661 | 81 | 0.123 | 0.091 | 2694 | 0.009 | 0.991 |
| l16 | res-lb-RF-mkv2-wintp | 645 | 85 | 0.132 | 0.091 | 2657 | 0.012 | 0.988 |
| acc | res-lb-RF-wintp | 660 | 80 | 0.121 | 0.102 | 2729 | 0.009 | 0.991 |
| acc | res-lb-RF-mkv2-wintp | 666 | 93 | 0.140 | 0.111 | 2915 | 0.008 | 0.992 |
| pooled | res-lb-RF-wintp | 1321 | 161 | 0.122 | 0.096 | 5423 | 0.009 | 0.991 |
| pooled | res-lb-RF-mkv2-wintp | 1311 | 178 | 0.136 | 0.101 | 5572 | 0.010 | 0.990 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Paired SE | Adverse >2 SE |
| --- | --- | --- | --- | --- | --- |
| hog_elixir_mean | 3.12847 | 3.17049 | 0.04203 | 0.03754 | no |
| hog_elixir_ge6 | 0.03312 | 0.03321 | 0.00009 | 0.00541 | no |
| hog_cannon_and_ge3 | 0.29892 | 0.32030 | 0.02138 | 0.01281 | no |
| barrel_answer_share | 0.12188 | 0.13577 | 0.01390 | 0.01237 | no |


Early wiring checks and command-event fingerprints are recorded in early-wiring.json. The exact staged parser selects kv2 for the treatment and k1a1 for the reference; all complete early pairs have different command-event hashes. START_CONFIG display names are overwritten with the baseline name by configure(), so those names cannot identify the loaded model.

## Analysis artifacts and reproducibility

- l16 hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/hz-l16.json`

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/readout-data.json`

Each hz_report was executed on 127x05 using the Python 3.12 environment and the archived RF1 analysis tree. hz_report.py, scale_report.py, l16_report.py and live_metrics.py are byte-identical to the KV1 launch archive on both study hosts (final-provenance.txt artifacts). Command: `PYTHONPATH=TREE`, `python -m bot.fullpool.hz_report DIR --ref res-lb-RF-wintp --arms TREATMENT --gate TREATMENT --gate-opponent LIVE-K4CW-r16-fp --json OUT`. Normalized inputs preserve the first valid occurrence of each (level row, player, opponent, index). Pooled copies namespace index as `level-row:index` to prevent hz_report from treating the same numeric index in L16/account as a duplicate. Raw rows are retained unchanged.

Computed source SHA256s at readout generation:
```text
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/scale_report.py
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/score_study.py
f044645d93f70ef0ef4e74297f75e008905d7991d29b9f8dc6f24472eb2f3a99  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/render_report.py
```


## Largest standardized metric changes

Descriptive ranking by absolute pooled delta / paired-game SE among the reported ratio metrics (CPU listed separately); no multiplicity adjustment or metric significance claim.

| Metric | Reference | kv2 | Delta | Paired SE | Absolute delta/SE |
| --- | --- | --- | --- | --- | --- |
| ElectroSpirit_plays_per_game | 7.63667 | 7.82167 | 0.18500 | 0.07857 | 2.35 |
| hog_cannon_and_ge3 | 0.29892 | 0.32030 | 0.02138 | 0.01281 | 1.67 |
| Fireball_enemy_in_radius_share | 0.47930 | 0.50913 | 0.02983 | 0.02011 | 1.48 |


## Standing metrics by opponent

These tables retain every hz_report mechanism field. CPU pooled is total own decision CPU / total own decisions; CPU median is the unchanged floor-quantile over per-game CPU/decision. All games ran without a live deadline.

| Row | Opponent | Arm | Games | CPU pooled/median ms | CPU games | Decisions/game | To decision p50/p90 s | To play p50/p90 s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | all three | reference | 600 | 505.2/480.4 | 600 | 140.5 | 0.150/1.150 | 1.500/5.750 |
| l16 | all three | kv2 | 600 | 504.0/489.3 | 600 | 140.1 | 0.150/1.150 | 1.500/5.750 |
| l16 | K4CW-fp | reference | 200 | 545.2/525.9 | 200 | 142.2 | 0.150/0.650 | 1.500/5.500 |
| l16 | K4CW-fp | kv2 | 200 | 538.4/514.0 | 200 | 140.3 | 0.150/1.150 | 1.500/5.500 |
| l16 | R3a | reference | 200 | 531.0/520.9 | 200 | 140.8 | 0.400/1.150 | 1.500/5.500 |
| l16 | R3a | kv2 | 200 | 534.0/514.0 | 200 | 141.1 | 0.400/1.150 | 1.500/5.750 |
| l16 | HPv2 | reference | 200 | 438.0/423.0 | 200 | 138.5 | 0.400/1.150 | 1.750/6.000 |
| l16 | HPv2 | kv2 | 200 | 438.8/418.7 | 200 | 139.0 | 0.400/1.150 | 1.750/5.750 |
| acc | all three | reference | 600 | 498.4/476.5 | 600 | 140.7 | 0.150/1.150 | 1.500/5.500 |
| acc | all three | kv2 | 600 | 507.0/489.7 | 600 | 144.0 | 0.150/1.150 | 1.500/5.500 |
| acc | K4CW-fp | reference | 200 | 539.7/514.9 | 200 | 142.1 | 0.150/1.150 | 1.500/5.500 |
| acc | K4CW-fp | kv2 | 200 | 549.3/534.0 | 200 | 147.0 | 0.150/1.150 | 1.500/5.500 |
| acc | R3a | reference | 200 | 535.3/515.5 | 200 | 144.4 | 0.400/0.900 | 1.500/5.750 |
| acc | R3a | kv2 | 200 | 535.8/513.4 | 200 | 149.2 | 0.400/1.150 | 1.500/5.500 |
| acc | HPv2 | reference | 200 | 416.0/396.7 | 200 | 135.7 | 0.400/1.150 | 1.750/5.750 |
| acc | HPv2 | kv2 | 200 | 429.6/401.7 | 200 | 135.7 | 0.400/1.150 | 1.750/5.750 |
| pooled | all three | reference | 1200 | 501.8/479.3 | 1200 | 140.6 | 0.150/1.150 | 1.500/5.750 |
| pooled | all three | kv2 | 1200 | 505.5/489.4 | 1200 | 142.0 | 0.150/1.150 | 1.500/5.500 |
| pooled | K4CW-fp | reference | 400 | 542.4/517.9 | 400 | 142.1 | 0.150/1.150 | 1.500/5.500 |
| pooled | K4CW-fp | kv2 | 400 | 544.0/525.7 | 400 | 143.7 | 0.150/1.150 | 1.500/5.500 |
| pooled | R3a | reference | 400 | 533.2/517.6 | 400 | 142.6 | 0.400/1.150 | 1.500/5.750 |
| pooled | R3a | kv2 | 400 | 534.9/513.5 | 400 | 145.1 | 0.400/1.150 | 1.500/5.750 |
| pooled | HPv2 | reference | 400 | 427.2/405.4 | 400 | 137.1 | 0.400/1.150 | 1.750/5.750 |
| pooled | HPv2 | kv2 | 400 | 434.3/411.1 | 400 | 137.4 | 0.400/1.150 | 1.750/5.750 |


| Row | Opponent | Arm | Incursions/game | Elixir mean/median | Elixir >=8 | Undefended 5s | Giant pushes | Giant undefended |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | all three | reference | 13.10 | 3.26/3.14 | 0.003 | 0.133 | 170 | 0.071 |
| l16 | all three | kv2 | 13.13 | 3.28/3.18 | 0.003 | 0.136 | 177 | 0.056 |
| l16 | K4CW-fp | reference | 14.88 | 3.21/3.09 | 0.002 | 0.146 | 7 | 0.143 |
| l16 | K4CW-fp | kv2 | 15.03 | 3.17/3.03 | 0.001 | 0.149 | 5 | 0.000 |
| l16 | R3a | reference | 13.49 | 3.26/3.11 | 0.003 | 0.130 | 73 | 0.082 |
| l16 | R3a | kv2 | 13.54 | 3.34/3.21 | 0.004 | 0.133 | 83 | 0.060 |
| l16 | HPv2 | reference | 10.92 | 3.33/3.21 | 0.003 | 0.120 | 90 | 0.056 |
| l16 | HPv2 | kv2 | 10.82 | 3.36/3.25 | 0.006 | 0.121 | 89 | 0.056 |
| acc | all three | reference | 13.23 | 3.27/3.16 | 0.003 | 0.135 | 157 | 0.064 |
| acc | all three | kv2 | 13.44 | 3.27/3.16 | 0.003 | 0.132 | 171 | 0.035 |
| acc | K4CW-fp | reference | 15.14 | 3.23/3.11 | 0.002 | 0.145 | 11 | 0.091 |
| acc | K4CW-fp | kv2 | 15.26 | 3.22/3.14 | 0.003 | 0.141 | 13 | 0.077 |
| acc | R3a | reference | 13.85 | 3.26/3.16 | 0.003 | 0.138 | 68 | 0.088 |
| acc | R3a | kv2 | 14.51 | 3.28/3.12 | 0.003 | 0.130 | 79 | 0.051 |
| acc | HPv2 | reference | 10.71 | 3.35/3.23 | 0.004 | 0.117 | 78 | 0.038 |
| acc | HPv2 | kv2 | 10.54 | 3.33/3.23 | 0.003 | 0.123 | 79 | 0.013 |
| pooled | all three | reference | 13.16 | 3.27/3.14 | 0.003 | 0.134 | 327 | 0.067 |
| pooled | all three | kv2 | 13.28 | 3.28/3.16 | 0.003 | 0.134 | 348 | 0.046 |
| pooled | K4CW-fp | reference | 15.01 | 3.22/3.11 | 0.002 | 0.145 | 18 | 0.111 |
| pooled | K4CW-fp | kv2 | 15.14 | 3.20/3.10 | 0.002 | 0.145 | 18 | 0.056 |
| pooled | R3a | reference | 13.67 | 3.26/3.12 | 0.003 | 0.134 | 141 | 0.085 |
| pooled | R3a | kv2 | 14.03 | 3.31/3.18 | 0.004 | 0.132 | 162 | 0.056 |
| pooled | HPv2 | reference | 10.81 | 3.34/3.21 | 0.004 | 0.119 | 168 | 0.048 |
| pooled | HPv2 | kv2 | 10.69 | 3.35/3.25 | 0.004 | 0.122 | 168 | 0.036 |


| Row | Opponent | Arm | Revealed wincon events | Wincon spend | Troop plays | Idle play | Defensive plays | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | all three | reference | 2123 | 0.060 | 18897 | 0.558 | 16664 | 0.261 |
| l16 | all three | kv2 | 2111 | 0.055 | 18964 | 0.559 | 16751 | 0.253 |
| l16 | K4CW-fp | reference | 748 | 0.060 | 6423 | 0.530 | 6125 | 0.282 |
| l16 | K4CW-fp | kv2 | 728 | 0.056 | 6318 | 0.531 | 6042 | 0.274 |
| l16 | R3a | reference | 728 | 0.069 | 6275 | 0.576 | 5437 | 0.274 |
| l16 | R3a | kv2 | 723 | 0.059 | 6403 | 0.574 | 5564 | 0.266 |
| l16 | HPv2 | reference | 647 | 0.051 | 6199 | 0.568 | 5102 | 0.224 |
| l16 | HPv2 | kv2 | 660 | 0.050 | 6243 | 0.571 | 5145 | 0.214 |
| acc | all three | reference | 2084 | 0.059 | 18957 | 0.563 | 16856 | 0.262 |
| acc | all three | kv2 | 2142 | 0.053 | 19629 | 0.558 | 17602 | 0.263 |
| acc | K4CW-fp | reference | 722 | 0.073 | 6440 | 0.532 | 6270 | 0.281 |
| acc | K4CW-fp | kv2 | 751 | 0.044 | 6710 | 0.527 | 6528 | 0.279 |
| acc | R3a | reference | 759 | 0.054 | 6497 | 0.578 | 5744 | 0.281 |
| acc | R3a | kv2 | 780 | 0.050 | 6823 | 0.580 | 6117 | 0.288 |
| acc | HPv2 | reference | 603 | 0.048 | 6020 | 0.579 | 4842 | 0.216 |
| acc | HPv2 | kv2 | 611 | 0.067 | 6096 | 0.568 | 4957 | 0.211 |
| pooled | all three | reference | 4207 | 0.060 | 37854 | 0.560 | 33520 | 0.262 |
| pooled | all three | kv2 | 4253 | 0.054 | 38593 | 0.558 | 34353 | 0.258 |
| pooled | K4CW-fp | reference | 1470 | 0.067 | 12863 | 0.531 | 12395 | 0.281 |
| pooled | K4CW-fp | kv2 | 1479 | 0.050 | 13028 | 0.529 | 12570 | 0.276 |
| pooled | R3a | reference | 1487 | 0.061 | 12772 | 0.577 | 11181 | 0.277 |
| pooled | R3a | kv2 | 1503 | 0.055 | 13226 | 0.577 | 11681 | 0.278 |
| pooled | HPv2 | reference | 1250 | 0.050 | 12219 | 0.573 | 9944 | 0.220 |
| pooled | HPv2 | kv2 | 1271 | 0.058 | 12339 | 0.570 | 10102 | 0.213 |


## Hog crossings by opponent

| Row | Opponent | Arm | Crossings | Elixir mean/median | Share >=6 | Cannon+3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | K4CW-fp | reference | 441 | 3.107/2.928 | 0.032 | 0.272 |
| l16 | K4CW-fp | kv2 | 454 | 3.024/2.785 | 0.029 | 0.286 |
| l16 | R3a | reference | 408 | 3.214/3.000 | 0.049 | 0.333 |
| l16 | R3a | kv2 | 405 | 3.241/3.089 | 0.035 | 0.341 |
| l16 | HPv2 | reference | 323 | 3.043/2.964 | 0.015 | 0.313 |
| l16 | HPv2 | kv2 | 331 | 3.178/3.107 | 0.033 | 0.344 |
| acc | K4CW-fp | reference | 432 | 3.090/2.928 | 0.023 | 0.275 |
| acc | K4CW-fp | kv2 | 453 | 3.189/3.000 | 0.033 | 0.294 |
| acc | R3a | reference | 417 | 3.306/3.107 | 0.050 | 0.331 |
| acc | R3a | kv2 | 432 | 3.230/3.053 | 0.035 | 0.350 |
| acc | HPv2 | reference | 304 | 2.947/2.794 | 0.023 | 0.266 |
| acc | HPv2 | kv2 | 304 | 3.175/3.044 | 0.036 | 0.316 |
| pooled | K4CW-fp | reference | 873 | 3.099/2.928 | 0.027 | 0.274 |
| pooled | K4CW-fp | kv2 | 907 | 3.107/2.875 | 0.031 | 0.290 |
| pooled | R3a | reference | 825 | 3.260/3.035 | 0.050 | 0.332 |
| pooled | R3a | kv2 | 837 | 3.235/3.071 | 0.035 | 0.345 |
| pooled | HPv2 | reference | 627 | 2.997/2.875 | 0.019 | 0.290 |
| pooled | HPv2 | kv2 | 635 | 3.177/3.089 | 0.035 | 0.331 |


## Card plays and observed hit shares by opponent

| Row | Opponent | Arm | Card | Plays/game | Plays | Observed frames | Observed hits | Hit/proximity share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | K4CW-fp | reference | Fireball | 0.950 | 190 | 180 | 80 | 0.444 |
| l16 | K4CW-fp | reference | Zap | 5.315 | 1063 | 1059 | 557 | 0.526 |
| l16 | K4CW-fp | reference | ElectroSpirit | 7.775 | 1555 | 1529 | 326 | 0.213 |
| l16 | K4CW-fp | kv2 | Fireball | 0.955 | 191 | 184 | 83 | 0.451 |
| l16 | K4CW-fp | kv2 | Zap | 5.475 | 1095 | 1090 | 576 | 0.528 |
| l16 | K4CW-fp | kv2 | ElectroSpirit | 7.730 | 1546 | 1521 | 364 | 0.239 |
| l16 | R3a | reference | Fireball | 1.185 | 237 | 223 | 100 | 0.448 |
| l16 | R3a | reference | Zap | 5.360 | 1072 | 1062 | 630 | 0.593 |
| l16 | R3a | reference | ElectroSpirit | 7.485 | 1497 | 1483 | 315 | 0.212 |
| l16 | R3a | kv2 | Fireball | 1.130 | 226 | 214 | 120 | 0.561 |
| l16 | R3a | kv2 | Zap | 5.400 | 1080 | 1075 | 616 | 0.573 |
| l16 | R3a | kv2 | ElectroSpirit | 7.785 | 1557 | 1541 | 328 | 0.213 |
| l16 | HPv2 | reference | Fireball | 1.130 | 226 | 213 | 111 | 0.521 |
| l16 | HPv2 | reference | Zap | 5.345 | 1069 | 1065 | 675 | 0.634 |
| l16 | HPv2 | reference | ElectroSpirit | 7.495 | 1499 | 1481 | 356 | 0.240 |
| l16 | HPv2 | kv2 | Fireball | 1.220 | 244 | 233 | 115 | 0.494 |
| l16 | HPv2 | kv2 | Zap | 5.330 | 1066 | 1062 | 637 | 0.600 |
| l16 | HPv2 | kv2 | ElectroSpirit | 7.620 | 1524 | 1505 | 384 | 0.255 |
| acc | K4CW-fp | reference | Fireball | 0.945 | 189 | 169 | 72 | 0.426 |
| acc | K4CW-fp | reference | Zap | 5.560 | 1112 | 1104 | 496 | 0.449 |
| acc | K4CW-fp | reference | ElectroSpirit | 7.815 | 1563 | 1545 | 334 | 0.216 |
| acc | K4CW-fp | kv2 | Fireball | 0.935 | 187 | 176 | 87 | 0.494 |
| acc | K4CW-fp | kv2 | Zap | 5.695 | 1139 | 1129 | 561 | 0.497 |
| acc | K4CW-fp | kv2 | ElectroSpirit | 8.075 | 1615 | 1599 | 348 | 0.218 |
| acc | R3a | reference | Fireball | 1.225 | 245 | 224 | 107 | 0.478 |
| acc | R3a | reference | Zap | 5.785 | 1157 | 1152 | 605 | 0.525 |
| acc | R3a | reference | ElectroSpirit | 7.895 | 1579 | 1560 | 334 | 0.214 |
| acc | R3a | kv2 | Fireball | 1.425 | 285 | 265 | 143 | 0.540 |
| acc | R3a | kv2 | Zap | 5.850 | 1170 | 1162 | 615 | 0.529 |
| acc | R3a | kv2 | ElectroSpirit | 8.280 | 1656 | 1641 | 348 | 0.212 |
| acc | HPv2 | reference | Fireball | 1.030 | 206 | 199 | 109 | 0.548 |
| acc | HPv2 | reference | Zap | 5.140 | 1028 | 1024 | 592 | 0.578 |
| acc | HPv2 | reference | ElectroSpirit | 7.355 | 1471 | 1451 | 323 | 0.223 |
| acc | HPv2 | kv2 | Fireball | 0.975 | 195 | 187 | 93 | 0.497 |
| acc | HPv2 | kv2 | Zap | 5.170 | 1034 | 1030 | 591 | 0.574 |
| acc | HPv2 | kv2 | ElectroSpirit | 7.440 | 1488 | 1472 | 337 | 0.229 |
| pooled | K4CW-fp | reference | Fireball | 0.948 | 379 | 349 | 152 | 0.436 |
| pooled | K4CW-fp | reference | Zap | 5.438 | 2175 | 2163 | 1053 | 0.487 |
| pooled | K4CW-fp | reference | ElectroSpirit | 7.795 | 3118 | 3074 | 660 | 0.215 |
| pooled | K4CW-fp | kv2 | Fireball | 0.945 | 378 | 360 | 170 | 0.472 |
| pooled | K4CW-fp | kv2 | Zap | 5.585 | 2234 | 2219 | 1137 | 0.512 |
| pooled | K4CW-fp | kv2 | ElectroSpirit | 7.902 | 3161 | 3120 | 712 | 0.228 |
| pooled | R3a | reference | Fireball | 1.205 | 482 | 447 | 207 | 0.463 |
| pooled | R3a | reference | Zap | 5.572 | 2229 | 2214 | 1235 | 0.558 |
| pooled | R3a | reference | ElectroSpirit | 7.690 | 3076 | 3043 | 649 | 0.213 |
| pooled | R3a | kv2 | Fireball | 1.278 | 511 | 479 | 263 | 0.549 |
| pooled | R3a | kv2 | Zap | 5.625 | 2250 | 2237 | 1231 | 0.550 |
| pooled | R3a | kv2 | ElectroSpirit | 8.033 | 3213 | 3182 | 676 | 0.212 |
| pooled | HPv2 | reference | Fireball | 1.080 | 432 | 412 | 220 | 0.534 |
| pooled | HPv2 | reference | Zap | 5.242 | 2097 | 2089 | 1267 | 0.607 |
| pooled | HPv2 | reference | ElectroSpirit | 7.425 | 2970 | 2932 | 679 | 0.232 |
| pooled | HPv2 | kv2 | Fireball | 1.097 | 439 | 420 | 208 | 0.495 |
| pooled | HPv2 | kv2 | Zap | 5.250 | 2100 | 2092 | 1228 | 0.587 |
| pooled | HPv2 | kv2 | ElectroSpirit | 7.530 | 3012 | 2977 | 721 | 0.242 |


ElectroSpirit remains the RF1 deployment-proximity surrogate, not an observed jump-hit rate. Fireball/Zap observations retain RF1 post-impact frame limitations.

## Barrel answers and Cannon placement by opponent

| Row | Opponent | Arm | Barrels | Answered <=2s | Answer share <=2s/1.5s | Cannon plays | Centre share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | K4CW-fp | reference | 242 | 29 | 0.120/0.103 | 930 | 0.004 | 0.996 |
| l16 | K4CW-fp | kv2 | 227 | 31 | 0.137/0.115 | 908 | 0.012 | 0.988 |
| l16 | R3a | reference | 224 | 35 | 0.156/0.121 | 890 | 0.011 | 0.989 |
| l16 | R3a | kv2 | 219 | 32 | 0.146/0.082 | 895 | 0.004 | 0.996 |
| l16 | HPv2 | reference | 195 | 17 | 0.087/0.041 | 874 | 0.011 | 0.989 |
| l16 | HPv2 | kv2 | 199 | 22 | 0.111/0.075 | 854 | 0.020 | 0.980 |
| acc | K4CW-fp | reference | 229 | 27 | 0.118/0.118 | 956 | 0.009 | 0.991 |
| acc | K4CW-fp | kv2 | 227 | 33 | 0.145/0.137 | 1048 | 0.006 | 0.994 |
| acc | R3a | reference | 241 | 36 | 0.149/0.129 | 935 | 0.007 | 0.993 |
| acc | R3a | kv2 | 243 | 36 | 0.148/0.119 | 987 | 0.004 | 0.996 |
| acc | HPv2 | reference | 190 | 17 | 0.089/0.047 | 838 | 0.011 | 0.989 |
| acc | HPv2 | kv2 | 196 | 24 | 0.122/0.071 | 880 | 0.016 | 0.984 |
| pooled | K4CW-fp | reference | 471 | 56 | 0.119/0.110 | 1886 | 0.007 | 0.993 |
| pooled | K4CW-fp | kv2 | 454 | 64 | 0.141/0.126 | 1956 | 0.009 | 0.991 |
| pooled | R3a | reference | 465 | 71 | 0.153/0.125 | 1825 | 0.009 | 0.991 |
| pooled | R3a | kv2 | 462 | 68 | 0.147/0.102 | 1882 | 0.004 | 0.996 |
| pooled | HPv2 | reference | 385 | 34 | 0.088/0.044 | 1712 | 0.011 | 0.989 |
| pooled | HPv2 | kv2 | 395 | 46 | 0.116/0.073 | 1734 | 0.018 | 0.982 |


## Guardrail SEs and sensitivity

As LP2: for a ratio m=sum(x)/sum(y), game influence is n*(x_i-m*y_i)/sum(y). The paired delta SE is sample SD of treatment-minus-reference influences / sqrt(n), preserving within-game event dependence and arm pairing. Cases with zero events still participate with zero sufficient statistics; a zero aggregate denominator is NA. More is better for all four gated metrics. The adverse threshold is strictly delta < -2*SE (numerical epsilon 1e-12), with no multiplicity adjustment. The primary metric gate pools all three opponents, following RF1 pooled metrics; level-row and opponent-specific checks below are sensitivity diagnostics. Score CIs remain the unchanged 4000-draw Random(0) bootstrap.

| Row | Opponent | Metric | Reference | kv2 | Delta | Paired SE | Ref/treat events | Adverse >2 SE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | all three | hog_elixir_mean | 3.12668 | 3.14093 | 0.01425 | 0.04876 | 1172/1190 | no |
| l16 | all three | hog_elixir_ge6 | 0.03328 | 0.03193 | -0.00134 | 0.00725 | 1172/1190 | no |
| l16 | all three | hog_cannon_and_ge3 | 0.30461 | 0.32101 | 0.01640 | 0.01763 | 1172/1190 | no |
| l16 | all three | barrel_answer_share | 0.12254 | 0.13178 | 0.00924 | 0.01699 | 661/645 | no |
| l16 | K4CW-fp | hog_elixir_mean | 3.10690 | 3.02449 | -0.08241 | 0.07307 | 441/454 | no |
| l16 | K4CW-fp | hog_elixir_ge6 | 0.03175 | 0.02863 | -0.00311 | 0.01092 | 441/454 | no |
| l16 | K4CW-fp | hog_cannon_and_ge3 | 0.27211 | 0.28634 | 0.01423 | 0.02770 | 441/454 | no |
| l16 | K4CW-fp | barrel_answer_share | 0.11983 | 0.13656 | 0.01673 | 0.02702 | 242/227 | no |
| l16 | R3a | hog_elixir_mean | 3.21415 | 3.24096 | 0.02680 | 0.07986 | 408/405 | no |
| l16 | R3a | hog_elixir_ge6 | 0.04902 | 0.03457 | -0.01445 | 0.01280 | 408/405 | no |
| l16 | R3a | hog_cannon_and_ge3 | 0.33333 | 0.34074 | 0.00741 | 0.02919 | 408/405 | no |
| l16 | R3a | barrel_answer_share | 0.15625 | 0.14612 | -0.01013 | 0.03335 | 224/219 | no |
| l16 | HPv2 | hog_elixir_mean | 3.04321 | 3.17825 | 0.13504 | 0.10440 | 323/331 | no |
| l16 | HPv2 | hog_elixir_ge6 | 0.01548 | 0.03323 | 0.01775 | 0.01411 | 323/331 | no |
| l16 | HPv2 | hog_cannon_and_ge3 | 0.31269 | 0.34441 | 0.03172 | 0.03629 | 323/331 | no |
| l16 | HPv2 | barrel_answer_share | 0.08718 | 0.11055 | 0.02337 | 0.02630 | 195/199 | no |
| acc | all three | hog_elixir_mean | 3.13028 | 3.20008 | 0.06981 | 0.05703 | 1153/1189 | no |
| acc | all three | hog_elixir_ge6 | 0.03296 | 0.03448 | 0.00153 | 0.00803 | 1153/1189 | no |
| acc | all three | hog_cannon_and_ge3 | 0.29315 | 0.31960 | 0.02645 | 0.01859 | 1153/1189 | no |
| acc | all three | barrel_answer_share | 0.12121 | 0.13964 | 0.01843 | 0.01798 | 660/666 | no |
| acc | K4CW-fp | hog_elixir_mean | 3.08995 | 3.18874 | 0.09879 | 0.10505 | 432/453 | no |
| acc | K4CW-fp | hog_elixir_ge6 | 0.02315 | 0.03311 | 0.00996 | 0.01282 | 432/453 | no |
| acc | K4CW-fp | hog_cannon_and_ge3 | 0.27546 | 0.29360 | 0.01814 | 0.03156 | 432/453 | no |
| acc | K4CW-fp | barrel_answer_share | 0.11790 | 0.14537 | 0.02747 | 0.03371 | 229/227 | no |
| acc | R3a | hog_elixir_mean | 3.30551 | 3.22977 | -0.07574 | 0.08247 | 417/432 | no |
| acc | R3a | hog_elixir_ge6 | 0.05036 | 0.03472 | -0.01564 | 0.01495 | 417/432 | no |
| acc | R3a | hog_cannon_and_ge3 | 0.33094 | 0.34954 | 0.01860 | 0.02746 | 417/432 | no |
| acc | R3a | barrel_answer_share | 0.14938 | 0.14815 | -0.00123 | 0.02920 | 241/243 | no |
| acc | HPv2 | hog_elixir_mean | 2.94722 | 3.17481 | 0.22758 | 0.10616 | 304/304 | no |
| acc | HPv2 | hog_elixir_ge6 | 0.02303 | 0.03618 | 0.01316 | 0.01281 | 304/304 | no |
| acc | HPv2 | hog_cannon_and_ge3 | 0.26645 | 0.31579 | 0.04934 | 0.03981 | 304/304 | no |
| acc | HPv2 | barrel_answer_share | 0.08947 | 0.12245 | 0.03298 | 0.02982 | 190/196 | no |
| pooled | all three | hog_elixir_mean | 3.12847 | 3.17049 | 0.04203 | 0.03754 | 2325/2379 | no |
| pooled | all three | hog_elixir_ge6 | 0.03312 | 0.03321 | 0.00009 | 0.00541 | 2325/2379 | no |
| pooled | all three | hog_cannon_and_ge3 | 0.29892 | 0.32030 | 0.02138 | 0.01281 | 2325/2379 | no |
| pooled | all three | barrel_answer_share | 0.12188 | 0.13577 | 0.01390 | 0.01237 | 1321/1311 | no |
| pooled | K4CW-fp | hog_elixir_mean | 3.09851 | 3.10652 | 0.00801 | 0.06428 | 873/907 | no |
| pooled | K4CW-fp | hog_elixir_ge6 | 0.02749 | 0.03087 | 0.00338 | 0.00842 | 873/907 | no |
| pooled | K4CW-fp | hog_cannon_and_ge3 | 0.27377 | 0.28997 | 0.01620 | 0.02097 | 873/907 | no |
| pooled | K4CW-fp | barrel_answer_share | 0.11890 | 0.14097 | 0.02207 | 0.02152 | 471/454 | no |
| pooled | R3a | hog_elixir_mean | 3.26033 | 3.23519 | -0.02514 | 0.05767 | 825/837 | no |
| pooled | R3a | hog_elixir_ge6 | 0.04970 | 0.03465 | -0.01505 | 0.00987 | 825/837 | no |
| pooled | R3a | hog_cannon_and_ge3 | 0.33212 | 0.34528 | 0.01316 | 0.02002 | 825/837 | no |
| pooled | R3a | barrel_answer_share | 0.15269 | 0.14719 | -0.00550 | 0.02204 | 465/462 | no |
| pooled | HPv2 | hog_elixir_mean | 2.99667 | 3.17660 | 0.17993 | 0.07432 | 627/635 | no |
| pooled | HPv2 | hog_elixir_ge6 | 0.01914 | 0.03465 | 0.01551 | 0.00958 | 627/635 | no |
| pooled | HPv2 | hog_cannon_and_ge3 | 0.29027 | 0.33071 | 0.04044 | 0.02671 | 627/635 | no |
| pooled | HPv2 | barrel_answer_share | 0.08831 | 0.11646 | 0.02814 | 0.01984 | 385/395 | no |


## Operational audit

Original successful shards with 150 rows: 16/16. Earliest logged start: 2026-10-18T07:50:16Z; latest logged end: 2026-10-18T08:52:05Z. Complete receipts, bank SHA256s, worker statuses and retry log paths: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/run-audit.json`.

| Host | Shard | Start UTC | End UTC / rc | Rows | PID/PGID | Retry logs |
| --- | --- | --- | --- | --- | --- | --- |
| 127x04 | l16-s0 | 2026-10-18T07:50:16Z | ('2026-10-18T08:30:15Z', '0') | 150 | 2152880/2152880 | 0 |
| 127x04 | l16-s1 | 2026-10-18T07:50:17Z | ('2026-10-18T08:26:42Z', '0') | 150 | 2152938/2152938 | 0 |
| 127x04 | l16-s2 | 2026-10-18T07:50:17Z | ('2026-10-18T08:30:09Z', '0') | 150 | 2152988/2152988 | 0 |
| 127x04 | l16-s3 | 2026-10-18T07:50:18Z | ('2026-10-18T08:28:08Z', '0') | 150 | 2153018/2153018 | 0 |
| 127x04 | acc-s0 | 2026-10-18T07:50:18Z | ('2026-10-18T08:29:49Z', '0') | 150 | 2153044/2153044 | 0 |
| 127x04 | acc-s1 | 2026-10-18T07:50:19Z | ('2026-10-18T08:28:08Z', '0') | 150 | 2153129/2153129 | 0 |
| 127x04 | acc-s2 | 2026-10-18T07:50:20Z | ('2026-10-18T08:30:33Z', '0') | 150 | 2153210/2153210 | 0 |
| 127x04 | acc-s3 | 2026-10-18T07:50:20Z | ('2026-10-18T08:30:31Z', '0') | 150 | 2153266/2153266 | 0 |
| 127x08 | l16-s4 | 2026-10-18T07:50:18Z | ('2026-10-18T08:49:36Z', '0') | 150 | 3743696/3743696 | 0 |
| 127x08 | l16-s5 | 2026-10-18T07:50:18Z | ('2026-10-18T08:50:44Z', '0') | 150 | 3743748/3743748 | 0 |
| 127x08 | l16-s6 | 2026-10-18T07:50:19Z | ('2026-10-18T08:48:45Z', '0') | 150 | 3743800/3743800 | 0 |
| 127x08 | l16-s7 | 2026-10-18T07:50:20Z | ('2026-10-18T08:49:56Z', '0') | 150 | 3743839/3743839 | 0 |
| 127x08 | acc-s4 | 2026-10-18T07:50:20Z | ('2026-10-18T08:48:09Z', '0') | 150 | 3743862/3743862 | 0 |
| 127x08 | acc-s5 | 2026-10-18T07:50:21Z | ('2026-10-18T08:52:05Z', '0') | 150 | 3743886/3743886 | 0 |
| 127x08 | acc-s6 | 2026-10-18T07:50:22Z | ('2026-10-18T08:49:37Z', '0') | 150 | 3743953/3743953 | 0 |
| 127x08 | acc-s7 | 2026-10-18T07:50:23Z | ('2026-10-18T08:49:55Z', '0') | 150 | 3744002/3744002 | 0 |


RF1 score_study.py extra() and hz_report definitions are reused exactly; runtime-only parameters extend the bank, arms and opponents. hz_report per-opponent summaries use the same implementation and symlinked normalized inputs. Original scorer/renderer files and repository code remain unchanged. The unchanged RF1/LP2 score bootstrap treats (level row,index,opponent) as paired observations and does not cluster repeated seeds across level rows.

Analysis plan, scorer/renderer substitutions, runtime source text, normalized inputs, full readout, per-game sufficient statistics, all ratio SEs and early wiring checks are retained under `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1`. Messaging rule: steer; on thread_not_sendable resend auto; never queue. No commits or sealing performed.

## Early rollout-model wiring

```json
{
  "checked_rows": 267,
  "complete_early_pairs": 81,
  "identical_command_pairs": 0,
  "different_command_pairs": 81,
  "start_config_name_caveat": "fullpool_worker.configure overwrites both arm display names with baseline player-config name; not a loaded-model field",
  "host_evidence": [
    {
      "host": "127x04",
      "at": "2026-10-18T08:01:00Z",
      "models": {
        "kv2": {
          "path": "/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/kv2.npz",
          "sha256": "0bb0353384fd4386c6091902d8af1a1717a1f0f9c35d417f1c63019ddeb043bb"
        },
        "k1a1": {
          "path": "/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/k1a1.npz",
          "sha256": "477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3"
        }
      },
      "launcher_model_environment": [
        "BOT_PQ_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp"
      ]
    },
    {
      "host": "127x08",
      "at": "2026-10-18T08:01:01Z",
      "models": {
        "kv2": {
          "path": "/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/kv2.npz",
          "sha256": "0bb0353384fd4386c6091902d8af1a1717a1f0f9c35d417f1c63019ddeb043bb"
        },
        "k1a1": {
          "path": "/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/k1a1.npz",
          "sha256": "477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3"
        }
      },
      "launcher_model_environment": [
        "BOT_PQ_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp"
      ]
    }
  ]
}
```

## Launch archive and model provenance

127x04:
```text
2026-10-18T09:02:06Z
a3af651cd8da
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/fullpool/scale_report.py
bb2067f2e827e4dff774718939dfebbe7a0867758f38e1a4fd715f11d3c4d34f  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/livediag/l16_report.py
631dd56ae639a026b4e7e0d0049427595db04eb6de6f620b7111b889b0e840e5  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/livediag/live_metrics.py
0bb0353384fd4386c6091902d8af1a1717a1f0f9c35d417f1c63019ddeb043bb  /mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/kv2.npz
477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3  /mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/k1a1.npz
```

127x08:
```text
2026-10-18T09:02:07Z
a3af651cd8da
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/fullpool/scale_report.py
bb2067f2e827e4dff774718939dfebbe7a0867758f38e1a4fd715f11d3c4d34f  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/livediag/l16_report.py
631dd56ae639a026b4e7e0d0049427595db04eb6de6f620b7111b889b0e840e5  /mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/livediag/live_metrics.py
0bb0353384fd4386c6091902d8af1a1717a1f0f9c35d417f1c63019ddeb043bb  /mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/kv2.npz
477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3  /mpac/sdicks02/jobs/clasher/bot-pq/models/lopp/k1a1.npz
```

## Exact staged parser check

Parser functions are extracted from the launch archive and executed with only the search constructor replaced by a keyword capture; no game or source file is changed. This proves last-model-token selection. The 81/81 early command-event differences provide the independent run-level treatment check.

```json
{
  "at": "2026-10-18T08:02:03Z",
  "source_sha256": {
    "/mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/search/lopp.py": "90eefbb51b9d95bf99000b9938389d1c36dbd14289dc9f0d320e877b57e31c83",
    "/mpac/sdicks02/jobs/clasher/bot-pq/repo-a3af651cd8da/bot/search/lopp_fast.py": "2ffb484382efcad3dfe45dc936414f92a75159f439660892d139041382f16dcc"
  },
  "parsers": {
    "res-lb-RF-wintp": {
      "body": "K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res",
      "model": "k1a1",
      "live_options": {
        "balance": true,
        "root_fidelity": "RF"
      },
      "kwargs": {
        "sample": true,
        "rowwise": true,
        "model": "k1a1",
        "fast_cut": true,
        "wall_ms": 200,
        "threads": 4,
        "pool": 4
      }
    },
    "res-lb-RF-mkv2-wintp": {
      "body": "K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-mkv2",
      "model": "kv2",
      "live_options": {
        "balance": true,
        "root_fidelity": "RF"
      },
      "kwargs": {
        "sample": true,
        "rowwise": true,
        "model": "kv2",
        "fast_cut": true,
        "wall_ms": 200,
        "threads": 4,
        "pool": 4
      }
    }
  }
}
```

Artifact hashes measured 2026-10-18T09:07:12Z:
```text
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/score_study.py
f044645d93f70ef0ef4e74297f75e008905d7991d29b9f8dc6f24472eb2f3a99  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/render_report.py
7e309ed684999721e597e7f0ad958c764664e2029508e85819717aa9ff4f7b86  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/scorer-runtime-source.txt
c7fb354d385cd75c5220bf44029b9051f2aa0c17df25757147873b8f7cb735d6  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/metric-runtime-source.txt
cc8764182089ce54f62b1b3d73b3b1b3b23819821255a7232d8dcceda944f26c  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/renderer-runtime-source.txt
282275e32f11c08c2808b4ebc0167122d7c5f969930dab654f2a9edc72a23cc0  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/kv1/report-extension-source.txt
```
