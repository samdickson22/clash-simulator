# LP2 results

Preregistration: [LP2-PREREG.md](LP2-PREREG.md). `l16` denotes L16; `acc` denotes the account row.

Readout generated 2026-10-18T06:41:44Z. Reference `res-lb-RF-wintp`; treatment `res-lb-RF-LP26-wintp`.

**Ship: FAIL.** Pooled K4CW lower-bound criterion: FAIL; neither-row-below−0.02 criterion: PASS; pooled metrics-within-2-SE criterion: PASS.

Metrics worse beyond 2 paired SE: none among gated pooled metrics. LP2 allows approximately 2 SE of worsening. This readout uses a strict adverse delta >2 paired-game SE threshold on the pooled both-opponent metrics, retaining RF1 metric definitions. CPU, play counts and Cannon location are descriptive. Row-specific SEs are reported separately.

**Row-level metric sensitivity: FAIL.** L16 elixir at crossing decreased by -0.09974, paired SE 0.02319 (4.30 SE adverse). The primary metric check follows RF1 pooled metrics; applying the same guardrail separately to each level row also rejects LP2. Overall ship FAIL is unchanged under either interpretation.

## Targeted LP metrics

| Level row | Target metric | Reference | LP26 | Delta (pp) | Paired SE (pp) |
| --- | --- | --- | --- | --- | --- |
| l16 | barrel_answer_share | 0.1083 | 0.1210 | +1.271 | 1.543 |
| acc | barrel_answer_share | 0.1049 | 0.1190 | +1.406 | 1.808 |
| pooled | barrel_answer_share | 0.1065 | 0.1200 | +1.343 | 1.199 |
| l16 | Zap_enemy_in_radius_share | 0.5492 | 0.5659 | +1.666 | 1.308 |
| acc | Zap_enemy_in_radius_share | 0.5105 | 0.5066 | -0.389 | 1.423 |
| pooled | Zap_enemy_in_radius_share | 0.5295 | 0.5348 | +0.528 | 0.970 |
| l16 | Fireball_enemy_in_radius_share | 0.4838 | 0.5069 | +2.314 | 3.347 |
| acc | Fireball_enemy_in_radius_share | 0.5242 | 0.5224 | -0.177 | 3.132 |
| pooled | Fireball_enemy_in_radius_share | 0.5040 | 0.5155 | +1.145 | 2.284 |

## Data integrity

