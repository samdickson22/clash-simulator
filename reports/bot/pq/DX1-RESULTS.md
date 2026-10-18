# DX1: policy-only losses and search-derived training targets

Pre-registration: [DX1-PREREG.md](DX1-PREREG.md). This is a diagnosis study for HP1 RL; there is no ship rule. Goal: a policy-only bot that beats the live search bot.

Generated 2026-10-18T11:50:09Z. Source archive revision `a2a9be89008b` (the archive has no Git metadata). Analysis by Sol on 127x05; games only on 127x04/127x08.

The v2 policy alone loses **23.67 percentage points against LIVE-K4CW-r16-fp**, **12.00 points against R3a**, and **3.67 points against HPv2** relative to search, pooled across level rows. The first two paired 95% intervals exclude zero; HPv2's interval includes zero. Against K4CW the deficit appears in both rows: −29.33 points at L16 and −18.00 at account levels. There are 226 pairs where search wins and pv2 loses, versus 108 in the reverse direction.

The main actionable diagnosis is **state-dependent play/hold timing**, followed by **Zap, ElectroSpirit and Cannon placement**. Search plays while pv2 waits on 17,812 searched decisions; search holds while pv2 plays on 21,458. The former is fully scored; only 12,419 of the latter are scored, so its measured burden is censored. After excluding comparisons where both already choose WAIT and differ only in hold duration, these two gate directions contribute 40.81% and 23.13% of measured signed regret. Double elixir contains 74.46% of that action-disagreement regret.

A necessary recorder distinction: **58,319 comparisons (30.03% of the raw regret sum) are timed hold versus plain WAIT even though both choose the same policy action on the current poll.** These are reported as `hold_duration`, with examples, but they are not 58,319 wrong play/hold decisions by pv2. Their score includes future waiting behavior and existing search wait bonuses. A play/hold policy cannot receive a different immediate action label for these states. Raw top-five rankings and rankings restricted to different policy actions are both provided below.

The policy already looks better on several RF1 proxies while losing more games: pooled idle share 36.03% versus search 55.98%, wrong-lane share 14.18% versus 25.57%, wincon dump share 2.17% versus 5.45%, and crossing elixir 4.20 versus 3.27. Search has faster accepted-play reaction (median 1.50 versus 1.75 s), a higher Barrel answer share (11.42% versus 6.01%), and higher Fireball unit-proximity share (48.50% versus 39.69%). These directions argue for learning action value and winning outcomes; globally minimizing idle/wrong-lane counts, maximizing reserves, or rewarding ElectroSpirit deployment proximity would be unsupported objectives. The trajectories and denominators differ, so these comparisons are descriptive, not causal explanations of the outcome gap.

## Outcome gap

Score = win 1, draw 0.5, loss 0. Contrast = pv2 − search. Primary 95% intervals use the unchanged `scale_report.boot`: 4000 paired-case bootstrap draws, `random.Random(0)`, sorted draws [100,3900]. L16 and account each have 150 pairs per opponent; the pooled analysis treats (row,index,opponent) as separate pairs, following RF1. Because the same indices recur across rows, a sensitivity clusters the paired differences across level rows by (opponent,index); it appears below and in `outcomes.json`. No early stopping or outcome-based exclusions.

| Row | Opponent | Pairs | Search score | pv2 score | pv2 − search [95% CI] | Search win/pv2 loss | Reverse |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | K4CW | 150 | 0.7400 | 0.4467 | -0.2933 [-0.3800, -0.2000] | 52 | 8 |
| l16 | R3a | 150 | 0.8800 | 0.7133 | -0.1667 [-0.2533, -0.0800] | 38 | 13 |
| l16 | HPv2 | 150 | 0.4467 | 0.3867 | -0.0600 [-0.1600, +0.0400] | 34 | 25 |
| l16 | all | 450 | 0.6889 | 0.5156 | -0.1733 [-0.2289, -0.1200] | 124 | 46 |
| acc | K4CW | 150 | 0.5533 | 0.3733 | -0.1800 [-0.2733, -0.0867] | 42 | 15 |
| acc | R3a | 150 | 0.6867 | 0.6133 | -0.0733 [-0.1667, +0.0267] | 33 | 22 |
| acc | HPv2 | 150 | 0.2800 | 0.2667 | -0.0133 [-0.1067, +0.0800] | 27 | 25 |
| acc | all | 450 | 0.5067 | 0.4178 | -0.0889 [-0.1444, -0.0311] | 102 | 62 |
| pooled | K4CW | 300 | 0.6467 | 0.4100 | -0.2367 [-0.3000, -0.1733] | 94 | 23 |
| pooled | R3a | 300 | 0.7833 | 0.6633 | -0.1200 [-0.1867, -0.0533] | 71 | 35 |
| pooled | HPv2 | 300 | 0.3633 | 0.3267 | -0.0367 [-0.1067, +0.0333] | 61 | 50 |
| pooled | all | 900 | 0.5978 | 0.4667 | -0.1311 [-0.1711, -0.0933] | 226 | 108 |

| Pooled opponent | Clusters | Cluster sensitivity 95% CI |
| --- | --- | --- |
| K4CW | 150 | [-0.3033, -0.1700] |
| R3a | 150 | [-0.1933, -0.0433] |
| HPv2 | 150 | [-0.1067, +0.0333] |
| all | 450 | [-0.1722, -0.0878] |

## Data integrity and completion

Owner resource rule: initially SIGSTOP/SIGCONT, then explicitly replaced with TERM+CONT and deferred relaunch. The initial rule made no group changes. Subsequent changes, if any, are logged per host in `dx1/logs/STOPPED.log`; the minute resource-control history is in `governor-history.jsonl`. The complete study rows were polled every 10 minutes.

Raw rows 1912; unique valid games 1800; command/outcome-identical duplicates 112; raw error rows 0; shadow error records 0. All 1800 expected (row,arm,opponent,index) keys are required by assertions. Each arm pair matches seed, seat, own and opponent deck order, truth card levels, and tower levels. Every row matches its bank SHA256 and bank case; pool source indices, no Goblin Hut, clean noise, terminal game, host, shard and both level configurations were checked. Row issues: `{}`.

| Host | Shard | End UTC / rc | Rows by attempt | Original PID / PGID |
| --- | --- | --- | --- | --- |
| 127x04 | l16-s0 | ['2026-10-18T10:56:05Z', '0'] | {'l16-s0': 150} | 3331026 / 3331026 |
| 127x04 | l16-s1 | ['2026-10-18T10:57:54Z', '0'] | {'l16-s1': 150} | 3331050 / 3331050 |
| 127x04 | l16-s2 | ['2026-10-18T10:57:46Z', '0'] | {'l16-s2': 150} | 3331101 / 3331101 |
| 127x04 | acc-s0 | ['2026-10-18T10:56:07Z', '0'] | {'acc-s0': 150} | 3331142 / 3331142 |
| 127x04 | acc-s1 | ['2026-10-18T11:00:13Z', '0'] | {'acc-s1': 150} | 3331169 / 3331169 |
| 127x04 | acc-s2 | ['2026-10-18T10:56:30Z', '0'] | {'acc-s2': 150} | 3331202 / 3331202 |
| 127x08 | l16-s3 | ['2026-10-18T11:14:43Z', '0'] | {'l16-s3': 150} | 545923 / 545923 |
| 127x08 | l16-s4 | ['2026-10-18T11:14:40Z', '0'] | {'l16-s4': 150} | 545942 / 545942 |
| 127x08 | l16-s5 | ['2026-10-18T11:14:51Z', '0'] | {'l16-s5': 150} | 545965 / 545965 |
| 127x08 | acc-s3 | ['2026-10-18T11:13:16Z', '0'] | {'acc-s3': 150} | 545983 / 545983 |
| 127x08 | acc-s4 | ['2026-10-18T11:17:51Z', '0'] | {'acc-s4': 150} | 546046 / 546046 |
| 127x08 | acc-s5 | ['2026-10-18T11:34:28Z', '0'] | {'acc-s5': 112, 'acc-s5-r2': 150} | 546087 / 546087 |

### Resource yields and exact-command relaunches

- 2026-10-18T11:04:00.117330+00:00 127x08 TERM+CONT acc-s5 PID/PGID 546087/546087 at load 69.73: RL cpu_job claim waiting.
- 2026-10-18T11:05:00.923692+00:00 127x08 RELAUNCH acc-s5 PID/PGID 787364/787364 at load 76.19: load1<90 and no live claim waiting.
  Exact relaunched command: `cd /mpac/sdicks02/jobs/clasher/bot-pq/repo-a2a9be89008b; bot/detach.sh /mpac/sdicks02/jobs/clasher/bot-pq/dx1/logs/acc-s5-retry1.log /mpac/sdicks02/jobs/clasher/bot-pq/dx1/logs/acc-s5-retry1.receipt.json bot/exit/cpu_job.sh 12 /mpac/sdicks02/jobs/clasher/bot-pq/repo-a2a9be89008b/bot/pq/l16.sh /mpac/sdicks02/jobs/clasher/bot-pq/repo-a2a9be89008b --workers 10 --out /mpac/sdicks02/jobs/clasher/bot-pq/dx1/acc-s5 --base 2680308772461232 --cases 150 --opponents LIVE-K4CW-r16-fp,R3a,HPv2 --pool /mpac/sdicks02/jobs/clasher/bot-cycle/lvg2/battlelog-pool-v3.2.jsonl --strata all=92,108,109,110,111,112,113,114,116,118,119,122,123,124,125,126,127,128,129,130,131,133,134,135,136,137,138,139,140,141,143,144,146,148,149,151,152,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,170 --vocab /mpac/sdicks02/jobs/clasher/bot-livediag/vocabv3/vocab-full.json --noise clean --own-deck HogRider,Archers,Cannon,Skeletons,Fireball,Zap,ElectroSpirit,Valkyrie --players res-lb-RF-sdiag-wintp,pv2 --levels account --our-levels Skeletons=7,Archers=8,Valkyrie=7,Cannon=9,Fireball=7,Zap=9,ElectroSpirit=8,HogRider=8,King=7 --shard 5/6`.
Original and rerun rows are scored from their union; duplicates match the RF1 command/outcome fingerprint and count once. Resource yielding is intentional, not an outcome-based exclusion. No SIGSTOP was issued by this watcher.

The account row uses own Skeletons 7, Archers 8, Valkyrie 7, Cannon 9, Fireball 7, Zap 9, ElectroSpirit 8, HogRider 8, King 7 against the source account card levels and King 9. L16 uses card and tower level 16 on both sides.

## Play-quality metrics: both arms, each row and opponent

Definitions are the unchanged RF1 scorer and `hz_report`; source hashes below establish that the staged DX1 and RF1 report definitions match. Values here retain full precision until display; machine-readable denominators and unrounded rates are in `metrics.json`/`metrics.csv`. Empty denominators are NA. The streaming implementation was checked against the unchanged RF1 `extra` on four historical games; every field matched exactly.

### Reaction, compute, idle deployment, wrong lane and win-condition dumps

| Row | Opp | Arm | N | CPU ms/decision | Reaction p50 / p90 s | Idle troop share | Wrong lane share | Wincon dump share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | HPv2 | pv2 | 150 | 23.3 | 1.500 / 5.000 | 40.1% | 9.5% | 1.3% |
| acc | HPv2 | search | 150 | 410.6 | 1.750 / 5.750 | 59.1% | 21.6% | 3.8% |
| acc | K4CW | pv2 | 150 | 30.6 | 2.000 / 6.250 | 32.7% | 17.7% | 5.2% |
| acc | K4CW | search | 150 | 504.2 | 1.500 / 5.500 | 52.2% | 27.7% | 4.4% |
| acc | R3a | pv2 | 150 | 29.4 | 1.750 / 6.250 | 35.4% | 15.7% | 1.6% |
| acc | R3a | search | 150 | 473.3 | 1.500 / 5.750 | 57.8% | 27.4% | 6.7% |
| acc | all | pv2 | 450 | 27.7 | 1.750 / 6.000 | 36.1% | 14.4% | 2.4% |
| acc | all | search | 450 | 463.4 | 1.500 / 5.750 | 56.3% | 25.8% | 5.0% |
| l16 | HPv2 | pv2 | 150 | 24.1 | 1.500 / 5.000 | 40.0% | 9.8% | 1.3% |
| l16 | HPv2 | search | 150 | 423.2 | 1.750 / 5.750 | 55.9% | 21.1% | 5.5% |
| l16 | K4CW | pv2 | 150 | 30.5 | 2.000 / 6.250 | 31.9% | 16.4% | 2.8% |
| l16 | K4CW | search | 150 | 486.5 | 1.500 / 5.500 | 53.2% | 27.3% | 6.7% |
| l16 | R3a | pv2 | 150 | 30.2 | 1.500 / 6.250 | 35.7% | 15.4% | 1.8% |
| l16 | R3a | search | 150 | 507.9 | 1.750 / 5.750 | 57.9% | 27.3% | 5.6% |
| l16 | all | pv2 | 450 | 28.2 | 1.500 / 6.000 | 35.9% | 13.9% | 1.9% |
| l16 | all | search | 450 | 472.6 | 1.500 / 5.750 | 55.6% | 25.3% | 5.9% |
| pooled | HPv2 | pv2 | 300 | 23.7 | 1.500 / 5.000 | 40.1% | 9.6% | 1.3% |
| pooled | HPv2 | search | 300 | 416.9 | 1.750 / 5.750 | 57.5% | 21.3% | 4.6% |
| pooled | K4CW | pv2 | 300 | 30.5 | 2.000 / 6.250 | 32.3% | 17.0% | 3.9% |
| pooled | K4CW | search | 300 | 495.5 | 1.500 / 5.500 | 52.7% | 27.5% | 5.5% |
| pooled | R3a | pv2 | 300 | 29.8 | 1.750 / 6.250 | 35.5% | 15.5% | 1.7% |
| pooled | R3a | search | 300 | 490.4 | 1.500 / 5.750 | 57.8% | 27.4% | 6.2% |
| pooled | all | pv2 | 900 | 28.0 | 1.750 / 6.000 | 36.0% | 14.2% | 2.2% |
| pooled | all | search | 900 | 467.9 | 1.500 / 5.750 | 56.0% | 25.6% | 5.5% |

