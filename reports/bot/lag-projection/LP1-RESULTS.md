# LP1 results

Preregistration: [PREREG.md](PREREG.md) and [AMENDMENT-1.md](AMENDMENT-1.md). `l16` denotes L16; `acc` denotes the account row. Extended metrics use the same definitions and identical analysis functions as [RF1-RESULTS.md](../pq/RF1-RESULTS.md).

Readout generated 2026-10-18T05:37:57Z. Reference `res-lb-wintp`; treatment `res-lb-LP26-wintp`.

**Ship: FAIL.** K4CW score criterion: FAIL; neither-row-below−0.02 criterion: FAIL; literal metrics-not-worse criterion: FAIL. LP1 requires pooled lower bound ≥0 and neither row point below −0.02.

Metrics with worse point estimates: cpu_ms_per_decision_pooled, elixir_at_cross_mean, wincon_spend_share, hog_elixir_mean, hog_elixir_ge6, hog_cannon_and_ge3, barrel_answer_share, ElectroSpirit_enemy_in_radius_share. The preregistration does not define metric tolerances or a composite gate. This readout applies a conservative zero-tolerance point-estimate check to the observable metrics below; play counts and Cannon location are descriptive. No metric-significance claim is made.

## Data integrity

Raw rows: 1200; unique valid rows: 1200; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'l16': 600, 'acc': 600}`. Hosts: `{'127x04': 600, '127x08': 600}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/raw`. Completion and rerun history is in the appended run audit.

Exactly 150 paired cases per opponent per level row; 300 pairs per opponent pooled over L16/account. The same seeds, decks and seats are used for both opponents. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | Both opponents treatment − reference, 95% CI |
| --- | --- | --- | --- |
| l16 | -0.0400 [-0.1267, +0.0467] (n=150) | +0.0067 [-0.0667, +0.0800] (n=150) | -0.0167 [-0.0733, +0.0400] (n=300) |
| acc | -0.0200 [-0.1000, +0.0600] (n=150) | +0.0000 [-0.0867, +0.0867] (n=150) | -0.0100 [-0.0700, +0.0500] (n=300) |
| pooled | -0.0300 [-0.0900, +0.0267] (n=300) | +0.0033 [-0.0567, +0.0600] (n=300) | -0.0133 [-0.0533, +0.0283] (n=600) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | Both score |
| --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 300 | 0.767 | 0.800 | 0.783 |
| l16 | res-lb-LP26-wintp | 300 | 0.727 | 0.807 | 0.767 |
| acc | res-lb-wintp | 300 | 0.420 | 0.593 | 0.507 |
| acc | res-lb-LP26-wintp | 300 | 0.400 | 0.593 | 0.497 |
| pooled | res-lb-wintp | 600 | 0.593 | 0.697 | 0.645 |
| pooled | res-lb-LP26-wintp | 600 | 0.563 | 0.700 | 0.632 |


## Standing play-quality metrics (both opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 610.0 | 1.500/5.750 | 3.25/3.11 | 0.004 | 0.059 | 0.553 | 0.282 |
| l16 | res-lb-LP26-wintp | 721.3 | 1.500/5.500 | 3.23/3.12 | 0.001 | 0.063 | 0.537 | 0.268 |
| acc | res-lb-wintp | 610.0 | 1.500/5.500 | 3.27/3.14 | 0.003 | 0.060 | 0.535 | 0.269 |
| acc | res-lb-LP26-wintp | 719.3 | 1.500/5.500 | 3.24/3.09 | 0.002 | 0.068 | 0.524 | 0.271 |
| pooled | res-lb-wintp | 610.0 | 1.500/5.500 | 3.26/3.12 | 0.003 | 0.059 | 0.543 | 0.275 |
| pooled | res-lb-LP26-wintp | 720.3 | 1.500/5.500 | 3.24/3.11 | 0.002 | 0.066 | 0.531 | 0.270 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 618 | 3.160 | 2.982 | 0.028 | 0.311 |
| l16 | res-lb-LP26-wintp | 616 | 3.079 | 2.892 | 0.019 | 0.289 |
| acc | res-lb-wintp | 624 | 3.240 | 3.011 | 0.037 | 0.335 |
| acc | res-lb-LP26-wintp | 638 | 3.174 | 3.000 | 0.030 | 0.331 |
| pooled | res-lb-wintp | 1242 | 3.200 | 3.000 | 0.032 | 0.323 |
| pooled | res-lb-LP26-wintp | 1254 | 3.128 | 2.964 | 0.025 | 0.310 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | Fireball | 0.893 | 268 | 241 | 0.506 |
| l16 | res-lb-wintp | Zap | 5.387 | 1616 | 1604 | 0.563 |
| l16 | res-lb-wintp | ElectroSpirit | 7.637 | 2291 | 2260 | 0.222 |
| l16 | res-lb-LP26-wintp | Fireball | 1.033 | 310 | 278 | 0.525 |
| l16 | res-lb-LP26-wintp | Zap | 5.377 | 1613 | 1602 | 0.573 |
| l16 | res-lb-LP26-wintp | ElectroSpirit | 7.747 | 2324 | 2307 | 0.219 |
| acc | res-lb-wintp | Fireball | 1.023 | 307 | 286 | 0.472 |
| acc | res-lb-wintp | Zap | 5.660 | 1698 | 1688 | 0.497 |
| acc | res-lb-wintp | ElectroSpirit | 7.987 | 2396 | 2372 | 0.239 |
| acc | res-lb-LP26-wintp | Fireball | 1.053 | 316 | 295 | 0.563 |
| acc | res-lb-LP26-wintp | Zap | 5.657 | 1697 | 1683 | 0.491 |
| acc | res-lb-LP26-wintp | ElectroSpirit | 7.990 | 2397 | 2374 | 0.237 |
| pooled | res-lb-wintp | Fireball | 0.958 | 575 | 527 | 0.488 |
| pooled | res-lb-wintp | Zap | 5.523 | 3314 | 3292 | 0.529 |
| pooled | res-lb-wintp | ElectroSpirit | 7.812 | 4687 | 4632 | 0.231 |
| pooled | res-lb-LP26-wintp | Fireball | 1.043 | 626 | 573 | 0.545 |
| pooled | res-lb-LP26-wintp | Zap | 5.517 | 3310 | 3285 | 0.531 |
| pooled | res-lb-LP26-wintp | ElectroSpirit | 7.868 | 4721 | 4681 | 0.228 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 381 | 17 | 0.045 | 0.045 | 1367 | 0.011 | 0.989 |
| l16 | res-lb-LP26-wintp | 368 | 19 | 0.052 | 0.041 | 1372 | 0.008 | 0.992 |
| acc | res-lb-wintp | 397 | 20 | 0.050 | 0.050 | 1490 | 0.009 | 0.991 |
| acc | res-lb-LP26-wintp | 395 | 13 | 0.033 | 0.030 | 1444 | 0.009 | 0.991 |
| pooled | res-lb-wintp | 778 | 37 | 0.048 | 0.048 | 2857 | 0.010 | 0.990 |
| pooled | res-lb-LP26-wintp | 763 | 32 | 0.042 | 0.035 | 2816 | 0.009 | 0.991 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Worse point estimate |
| --- | --- | --- | --- | --- |
| cpu_ms_per_decision_pooled | 610.000 | 720.300 | 110.300 | yes |
| enemy_to_our_play_p50 | 1.500 | 1.500 | 0.000 | no |
| enemy_to_our_play_p90 | 5.500 | 5.500 | 0.000 | no |
| elixir_at_cross_mean | 3.260 | 3.240 | -0.020 | yes |
| wincon_spend_share | 0.059 | 0.066 | 0.007 | yes |
| idle_play_share | 0.543 | 0.531 | -0.012 | no |
| wrong_lane_share | 0.275 | 0.270 | -0.005 | no |
| hog_elixir_mean | 3.200 | 3.128 | -0.073 | yes |
| hog_elixir_ge6 | 0.032 | 0.025 | -0.007 | yes |
| hog_cannon_and_ge3 | 0.323 | 0.310 | -0.013 | yes |
| barrel_answer_share | 0.048 | 0.042 | -0.006 | yes |
| Fireball_enemy_in_radius_share | 0.488 | 0.545 | 0.057 | no |
| Zap_enemy_in_radius_share | 0.529 | 0.531 | 0.002 | no |
| ElectroSpirit_enemy_in_radius_share | 0.231 | 0.228 | -0.002 | yes |


## Analysis artifacts and reproducibility

- l16 hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/hz-l16.json`

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/readout-data.json`

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
| l16 | res-lb-wintp | LIVE-K4CW-r16-fp | 115 | 0 | 35 |
| l16 | res-lb-wintp | R3a | 120 | 0 | 30 |
| l16 | res-lb-LP26-wintp | LIVE-K4CW-r16-fp | 109 | 0 | 41 |
| l16 | res-lb-LP26-wintp | R3a | 121 | 0 | 29 |
| acc | res-lb-wintp | LIVE-K4CW-r16-fp | 63 | 0 | 87 |
| acc | res-lb-wintp | R3a | 89 | 0 | 61 |
| acc | res-lb-LP26-wintp | LIVE-K4CW-r16-fp | 60 | 0 | 90 |
| acc | res-lb-LP26-wintp | R3a | 89 | 0 | 61 |


## Treatment diagnostics

Instrumentation validity: PASS. LP1 requires zero lag-projection errors; LV3 treatment statuses and revealed levels are checked during scoring.

| Level row | Opponent | LP games | Decisions | Added candidates | Errors | Added / decision |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | all | 300 | 42120 | 182291 | 0 | 4.328 |
| l16 | LIVE-K4CW-r16-fp | 150 | 21125 | 94518 | 0 | 4.474 |
| l16 | R3a | 150 | 20995 | 87773 | 0 | 4.181 |
| acc | all | 300 | 43334 | 188518 | 0 | 4.350 |
| acc | LIVE-K4CW-r16-fp | 150 | 21785 | 94771 | 0 | 4.350 |
| acc | R3a | 150 | 21549 | 93747 | 0 | 4.350 |
| pooled | all | 600 | 85454 | 370809 | 0 | 4.339 |
| pooled | LIVE-K4CW-r16-fp | 300 | 42910 | 189289 | 0 | 4.411 |
| pooled | R3a | 300 | 42544 | 181520 | 0 | 4.267 |


Instrumentation JSON: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/lp1/instrumentation.json`.

