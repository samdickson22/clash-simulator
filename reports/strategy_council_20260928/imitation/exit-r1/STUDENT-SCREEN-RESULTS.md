# Frozen ExIt round-1 student screen results

All three arms are killed by the frozen rules. S-teacher improves paired loss by7.5pp (95% CI−12.67 to−2.17), but its teacher play recall40.34% is below50%. S-mix and S-human also fail paired-CI and recall rules; S-human additionally exceeds the WAIT threshold. No arm proceeds to live replacement or round2.

Exploration lane; no multiplicity adjustment. All intervals are percentile 95% bootstrap intervals from 5,000 resamples with seed 80991010. Complete game seeds are the resampling unit; metric(b) resamples student/reference pairs jointly.

Each arm used the released v1 main-2026100802 step22552 EMA, width192, 4,883 steps ×8,192 =40,001,536 rows, fixed T11 optimizer/schedule, final EMA only. Teacher fractions were 0.5/1.0/0.0, temperature0.1, rare-play weight4 and value loss0. No reporting seed was used for tuning or checkpoint selection.

S-human uses the coordinator-authorized operational micro3584 amendment from checkpoint200. Effective batch8192, sampled rows/order and global loss denominators are unchanged. Gradient accumulation changes floating-point summation order; this continuation is not claimed bit-identical to micro7168. Its exact checkpoint recipe fingerprint remains7168; runtime/segment evidence records the actual3584.

A coordinator-authorized staged reporting amendment began the common600 init-W reference cases and64 held-out teacher games on03 while fitting continued. S-human cases began on03;38 unclaimed fallback identities moved to04/08. S-teacher ran on04/08; S-mix was distributed across01/03/04/08 as its final EMA sealed. The frozen seed/deck/seat schedule and per-seed shared reference are unchanged. The03 manager paused new claims while its56 existing children completed untouched; phase costs include parent/reaped/unreaped child CPU with recorded tick precision. After the complete-case gate, independent arm diagnostics run in parallel on home03 cores58/59/60 at nice19/SCHED_IDLE, scientific Torchthreads1, with unchanged per-arm calculations and bootstrap settings. No agreement metrics, CIs or kill decisions were computed before all final fits and all3232 reporting tasks completed. Immutable raw stage receipts retain their original input-freeze SHA; the final reducer view validates each stage input and checkpoint as a matching subset of the common final freeze and changes only the provenance envelope, retaining original stage and raw-case SHAs.

Reporting uses the qualified E1 native f387b2d2..., as required by the frozen plan. The first startup used the generation native and failed before creating any games; its 1289.014866 CPU-seconds are included in reporting costs. A later stale internal01 stop blocked the first mix pool; all interrupted phase costs and completed human receipts were retained, and the exact unfinished mix identities resumed in a new phase under the same freezes. Corpus and fit pins remain unchanged. The dated reporting native amendment preceded all affected outcomes.

## Arm decisions and metrics(a)/(b)

Exploration lane; no multiplicity adjustment.

| Arm | (a) loss %, 95% CI | (a) win %, 95% CI | (a) draw %, 95% CI | (b) loss change pp, paired 95% CI | Decision | Kill rules fired |
| --- | --- | --- | --- | --- | --- | --- |
| S-mix | 69.531250 [63.671875, 75.009766] | 30.468750 [24.990234, 36.328125] | 0.000000 [0.000000, 0.000000] | -1.833333 [-7.000000, 3.333333] | KILLED | teacher play recall below 50%; paired loss-change CI upper bound is nonnegative |
| S-teacher | 69.140625 [63.671875, 74.609375] | 30.859375 [25.390625, 36.328125] | 0.000000 [0.000000, 0.000000] | -7.500000 [-12.666667, -2.166667] | KILLED | teacher play recall below 50% |
| S-human | 45.703125 [39.843750, 51.953125] | 54.296875 [48.046875, 60.156250] | 0.000000 [0.000000, 0.000000] | -2.333333 [-7.166667, 2.500000] | KILLED | teacher play recall below 50%; WAIT rate exceeds 1.5 times teacher; paired loss-change CI upper bound is nonnegative |

