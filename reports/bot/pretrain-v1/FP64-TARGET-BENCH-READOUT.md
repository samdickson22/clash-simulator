# FP64 Mac latency measurement

The selected v3 checkpoints each completed 20,000 exact Session decisions on CPU1
and CPU4, after 200 warmups per phase. S100 passes the timing budget. M fails at
both thread settings. Every phase observed active Canvasdoc and is shared-load
evidence; an idle rerun remains pending. Replay emulators and all other Mac
workloads were left untouched. No serving precision or model choice was adopted.

| Size | CPU threads | Decisions | p95 ms | p99 ms | Budget | Canvasdoc peak CPU % | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---:|---:|
| M | 1 | 20000 | 45.302 | 59.454 | fail | 113.2 | 1213792 |
| M | 4 | 20000 | 40.351 | 59.143 | fail | 20.4 | 1161472 |
| S100 | 1 | 20000 | 18.207 | 27.593 | pass | 18.2 | 795536 |
| S100 | 4 | 20000 | 23.744 | 47.565 | pass | 59.9 | 878224 |

The unchanged benchmark limits are p95 <=30 ms and p99 <=50 ms. Complete raw
telemetry is retained. Prelaunch Canvasdoc was idle, but activity during every
phase prevents an idle/clean claim. RSS covers the attributed VM host process,
Colima services and descendants; CPU uses ps percent, 100% per logical core.
FP64 MPS is unsupported. Its receipts explicitly say unmeasured and contain no
latency or decision-count claim. Previous FP32 Mac results remain separate.

Reviewed source is `48795b3c7e343ca038d23abea9f6c69eea219d60`, package SHA256
`6d8b3ca1d41089362f1a64760dc065912d416a27858c724133abb8625ff83291`.
The frozen 36-file real-record corpus has canonical SHA256
`0c1b52af43c431e18d30416fcf6bd988c57e97351c11838fc1bfbd36ee65c028`.
Checkpoint files are the previously selected v3 S100/M anchors, with exact SHA
values in each result and [FP64-OFFLINE-RESULTS.json](FP64-OFFLINE-RESULTS.json).
These timings do not qualify the newer 41,328-match starts or full PPO.

Owner PID 9723 completed and exited. Mac files remain solely beneath
`~/clasher-pretrain-bench/offline-fp64-48795b3c7/`.
Complete receipts were copied to 05 under
`/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/fp64-mac-complete/`.
Transfer archive SHA256:
`91ff5393b2113eb7448fcaa99c55a0dfbd3644e8d900e7c5b6e2be83da21409f`.
