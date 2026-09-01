# Hog 2.6 spatial-teacher CUDA handoff

Date: 2026-09-01

## Immutable package

- source commit: `68fa36af7dc198da6561a4c9266f1ccb13e5bae2`
- archive: `/private/tmp/clasher-hog26-spatial-u20-cuda-68fa36af.tar.gz`
- archive SHA-256:
  `1b6c4f2426ffe9c8c1e81e56f226e68b77a9bc90c8528dd2ecab43a901f6587c`
- size: 84 MiB

The root-level `PACKAGE_SOURCE_COMMIT` identifies the extracted source.  The
archive contains only the committed source plus the exact initializer and
spatial-teacher update-20 checkpoints.

## Setup

```bash
mkdir -p ~/clasher-spatial-gate
tar -xzf ~/clasher-hog26-spatial-u20-cuda-68fa36af.tar.gz \
  -C ~/clasher-spatial-gate
cd ~/clasher-spatial-gate
cat PACKAGE_SOURCE_COMMIT
uv sync --frozen --python 3.12
nvidia-smi
```

Verify the transferred archive SHA-256 before extraction.

## Frozen CUDA Graph gate

```bash
cd ~/clasher-spatial-gate
OUTPUT_ROOT=$PWD/reports/hog26_spatial_teacher_cuda_gate \
PYTHON_BIN=$PWD/.venv/bin/python \
scripts/run_hog26_spatial_teacher_cuda_gate.sh
```

This evaluates initializer versus candidate against all six strategy bots plus
random, four games per opponent and arm: 56 games.  It fails closed unless:

- both checkpoint SHA-256 values match the predeclared identities;
- every evaluation row reports CUDA Graph execution;
- candidate aggregate outcome score is strictly higher;
- at least two opponent buckets improve;
- no opponent bucket regresses;
- every candidate placement rate remains in `[0.05, 0.35]`.

A pass writes `EXPANDED_EVALUATION_REQUIRED`; it does not promote the candidate.
Copy the complete report root off the host before termination.

## Local evidence boundary

The candidate improved the Python development breadth screen but tied the
initializer 0-4 in the matched Simple/MPS transfer screen.  Therefore CUDA
Simple evidence is mandatory.  No historical CUDA throughput or gameplay claim
is attributed to this package.