All three arms completed 256/256 terminal head-to-head games and 600/600 terminal fallback/proposer games. The common init-W reference completed 600/600. Each arm has the same 64 terminal held-out teacher games. No arm was omitted because a kill rule fired.

## Fit throughput and resources

Exploration lane; no multiplicity adjustment.

| Arm / host(s) | Rows/s, full fit wall | GPU-hours, full fit wall | Optimizer GPU-hours | Fit CPU-hours | Peak PSS GiB | Minimum GPU free GiB | Minimum MemAvailable GiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-mix / 127x01 | 3146.10 | 3.531846 | 2.999443 | 19.067445 | 35.732 | 3.044 | 95.520 |
| S-teacher / 127x04 | 4003.14 | 2.775705 | 2.541383 | 6.567472 | 32.523 | 45.083 | 103.896 |
| S-human / 127x09 → 127x08 | 5285.30 | 2.102349 | 1.489534 | 9.590224 | 49.513 | 10.118 | 102.095 |

The coordinator-directed loader6 operational amendment preserved all scientific rows, mixing order, seeds, cursor, losses and optimizer state. All three arms passed serial/parallel two-step train-only GPU replay with the model, EMA, optimizer, scheduler and all RNG states bit for bit equal before resuming. Complete human and teacher index vectors are rechecked at every prefetched production step. Actual workers6, scientific loader1, prefetch4, no random mmap advice; leased aggregate PSS guard46GB and home MemAvailable floor24GiB. Parent cores118/119/126, loader cores120–125; Torch scientific threads1. Periodic checkpoints200–250 steps, with final-step EMA selection unchanged.

Exploration lane; no multiplicity adjustment.

| Arm | Before rows/s, >5min | Before s/step | After rows/s, >5min | After s/step | Remaining fit ETA hours at measurement |
| --- | --- | --- | --- | --- | --- |
| S-mix | 859.62 | 9.529776 | 3656.07 | 2.240658 | 2.434 |
| S-teacher | 2148.47 | 3.812944 | 4234.37 | 1.934644 | 1.897 |
| S-human | 1272.17 | 6.439390 | 4655.37 | 1.759688 | 2.168 |

GPU-hours use elapsed wall time while each GPU was allocated, including store preparation and batch gathering across all exact-state fit segments. Optimizer time is synchronized step wall time and is shown separately. Initial fits ran simultaneously on01/04/09, nice10, one GPU per arm. 09 used the versioned capture-extension supervisor with a live Oct11 lease, four declared processes and46GB PSS cap. S-human continued on owned08 from checkpoint108 after an attempted-step239 CUDA OOM on09;130 completed unsaved updates were archived and replayed. Owned08 reproduced the same OOM; checkpoint200 preserved92 useful updates, and38 additional unsaved updates were archived and replayed. Expandable allocation was then enabled for S-human after a dated operational amendment and a bit-exact two-step default/expandable replay from200. It failed at the same dense step239 allocation with a CUDA driver invalid-argument error; another38 updates were archived and replayed. S-human then resumed200 with default allocation and the separately dated micro3584 runtime amendment. An inherited46GB aggregate PSS guard then clean-saved232 on owned08 while MemAvailable remained115.7GB. A dated amendment scoped that PSS cap to leased hosts and retained the24GiB home memory floor; exact232 resumed without lost updates. Their GPU/CPU cost is included in the segment totals. S-mix completed step239 but stopped because the wrapper incorrectly applied the leased8GiB reserve to owned01; it resumed exactly after that guard scope was corrected. Owned GPUs have no leased8GiB reserve floor. No CPU simulation ran on leased hosts.08 joined reporting at nice19/SCHED_IDLE with48 physical workers, cores0/1 reserved and the existing cache service untouched.08 had an owned stop file and a five-minute reclaim bound.

Exploration lane; no multiplicity adjustment.

