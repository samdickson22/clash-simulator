# RF1 results

Preregistration: [RF-PREREG.md](RF-PREREG.md). `l16` denotes L16; `acc` denotes the account row.

Readout generated 2026-10-18T04:56:25Z. Reference `res-lb-wintp`; treatment `res-lb-RF-wintp`.

**Ship: FAIL.** Pooled K4CW lower-bound criterion: PASS; neither-row-below−0.02 criterion: PASS; literal metrics-not-worse criterion: FAIL.

Metrics with worse point estimates: elixir_at_cross_mean, idle_play_share, hog_elixir_ge6, hog_cannon_and_ge3, Fireball_enemy_in_radius_share. The preregistration does not define metric tolerances or a composite gate. This readout applies a conservative zero-tolerance point-estimate check to the observable metrics below; play counts and Cannon location are descriptive. No metric-significance claim is made.

## Data integrity

Raw rows: 1600; unique valid rows: 1600; duplicate rows: 0, all identical in command events plus win/draw and counted once; error rows retained in audit: 0. Unique rows by level row: `{'l16': 800, 'acc': 800}`. Hosts: `{'127x04': 800, '127x08': 800}`. Issues in raw valid rows: `{}`.

Full audit and row paths: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/audit.json`. Original logs/receipts and bank files are mirrored under `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw`. Completion and rerun history is in the appended run audit.

Exactly 200 paired cases per opponent per level row; 400 pairs per opponent pooled over L16/account. Arms are checked for matching seed, seat, deck order and truth levels on every pair; bank seeds and the absence of Goblin Hut are checked. No early stopping or outcome-based exclusions.

## Paired score contrasts

Score is win=1, draw=0.5. CIs are the tree’s unchanged `hz_report`/`scale_report.boot`: 4000 case bootstrap draws with `random.Random(0)`, sorted draws [100,3900]. Pooling treats each (level row, index, opponent) as a separate paired observation as requested; no clustering over repeated seeds across level rows.

| Level row | K4CW treatment − reference, 95% CI | R3a treatment − reference, 95% CI | Both opponents treatment − reference, 95% CI |
| --- | --- | --- | --- |
| l16 | +0.0350 [-0.0450, +0.1150] (n=200) | +0.0000 [-0.0750, +0.0750] (n=200) | +0.0175 [-0.0375, +0.0725] (n=400) |
| acc | +0.1350 [+0.0600, +0.2050] (n=200) | +0.0100 [-0.0600, +0.0800] (n=200) | +0.0725 [+0.0200, +0.1225] (n=400) |
| pooled | +0.0850 [+0.0300, +0.1400] (n=400) | +0.0050 [-0.0475, +0.0550] (n=400) | +0.0450 [+0.0075, +0.0825] (n=800) |


## Scores by arm and opponent

| Level row | Arm | Games | K4CW score | R3a score | Both score |
| --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 400 | 0.695 | 0.790 | 0.743 |
| l16 | res-lb-RF-wintp | 400 | 0.730 | 0.790 | 0.760 |
| acc | res-lb-wintp | 400 | 0.390 | 0.595 | 0.492 |
| acc | res-lb-RF-wintp | 400 | 0.525 | 0.605 | 0.565 |
| pooled | res-lb-wintp | 800 | 0.542 | 0.693 | 0.618 |
| pooled | res-lb-RF-wintp | 800 | 0.627 | 0.698 | 0.662 |


## Standing play-quality metrics (both opponents)

| Level row | Arm | CPU ms/decision | Reaction p50/p90 s | Elixir crossing mean/median | Elixir crossing ≥8 | Wincon spend | Idle play | Wrong lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 806.0 | 1.500/5.500 | 3.26/3.14 | 0.004 | 0.057 | 0.544 | 0.274 |
| l16 | res-lb-RF-wintp | 797.1 | 1.500/5.500 | 3.21/3.07 | 0.003 | 0.061 | 0.541 | 0.264 |
| acc | res-lb-wintp | 797.5 | 1.500/5.500 | 3.26/3.14 | 0.004 | 0.075 | 0.528 | 0.270 |
| acc | res-lb-RF-wintp | 787.3 | 1.500/5.500 | 3.22/3.11 | 0.003 | 0.069 | 0.539 | 0.267 |
| pooled | res-lb-wintp | 801.7 | 1.500/5.500 | 3.26/3.14 | 0.004 | 0.066 | 0.536 | 0.272 |
| pooled | res-lb-RF-wintp | 792.1 | 1.500/5.500 | 3.22/3.09 | 0.003 | 0.065 | 0.540 | 0.266 |


CPU is total own-seat decision CPU divided by total own-seat decisions on the allowed study hosts, not wall time. Reaction is accepted enemy play → next accepted own play (20 ticks/s; events with no subsequent own play omitted). All other standing definitions are those in the tree’s `bot/fullpool/hz_report.py`: crossing = transition from no enemy at y<15 to at least one; wincon-spend = revealed enemy wincon event preceded within 3 s by own accepted play and elixir≤1; idle = own accepted troop aimed with no enemy within 6 tiles on the preceding own frame; wrong-lane = opposite-lane defensive non-spell aim relative to nearest visible incursion within ±3 s. The JSON includes their denominators and additional decision-reaction and incursion metrics.

## Enemy Hog Rider crossings

| Level row | Arm | Crossings | Elixir mean | Elixir median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 920 | 3.162 | 2.964 | 0.036 | 0.321 |
| l16 | res-lb-RF-wintp | 919 | 3.257 | 3.142 | 0.034 | 0.310 |
| acc | res-lb-wintp | 914 | 3.180 | 3.000 | 0.034 | 0.316 |
| acc | res-lb-RF-wintp | 917 | 3.119 | 2.892 | 0.033 | 0.268 |
| pooled | res-lb-wintp | 1834 | 3.171 | 3.000 | 0.035 | 0.318 |
| pooled | res-lb-RF-wintp | 1836 | 3.188 | 3.000 | 0.033 | 0.289 |


A Hog crossing is the first frame of a tracked enemy `HogRider` with y<15. Packets omit entity IDs, so adjacent-frame Hog positions are greedily matched by nearest Euclidean distance, with a maximum displacement max(1 tile, 0.2×elapsed ticks); unmatched positions start tracks. Each track counts once. Elixir and hand are from that crossing frame. This can split tracks across missing frames; it is an observational crossing estimate, not hidden entity-ID truth.

## Fireball, Zap and ElectroSpirit use

| Level row | Arm | Card | Plays/game | Plays | Frames available | Enemy within 2.5 share |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | Fireball | 0.993 | 397 | 362 | 0.486 |
| l16 | res-lb-wintp | Zap | 5.438 | 2175 | 2160 | 0.537 |
| l16 | res-lb-wintp | ElectroSpirit | 7.768 | 3107 | 3079 | 0.217 |
| l16 | res-lb-RF-wintp | Fireball | 0.938 | 375 | 349 | 0.484 |
| l16 | res-lb-RF-wintp | Zap | 5.185 | 2074 | 2060 | 0.543 |
| l16 | res-lb-RF-wintp | ElectroSpirit | 7.497 | 2999 | 2967 | 0.245 |
| acc | res-lb-wintp | Fireball | 1.035 | 414 | 373 | 0.539 |
| acc | res-lb-wintp | Zap | 5.668 | 2267 | 2256 | 0.508 |
| acc | res-lb-wintp | ElectroSpirit | 7.920 | 3168 | 3133 | 0.223 |
| acc | res-lb-RF-wintp | Fireball | 1.020 | 408 | 374 | 0.519 |
| acc | res-lb-RF-wintp | Zap | 5.588 | 2235 | 2220 | 0.513 |
| acc | res-lb-RF-wintp | ElectroSpirit | 7.970 | 3188 | 3153 | 0.235 |
| pooled | res-lb-wintp | Fireball | 1.014 | 811 | 735 | 0.513 |
| pooled | res-lb-wintp | Zap | 5.553 | 4442 | 4416 | 0.522 |
| pooled | res-lb-wintp | ElectroSpirit | 7.844 | 6275 | 6212 | 0.220 |
| pooled | res-lb-RF-wintp | Fireball | 0.979 | 783 | 723 | 0.502 |
| pooled | res-lb-RF-wintp | Zap | 5.386 | 4309 | 4280 | 0.527 |
| pooled | res-lb-RF-wintp | ElectroSpirit | 7.734 | 6187 | 6120 | 0.240 |


Counts use accepted play-log entries. Fireball landing tick is accepted-play tick + ceil(distance from own king (9,3) to aim / 0.6 tiles per tick), matching the installed simulator’s Fireball speed 600 millitiles/tick and launch point. Zap landing is the next tick. ElectroSpirit is a troop: its listed proximity measure uses deployment completion at play+20 ticks at its aimed tile; its actual later jump-impact location/time is not in these packets, so this is a deployment-proximity surrogate, not a spell hit rate. The nearest available own perception frame at or after that tick is used; a hit here means ≥1 enemy unit centre within 2.5 tiles of the aim. Enemy towers are absent from packet units. Units already killed by impact also disappear, so this observational measure undercounts actual successful damage. No after-landing frame → excluded from the observed-share denominator, with total plays and frame counts shown. Exact impact damage/actual ElectroSpirit jump success is unavailable.

## Goblin Barrel responses and Cannon placement

| Level row | Arm | Enemy Barrels | Answered ≤2s | Share ≤2s | Share ≤1.5s | Cannon plays | Centre near king share | Elsewhere share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | res-lb-wintp | 553 | 25 | 0.045 | 0.042 | 1842 | 0.008 | 0.992 |
| l16 | res-lb-RF-wintp | 559 | 84 | 0.150 | 0.127 | 1853 | 0.006 | 0.994 |
| acc | res-lb-wintp | 564 | 36 | 0.064 | 0.059 | 1917 | 0.007 | 0.993 |
| acc | res-lb-RF-wintp | 582 | 72 | 0.124 | 0.107 | 1948 | 0.011 | 0.989 |
| pooled | res-lb-wintp | 1117 | 61 | 0.055 | 0.050 | 3759 | 0.007 | 0.993 |
| pooled | res-lb-RF-wintp | 1141 | 156 | 0.137 | 0.117 | 3801 | 0.008 | 0.992 |


An enemy Barrel is an accepted GoblinBarrel play. Its action aim is rotated from the opponent’s frame to ours via (18−x,32−y). Answered means ≥1 accepted own spell or troop (buildings excluded) aimed within 3 tiles of that point at an accepted-play tick 0..40 ticks after the enemy play. The ≤2 s measure follows the task; the ≤1.5 s sensitivity preserves the preregistration’s shorter window. This is aimed-response timing, not proof the troop reached the point. Cannon centre-near-king means accepted aimed tile column floor(x)∈{7,8,9,10} and Euclidean distance ≤5 from own king (9,3); all other accepted Cannon plays are elsewhere.

## Metric gate audit

| Metric | Reference | Treatment | Treatment − reference | Worse point estimate |
| --- | --- | --- | --- | --- |
| cpu_ms_per_decision_pooled | 801.700 | 792.100 | -9.600 | no |
| enemy_to_our_play_p50 | 1.500 | 1.500 | 0.000 | no |
| enemy_to_our_play_p90 | 5.500 | 5.500 | 0.000 | no |
| elixir_at_cross_mean | 3.260 | 3.220 | -0.040 | yes |
| wincon_spend_share | 0.066 | 0.065 | -0.001 | no |
| idle_play_share | 0.536 | 0.540 | 0.004 | yes |
| wrong_lane_share | 0.272 | 0.266 | -0.006 | no |
| hog_elixir_mean | 3.171 | 3.188 | 0.017 | no |
| hog_elixir_ge6 | 0.035 | 0.033 | -0.002 | yes |
| hog_cannon_and_ge3 | 0.318 | 0.289 | -0.029 | yes |
| barrel_answer_share | 0.055 | 0.137 | 0.082 | no |
| Fireball_enemy_in_radius_share | 0.513 | 0.502 | -0.011 | yes |
| Zap_enemy_in_radius_share | 0.522 | 0.527 | 0.005 | no |
| ElectroSpirit_enemy_in_radius_share | 0.220 | 0.240 | 0.019 | no |


The supplied runner’s PacketRecorder filters decision statistics to source/hit/completed/timed_wait. `from_second` is not recorded. Consequently the chosen-play share exclusive to v2 is unavailable; rowsum’s printed zero must not be interpreted as a measured zero. Search/fast-path wiring is assessed separately by the smoke command-event comparison.

## Analysis artifacts and reproducibility

- l16 hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/hz-l16.json`