CPU = total own-seat CPU / total decisions (04/08). Reaction = accepted enemy play → next accepted own play; no subsequent play is omitted. Idle = accepted troop with no enemy within 6 tiles of its aim on the preceding own frame. Wrong lane = accepted non-spell defensive aim opposite the nearest visible incursion within ±3 s; centre columns count for both lanes. Wincon dump = a revealed enemy wincon play preceded within 3 s by our accepted play with observed elixir ≤1. These are descriptive proxies: idle can include useful offense/cycling, and the wrong-lane definition includes useful counterpressure.

### General incursions and enemy Hog crossings

| Row | Opp | Arm | Incursions | Elixir mean / median | Elixir ≥8 | No play ≤5 s | Hog crossings | Hog elixir mean / median | Hog elixir ≥6 | Hog Cannon + elixir ≥3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | HPv2 | pv2 | 1837 | 4.373 / 4.000 | 5.9% | 6.9% | 378 | 4.248 / 3.732 | 20.4% | 35.2% |
| acc | HPv2 | search | 1596 | 3.311 / 3.178 | 0.4% | 12.3% | 303 | 3.143 / 3.035 | 3.6% | 30.7% |
| acc | K4CW | pv2 | 2407 | 3.997 / 3.821 | 2.4% | 8.7% | 268 | 3.775 / 3.428 | 13.4% | 26.5% |
| acc | K4CW | search | 2305 | 3.196 / 3.053 | 0.3% | 14.5% | 263 | 3.111 / 2.892 | 3.4% | 28.1% |
| acc | R3a | pv2 | 2413 | 4.320 / 4.125 | 3.9% | 9.7% | 305 | 3.865 / 3.857 | 13.1% | 37.4% |
| acc | R3a | search | 2072 | 3.317 / 3.232 | 0.3% | 13.1% | 284 | 3.310 / 3.095 | 3.9% | 35.2% |
| acc | all | pv2 | 6657 | 4.218 / 3.964 | 3.9% | 8.5% | 951 | 3.992 / 3.642 | 16.1% | 33.4% |
| acc | all | search | 5973 | 3.268 / 3.142 | 0.3% | 13.4% | 850 | 3.189 / 3.035 | 3.6% | 31.4% |
| l16 | HPv2 | pv2 | 1857 | 4.359 / 4.000 | 6.0% | 7.1% | 375 | 4.287 / 3.714 | 24.0% | 34.7% |
| l16 | HPv2 | search | 1670 | 3.344 / 3.214 | 0.4% | 12.3% | 307 | 3.083 / 3.002 | 2.6% | 33.6% |
| l16 | K4CW | pv2 | 2325 | 3.947 / 3.785 | 2.3% | 8.2% | 272 | 3.601 / 3.366 | 9.2% | 26.8% |
| l16 | K4CW | search | 2258 | 3.182 / 3.071 | 0.2% | 15.8% | 269 | 3.306 / 3.196 | 3.7% | 38.7% |
| l16 | R3a | pv2 | 2343 | 4.284 / 4.071 | 4.5% | 9.3% | 317 | 3.935 / 3.607 | 12.9% | 34.1% |
| l16 | R3a | search | 2028 | 3.283 / 3.178 | 0.4% | 14.9% | 276 | 3.240 / 3.089 | 1.8% | 30.4% |
| l16 | all | pv2 | 6525 | 4.185 / 3.946 | 4.2% | 8.3% | 964 | 3.978 / 3.571 | 16.2% | 32.3% |
| l16 | all | search | 5956 | 3.262 / 3.142 | 0.3% | 14.5% | 852 | 3.204 / 3.071 | 2.7% | 34.2% |
| pooled | HPv2 | pv2 | 3694 | 4.366 / 4.000 | 6.0% | 7.0% | 753 | 4.267 / 3.714 | 22.2% | 34.9% |
| pooled | HPv2 | search | 3266 | 3.328 / 3.214 | 0.4% | 12.3% | 610 | 3.113 / 3.017 | 3.1% | 32.1% |
| pooled | K4CW | pv2 | 4732 | 3.973 / 3.803 | 2.3% | 8.5% | 540 | 3.687 / 3.376 | 11.3% | 26.7% |
| pooled | K4CW | search | 4563 | 3.189 / 3.053 | 0.2% | 15.1% | 532 | 3.209 / 3.071 | 3.6% | 33.5% |
| pooled | R3a | pv2 | 4756 | 4.302 / 4.107 | 4.2% | 9.5% | 622 | 3.901 / 3.705 | 13.0% | 35.7% |
| pooled | R3a | search | 4100 | 3.300 / 3.196 | 0.3% | 14.0% | 560 | 3.275 / 3.095 | 2.9% | 32.9% |
| pooled | all | pv2 | 13182 | 4.202 / 3.964 | 4.0% | 8.4% | 1915 | 3.985 / 3.621 | 16.1% | 32.8% |
| pooled | all | search | 11929 | 3.265 / 3.142 | 0.3% | 14.0% | 1702 | 3.196 / 3.071 | 3.2% | 32.8% |

RF1 crossing threshold is y<15 (distinct from the requested shadow context y<16). General incursions count transitions from no enemy unit on our half to any. Hog crossings greedily match adjacent-frame positions within max(1 tile,0.2×elapsed ticks), counting each reconstructed track once at y<15. Missing frames can split tracks. Elixir/hand are from the crossing frame.

### Spells and ElectroSpirit deployment proximity

| Row | Opp | Arm | Card | Plays | Plays/game | Frames | Enemy ≤2.5 tiles |
| --- | --- | --- | --- | --- | --- | --- | --- |
| acc | HPv2 | pv2 | Fireball | 292 | 1.947 | 289 | 45.0% |
| acc | HPv2 | pv2 | Zap | 1256 | 8.373 | 1255 | 51.2% |
| acc | HPv2 | pv2 | ElectroSpirit | 1485 | 9.900 | 1472 | 38.0% |
| acc | HPv2 | search | Fireball | 181 | 1.207 | 171 | 55.0% |
| acc | HPv2 | search | Zap | 821 | 5.473 | 818 | 56.8% |
| acc | HPv2 | search | ElectroSpirit | 1132 | 7.547 | 1123 | 22.4% |
| acc | K4CW | pv2 | Fireball | 151 | 1.007 | 149 | 37.6% |
| acc | K4CW | pv2 | Zap | 1181 | 7.873 | 1178 | 50.1% |
| acc | K4CW | pv2 | ElectroSpirit | 1386 | 9.240 | 1375 | 37.7% |
| acc | K4CW | search | Fireball | 151 | 1.007 | 142 | 46.5% |
| acc | K4CW | search | Zap | 854 | 5.693 | 845 | 50.3% |
| acc | K4CW | search | ElectroSpirit | 1221 | 8.140 | 1208 | 24.8% |
| acc | R3a | pv2 | Fireball | 289 | 1.927 | 274 | 35.8% |
| acc | R3a | pv2 | Zap | 1208 | 8.053 | 1204 | 51.9% |
| acc | R3a | pv2 | ElectroSpirit | 1428 | 9.520 | 1414 | 39.5% |
| acc | R3a | search | Fireball | 179 | 1.193 | 172 | 49.4% |
| acc | R3a | search | Zap | 829 | 5.527 | 820 | 50.7% |
| acc | R3a | search | ElectroSpirit | 1185 | 7.900 | 1179 | 18.1% |
| acc | all | pv2 | Fireball | 732 | 1.627 | 712 | 39.9% |
| acc | all | pv2 | Zap | 3645 | 8.100 | 3637 | 51.1% |
| acc | all | pv2 | ElectroSpirit | 4299 | 9.553 | 4261 | 38.4% |
| acc | all | search | Fireball | 511 | 1.136 | 485 | 50.5% |
| acc | all | search | Zap | 2504 | 5.564 | 2483 | 52.6% |
| acc | all | search | ElectroSpirit | 3538 | 7.862 | 3510 | 21.8% |
| l16 | HPv2 | pv2 | Fireball | 266 | 1.773 | 261 | 46.4% |
| l16 | HPv2 | pv2 | Zap | 1271 | 8.473 | 1270 | 52.8% |
| l16 | HPv2 | pv2 | ElectroSpirit | 1489 | 9.927 | 1474 | 35.8% |
| l16 | HPv2 | search | Fireball | 177 | 1.180 | 167 | 53.3% |
| l16 | HPv2 | search | Zap | 863 | 5.753 | 859 | 58.6% |
| l16 | HPv2 | search | ElectroSpirit | 1164 | 7.760 | 1145 | 23.6% |
| l16 | K4CW | pv2 | Fireball | 131 | 0.873 | 127 | 30.7% |
| l16 | K4CW | pv2 | Zap | 1177 | 7.847 | 1172 | 57.8% |
| l16 | K4CW | pv2 | ElectroSpirit | 1381 | 9.207 | 1369 | 40.0% |
| l16 | K4CW | search | Fireball | 139 | 0.927 | 129 | 40.3% |
| l16 | K4CW | search | Zap | 784 | 5.227 | 780 | 56.4% |
| l16 | K4CW | search | ElectroSpirit | 1149 | 7.660 | 1135 | 24.3% |
| l16 | R3a | pv2 | Fireball | 260 | 1.733 | 253 | 36.8% |
| l16 | R3a | pv2 | Zap | 1180 | 7.867 | 1173 | 56.4% |
| l16 | R3a | pv2 | ElectroSpirit | 1401 | 9.340 | 1391 | 39.5% |
| l16 | R3a | search | Fireball | 173 | 1.153 | 153 | 43.8% |
| l16 | R3a | search | Zap | 773 | 5.153 | 773 | 59.4% |
| l16 | R3a | search | ElectroSpirit | 1129 | 7.527 | 1114 | 18.0% |
| l16 | all | pv2 | Fireball | 657 | 1.460 | 641 | 39.5% |
| l16 | all | pv2 | Zap | 3628 | 8.062 | 3615 | 55.6% |
| l16 | all | pv2 | ElectroSpirit | 4271 | 9.491 | 4234 | 38.4% |
| l16 | all | search | Fireball | 489 | 1.087 | 449 | 46.3% |
| l16 | all | search | Zap | 2420 | 5.378 | 2412 | 58.1% |
| l16 | all | search | ElectroSpirit | 3442 | 7.649 | 3394 | 22.0% |
| pooled | HPv2 | pv2 | Fireball | 558 | 1.860 | 550 | 45.6% |
| pooled | HPv2 | pv2 | Zap | 2527 | 8.423 | 2525 | 52.0% |
| pooled | HPv2 | pv2 | ElectroSpirit | 2974 | 9.913 | 2946 | 36.9% |
| pooled | HPv2 | search | Fireball | 358 | 1.193 | 338 | 54.1% |
| pooled | HPv2 | search | Zap | 1684 | 5.613 | 1677 | 57.7% |
| pooled | HPv2 | search | ElectroSpirit | 2296 | 7.653 | 2268 | 23.0% |
| pooled | K4CW | pv2 | Fireball | 282 | 0.940 | 276 | 34.4% |
| pooled | K4CW | pv2 | Zap | 2358 | 7.860 | 2350 | 54.0% |
| pooled | K4CW | pv2 | ElectroSpirit | 2767 | 9.223 | 2744 | 38.9% |
| pooled | K4CW | search | Fireball | 290 | 0.967 | 271 | 43.5% |
| pooled | K4CW | search | Zap | 1638 | 5.460 | 1625 | 53.2% |
| pooled | K4CW | search | ElectroSpirit | 2370 | 7.900 | 2343 | 24.6% |
| pooled | R3a | pv2 | Fireball | 549 | 1.830 | 527 | 36.2% |
| pooled | R3a | pv2 | Zap | 2388 | 7.960 | 2377 | 54.1% |
| pooled | R3a | pv2 | ElectroSpirit | 2829 | 9.430 | 2805 | 39.5% |
| pooled | R3a | search | Fireball | 352 | 1.173 | 325 | 46.8% |
| pooled | R3a | search | Zap | 1602 | 5.340 | 1593 | 54.9% |
| pooled | R3a | search | ElectroSpirit | 2314 | 7.713 | 2293 | 18.1% |
| pooled | all | pv2 | Fireball | 1389 | 1.543 | 1353 | 39.7% |
| pooled | all | pv2 | Zap | 7273 | 8.081 | 7252 | 53.3% |
| pooled | all | pv2 | ElectroSpirit | 8570 | 9.522 | 8495 | 38.4% |
| pooled | all | search | Fireball | 1000 | 1.111 | 934 | 48.5% |
| pooled | all | search | Zap | 4924 | 5.471 | 4895 | 55.3% |
| pooled | all | search | ElectroSpirit | 6980 | 7.756 | 6904 | 21.9% |

Fireball observation tick = play + ceil(distance from king (9,3) to aimed tile centre /0.6); Zap = play+1. ElectroSpirit = play+20 at the deployment aim; this is a deployment-proximity surrogate, not its later jump impact. Use the first own frame at or after that tick and enemy unit centres within 2.5 tiles. Towers are absent, killed units disappear, and no subsequent frame means exclusion from the observed denominator; these values are not literal damage/hit rates.

### Goblin Barrel answers and Cannon placement