## Run completion audit

Audit generated 2026-10-18T05:36:44Z.
Completed shards after authorized retries: 12/12. Original rows and all retry rows retained; the scorer checks duplicate identity and exact expected valid case keys.
Staged source revision from STAGED-REV: `656771761ba1`.
- 127x04 l16-s0: start ['2026-10-18T04:31:29Z']; end [('2026-10-18T05:11:01Z', '0')]; expected rows 100; original receipt PID/PGID 197319/197319.
  Output l16-s0: 100 raw rows; worker statuses {'628682': 0, '628690': 0, '628697': 0, '628700': 0, '628704': 0, '628707': 0, '628709': 0, '628712': 0, '628726': 0, '628732': 0}; bank SHA256 `a481ea09657975b0d39ed1a456b3b9c96d6fe963ce82e9c0971f2f9b4c99b519`.
- 127x04 l16-s1: start ['2026-10-18T04:31:32Z']; end [('2026-10-18T05:09:49Z', '0')]; expected rows 100; original receipt PID/PGID 197360/197360.
  Output l16-s1: 100 raw rows; worker statuses {'628582': 0, '628584': 0, '628586': 0, '628591': 0, '628594': 0, '628596': 0, '628598': 0, '628600': 0, '628608': 0, '628619': 0}; bank SHA256 `e219a120f4f332356386ff0614b4c8c96435b801ba030541a368cb876ba6bead`.