| Arm | Loader qualification GPU-hours | Qualification CPU-hours | Whole fitting window GPU-hours (includes restart gaps) |
| --- | --- | --- | --- |
| S-mix | 0.072045 | 0.064440 | 3.760968 |
| S-teacher | 0.063489 | 0.066758 | 2.934887 |
| S-human | 0.024753 | 0.029192 | 2.646376 |

Separate allocator qualification: 0.031447 GPU-hours and 0.050649 CPU-hours.

Exploration lane; no multiplicity adjustment.

| Home host | Physical worker cores | Peak owned processes | Pool wall-hours | Worker CPU-hours | Manager CPU-hours | Minimum MemAvailable GiB |
| --- | --- | --- | --- | --- | --- | --- |
| 03 | 56 | 57 | 1.196711 | 46.944613 | 0.001986 | 87.084 |
| 04 | 60 | 61 | 0.661122 | 17.574143 | 0.000978 | 91.763 |
| 01 | 44 | 45 | 0.148877 | 5.434068 | 0.000330 | 100.825 |
| 08 | 48 | 49 | 0.665367 | 15.641236 | 0.001070 | 94.906 |

Total home reporting pool CPU-hours: 85.956485, including held-out teacher generation (0.902288 game CPU-hours). These process-accounting totals include interpreter startup and SHA checks; game-only times below exclude startup. Separate freeze/held-out packing/agreement/reduction CPU-hours: 0.771957. Total metered fitting, qualifications, reporting and scientific postprocessing:8.601633 GPU-hours and122.164622 CPU-hours. These include all failed/recovered fit and reporting phases,206 discarded S-human updates, loader replay qualifications and allocator qualification. Data staging, training-corpus preparation and final report emission are outside these screen compute totals.

## Metric(c): teacher agreement

Rates below are probability-based at T=1. Top8 agreement is recall among teacher-chosen plays. Teacher self-recall is1.0. Pending-command WAIT rows are unsupervised; expanded timed WAITs remain supervised.

### Scored teacher roots

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | S-mix | S-teacher | S-human |
| --- | --- | --- | --- |
| teacher_play_rate | 0.345945 [0.331782, 0.358931] | 0.345945 [0.331782, 0.358931] | 0.345945 [0.331782, 0.358931] |
| teacher_wait_rate | 0.654055 [0.641069, 0.668218] | 0.654055 [0.641069, 0.668218] | 0.654055 [0.641069, 0.668218] |
| student_play_rate | 0.279222 [0.260154, 0.297177] | 0.283527 [0.265597, 0.300288] | 0.018271 [0.016077, 0.020362] |
| student_wait_rate | 0.720778 [0.702823, 0.739846] | 0.716473 [0.699712, 0.734403] | 0.981729 [0.979638, 0.983923] |
| play_recall | 0.390209 [0.377850, 0.401102] | 0.403391 [0.393335, 0.412336] | 0.027553 [0.024602, 0.030222] |
| play_prevalence_ratio | 0.807129 [0.774478, 0.836618] | 0.819574 [0.789152, 0.846724] | 0.052816 [0.047692, 0.057565] |
| top8_action_recall | 0.271623 [0.255510, 0.288615] | 0.298070 [0.280746, 0.316274] | 0.078270 [0.066947, 0.089679] |
| hard_action_agreement | 0.553289 [0.527582, 0.580199] | 0.555391 [0.530214, 0.582130] | 0.654055 [0.641069, 0.668218] |

64 whole teacher games; 8,088 eligible rows.