| Row | Opp | Arm | Enemy Barrels | Answers ≤2 s | Share ≤2 s | Share ≤1.5 s | Cannon plays | Centre near king | Elsewhere |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | HPv2 | pv2 | 257 | 36 | 14.0% | 11.7% | 1078 | 7.1% | 92.9% |
| acc | HPv2 | search | 178 | 20 | 11.2% | 7.9% | 668 | 1.9% | 98.1% |
| acc | K4CW | pv2 | 181 | 3 | 1.7% | 1.1% | 1000 | 3.6% | 96.4% |
| acc | K4CW | search | 176 | 16 | 9.1% | 8.0% | 730 | 0.8% | 99.2% |
| acc | R3a | pv2 | 225 | 7 | 3.1% | 1.8% | 966 | 0.9% | 99.1% |
| acc | R3a | search | 200 | 21 | 10.5% | 8.5% | 717 | 0.7% | 99.3% |
| acc | all | pv2 | 663 | 46 | 6.9% | 5.4% | 3044 | 4.0% | 96.0% |
| acc | all | search | 554 | 57 | 10.3% | 8.1% | 2115 | 1.1% | 98.9% |
| l16 | HPv2 | pv2 | 239 | 26 | 10.9% | 7.5% | 1098 | 8.9% | 91.1% |
| l16 | HPv2 | search | 200 | 22 | 11.0% | 7.5% | 670 | 1.9% | 98.1% |
| l16 | K4CW | pv2 | 187 | 4 | 2.1% | 2.1% | 1016 | 4.6% | 95.4% |
| l16 | K4CW | search | 185 | 31 | 16.8% | 14.6% | 686 | 0.6% | 99.4% |
| l16 | R3a | pv2 | 242 | 4 | 1.7% | 1.2% | 957 | 1.7% | 98.3% |
| l16 | R3a | search | 199 | 20 | 10.1% | 5.5% | 676 | 1.2% | 98.8% |
| l16 | all | pv2 | 668 | 34 | 5.1% | 3.7% | 3071 | 5.2% | 94.8% |
| l16 | all | search | 584 | 73 | 12.5% | 9.1% | 2032 | 1.2% | 98.8% |
| pooled | HPv2 | pv2 | 496 | 62 | 12.5% | 9.7% | 2176 | 8.0% | 92.0% |
| pooled | HPv2 | search | 378 | 42 | 11.1% | 7.7% | 1338 | 1.9% | 98.1% |
| pooled | K4CW | pv2 | 368 | 7 | 1.9% | 1.6% | 2016 | 4.1% | 95.9% |
| pooled | K4CW | search | 361 | 47 | 13.0% | 11.4% | 1416 | 0.7% | 99.3% |
| pooled | R3a | pv2 | 467 | 11 | 2.4% | 1.5% | 1923 | 1.3% | 98.7% |
| pooled | R3a | search | 399 | 41 | 10.3% | 7.0% | 1393 | 0.9% | 99.1% |
| pooled | all | pv2 | 1331 | 80 | 6.0% | 4.6% | 6115 | 4.6% | 95.4% |
| pooled | all | search | 1138 | 130 | 11.4% | 8.6% | 4147 | 1.2% | 98.8% |

Barrel response = accepted own spell/troop (buildings excluded) aimed within 3 tiles of the opponent aim rotated to our frame (18−x,32−y), 0..40 ticks after the accepted Barrel play; sensitivity 0..30 ticks. It measures aimed response, not arrival or damage. Cannon centre-near-king = aim column floor(x)∈{7,8,9,10} and distance ≤5 from (9,3). Remaining standing metrics (decision reaction, Giant pushes, CPU medians and exact denominators) are fully retained below and in JSON.

| Row | Opp | Arm | Enemy→decision p50 / p90 s | Giant pushes | Undefended Giant share | CPU median ms | Decisions/game |
| --- | --- | --- | --- | --- | --- | --- | --- |
| acc | HPv2 | pv2 | 0.150 / 1.150 | 75 | 1.3% | 19.3 | 563.6 |
| acc | HPv2 | search | 0.400 / 1.150 | 64 | 6.2% | 362.8 | 139.1 |
| acc | K4CW | pv2 | 0.150 / 1.150 | 5 | 0.0% | 22.9 | 549.4 |
| acc | K4CW | search | 0.150 / 1.150 | 11 | 18.2% | 423.0 | 145.1 |
| acc | R3a | pv2 | 0.150 / 1.150 | 58 | 1.7% | 21.8 | 571.3 |
| acc | R3a | search | 0.400 / 1.150 | 53 | 7.5% | 406.5 | 143.5 |
| acc | all | pv2 | 0.150 / 1.150 | 138 | 1.4% | 21.6 | 561.5 |
| acc | all | search | 0.150 / 1.150 | 128 | 7.8% | 396.5 | 142.6 |
| l16 | HPv2 | pv2 | 0.150 / 1.150 | 76 | 0.0% | 20.2 | 560.6 |
| l16 | HPv2 | search | 0.400 / 1.150 | 70 | 7.1% | 382.7 | 140.2 |
| l16 | K4CW | pv2 | 0.150 / 1.150 | 6 | 0.0% | 22.4 | 544.6 |
| l16 | K4CW | search | 0.150 / 1.150 | 5 | 20.0% | 410.3 | 139.7 |
| l16 | R3a | pv2 | 0.150 / 1.150 | 57 | 1.8% | 21.8 | 557.1 |
| l16 | R3a | search | 0.400 / 0.900 | 52 | 5.8% | 413.6 | 140.3 |
| l16 | all | pv2 | 0.150 / 1.150 | 139 | 0.7% | 21.6 | 554.1 |
| l16 | all | search | 0.150 / 1.150 | 127 | 7.1% | 400.8 | 140.1 |
| pooled | HPv2 | pv2 | 0.150 / 1.150 | 151 | 0.7% | 19.7 | 562.1 |
| pooled | HPv2 | search | 0.400 / 1.150 | 134 | 6.7% | 373.4 | 139.6 |
| pooled | K4CW | pv2 | 0.150 / 1.150 | 11 | 0.0% | 22.5 | 547.0 |
| pooled | K4CW | search | 0.150 / 1.150 | 16 | 18.8% | 414.8 | 142.4 |
| pooled | R3a | pv2 | 0.150 / 1.150 | 115 | 1.7% | 21.8 | 564.2 |
| pooled | R3a | search | 0.400 / 1.150 | 105 | 6.7% | 408.0 | 141.9 |
| pooled | all | pv2 | 0.150 / 1.150 | 277 | 1.1% | 21.6 | 557.8 |
| pooled | all | search | 0.150 / 1.150 | 255 | 7.5% | 398.5 | 141.3 |

`from_second` is filtered out by PacketRecorder and is unavailable; no zero is inferred. The policy-only arm has no searched decisions, so the generic stats-based enemy→decision metric must not be read as search latency for pv2.

## Shadow action agreement and regret

Search-arm shadow games 900/900; actable shadow polls 498681; searched decisions 127187; decisions with a scorer snapshot 127187; timed-wait keys recovered 74640. Every searched PacketRecorder index is covered by a shadow record. Off-cadence polls/blocked holds are excluded from these tables.

Recorder correction: `shadow.search` is `Decision.action`, which normalizes timed holds to WAIT 2304. We recover 2400/2401/2402 from `packet_dec[n].stats.timed_wait` (10/20/40 ticks; interruptible wrapper), falling back to `wait_ticks`. Action agreement compares the submitted normalized WAIT/play; exact-key agreement additionally distinguishes timed hold from plain WAIT. The policy can represent play or WAIT, so duration disagreement alone cannot be fixed with a different gate label. We do not infer a key merely by taking argmax of scores.

Regret is search choice minus the policy action on matched scales: if both keys have final `work`/`scores`, subtract refined values; otherwise compare both native values from `coarse` (plays) and `waits` (holds). Key 2400 aliases WAIT 2304 in the native evaluator, so its native value is recovered from waits[2304]. Never subtract a refined chosen score from a native policy score. The candidate CSV maps all teacher holds to policy action WAIT 2304 and gate label 0, retaining the scored search key and duration separately. The final refined scores mix rollouts and include existing search bonuses/reserve terms, whereas coarse/native values do not. Unscored comparisons are excluded from means/medians and retained in coverage. The v2 top legal action can be absent from the search candidate set entirely; the coarse scan covers search candidates, not every legal tile. This censors regret non-randomly by decision type. Rankings are conditional on score availability, not a ranking of true policy error across all legal actions. Coarse regret can be negative because a refined choice need not maximize native coarse value. Signed totals/shares are primary; positive-only totals/shares are sensitivity. These sums mix scorer regimes and are prioritization proxies, not calibrated outcome value.

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 127187 | 53.2% | 7.3% | 107743 (84.7%) | 0.01839 | 0.00611 | 1981.5742 | 100.0% | 100.0% |

### Mutually exclusive broad decision types

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration | 58319 | 100.0% | 0.0% | 58319 (100.0%) | 0.01020 | 0.00596 | 595.1298 | 30.0% | 30.0% |
| search_plays_policy_waits | 17812 | 0.0% | 0.0% | 17812 (100.0%) | 0.03176 | 0.01258 | 565.7530 | 28.6% | 28.5% |
| same_card_different_tile | 13442 | 0.0% | 0.0% | 7461 (55.5%) | 0.04423 | 0.00973 | 330.0287 | 16.7% | 16.6% |
| search_holds_policy_plays | 21458 | 0.0% | 0.0% | 12419 (57.9%) | 0.02583 | 0.00975 | 320.7508 | 16.2% | 16.3% |
| different_class | 5423 | 0.0% | 0.0% | 2043 (37.7%) | 0.07370 | 0.01868 | 150.5774 | 7.6% | 7.6% |
| same_class_different_card | 1440 | 0.0% | 0.0% | 396 (27.5%) | 0.04882 | 0.01598 | 19.3346 | 1.0% | 1.0% |
| agreement | 9293 | 100.0% | 100.0% | 9293 (100.0%) | 0.00000 | 0.00000 | 0.0000 | 0.0% | 0.0% |

### Detailed types, ranked by signed regret

Transition A>B means policy class A → search class B. HogRider is a separate win-condition class; Cannon is building; Fireball/Zap are spells; other own cards are troops. Same-card tile changes are split by card. Same-class different-card choices remain separate from tile choices.

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration | 58319 | 100.0% | 0.0% | 58319 (100.0%) | 0.01020 | 0.00596 | 595.1298 | 30.0% | 30.0% |
| search_plays_policy_waits | 17812 | 0.0% | 0.0% | 17812 (100.0%) | 0.03176 | 0.01258 | 565.7530 | 28.6% | 28.5% |
| search_holds_policy_plays | 21458 | 0.0% | 0.0% | 12419 (57.9%) | 0.02583 | 0.00975 | 320.7508 | 16.2% | 16.3% |
| tile:Zap | 2207 | 0.0% | 0.0% | 1748 (79.2%) | 0.04290 | 0.00473 | 74.9924 | 3.8% | 3.8% |
| tile:ElectroSpirit | 2932 | 0.0% | 0.0% | 1299 (44.3%) | 0.04791 | 0.01077 | 62.2321 | 3.1% | 3.1% |
| tile:Cannon | 1650 | 0.0% | 0.0% | 996 (60.4%) | 0.05420 | 0.01177 | 53.9829 | 2.7% | 2.7% |
| tile:HogRider | 2503 | 0.0% | 0.0% | 1389 (55.5%) | 0.03838 | 0.01120 | 53.3159 | 2.7% | 2.7% |
| tile:Skeletons | 2103 | 0.0% | 0.0% | 1222 (58.1%) | 0.03385 | 0.01156 | 41.3623 | 2.1% | 2.1% |
| spell>troop | 1498 | 0.0% | 0.0% | 793 (52.9%) | 0.03874 | 0.01860 | 30.7182 | 1.6% | 1.5% |
| troop>spell | 693 | 0.0% | 0.0% | 146 (21.1%) | 0.18587 | 0.02004 | 27.1363 | 1.4% | 1.4% |
| tile:Archers | 1398 | 0.0% | 0.0% | 403 (28.8%) | 0.06079 | 0.01014 | 24.4987 | 1.2% | 1.2% |
| win_condition>troop | 586 | 0.0% | 0.0% | 202 (34.5%) | 0.09205 | 0.02378 | 18.5945 | 0.9% | 0.9% |
| spell>building | 349 | 0.0% | 0.0% | 180 (51.6%) | 0.10046 | 0.01683 | 18.0825 | 0.9% | 0.9% |
| tile:Fireball | 202 | 0.0% | 0.0% | 145 (71.8%) | 0.11761 | 0.00397 | 17.0531 | 0.9% | 0.9% |
| win_condition>spell | 214 | 0.0% | 0.0% | 57 (26.6%) | 0.28557 | 0.02424 | 16.2775 | 0.8% | 0.8% |
| troop>different_troop | 1317 | 0.0% | 0.0% | 321 (24.4%) | 0.04747 | 0.01537 | 15.2376 | 0.8% | 0.8% |
| troop>win_condition | 303 | 0.0% | 0.0% | 116 (38.3%) | 0.07260 | 0.02008 | 8.4211 | 0.4% | 0.4% |
| building>spell | 135 | 0.0% | 0.0% | 28 (20.7%) | 0.23652 | 0.01778 | 6.6226 | 0.3% | 0.3% |
| spell>win_condition | 197 | 0.0% | 0.0% | 85 (43.1%) | 0.07658 | 0.02696 | 6.5089 | 0.3% | 0.3% |
| win_condition>building | 114 | 0.0% | 0.0% | 43 (37.7%) | 0.13828 | 0.01521 | 5.9459 | 0.3% | 0.3% |
| building>troop | 675 | 0.0% | 0.0% | 217 (32.1%) | 0.02680 | 0.01418 | 5.8159 | 0.3% | 0.3% |
| troop>building | 536 | 0.0% | 0.0% | 150 (28.0%) | 0.03695 | 0.01513 | 5.5431 | 0.3% | 0.3% |
| spell>different_spell | 123 | 0.0% | 0.0% | 75 (61.0%) | 0.05463 | 0.01928 | 4.0970 | 0.2% | 0.2% |
| tile:Valkyrie | 447 | 0.0% | 0.0% | 259 (57.9%) | 0.01000 | 0.00593 | 2.5913 | 0.1% | 0.1% |
| building>win_condition | 123 | 0.0% | 0.0% | 26 (21.1%) | 0.03504 | 0.02543 | 0.9109 | 0.0% | 0.0% |
| agreement | 9293 | 100.0% | 100.0% | 9293 (100.0%) | 0.00000 | 0.00000 | 0.0000 | 0.0% | 0.0% |

### Top five types with different immediate policy actions