- 127x04 l16-s2: start ['2026-10-18T04:31:35Z']; end [('2026-10-18T05:10:53Z', '0')]; expected rows 100; original receipt PID/PGID 197409/197409.
  Output l16-s2: 100 raw rows; worker statuses {'629467': 0, '629474': 0, '629478': 0, '629481': 0, '629483': 0, '629486': 0, '629490': 0, '629493': 0, '629494': 0, '629496': 0}; bank SHA256 `0dfd22957a07f97938d95bbd3f6950d5228745694d6845066561682aa32c0597`.
- 127x04 acc-s0: start ['2026-10-18T04:31:10Z']; end [('2026-10-18T05:12:19Z', '0')]; expected rows 100; original receipt PID/PGID 197441/197441.
  Output acc-s0: 100 raw rows; worker statuses {'625572': 0, '625579': 0, '625587': 0, '625594': 0, '625601': 0, '625610': 0, '625616': 0, '625618': 0, '625621': 0, '625622': 0}; bank SHA256 `389870daf0be8bf0af516b750e43a2f18a6bebc8e87c7ab8f5839b0498f9abda`.
- 127x04 acc-s1: start ['2026-10-18T04:31:12Z']; end [('2026-10-18T05:10:55Z', '0')]; expected rows 100; original receipt PID/PGID 197467/197467.
  Output acc-s1: 100 raw rows; worker statuses {'626081': 0, '626088': 0, '626094': 0, '626109': 0, '626112': 0, '626118': 0, '626121': 0, '626123': 0, '626126': 0, '626140': 0}; bank SHA256 `1f22ec7b1aabaa5abc0ae522abbf9a2937234ebb740767250fd6a4f113465d0e`.
