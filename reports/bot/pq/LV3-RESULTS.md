# LV3 results

Preregistration: [LV3-PREREG.md](LV3-PREREG.md). Account levels only; the account and pooled rows contain the same games. Extended metrics use the same definitions and identical analysis functions as [RF1-RESULTS.md](RF1-RESULTS.md).

Readout generated 2026-10-18T06:21:15Z. Reference `res-lb-wintp`; treatment `res-lb-PLr-wintp`.

**Ship: FAIL.** K4CW score criterion: FAIL; literal metrics-not-worse criterion: FAIL. LV3 requires lower bound >0, or lower bound ≥0 with point >+0.02.

Metrics with worse point estimates: cpu_ms_per_decision_pooled, hog_elixir_ge6, hog_cannon_and_ge3, barrel_answer_share. The preregistration does not define metric tolerances or a composite gate. This readout applies a conservative zero-tolerance point-estimate check to the observable metrics below; play counts and Cannon location are descriptive. No metric-significance claim is made.

## Data integrity

Raw rows: 1200; unique valid rows: 1200; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'acc': 1200}`. Hosts: `{'127x04': 600, '127x08': 600}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/raw`. Completion and rerun history is in the appended run audit.

Exactly 300 paired cases per opponent, account levels only. Opponents use separate seeds as registered. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | Both opponents treatment − reference, 95% CI |
| --- | --- | --- | --- |
| acc | +0.0100 [-0.0567, +0.0733] (n=300) | +0.0067 [-0.0633, +0.0733] (n=300) | +0.0083 [-0.0383, +0.0533] (n=600) |
| pooled | +0.0100 [-0.0567, +0.0733] (n=300) | +0.0067 [-0.0633, +0.0733] (n=300) | +0.0083 [-0.0383, +0.0533] (n=600) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | Both score |
| --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | 600 | 0.493 | 0.657 | 0.575 |
| acc | res-lb-PLr-wintp | 600 | 0.503 | 0.663 | 0.583 |
| pooled | res-lb-wintp | 600 | 0.493 | 0.657 | 0.575 |
| pooled | res-lb-PLr-wintp | 600 | 0.503 | 0.663 | 0.583 |


## Standing play-quality metrics (both opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | 624.9 | 1.500/5.500 | 3.28/3.14 | 0.004 | 0.060 | 0.541 | 0.277 |
| acc | res-lb-PLr-wintp | 651.1 | 1.500/5.500 | 3.33/3.21 | 0.005 | 0.055 | 0.537 | 0.266 |
| pooled | res-lb-wintp | 624.9 | 1.500/5.500 | 3.28/3.14 | 0.004 | 0.060 | 0.541 | 0.277 |
| pooled | res-lb-PLr-wintp | 651.1 | 1.500/5.500 | 3.33/3.21 | 0.005 | 0.055 | 0.537 | 0.266 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | 1283 | 3.183 | 3.000 | 0.043 | 0.318 |
| acc | res-lb-PLr-wintp | 1277 | 3.227 | 3.017 | 0.038 | 0.317 |
| pooled | res-lb-wintp | 1283 | 3.183 | 3.000 | 0.043 | 0.318 |
| pooled | res-lb-PLr-wintp | 1277 | 3.227 | 3.017 | 0.038 | 0.317 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | Fireball | 1.162 | 697 | 653 | 0.504 |
| acc | res-lb-wintp | Zap | 5.747 | 3448 | 3419 | 0.518 |
| acc | res-lb-wintp | ElectroSpirit | 8.008 | 4805 | 4746 | 0.225 |
| acc | res-lb-PLr-wintp | Fireball | 1.013 | 608 | 564 | 0.544 |
| acc | res-lb-PLr-wintp | Zap | 5.720 | 3432 | 3409 | 0.527 |
| acc | res-lb-PLr-wintp | ElectroSpirit | 7.912 | 4747 | 4691 | 0.228 |
| pooled | res-lb-wintp | Fireball | 1.162 | 697 | 653 | 0.504 |
| pooled | res-lb-wintp | Zap | 5.747 | 3448 | 3419 | 0.518 |
| pooled | res-lb-wintp | ElectroSpirit | 8.008 | 4805 | 4746 | 0.225 |
| pooled | res-lb-PLr-wintp | Fireball | 1.013 | 608 | 564 | 0.544 |
| pooled | res-lb-PLr-wintp | Zap | 5.720 | 3432 | 3409 | 0.527 |
| pooled | res-lb-PLr-wintp | ElectroSpirit | 7.912 | 4747 | 4691 | 0.228 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | 622 | 32 | 0.051 | 0.050 | 2964 | 0.011 | 0.989 |
| acc | res-lb-PLr-wintp | 659 | 27 | 0.041 | 0.036 | 3145 | 0.008 | 0.992 |
| pooled | res-lb-wintp | 622 | 32 | 0.051 | 0.050 | 2964 | 0.011 | 0.989 |
| pooled | res-lb-PLr-wintp | 659 | 27 | 0.041 | 0.036 | 3145 | 0.008 | 0.992 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Worse point estimate |
| --- | --- | --- | --- | --- |
| cpu_ms_per_decision_pooled | 624.900 | 651.100 | 26.200 | yes |
| enemy_to_our_play_p50 | 1.500 | 1.500 | 0.000 | no |
| enemy_to_our_play_p90 | 5.500 | 5.500 | 0.000 | no |
| elixir_at_cross_mean | 3.280 | 3.330 | 0.050 | no |
| wincon_spend_share | 0.060 | 0.055 | -0.005 | no |
| idle_play_share | 0.541 | 0.537 | -0.004 | no |
| wrong_lane_share | 0.277 | 0.266 | -0.011 | no |
| hog_elixir_mean | 3.183 | 3.227 | 0.044 | no |
| hog_elixir_ge6 | 0.043 | 0.038 | -0.004 | yes |
| hog_cannon_and_ge3 | 0.318 | 0.317 | -0.001 | yes |
| barrel_answer_share | 0.051 | 0.041 | -0.010 | yes |
| Fireball_enemy_in_radius_share | 0.504 | 0.544 | 0.040 | no |
| Zap_enemy_in_radius_share | 0.518 | 0.527 | 0.009 | no |
| ElectroSpirit_enemy_in_radius_share | 0.225 | 0.228 | 0.004 | no |


## Analysis artifacts and reproducibility

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/readout-data.json`