Raw rows: 1600; unique valid rows: 1600; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'l16': 800, 'acc': 800}`. Hosts: `{'127x04': 800, '127x08': 800}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw`. Completion and rerun history is in the appended run audit.

Exactly 200 paired cases per opponent per level row; 400 pairs per opponent pooled over L16/account. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | Both opponents treatment − reference, 95% CI |
| --- | --- | --- | --- |
| l16 | +0.0750 [+0.0100, +0.1400] (n=200) | +0.0150 [-0.0350, +0.0700] (n=200) | +0.0450 [+0.0025, +0.0875] (n=400) |
| acc | +0.0100 [-0.0700, +0.0900] (n=200) | +0.0050 [-0.0600, +0.0750] (n=200) | +0.0075 [-0.0450, +0.0575] (n=400) |
| pooled | +0.0425 [-0.0075, +0.0950] (n=400) | +0.0100 [-0.0325, +0.0525] (n=400) | +0.0262 [-0.0075, +0.0612] (n=800) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | Both score |
| --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 400 | 0.715 | 0.890 | 0.802 |
| l16 | res-lb-RF-LP26-wintp | 400 | 0.790 | 0.905 | 0.848 |
| acc | res-lb-RF-wintp | 400 | 0.515 | 0.635 | 0.575 |
| acc | res-lb-RF-LP26-wintp | 400 | 0.525 | 0.640 | 0.583 |
| pooled | res-lb-RF-wintp | 800 | 0.615 | 0.762 | 0.689 |
| pooled | res-lb-RF-LP26-wintp | 800 | 0.657 | 0.772 | 0.715 |


## Standing play-quality metrics (both opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 598.3 | 1.500/5.750 | 3.25/3.12 | 0.004 | 0.071 | 0.543 | 0.263 |
| l16 | res-lb-RF-LP26-wintp | 699.6 | 1.500/5.500 | 3.15/3.03 | 0.002 | 0.064 | 0.540 | 0.264 |
| acc | res-lb-RF-wintp | 586.8 | 1.500/5.500 | 3.22/3.07 | 0.002 | 0.055 | 0.546 | 0.271 |
| acc | res-lb-RF-LP26-wintp | 698.6 | 1.500/5.500 | 3.25/3.14 | 0.002 | 0.057 | 0.532 | 0.271 |
| pooled | res-lb-RF-wintp | 592.5 | 1.500/5.500 | 3.24/3.11 | 0.003 | 0.063 | 0.545 | 0.267 |
| pooled | res-lb-RF-LP26-wintp | 699.0 | 1.500/5.500 | 3.20/3.09 | 0.002 | 0.060 | 0.536 | 0.268 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 873 | 3.136 | 2.928 | 0.029 | 0.288 |
| l16 | res-lb-RF-LP26-wintp | 853 | 3.104 | 2.964 | 0.025 | 0.300 |
| acc | res-lb-RF-wintp | 906 | 3.167 | 3.000 | 0.022 | 0.312 |
| acc | res-lb-RF-LP26-wintp | 927 | 3.122 | 2.964 | 0.024 | 0.309 |
| pooled | res-lb-RF-wintp | 1779 | 3.152 | 2.964 | 0.025 | 0.300 |
| pooled | res-lb-RF-LP26-wintp | 1780 | 3.113 | 2.964 | 0.024 | 0.304 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | Fireball | 1.010 | 404 | 370 | 0.484 |
| l16 | res-lb-RF-wintp | Zap | 5.200 | 2080 | 2072 | 0.549 |
| l16 | res-lb-RF-wintp | ElectroSpirit | 7.617 | 3047 | 3012 | 0.214 |
| l16 | res-lb-RF-LP26-wintp | Fireball | 0.975 | 390 | 361 | 0.507 |
| l16 | res-lb-RF-LP26-wintp | Zap | 5.175 | 2070 | 2064 | 0.566 |
| l16 | res-lb-RF-LP26-wintp | ElectroSpirit | 7.585 | 3034 | 2996 | 0.226 |
| acc | res-lb-RF-wintp | Fireball | 1.012 | 405 | 372 | 0.524 |
| acc | res-lb-RF-wintp | Zap | 5.402 | 2161 | 2149 | 0.510 |
| acc | res-lb-RF-wintp | ElectroSpirit | 7.730 | 3092 | 3059 | 0.212 |
| acc | res-lb-RF-LP26-wintp | Fireball | 1.185 | 474 | 446 | 0.522 |
| acc | res-lb-RF-LP26-wintp | Zap | 5.735 | 2294 | 2278 | 0.507 |
| acc | res-lb-RF-LP26-wintp | ElectroSpirit | 8.217 | 3287 | 3249 | 0.234 |
| pooled | res-lb-RF-wintp | Fireball | 1.011 | 809 | 742 | 0.504 |
| pooled | res-lb-RF-wintp | Zap | 5.301 | 4241 | 4221 | 0.529 |
| pooled | res-lb-RF-wintp | ElectroSpirit | 7.674 | 6139 | 6071 | 0.213 |
| pooled | res-lb-RF-LP26-wintp | Fireball | 1.080 | 864 | 807 | 0.515 |
| pooled | res-lb-RF-LP26-wintp | Zap | 5.455 | 4364 | 4342 | 0.535 |
| pooled | res-lb-RF-LP26-wintp | ElectroSpirit | 7.901 | 6321 | 6245 | 0.230 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 434 | 47 | 0.108 | 0.083 | 1839 | 0.013 | 0.987 |
| l16 | res-lb-RF-LP26-wintp | 438 | 53 | 0.121 | 0.096 | 1814 | 0.008 | 0.992 |
| acc | res-lb-RF-wintp | 486 | 51 | 0.105 | 0.078 | 1970 | 0.009 | 0.991 |
| acc | res-lb-RF-LP26-wintp | 479 | 57 | 0.119 | 0.084 | 1977 | 0.009 | 0.991 |
| pooled | res-lb-RF-wintp | 920 | 98 | 0.107 | 0.080 | 3809 | 0.011 | 0.989 |
| pooled | res-lb-RF-LP26-wintp | 917 | 110 | 0.120 | 0.089 | 3791 | 0.008 | 0.992 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Paired SE | Gate: adverse >2 SE |
| --- | --- | --- | --- | --- | --- |
| barrel_answer_share | 0.10652 | 0.11996 | 0.01343 | 0.01199 | no |
| Zap_enemy_in_radius_share | 0.52950 | 0.53478 | 0.00528 | 0.00970 | no |
| Fireball_enemy_in_radius_share | 0.50404 | 0.51549 | 0.01145 | 0.02284 | no |
| cpu_ms_per_decision_pooled | 592.50581 | 699.04825 | 106.54244 | 4.82593 | descriptive |
| enemy_to_our_play_p50 | 1.50000 | 1.50000 | 0.00000 | 0.00000 | no |
| enemy_to_our_play_p90 | 5.50000 | 5.50000 | 0.00000 | 0.08219 | no |
| elixir_at_cross_mean | 3.23543 | 3.20262 | -0.03280 | 0.01749 | no |
| wincon_spend_share | 0.06307 | 0.06029 | -0.00278 | 0.00520 | no |
| idle_play_share | 0.54467 | 0.53581 | -0.00886 | 0.00415 | no |
| wrong_lane_share | 0.26687 | 0.26761 | 0.00074 | 0.00387 | no |
| hog_elixir_mean | 3.15196 | 3.11343 | -0.03853 | 0.03634 | no |
| hog_elixir_ge6 | 0.02530 | 0.02416 | -0.00114 | 0.00410 | no |
| hog_cannon_and_ge3 | 0.30017 | 0.30449 | 0.00433 | 0.01324 | no |
| ElectroSpirit_enemy_in_radius_share | 0.21298 | 0.23042 | 0.01744 | 0.00695 | no |


LP2 rows record lag-projection counters separately in `lagproj_stats`; the measured counters and their denominators are reported below. No selected-play attribution is inferred from packet statistics.

## Analysis artifacts and reproducibility

- l16 hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/hz-l16.json`

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2/readout-data.json`

Each hz_report was executed from the staged tree with its Python 3.12 environment, `PYTHONPATH=TREE`, `python -m bot.fullpool.hz_report DIR --ref res-lb-RF-wintp --arms TREATMENT --gate TREATMENT --gate-opponent LIVE-K4CW-r16-fp --json OUT`. Normalized inputs preserve the first valid occurrence of each (level row, player, opponent, index). Pooled copies namespace index as `level-row:index` to prevent hz_report from treating the same numeric index in L16/account as a duplicate. Raw rows are retained unchanged.

Computed source SHA256s at readout generation:
```text
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-656771761ba1/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-656771761ba1/bot/fullpool/scale_report.py
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/score_study.py
f044645d93f70ef0ef4e74297f75e008905d7991d29b9f8dc6f24472eb2f3a99  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/render_report.py
```

## Run completion audit

2026-10-18T06:37:48Z
Original successful shards with 100 rows: 16/16. Earliest logged start 2026-10-18T05:09:04Z; latest end 2026-10-18T06:30:36Z.
- 127x04 l16-s0: start 2026-10-18T05:09:20Z; end ('2026-10-18T05:43:38Z', '0'); 100 original rows; receipt PID/PGID 805319/805319; worker statuses {'907498': 0, '907499': 0, '907502': 0, '907503': 0, '907519': 0, '907525': 0, '907532': 0, '907550': 0, '907578': 0, '907595': 0}.
  Bank SHA256: f75cfd8daebec90659c059c4789e473a720c79666d03b404fba1d38a597d08f7  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/l16-s0/bank.json
- 127x04 l16-s1: start 2026-10-18T05:09:22Z; end ('2026-10-18T05:44:05Z', '0'); 100 original rows; receipt PID/PGID 805348/805348; worker statuses {'907247': 0, '907249': 0, '907250': 0, '907256': 0, '907264': 0, '907271': 0, '907279': 0, '907287': 0, '907295': 0, '907301': 0}.
  Bank SHA256: e092135d2d30cde9441991bc5e9350be7bdfa35ab4c2e3bddd7003c484075b4c  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/l16-s1/bank.json
- 127x04 l16-s2: start 2026-10-18T05:09:04Z; end ('2026-10-18T05:43:01Z', '0'); 100 original rows; receipt PID/PGID 805384/805384; worker statuses {'906024': 0, '906031': 0, '906040': 0, '906050': 0, '906058': 0, '906066': 0, '906072': 0, '906074': 0, '906076': 0, '906078': 0}.
  Bank SHA256: 116187c76b0fcd7d948bd5f8a07a93e4e02758e7e04aac03e8f776d90057d434  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/l16-s2/bank.json
- 127x04 l16-s3: start 2026-10-18T05:09:28Z; end ('2026-10-18T05:45:18Z', '0'); 100 original rows; receipt PID/PGID 805430/805430; worker statuses {'908214': 0, '908216': 0, '908218': 0, '908221': 0, '908223': 0, '908225': 0, '908234': 0, '908246': 0, '908253': 0, '908264': 0}.
  Bank SHA256: 7d7fb7bc5b5dc0ff838df21a9328935b9816592cc8ccbb1cfe1b92a73057cfa7  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/l16-s3/bank.json
- 127x04 acc-s0: start 2026-10-18T05:09:52Z; end ('2026-10-18T05:44:02Z', '0'); 100 original rows; receipt PID/PGID 805476/805476; worker statuses {'912461': 0, '912468': 0, '912475': 0, '912479': 0, '912488': 0, '912508': 0, '912516': 0, '912524': 0, '912533': 0, '912542': 0}.
  Bank SHA256: ac313c46d299a257162719b751ac887f72e1c0ec7ee8658d33f0617d562bc2c0  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/acc-s0/bank.json
- 127x04 acc-s1: start 2026-10-18T05:09:54Z; end ('2026-10-18T05:45:44Z', '0'); 100 original rows; receipt PID/PGID 805520/805520; worker statuses {'912460': 0, '912467': 0, '912473': 0, '912477': 0, '912482': 0, '912501': 0, '912514': 0, '912522': 0, '912535': 0, '912543': 0}.
  Bank SHA256: f263aa63d1778b95f011eeb69c0a8a25d4422782e28d0b8db1cf72e40cbdf98e  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/acc-s1/bank.json
- 127x04 acc-s2: start 2026-10-18T05:09:12Z; end ('2026-10-18T05:46:33Z', '0'); 100 original rows; receipt PID/PGID 805545/805545; worker statuses {'905896': 0, '905897': 0, '905902': 0, '905904': 0, '905909': 0, '905925': 0, '905933': 0, '905941': 0, '905947': 0, '905957': 0}.
  Bank SHA256: c46442f0454d6565f79d11c6776c4154e74d88f4f0ad404259c819b299e7550d  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/acc-s2/bank.json
- 127x04 acc-s3: start 2026-10-18T05:09:57Z; end ('2026-10-18T05:44:44Z', '0'); 100 original rows; receipt PID/PGID 805586/805586; worker statuses {'911837': 0, '911845': 0, '911878': 0, '911900': 0, '911905': 0, '911913': 0, '911921': 0, '911927': 0, '911933': 0, '911941': 0}.
  Bank SHA256: d303eebb794a2b5b591d3dffe04a6ae9ccc01962d9eb109ebf40308aba5ea8e1  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/lp2/acc-s3/bank.json
- 127x08 l16-s4: start 2026-10-18T05:29:44Z; end ('2026-10-18T06:28:41Z', '0'); 100 original rows; receipt PID/PGID 2505809/2505809; worker statuses {'2770909': 0, '2770910': 0, '2770913': 0, '2770921': 0, '2770928': 0, '2770934': 0, '2770937': 0, '2770944': 0, '2770955': 0, '2770963': 0}.
  Bank SHA256: 55c6bef3f778525afa675d4bc5875b886436a225ac5ea4050b40032c028b4c27  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/l16-s4/bank.json
- 127x08 l16-s5: start 2026-10-18T05:29:46Z; end ('2026-10-18T06:30:36Z', '0'); 100 original rows; receipt PID/PGID 2505854/2505854; worker statuses {'2768481': 0, '2768489': 0, '2768496': 0, '2768504': 0, '2768510': 0, '2768518': 0, '2768527': 0, '2768535': 0, '2768543': 0, '2768552': 0}.
  Bank SHA256: 088297127d3c1760afd12de5de311d8e8825874f34f4961d2ec68da5f696ecc3  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/l16-s5/bank.json
- 127x08 l16-s6: start 2026-10-18T05:29:49Z; end ('2026-10-18T06:28:07Z', '0'); 100 original rows; receipt PID/PGID 2505895/2505895; worker statuses {'2774977': 0, '2774989': 0, '2774992': 0, '2775006': 0, '2775023': 0, '2775039': 0, '2775054': 0, '2775069': 0, '2775080': 0, '2775093': 0}.
  Bank SHA256: 600d881b7a6f524c9f819ca7dfcb24ec693a405de9175b3f802d0b52784de2f7  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/l16-s6/bank.json
- 127x08 l16-s7: start 2026-10-18T05:29:29Z; end ('2026-10-18T06:27:27Z', '0'); 100 original rows; receipt PID/PGID 2505932/2505932; worker statuses {'2768084': 0, '2768092': 0, '2768099': 0, '2768105': 0, '2768113': 0, '2768119': 0, '2768127': 0, '2768133': 0, '2768139': 0, '2768145': 0}.
  Bank SHA256: 0d849ad2f21d987ca41397ed1c029d77cfe63b95eb1a9dc7f7e7c375c652b771  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/l16-s7/bank.json
- 127x08 acc-s4: start 2026-10-18T05:29:31Z; end ('2026-10-18T06:28:49Z', '0'); 100 original rows; receipt PID/PGID 2505998/2505998; worker statuses {'2770619': 0, '2770624': 0, '2770631': 0, '2770637': 0, '2770643': 0, '2770650': 0, '2770655': 0, '2770663': 0, '2770668': 0, '2770671': 0}.
  Bank SHA256: 1a26ee3f298767698b4e706ff28c27a91d93f5d19c2b67fa28eebc79a63215eb  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/acc-s4/bank.json
- 127x08 acc-s5: start 2026-10-18T05:29:35Z; end ('2026-10-18T06:27:48Z', '0'); 100 original rows; receipt PID/PGID 2506056/2506056; worker statuses {'2767986': 0, '2767991': 0, '2767993': 0, '2767995': 0, '2767997': 0, '2767999': 0, '2768005': 0, '2768020': 0, '2768028': 0, '2768034': 0}.
  Bank SHA256: 115f0673912b3f2a28d9af10a0eb5e229840b50ed1dff6e7a5cb90318f4b48b1  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/acc-s5/bank.json
- 127x08 acc-s6: start 2026-10-18T05:29:37Z; end ('2026-10-18T06:29:36Z', '0'); 100 original rows; receipt PID/PGID 2506102/2506102; worker statuses {'2768912': 0, '2768914': 0, '2768916': 0, '2768922': 0, '2768924': 0, '2768927': 0, '2768930': 0, '2768931': 0, '2768933': 0, '2768953': 0}.
  Bank SHA256: 5b2014de0d2d0ec855e9c0e5e18f26de5e8f38377208a13b850393eac9bc8628  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/acc-s6/bank.json
- 127x08 acc-s7: start 2026-10-18T05:29:41Z; end ('2026-10-18T06:28:15Z', '0'); 100 original rows; receipt PID/PGID 2506137/2506137; worker statuses {'2768700': 0, '2768706': 0, '2768715': 0, '2768721': 0, '2768729': 0, '2768735': 0, '2768741': 0, '2768753': 0, '2768765': 0, '2768771': 0}.
  Bank SHA256: 9ffa3ac7b3aa79f718f2d7a54deb39d295e643de441a91fd5e1af0d417ba2ab2  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/lp2/acc-s7/bank.json



## Standard errors and LP2 metric rule

A paired case is (level row, opponent, index), exactly as in RF1. For a pooled ratio m=sum(x)/sum(y), the game influence is n*(x_i-m*y_i)/sum(y). The delta SE is sample SD of treatment-minus-reference game influences divided by sqrt(n). This preserves pairing and allows within-game event dependence. For reaction p50/p90, SE is the sample SD of 4000 paired-case bootstrap deltas, NumPy default_rng(0), with the unchanged l16_report.q zero-based floor(f*n) quantile. These are metric SEs; score CIs above remain the exact RF1 random.Random(0) bootstrap. No multiplicity adjustment is applied.

The metric gate uses pooled both-opponent results, following RF1 pooling; an adverse delta must exceed 2*SE to fail. Ratios use unrounded event totals for the check. More elixir at crossings, Cannon-plus-elixir availability, Barrel answers and observed hit shares are better; shorter reaction, lower idle/wrong-lane/wincon-spend shares are better. CPU, play frequency and Cannon centre placement remain descriptive. Row-specific adverse flags below are diagnostic.

| Level row | Metric | Delta | Paired SE | Adverse >2 SE |
| --- | --- | --- | --- | --- |
| l16 | elixir_at_cross_mean | -0.099739 | 0.023193 | yes |
| l16 | wincon_spend_share | -0.007467 | 0.007475 | no |
| l16 | idle_play_share | -0.003255 | 0.005724 | no |
| l16 | wrong_lane_share | 0.000764 | 0.005385 | no |
| l16 | hog_elixir_mean | -0.032205 | 0.052279 | no |
| l16 | hog_elixir_ge6 | -0.004018 | 0.006029 | no |
| l16 | hog_cannon_and_ge3 | 0.012603 | 0.019618 | no |
| l16 | barrel_answer_share | 0.012710 | 0.015434 | no |
| l16 | Fireball_enemy_in_radius_share | 0.023141 | 0.033472 | no |
| l16 | Zap_enemy_in_radius_share | 0.016664 | 0.013077 | no |
| l16 | ElectroSpirit_enemy_in_radius_share | 0.011826 | 0.009423 | no |
| l16 | enemy_to_our_play_p50 | 0.000000 | 0.000000 | no |
| l16 | enemy_to_our_play_p90 | -0.250000 | 0.151346 | no |
| acc | elixir_at_cross_mean | 0.031660 | 0.025573 | no |
| acc | wincon_spend_share | 0.001852 | 0.007236 | no |
| acc | idle_play_share | -0.014097 | 0.005973 | no |
| acc | wrong_lane_share | 0.000450 | 0.005555 | no |
| acc | hog_elixir_mean | -0.045042 | 0.050563 | no |
| acc | hog_elixir_ge6 | 0.001657 | 0.005558 | no |
| acc | hog_cannon_and_ge3 | -0.003840 | 0.017922 | no |
| acc | barrel_answer_share | 0.014060 | 0.018080 | no |
| acc | Fireball_enemy_in_radius_share | -0.001772 | 0.031321 | no |
| acc | Zap_enemy_in_radius_share | -0.003885 | 0.014233 | no |
| acc | ElectroSpirit_enemy_in_radius_share | 0.022719 | 0.010180 | no |
| acc | enemy_to_our_play_p50 | 0.000000 | 0.000000 | no |
| acc | enemy_to_our_play_p90 | 0.000000 | 0.029376 | no |
| pooled | elixir_at_cross_mean | -0.032802 | 0.017486 | no |
| pooled | wincon_spend_share | -0.002779 | 0.005203 | no |
| pooled | idle_play_share | -0.008859 | 0.004152 | no |
| pooled | wrong_lane_share | 0.000739 | 0.003869 | no |
| pooled | hog_elixir_mean | -0.038529 | 0.036335 | no |
| pooled | hog_elixir_ge6 | -0.001138 | 0.004104 | no |
| pooled | hog_cannon_and_ge3 | 0.004326 | 0.013240 | no |
| pooled | barrel_answer_share | 0.013435 | 0.011995 | no |
| pooled | Fireball_enemy_in_radius_share | 0.011446 | 0.022835 | no |
| pooled | Zap_enemy_in_radius_share | 0.005281 | 0.009704 | no |
| pooled | ElectroSpirit_enemy_in_radius_share | 0.017445 | 0.006946 | no |
| pooled | enemy_to_our_play_p50 | 0.000000 | 0.000000 | no |
| pooled | enemy_to_our_play_p90 | 0.000000 | 0.082191 | no |


## Additional standing metrics

| Level row | Arm | Decision reaction p50/p90 s | Giant undefended share / pushes | Incursions/game | Incursion undefended ≤5s |
| --- | --- | --- | --- | --- | --- |
| l16 | res-lb-RF-wintp | 0.150/1.150 | 0.060 / 100 | 14.22 | 0.134 |
| l16 | res-lb-RF-LP26-wintp | 0.150/0.900 | 0.022 / 92 | 14.05 | 0.147 |
| acc | res-lb-RF-wintp | 0.150/0.900 | 0.056 / 107 | 14.38 | 0.137 |
| acc | res-lb-RF-LP26-wintp | 0.150/1.150 | 0.095 / 95 | 14.74 | 0.131 |
| pooled | res-lb-RF-wintp | 0.150/0.900 | 0.058 / 207 | 14.30 | 0.136 |
| pooled | res-lb-RF-LP26-wintp | 0.150/1.150 | 0.059 / 187 | 14.39 | 0.139 |


## Lag-projected candidate counters

| Level row | LP games | Candidates added | LP decisions | Added/decision | LP errors |
| --- | --- | --- | --- | --- | --- |
| l16 | 400 | 228066 | 55572 | 4.103973 | 0 |
| acc | 400 | 247360 | 58819 | 4.205444 | 0 |
| pooled | 800 | 475426 | 114391 | 4.156149 | 0 |


The LP decision totals equal the own-seat timing decision totals in every level-row aggregate. Reference has no LP installation. Counts sum unique rows once. Study CPU times come from serial-twin runs without a live deadline; they do not measure compliance with the 200 ms live wall.

## Operational audit

All 16 original shards succeeded with 100 rows each and worker status 0. No game reruns were needed. Watch checks ran in a Sol-owned shell loop at 600-second intervals on 127x04/127x08; other hosts/jobs were untouched. The first path check found the RF1 analysis scripts absent on 127x04; exact SHA256-matching originals were recovered from 127x05 and copied unchanged to 127x04. A supplemental-analysis JSON serialization error (NumPy boolean) was corrected and that analysis rerun successfully. These analysis-only failures did not alter game data. No commits or bot code edits were made.

The unchanged RF1 scorer was executed on 127x04 with only study/base/reference/treatment/tree parameters substituted in memory; the renderer was parameterized for LP2 and its pre-registered 2-SE rule. Original script files remain unchanged. Runtime substitutions are saved as scorer-parameters.json and renderer-parameters.json. Metric SEs and per-case sufficient statistics are in metric-se.json and per-case-features.json; LP counters are in lagproj-metrics.json. All are under /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/lp2.