| Type | N | Scored N | Mean regret | Median regret | Share of action-disagreement regret |
| --- | --- | --- | --- | --- | --- |
| search_plays_policy_waits | 17812 | 17812 | 0.03176 | 0.01258 | 40.8% |
| search_holds_policy_plays | 21458 | 12419 | 0.02583 | 0.00975 | 23.1% |
| tile:Zap | 2207 | 1748 | 0.04290 | 0.00473 | 5.4% |
| tile:ElectroSpirit | 2932 | 1299 | 0.04791 | 0.01077 | 4.5% |
| tile:Cannon | 1650 | 996 | 0.05420 | 0.01177 | 3.9% |

The denominator here is 1386.444443 signed score units, excluding the same-WAIT duration comparisons; the preceding raw tables use all 1981.574213 units.

### Score coverage and separate scorer regimes

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| native | 12315 | 0.0% | 0.0% | 12315 (100.0%) | 0.04677 | 0.01301 | 575.9552 | 29.1% | 29.2% |
| refined | 95428 | 70.9% | 9.7% | 95428 (100.0%) | 0.01473 | 0.00604 | 1405.6190 | 70.9% | 70.8% |
| unscored | 19444 | 0.0% | 0.0% | 0 (0.0%) | NA | NA | 0.0000 | 0.0% | 0.0% |

| Type | Refined N | Native N | Unscored N | Refined signed sum | Native signed sum | Positive mass | Negative mass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration | 58319 | 0 | 0 | 595.12977 | 0.00000 | 595.12977 | 0.00000 |
| search_plays_policy_waits | 17812 | 0 | 0 | 565.75297 | 0.00000 | 565.75297 | 0.00000 |
| search_holds_policy_plays | 5603 | 6816 | 9039 | 114.53723 | 206.21353 | 323.87937 | -3.12862 |
| tile:Zap | 1131 | 617 | 459 | 33.17002 | 41.82239 | 74.99240 | 0.00000 |
| tile:ElectroSpirit | 511 | 788 | 1633 | 10.93594 | 51.29612 | 62.23206 | 0.00000 |
| tile:Cannon | 421 | 575 | 654 | 11.17429 | 42.80857 | 53.98286 | 0.00000 |
| tile:HogRider | 666 | 723 | 1114 | 26.34902 | 26.96691 | 53.31593 | 0.00000 |
| tile:Skeletons | 495 | 727 | 881 | 7.76096 | 33.60138 | 41.36234 | 0.00000 |
| spell>troop | 232 | 561 | 705 | 4.17410 | 26.54408 | 30.71819 | 0.00000 |
| troop>spell | 48 | 98 | 547 | 8.59185 | 18.54448 | 27.13633 | 0.00000 |
| tile:Archers | 176 | 227 | 995 | 3.58941 | 20.90933 | 24.49874 | 0.00000 |
| win_condition>troop | 56 | 146 | 384 | 4.02021 | 14.57431 | 18.59452 | 0.00000 |
| spell>building | 58 | 122 | 169 | 2.82387 | 15.25864 | 18.08252 | 0.00000 |
| tile:Fireball | 101 | 44 | 57 | 2.41803 | 14.63504 | 17.05307 | 0.00000 |
| win_condition>spell | 10 | 47 | 157 | 0.98581 | 15.29172 | 16.27753 | 0.00000 |
| troop>different_troop | 80 | 241 | 996 | 1.93930 | 13.29830 | 15.23760 | 0.00000 |
| troop>win_condition | 36 | 80 | 187 | 0.57191 | 7.84916 | 8.42107 | 0.00000 |
| building>spell | 8 | 20 | 107 | 1.97429 | 4.64827 | 6.62256 | 0.00000 |
| spell>win_condition | 27 | 58 | 112 | 0.66130 | 5.84758 | 6.50888 | 0.00000 |
| win_condition>building | 11 | 32 | 71 | 3.12085 | 2.82501 | 5.94586 | 0.00000 |
| building>troop | 73 | 144 | 458 | 1.78169 | 4.03419 | 5.81589 | 0.00000 |
| troop>building | 48 | 102 | 386 | 0.36198 | 5.18114 | 5.54312 | 0.00000 |
| spell>different_spell | 24 | 51 | 48 | 2.38483 | 1.71219 | 4.09702 | 0.00000 |
| tile:Valkyrie | 181 | 78 | 188 | 1.22345 | 1.36783 | 2.59129 | 0.00000 |
| building>win_condition | 8 | 18 | 97 | 0.18590 | 0.72503 | 0.91093 | 0.00000 |

### Agreement and regret by context

Phase = tick<2400 single elixir, otherwise double (the preregistered cutoff). Enemy units on our half use y<16; Hog on board is any visible enemy HogRider. “Just played” = accepted enemy Hog in the preceding 60 ticks (3 s), chosen before inspecting DX1 outcomes to align with RF1 reaction windows; the board-only and recent-only sensitivities are shown separately. Elixir buckets are [0,3),[3,6),[6,8),[8,10+]. Hand C/F/Z marks Cannon/Fireball/Zap available regardless of affordability. Counts are decision-weighted, so these context groups overlap and their shares must not be added.

#### row

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acc | 64152 | 53.2% | 7.4% | 54322 (84.7%) | 0.01919 | 0.00611 | 1042.4936 | 52.6% | 52.6% |
| l16 | 63035 | 53.1% | 7.2% | 53421 (84.7%) | 0.01758 | 0.00611 | 939.0806 | 47.4% | 47.4% |

#### opponent

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HPv2 | 41892 | 53.9% | 7.9% | 35860 (85.6%) | 0.01780 | 0.00611 | 638.4039 | 32.2% | 32.2% |
| LIVE-K4CW-r16-fp | 42730 | 52.1% | 6.8% | 35775 (83.7%) | 0.01993 | 0.00616 | 712.9953 | 36.0% | 36.0% |
| R3a | 42565 | 53.5% | 7.2% | 36108 (84.8%) | 0.01745 | 0.00611 | 630.1750 | 31.8% | 31.8% |

#### phase

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| double | 54977 | 39.1% | 10.1% | 41316 (75.2%) | 0.03162 | 0.00626 | 1306.5810 | 65.9% | 65.9% |
| single | 72210 | 63.9% | 5.1% | 66427 (92.0%) | 0.01016 | 0.00609 | 674.9932 | 34.1% | 34.1% |

#### enemy_our_half

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 55502 | 59.3% | 8.2% | 50104 (90.3%) | 0.01518 | 0.00601 | 760.7484 | 38.4% | 38.4% |
| True | 71685 | 48.4% | 6.6% | 57639 (80.4%) | 0.02118 | 0.00619 | 1220.8258 | 61.6% | 61.6% |

#### enemy_hog_board_or_recent

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 115188 | 54.0% | 7.2% | 97984 (85.1%) | 0.01759 | 0.00611 | 1723.5998 | 87.0% | 87.0% |
| True | 11999 | 45.0% | 8.3% | 9759 (81.3%) | 0.02643 | 0.00613 | 257.9744 | 13.0% | 13.0% |

#### enemy_hog_board

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 115188 | 54.0% | 7.2% | 97984 (85.1%) | 0.01759 | 0.00611 | 1723.5998 | 87.0% | 87.0% |
| True | 11999 | 45.0% | 8.3% | 9759 (81.3%) | 0.02643 | 0.00613 | 257.9744 | 13.0% | 13.0% |

#### enemy_hog_recent

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 122809 | 53.5% | 7.3% | 104259 (84.9%) | 0.01804 | 0.00611 | 1880.5564 | 94.9% | 94.9% |
| True | 4378 | 42.3% | 7.6% | 3484 (79.6%) | 0.02899 | 0.00629 | 101.0178 | 5.1% | 5.1% |

#### enemy_wincon_board

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 104044 | 54.7% | 7.2% | 88768 (85.3%) | 0.01692 | 0.00611 | 1502.0712 | 75.8% | 75.8% |
| True | 23143 | 46.2% | 8.0% | 18975 (82.0%) | 0.02527 | 0.00612 | 479.5030 | 24.2% | 24.2% |

#### elixir_bucket

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-<3 | 75003 | 69.2% | 7.3% | 69140 (92.2%) | 0.01483 | 0.00601 | 1025.6239 | 51.8% | 51.8% |
| 3-<6 | 49180 | 31.0% | 7.4% | 36392 (74.0%) | 0.02505 | 0.00812 | 911.6126 | 46.0% | 46.0% |
| 6-<8 | 2818 | 15.9% | 5.9% | 2095 (74.3%) | 0.02018 | 0.01116 | 42.2727 | 2.1% | 2.1% |
| 8+ | 186 | 9.1% | 2.7% | 116 (62.4%) | 0.01780 | 0.01308 | 2.0649 | 0.1% | 0.1% |

#### Cannon

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 52109 | 49.6% | 7.7% | 43040 (82.6%) | 0.01906 | 0.00615 | 820.1726 | 41.4% | 41.4% |
| True | 75078 | 55.6% | 7.1% | 64703 (86.2%) | 0.01795 | 0.00611 | 1161.4016 | 58.6% | 58.6% |

#### Fireball

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 12298 | 43.4% | 8.1% | 9949 (80.9%) | 0.02079 | 0.00642 | 206.8441 | 10.4% | 10.4% |
| True | 114889 | 54.2% | 7.2% | 97794 (85.1%) | 0.01815 | 0.00611 | 1774.7301 | 89.6% | 89.6% |

#### Zap

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 60759 | 55.9% | 8.5% | 51924 (85.5%) | 0.01735 | 0.00599 | 901.0820 | 45.5% | 45.5% |
| True | 66428 | 50.6% | 6.2% | 55819 (84.0%) | 0.01936 | 0.00625 | 1080.4922 | 54.5% | 54.5% |

#### hand_mask

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| --- | 573 | 35.6% | 8.7% | 433 (75.6%) | 0.02077 | 0.00636 | 8.9933 | 0.5% | 0.5% |
| --Z | 2390 | 37.3% | 6.9% | 1803 (75.4%) | 0.02421 | 0.00669 | 43.6433 | 2.2% | 2.2% |
| -F- | 18596 | 51.2% | 9.1% | 15366 (82.6%) | 0.01719 | 0.00601 | 264.1078 | 13.3% | 13.3% |
| -FZ | 30550 | 49.9% | 6.9% | 25438 (83.3%) | 0.01979 | 0.00621 | 503.4281 | 25.4% | 25.4% |
| C-- | 3608 | 47.3% | 11.4% | 3014 (83.5%) | 0.01801 | 0.00606 | 54.2698 | 2.7% | 2.7% |
| C-Z | 5727 | 44.3% | 6.5% | 4699 (82.0%) | 0.02127 | 0.00657 | 99.9376 | 5.0% | 5.0% |
| CF- | 37982 | 59.3% | 7.9% | 33111 (87.2%) | 0.01733 | 0.00596 | 573.7110 | 29.0% | 28.9% |
| CFZ | 27761 | 54.0% | 5.5% | 23879 (86.0%) | 0.01815 | 0.00624 | 433.4832 | 21.9% | 21.9% |

#### outcome_stratum

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| other | 78539 | 53.7% | 7.4% | 66797 (85.0%) | 0.01804 | 0.00611 | 1205.1199 | 60.8% | 60.8% |
| policy_win_search_loss | 15255 | 53.8% | 7.5% | 12974 (85.0%) | 0.01691 | 0.00613 | 219.4006 | 11.1% | 11.1% |
| search_win_policy_loss | 33393 | 51.6% | 7.0% | 27972 (83.8%) | 0.01991 | 0.00614 | 557.0537 | 28.1% | 28.1% |

### Same-card geometry

| Card/type | Tile disagreements | Mean distance | Median distance | Half changes | Lane changes |
| --- | --- | --- | --- | --- | --- |
| tile:Zap | 2207 | 3.788 | 2.000 | 352 | 384 |
| tile:ElectroSpirit | 2932 | 7.153 | 6.403 | 265 | 1424 |
| tile:Cannon | 1650 | 3.236 | 2.828 | 0 | 956 |
| tile:HogRider | 2503 | 7.073 | 7.000 | 351 | 1248 |
| tile:Skeletons | 2103 | 5.887 | 5.000 | 131 | 1065 |
| tile:Archers | 1398 | 5.543 | 5.000 | 64 | 840 |
| tile:Fireball | 202 | 3.042 | 1.414 | 18 | 25 |
| tile:Valkyrie | 447 | 4.183 | 2.236 | 60 | 154 |

#### tile_half (policy→search)

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| enemy>enemy | 1319 | 0.0% | 0.0% | 1068 (81.0%) | 0.04072 | 0.00673 | 43.4844 | 2.2% | 2.2% |
| enemy>own | 451 | 0.0% | 0.0% | 248 (55.0%) | 0.10765 | 0.01124 | 26.6973 | 1.3% | 1.3% |
| own>enemy | 790 | 0.0% | 0.0% | 371 (47.0%) | 0.16521 | 0.01857 | 61.2935 | 3.1% | 3.1% |
| own>own | 10882 | 0.0% | 0.0% | 5774 (53.1%) | 0.03439 | 0.00954 | 198.5536 | 10.0% | 10.0% |

#### tile_lane (policy→search)

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| centre>centre | 876 | 0.0% | 0.0% | 503 (57.4%) | 0.04080 | 0.00928 | 20.5235 | 1.0% | 1.0% |
| centre>left | 1425 | 0.0% | 0.0% | 554 (38.9%) | 0.05079 | 0.01290 | 28.1372 | 1.4% | 1.4% |
| centre>right | 1293 | 0.0% | 0.0% | 577 (44.6%) | 0.05733 | 0.01428 | 33.0772 | 1.7% | 1.7% |
| left>centre | 617 | 0.0% | 0.0% | 319 (51.7%) | 0.06288 | 0.01542 | 20.0579 | 1.0% | 1.0% |
| left>left | 3584 | 0.0% | 0.0% | 2440 (68.1%) | 0.02964 | 0.00686 | 72.3250 | 3.6% | 3.6% |
| left>right | 1086 | 0.0% | 0.0% | 400 (36.8%) | 0.08695 | 0.01645 | 34.7782 | 1.8% | 1.8% |
| right>centre | 585 | 0.0% | 0.0% | 290 (49.6%) | 0.10008 | 0.01590 | 29.0237 | 1.5% | 1.5% |
| right>left | 1090 | 0.0% | 0.0% | 433 (39.7%) | 0.07478 | 0.01614 | 32.3810 | 1.6% | 1.6% |
| right>right | 2886 | 0.0% | 0.0% | 1945 (67.4%) | 0.03071 | 0.00675 | 59.7248 | 3.0% | 3.0% |