Each hz_report was executed from the staged tree with its Python 3.12 environment, `PYTHONPATH=TREE`, `python -m bot.fullpool.hz_report DIR --ref res-lb-wintp --arms TREATMENT --gate TREATMENT --gate-opponent LIVE-K4CW-r16-fp --json OUT`. Normalized inputs preserve the first valid occurrence of each (level row, player, opponent, index). Pooled copies namespace index as `level-row:index` to prevent hz_report from treating the same numeric index in L16/account as a duplicate. Raw rows are retained unchanged.

Computed source SHA256s at readout generation:
```text
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-656771761ba1/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-656771761ba1/bot/fullpool/scale_report.py
9964c61868573a52928ad0faee174aa102dc2a51c39d0f9094b309bb82938750  /mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/score_study.py
a9c594d1a03be01f6b5fe8e290e9bddb163b4409f2cbc20ee50eb688a279d0e7  /mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/render_report.py
```

## Wins, draws and losses

| Level row | Arm | Opponent | Wins | Draws | Losses |
| --- | --- | --- | --- | --- | --- |
| acc | res-lb-wintp | LIVE-K4CW-r16-fp | 148 | 0 | 152 |
| acc | res-lb-wintp | R3a | 197 | 0 | 103 |
| acc | res-lb-PLr-wintp | LIVE-K4CW-r16-fp | 151 | 0 | 149 |
| acc | res-lb-PLr-wintp | R3a | 199 | 0 | 101 |


