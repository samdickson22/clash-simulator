# T4 all-card imitation implementation

Fresh plain PyTorch, 2,254,938 trainable parameters. Four pre-LN d192, six-head,
FFN768 blocks; tile cross-attention d64/4 heads and FFN256; gate/card/conditional
576-tile policy; eight-class intent and 13 discrete hazard logits. No old model,
trainer, checkpoint, recurrence, or value head. CPU and eager CUDA supported;
CUDA uses bf16 autocast. No compile path.

Tile width 64 is the design's prescribed latency fallback. The initial d128
model had 2,399,898 parameters; qualified dev rows reached 78 entities and its
78-entity CPU p99 was 17.45 ms. Single-request inference now omits padding;
its logits match the padded training path in a unit test. Training still buckets.

## Entry points

Run as modules from the checkout (or from an isolated snapshot with its directory
on PYTHONPATH). The CPU test env on 127x05 is
`/mpac/sdicks02/tmp/imitation-model-cpu/bin/python`.

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 /mpac/sdicks02/tmp/imitation-model-cpu/bin/python -m pytest imitation/model/tests -q
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 /mpac/sdicks02/tmp/imitation-model-cpu/bin/python -m imitation.model.benchmark --iterations 1000 --output /mpac/sdicks02/tmp/t4-latency-new.json
```

- `network.py`: tensor-only network, `log_policy`, scriptable forward with
  teacher-forced slot or all four conditionals. Illegal supports have exactly
  zero probability, including all-illegal card/tile supports on forced waits.
- `features.py`: **shared** train/serve public adapter. First four tokens are
  hand cards; no hand-slot embeddings. Entities are sets, with Fourier position
  features. Own/opp queues have ordered roles. Deck tokens sort by token ID and
  carry their canonical index, matching the eight auxiliary output classes.
- `losses.py`: weighted conditional losses. Gate only on playable supervised
  rows; card/tile only on labelled plays. Intent CE only on observed next cards,
  hazard survival terms through complete intervals for censored rows. Bin ends
  match T3: 12 log-spaced boundaries 0.05..10 seconds, then >10 seconds.
- `store.py`: read-only adapters for the actual T3 `clasher.imitation.packed.v1`
  store and an explicit synthetic fixture schema. Pass **role directories**,
  e.g. `/.../c56-store-v1/train`. T3 uses big-endian packed masks; fixture schema
  uses little-endian. It opens train/dev only and never reads audit files.
- `train.py`: hash-by-row-and-epoch wait sampling, iid shuffling, local entity
  count bucketing, effective batch 8192 via microbatches (default 64), AdamW
  3e-4/.05, cosine + 2000-step warmup, clip1, EMA.999; detached JSONL logs,
  atomic full checkpoints, SIGTERM/INT checkpointing and resumable epoch cursor.
- `evaluate.py` / `runner.py`: all frozen metrics plus proposal top8 exact/within
  one Euclidean tile, tile within1, intent hazards, per-card/arena and frozen
  metadata slices; ECE before/after independent gate/card/tile dev temperatures.
  Natural unit weights, all supervised rows; default 10,000 whole-perspective
  bootstrap resamples. Metric row arrays and identities persist for independent
  recomputation and paired baseline comparisons. CLI intentionally accepts dev
  only in T4. `offline_gates` implements A1–A4 and treats missing cards as
  unassessed. The calibrated gate ECE is binary P(play-or-ability), with
  multiclass gate ECE also reported. Equal-mass timing calibration is separate.
- `assets.py`: reuses only approved v5 static feature builders. Generate the
  asset NPZ using **T3's frozen runtime and gamedata**, not the current canonical
  checkout. Records the actual full token/asset SHA256. No pretrained weights.
- `inference.py`: `load_policy(path)` loads EMA by default, returning a CPU
  `Policy` with `propose(public_packet, d1, k=8)` and stochastic `sample(...)`.
  `Policy.export(path)` scripts the tensor model and embeds provenance/hashes.

## CPU API and export

```python
from imitation.model import load_policy
policy = load_policy(checkpoint_path)
candidates = policy.propose(public_packet, d1, k=8)
# [{'action': slot*576+tile, 'slot': slot, 'tile': tile,
#   'probability': p_card * p_tile_given_card}, ...]
policy.export('policy.ts')
```

The packet is a mapping/object with v5 hand_ids(5), hand_levels(5), globals(18),
entity_ids/levels/features(17 compact or 32 full)/mask, seen-card IDs,
champion_button, and unpacked action_mask(2306). The caller uses the existing v5
mask builder. `d1` uses the actual token-valued sidecar fields described in
`reports/strategy_council_20260928/imitation/DATA-CONTRACT.md`: integer-ms
refills, split recent-play and ability history arrays, own deck/queue,
opponent known hand/next/queue, elixir/revealed count/exact flag. Coordinates are
already canonical normalized. No own/opp event stream reconstruction is hidden
in the model; T1 supplies D1. A normalized mapping with combined history columns
is also accepted for fixtures; see `synthetic.packet`.

`propose` omits gate probabilities, wait and ability; search adds no-op itself.
No legal play returns []; fewer than k legal pairs returns all of them. The
TorchScript artifact provides `forward(batch, teacher)` and `log_policy(batch)`.
Its tensor dictionary comes from `build_row`/`collate_features`, which must be
ported byte-for-byte by a non-Python Mac caller. The Python CPU API is complete;
Mac runtime benchmarking and T6 train/serve equality are later tasks.

## Qualified GPU shakedown

Update 2026-10-08 07:21Z: the initial job `t4-shakedown-20261008T0714Z`
exited 1 during dev loading after completing eight subset optimizer steps.
The real store exceeds the design's assumed 64 entities (train max 74, dev 78).
The adapter now retains up to the v5 packet cap of 128, using a 192-token bucket
when needed. A checkpoint is saved before dev validation so failures can resume.
See `../PROGRESS-model.md` and `receipts/t3-wait.json` for the current rerun label.
`shakedown.py` runs the fixed sequence below and writes stage receipts.
The adapter validates column shapes/dtypes and binds qualification to the
store manifest, role-file hash and train/dev counts. Results remain pending.

Do not start real fitting until the actual T3-PASS receipt exists. It is polled
at 10-minute intervals by the same-thread scheduler recorded in PROGRESS-model.
The actual packed adapter is tested against a synthetic replica, but real-store
integration still must be checked against the PASS receipt and finalized schema.

On 127x04 only after `who`, worker-budget and GPU occupancy checks, stage **only
this task's files** with `rsync -c` into a fresh owned snapshot. Use the existing
`fleet/fleet_run.sh` detached launcher; its launch receipt is not job completion.
Set `PYTHONPATH` explicitly in the `env` command after the launcher because the
launcher sets its own. Interpreter: `/mpac/sdicks02/envs/clasher-gpu/bin/python`.
One trainer plus at most two loader workers leaves room under the shared 80
worker total; account for *all* other active workers before launching.

Generate static assets on the GPU host with the frozen runtime's `src` first
in PYTHONPATH, and `CLASHER_ROOT` pointing to `c56/data/runtime-engine-v3b`.
The source snapshot itself follows on PYTHONPATH. An example module invocation:

```bash
python -m imitation.model.assets /owned/t4-run/assets.npz
python -m imitation.model.train \
  --store /qualified/c56-store-v1/train --dev /qualified/c56-store-v1/dev \
  --assets /owned/t4-run/assets.npz --qualification /qualified/receipts/T3-PASS.json \
  --output /owned/t4-run/subset --epochs 1 --subset-fraction .02 --epoch-fraction .2