### All eligible poll rows

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | S-mix | S-teacher | S-human |
| --- | --- | --- | --- |
| teacher_play_rate | 0.073729 [0.069500, 0.077743] | 0.073729 [0.069500, 0.077743] | 0.073729 [0.069500, 0.077743] |
| teacher_wait_rate | 0.926271 [0.922257, 0.930500] | 0.926271 [0.922257, 0.930500] | 0.926271 [0.922257, 0.930500] |
| student_play_rate | 0.174403 [0.164148, 0.184266] | 0.168113 [0.158348, 0.177323] | 0.016522 [0.014422, 0.018559] |
| student_wait_rate | 0.825597 [0.815734, 0.835852] | 0.831887 [0.822677, 0.841652] | 0.983478 [0.981441, 0.985578] |
| play_recall | 0.390209 [0.377850, 0.401102] | 0.403391 [0.393335, 0.412336] | 0.027553 [0.024602, 0.030222] |
| play_prevalence_ratio | 2.365472 [2.290002, 2.441527] | 2.280162 [2.208423, 2.352617] | 0.224091 [0.203808, 0.243614] |
| top8_action_recall | 0.271623 [0.255510, 0.288615] | 0.298070 [0.280746, 0.316274] | 0.078270 [0.066947, 0.089679] |
| hard_action_agreement | 0.904242 [0.897135, 0.911459] | 0.904427 [0.897458, 0.911524] | 0.926271 [0.922257, 0.930500] |

64 whole teacher games; 37,950 eligible rows.

## Free-running and deadline diagnostics

Play/WAIT rates use sampled actions per poll; pending and timed WAITs are shown separately. Deadline counters use search decisions as denominator. Completed roots exclude late/partial roots. Latency quantiles are descriptive decision quantiles; mean latency CIs resample whole games.

### h2h / S-mix

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.695312 [0.636719, 0.750098] | 0.304688 [0.249902, 0.363281] |
| win | 0.304688 [0.249902, 0.363281] | 0.695312 [0.636719, 0.750098] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.059882 [0.058577, 0.061200] | 0.042858 [0.041733, 0.043957] |
| WAIT_rate | 0.940118 [0.938800, 0.941423] | 0.957142 [0.956043, 0.958267] |
| submitted_play_rate | 0.058373 [0.057203, 0.059556] | 0.038383 [0.037562, 0.039171] |
| pending_poll_rate | 0.290628 [0.284779, 0.296552] | 0.190956 [0.186871, 0.194889] |
| timed_wait_poll_rate | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |

Terminal 256/256; game CPU-hours 2.163615; summed game wall-hours 2.206251; ordered command hashes SHA256 `66bd252bd01092041bba3eece06b6d0f18db5f3ffcb636784299cfe320a29789`.

### h2h / S-teacher

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.691406 [0.636719, 0.746094] | 0.308594 [0.253906, 0.363281] |
| win | 0.308594 [0.253906, 0.363281] | 0.691406 [0.636719, 0.746094] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.060424 [0.058986, 0.061852] | 0.042482 [0.041445, 0.043534] |
| WAIT_rate | 0.939576 [0.938148, 0.941014] | 0.957518 [0.956466, 0.958555] |
| submitted_play_rate | 0.059143 [0.057812, 0.060453] | 0.038226 [0.037455, 0.039005] |
| pending_poll_rate | 0.293924 [0.287330, 0.300496] | 0.190015 [0.186204, 0.193897] |
| timed_wait_poll_rate | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |

Terminal 256/256; game CPU-hours 2.111268; summed game wall-hours 2.156304; ordered command hashes SHA256 `79a1909323599a61d56295a02966a711bd56454791bc270f6acebfda866efcd7`.

### h2h / S-human

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.457031 [0.398438, 0.519531] | 0.542969 [0.480469, 0.601562] |
| win | 0.542969 [0.480469, 0.601562] | 0.457031 [0.398438, 0.519531] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.041960 [0.040848, 0.043069] | 0.040153 [0.039027, 0.041220] |
| WAIT_rate | 0.958040 [0.956931, 0.959152] | 0.959847 [0.958780, 0.960973] |
| submitted_play_rate | 0.036109 [0.035332, 0.036889] | 0.035752 [0.034890, 0.036569] |
| pending_poll_rate | 0.179760 [0.175878, 0.183619] | 0.178116 [0.173810, 0.182175] |
| timed_wait_poll_rate | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |

Terminal 256/256; game CPU-hours 2.005924; summed game wall-hours 2.009307; ordered command hashes SHA256 `083f7a62193720517e5dd9eb7b5154ee41a86498b066f229e64318de0c9e91b0`.