#### tile_distance_bucket (policy→search)

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10+ | 2437 | 0.0% | 0.0% | 950 (39.0%) | 0.09267 | 0.01564 | 88.0378 | 4.4% | 4.4% |
| 2-<5 | 4309 | 0.0% | 0.0% | 2623 (60.9%) | 0.03897 | 0.00941 | 102.2151 | 5.2% | 5.2% |
| 5-<10 | 3807 | 0.0% | 0.0% | 1565 (41.1%) | 0.05383 | 0.01524 | 84.2496 | 4.3% | 4.2% |
| <2 | 2889 | 0.0% | 0.0% | 2323 (80.4%) | 0.02390 | 0.00360 | 55.5262 | 2.8% | 2.8% |

### Top types within the requested contexts

Each row below is a type × context intersection; shares use the total study regret denominator. The complete cross-tabulation, including every type and hand mask, is in `shadow-tables.json`/CSV.

#### Top five types by phase

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / double | 15927 | 100.0% | 0.0% | 15927 (100.0%) | 0.01721 | 0.00606 | 274.1823 | 13.8% | 13.8% |
| hold_duration / single | 42392 | 100.0% | 0.0% | 42392 (100.0%) | 0.00757 | 0.00591 | 320.9475 | 16.2% | 16.2% |
| search_holds_policy_plays / double | 12490 | 0.0% | 0.0% | 6465 (51.8%) | 0.03663 | 0.01074 | 236.8319 | 12.0% | 12.0% |
| search_holds_policy_plays / single | 8968 | 0.0% | 0.0% | 5954 (66.4%) | 0.01409 | 0.00884 | 83.9189 | 4.2% | 4.3% |
| search_plays_policy_waits / double | 7023 | 0.0% | 0.0% | 7023 (100.0%) | 0.05309 | 0.01295 | 372.8718 | 18.8% | 18.8% |
| search_plays_policy_waits / single | 10789 | 0.0% | 0.0% | 10789 (100.0%) | 0.01788 | 0.01236 | 192.8812 | 9.7% | 9.7% |
| tile:ElectroSpirit / double | 2021 | 0.0% | 0.0% | 836 (41.4%) | 0.06103 | 0.01058 | 51.0240 | 2.6% | 2.6% |
| tile:ElectroSpirit / single | 911 | 0.0% | 0.0% | 463 (50.8%) | 0.02421 | 0.01111 | 11.2081 | 0.6% | 0.6% |
| tile:Zap / double | 1308 | 0.0% | 0.0% | 977 (74.7%) | 0.06436 | 0.00543 | 62.8785 | 3.2% | 3.2% |
| tile:Zap / single | 899 | 0.0% | 0.0% | 771 (85.8%) | 0.01571 | 0.00355 | 12.1139 | 0.6% | 0.6% |

#### Top five types by enemy_our_half

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / False | 28398 | 100.0% | 0.0% | 28398 (100.0%) | 0.00971 | 0.00581 | 275.7359 | 13.9% | 13.9% |
| hold_duration / True | 29921 | 100.0% | 0.0% | 29921 (100.0%) | 0.01067 | 0.00606 | 319.3939 | 16.1% | 16.1% |
| search_holds_policy_plays / False | 6824 | 0.0% | 0.0% | 3989 (58.5%) | 0.02438 | 0.01016 | 97.2324 | 4.9% | 5.0% |
| search_holds_policy_plays / True | 14634 | 0.0% | 0.0% | 8430 (57.6%) | 0.02651 | 0.00955 | 223.5184 | 11.3% | 11.4% |
| search_plays_policy_waits / False | 10586 | 0.0% | 0.0% | 10586 (100.0%) | 0.02749 | 0.01267 | 290.9982 | 14.7% | 14.7% |
| search_plays_policy_waits / True | 7226 | 0.0% | 0.0% | 7226 (100.0%) | 0.03802 | 0.01241 | 274.7548 | 13.9% | 13.8% |
| tile:ElectroSpirit / False | 650 | 0.0% | 0.0% | 319 (49.1%) | 0.03075 | 0.01047 | 9.8096 | 0.5% | 0.5% |
| tile:ElectroSpirit / True | 2282 | 0.0% | 0.0% | 980 (42.9%) | 0.05349 | 0.01089 | 52.4225 | 2.6% | 2.6% |
| tile:Zap / False | 574 | 0.0% | 0.0% | 486 (84.7%) | 0.02686 | 0.00680 | 13.0526 | 0.7% | 0.7% |
| tile:Zap / True | 1633 | 0.0% | 0.0% | 1262 (77.3%) | 0.04908 | 0.00418 | 61.9398 | 3.1% | 3.1% |

#### Top five types by enemy_hog_board_or_recent

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / False | 53922 | 100.0% | 0.0% | 53922 (100.0%) | 0.01004 | 0.00596 | 541.3196 | 27.3% | 27.3% |
| hold_duration / True | 4397 | 100.0% | 0.0% | 4397 (100.0%) | 0.01224 | 0.00601 | 53.8101 | 2.7% | 2.7% |
| search_holds_policy_plays / False | 18876 | 0.0% | 0.0% | 10757 (57.0%) | 0.02491 | 0.00974 | 267.9388 | 13.5% | 13.6% |
| search_holds_policy_plays / True | 2582 | 0.0% | 0.0% | 1662 (64.4%) | 0.03178 | 0.00977 | 52.8119 | 2.7% | 2.7% |
| search_plays_policy_waits / False | 16649 | 0.0% | 0.0% | 16649 (100.0%) | 0.03084 | 0.01253 | 513.3969 | 25.9% | 25.9% |
| search_plays_policy_waits / True | 1163 | 0.0% | 0.0% | 1163 (100.0%) | 0.04502 | 0.01381 | 52.3561 | 2.6% | 2.6% |
| tile:ElectroSpirit / False | 2484 | 0.0% | 0.0% | 1043 (42.0%) | 0.04906 | 0.01086 | 51.1667 | 2.6% | 2.6% |
| tile:ElectroSpirit / True | 448 | 0.0% | 0.0% | 256 (57.1%) | 0.04322 | 0.01070 | 11.0654 | 0.6% | 0.6% |
| tile:Zap / False | 1963 | 0.0% | 0.0% | 1567 (79.8%) | 0.03756 | 0.00537 | 58.8636 | 3.0% | 3.0% |
| tile:Zap / True | 244 | 0.0% | 0.0% | 181 (74.2%) | 0.08911 | 0.00099 | 16.1288 | 0.8% | 0.8% |

#### Top five types by elixir_bucket

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / 0-<3 | 46431 | 100.0% | 0.0% | 46431 (100.0%) | 0.00960 | 0.00596 | 445.6720 | 22.5% | 22.5% |
| hold_duration / 3-<6 | 11593 | 100.0% | 0.0% | 11593 (100.0%) | 0.01264 | 0.00554 | 146.5812 | 7.4% | 7.4% |
| hold_duration / 6-<8 | 283 | 100.0% | 0.0% | 283 (100.0%) | 0.00945 | 0.00651 | 2.6753 | 0.1% | 0.1% |
| hold_duration / 8+ | 12 | 100.0% | 0.0% | 12 (100.0%) | 0.01678 | 0.01165 | 0.2013 | 0.0% | 0.0% |
| search_holds_policy_plays / 0-<3 | 10409 | 0.0% | 0.0% | 6713 (64.5%) | 0.02214 | 0.00915 | 148.6127 | 7.5% | 7.6% |
| search_holds_policy_plays / 3-<6 | 10691 | 0.0% | 0.0% | 5573 (52.1%) | 0.03045 | 0.01057 | 169.7054 | 8.6% | 8.6% |
| search_holds_policy_plays / 6-<8 | 332 | 0.0% | 0.0% | 124 (37.3%) | 0.01816 | 0.01272 | 2.2514 | 0.1% | 0.1% |
| search_holds_policy_plays / 8+ | 26 | 0.0% | 0.0% | 9 (34.6%) | 0.02014 | 0.01815 | 0.1812 | 0.0% | 0.0% |
| search_plays_policy_waits / 0-<3 | 7131 | 0.0% | 0.0% | 7131 (100.0%) | 0.03854 | 0.01189 | 274.8081 | 13.9% | 13.8% |
| search_plays_policy_waits / 3-<6 | 9368 | 0.0% | 0.0% | 9368 (100.0%) | 0.02863 | 0.01302 | 268.2304 | 13.5% | 13.5% |
| search_plays_policy_waits / 6-<8 | 1250 | 0.0% | 0.0% | 1250 (100.0%) | 0.01721 | 0.01356 | 21.5096 | 1.1% | 1.1% |
| search_plays_policy_waits / 8+ | 63 | 0.0% | 0.0% | 63 (100.0%) | 0.01912 | 0.01398 | 1.2048 | 0.1% | 0.1% |
| tile:ElectroSpirit / 0-<3 | 2129 | 0.0% | 0.0% | 1086 (51.0%) | 0.05280 | 0.01087 | 57.3407 | 2.9% | 2.9% |
| tile:ElectroSpirit / 3-<6 | 781 | 0.0% | 0.0% | 209 (26.8%) | 0.02314 | 0.01055 | 4.8354 | 0.2% | 0.2% |
| tile:ElectroSpirit / 6-<8 | 19 | 0.0% | 0.0% | 3 (15.8%) | 0.01752 | 0.02235 | 0.0526 | 0.0% | 0.0% |
| tile:ElectroSpirit / 8+ | 3 | 0.0% | 0.0% | 1 (33.3%) | 0.00347 | 0.00347 | 0.0035 | 0.0% | 0.0% |
| tile:Zap / 0-<3 | 1311 | 0.0% | 0.0% | 1057 (80.6%) | 0.04973 | 0.00461 | 52.5670 | 2.7% | 2.6% |
| tile:Zap / 3-<6 | 878 | 0.0% | 0.0% | 675 (76.9%) | 0.03284 | 0.00500 | 22.1652 | 1.1% | 1.1% |
| tile:Zap / 6-<8 | 18 | 0.0% | 0.0% | 16 (88.9%) | 0.01626 | 0.01153 | 0.2602 | 0.0% | 0.0% |

#### Top five types by Cannon

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / False | 21855 | 100.0% | 0.0% | 21855 (100.0%) | 0.00989 | 0.00596 | 216.0583 | 10.9% | 10.9% |
| hold_duration / True | 36464 | 100.0% | 0.0% | 36464 (100.0%) | 0.01040 | 0.00596 | 379.0715 | 19.1% | 19.1% |
| search_holds_policy_plays / False | 10048 | 0.0% | 0.0% | 5579 (55.5%) | 0.02827 | 0.01011 | 157.7239 | 8.0% | 8.0% |
| search_holds_policy_plays / True | 11410 | 0.0% | 0.0% | 6840 (59.9%) | 0.02383 | 0.00947 | 163.0269 | 8.2% | 8.3% |
| search_plays_policy_waits / False | 7477 | 0.0% | 0.0% | 7477 (100.0%) | 0.03130 | 0.01225 | 234.0424 | 11.8% | 11.8% |
| search_plays_policy_waits / True | 10335 | 0.0% | 0.0% | 10335 (100.0%) | 0.03210 | 0.01283 | 331.7106 | 16.7% | 16.7% |
| tile:ElectroSpirit / False | 1561 | 0.0% | 0.0% | 648 (41.5%) | 0.05087 | 0.01053 | 32.9628 | 1.7% | 1.7% |
| tile:ElectroSpirit / True | 1371 | 0.0% | 0.0% | 651 (47.5%) | 0.04496 | 0.01149 | 29.2693 | 1.5% | 1.5% |
| tile:Zap / False | 913 | 0.0% | 0.0% | 741 (81.2%) | 0.04281 | 0.00495 | 31.7256 | 1.6% | 1.6% |
| tile:Zap / True | 1294 | 0.0% | 0.0% | 1007 (77.8%) | 0.04297 | 0.00461 | 43.2668 | 2.2% | 2.2% |

#### Top five types by Fireball

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / False | 4341 | 100.0% | 0.0% | 4341 (100.0%) | 0.01016 | 0.00606 | 44.1043 | 2.2% | 2.2% |
| hold_duration / True | 53978 | 100.0% | 0.0% | 53978 (100.0%) | 0.01021 | 0.00595 | 551.0255 | 27.8% | 27.8% |
| search_holds_policy_plays / False | 2288 | 0.0% | 0.0% | 1246 (54.5%) | 0.02594 | 0.00984 | 32.3210 | 1.6% | 1.6% |
| search_holds_policy_plays / True | 19170 | 0.0% | 0.0% | 11173 (58.3%) | 0.02581 | 0.00974 | 288.4297 | 14.6% | 14.7% |
| search_plays_policy_waits / False | 2311 | 0.0% | 0.0% | 2311 (100.0%) | 0.03241 | 0.01279 | 74.8955 | 3.8% | 3.8% |
| search_plays_policy_waits / True | 15501 | 0.0% | 0.0% | 15501 (100.0%) | 0.03167 | 0.01255 | 490.8574 | 24.8% | 24.7% |
| tile:ElectroSpirit / False | 349 | 0.0% | 0.0% | 131 (37.5%) | 0.03500 | 0.01160 | 4.5847 | 0.2% | 0.2% |
| tile:ElectroSpirit / True | 2583 | 0.0% | 0.0% | 1168 (45.2%) | 0.04936 | 0.01070 | 57.6474 | 2.9% | 2.9% |
| tile:Zap / False | 237 | 0.0% | 0.0% | 181 (76.4%) | 0.07641 | 0.00369 | 13.8302 | 0.7% | 0.7% |
| tile:Zap / True | 1970 | 0.0% | 0.0% | 1567 (79.5%) | 0.03903 | 0.00477 | 61.1622 | 3.1% | 3.1% |