python -m imitation.model.train \
  --store /qualified/c56-store-v1/train --dev /qualified/c56-store-v1/dev \
  --assets /owned/t4-run/assets.npz --qualification /qualified/receipts/T3-PASS.json \
  --output /owned/t4-run/overfit --batch-size 1000 --overfit-rows 1000 --max-steps 200
python -m imitation.model.evaluate \
  --store /qualified/c56-store-v1/dev --assets /owned/t4-run/assets.npz \
  --roles /frozen/c56_roles_v1.json --checkpoint /owned/t4-run/subset/CHOSEN.pt \
  --output /owned/t4-run/dev-evaluation --device cuda --calibrate
```

These are shakedown commands, not authorization to launch T5. Subset uses a
fixed 2% hash-selected perspective subset and 0.2 of its epoch's sampled rows.
Overfit repeats the same 1,000 training rows. No eval/eval_ood or Mac commands.
Logs report each conditional loss, total loss, rows/s including loader and
step-only rows/s, gradient norm, LR, allocated/reserved GPU peak memory.
Record the loss curve rather than declaring a pass from process exit alone.

Resume with `--resume CHECKPOINT` and the **same recipe flags**. Resume validates
config, data hashes and recipe, restores optimizer/scheduler/RNG and sampler
cursor. It finishes an interrupted epoch. A checkpoint already at max-steps does
not train another batch. EMA is used for dev selection. Early stopping patience
is three epochs by default, recorded in config.

## Clarifications and deviations

- Qualified data exceeds 64 entities in 112 train and 10 dev rows. Retain the
  full v5 cap of 128 entities, with 128/192-token buckets beyond the design's
  48/64/96. No entity truncation or hidden selection. Absent history/seen slots are omitted;
  unknown opponent-cycle facts remain explicit tokens.
- Intent class order is canonical sorted own-deck token IDs. T3's original deck
  indices are remapped by token identity. This is necessary for the CLS MLP to
  have well-defined classes independent of storage order.
- Hazard censoring at an exact boundary includes survival of that completed
  interval; event-at-boundary belongs to that interval. T3's single intent_bin
  does not distinguish this case, so the adapter derives the correct bin from
  intent_delay_ticks and intent_censored without changing stored targets.
- Training uses the frozen quality/balance weights and wait IPW once. Reported
  metrics use unit natural supervised-row weights per frozen JSON. The primary
  when metric uses playable rows per design; *_all also preserves the frozen
  JSON's all-row definition. Both are saved to avoid silently resolving the
  small wording conflict.
- The hard no-delete rule wins over checkpoint pruning: last-three/best are
  indexed, but old owned checkpoints are retained. No source data is deleted.
- Temperature fitting uses a deterministic uniform dev reservoir capped at
  100,000 rows by default; report records cap and fitted temperatures. Full dev
  metrics and slices use every row. Set a larger cap explicitly for T5 if wanted.
- Default early-stop patience (3), hazard lower boundary (.05s from T3), 10 ECE
  bins and eight ability history slots are explicit implementation choices where
  the prose design did not pin those details. Trunk width remains as designed;
  tile width uses the predeclared latency fallback of 64.
- The draft design's token SHA prefix is stale relative to the current checkout.
  Always use the actual frozen-runtime asset SHA, and record it in checkpoints.

## Current evidence

See `../PROGRESS-model.md` and `receipts/`. CPU tests and latency are real
measurements of synthetic inputs. They do **not** claim the GPU shakedown passed.
T3 real-store loading, rows/s, loss curve and GPU memory remain pending its PASS.

For paired dev baseline diagnostics, pass `--frequency-counts` with T3's
train-only histogram NPZ and `--card-scope` with the preregistered token-ID list.
This evaluates those counts using this evaluator's exact row eligibility; it
never imports or runs T3's baseline scorer. `--p16-summary` can consume the
already-scored **dev** P16 result after checking its supervised-play count.
Alternatively, `--frequency-rows` / `--p16-rows` consume aligned metric arrays
with exact row-ID verification. T4 neither executes the old BC code nor reads
its checkpoint. The model and optimizer checkpoint replay test is bit-exact.
