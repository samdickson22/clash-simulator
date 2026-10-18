# HPC1 results

Preregistration: [HPC-PREREG.md](HPC-PREREG.md). `l16` denotes L16; `acc` denotes the account row.

Readout generated 2026-10-18T04:56:25Z. Reference `res-lb-wintp`; treatment `res-lb-hk16-fv2-wintp`.

**Ship: FAIL.** Pooled K4CW lower-bound criterion: FAIL; neither-row-below−0.02 criterion: PASS; literal metrics-not-worse criterion: FAIL.

Metrics with worse point estimates: cpu_ms_per_decision_pooled, elixir_at_cross_mean, hog_elixir_mean, hog_elixir_ge6, hog_cannon_and_ge3, barrel_answer_share, Fireball_enemy_in_radius_share. The preregistration does not define metric tolerances or a composite gate. This readout applies a conservative zero-tolerance point-estimate check to the observable metrics below; play counts and Cannon location are descriptive. No metric-significance claim is made.

## Data integrity

Raw rows: 1600; unique valid rows: 1600; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'l16': 800, 'acc': 800}`. Hosts: `{'127x04': 800, '127x08': 800}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw`. Completion and rerun history is in the appended run audit.

Exactly 200 paired cases per opponent per level row; 400 pairs per opponent pooled over L16/account. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | Both opponents treatment − reference, 95% CI |
| --- | --- | --- | --- |
| l16 | +0.0550 [-0.0350, +0.1400] (n=200) | +0.0200 [-0.0450, +0.0800] (n=200) | +0.0375 [-0.0150, +0.0900] (n=400) |
| acc | +0.0500 [-0.0400, +0.1350] (n=200) | -0.0300 [-0.1050, +0.0500] (n=200) | +0.0100 [-0.0500, +0.0700] (n=400) |
| pooled | +0.0525 [-0.0075, +0.1150] (n=400) | -0.0050 [-0.0575, +0.0450] (n=400) | +0.0238 [-0.0163, +0.0625] (n=800) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | Both score |
| --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 400 | 0.685 | 0.810 | 0.748 |
| l16 | res-lb-hk16-fv2-wintp | 400 | 0.740 | 0.830 | 0.785 |
| acc | res-lb-wintp | 400 | 0.450 | 0.625 | 0.537 |
| acc | res-lb-hk16-fv2-wintp | 400 | 0.500 | 0.595 | 0.547 |
| pooled | res-lb-wintp | 800 | 0.568 | 0.718 | 0.642 |
| pooled | res-lb-hk16-fv2-wintp | 800 | 0.620 | 0.713 | 0.666 |


## Standing play-quality metrics (both opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 809.1 | 1.500/5.500 | 3.25/3.14 | 0.002 | 0.072 | 0.549 | 0.270 |
| l16 | res-lb-hk16-fv2-wintp | 898.2 | 1.500/5.500 | 3.20/3.11 | 0.001 | 0.060 | 0.526 | 0.259 |
| acc | res-lb-wintp | 804.9 | 1.500/5.500 | 3.26/3.16 | 0.002 | 0.056 | 0.535 | 0.264 |
| acc | res-lb-hk16-fv2-wintp | 882.8 | 1.500/5.500 | 3.18/3.07 | 0.002 | 0.059 | 0.531 | 0.268 |
| pooled | res-lb-wintp | 807.0 | 1.500/5.500 | 3.25/3.14 | 0.002 | 0.064 | 0.542 | 0.267 |
| pooled | res-lb-hk16-fv2-wintp | 890.5 | 1.500/5.500 | 3.19/3.07 | 0.002 | 0.059 | 0.528 | 0.263 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 776 | 3.232 | 3.000 | 0.039 | 0.325 |
| l16 | res-lb-hk16-fv2-wintp | 810 | 3.218 | 3.142 | 0.021 | 0.336 |
| acc | res-lb-wintp | 782 | 3.269 | 3.142 | 0.035 | 0.354 |
| acc | res-lb-hk16-fv2-wintp | 792 | 3.198 | 3.053 | 0.029 | 0.317 |
| pooled | res-lb-wintp | 1558 | 3.251 | 3.071 | 0.037 | 0.340 |
| pooled | res-lb-hk16-fv2-wintp | 1602 | 3.208 | 3.107 | 0.025 | 0.326 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | Fireball | 0.980 | 392 | 362 | 0.492 |
| l16 | res-lb-wintp | Zap | 5.223 | 2089 | 2085 | 0.578 |
| l16 | res-lb-wintp | ElectroSpirit | 7.548 | 3019 | 2987 | 0.224 |
| l16 | res-lb-hk16-fv2-wintp | Fireball | 0.900 | 360 | 324 | 0.444 |
| l16 | res-lb-hk16-fv2-wintp | Zap | 5.280 | 2112 | 2102 | 0.599 |
| l16 | res-lb-hk16-fv2-wintp | ElectroSpirit | 7.872 | 3149 | 3107 | 0.225 |
| acc | res-lb-wintp | Fireball | 1.077 | 431 | 402 | 0.485 |
| acc | res-lb-wintp | Zap | 5.570 | 2228 | 2209 | 0.537 |
| acc | res-lb-wintp | ElectroSpirit | 7.933 | 3173 | 3135 | 0.214 |
| acc | res-lb-hk16-fv2-wintp | Fireball | 0.915 | 366 | 331 | 0.529 |
| acc | res-lb-hk16-fv2-wintp | Zap | 5.625 | 2250 | 2232 | 0.535 |
| acc | res-lb-hk16-fv2-wintp | ElectroSpirit | 7.995 | 3198 | 3164 | 0.221 |
| pooled | res-lb-wintp | Fireball | 1.029 | 823 | 764 | 0.488 |
| pooled | res-lb-wintp | Zap | 5.396 | 4317 | 4294 | 0.557 |
| pooled | res-lb-wintp | ElectroSpirit | 7.740 | 6192 | 6122 | 0.219 |
| pooled | res-lb-hk16-fv2-wintp | Fireball | 0.907 | 726 | 655 | 0.487 |
| pooled | res-lb-hk16-fv2-wintp | Zap | 5.452 | 4362 | 4334 | 0.566 |
| pooled | res-lb-hk16-fv2-wintp | ElectroSpirit | 7.934 | 6347 | 6271 | 0.223 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 471 | 22 | 0.047 | 0.045 | 1808 | 0.008 | 0.992 |
| l16 | res-lb-hk16-fv2-wintp | 474 | 15 | 0.032 | 0.027 | 1889 | 0.019 | 0.981 |
| acc | res-lb-wintp | 507 | 22 | 0.043 | 0.041 | 1955 | 0.008 | 0.992 |
| acc | res-lb-hk16-fv2-wintp | 494 | 22 | 0.045 | 0.043 | 1918 | 0.017 | 0.983 |
| pooled | res-lb-wintp | 978 | 44 | 0.045 | 0.043 | 3763 | 0.008 | 0.992 |
| pooled | res-lb-hk16-fv2-wintp | 968 | 37 | 0.038 | 0.035 | 3807 | 0.018 | 0.982 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Worse point estimate |
| --- | --- | --- | --- | --- |
| cpu_ms_per_decision_pooled | 807.000 | 890.500 | 83.500 | yes |
| enemy_to_our_play_p50 | 1.500 | 1.500 | 0.000 | no |
| enemy_to_our_play_p90 | 5.500 | 5.500 | 0.000 | no |
| elixir_at_cross_mean | 3.250 | 3.190 | -0.060 | yes |
| wincon_spend_share | 0.064 | 0.059 | -0.005 | no |
| idle_play_share | 0.542 | 0.528 | -0.014 | no |
| wrong_lane_share | 0.267 | 0.263 | -0.004 | no |
| hog_elixir_mean | 3.251 | 3.208 | -0.043 | yes |
| hog_elixir_ge6 | 0.037 | 0.025 | -0.012 | yes |
| hog_cannon_and_ge3 | 0.340 | 0.326 | -0.013 | yes |
| barrel_answer_share | 0.045 | 0.038 | -0.007 | yes |
| Fireball_enemy_in_radius_share | 0.488 | 0.487 | -0.001 | yes |
| Zap_enemy_in_radius_share | 0.557 | 0.566 | 0.009 | no |
| ElectroSpirit_enemy_in_radius_share | 0.219 | 0.223 | 0.004 | no |


The supplied runner’s PacketRecorder filters decision statistics to source/hit/completed/timed_wait. `from_second` is not recorded. Consequently the chosen-play share exclusive to v2 is unavailable; rowsum’s printed zero must not be interpreted as a measured zero. Search/fast-path wiring is assessed separately by the smoke command-event comparison.

## Analysis artifacts and reproducibility

- l16 hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/hz-l16.json`

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/hpc1/readout-data.json`

Each hz_report was executed from the staged tree with its Python 3.12 environment, `PYTHONPATH=TREE`, `python -m bot.fullpool.hz_report DIR --ref res-lb-wintp --arms TREATMENT --gate TREATMENT --gate-opponent LIVE-K4CW-r16-fp --json OUT`. Normalized inputs preserve the first valid occurrence of each (level row, player, opponent, index). Pooled copies namespace index as `level-row:index` to prevent hz_report from treating the same numeric index in L16/account as a duplicate. Raw rows are retained unchanged.

Computed source SHA256s at readout generation:
```text
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/scale_report.py
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/score_study.py
f044645d93f70ef0ef4e74297f75e008905d7991d29b9f8dc6f24472eb2f3a99  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/render_report.py
```

## Run completion audit

2026-10-18T04:54:43Z
Original successful shards with 100 rows: 16/16. Earliest logged start 2026-10-18T03:25:31Z; latest end 2026-10-18T04:53:16Z.
- 127x04 l16-s0: start 2026-10-18T03:25:31Z; end ('2026-10-18T04:33:44Z', '0'); 100 original rows; receipt PID/PGID 158266/158266; worker statuses {'173847': 0, '173848': 0, '173851': 0, '173865': 0, '173875': 0, '173885': 0, '173909': 0, '173932': 0, '173948': 0, '173975': 0}.
  Bank SHA256: c11ef110c71b836f8766b394a23b72a639c0d9a5be8c325a6116024a1e37ff69  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/l16-s0/bank.json
- 127x04 l16-s1: start 2026-10-18T03:25:33Z; end ('2026-10-18T04:31:54Z', '0'); 100 original rows; receipt PID/PGID 158291/158291; worker statuses {'174334': 0, '174339': 0, '174349': 0, '174351': 0, '174355': 0, '174361': 0, '174363': 0, '174365': 0, '174369': 0, '174370': 0}.
  Bank SHA256: 77d21a41eca0a0d5c657ea4cf113c4c4fc096b48289ea3d01eb9e7d157341ea5  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/l16-s1/bank.json
- 127x04 l16-s2: start 2026-10-18T03:25:34Z; end ('2026-10-18T04:32:01Z', '0'); 100 original rows; receipt PID/PGID 158338/158338; worker statuses {'174802': 0, '174811': 0, '174823': 0, '174829': 0, '174837': 0, '174849': 0, '174857': 0, '174867': 0, '174877': 0, '174883': 0}.
  Bank SHA256: 3c522914730c2fab6185222bfb92d9493fc61fc7a3eee38531ce6f442d1846db  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/l16-s2/bank.json
- 127x04 l16-s3: start 2026-10-18T03:25:35Z; end ('2026-10-18T04:33:04Z', '0'); 100 original rows; receipt PID/PGID 158387/158387; worker statuses {'174975': 0, '174984': 0, '174989': 0, '174996': 0, '175003': 0, '175011': 0, '175018': 0, '175026': 0, '175027': 0, '175034': 0}.
  Bank SHA256: 6d4478a682fe45f488cd20862649f97963e17f2bb766314fa621989b70310907  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/l16-s3/bank.json
- 127x04 acc-s0: start 2026-10-18T03:25:36Z; end ('2026-10-18T04:32:12Z', '0'); 100 original rows; receipt PID/PGID 158422/158422; worker statuses {'175275': 0, '175289': 0, '175299': 0, '175317': 0, '175329': 0, '175337': 0, '175348': 0, '175357': 0, '175366': 0, '175374': 0}.
  Bank SHA256: 18aa250ebd657841b3d5d004d5d1ba1500bbcd6ac46ce0c3014c5f547081c236  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/acc-s0/bank.json
- 127x04 acc-s1: start 2026-10-18T03:25:38Z; end ('2026-10-18T04:33:32Z', '0'); 100 original rows; receipt PID/PGID 158483/158483; worker statuses {'175777': 0, '175784': 0, '175797': 0, '175798': 0, '175800': 0, '175802': 0, '175816': 0, '175819': 0, '175837': 0, '175846': 0}.
  Bank SHA256: 3ff1f05e7d79a8ad189521089a26dc73ec7afc60b4fbc7a23759b01f446c3964  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/acc-s1/bank.json
- 127x04 acc-s2: start 2026-10-18T03:25:39Z; end ('2026-10-18T04:34:53Z', '0'); 100 original rows; receipt PID/PGID 158539/158539; worker statuses {'176826': 0, '176831': 0, '176843': 0, '176852': 0, '176860': 0, '176876': 0, '176887': 0, '176901': 0, '176910': 0, '176916': 0}.
  Bank SHA256: 1e025c2d49deedb6260a20af49df767e7cd8bbc6dc1e6ee504cf8d90feca6751  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/acc-s2/bank.json
- 127x04 acc-s3: start 2026-10-18T03:25:40Z; end ('2026-10-18T04:33:27Z', '0'); 100 original rows; receipt PID/PGID 158568/158568; worker statuses {'176744': 0, '176749': 0, '176755': 0, '176760': 0, '176766': 0, '176772': 0, '176781': 0, '176783': 0, '176785': 0, '176792': 0}.
  Bank SHA256: e5897f3339e971ee6c3d978cfcdec7ad6d4d093f4e818310dd2b09e5231da29d  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/hpc1/acc-s3/bank.json
- 127x08 l16-s4: start 2026-10-18T03:25:31Z; end ('2026-10-18T04:46:00Z', '0'); 100 original rows; receipt PID/PGID 1869271/1869271; worker statuses {'1884794': 0, '1884799': 0, '1884807': 0, '1884809': 0, '1884815': 0, '1884823': 0, '1884831': 0, '1884839': 0, '1884845': 0, '1884850': 0}.
  Bank SHA256: 0274d54e41d49d698794434fbd4a8fee1861fd7d0e7555a1d40b7e56b6688327  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/l16-s4/bank.json
- 127x08 l16-s5: start 2026-10-18T03:25:31Z; end ('2026-10-18T04:44:30Z', '0'); 100 original rows; receipt PID/PGID 1869312/1869312; worker statuses {'1885123': 0, '1885126': 0, '1885151': 0, '1885164': 0, '1885190': 0, '1885203': 0, '1885212': 0, '1885221': 0, '1885231': 0, '1885248': 0}.
  Bank SHA256: 0274d54e41d49d698794434fbd4a8fee1861fd7d0e7555a1d40b7e56b6688327  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/l16-s5/bank.json
- 127x08 l16-s6: start 2026-10-18T03:25:32Z; end ('2026-10-18T04:43:34Z', '0'); 100 original rows; receipt PID/PGID 1869384/1869384; worker statuses {'1884912': 0, '1884924': 0, '1884948': 0, '1884970': 0, '1884977': 0, '1884983': 0, '1884991': 0, '1884997': 0, '1884999': 0, '1885001': 0}.
  Bank SHA256: c11ef110c71b836f8766b394a23b72a639c0d9a5be8c325a6116024a1e37ff69  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/l16-s6/bank.json
- 127x08 l16-s7: start 2026-10-18T03:25:33Z; end ('2026-10-18T04:42:00Z', '0'); 100 original rows; receipt PID/PGID 1869407/1869407; worker statuses {'1885274': 0, '1885275': 0, '1885276': 0, '1885278': 0, '1885292': 0, '1885297': 0, '1885303': 0, '1885308': 0, '1885315': 0, '1885325': 0}.
  Bank SHA256: 77d21a41eca0a0d5c657ea4cf113c4c4fc096b48289ea3d01eb9e7d157341ea5  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/l16-s7/bank.json
- 127x08 acc-s4: start 2026-10-18T03:25:34Z; end ('2026-10-18T04:53:16Z', '0'); 100 original rows; receipt PID/PGID 1869430/1869430; worker statuses {'1885595': 0, '1885602': 0, '1885610': 0, '1885613': 0, '1885615': 0, '1885619': 0, '1885626': 0, '1885628': 0, '1885632': 0, '1885650': 0}.
  Bank SHA256: 9fad113424ae961095486754768f3aa8432d2746b981b9e2312081f4970660ad  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/acc-s4/bank.json
- 127x08 acc-s5: start 2026-10-18T03:25:35Z; end ('2026-10-18T04:45:08Z', '0'); 100 original rows; receipt PID/PGID 1869454/1869454; worker statuses {'1886454': 0, '1886459': 0, '1886464': 0, '1886469': 0, '1886476': 0, '1886480': 0, '1886483': 0, '1886489': 0, '1886496': 0, '1886509': 0}.
  Bank SHA256: f85d2fd7adf7da06d248cc62bf245760be982e190e16cdbc083bf3d26ede00cd  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/acc-s5/bank.json
- 127x08 acc-s6: start 2026-10-18T03:25:36Z; end ('2026-10-18T04:45:05Z', '0'); 100 original rows; receipt PID/PGID 1869508/1869508; worker statuses {'1886297': 0, '1886301': 0, '1886302': 0, '1886305': 0, '1886313': 0, '1886330': 0, '1886341': 0, '1886352': 0, '1886364': 0, '1886373': 0}.
  Bank SHA256: 18aa250ebd657841b3d5d004d5d1ba1500bbcd6ac46ce0c3014c5f547081c236  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/acc-s6/bank.json
- 127x08 acc-s7: start 2026-10-18T03:25:37Z; end ('2026-10-18T04:44:24Z', '0'); 100 original rows; receipt PID/PGID 1869561/1869561; worker statuses {'1886300': 0, '1886304': 0, '1886308': 0, '1886311': 0, '1886321': 0, '1886334': 0, '1886338': 0, '1886348': 0, '1886362': 0, '1886374': 0}.
  Bank SHA256: dc906c92b4b444bcd841d2cdc482dd3baf9740eda55bd5a91fac38311172237f  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/hpc1/acc-s7/bank.json


## Smoke comparison

Smoke s2 on 127x04, bank 0x5A12, ended 2026-10-18T03:44:00Z rc 0; comparison generated 2026-10-18T03:48:12Z. SHA256 is computed over `json.dumps(result.command_events, sort_keys=True).encode()` for each complete case.

| Case | Arm | Full command-event SHA256 | Same as plain | Win | Issues |
| --- | --- | --- | --- | --- | --- |
| 0 | res-lb-LP26-wintp | 0856b5fecd842221ee71b3ebe1a3a953b7baa6db70400c8a3aeec22589c73569 | True | 1 | [] |
| 0 | res-lb-RF-LP26-wintp | 27be8b037150414f413463af4247ad2a288e480ecacda66354a49e410bd16e05 | False | 1 | [] |
| 0 | res-lb-RF-wintp | 167043a5ad9c47b7216b08c876df21637cd8d0cfb6d76ba9d071ffe1191dfb26 | False | 1 | [] |
| 0 | res-lb-hk16-fv2-wintp | 3c91eae3c78f3a38104f1c09366d0f71fbc71d911ed5d8bcc4387cebcdb37667 | False | 1 | [] |
| 0 | res-lb-hk16-wintp | 3c91eae3c78f3a38104f1c09366d0f71fbc71d911ed5d8bcc4387cebcdb37667 | False | 1 | [] |
| 0 | res-lb-wintp | 0856b5fecd842221ee71b3ebe1a3a953b7baa6db70400c8a3aeec22589c73569 | True | 1 | [] |
| 1 | res-lb-LP26-wintp | b959058c4c1f2a4b3238021385c30589e34cf79619ee67206845aba3c6f4ee51 | False | 1 | ['unmapped public rows'] |
| 1 | res-lb-RF-LP26-wintp | 5ee6a05109632c3bf5e1e897c3a8fe7a537f271e7463b2e530f6b41e19ae856e | False | 1 | ['unmapped public rows'] |
| 1 | res-lb-RF-wintp | 4c9981f13c11b70c4fbed3cf41f6ac2f5ccb0c50b4d1e1bedaaf4b36a3660559 | False | 1 | [] |
| 1 | res-lb-hk16-fv2-wintp | 03a154b892f34dc6ce287e7a664d6df020ec0e5c95601e8babbd20ebbe52fc73 | False | 1 | ['unmapped public rows'] |
| 1 | res-lb-hk16-wintp | 03a154b892f34dc6ce287e7a664d6df020ec0e5c95601e8babbd20ebbe52fc73 | False | 1 | ['unmapped public rows'] |
| 1 | res-lb-wintp | 90c2885028eeda96ba593400a6a03890059f50704258d4b65ec8d28760c9db5e | True | 0 | ['unmapped public rows'] |

`res-lb-hk16-wintp` is identical to plain on cases [].

`res-lb-hk16-fv2-wintp` is identical to plain on cases [].

`res-lb-RF-wintp` is identical to plain on cases [].

`res-lb-LP26-wintp` is identical to plain on cases [0].

`res-lb-RF-LP26-wintp` is identical to plain on cases [].

The hk16 proposer changes command events in both cases; the identical-hk16-to-plain alarm does not trigger. hk16-fv2 and hk16 match each other in both cases, consistent with the serial twin having no cutoff. Case 1 has expected SpearGoblin_Dummy unmapped-row notices in plain/hk16/hk16-fv2/LP26/RF-LP26; the runner explicitly permits that no-counterpart sprite, and the main-study pool excludes Goblin Hut. No smoke error rows.

