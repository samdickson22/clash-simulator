# T0 GPU training environment receipt

Measured 2026-10-07 on 127x07, 127x04 and 127x08. **PASS for eager CUDA training on all three hosts. `torch.compile`/Inductor fails on all three.** No real models were trained. 127x05 only edited files, transferred small source snapshots and collected receipts. No work was run on the Mac or 127x01; the latter was left to the hub rebuild worker. No excluded fleet hosts were contacted.

The environment is `/mpac/sdicks02/envs/clasher-gpu` on each GPU host. It is independent of the repository `.venv`, `pyproject.toml` and `uv.lock`. Setup on 127x04/08 reran the pinned installer rather than copying the environment. All downloads, Python installations, caches, logs and synthetic data live under `/mpac/sdicks02`. Environment size on 127x07: 5.7 GiB (`du -sh`, excluding separate Python installation and package caches).

## Versions and selection

| Component | Version |
|---|---|
| Python | 3.12.12, uv managed |
| uv used | 0.12.23 |
| Torch / CUDA runtime | 2.7.1+cu118 / 11.8 |
| torchvision | 0.22.1+cu118 |
| Ultralytics | 8.1.24, project pin |
| NumPy / OpenCV | 1.26.4 / 4.10.0.84 |
| cuDNN / Triton | 9.1.0.70 / 3.3.1 |
| NVIDIA driver | 470.256.02 on all three |
| GPU / capability | RTX A6000, 48 GB / sm_86 |
| OS ABI | Ubuntu 20.04, glibc 2.31; no system nvcc |

