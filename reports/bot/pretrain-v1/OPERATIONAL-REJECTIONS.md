# Operational rejection accounting

Sam's 2026-10-22 amendment preserves the public mask and calibrated engine. A rejected executed tap remains
its original PPO action and poll transition. It spends no elixir, consumes no card, and receives no extra reward
penalty. Other execution and contract failures still fail closed. The superseded zero-rejection fixture gate
must be replaced and independently reviewed before relaunch.

## BC reference available before the revised fixture

The exact selected next-S100 checkpoint is
`74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f`.
The frozen next bank is
`10c24cd429416344d6ee69342bc6317a2c90387bb73a97eb38c9dbf4cf30a276`.
All 1,600 assigned rows are sealed. There are 1,591 games with execution telemetry and nine other execution
failures without recoverable command telemetry. Those nine cases remain failures in all-assigned game accounting;
they do not contribute invented zero commands or rejections.

| Card | Executed taps | Rejected taps | Rejection rate |
|---|---:|---:|---:|
| Cannon | 4,663 | 21 | 0.450354% |
| Fireball | 2,331 | 0 | 0% |
| HogRider | 7,609 | 0 | 0% |
| IceGolem | 8,509 | 0 | 0% |
| IceSpirit | 9,130 | 0 | 0% |
| Musketeer | 6,881 | 0 | 0% |
| Skeletons | 8,708 | 1 | 0.011484% |
| Zap | 5,263 | 0 | 0% |
| Total | 53,094 | 22 | 0.041436% |

Submitted taps total 53,422; accepted executed taps total 53,072; unexecuted terminal pending taps total 328.
The pending taps are excluded from the executed-rejection denominator. The nine other failures are frozen
R3a opponent errors, separately retained in the source rows. The M bank is now complete with the same nine failed case indices. Its selected checkpoint is
`947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4`. M has 60,490 submitted,
60,104 executed, 60,085 accepted, 19 rejected and 386 terminal pending taps. Its executed-rejection rate is
0.031612%. All 19 rejected taps are Cannon, 19 / 6,146 Cannon executions, 0.309144%. The other seven cards
have zero rejected taps. Their executed counts are Fireball 3,588, HogRider 6,568, IceGolem 9,732,
IceSpirit 10,294, Musketeer 7,023, Skeletons 9,882 and Zap 6,871.

These counts were independently reconciled against every stored per-card execution log and channel counter.
Evidence, including all 1,600 row-file SHA256s, is
`/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/rejection-amendment-20261022/independent-S100-BC-counts.json`.
R38 gives exact-source GO for the reporting module at `8fe59e7d2246baefb908d793122086f790e9cc33`.
The parent and reviewer independently cross-checked the full S100 row hashes/counts. Both complete sidecars
retain nine other failures and no contract failures. They are baseline evidence, not passing game verdicts.
This bank is BC game-evaluation exposure, not the fixture's one-opponent readiness exposure or registered RL.

## Retained rejected transition

The failed first fixture's Cannon tap was submitted at tick 5265, executed at 5292, and rejected by the
unchanged overlapping-building rule. Its original queue receipt retains action 1933, old log probability
-5.7638250995640075, actor=true, reward=0, terminated=false, under version 2. Separate native checks confirm
unchanged hand/elixir, game_over=false, and a released command reservation. The original failed run is immutable.

## Alerts and follow-up

Per-snapshot overall and per-card rates strictly above twice the same size's frozen BC-start rate trigger an
alert only. Exact counts govern the comparison, with no pseudocounts. Missing or zero-exposure references are
unavailable; a measured BC zero rate alerts on any positive current rate. Evaluation references must bind the
checkpoint, case bank and exposure. Training and readiness exposures are labelled separately.

An occupancy-aware public placement mask is a possible later improvement. It is outside this launch.


## Reporting commands and limits

`bot.pretrain_v1.report_operational_rejections` reads sealed `eval_rsim` rows without importing a simulator
or changing the frozen evaluator. Pass the exact eval manifest, bank and anchor SHA256s, its original
candidate package directory as `--candidate-root`, explicit size/version/scope, and an output path outside
the frozen eval directory. `--bc-start --version 0` marks the exact BC checkpoint. Optional `--baseline`
and `--baseline-sha256` compare a frozen report on matched exposure. A report with retained execution
failures exits nonzero and still writes its full assigned/failure accounting. It is not a game verdict.

Frozen rows do not always retain the card identity of terminal pending taps. Those per-card submitted/pending
counts remain unavailable. Overall submitted/pending and per-card executed/accepted/rejected counts are exact.
The offline fixture reports per-version outcomes using the sampled command's version, never finish-time weights.