#### Top five types by Zap

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / False | 28822 | 100.0% | 0.0% | 28822 (100.0%) | 0.01028 | 0.00586 | 296.3093 | 15.0% | 14.9% |
| hold_duration / True | 29497 | 100.0% | 0.0% | 29497 (100.0%) | 0.01013 | 0.00606 | 298.8205 | 15.1% | 15.1% |
| search_holds_policy_plays / False | 7943 | 0.0% | 0.0% | 4145 (52.2%) | 0.02732 | 0.00836 | 113.2570 | 5.7% | 5.8% |
| search_holds_policy_plays / True | 13515 | 0.0% | 0.0% | 8274 (61.2%) | 0.02508 | 0.01053 | 207.4938 | 10.5% | 10.5% |
| search_plays_policy_waits / False | 9556 | 0.0% | 0.0% | 9556 (100.0%) | 0.02877 | 0.01268 | 274.9474 | 13.9% | 13.9% |
| search_plays_policy_waits / True | 8256 | 0.0% | 0.0% | 8256 (100.0%) | 0.03522 | 0.01245 | 290.8056 | 14.7% | 14.7% |
| tile:ElectroSpirit / False | 1839 | 0.0% | 0.0% | 893 (48.6%) | 0.04781 | 0.01152 | 42.6916 | 2.2% | 2.2% |
| tile:ElectroSpirit / True | 1093 | 0.0% | 0.0% | 406 (37.1%) | 0.04813 | 0.00949 | 19.5405 | 1.0% | 1.0% |
| tile:Zap / True | 2207 | 0.0% | 0.0% | 1748 (79.2%) | 0.04290 | 0.00473 | 74.9924 | 3.8% | 3.8% |

#### Top five types by outcome_stratum

| Context/type | N | Action agree | Key agree | Scored | Mean regret | Median regret | Signed sum | Share signed regret | Share positive regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hold_duration / other | 36364 | 100.0% | 0.0% | 36364 (100.0%) | 0.00995 | 0.00596 | 361.6825 | 18.3% | 18.2% |
| hold_duration / policy_win_search_loss | 7069 | 100.0% | 0.0% | 7069 (100.0%) | 0.00943 | 0.00596 | 66.6317 | 3.4% | 3.4% |
| hold_duration / search_win_policy_loss | 14886 | 100.0% | 0.0% | 14886 (100.0%) | 0.01121 | 0.00596 | 166.8156 | 8.4% | 8.4% |
| search_holds_policy_plays / other | 13026 | 0.0% | 0.0% | 7551 (58.0%) | 0.02560 | 0.00968 | 193.3003 | 9.8% | 9.8% |
| search_holds_policy_plays / policy_win_search_loss | 2379 | 0.0% | 0.0% | 1362 (57.3%) | 0.02228 | 0.00972 | 30.3396 | 1.5% | 1.5% |
| search_holds_policy_plays / search_win_policy_loss | 6053 | 0.0% | 0.0% | 3506 (57.9%) | 0.02770 | 0.00985 | 97.1109 | 4.9% | 4.9% |
| search_plays_policy_waits / other | 11006 | 0.0% | 0.0% | 11006 (100.0%) | 0.03181 | 0.01234 | 350.0870 | 17.7% | 17.6% |
| search_plays_policy_waits / policy_win_search_loss | 2179 | 0.0% | 0.0% | 2179 (100.0%) | 0.03049 | 0.01308 | 66.4309 | 3.4% | 3.3% |
| search_plays_policy_waits / search_win_policy_loss | 4627 | 0.0% | 0.0% | 4627 (100.0%) | 0.03225 | 0.01288 | 149.2350 | 7.5% | 7.5% |
| tile:ElectroSpirit / other | 1794 | 0.0% | 0.0% | 812 (45.3%) | 0.04272 | 0.01086 | 34.6902 | 1.8% | 1.7% |
| tile:ElectroSpirit / policy_win_search_loss | 389 | 0.0% | 0.0% | 184 (47.3%) | 0.05998 | 0.01210 | 11.0364 | 0.6% | 0.6% |
| tile:ElectroSpirit / search_win_policy_loss | 749 | 0.0% | 0.0% | 303 (40.5%) | 0.05447 | 0.01027 | 16.5054 | 0.8% | 0.8% |
| tile:Zap / other | 1395 | 0.0% | 0.0% | 1100 (78.9%) | 0.03920 | 0.00445 | 43.1148 | 2.2% | 2.2% |
| tile:Zap / policy_win_search_loss | 254 | 0.0% | 0.0% | 218 (85.8%) | 0.04967 | 0.00450 | 10.8274 | 0.5% | 0.5% |
| tile:Zap / search_win_policy_loss | 558 | 0.0% | 0.0% | 430 (77.1%) | 0.04895 | 0.00500 | 21.0502 | 1.1% | 1.1% |

## Training targets for HP1 RL

### Priority 1: timely useful plays when the policy waits

Use the 17,812 search-play/policy-WAIT states as the first ExIt curriculum: all 17,812 have both actions refined-scored, mean margin 0.03176, median 0.01258. The double-elixir subset has 7,023 states and mean margin 0.05309, versus 0.01788 in single elixir. Enemy-on-our-half states have mean margin 0.03802 (7,226 states); the 10,586 without an incursion still contribute 290.998 score units, so this is not exclusively a defensive-reaction problem. Upweight late, low-to-medium elixir states with clear positive margins and retain both initiative and urgent-response examples.

The missed search plays span the deck. By measured regret they start with Zap (1,768 states; sum 127.060), Skeletons (4,253; 118.159), ElectroSpirit (3,515; 91.521), Archers (3,309; 79.082), then HogRider (2,134; 56.967) and Cannon (1,498; 54.219). This is broader than a “play Hog more” target. Labels are gate=play plus the search's conditional card and tile. Distill a scored action distribution where several actions are near-tied; use a strong one-action target only when the margin over the student's alternative and other refined alternatives is clearly large. The worked examples include a missed Hog play and a missed Zap with approximately two score units of modeled advantage; those are model predictions, not proven counterfactual wins.

### Priority 2: selective holds instead of low-value Zap/cycle spends

The opposite gate error has 21,458 states, with 12,419 scored (57.88% coverage), mean measured margin 0.02583 and median 0.00975. Double elixir accounts for 236.832 of its 320.751 signed score units; enemy-on-our-half states account for 223.518. States with 3..6 elixir have mean measured margin 0.03045. Upweight these scored states alongside Priority 1, rather than shifting a global threshold toward playing or waiting in every state.

Zap is the largest policy-play component: 6,703 proposed Zap spends, 5,151 scored, sum 139.154. Skeletons and ElectroSpirit contribute another 51.796 and 46.029. Labels are gate=WAIT with a masked conditional play loss. Keep the scored hold key/duration as auxiliary training metadata; all actual policy action labels normalize holds to WAIT 2304. Distill across subsequent public states if learning how long to remain patient; immediate same-WAIT `hold_duration` comparisons alone cannot supervise a different current gate decision. Do not implement a card-specific hold rule or an elixir reserve reward. Search itself already includes reserve/wait terms, which should not become the student's objective by assumption.

### Priority 3: state-dependent tile value for Zap, ElectroSpirit and Cannon

Prioritize the conditional tile head once the same card is selected. Zap has 2,207 tile disagreements (1,748 scored; mean/median margin 0.04290/0.00473; 5.41% of action-disagreement regret), ElectroSpirit 2,932 (1,299 scored; 0.04791/0.01077; 4.49%), and Cannon 1,650 (996 scored; 0.05420/0.01177; 3.89%). Those three total 6,789 disagreements and 13.79% of measured action-disagreement regret. Mean tile distances are 3.79, 7.15 and 3.24 tiles respectively; lane-label changes occur in 384, 1,424 and 956 states (centre→side changes are included, not just left↔right).

For Zap, upweight double elixir, enemy units on our half, and 0..3 elixir. For ElectroSpirit, upweight double elixir and low-elixir threatened states while retaining the wide placement distribution. For Cannon, 1,529/1,650 disagreements have enemies on our half; they carry 53.225/53.983 measured score units. Hog-on-board/recent states carry 27.094 Cannon score units, roughly half the Cannon burden. Supervise relative board-aware tile/action value, with teacher soft targets across scored placements and explicit coverage accounting. Do not hard-code a Cannon square, lane, Spirit deployment point or spell radius reward. The Cannon worked examples are included in addition to the raw top-five types.

### Labels, data collection and objective

`exit-target-candidates.csv` contains **25,845 positive refined comparisons with different immediate policy actions**, including source packet paths/indices, normalized action and gate label, scored search key/duration, margin and paired-outcome stratum. It is an auditable candidate index, not a recommendation to train indiscriminately on every row. Filter to completed search decisions, reject tiny/tied margins, inspect the full refined work set, cap contributions per game, and stratify by phase/type. Choose margin cutoffs/weights on disjoint validation data; do not add a fixed gameplay rule. Native-only comparisons remain valuable diagnosis and collection priorities, but should receive confidence checks or fresh matched refinement before becoming strong one-action labels. Preserve the 19,444 unscored states as a collection target: their missingness is not random, especially for placement.

The retained `packet_perc` summaries omit tower health, the full policy feature packet, action masks and D1 history. They are sufficient for these descriptive tables, but are not complete training inputs. Recover full inputs by deterministic case/action replay with a feature recorder, or collect fresh disjoint training trajectories with complete model inputs; do not feed the partial board summaries as though they were the original policy state. Tower health is also unavailable in the worked board summaries, so a large-margin enemy-half Zap must not be asserted to be a verified lethal spell.

Collect equivalent states on **student trajectories** with search labeling during training (DAgger/ExIt), then deploy the policy alone. Search-trajectory labels alone do not cover the states reached after the student diverges. Where possible, confirm high-margin targets with an independent search sample or matched rollout evaluation; require outcome improvement on held-out seeds before trusting the search's model preference. The 226 search-win/policy-loss pairs locate useful examples, but their game label is not a causal action-advantage label for every shadow state.

Use terminal win/draw/loss reward as the primary RL objective, plus an auxiliary distillation loss for gate/card/tile targets. Compare outcome-only RL with outcome-RL plus distillation. A shaping candidate is a learned outcome-value potential, `gamma*Phi(next_state)-Phi(state)`, with consistent discounting and zero terminal potential; learn Phi from game outcomes and validate the objective rather than manually rewarding particular cards, reserve levels, lanes or proximity. Avoid treating the search's 8-second score, its reserve penalty, or its wait bonus as ground-truth reward. Calibrate the fine-tuned gate/threshold on held-out play: changing the network can change the meaning of the human-policy tau*.

### Opponent pool and confirmation

Prioritize **LIVE-K4CW-r16-fp**, where the deficit is largest and clear at both level rows. Retain **R3a** (clear pooled deficit; the account-only interval includes zero) and **HPv2** (no resolved pooled difference) as diversity/retention opponents. Add frozen current live K4L search snapshots as training opponents and direct head-to-head benchmarks for Sam's policy-only-beats-live-search goal; retain older snapshots to limit forgetting. Keep L16 and account rows separate in evaluation and retain the 53-row pool coverage. Select pool weights using held-out outcomes, not a hand-set defensive script. No new training or matches were launched by this analysis.

The confirmation experiment should compare a new policy-only checkpoint against the fixed live bot on new paired seeds, at both level rows, with the same outcome and RF1 diagnostics. Do not promote solely because a proxy improved or a teacher regret fell. If DX1 examples are used for training, retire DX1 from held-out evaluation.

## Five worked examples for the raw top five types and the top five actionable types

Select highest positive-regret examples from distinct paired cases where search won and pv2 lost, then fill from other distinct cases if needed. Selection is illustrative and outcome-conditioned; it does not establish a causal error by the policy. Board summaries use the exact search-arm perception, not the diverged policy-arm board. Coordinates below are zero-based action tile indices; units are continuous tile coordinates. Action-score pairs and record paths are in `examples.json` and `flip-examples.json`; the full work/scores arrays are retained in each referenced raw search game.

### hold_duration

Count 58319; scored 58319; signed regret share 30.0%; positive-only share 30.0%.

1. **l16 / K4CW / case 133 / tick 3590** (packet n=700, seat=1, seed=2680308772461365; search_win_policy_loss). Elixir 3.357; gate 0.01824; hand slots 0..3: Fireball, Skeletons, Cannon, Zap.
   Ours: Archer(8.00,13.50); Archer(9.00,13.50); ElectroSpirit(13.22,7.86); Valkyrie(14.08,16.93).
   Enemy: Skeleton(8.33,15.17); Skeleton(5.48,17.66); Skeleton(11.79,18.26); Skeleton(7.56,19.56); Valkyrie(4.14,17.46); Witch(8.50,18.50).
   Policy: WAIT. Search: hold 20 ticks (key 2401; decoded WAIT).
   refined scores: search 2.000000, policy -1.046065; regret +3.046065. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s1/rows/000133-00.json`.

2. **l16 / R3a / case 80 / tick 3780** (packet n=738, seat=0, seed=2680308772461463; search_win_policy_loss). Elixir 3.142; gate 0.00974; hand slots 0..3: Fireball, HogRider, Valkyrie, Cannon.
   Ours: ElectroSpirit(14.11,16.98); Skeleton(14.11,19.38); Cannon(16.50,12.50).
   Enemy: Cannon(3.50,21.50).
   Policy: WAIT. Search: hold 40 ticks (key 2402; decoded WAIT).
   refined scores: search 2.000000, policy -0.025005; regret +2.025005. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s2/rows/000230-00.json`.

