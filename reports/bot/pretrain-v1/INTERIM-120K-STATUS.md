# Interim 120k M training status

All three seeds are running to completion under Sam's latest authorization. M is primary and S100 secondary.
No deployment. Checkpoint/yield/controller development was cancelled by decision before use. No new resume flags,
training source or automatic second-seed loop runs. The immutable source is 40ea0b503d94daba5486cb151f759b233664ba43,
reviewed with R3 GO and independently bound/landed by the parent. The two implementation commits are b53b95763
and 40ea0b503, parent cherry-picks 15cf69733 and 4c730c439.

The frozen oldest 240 sealed batches contain 119,970 source matches, 119,475 usable matches and 23,498,034 rows.
There are 18,811,143 TRAIN rows, 2,332,353 DEV rows and 2,354,538 FINAL rows. Both seats and physical duplicate games
retain their original split. FINAL remains unused by training, calibration and selection. Exact/outcome value
labels and imitation-truncated other tiers are unchanged. Live own-bot memory is validation/evaluation only.

Input receipt map SHA256: 2422eb7321982a60b14f5152d3a4338f456294d1cd249b6cbb973de834c765c2.
Store manifest SHA256: 1aa01c37fdd18ac7c23a5e9cf7b875b674d5021309ab4b4b79603fd29661b264.
The store is /mpac/sdicks02/datasets/pretrain-v1/05/interim-20261022-b240/f-ce6e509ee43a-b-1005dbb4
on 05/08/01/02. Every transferred file was SHA-verified, and the exact shard set checked before readiness.

Build owner 1254644 completed naturally with 24 workers on 05, reusing 83 verified immutable shards and building 157.
Measured build throughput was 49.16 usable matches/sec and 9,660 rows/sec, 26.49 minutes through the last shard,
29.57 minutes through verified 08 readiness. All source-missing/SHA/no-job/perspective-exception counters are zero.

M training remains d320/L6/H8/FFN1280/dropout .1, batch 512, bf16, AdamW 2e-4/wd .01, 3 torch threads,
8 passes maximum, patience 2, one-pass warmup and cosine, 64 GPU-hour per-seed cap. R7 consumed-future release and
host checks remain. Initial admission requires 50 GiB available/load <80/empty GPU; cooperative batch checks stop
our own job below 29 GiB or above 90 load without process signals. Per-seed allocator cap is 39.03515625 GiB.

| Host | Seed | PID | Launched UTC | Step sampled | Rows/sec | Physical GPU GiB | Host available GiB |
|---|---:|---:|---|---:|---:|---:|---:|
| 127x01 | 2026102002 | 2786949 | 20:54:57Z | 1500 | 4371.4 | 13.21 | 103.34 |
| 127x02 | 2026102003 | 3293704 | 20:54:57Z | 1500 | 4354.0 | 15.81 | 103.39 |
| 127x08 | 2026102001 | 2985510 | 20:48:23Z | 2000 | 3095.5 | 16.26 | 34.30 |

Rates are early training samples, before any shared soak. They imply roughly 1.8 hours/epoch on 08 and 1.2 hours
on 01/02, up to 14.5/9.7 hours for 8 passes, plus later validation/calibration and full-DEV selection; early stopping
may shorten this. Prior 41k M complete-workflow allocator peak 32.10 GiB includes larger DEV/calibration batches.
The current hundreds-step measurements do not establish that complete-workflow peak. Parent owns any soak
co-location decision and GPU admission. No shared soak was launched here.

The same 73 source inputs and exact 08 Python/NumPy/Torch runtime identities are enforced on 01/02. Only the host
binding was added to their operational manifests. Archive SHA256 is
dd3c26ff79de1f9acd39b8f27919451ac250e4ef04be82244303680331a55e8d.
08 training pin: e34e88921c36f87febeda11857af5e49fdd1fe8698a250da0e0ec674c5fe7125.
01 host-binding pin: d7f92827159ad55beaec95e893e0c0cdfbdbf93c749fd86dcd44e4a337f79cc4.
02 host-binding pin: 189ad047c53fb85eed8a6a2cd190d6c3ce4a24886d19652466a8f96bb99982d0.

Receipts and telemetry are under /mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240/ on 05 and each
training host. all-three-launches.json preserves exact commands/PIDs/start/boot identities; frozen-snapshot-final.json,
mirror-0102.json and three-host-telemetry.jsonl preserve measured evidence. Amendment receipts supersede historical
dropout-zero, review-pending, serial-two and yield plans without overwriting them. These are active training jobs;
no seed has completed and no anchor is admitted yet. After all seeds complete, mirror their immutable run artifacts
to 08 with SHA verification and run the existing registered select_bc over all three seed runs, full DEV, before
claiming an admitted anchor. The model-only epoch checkpoints do not support exact optimization resume.
