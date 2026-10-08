# T6/T7 fleet runbook

All commands run from `/mpac/sdicks02/repos/clasher` on **127x01**. Use only
`/mpac/sdicks02/envs/clasher-gpu/bin/python`; eager CUDA, no compile. Check `who`,
Python worker count and `nvidia-smi` before each launch: total <=96 (<=16 with
console user), leave >=12GiB GPU headroom. `fleet_run.sh` applies nice 10 and
thread limits. Use distinct labels; inspect `.exit`, not just launch acceptance.
Only copy owned source paths with `rsync -cR`; never sync the whole checkout.

Formal commands are PREPARED, not running or automatically scheduled. T1 has not
provided Phase A completion. Do not create completion receipts yourself. Once its
authentic `pipeline-state.json` (`stage=complete`) and `phase-a-exit.json`
(`code=0`) are mirrored, run the following sequentially through the fleet helper
(substitute real receipt paths and a fresh output path):

```bash
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6-formal-UNIQUE \
  bash reports/strategy_council_20260928/live-loop/v4/l1/formal_train.sh \
  t6 /path/from/T1/pipeline-state.json /path/from/T1/phase-a-exit.json \
  /mpac/sdicks02/repos/clasher-v4-training/t6-formal-UNIQUE

bash reports/strategy_council_20260928/fleet/fleet_run.sh t7-formal-UNIQUE \
  bash reports/strategy_council_20260928/live-loop/v4/l1/formal_train.sh \
  t7 /path/from/T1/pipeline-state.json /path/from/T1/phase-a-exit.json \
  /mpac/sdicks02/repos/clasher-v4-training/t7-formal-UNIQUE
```

T6: 24x400 steps, seed 6107, unchanged v2 warm start, 3-positive/1-negative
sampling, losses, LR and clip, fp32 control. Only CUDA plumbing and an explicit
4096MiB cache disk allowance differ operationally. All converter payloads remain
retained. The adapter supplies only missing evaluator layout/protocol-2 metadata.
T7: 24x400 steps, seed 6108, fresh random weights, bf16, batch one T16 window,
AdamW 0.0003, no worker subprocesses. Epoch checkpoints and optimizer/RNG state
are written. Training populations are snapshotted before decoding.

Resume T7 with identical arguments and `--resume` through a new fleet label,
after verifying the old PID has exited. Source/options must match its manifest.
It resumes from the last eight-step checkpoint; inspect the training JSONL for
an uncheckpointed tail before aggregating metrics. T6's unchanged trainer is not
optimizer-resumable: preserve partial output, use a fresh run directory and
replay the deterministic fit. Complete stages are reused by run_t6_shake.py;
partial stages deliberately refuse overwrite. Conversion resumes complete
per-match roundtrip outputs and refuses to overwrite partial matches.

No heldout scoring entry point is enabled by these commands. Formal model
selection/calibration must finish on validation and be sealed. The full v4
heldout evaluator and T5/T8 integration/Mac replay remain follow-on work; all
§5.1 endpoints are registered, but this implementation shakedown does not certify
them. T6 validation is available through the unchanged evaluator. Gap diagnostic:

```bash
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6-gap-UNIQUE \
 /mpac/sdicks02/envs/clasher-gpu/bin/python \
 reports/strategy_council_20260928/live-loop/v4/l1/gap_t6.py \
 --dataset /path/to/t6/dataset --run /path/to/t6/run \
 --l2 reports/strategy_council_20260928/live-loop/l2/native \
 --output /mpac/sdicks02/repos/clasher-v4-training/t6-gap-UNIQUE
```

Retain all source/data/weights on 01; mirror only code, docs, JSON receipts and
logs to 05. No media or model files to 05. Keep total v4 fleet footprint <=40GB;
stop on space pressure instead of deleting data. Export plan: EXPORT.md.
