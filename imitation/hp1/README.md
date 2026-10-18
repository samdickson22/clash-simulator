# HP1 P1 pilot code (reports/bot/hp1/DESIGN.md §2.5, §7)

- `lagshift.py`: command-lag label overlay for the v2 train role (CPU, read-only on the store, ~5 GB RAM).
- `train.py`: the qualified T4 trainer with T11 mixed sampling, plus `--layers/--ffn`, `--init`, `--lr`,
  `--overlay`, `--stop-after-epochs`, `--max-gpu-gb`, `--smoke`, and opt-in `--block-shuffle`.
- `test_lagshift.py`: unit tests (`python -m pytest imitation/hp1/test_lagshift.py -q`).

Store S = `~/repos/clasher-t11-home-v1/data/v2-store-v1` (04, 08). Inputs A = `assets.npz` (sha 3954af44…) and
Q = `T11-STORE-PASS.json` (sha 0e14fefa…) from 04 `~/repos/clasher-t11-home-v1/inputs/`.
Common T4 args: `--store S/train --dev S/dev --assets A --qualification Q --batch-size 8192 --workers 2
--warmup 2000 --patience 3 --tile-width 64 --checkpoint-every 1000`. The wrapper writes `OUT.hp1-options.jsonl` beside OUT (T4 needs OUT fresh).

| run | extra args | GPU estimate |
|---|---|---|
| overlay (CPU) | `python -m imitation.hp1.lagshift --store S/train --out $J/overlay-lag30` | none, minutes |
| CPU smoke cap-1 | `--device cpu --layers 6 --ffn 1536 --batch-size 64 --microbatch 64 --workers 0 --epochs 3 --epoch-fraction 0.00001 --max-steps 50 --stop-after-epochs 1 --smoke --seed 1 --output $J/smoke/cpu-cap` (fresh launch; exits after epoch 1's dev) | none |
| CPU smoke cap-2 | same args, `--stop-after-epochs 2 --resume $J/smoke/cpu-cap/epoch-000-step-*.pt` (resume across the epoch boundary) | none |
| CPU smoke lag | `--device cpu --init V2 --lr 1e-4 --overlay $J/overlay-lag30 --batch-size 64 --microbatch 64 --workers 0 --epochs 2 --epoch-fraction 0.00001 --max-steps 50 --stop-after-epochs 1 --smoke --seed 2 --output $J/smoke/cpu-lag` | none |
| CPU smoke lag-2 | same args as lag without `--init`, plus `--stop-after-epochs 2 --resume <lag's epoch-000 checkpoint>` (init pin carried over) | none |
| GPU smoke | `--max-steps 20 --smoke --output $J/smoke/gpu-...` | minutes |
| P1-cap | `--layers 6 --ffn 1536 --epochs 6 --stop-after-epochs 1 --microbatch 2048 --seed 2026101801 --max-gpu-gb 24` | ≈3.5 h + ≈0.6 h dev |
| P1-lag | `--init v2-best-dev-step-00046459.pt --lr 1e-4 --warmup 500 --epochs 1 --epoch-fraction 0.5 --overlay $J/overlay-lag30 --microbatch 7168 --seed 2026101802 --max-gpu-gb 32` | ≈1.2 h + ≈0.4 h dev |

P1-cap's schedule is the full 6-epoch cosine, so its epoch-1 dev EMA joint NLL compares like-for-like with v2's
0.28237 (seed 22, step 7744) and the run can be resumed to 6 epochs with `--resume`. Pass: ≤ 0.2774.
Launch through `bot/detach.sh` + `bot/exit/cpu_job.sh 4 nice -n 15 ...`; GPU only in a window the BOT LEAD arranges.

The block loader uses `--block-shuffle --shuffle-buffer-gb 20 --workers 1` (default OFF;
buffer limit 24 GiB; one prefetch thread, or `--workers 0` synchronously). Whole perspectives
are read in physical order into one bounded raw buffer, then T11's selected rows are shuffled
within each chunk. Source mmap pages are released every 64 MiB during sequential copies.
The row set, feature builder, label/mask/overlay logic, and wait weights are unchanged.
Complete epochs (`--epoch-fraction 1`) are required. The buffer size is a checkpoint pin;
resume must retain it, the seed, and all scientific arguments. Chunk-local shuffling changes
batch membership relative to global IID shuffling. Tests: `python -m pytest imitation/hp1 -q`.