3. **acc / HPv2 / case 129 / tick 5700** (packet n=1122, seat=1, seed=2680308772461663; search_win_policy_loss). Elixir 1.946; gate 0.00000; hand slots 0..3: Valkyrie, Fireball, Cannon, Zap.
   Ours: Archer(13.00,14.50); Archer(14.00,14.50); ElectroSpirit(13.67,10.31); HogRider(15.69,13.81); Skeleton(13.49,8.68); Skeleton(14.09,11.06); Skeleton(13.53,11.85).
   Enemy: Minion(3.50,16.92); Minion(3.00,17.79); Minion(4.00,17.79); Cannon(3.50,21.50).
   Policy: WAIT. Search: hold 40 ticks (key 2402; decoded WAIT).
   refined scores: search 0.022855, policy -2.000000; regret +2.022855. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s3/rows/000429-00.json`.

4. **acc / K4CW / case 72 / tick 5810** (packet n=1144, seat=0, seed=2680308772461304; search_win_policy_loss). Elixir 2.858; gate 0.00000; hand slots 0..3: HogRider, Valkyrie, Cannon, Fireball.
   Ours: Archer(2.21,14.02); Archer(1.28,14.57); Skeleton(13.77,13.03); Skeleton(15.20,13.10).
   Enemy: Archer(14.98,15.74); MiniPekka(3.20,21.50); Minion(4.04,19.51); Musketeer(3.50,28.50).
   Policy: WAIT. Search: hold 40 ticks (key 2402; decoded WAIT).
   refined scores: search 2.000000, policy -0.020687; regret +2.020687. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/acc-s0/rows/000072-00.json`.

5. **acc / HPv2 / case 13 / tick 3690** (packet n=720, seat=1, seed=2680308772461547; search_win_policy_loss). Elixir 1.928; gate 0.00363; hand slots 0..3: Skeletons, Valkyrie, Cannon, Fireball.
   Ours: Archer(3.16,16.43); Archer(3.30,17.42); ElectroSpirit(3.23,14.38); HogRider(4.16,15.00).
   Enemy: BattleRam(14.50,17.50); Musketeer(10.93,21.07).
   Policy: WAIT. Search: hold 40 ticks (key 2402; decoded WAIT).
   refined scores: search 0.011416, policy -2.000000; regret +2.011416. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/acc-s1/rows/000313-00.json`.

### search_plays_policy_waits

Count 17812; scored 17812; signed regret share 28.6%; positive-only share 28.5%.

1. **acc / R3a / case 101 / tick 4420** (packet n=866, seat=1, seed=2680308772461484; search_win_policy_loss). Elixir 4.000; gate 0.01663; hand slots 0..3: Cannon, HogRider, Fireball, Valkyrie.
   Ours: Archer(7.07,14.67); Archer(13.38,15.25); Skeleton(2.38,8.10); Skeleton(2.57,9.10); Skeleton(2.71,10.09).
   Enemy: Knight(4.19,15.60); Valkyrie(4.21,17.55).
   Policy: WAIT. Search: HogRider slot 1 @ tile (3,13) [own, left].
   refined scores: search 2.000000, policy -0.018590; regret +2.018590. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5/rows/000251-00.json`.

2. **l16 / HPv2 / case 93 / tick 3750** (packet n=732, seat=1, seed=2680308772461627; search_win_policy_loss). Elixir 2.071; gate 0.00947; hand slots 0..3: Valkyrie, Zap, Fireball, Archers.
   Ours: Archer(13.26,14.96); HogRider(13.59,23.45); Skeleton(15.10,23.62); Skeleton(12.93,24.41); Skeleton(12.76,25.39); Cannon(9.50,9.50).
   Enemy: HogRider(11.27,8.73).
   Policy: WAIT. Search: Zap slot 1 @ tile (14,22) [enemy, right].
   refined scores: search 2.000000, policy -0.013499; regret +2.013499. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s3/rows/000393-00.json`.

3. **acc / HPv2 / case 83 / tick 3840** (packet n=750, seat=1, seed=2680308772461617; search_win_policy_loss). Elixir 4.285; gate 0.01023; hand slots 0..3: Skeletons, Cannon, Valkyrie, Fireball.
   Ours: Archer(3.37,19.06); Archer(4.82,19.18); HogRider(4.53,23.28).
   Enemy: MiniPekka(3.50,23.50).
   Policy: WAIT. Search: Fireball slot 3 @ tile (4,22) [enemy, left].
   refined scores: search 1.989275, policy -0.016916; regret +2.006191. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5-r2/rows/000383-00.json`.

4. **l16 / K4CW / case 62 / tick 4730** (packet n=928, seat=0, seed=2680308772461294; search_win_policy_loss). Elixir 2.071; gate 0.01365; hand slots 0..3: Fireball, Valkyrie, Zap, Archers.
   Ours: ElectroSpirit(2.50,2.50); Cannon(9.50,13.50).
   Enemy: BabyDragon(10.62,17.93); MiniPekka(5.20,15.17); Skeleton(4.51,14.53); Skeleton(13.54,15.70); Skeleton(4.43,15.73); Skeleton(4.46,16.84); Skeleton(13.31,21.41); Skeleton(12.26,21.67); Skeleton(11.23,21.92); Skeleton(13.85,22.32); Skeleton(12.81,22.43); Skeleton(11.95,22.60); Skeleton(14.79,22.66); Skeleton(10.89,22.94); Skeleton(12.28,23.55); Skeleton(13.02,24.22).
   Policy: WAIT. Search: Zap slot 2 @ tile (13,20) [enemy, right].
   refined scores: search 0.001755, policy -2.000000; regret +2.001755. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s2/rows/000062-00.json`.

5. **acc / HPv2 / case 48 / tick 3990** (packet n=780, seat=0, seed=2680308772461582; search_win_policy_loss). Elixir 3.642; gate 0.01165; hand slots 0..3: Fireball, Cannon, Valkyrie, Archers.
   Ours: ElectroSpirit(3.26,19.83); HogRider(3.22,23.12); Skeleton(3.20,20.70); Skeleton(4.10,21.22); Skeleton(4.31,22.45); Valkyrie(3.21,21.61); Cannon(10.50,7.50).
   Enemy: none.
   Policy: WAIT. Search: Archers slot 3 @ tile (9,20) [enemy, centre].
   refined scores: search 1.994630, policy -0.002366; regret +1.996996. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/acc-s0/rows/000348-00.json`.

### search_holds_policy_plays

Count 21458; scored 12419; signed regret share 16.2%; positive-only share 16.3%.

1. **l16 / K4CW / case 62 / tick 4970** (packet n=976, seat=0, seed=2680308772461294; search_win_policy_loss). Elixir 3.708; gate 0.03286; hand slots 0..3: Fireball, Valkyrie, HogRider, Zap.
   Ours: Archer(5.15,6.46); Archer(2.67,8.51); ElectroSpirit(12.50,11.50); Cannon(10.50,10.50).
   Enemy: BabyDragon(13.50,11.50); MiniPekka(11.63,11.90); SkeletonWarrior(3.26,14.45); SkeletonWarrior(2.89,16.02); SkeletonWarrior(3.88,16.22).
   Policy: Zap slot 3 @ tile (12,12) [own, right]. Search: WAIT.
   refined scores: search 2.000000, policy -0.995658; regret +2.995658. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s2/rows/000062-00.json`.

2. **l16 / K4CW / case 47 / tick 4400** (packet n=862, seat=1, seed=2680308772461279; search_win_policy_loss). Elixir 3.285; gate 0.05164; hand slots 0..3: Fireball, Cannon, Zap, Valkyrie.
   Ours: Archer(5.00,7.50); Archer(6.00,7.50); HogRider(13.59,23.22).
   Enemy: Barbarian(3.82,9.54); Barbarian(4.23,10.44); Barbarian(3.77,11.41); Barbarian(3.27,12.48); Barbarian(3.77,13.49); Skeleton(14.05,21.79); Skeleton(12.61,22.64); Skeleton(14.30,23.97); Skeleton(15.20,24.06); Witch(14.60,22.63).
   Policy: Zap slot 2 @ tile (14,23) [enemy, right]. Search: hold 40 ticks (key 2402; decoded WAIT).
   refined scores: search 2.000000, policy -0.060690; regret +2.060690. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s5/rows/000047-00.json`.

3. **l16 / HPv2 / case 89 / tick 5410** (packet n=1064, seat=1, seed=2680308772461623; search_win_policy_loss). Elixir 3.358; gate 0.04052; hand slots 0..3: Archers, ElectroSpirit, HogRider, Fireball.
   Ours: Archer(13.33,17.76); Valkyrie(3.38,12.13); Cannon(7.50,10.50).
   Enemy: Knight(14.60,20.64); Cannon(3.50,21.50); Cannon(16.50,21.50).
   Policy: ElectroSpirit slot 1 @ tile (14,14) [own, right]. Search: WAIT.
   native scores: search 2.000000, policy -0.010291; regret +2.010291. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s5/rows/000389-00.json`.

4. **l16 / R3a / case 23 / tick 4110** (packet n=804, seat=1, seed=2680308772461406; search_win_policy_loss). Elixir 2.928; gate 0.02543; hand slots 0..3: Fireball, Valkyrie, Zap, Skeletons.
   Ours: Archer(2.98,4.56); Archer(4.02,4.56); HogRider(15.37,23.35); Skeleton(4.13,9.94); Skeleton(3.18,10.25).
   Enemy: MiniPekka(14.64,21.70).
   Policy: Zap slot 2 @ tile (14,22) [enemy, right]. Search: hold 40 ticks (key 2402; decoded WAIT).
   native scores: search 2.000000, policy 0.001496; regret +1.998504. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s5/rows/000173-00.json`.

5. **l16 / HPv2 / case 120 / tick 3470** (packet n=676, seat=0, seed=2680308772461654; search_win_policy_loss). Elixir 2.071; gate 0.02249; hand slots 0..3: Zap, Fireball, HogRider, Valkyrie.
   Ours: Archer(5.31,23.22); Archer(4.46,23.84); Skeleton(11.69,6.93); Skeleton(13.06,7.01); Skeleton(12.27,7.75).
   Enemy: Barbarian(13.27,8.02); Knight(8.84,11.16); MiniPekka(12.20,8.74).
   Policy: Zap slot 0 @ tile (12,8) [own, right]. Search: WAIT.
   native scores: search 2.000000, policy 0.011364; regret +1.988636. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s0/rows/000420-00.json`.

### tile:Zap

Count 2207; scored 1748; signed regret share 3.8%; positive-only share 3.8%.

1. **acc / K4CW / case 124 / tick 4230** (packet n=828, seat=0, seed=2680308772461356; search_win_policy_loss). Elixir 2.214; gate 0.02010; hand slots 0..3: Zap, HogRider, Fireball, Valkyrie.
   Ours: Archer(5.05,5.93); Archer(5.97,6.21); Cannon(7.50,10.50).
   Enemy: Archer(15.76,12.86); Archer(13.71,12.92); BattleRam(14.50,18.50); HogRider(14.74,9.81).
   Policy: Zap slot 0 @ tile (14,10) [own, right]. Search: Zap slot 0 @ tile (2,22) [enemy, left].
   refined scores: search 2.000000, policy -2.000000; regret +4.000000. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s4/rows/000124-00.json`.

2. **acc / K4CW / case 131 / tick 5430** (packet n=1068, seat=1, seed=2680308772461363; search_win_policy_loss). Elixir 2.433; gate 0.03002; hand slots 0..3: Valkyrie, Skeletons, Zap, Fireball.
   Ours: HogRider(4.97,17.03); Cannon(10.50,13.50).
   Enemy: Knight(8.50,12.50); Skeleton(12.55,14.29); Skeleton(15.71,14.87); Skeleton(13.69,16.08); SkeletonWarrior(5.57,13.81); SkeletonWarrior(3.54,13.84); SkeletonWarrior(3.90,16.31); Witch(14.69,15.14).
   Policy: Zap slot 2 @ tile (13,14) [own, right]. Search: Zap slot 2 @ tile (4,22) [enemy, left].
   refined scores: search 2.000000, policy -0.027818; regret +2.027818. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5/rows/000131-00.json`.

3. **acc / R3a / case 60 / tick 4360** (packet n=854, seat=0, seed=2680308772461443; search_win_policy_loss). Elixir 2.857; gate 0.08005; hand slots 0..3: Zap, Valkyrie, Cannon, Archers.
   Ours: HogRider(3.55,13.79); Skeleton(3.99,15.23); Skeleton(4.08,16.22); Skeleton(14.10,16.56).
   Enemy: BattleRam(3.57,18.42); HogRider(2.89,14.94).
   Policy: Zap slot 0 @ tile (3,14) [own, left]. Search: Zap slot 0 @ tile (13,22) [enemy, right].
   native scores: search 2.000000, policy -0.025965; regret +2.025965. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/acc-s0/rows/000210-00.json`.

4. **acc / R3a / case 101 / tick 4220** (packet n=826, seat=1, seed=2680308772461484; search_win_policy_loss). Elixir 2.857; gate 0.06119; hand slots 0..3: Cannon, Zap, Fireball, Archers.
   Ours: HogRider(4.03,19.47); Cannon(10.50,9.50).
   Enemy: Knight(2.21,18.55); Skeleton(13.29,13.84); Skeleton(14.22,14.39); Skeleton(13.44,15.05); Skeleton(15.30,15.22); Skeleton(14.37,15.32); Skeleton(15.07,16.14); Skeleton(13.89,16.16); Skeleton(13.56,17.01); Skeleton(14.51,17.04); Skeleton(13.81,17.90); Skeleton(13.45,18.91); Skeleton(14.41,19.15); Skeleton(13.77,19.94); Skeleton(15.25,20.58); Skeleton(13.70,20.95); SkeletonWarrior(2.99,15.34).
   Policy: Zap slot 1 @ tile (14,16) [enemy, right]. Search: Zap slot 1 @ tile (2,19) [enemy, left].
   native scores: search 2.000000, policy 0.003777; regret +1.996223. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5/rows/000251-00.json`.

5. **l16 / HPv2 / case 30 / tick 5110** (packet n=1004, seat=0, seed=2680308772461564; search_win_policy_loss). Elixir 3.233; gate 0.02423; hand slots 0..3: Valkyrie, Zap, HogRider, Archers.
   Ours: Archer(14.66,10.71); Archer(15.74,10.80); Skeleton(13.66,12.77); Skeleton(15.20,13.10); Skeleton(14.64,14.51); Cannon(10.50,10.50).
   Enemy: SkeletonDragon(15.07,16.70); SkeletonDragon(17.60,16.80); SkeletonWarrior(14.06,13.69).
   Policy: Zap slot 1 @ tile (14,13) [own, right]. Search: Zap slot 1 @ tile (13,22) [enemy, right].
   native scores: search 2.000000, policy 0.128133; regret +1.871867. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s0/rows/000330-00.json`.

