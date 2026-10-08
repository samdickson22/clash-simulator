# Isolated T6/T8 evaluation launch

All results made so far use a full-size randomly initialized checkpoint and are
**plumbing only**. See `imitation/PROGRESS-T6T8.md` for measured qualification and
retained failed timing attempts. Do not overwrite shared host `imitation/` paths.

## Snapshot and input contract

The model and evaluation package are loaded from an immutable snapshot; the
engine and data checkout are separate read-only inputs. `snapshot.py` records
per-file SHA256, the full tree SHA256, source HEAD, and which files match model
commit `43d895e069e5b6ce25229c2fefa140880869dce2` exactly. A real package boundary
prevents Python from merging the snapshot with mutable shared model code.

On 127x05, prepare a NEW snapshot from the current source (no game work here):

```bash
python3 imitation/evaluation/snapshot.py \
  --source /mpac/sdicks02/repos/clasher \
  --parent /mpac/sdicks02/repos/clasher-eval-snapshots
```

Use the printed directory/hash. Transfer with `rsync -rc --checksum` to:
- ordinary host: `/mpac/sdicks02/repos/clasher-eval-snapshots/<short-tree-sha>/`
- leased host: `/mpac/sdicks02/repos/clasher-lease/eval-snapshots/<short-tree-sha>/`

Run `python -B -m imitation.evaluation.snapshot --verify "$SNAP"` after staging
and before jobs. Never edit an existing snapshot. If T4/T5 changes model code,
create and qualify a new snapshot. At T5 checkpoint selection, resnapshot the
final source and pin that full tree hash in BOTH frozen gate PREREGs/manifests.
The registration command below does this and rejects non-snapshot execution.

Plumbing snapshots used:
- `6e8fced75565f630`: 127x03 standalone adapters and initial search attempt.
- `c42198b5a93af5bb`: accepts a checksum-pinned external C56 prior on leased 11.
- `74720afb0fb8ee3b`: exact faster public-prior array operations, shared by A/B.
- **`e3c60ef30743427a`**: final single snapshot for all routes; correct eval-deck
  ownership in both C56 smoke seats. Full SHA256:
  `e3c60ef30743427aa8b654d3327fe0a567791a78221c90468181c2ab70a6cc90`.
  Search: 20 games, p50 5.027 ms, p99 200.362 ms, max 242.041 ms, no >250 ms.
  Standalone: four terminal games per route; zero illegal/rejected imitation
  commands. Unchanged script rejections are retained separately.

Only the C56 prior and synthetic checkpoint needed transfer to leased 11; both
are under `clasher-lease/eval-snapshots/inputs-t6t8/`, separately hashed. No
borrower/owner shared code, gamedata, environments or caches were changed.

## Environment and host admission

Ordinary 127x03:

```bash
RUNTIME=/mpac/sdicks02/repos/clasher
SNAP=/mpac/sdicks02/repos/clasher-eval-snapshots/REPLACE_SHORT_SHA
OUT=/mpac/sdicks02/repos/clasher-eval-snapshots/runs/REPLACE_FRESH_LABEL
PY="$RUNTIME/.venv/bin/python"
export CLASHER_ROOT="$RUNTIME" CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME"
export PYTHONPATH="$SNAP:$RUNTIME/src:$RUNTIME/engine-rs"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
who
ps -eo pid,ppid,ni,pcpu,comm,args --sort=-pcpu
```

Total workers <=96, <=16 with a console user; include existing work and
supervisors. Do not assume low average load guarantees the wall bound. The busy
03 search attempt failed the wall bound and remains retained. Use nice 10+.

For leased 11/13/14/16/18, read `/mpac/sdicks02/cc/FLEET-SHARING.md`, the live
host lease and `who`; refusal/reclaim/expiry/missing lease blocks launch. Source
ONLY `/mpac/sdicks02/repos/clasher-lease/env.sh`, then set:

```bash
RUNTIME="$CLASHER_LEASE_ROOT/repo"
SNAP="$CLASHER_LEASE_ROOT/eval-snapshots/REPLACE_SHORT_SHA"
OUT="$CLASHER_LEASE_ROOT/eval-snapshots/runs/REPLACE_FRESH_LABEL"
PY="$RUNTIME/.venv/bin/python"
export CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME"
export PYTHONPATH="$SNAP:$RUNTIME/src:$RUNTIME/engine-rs"
```

Use the reclaim-aware `"$CLASHER_LEASE_ROOT/run.sh" LABEL COMMAND...` launcher,
never `fleet_run.sh` on a leased host. Keep children in its process tree. Its
exit receipt, not launch acknowledgment, establishes completion. Respect each
lease's cap/RSS budget. The qualified timing setup used four workers on disjoint
three-core CPU sets on 11, 200-ms player deadline and two Rust threads per player.
No work on 02/07/10/12/17; GPU-only leases 09/15 are not CPU game hosts.

## Synthetic smokes

Fresh checkpoint generation, if needed (one CPU worker, never overwrite):

```bash
"$PY" -B -m imitation.evaluation.synthetic_checkpoint --output "$OUT/random.pt"
```

Use a detached niced ordinary launcher or reclaim-aware leased launcher around
each command below. These are worker commands, not permission to overfill hosts.
`CKPT` must name the random checkpoint and `PRIOR` the exact Stage 5 C56 prior.