- 127x04 acc-s2: start ['2026-10-18T04:31:14Z']; end [('2026-10-18T05:21:26Z', '0')]; expected rows 100; original receipt PID/PGID 197552/197552.
  Output acc-s2: 100 raw rows; worker statuses {'626286': 0, '626288': 0, '626290': 0, '626292': 0, '626294': 0, '626296': 0, '626298': 0, '626300': 0, '626302': 0, '626304': 0}; bank SHA256 `35df3915d4c1f35528d80837f34b51753ec3e1886b7de4cf272966e6bbd699a1`.
- 127x08 l16-s3: start ['2026-10-18T04:43:04Z']; end [('2026-10-18T05:30:36Z', '0')]; expected rows 100; original receipt PID/PGID 1904095/1904095.
  Output l16-s3: 100 raw rows; worker statuses {'2411968': 0, '2411973': 0, '2411980': 0, '2411982': 0, '2411985': 0, '2411989': 0, '2411993': 0, '2411997': 0, '2412001': 0, '2412005': 0}; bank SHA256 `d0646c82b0e22c7a648be685c8ed5f7ee3827176de793f75e549194a9d836147`.
- 127x08 l16-s4: start ['2026-10-18T04:43:06Z']; end [('2026-10-18T05:35:23Z', '0')]; expected rows 100; original receipt PID/PGID 1904138/1904138.
  Output l16-s4: 100 raw rows; worker statuses {'2411983': 0, '2411987': 0, '2411991': 0, '2411995': 0, '2411999': 0, '2412003': 0, '2412007': 0, '2412010': 0, '2412025': 0, '2412033': 0}; bank SHA256 `bb7bcff756382371bac7d4febefef37bef7d463e6f93f35f43ac12545704db9f`.
