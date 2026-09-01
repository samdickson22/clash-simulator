# Hog 2.6 spatial-teacher CUDA handoff

Date: 2026-09-01

## Immutable package

- source commit: `e8c7adbb537d8fec0179382841db8a9c95c2422f`
- archive: `/private/tmp/clasher-hog26-spatial-u20-cuda-e8c7adbb.tar.gz`
- archive SHA-256:
  `b4545aafc82e0f9031b646d1278dbdfdab1582f82d26444f3c0d3a3014473da2`
- size: 84 MiB

The root-level `PACKAGE_SOURCE_COMMIT` identifies the extracted source.  The
archive contains only the committed source plus the exact initializer and
spatial-teacher update-20 checkpoints.

## Setup

```bash
mkdir -p ~/clasher-spatial-gate
tar -xzf ~/clasher-hog26-spatial-u20-cuda-e8c7adbb.tar.gz \
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
random in one resident mixed-league batch per arm, four games per opponent and
arm: 56 games.  It fails closed unless:

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