### fallback / init

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.500000 [0.460000, 0.540000] | 0.500000 [0.460000, 0.540000] |
| win | 0.500000 [0.460000, 0.540000] | 0.500000 [0.460000, 0.540000] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.020268 [0.019174, 0.021334] | 0.020591 [0.019460, 0.021714] |
| WAIT_rate | 0.979732 [0.978666, 0.980826] | 0.979409 [0.978286, 0.980540] |
| submitted_play_rate | 0.049169 [0.048396, 0.049963] | 0.049306 [0.048518, 0.050100] |
| pending_poll_rate | 0.243515 [0.239648, 0.247532] | 0.244253 [0.240257, 0.248264] |
| timed_wait_poll_rate | 0.332645 [0.322270, 0.343323] | 0.327604 [0.317655, 0.337999] |
| deadline_hit_rate | 0.774760 [0.762771, 0.786037] | 0.777768 [0.766438, 0.788643] |
| fallback_rate | 0.493043 [0.469291, 0.515359] | 0.494551 [0.471379, 0.516980] |
| wall_overrun_rate | 0.006101 [0.005863, 0.006354] | 0.005689 [0.005460, 0.005932] |
| completed_roots_per_decision | 2.951940 [2.809845, 3.102372] | 2.964672 [2.820136, 3.117507] |
| mean_proposer_seconds | 0.008226 [0.008146, 0.008301] | 0.008262 [0.008185, 0.008332] |

Terminal 600/600; game CPU-hours 15.417484; summed game wall-hours 15.443486; ordered command hashes SHA256 `bf6cd456bdaadb5927206e960bc36e2eea09e08ecfe1c3f49a202be1319afbf0`.

Exploration lane; no multiplicity adjustment.

| Latency seconds, p50 / p95 / p99 | Student / reference seat | Opponent seat |
| --- | --- | --- |
| proposer_seconds_p50_p95_p99 | 0.009617 / 0.010538 / 0.011172 | 0.009618 / 0.010526 / 0.011134 |
| decision_wall_seconds_p50_p95_p99 | 0.192052 / 0.192188 / 0.193636 | 0.192052 / 0.192188 / 0.193655 |

### fallback / S-mix

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.481667 [0.441667, 0.521667] | 0.518333 [0.478333, 0.558333] |
| win | 0.518333 [0.478333, 0.558333] | 0.481667 [0.441667, 0.521667] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.098596 [0.096891, 0.100272] | 0.020884 [0.019772, 0.021993] |
| WAIT_rate | 0.901404 [0.899728, 0.903109] | 0.979116 [0.978007, 0.980228] |
| submitted_play_rate | 0.058608 [0.057766, 0.059452] | 0.051842 [0.050969, 0.052669] |
| pending_poll_rate | 0.291314 [0.287088, 0.295531] | 0.257022 [0.252632, 0.261162] |
| timed_wait_poll_rate | 0.445723 [0.439201, 0.452257] | 0.341787 [0.332366, 0.351659] |
| deadline_hit_rate | 0.577866 [0.567257, 0.587901] | 0.756218 [0.743931, 0.767682] |
| fallback_rate | 0.176682 [0.164233, 0.189164] | 0.459468 [0.436654, 0.481797] |
| wall_overrun_rate | 0.006675 [0.006452, 0.006910] | 0.006089 [0.005852, 0.006318] |
| completed_roots_per_decision | 5.032358 [4.908574, 5.155426] | 3.228103 [3.075539, 3.385452] |
| mean_proposer_seconds | 0.006842 [0.006754, 0.006928] | 0.008133 [0.008040, 0.008223] |

Terminal 600/600; game CPU-hours 13.646940; summed game wall-hours 13.663409; ordered command hashes SHA256 `5d17df632fc2e028f078d4d593a1c8231e00ee4d333500284a993394e27a5e34`.

Exploration lane; no multiplicity adjustment.

| Latency seconds, p50 / p95 / p99 | Student / reference seat | Opponent seat |
| --- | --- | --- |
| proposer_seconds_p50_p95_p99 | 0.009224 / 0.010631 / 0.011278 | 0.009562 / 0.010789 / 0.011480 |
| decision_wall_seconds_p50_p95_p99 | 0.192045 / 0.192141 / 0.193022 | 0.192051 / 0.192168 / 0.193433 |