The [official cu118 wheel index](https://download.pytorch.org/whl/cu118/torch/) lists 2.7.1 as its newest Linux CPython 3.12 build, with a manylinux_2_28 wheel compatible with glibc 2.31. [PyTorch's version instructions](https://pytorch.org/get-started/previous-versions/) match torch 2.7.1 to torchvision 0.22.1. This is the newest published cu118 wheel verified here, not a claim about custom source builds.

`nvidia-smi` advertises CUDA 11.4 because of the installed driver; the wheel supplies CUDA 11.8 runtime libraries. [NVIDIA's minor-version compatibility rules](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) permit CUDA 11.x on Linux drivers at least 450.80.02, with restrictions for newer features and PTX. Actual matmul, convolution, attention, backward passes and detection training passed below. Compilation did not, so CUDA availability alone is not the acceptance criterion.

`gpu_env.sh` pins Python and all 49 Python/runtime packages, including the NVIDIA libraries. It uses PyPI plus `https://download.pytorch.org/whl/cu118`; explicit `+cu118` pins prevent a CUDA 12 wheel being selected. It searches both trusted indexes because the Torch mirror contains older copies of some PyPI dependencies. NumPy stays at 1.26.4 for the old perception stack, and OpenCV stays at 4.10.0.84 to avoid a dependency forcing NumPy 2.

## Per-host measurements

Every initial `who` was empty, GPU compute processes were absent, and `/mpac` had about 1.7 TiB free. The checker runs at nice 10, checks `who` before each probe and skips an occupied host. Each probe has a separate process and a 120-second timeout. Only its own subprocess group can be terminated on timeout.

| Host | Required checks | FP32 TFLOPS | TF32 TFLOPS | bf16 TFLOPS | ResNet step ms | Transformer AMP step ms | Loader images/s | YOLO epoch s | YOLO complete train/validate/save s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 127x07 | PASS, including source import recheck | 24.12 | 62.14 | 105.53 | 10.18 | 24.24 | 7,178 | 1.796 | 5.758 |
| 127x04 | PASS, including source import recheck | 23.67 | 61.56 | 104.41 | 9.81 | 24.40 | 8,520 | 1.742 | 5.497 |
| 127x08 | PASS, including source import recheck | 23.75 | 61.51 | 104.95 | 9.59 | 23.95 | 8,400 | 1.722 | 5.213 |

On every host: `torch.cuda.is_available()` was true, the device was `NVIDIA RTX A6000`, bf16 support reported true, and torchvision CUDA NMS passed. ResNet and transformer losses were finite and parameters changed. YOLO finished validation and wrote/reloaded both `last.pt` and `best.pt`.

| Probe | Peak allocated MiB, every host | Peak reserved MiB, every host |
|---|---:|---:|
| Each 8192-square matmul | 1,056.0 | 1,058.0 |
| ResNet18 training | 346.9 | 404.0 |
| Six-layer transformer AMP | 446.8 | 486.0 |
| 16-worker DataLoader | 9.2 | 20.0 |
| YOLOv8s train + validation | 612.5 | 666.0 |

These are `torch.cuda.max_memory_allocated/reserved()` per isolated probe. They exclude driver/context memory and allocations outside Torch's allocator. Initial/final `nvidia-smi` memory readings are also in each receipt; desktop baseline was 16 MiB on 04/07 and 104 MiB on 08.

Benchmark definitions:

- Matmul: FP32 inputs, 8192×8192, three warmups and ten measured multiplies; CUDA-event timing; `2*N^3*steps/seconds` TFLOPS. FP32 disables TF32; TF32 enables it; bf16 uses autocast and produces bf16 output. Sampled relative L2 errors against CPU float64 were 1.25e-6 / 2.48e-4 / 2.94e-3 respectively on all hosts. The measurements are brief throughput smoke tests.
- Convolution: ResNet18, 11.18M parameters, batch 16, 128×128, FP32 AdamW; three warmups and ten measured forward/backward/update steps. Loss fell from about 0.0051 to 0.00030 on the repeated synthetic batch.
- Transformer: six encoder layers, d=512, eight heads, FFN=2048, 18.91M parameters, batch 8, sequence 128. FP16 autocast with GradScaler and AdamW; three warmups plus ten measured steps. Loss fell from 1.841 to 1.531.
- DataLoader: 16 workers, batch 32, random uint8 RGB 224×224 images, pinned memory and asynchronous H2D copies. Eight warmup batches, then 64 measured batches/2,048 images. Startup plus warmups: 1.684 / 1.696 / 1.518 s on 07/04/08. This exercises generated data and IPC/H2D, not dataset disk decoding; it is not a prediction of v4 video loading speed.
- YOLOv8s: 11.14M parameters; 24 generated training images and eight validation images, one class, 320×320, batch four, two workers, AdamW, one epoch. Initialized from YAML, no pretrained weights, no external downloads, AMP disabled as in the existing v3 perception trainer. Separate transformer and bf16 probes cover AMP. Epoch timing covers six training batches; complete timing includes setup, validation, save and checkpoint reload. Dummy mAP is zero and carries no quality claim.

## Limitations and T6/T7 handoff

1. **`torch.compile` fails on 04/07/08:** the default GPU backend (`inductor`, Triton 3.3.1) reports `Triton Error [CUDA]: device kernel image is invalid` during a pointwise forward compilation. This is consistent with the old driver's limitations but the exact binary/PTX cause was not isolated. Compile attempt process times: 9.69 / 8.87 / 8.49 s on 07/04/08. Use eager execution; no fallback, driver change, Triton downgrade or compiler repair was attempted.
2. **Old Ultralytics checkpoint loading:** PyTorch 2.7 defaults `torch.load` to weights-only. Ultralytics 8.1.24 loads full modules when stripping and validating its own checkpoints. Set `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` for those trusted local files. `gpu_check.py` sets it itself; activation alone does not. This leaves the v3 trainer's explicit `weights_only=True` call intact. Do not apply this workaround to untrusted checkpoints.
3. **Existing entry points need a CUDA port for T6:** `scripts/train_l1_stream_v3.py` hard-codes `.to('mps')`, `train_l1_events_v2.py` also hard-codes MPS, and `train_l1_perception.py` checks MPS availability and supplies `device='mps'`. Imports were verified; these scripts cannot train unmodified on Linux. The coordinator must authorize/implement a device parameter while preserving the v3 architecture, losses, splits and initialization. This task made no source changes.
4. **Remote source freshness:** 07 and 08 initially lacked `train_l1_stream_v3.py`; 04 had it by check time. Current `src/` and `scripts/` from 127x05 were copied to `/mpac/sdicks02/tmp/clasher-gpu-import-source/` solely for read-only import checks on every host. `-B` prevented bytecode writes. No real data, renderer, simulator engine, current v3 weights, or training entry-point execution was tested. Reconcile the training checkout before T6/T7.
5. No NCCL multi-node, custom CUDA extensions, prolonged thermals, YOLO AMP, full-size 448×832 batches or real-data throughput validation. T0 does not validate the design's training-hour estimates. T6 awaits the v4 data converter/Phase A; T7 awaits T6 and Phase A. Independent single-GPU sweeps fit this environment; cross-host distributed training remains untested.

## Recreate, activate and run

From 127x05, these commands stage only the two new scripts and build on a permitted GPU host. Repeat with `127x04` and `127x08`. The installer rejects other hosts and occupied machines, locks setup, and runs uv under nice. It synchronizes only the standalone env; do not run it during an active training job.

```bash
cd /mpac/sdicks02/repos/clasher
fleet=reports/strategy_council_20260928/fleet
ssh 127x07 'who; mkdir -p /mpac/sdicks02/tmp'
scp "$fleet/gpu_env.sh" "$fleet/gpu_check.py" 127x07:/mpac/sdicks02/tmp/
ssh 127x07 'nice -n 10 bash /mpac/sdicks02/tmp/gpu_env.sh'
```

On the GPU host:

```bash
source /mpac/sdicks02/env.sh
source /mpac/sdicks02/envs/clasher-gpu/bin/activate
export TMPDIR=/mpac/sdicks02/tmp PYTHONDONTWRITEBYTECODE=1
export CUDA_CACHE_PATH=/mpac/sdicks02/cache/cuda
export TRITON_CACHE_DIR=/mpac/sdicks02/cache/triton
export TORCHINDUCTOR_CACHE_DIR=/mpac/sdicks02/cache/torchinductor
export MPLCONFIGDIR=/mpac/sdicks02/cache/matplotlib
export YOLO_CONFIG_DIR=/mpac/sdicks02/tmp/clasher-gpu-yolo-config
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
export PYTHONPATH=/mpac/sdicks02/repos/clasher/src:/mpac/sdicks02/repos/clasher/scripts

# Use the actual training checkout after it is reconciled.
# For the current import snapshot from this receipt:
export CLASHER_ROOT=/mpac/sdicks02/tmp/clasher-gpu-import-source
nice -n 10 python -B /mpac/sdicks02/tmp/gpu_check.py \
  --output /mpac/sdicks02/tmp/clasher-gpu-check-rerun.json
```

The checker prints one JSON object to stdout and diagnostics to stderr. It returns nonzero for a failed/skipped required probe; compile failure is recorded but does not fail the eager-training gate. `--only imports` rechecks dependencies without GPU benchmarks; `--only yolo` runs just the synthetic training epoch.

Detached single-GPU training smoke, using the existing `fleet_run.sh` helper (confirmed identical on 127x07 and 127x05):

```bash
ssh 127x07 'bash -s' <<'REMOTE'
set -euo pipefail
test -z "$(who)" || { echo "Host occupied" >&2; exit 75; }
base=/mpac/sdicks02
root=$base/repos/clasher
label=t0-gpu-check-$(date -u +%Y%m%dT%H%M%SZ)
bash "$root/reports/strategy_council_20260928/fleet/fleet_run.sh" "$label" \
  env CLASHER_ROOT="$base/tmp/clasher-gpu-import-source" \
  TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 \
  "$base/envs/clasher-gpu/bin/python" -B "$base/tmp/gpu_check.py" \
  --output "$base/tmp/$label.json"
echo "receipt=$base/tmp/$label.json"
echo "log=$base/jobs/clasher/$label.log exit=$base/jobs/clasher/$label.exit"
REMOTE
```

`fleet_run.sh` uses `nohup setsid nice -n 10`, a per-label `flock`, a PID record, `/usr/bin/time -v`, and an atomic numeric exit receipt. Inspect the `.log`, `.exit` and JSON; launch acceptance is not job success. A completed label is not rerun, so use a fresh label for each check. Keep outputs resumable: detached execution is not a guarantee against host/session restarts. Use one GPU job per host. For T6/T7, substitute the approved CUDA trainer and its arguments for `gpu_check.py`, use the actual reconciled repo as `CLASHER_ROOT`, and retain these cache exports (plus the helper's thread limits and explicit env interpreter). The original MPS scripts are not ready substitutes.

The helper was exercised on 127x07 with the final checker and `--only imports`, label `t0-gpu-final-imports-20261007`. Its JSON reported import PASS at nice 10, and `/mpac/sdicks02/jobs/clasher/t0-gpu-final-imports-20261007.exit` contained `0`. This validates launch/log/exit handling without repeating GPU benchmarks. The final installer was also rerun on 127x07 and found the 49-package environment already synchronized; all three hosts' final package freezes matched.

## Receipts and artifacts

On each GPU host, raw receipts and stderr logs are `/mpac/sdicks02/tmp/clasher-gpu-<host>.json` and `.log`. Supplemental current-source imports are `/mpac/sdicks02/tmp/clasher-gpu-<host>-imports.json`. Initial full receipts on 07/08 record the missing-source import failure; supplemental receipts establish the corrected import result without repeating successful GPU probes.

Copies on 127x05 are under `/mpac/sdicks02/tmp/clasher-gpu-receipts/`. Each `clasher-gpu-<host>-verified.json` explicitly composes the original GPU suite and supplemental import receipt, retains the initial import result, checks identical package versions, and reports `full_required_suite_passed=true`; `compile.status` remains `fail`. Raw receipts are retained alongside it. Full Python traceback and per-probe process times are in the JSON.

Synthetic datasets/checkpoints remain on their originating hosts:

- 127x07: `/mpac/sdicks02/tmp/clasher-gpu-yolo-4aliol4m/`
- 127x04: `/mpac/sdicks02/tmp/clasher-gpu-yolo-odjmfr51/`
- 127x08: `/mpac/sdicks02/tmp/clasher-gpu-yolo-hgt1gyz6/`

These artifacts demonstrate training mechanics only and must not enter real training datasets or be used as perception weights.

## Mac export expectation (documentation only)

Design §2.3/§2.8 and T7 expect training and independent sweeps on fleet A6000s, then transfer of selected real weights/configs to the Mac. Export there in a separately validated Mac environment to CoreML **mlprogram**, fp16, targeting ANE execution; MPS remains the inference fallback. The ≤12M-parameter shared backbone covers bodies/HUD on the 448×832 arena crop, with a separate ≤4M temporal event head using cached features. Temporal/irregular-time conversion support must be validated rather than assumed.

The Mac benchmark must run with the emulator and satisfy perception p50 ≤25 ms/p95 ≤40 ms and the v4 loop gates; offline GPU throughput cannot certify those budgets. Selection uses validation, followed by heldout §5.1 tests. T6 is the v3 control on v4 data; T7 adds the v4 perception model and CoreML packages. No CoreML tools were installed in the fleet env, and no Mac command, export or benchmark was run for T0. The current task's host restrictions supersede DESIGN.md's stale references to 127x02.
