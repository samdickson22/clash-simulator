# T6/T8 launch commands

Run from `/mpac/sdicks02/repos/clasher` on an authorized fleet host. The 127x05
checkout is the source/mirror, not a game worker. No commits or engine/gamedata
edits are part of these adapters. Copy only owned evaluation code/docs/receipts
with `rsync -c`; do not overwrite another task's dependency files.

## Dependency and runtime preflight

`imitation/model/` must already be available to the worker, with the T5-selected
CPU API. The current 127x03 checkout lacks it; dependency staging authorization
or a pre-existing model snapshot is still needed. Do not treat a stub proposer
as a model latency test. The native extension, root metadata, deck catalogs and
P16 comparator checkpoints must also exist. This adapter uses the checkout's
Python engine with P16 decks/scripts and records/pins its source and gamedata;
it does not silently claim identity with pilot-runtime-v4. If frozen-v4 engine
identity is required, qualify that separately before freezing the manifest.

```bash
who
ps -eo pid,ppid,ni,pcpu,comm,args --sort=-pcpu
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/engine-rs"
export CLASHER_ROOT="$PWD"
PY="$PWD/.venv/bin/python"
```

Count all workers on the host before launching; maximum 96 total, 16 with a
console user. Each search process can also start two native threads. Start one
process initially on the busy 127x03 host; add workers only after another load
check. Use the detached fleet launcher, which sets nice 10 and keeps exit logs.
127x04/08 are unavailable until S3 finishes. Never use forbidden hosts.

## Plumbing only

Generate the full-size random checkpoint once (or use the already generated
`/mpac/sdicks02/tmp/t6t8-synthetic.pt`).

```bash
nice -n 10 "$PY" -B -m imitation.evaluation.synthetic_checkpoint \
  --output /mpac/sdicks02/tmp/t6t8-random-new.pt
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6t8-search-smoke-r1 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.smoke \
  --checkpoint /mpac/sdicks02/tmp/t6t8-synthetic.pt \
  --games 20 --skew-games 8 --output imitation/receipts-t6t8/search-r1
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6t8-c56-smoke-r1 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.smoke \
  --checkpoint /mpac/sdicks02/tmp/t6t8-synthetic.pt --standalone --games 4 \
  --seed 68275001 --skew-games 4 --output imitation/receipts-t6t8/c56-r1
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6t8-p16-smoke-r1 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.run_p16 \
  --checkpoint /mpac/sdicks02/tmp/t6t8-synthetic.pt --games 4 --cell 0 \
  --seed 68375001 --plumbing-only --output imitation/receipts-t6t8/p16-r1
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6t8-h2h-smoke-r1 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.run_p16 \
  --checkpoint /mpac/sdicks02/tmp/t6t8-synthetic.pt --games 4 --cell 0 \
  --seed 68475001 --head-to-head --plumbing-only --output imitation/receipts-t6t8/h2h-r1
nice -n 10 "$PY" -B -m imitation.evaluation.summarize_smoke \
  imitation/receipts-t6t8/search-r1 --games 20 \
  --output imitation/receipts-t6t8/search-r1-summary.json
```

These are separate jobs; do not paste all launch commands concurrently without
checking the combined worker budget. No synthetic results establish strength.
Four-game P16 smoke covers both seats of two holdout/balanced worlds; full gate
covers every role/style/block. H2H smoke preserves fixed physical decks.

## Prepare and freeze gates after T5

Set `CKPT` to the dev-selected v1 checkpoint and `CKPT_SHA` to its T5 SHA256.
Use fresh output directories (do not reuse plumbing outputs).

```bash
CKPT=/absolute/path/to/T5-selected-v1.pt
CKPT_SHA=REPLACE_WITH_T5_SHA256
nice -n 10 "$PY" -B -m imitation.evaluation.register --gate b --output imitation/gate-b/v1
nice -n 10 "$PY" -B -m imitation.evaluation.register --gate c --output imitation/gate-c/v1
```

This writes schedules/proposed seeds only. Complete the PREREG fleet seed audit
before freezing. `seed_audit scan` scans JSON/JSONL/gzip/NPZ and exact integers in
text. Include both `reports` and `imitation`, plus prior job logs. Exclude only
the new prospective gate directory and this prospective adapter source; include
plumbing receipts and every historical/failed receipt. Run independently on all
five authorized hosts, using the same proposed seed file. It reports source
files with seed formulas for explicit range review. Preserve inventories and
range-review receipt; `merge` refuses incomplete inventories or unreviewed ranges.
Do not copy arbitrary existing files across hosts to run this audit.

Example per-host scan (owned scripts only may be staged):

```bash
nice -n 10 "$PY" -B -m imitation.evaluation.seed_audit scan \
  --root reports --root imitation --root /mpac/sdicks02/jobs/clasher \
  --seeds imitation/gate-b/v1/proposed-seeds.json \
  --exclude imitation/gate-b --exclude imitation/evaluation \
  --output /absolute/owned/audit-b-127x03.json
```

Use `seed_audit merge --inventory PATH` for each of the five inventories,
`--range-review PATH --output PATH`. The range-review JSON contains
`complete: true`, `no_overlap: true`, `inventory_hashes: {path: sha256}` and
`reviewed_formula_files: {host: [exact inventoried formula paths]}`. These fields
must represent a real completed review. Do not fabricate an audit to bypass it.

Once the audit passes and T6/T8 smoke acceptance is independently checked:

```bash
nice -n 10 "$PY" -B -m imitation.evaluation.register --gate b --output imitation/gate-b/v1 \
  --checkpoint "$CKPT" --checkpoint-sha256 "$CKPT_SHA" --audit /absolute/owned/gate-b-seed-audit.json
nice -n 10 "$PY" -B -m imitation.evaluation.register --gate c --output imitation/gate-c/v1 \
  --checkpoint "$CKPT" --checkpoint-sha256 "$CKPT_SHA" --audit /absolute/owned/gate-c-seed-audit.json
```

Freeze writes a checkpoint-filled `PREREG.frozen.md` and pinned `manifest.json`;
the requested draft remains TBD. Synthetic checkpoints are refused.

## Exact gate game launches

```bash
bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-gate-b-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.run_gate \
  --manifest imitation/gate-b/v1/manifest.json --worker 0 --workers 1
bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-gate-c-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" "$PY" -B -m imitation.evaluation.run_gate \
  --manifest imitation/gate-c/v1/manifest.json --worker 0 --workers 1
```

Gate (b): 640 B-v-A plus 256 A-v-scripts plus 256 B-v-scripts. Gate (c): two
P16 blocks × three policies × six cells ×32; 256 fixed-world H2H; 384 C56 scripts.
`--workers N --worker I` shards pair/cell ownership; use identical N and disjoint
I for every worker. Pin paths are absolute: freeze against the intended worker
checkout, and ensure identical hashes/paths on mirrors before using them.
`run_gate --section p16|h2h|c56` can split gate (c), but do not overlap an `all`
worker with section workers. Successful game receipts resume; failed P16 attempts
require a fresh rerun directory and an explicit retained technical-rerun reason.
Do not run outcome analyses until all registered games finish.