### fallback / S-teacher

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.425000 [0.385000, 0.463333] | 0.575000 [0.536667, 0.615000] |
| win | 0.575000 [0.536667, 0.615000] | 0.425000 [0.385000, 0.463333] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.094950 [0.093448, 0.096405] | 0.022986 [0.021862, 0.024119] |
| WAIT_rate | 0.905050 [0.903595, 0.906552] | 0.977014 [0.975881, 0.978138] |
| submitted_play_rate | 0.058627 [0.057769, 0.059431] | 0.050956 [0.050096, 0.051808] |
| pending_poll_rate | 0.291338 [0.287070, 0.295342] | 0.252448 [0.248166, 0.256667] |
| timed_wait_poll_rate | 0.441412 [0.434656, 0.448187] | 0.322586 [0.313146, 0.332532] |
| deadline_hit_rate | 0.589242 [0.578873, 0.599615] | 0.780245 [0.769006, 0.790692] |
| fallback_rate | 0.193238 [0.179331, 0.207538] | 0.497459 [0.475602, 0.518723] |
| wall_overrun_rate | 0.010220 [0.006423, 0.017671] | 0.010029 [0.006196, 0.017596] |
| completed_roots_per_decision | 4.822375 [4.699340, 4.948682] | 2.957876 [2.819448, 3.104261] |
| mean_proposer_seconds | 0.007123 [0.006905, 0.007471] | 0.008632 [0.008376, 0.009043] |

Terminal 600/600; game CPU-hours 14.086804; summed game wall-hours 14.198249; ordered command hashes SHA256 `6b09097f31ee8fff58ebd21f37bb764b2c4e4790671e914508b6d5d447917a2f`.

Exploration lane; no multiplicity adjustment.

| Latency seconds, p50 / p95 / p99 | Student / reference seat | Opponent seat |
| --- | --- | --- |
| proposer_seconds_p50_p95_p99 | 0.009352 / 0.010906 / 0.011728 | 0.009732 / 0.011078 / 0.012008 |
| decision_wall_seconds_p50_p95_p99 | 0.192047 / 0.192151 / 0.202255 | 0.192053 / 0.192182 / 0.200183 |

### fallback / S-human

Exploration lane; no multiplicity adjustment.

| Metric (95% CI) | Student / reference seat | Opponent seat |
| --- | --- | --- |
| loss | 0.476667 [0.435000, 0.516667] | 0.523333 [0.483333, 0.565000] |
| win | 0.523333 [0.483333, 0.565000] | 0.476667 [0.435000, 0.516667] |
| draw | 0.000000 [0.000000, 0.000000] | 0.000000 [0.000000, 0.000000] |
| play_rate | 0.020208 [0.019077, 0.021354] | 0.019523 [0.018454, 0.020599] |
| WAIT_rate | 0.979792 [0.978646, 0.980923] | 0.980477 [0.979401, 0.981546] |
| submitted_play_rate | 0.050589 [0.049707, 0.051447] | 0.050564 [0.049701, 0.051429] |
| pending_poll_rate | 0.250616 [0.246198, 0.254941] | 0.250579 [0.246241, 0.254914] |
| timed_wait_poll_rate | 0.338147 [0.328075, 0.348633] | 0.334628 [0.324287, 0.345177] |
| deadline_hit_rate | 0.760010 [0.747192, 0.771884] | 0.764486 [0.751452, 0.776527] |
| fallback_rate | 0.472070 [0.449059, 0.495009] | 0.472863 [0.449031, 0.496101] |
| wall_overrun_rate | 0.005849 [0.005612, 0.006081] | 0.006047 [0.005806, 0.006290] |
| completed_roots_per_decision | 3.154427 [2.997654, 3.313900] | 3.147301 [2.992436, 3.311369] |
| mean_proposer_seconds | 0.008167 [0.008073, 0.008251] | 0.008191 [0.008104, 0.008275] |