- acc hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/hz-acc.json`

- pooled hz_report JSON: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/hz-pooled.json`

- Extended metrics (all opponents and each opponent separately): `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/extra-metrics.json`

- Combined machine-readable readout: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/rf1/readout-data.json`

Each hz_report was executed from the staged tree with its Python 3.12 environment, `PYTHONPATH=TREE`, `python -m bot.fullpool.hz_report DIR --ref res-lb-wintp --arms TREATMENT --gate TREATMENT --gate-opponent LIVE-K4CW-r16-fp --json OUT`. Normalized inputs preserve the first valid occurrence of each (level row, player, opponent, index). Pooled copies namespace index as `level-row:index` to prevent hz_report from treating the same numeric index in L16/account as a duplicate. Raw rows are retained unchanged.

Computed source SHA256s at readout generation:
```text
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  /mpac/sdicks02/jobs/clasher/bot-pq/repo-aab2faf78a51/bot/fullpool/scale_report.py
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/score_study.py
f044645d93f70ef0ef4e74297f75e008905d7991d29b9f8dc6f24472eb2f3a99  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/render_report.py
```

## Run completion audit

2026-10-18T04:54:44Z
Original successful shards with 100 rows: 16/16. Earliest logged start 2026-10-18T03:25:24Z; latest end 2026-10-18T04:52:25Z.
- 127x04 l16-s0: start 2026-10-18T03:25:24Z; end ('2026-10-18T04:32:16Z', '0'); 100 original rows; receipt PID/PGID 157936/157936; worker statuses {'172577': 0, '172585': 0, '172589': 0, '172595': 0, '172597': 0, '172599': 0, '172601': 0, '172620': 0, '172632': 0, '172659': 0}.
  Bank SHA256: 35a841517f767bf93a40a3c5899c18f67c8f45d0407b608a04c78ad8946aea16  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/l16-s0/bank.json
- 127x04 l16-s1: start 2026-10-18T03:25:25Z; end ('2026-10-18T04:32:12Z', '0'); 100 original rows; receipt PID/PGID 157984/157984; worker statuses {'172460': 0, '172472': 0, '172478': 0, '172484': 0, '172492': 0, '172500': 0, '172506': 0, '172515': 0, '172525': 0, '172529': 0}.
  Bank SHA256: 35a841517f767bf93a40a3c5899c18f67c8f45d0407b608a04c78ad8946aea16  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/l16-s1/bank.json
- 127x04 l16-s2: start 2026-10-18T03:25:26Z; end ('2026-10-18T04:31:53Z', '0'); 100 original rows; receipt PID/PGID 158040/158040; worker statuses {'172509': 0, '172516': 0, '172527': 0, '172531': 0, '172533': 0, '172536': 0, '172539': 0, '172541': 0, '172542': 0, '172544': 0}.
  Bank SHA256: 8af2c88e79e13c446bb29267f4985e48d3a3a8f55ca27caabf9b0b8ec9b42c67  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/l16-s2/bank.json
- 127x04 l16-s3: start 2026-10-18T03:25:27Z; end ('2026-10-18T04:31:53Z', '0'); 100 original rows; receipt PID/PGID 158083/158083; worker statuses {'172635': 0, '172636': 0, '172658': 0, '172666': 0, '172674': 0, '172682': 0, '172689': 0, '172727': 0, '172755': 0, '172780': 0}.
  Bank SHA256: e28407cb9eb059def7ae64a38a3eb5cbc1ba3bbb08a1124f9c24151c5f9b9e42  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/l16-s3/bank.json
- 127x04 acc-s0: start 2026-10-18T03:25:28Z; end ('2026-10-18T04:38:06Z', '0'); 100 original rows; receipt PID/PGID 158106/158106; worker statuses {'172885': 0, '172887': 0, '172893': 0, '172895': 0, '172897': 0, '172899': 0, '172901': 0, '172902': 0, '172917': 0, '172922': 0}.
  Bank SHA256: 08dcc53565f8c48b8e49ed284a1d05d45f1a40715f94b070e2753da084364b37  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/acc-s0/bank.json
- 127x04 acc-s1: start 2026-10-18T03:25:28Z; end ('2026-10-18T04:36:27Z', '0'); 100 original rows; receipt PID/PGID 158154/158154; worker statuses {'173297': 0, '173299': 0, '173301': 0, '173303': 0, '173305': 0, '173308': 0, '173322': 0, '173330': 0, '173340': 0, '173348': 0}.
  Bank SHA256: 08dcc53565f8c48b8e49ed284a1d05d45f1a40715f94b070e2753da084364b37  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/acc-s1/bank.json
- 127x04 acc-s2: start 2026-10-18T03:25:29Z; end ('2026-10-18T04:34:34Z', '0'); 100 original rows; receipt PID/PGID 158203/158203; worker statuses {'173504': 0, '173505': 0, '173508': 0, '173513': 0, '173515': 0, '173517': 0, '173519': 0, '173535': 0, '173550': 0, '173560': 0}.
  Bank SHA256: 8a5ee383cc62fff78fc90714b5b456bcdb1ec99c3f9ba9b15688f2ac7433917a  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/acc-s2/bank.json
- 127x04 acc-s3: start 2026-10-18T03:25:30Z; end ('2026-10-18T04:39:06Z', '0'); 100 original rows; receipt PID/PGID 158238/158238; worker statuses {'173546': 0, '173555': 0, '173565': 0, '173569': 0, '173570': 0, '173574': 0, '173583': 0, '173590': 0, '173599': 0, '173608': 0}.
  Bank SHA256: bbec7fed393376e4597450bda121f0a005b8bd71fe395a165a688d675d686149  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x04/rf1/acc-s3/bank.json
- 127x08 l16-s4: start 2026-10-18T03:25:26Z; end ('2026-10-18T04:46:34Z', '0'); 100 original rows; receipt PID/PGID 1868916/1868916; worker statuses {'1884038': 0, '1884040': 0, '1884042': 0, '1884044': 0, '1884046': 0, '1884048': 0, '1884050': 0, '1884052': 0, '1884054': 0, '1884056': 0}.
  Bank SHA256: 8af2c88e79e13c446bb29267f4985e48d3a3a8f55ca27caabf9b0b8ec9b42c67  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/l16-s4/bank.json
- 127x08 l16-s5: start 2026-10-18T03:25:27Z; end ('2026-10-18T04:45:41Z', '0'); 100 original rows; receipt PID/PGID 1868970/1868970; worker statuses {'1883944': 0, '1883951': 0, '1883961': 0, '1883970': 0, '1883979': 0, '1883987': 0, '1883998': 0, '1884008': 0, '1884016': 0, '1884024': 0}.
  Bank SHA256: e28407cb9eb059def7ae64a38a3eb5cbc1ba3bbb08a1124f9c24151c5f9b9e42  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/l16-s5/bank.json
- 127x08 l16-s6: start 2026-10-18T03:25:27Z; end ('2026-10-18T04:45:16Z', '0'); 100 original rows; receipt PID/PGID 1868999/1868999; worker statuses {'1883815': 0, '1883822': 0, '1883827': 0, '1883829': 0, '1883830': 0, '1883833': 0, '1883837': 0, '1883839': 0, '1883841': 0, '1883843': 0}.
  Bank SHA256: e28407cb9eb059def7ae64a38a3eb5cbc1ba3bbb08a1124f9c24151c5f9b9e42  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/l16-s6/bank.json
- 127x08 l16-s7: start 2026-10-18T03:25:27Z; end ('2026-10-18T04:44:54Z', '0'); 100 original rows; receipt PID/PGID 1869034/1869034; worker statuses {'1884155': 0, '1884160': 0, '1884166': 0, '1884170': 0, '1884174': 0, '1884178': 0, '1884181': 0, '1884198': 0, '1884206': 0, '1884214': 0}.
  Bank SHA256: 021eb880fb4184ab15236a4af31d0d8ccd464f3c5f7ee77c1c3076e3cc814fca  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/l16-s7/bank.json
- 127x08 acc-s4: start 2026-10-18T03:25:28Z; end ('2026-10-18T04:44:14Z', '0'); 100 original rows; receipt PID/PGID 1869082/1869082; worker statuses {'1884137': 0, '1884147': 0, '1884151': 0, '1884153': 0, '1884156': 0, '1884164': 0, '1884168': 0, '1884172': 0, '1884176': 0, '1884180': 0}.
  Bank SHA256: 08dcc53565f8c48b8e49ed284a1d05d45f1a40715f94b070e2753da084364b37  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/acc-s4/bank.json
- 127x08 acc-s5: start 2026-10-18T03:25:29Z; end ('2026-10-18T04:52:25Z', '0'); 100 original rows; receipt PID/PGID 1869125/1869125; worker statuses {'1884276': 0, '1884281': 0, '1884284': 0, '1884286': 0, '1884288': 0, '1884294': 0, '1884296': 0, '1884298': 0, '1884300': 0, '1884302': 0}.
  Bank SHA256: 8a5ee383cc62fff78fc90714b5b456bcdb1ec99c3f9ba9b15688f2ac7433917a  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/acc-s5/bank.json
- 127x08 acc-s6: start 2026-10-18T03:25:29Z; end ('2026-10-18T04:48:27Z', '0'); 100 original rows; receipt PID/PGID 1869197/1869197; worker statuses {'1884387': 0, '1884395': 0, '1884403': 0, '1884405': 0, '1884406': 0, '1884408': 0, '1884411': 0, '1884414': 0, '1884416': 0, '1884418': 0}.
  Bank SHA256: 8a5ee383cc62fff78fc90714b5b456bcdb1ec99c3f9ba9b15688f2ac7433917a  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/acc-s6/bank.json
- 127x08 acc-s7: start 2026-10-18T03:25:30Z; end ('2026-10-18T04:44:44Z', '0'); 100 original rows; receipt PID/PGID 1869243/1869243; worker statuses {'1884574': 0, '1884582': 0, '1884590': 0, '1884598': 0, '1884606': 0, '1884612': 0, '1884620': 0, '1884628': 0, '1884634': 0, '1884642': 0}.
  Bank SHA256: bbec7fed393376e4597450bda121f0a005b8bd71fe395a165a688d675d686149  /mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/raw/127x08/rf1/acc-s7/bank.json


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