## Treatment diagnostics

Instrumentation validity: PASS. LP1 requires zero lag-projection errors; LV3 treatment statuses and revealed levels are checked during scoring.

| Level row | Opponent | PLr games | Status | Reveals | Reveals/game | Reveals changing level | Changes/game | Games with change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | all | 600 | {'exact': 600} | 4234 | 7.057 | 1291 | 2.152 | 489 |
| acc | LIVE-K4CW-r16-fp | 300 | {'exact': 300} | 2108 | 7.027 | 653 | 2.177 | 242 |
| acc | R3a | 300 | {'exact': 300} | 2126 | 7.087 | 638 | 2.127 | 247 |
| pooled | all | 600 | {'exact': 600} | 4234 | 7.057 | 1291 | 2.152 | 489 |
| pooled | LIVE-K4CW-r16-fp | 300 | {'exact': 300} | 2108 | 7.027 | 653 | 2.177 | 242 |
| pooled | R3a | 300 | {'exact': 300} | 2126 | 7.087 | 638 | 2.127 | 247 |


The `revealed` log is a list of (tick, card, observed level, prior level). Each log entry is counted once; a changed level is observed level != prior level. Every treatment status is checked to start with `exact`.

Instrumentation JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lv3/instrumentation.json`.

## Run completion audit

Audit generated 2026-10-18T06:19:51Z.
Completed shards after authorized retries: 8/8. Original rows and all retry rows retained; the scorer checks duplicate identity and exact expected valid case keys.
Staged source revision from STAGED-REV: `656771761ba1`.
- 127x04 acc-s0: start ['2026-10-18T04:31:17Z']; end [('2026-10-18T05:27:01Z', '0')]; expected rows 150; original receipt PID/PGID 197598/197598.
  Output acc-s0: 150 raw rows; worker statuses {'626482': 0, '626492': 0, '626518': 0, '626544': 0, '626556': 0, '626559': 0, '626562': 0, '626564': 0, '626569': 0, '626571': 0}; bank SHA256 `7332810d58d61e8a6a0e2c7f2ffe35db93b1a664212dc602b1ded53ff00b6c6f`.
- 127x04 acc-s1: start ['2026-10-18T04:31:19Z']; end [('2026-10-18T05:32:52Z', '0')]; expected rows 150; original receipt PID/PGID 197648/197648.
  Output acc-s1: 150 raw rows; worker statuses {'627000': 0, '627008': 0, '627016': 0, '627018': 0, '627020': 0, '627026': 0, '627028': 0, '627030': 0, '627032': 0, '627034': 0}; bank SHA256 `2f4bdb16be18b969cab520a9050d1ebaa704ccf011a12013aa0e881ef6ea555b`.
- 127x04 acc-s2: start ['2026-10-18T04:31:22Z']; end [('2026-10-18T05:31:18Z', '0')]; expected rows 150; original receipt PID/PGID 197686/197686.
  Output acc-s2: 150 raw rows; worker statuses {'627425': 0, '627427': 0, '627428': 0, '627430': 0, '627432': 0, '627434': 0, '627436': 0, '627440': 0, '627455': 0, '627462': 0}; bank SHA256 `695d53e03bcd2efddcb4c77aa3822304dbdd4303513ca1a4394606cb1331b271`.
- 127x04 acc-s3: start ['2026-10-18T04:31:24Z']; end [('2026-10-18T05:29:37Z', '0')]; expected rows 150; original receipt PID/PGID 197717/197717.
  Output acc-s3: 150 raw rows; worker statuses {'627532': 0, '627534': 0, '627540': 0, '627542': 0, '627545': 0, '627547': 0, '627549': 0, '627570': 0, '627576': 0, '627584': 0}; bank SHA256 `57e0f06927f44d4bee064aa69643f442b48f67fc0cf094eb35d9f7ef62c9c3a1`.
- 127x08 acc-s4: start ['2026-10-18T04:43:21Z']; end [('2026-10-18T06:13:37Z', '0')]; expected rows 150; original receipt PID/PGID 1904364/1904364.
  Output acc-s4: 150 raw rows; worker statuses {'2414683': 0, '2414690': 0, '2414694': 0, '2414697': 0, '2414701': 0, '2414707': 0, '2414709': 0, '2414712': 0, '2414715': 0, '2414728': 0}; bank SHA256 `ec0fe2d8c30378ba9a277013d7b3f6a8ab88fef4ec4b0c153192c884a9e88eac`.
- 127x08 acc-s5: start ['2026-10-18T04:43:23Z']; end [('2026-10-18T06:08:58Z', '0')]; expected rows 150; original receipt PID/PGID 1904409/1904409.
  Output acc-s5: 150 raw rows; worker statuses {'2414885': 0, '2414890': 0, '2414898': 0, '2414906': 0, '2414912': 0, '2414918': 0, '2414927': 0, '2414936': 0, '2414944': 0, '2414950': 0}; bank SHA256 `849344fc6e62aea5eb4011c923b450e978f88bbf5ee866b4a231606619b4a3e1`.
- 127x08 acc-s6: start ['2026-10-18T04:43:25Z']; end [('2026-10-18T06:15:46Z', '0')]; expected rows 150; original receipt PID/PGID 1904460/1904460.
  Output acc-s6: 150 raw rows; worker statuses {'2414043': 0, '2414051': 0, '2414060': 0, '2414066': 0, '2414074': 0, '2414085': 0, '2414093': 0, '2414101': 0, '2414103': 0, '2414105': 0}; bank SHA256 `c166f80c715a4220ad20f63c4a42608c76b8d66ffca61b6029a16ceab43e830b`.
- 127x08 acc-s7: start ['2026-10-18T04:43:03Z']; end [('2026-10-18T06:18:04Z', '0')]; expected rows 150; original receipt PID/PGID 1904495/1904495.
  Output acc-s7: 150 raw rows; worker statuses {'2412590': 0, '2412591': 0, '2412593': 0, '2412595': 0, '2412601': 0, '2412603': 0, '2412605': 0, '2412607': 0, '2412609': 0, '2412612': 0}; bank SHA256 `83ac2b4bf563372385ff229b97b81f34fc5ab8fcec49e08fe3505c1063b4781f`.
Bank source pin population_sha256: `2cff081966197616e9e99cdd34e79eb08737d02b16ddd7b704156cf637ae5850`.
Bank source pin vocab_sha256: `f588168f9def92fff7ca6660778cb87bb1dd5224be7bea6a21892c6b6721192c`.
Bank source pin driver_sha256: `3a6b099788de221a4e4dc00ff02137e17e03a314dbb4fbb8eeedfaf34fbee17d`.
Bank source pin factory_sha256: `0b8181c805a6e748c970e22936c8b1311f6fe8fb1c18d7d1c317532a5d28680a`.
Bank source pin plan_table_sha256: `81e1f4b0c6ef7974ff790f3a5535ff36e931d37f61c6f77e897a147c8bf2c9f9`.


## Smoke comparison

Smoke audit generated 2026-10-18T04:54:13Z.

Smoke s4: four completed rows, zero row errors; LP candidate additions 2743 across 600 decisions (4.572/decision), zero projection errors. Both case-1 arms flag `unmapped public rows`; retained and reported to owner. RF1’s smoke readout identifies these as the runner-permitted SpearGoblin_Dummy sprite notice; the main-study pool excludes Goblin Hut and all LV3 study rows have no issues. Smoke s5: two completed rows, zero row errors/issues, both planner statuses `exact`.

Raw smoke rows and logs: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/raw/127x04/smoke/`; instrumentation: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/smoke-check.json`.

s4 completion: [('2026-10-18T04:43:27Z', '0')]

s5 completion: [('2026-10-18T04:39:17Z', '0')]