Terminal 600/600; game CPU-hours 15.437507; summed game wall-hours 15.464953; ordered command hashes SHA256 `e20e9d958bab428d9e5021dc056d92ebafab76be36b131cdf7a5a59c01d30dba`.

Exploration lane; no multiplicity adjustment.

| Latency seconds, p50 / p95 / p99 | Student / reference seat | Opponent seat |
| --- | --- | --- |
| proposer_seconds_p50_p95_p99 | 0.009639 / 0.010629 / 0.011304 | 0.009632 / 0.010619 / 0.011268 |
| decision_wall_seconds_p50_p95_p99 | 0.192052 / 0.192183 / 0.193482 | 0.192052 / 0.192183 / 0.193593 |

## Immutable provenance and execution notes

The frozen 14:38:39Z completed-game prefixes contain49,577 terminal SHA-sealed games, 6,009,681 roots and38,738,534 rows. Forty games finished during stop drainage and were excluded to preserve the exact coordinator cutoff. All generators exited0 and vacated before packing. All71 packed files were checksum-verified on every fitting host before any optimizer step.

Exploration lane; no multiplicity adjustment.

| Artifact | SHA256 |
| --- | --- |
| Packed training corpus manifest | 1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b |
| Held-out teacher manifest | 0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f |
| Pre-fit pin receipt | 511140704d571c09dfc3feed220a2ca8284b8ccc4be09e7affbf294922ae7c26 |
| Loader6 operational amendment | 44fb0ac7096d789c974377d5e9d8818db4e60b1884ed32a83e31b1f698d1765f |
| Parent affinity operational amendment | 3a8518a53c5e5a291effc31520feaf99bbd6a6535be74c5bad7276f4e0aa1a8f |
| Owned GPU migration operational amendment | 23e63c3c70e9eaa7c5ded4c1f79300ee9eb515fbbf98721e3a46c45d6e752abf |
| Owned PSS guard scope operational amendment | 9c860c5528c8807cda8b92b20fd775d65d0766d2176a6a86f273a91dc8084610 |
| S-human allocator operational amendment | f3746d49a2ad5ecf559b6c5ca805dc8c2ef1110718203072d8a29547284afd49 |
| S-human micro3584 operational amendment | 7e218adbcf764cb0d49bf403934e794a7d8eb2809b63bc43e6fa1eefcd37b992 |
| Staged reporting operational amendment | 59620484401adb4e962119b9d54e22c85f20f8aa90a19dd46bdf57d25451148a |
| Reporting rebalance amendment | 415dcfa0b511f5b6776f42848792c1d2a3521ca93ada9c5257683ff924b2703e |
| Parallel postprocessing amendment | 2ef18e8a94bcf3af22a4cb5af29c8e548064796c4452fd5f314375f3c1e4a7b0 |
| S-mix per-mode dispatch amendment | 6b23200b347b90c3383f13ce7896487d27af5482175353fa82f2a37f1a68a2a6 |
| Immutable raw case SHA manifest | 322b559f9828599583ed5d0555d6ecbbad5cbce79ba5e790796191509502379c |
| S-human reporting stage freeze | 86c3a266bb196bdf04444c5ca7afaf851056be1d2aeea76114c56d00343145e7 |
| S-mix reporting stage freeze | 11b1c17215ed83f78402c33e3559901c6babe6462f45962f9914694f0449ab43 |
| S-teacher reporting stage freeze | 6ff839335cabdce6bdc677c990f8af4c4a1d06bc55fdfa5243cb5389dc386869 |
| init-reference reporting stage freeze | d3d9258a3b957285be68c0333fa6686f408a26d4608109cd666b5c8e58978c06 |
| Owned migration receipt | ef4e1aa3fafe6eabfbcbcf3fafd05ddb3bb7f0f16c16b5b91255636bfde786c0 |
| Final reporting execution freeze | ff4ae6ef20cda181f09ff3dcadaedb0a4435bf92c0ce388e3adc466c75f813fa |
| Aggregate metrics | 9a333c93eddb1a8f14d4738ee93ac0c46bc2772014c6b841a1129a6be3d6dcf9 |
| S-mix final step4883 EMA checkpoint | 78928c0ead5e11d458b37e2f57a56e3f9b234e6acb83a9984c3cc1e206c19a59 |
| S-teacher final step4883 EMA checkpoint | 29d17153570025b924707e50e2b35c43919b77b1b5429f5a93232044d3b53f5e |
| S-human final step4883 EMA checkpoint | bb257672d47465b20611c29f714cc4e077e5f1aeedc504fc6a8f7d1566fe4bf5 |
| STUDENT-SCREEN-PLAN.md | d98fdd74f2c59a23806aae1cfd85852016796d40f6d8d71e2ed6b3c9171b6138 |
| student-seed-audit.json | 3e2764ad69a2a1c05ddc93dc27770261856517e231341eb1881e1b0a7e5c0986 |
| clasher_core.abi3.so | f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8 |
| main02.pt | d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed |
| assets.npz | 3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737 |
| STUDENT-SCREEN-FREEZE-20261009.json | 787e4c6a0aac6f5c860520782e7479c75d8a2aaa22b957d11a13a5647ad462c4 |

