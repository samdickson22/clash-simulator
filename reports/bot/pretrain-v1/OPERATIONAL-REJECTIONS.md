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
R3a opponent errors, separately retained in the source rows. The M bank remains in progress and its final
reference is unavailable until all assigned attempts are sealed.

These counts were independently reconciled against every stored per-card execution log and channel counter.
Evidence, including all 1,600 row-file SHA256s, is
`/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/rejection-amendment-20261022/independent-S100-BC-counts.json`.
The revised reporting module still requires source review and a cross-check against these independent counts.
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