```bash
"$PY" -B -m imitation.evaluation.smoke --checkpoint "$CKPT" --prior "$PRIOR" \
  --games 20 --skew-games 8 --output "$OUT/search" --workers 1 --worker 0
"$PY" -B -m imitation.evaluation.smoke --checkpoint "$CKPT" --standalone \
  --games 4 --seed 68275001 --skew-games 4 --output "$OUT/c56"
"$PY" -B -m imitation.evaluation.run_p16 --checkpoint "$CKPT" \
  --games 4 --cell 0 --seed 68375001 --plumbing-only --output "$OUT/p16"
"$PY" -B -m imitation.evaluation.run_p16 --checkpoint "$CKPT" \
  --games 4 --cell 0 --seed 68475001 --head-to-head --plumbing-only --output "$OUT/h2h"
```

For four search workers use `--workers 4 --worker I`, I=0..3, one shared output
directory and disjoint ownership; do not overlap with a worker launched at N=1.
The exact leased batch scripts/exit receipts are retained with the evidence.
P16 smoke covers both seats of two holdout/balanced worlds. H2H smoke fixes
physical decks and swaps controllers. The full gate expands all cells/styles.
Legality receipts distinguish candidate rejection from script rejection.

## Prepare and freeze gates after T5

Set the final dev-selected checkpoint and its externally established SHA256:

```bash
CKPT=/absolute/path/to/T5-selected-v1.pt
CKPT_SHA=REPLACE_WITH_T5_SHA256
"$PY" -B -m imitation.evaluation.register --gate b --output "$OUT/gate-b"
"$PY" -B -m imitation.evaluation.register --gate c --output "$OUT/gate-c"
```

This only prepares schedules/proposed seeds. Perform the PREREG audit against
all historical authorized-host inventories (including failed/partial runs,
leased runs, generated seed ranges and mirrors), before playing any gate games.
The original five-host historical audit remains required; include new leased
receipts in its consolidated inventories. Exact scans are available with:

```bash
"$PY" -B -m imitation.evaluation.seed_audit scan \
  --root "$RUNTIME/reports" --root "$RUNTIME/imitation" --root /absolute/job/logs \
  --seeds "$OUT/gate-b/proposed-seeds.json" \
  --exclude /absolute/prospective/gate-b --exclude "$SNAP" \
  --output /absolute/owned/audit-b-HOST.json
```

Scan both gates separately. Preserve all inventories and explicitly review the
reported seed-formula paths/ranges. `seed_audit merge` requires five
`--inventory PATH` arguments, `--range-review PATH --output PATH`. Its review
JSON records `complete`, `no_overlap`, `inventory_hashes: {path: sha256}` and
`reviewed_formula_files: {host: [paths]}`. Those must represent a real complete
review, not filled-in placeholders. Add all new leased receipts to that review.

After smoke qualification and independent review, freeze:

```bash
"$PY" -B -m imitation.evaluation.register --gate b --output "$OUT/gate-b" \
  --checkpoint "$CKPT" --checkpoint-sha256 "$CKPT_SHA" --audit /absolute/owned/gate-b-seed-audit.json
"$PY" -B -m imitation.evaluation.register --gate c --output "$OUT/gate-c" \
  --checkpoint "$CKPT" --checkpoint-sha256 "$CKPT_SHA" --audit /absolute/owned/gate-c-seed-audit.json
```

Freeze writes `PREREG.frozen.md` with checkpoint and full snapshot SHA256, plus
`manifest.json`. Synthetic checkpoints and incomplete audits are refused. Source
drafts stay TBD. Absolute runtime/input pins must agree on every worker host.

## Exact confirmation launch commands

On ordinary 03 (after admission/load check):

```bash
bash "$RUNTIME/reports/strategy_council_20260928/fleet/fleet_run.sh" imitation-gate-b-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME" \
  "$PY" -B -m imitation.evaluation.run_gate --manifest "$OUT/gate-b/manifest.json" --worker 0 --workers 1
bash "$RUNTIME/reports/strategy_council_20260928/fleet/fleet_run.sh" imitation-gate-c-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME" \
  "$PY" -B -m imitation.evaluation.run_gate --manifest "$OUT/gate-c/manifest.json" --worker 0 --workers 1
```

Leased equivalent (all runtime/data/comparator inputs must first be present and
pinned in the Clasher footprint):

```bash
bash "$CLASHER_LEASE_ROOT/run.sh" imitation-gate-b-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME" \
  "$PY" -B -m imitation.evaluation.run_gate --manifest "$OUT/gate-b/manifest.json" --worker 0 --workers 1
bash "$CLASHER_LEASE_ROOT/run.sh" imitation-gate-c-v1-w0 \
  env PYTHONPATH="$PYTHONPATH" CLASHER_EVAL_RUNTIME_ROOT="$RUNTIME" \
  "$PY" -B -m imitation.evaluation.run_gate --manifest "$OUT/gate-c/manifest.json" --worker 0 --workers 1
```

Gate b runs 640 B-v-A +256 A-v-scripts +256 B-v-scripts. Gate c runs 384×3 P16
policy games +256 H2H +384 C56 script games. Use identical N/disjoint worker I
when sharding; do not overlap `--section all` with individual section workers.
No outcome analysis before completion. Retain technical failures and rerun
reasons; do not rerun to remove a slow decision or a loss.

Runtime qualification is the checkout Python engine on P16 decks/protocol,
not a claim of byte-identical engine source to historical pilot-runtime-v4.
The imitation actor uses v5; P16 scripts and s2902 keep their v4 infrastructure.
Both search arms use the verified exact fast-prior implementation; scripts,
search scoring, candidate priority, tie rule, engine and gamedata are unchanged.