Exploration lane; no multiplicity adjustment.

| Fit input | SHA256 |
| --- | --- |
| Human train manifest | 0546cfddcf79be12509953358fb499ac3be29493ba4a87893bfbfbbe0f179e68 |
| Human parent manifest | 7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f |
| Human dev manifest | 18a7d8e732080c3b6146b21a9d0f74683aba258b3e60f01d92037b9d7f0ccd4b |
| Public mask | 0287247280426d948865237ca9dedf98ed2de8db0e419e1a1952a6bf1209149a |
| Public assets | 3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737 |
| Common init checkpoint | d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed |

The pre-fit receipt also pins the human parent/dev manifests, publicmask, all training columns, the immutable runtime source files and init step/width. Qualified fitting runtime: NumPy2.3.5, Torch2.7.1+cu118. Frozen scientific code commits:39b6adf6 andf98d8926. Execution receipt commits: b6b39380, f48d865d, ee6baaad, 666dd205, b839f178 and620c79a2 (later completion commits are in repository history). Eight frozen tests passed, including real pack identity/tamper rejection and ratio0 equality to qualified T11.

Technical setup retries occurred before fitting: self-SSH replaced by local copy, B4 modules overlaid from the unchanged frozen source, task-local GPU site-packages exposed, destination verifier made Python3.8 compatible, and instrumentation moved after the fresh-output check. The old09 supervisor refused before admission; the coordinator directed use of the existing Oct11 capture-extension wrapper. No global wrapper was edited. No sampling, optimizer/schedule, reporting seed, scientific source code or kill rule changed. The disclosed micro3584 operational amendment changes floating-point accumulation order. V3 retains a historical base runtime hash; the micro amendment and continuation receipt pin the actual amended runtime adapter.

Seed audit limitation from the coordinator freeze:02/07/18 were not directly inventoried; committed formula ranges and archive/mirror supplements cover them as disclosed in the seed-audit receipt. A surviving exploration arm would still require registered confirmatory gates and the L2 amendment before live replacement or DAgger round2.

Complete machine-readable evidence: `receipts/student-screen-complete.json`; pre-fit and launch evidence: `receipts/student-screen-pre-fit.json` and `receipts/student-fit-launch.json`. Raw corpora, checkpoints and games remain under the host-local task directory and are not committed.

Independent completion verification: `receipts/student-final-metadata-verification.json` checks all3168 raw cases, all2312 pre-mix byte pins, all4608 held-out sealed files and all3232 distinct tasks. `receipts/student-final-result-verification.json` independently replays the frozen paired bootstrap exactly, validates every kill decision and checks each final4883 checkpoint SHA. Completion receipt SHA256: `87e97cd927c4a0484946bc061197377def83a66135de0dbc23fab3489a96be62`. Final implementation and measurement commits include95d7c353,6f0418b2,8a506642 and80b63dfb; this report and its receipts are committed separately.