### tile:ElectroSpirit

Count 2932; scored 1299; signed regret share 3.1%; positive-only share 3.1%.

1. **l16 / R3a / case 60 / tick 3760** (packet n=734, seat=0, seed=2680308772461443; search_win_policy_loss). Elixir 2.428; gate 0.02975; hand slots 0..3: Valkyrie, ElectroSpirit, Fireball, Cannon.
   Ours: Archer(6.99,12.51); Archer(12.85,14.72); HogRider(12.91,18.40); Skeleton(2.55,13.70); Skeleton(2.33,14.68); Skeleton(5.24,14.69).
   Enemy: Archer(3.00,20.50); Archer(4.00,20.50); BattleRam(3.80,13.06).
   Policy: ElectroSpirit slot 1 @ tile (3,8) [own, left]. Search: ElectroSpirit slot 1 @ tile (13,14) [own, right].
   native scores: search 2.000000, policy -0.017786; regret +2.017786. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s0/rows/000210-00.json`.

2. **acc / HPv2 / case 119 / tick 4590** (packet n=900, seat=1, seed=2680308772461653; search_win_policy_loss). Elixir 2.071; gate 0.03947; hand slots 0..3: Fireball, ElectroSpirit, Cannon, Archers.
   Ours: Skeleton(7.80,20.10); Skeleton(9.20,20.10); Skeleton(8.50,21.31); Valkyrie(11.35,21.29).
   Enemy: Goblin(2.10,7.31); Skeleton(15.19,22.65); Skeleton(14.58,23.60); Skeleton(15.98,23.72).
   Policy: ElectroSpirit slot 1 @ tile (8,20) [enemy, centre]. Search: ElectroSpirit slot 1 @ tile (7,20) [enemy, left].
   native scores: search 2.000000, policy 0.033228; regret +1.966772. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5-r2/rows/000419-00.json`.

3. **l16 / HPv2 / case 91 / tick 4460** (packet n=874, seat=1, seed=2680308772461625; search_win_policy_loss). Elixir 1.428; gate 0.03773; hand slots 0..3: Valkyrie, Zap, ElectroSpirit, Fireball.
   Ours: HogRider(1.50,14.50).
   Enemy: Archer(3.65,15.86); Bat(10.07,15.33); Bat(6.12,15.85); Bat(11.32,16.57); Bat(5.57,16.65); Bat(7.21,17.12); MiniPekka(4.19,14.80).
   Policy: ElectroSpirit slot 2 @ tile (4,14) [own, left]. Search: ElectroSpirit slot 2 @ tile (6,13) [own, left].
   native scores: search 2.000000, policy 0.043251; regret +1.956749. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s1/rows/000391-00.json`.

4. **l16 / K4CW / case 20 / tick 3450** (packet n=672, seat=0, seed=2680308772461252; search_win_policy_loss). Elixir 2.357; gate 0.02011; hand slots 0..3: Valkyrie, Fireball, Cannon, ElectroSpirit.
   Ours: HogRider(4.93,17.07); Skeleton(6.80,10.10); Skeleton(8.20,10.10); Skeleton(7.50,11.31); Valkyrie(13.79,21.22).
   Enemy: BabyDragon(14.50,18.50); Witch(3.75,16.00).
   Policy: ElectroSpirit slot 3 @ tile (3,14) [own, left]. Search: ElectroSpirit slot 3 @ tile (15,1) [own, right].
   native scores: search 2.000000, policy 0.054760; regret +1.945240. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s2/rows/000020-00.json`.

5. **l16 / HPv2 / case 30 / tick 3780** (packet n=738, seat=0, seed=2680308772461564; search_win_policy_loss). Elixir 2.142; gate 0.02301; hand slots 0..3: Fireball, Archers, Cannon, ElectroSpirit.
   Ours: HogRider(15.61,14.68); Valkyrie(3.04,15.84); Cannon(10.50,9.50).
   Enemy: Skeleton(16.64,15.16); SkeletonDragon(0.25,17.50); SkeletonDragon(3.00,17.50); SkeletonWarrior(4.52,17.76); SkeletonWarrior(2.32,17.86).
   Policy: ElectroSpirit slot 3 @ tile (14,14) [own, right]. Search: ElectroSpirit slot 3 @ tile (15,8) [own, right].
   native scores: search 2.000000, policy 0.062929; regret +1.937071. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s0/rows/000330-00.json`.

### tile:Cannon

Count 1650; scored 996; signed regret share 2.7%; positive-only share 2.7%.

1. **acc / K4CW / case 131 / tick 5580** (packet n=1098, seat=1, seed=2680308772461363; search_win_policy_loss). Elixir 3.496; gate 0.04723; hand slots 0..3: Valkyrie, Cannon, HogRider, Fireball.
   Ours: Archer(13.76,15.56); Archer(15.28,15.73).
   Enemy: Knight(10.63,12.83); Musketeer(4.38,27.74); Skeleton(13.60,14.07); Skeleton(15.95,14.39); Skeleton(12.89,14.78); Skeleton(3.33,14.98); Skeleton(4.17,15.35); Skeleton(3.39,15.97); Skeleton(2.52,16.22); Skeleton(4.21,16.30); Skeleton(5.05,16.86); Skeleton(3.62,17.07); Skeleton(2.68,17.22); Skeleton(4.39,17.50); Skeleton(3.30,17.99); Skeleton(4.13,18.35); Skeleton(2.67,18.84); Skeleton(4.66,19.17); Skeleton(3.55,19.31); Skeleton(4.24,20.02); SkeletonWarrior(3.65,13.42); SkeletonWarrior(2.89,14.13); SkeletonWarrior(4.05,14.32); Witch(14.73,14.00).
   Policy: Cannon slot 1 @ tile (8,9) [own, centre]. Search: Cannon slot 1 @ tile (10,9) [own, right].
   native scores: search -0.189256, policy -2.000000; regret +1.810744. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/acc-s5/rows/000131-00.json`.

2. **l16 / K4CW / case 96 / tick 3180** (packet n=618, seat=0, seed=2680308772461328; search_win_policy_loss). Elixir 3.714; gate 0.17310; hand slots 0..3: Zap, HogRider, Valkyrie, Cannon.
   Ours: Archer(4.77,8.92); Archer(6.02,9.72); Skeleton(13.81,19.34); Skeleton(13.89,20.35); Skeleton(13.96,21.37).
   Enemy: HogRider(3.17,14.87); Valkyrie(2.92,11.86).
   Policy: Cannon slot 3 @ tile (8,13) [own, centre]. Search: Cannon slot 3 @ tile (7,13) [own, left].
   native scores: search 0.152043, policy -0.061063; regret +0.213106. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s0/rows/000096-00.json`.

3. **l16 / R3a / case 89 / tick 3390** (packet n=660, seat=1, seed=2680308772461472; search_win_policy_loss). Elixir 3.214; gate 0.14546; hand slots 0..3: Valkyrie, Cannon, HogRider, Fireball.
   Ours: Archer(5.00,11.50); Archer(3.94,11.79); Skeleton(2.32,7.84).
   Enemy: HogRider(14.74,14.20).
   Policy: Cannon slot 1 @ tile (9,10) [own, centre]. Search: Cannon slot 1 @ tile (11,13) [own, right].
   native scores: search 0.165843, policy -0.033770; regret +0.199613. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s5/rows/000239-00.json`.

4. **l16 / K4CW / case 58 / tick 3350** (packet n=652, seat=0, seed=2680308772461290; search_win_policy_loss). Elixir 5.785; gate 0.08774; hand slots 0..3: Cannon, Zap, Fireball, Valkyrie.
   Ours: none.
   Enemy: Barbarian(14.27,10.67); MiniPekka(14.74,13.52); Musketeer(3.50,17.50).
   Policy: Cannon slot 0 @ tile (9,10) [own, centre]. Search: Cannon slot 0 @ tile (10,10) [own, right].
   native scores: search 0.094942, policy -0.103807; regret +0.198749. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x08/dx1/l16-s4/rows/000058-00.json`.

5. **l16 / HPv2 / case 31 / tick 2190** (packet n=420, seat=1, seed=2680308772461565; search_win_policy_loss). Elixir 3.107; gate 0.06449; hand slots 0..3: Fireball, Cannon, Valkyrie, HogRider.
   Ours: none.
   Enemy: Skeleton(14.09,8.71); Skeleton(15.32,9.19); Skeleton(13.69,9.49); Skeleton(14.61,9.66); Skeleton(15.21,10.35); Skeleton(14.01,10.36); Skeleton(15.23,11.34); Skeleton(14.21,11.43); Skeleton(14.78,12.23); Skeleton(13.84,12.34); Skeleton(15.08,13.15); Skeleton(14.12,13.27); Skeleton(15.04,14.24); Skeleton(14.08,14.35).
   Policy: Cannon slot 1 @ tile (9,10) [own, centre]. Search: Cannon slot 1 @ tile (11,10) [own, right].
   native scores: search -0.122311, policy -0.298312; regret +0.176001. Source `search`; row `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/raw/127x04/dx1/l16-s1/rows/000331-00.json`.

## Limits and follow-up design

The regret proxy is the search’s own approximately 8 s lookahead model, not a true counterfactual win probability or measured causal advantage. It contains model error, hidden-state belief sampling, candidate restrictions, score bonuses, and a finite horizon. Search trajectories are off-policy for pv2; the policy-only games diverge after initial actions, so a shadow disagreement cannot be assigned the paired game outcome as its causal effect. Decision counts overrepresent long games and repeated states; no independent-decision significance claim is made. Native/refined mixing, negative native regrets, wait-duration normalization and unscored actions are explicitly audited above.

DX1 is 150 pre-registered cases per opponent per level row, one deck and a 53-row pool. It covers the supplied simulator/levels, not live perception, real deployment latency or all deck metas. Timing includes instrumented runs: shadow inference is outside the play lateness timer, but its resource cost can still affect host throughput. Metrics are observational RF1 proxies with the documented missing IDs/impacts. The supplied two-case shadow smoke established identical command hashes in those cases only.

Use disjoint training seeds and a separate held-out pool to test the proposed policy changes, retaining the live search bot as a fixed benchmark. Compare the final policy-only bot against live search at both level rows, with paired outcomes and these play-quality diagnostics. If DX1 snapshots enter training, retire this bank from held-out evaluation. No model was trained, no bot code changed, no jobs outside DX1 touched, and no commit or sealing action was made.

## Machine-readable artifacts and provenance

- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/audit.json`: full row/bank audit and source paths.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/outcomes.json`: paired scores, CIs and clustered sensitivity.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/paired-cases.csv`: one record per paired case.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/games.csv`: per-arm outcomes.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/metrics.json`: all RF1 metrics, counts and denominators.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/metrics.csv`: flat metric rows with nested spell fields.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/shadow-tables.json`: all context/type/geometry intersections and scorer regimes.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/shadow-tables.csv`: same tables in CSV.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/decisions.jsonl`: every searched shadow decision with decoded actions and matched-scale scores.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/examples.json`: five highest-margin distinct cases per detailed type.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/flip-examples.json`: five examples per type from search-win/policy-loss pairs.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/exit-target-candidates.csv`: positive refined disagreements, action/gate labels, source packet and paired outcome.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/gate-card-targets.json`: play/hold disagreement counts and regret by card and phase.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/action-disagreement-types.json`: type ranking and normalized regret after removing same-WAIT duration comparisons.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/governor-history.jsonl`: resource priority checks and yield/relaunch events.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/watch-history.jsonl`: 10-minute receipt/job status history.
- `/mpac/sdicks02/jobs/clasher/bot-pq/dx1-analysis/source-provenance.json`: same-step source revision and hashes.

Source SHA256s read on 2026-10-18T10:30:53.476182+00:00:

```text
4bb4a2913f43e088134313d9254774e6a0117b029620f80ae2c6758bbe0637c5  STAGED-REV
23c44946873d025d1c7f824c0247f85b30ce3bb13335d6e6202748b54745cdf4  bot/pq/shadow.py
5be495ed4d8418aaee3c64fbb2cdb84cb08b64c07b0e234f608b813e8e04cfa8  bot/search/lopp_fast.py
8e54abe94dd58e3c7241037cf81fa8b024b664550bf8e5602cd6bfaaa99c57aa  bot/search/oppmodel.py
02252a3d84a4754b9e39aeac45db83b92152a2efdffafea8032d03fe28d83db4  bot/live/player.py
ef68c4c9c13c8770f983c3b011e6ab364d58b2b181f390c053a85a51fdb236d6  bot/search/interrupt.py
93a975e1fdd5092f1ed8c94489710ec9209ec504ff9ac184b641be47c26ad8f8  bot/players/search.py
595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7  bot/fullpool/hz_report.py
597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95  bot/fullpool/scale_report.py
bb2067f2e827e4dff774718939dfebbe7a0867758f38e1a4fd715f11d3c4d34f  bot/livediag/l16_report.py
631dd56ae639a026b4e7e0d0049427595db04eb6de6f620b7111b889b0e840e5  bot/livediag/live_metrics.py
```

Analysis SHA256s computed during this render:

```text
c3432ac62a433cb2c3950a82340707ae950ee835d1de35c603f75d4b9cdcf688  analyze.py
8f16309871f2a5eaea061a88ae895ec527d4b52b6da03f7788ac70ae342c7a94  render.py
f233dc03c86beee94147127045e965764f3cd1cd52d848274e6d1c46aff583d8  score_study.py
```