- 127x08 l16-s5: start ['2026-10-18T04:43:08Z']; end [('2026-10-18T05:30:24Z', '0')]; expected rows 100; original receipt PID/PGID 1904181/1904181.
  Output l16-s5: 100 raw rows; worker statuses {'2412395': 0, '2412410': 0, '2412418': 0, '2412427': 0, '2412439': 0, '2412449': 0, '2412457': 0, '2412467': 0, '2412475': 0, '2412483': 0}; bank SHA256 `35e621268b34d6feefc95ff2eefafe68c40c7eb72db5833cfdfa798caa9be34e`.
- 127x08 acc-s3: start ['2026-10-18T04:43:10Z']; end [('2026-10-18T05:32:07Z', '0')]; expected rows 100; original receipt PID/PGID 1904218/1904218.
  Output acc-s3: 100 raw rows; worker statuses {'2412195': 0, '2412197': 0, '2412199': 0, '2412201': 0, '2412204': 0, '2412220': 0, '2412228': 0, '2412236': 0, '2412244': 0, '2412252': 0}; bank SHA256 `d8a6b66847e3c7908b8740b9f0ea9cc36b3b7bd5fccbcdeffa82914a864458f2`.
- 127x08 acc-s4: start ['2026-10-18T04:43:14Z']; end [('2026-10-18T05:31:58Z', '0')]; expected rows 100; original receipt PID/PGID 1904264/1904264.
  Output acc-s4: 100 raw rows; worker statuses {'2413125': 0, '2413127': 0, '2413132': 0, '2413139': 0, '2413147': 0, '2413156': 0, '2413159': 0, '2413161': 0, '2413163': 0, '2413169': 0}; bank SHA256 `24907cad843dabb4b7d3c030900509aa7c80d26702618555ed8835fe2e7af00f`.
- 127x08 acc-s5: start ['2026-10-18T04:43:16Z']; end [('2026-10-18T05:33:56Z', '0')]; expected rows 100; original receipt PID/PGID 1904316/1904316.
  Output acc-s5: 100 raw rows; worker statuses {'2413347': 0, '2413350': 0, '2413353': 0, '2413355': 0, '2413356': 0, '2413363': 0, '2413365': 0, '2413367': 0, '2413368': 0, '2413370': 0}; bank SHA256 `b4a976fa35f855d2396a72e384b64c81e01fcdbe00478c0784ed472d1f8bf8fe`.
Bank source pin population_sha256: `01732d23c278964ba55709196470bc21b074d24d730917793129fa7a5a926810`.
Bank source pin vocab_sha256: `f588168f9def92fff7ca6660778cb87bb1dd5224be7bea6a21892c6b6721192c`.
Bank source pin driver_sha256: `3a6b099788de221a4e4dc00ff02137e17e03a314dbb4fbb8eeedfaf34fbee17d`.
Bank source pin factory_sha256: `0b8181c805a6e748c970e22936c8b1311f6fe8fb1c18d7d1c317532a5d28680a`.
Bank source pin plan_table_sha256: `None`.


## Smoke comparison

Smoke audit generated 2026-10-18T04:54:13Z.

Smoke s4: four completed rows, zero row errors; LP candidate additions 2743 across 600 decisions (4.572/decision), zero projection errors. Both case-1 arms flag `unmapped public rows`; retained and reported to owner. RF1’s smoke readout identifies these as the runner-permitted SpearGoblin_Dummy sprite notice; the main-study pool excludes Goblin Hut and all LP1 study rows have no issues. Smoke s5: two completed rows, zero row errors/issues, both planner statuses `exact`.

Raw smoke rows and logs: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/raw/127x04/smoke/`; instrumentation: `/mpac/sdicks02/jobs/clasher/bot-pq-watch-lp1-lv3/smoke-check.json`.

s4 completion: [('2026-10-18T04:43:27Z', '0')]

s5 completion: [('2026-10-18T04:39:17Z', '0')]

