# Hog 2.6 joint action-value CUDA handoff

Date: 2026-09-01

## Immutable package

- source commit: `7a3aee4c`
- archive: `/private/tmp/clasher-hog26-joint-q-cuda-7a3aee4c.tar.gz`
- archive SHA-256:
  `f73206f90f6ece015597146e3411db0008c376f7b909cf5799619e37cb65b166`
- size: 79 MiB

The archive contains the exact committed tree plus the three untracked selected
initializer checkpoints.  It excludes the dirty desktop checkout and historical
untracked datasets/reports.

## Pod setup

Use one CUDA GPU with enough local disk for the extracted repository and
checkpoints.  H100/H200/A6000 are supported by the source; H100/H200 is preferred
for the campaign.  CUDA Graph execution is default and fail-closed on CUDA.

```bash
mkdir -p ~/clasher-joint-q
tar -xzf ~/clasher-hog26-joint-q-cuda-7a3aee4c.tar.gz -C ~/clasher-joint-q
cd ~/clasher-joint-q
uv sync --frozen --python 3.12
nvidia-smi
uv run python - <<'PY'
import torch
assert torch.cuda.is_available()
print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name())
PY
```

Copy the archive to the pod before extraction and verify its SHA-256 there.

## Three-seed device screen

```bash
cd ~/clasher-joint-q
OUTPUT_ROOT=$PWD/reports/hog26_joint_q_cuda_smoke \
UPDATES=1 \
PYTHON_BIN=$PWD/.venv/bin/python \
scripts/run_hog26_joint_action_value_cuda_three_seed.sh
```

The driver fails closed unless every child:

- uses `execution_mode=cuda-graph`;
- has zero shared-initializer tensor mismatches;
- has exactly 14 candidate-only action-value entries;
- produces finite positive candidate Q loss;
- keeps the control Q loss/gate exactly zero;
- retains candidate/control throughput ratio at least 0.95.

Inspect:

```bash
python -m json.tool reports/hog26_joint_q_cuda_smoke/summary.json
sha256sum -c <(awk '{print $1 "  reports/hog26_joint_q_cuda_smoke/summary.json"}' \
  reports/hog26_joint_q_cuda_smoke/summary.sha256)
```

Do not run the pilot if the device screen rejects.

## Five-update pilot

Only after all three one-update screens pass:

```bash
cd ~/clasher-joint-q
OUTPUT_ROOT=$PWD/reports/hog26_joint_q_cuda_u5 \
UPDATES=5 \
PYTHON_BIN=$PWD/.venv/bin/python \
scripts/run_hog26_joint_action_value_cuda_three_seed.sh
```

Copy both report roots and all final checkpoints off the pod with SHA-256 hashes
before terminating compute.  The five-update result is a development pilot only;
it still requires deterministic collapse and seven-opponent breadth screens.

## Current external state

At package time Prime Intellect had no running pod and wallet balance -$17.23.
The authorized school host timed out on SSH.  No CUDA smoke has run on this source
commit, and no historical CUDA rate is attributed to it.
