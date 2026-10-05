# TV Royale YouTube CUDA extraction package — 2026-08-17

## Status

The deterministic H100/H200 package is implemented but has **not** completed a
CUDA smoke run. No H100 or H200 throughput is claimed.

The portable Linux clock provider is pinned at
`tools/recognize_public_clock.py`, SHA-256
`fd4975980ee960e98d490b5bab8d84ee3999c8c7278cc8421051b9ec15fba5a7`.
Its precision-v2 exact one-video interface and merger smoke passed, so the
explicit H200 one-video smoke is unblocked. Replay-disjoint observed accepted
accuracy is now 57/57 after a calibration-only support-floor rejection rule,
but native 886/888 layouts remain fail-closed. Bulk mode therefore remains
hard-blocked in code and still requires the CUDA smoke's exact
`SMOKE_GATE.json` plus direct native-layout evidence.

Mask contract v2 is mandatory throughout. Pin files, smoke gates, completion
markers, and shard manifests use v2 schemas. Contract-v1 shards and smoke gates
are rejected rather than upgraded or mixed.

## Package

- launcher: `scripts/run_tv_royale_youtube_cuda_shard.py`;
- bounded cross-platform acquisition: `scripts/acquire_tv_royale_youtube_fullmatch.py`;
- exact detector benchmark: `scripts/perf/benchmark_tv_royale_youtube_detector.py`;
- semantic extractor: `scripts/extract_tv_royale_youtube_fullmatch.py`;
- clock-anchor merger: `scripts/apply_tv_royale_youtube_clock_adapter.py`;
- contract-v2 mask builder: `scripts/build_tv_royale_youtube_fullmatch_masks.py`;
- independent verifier: `scripts/verify_tv_royale_youtube_fullmatch_contract.py`;
- machine-readable pins: `datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json`.

The pins freeze Python/package versions; `uv.lock` and `pyproject.toml`; both
detector checkpoints; MobileNetV3 weights; stable vocabulary; mask builder and
contract implementation; acquisition/extractor/benchmark/verifier/launcher
source; YoutubeExplode wrapper/project; and the two external source revisions.
The lock includes the hashes of the Linux x86-64 PyTorch/CUDA dependency
wheels. Runtime preflight rejects any mismatch.

## Determinism, resume, and publication

Videos are assigned by the first 64 bits of
`SHA256("<seed>:<video_id>") modulo shard_count`, then processed in video-ID
order. Only explicitly public rows enter a shard.

The downloader queue is hard-bounded to one video per worker. Each source is
limited to 500 MiB, video-only, hashed, fully decoded, and indexed at exact
contiguous 10 Hz output PTS before inference. Scratch contains one active
source/job. Completed scratch is deleted only after the verifier passes and the
completion marker is durable.

Every output artifact is written atomically by its producer. A directory is
publishable only when its atomically written `COMPLETE.json` validates the v2
manifest/report hashes and zero failed gates. `JOB.json` and
`SCRATCH_JOB.json` prevent unrelated or differently pinned state from being
resumed. An interrupted `.publication.partial` is launcher-owned and rebuilt;
completed stages with validated inputs are reused.

Per-stage telemetry records command, return code, wall/user/system time,
platform-normalized peak child RSS bytes, and bounded stdout/stderr tails. The
detector benchmark additionally records device name/class, CUDA/cuDNN, exact
frame count, repeat digests, FPS, and peak allocated VRAM. Measurements are
evidence only; the launcher sets `throughput_claimed=false`.

## Linux clock adapter contract

The pinned executable declares schema `clasher.youtube.clock_adapter.v1` and is
called without a shell:

```text
<clock-adapter>
  --source-video <source.webm>
  --source-manifest <acquisition/manifest.json>
  --output-jsonl <clock_anchors.jsonl>
  --sample-hz 10
  --anchor-stride-frames 5
```

Each JSONL row must have schema `clasher.youtube.clock_anchor.v1`, an exact
stride-aligned `output_pts`, integer `seconds_remaining`, confidence in `(0,1]`,
`raw_text` list, and `current_frame_only=true`. The pinned merger validates the
rows, preserves exact acquisition PTS/time bases and hashes, propagates only
within the same five-frame/half-second window, and leaves missing anchors
invalid. The independent full-contract verifier is run against the final
self-contained publication.

Exact portable-clock evidence on `hTG8dM4KtM4`: 535 anchors; 100% conditional
agreement with the native teacher; 85.87% overall coverage; 81.08% fixed
temporal-holdout coverage; zero monotonic violations. A second invocation
through the packaged argv produced the identical anchor SHA-256
`5495aead8db5290c7c4eba9e5c366b64fee76fedc4ea6f59c240d42d9336f482`.
The merger accepted all anchors and produced 2,675 valid 10 Hz clock frames.
This is one-video temporal holdout evidence, not replay-disjoint validation.

The frozen precision repair was then evaluated on 120 retained frames from ten
replay IDs. A confident Vision teacher supplied 108 labels; the repaired
provider accepted 57 and all 57 were exact. Teacher-conditioned coverage was
52.778%. This passes the observed precision target while preserving the exact
one-video anchor hash, but it does not enable native 886x1920 or 888x1920
inputs. Full evidence is in
`reports/tv_royale_portable_clock_precision_repair_20260817.json`.

## DigitalOcean preflight

The commands below assume the provisioned droplet's non-rotational local NVMe
is already mounted at `/mnt/local-nvme`. They do not format or mount a device.
Verify the mount before writing:

```bash
export CLASHER_REPO=/opt/clasher
export CLASHER_NVME=/mnt/local-nvme
export CLASHER_SCRATCH=$CLASHER_NVME/clasher-scratch
export CLASHER_OUTPUT=$CLASHER_NVME/clasher-output
export CLASHER_CLOCK=$CLASHER_REPO/tools/recognize_public_clock.py
export CLASHER_DOTNET=/usr/share/dotnet/dotnet

findmnt --target "$CLASHER_NVME"
lsblk -d -o NAME,ROTA,TYPE,SIZE,MODEL
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv

cd "$CLASHER_REPO"
uv sync --frozen --python 3.12
"$CLASHER_DOTNET" --version
ffmpeg -version | head -1
ffprobe -version | head -1

install -d -m 0750 "$CLASHER_SCRATCH" "$CLASHER_OUTPUT"
test -x "$CLASHER_CLOCK"
sha256sum "$CLASHER_CLOCK"
```

Verify the already populated provider and the complete pins before launch:

```bash
cd "$CLASHER_REPO"
test "$(sha256sum "$CLASHER_CLOCK" | awk '{print $1}')" = \
  fd4975980ee960e98d490b5bab8d84ee3999c8c7278cc8421051b9ec15fba5a7
PYTHONPATH=src:. uv run python - <<'PY'
from pathlib import Path
from scripts.run_tv_royale_youtube_cuda_shard import validate_pins
validate_pins(
    Path("datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json"),
    repository=Path(".").resolve(),
)
print("pins_ok")
PY
```

The pins file is content-addressed by every smoke/completion record. A
full-channel metadata manifest and replay-disjoint clock report must replace
their current canary/pending entries before a bulk wave.

## DataCrunch / Verda `1H200.141S.44V`

For the first CUDA smoke, use an **on-demand** x86-64 Ubuntu 22 instance of
type `1H200.141S.44V`. Verda lists this shape as one H200 SXM5 with 141 GB
VRAM, 44 CPUs, and 182 GB RAM. The provider supports attaching additional NVMe
volumes when an instance is created; do not infer a mount path from the
instance type. See the provider's [H200 instance specification](https://verda.com/de/blog/nvidia-h200),
[instance setup guide](https://docs.verda.com/cpu-and-gpu-instances/set-up-a-gpu-instance/),
and [volume API contract](https://api.verda.com/v1/docs).

Provision and attach a volume of at least 500 GB through the Verda UI/API, then
discover and verify its actual mount. The commands below are read-only until
`install -d`; replace `/verified/provider/mount` only after correlating
`findmnt` with the attached device shown by `lsblk`:

```bash
uname -m
test "$(uname -m)" = x86_64
cat /etc/os-release
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv

lsblk -b -o NAME,PATH,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,MODEL
findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS

export CLASHER_REPO=/opt/clasher
export CLASHER_NVME=/verified/provider/mount
findmnt --target "$CLASHER_NVME"
volume_bytes=$(df -B1 --output=size "$CLASHER_NVME" | tail -1 | tr -d ' ')
test "$volume_bytes" -ge 500000000000

export CLASHER_SCRATCH=$CLASHER_NVME/clasher-scratch
export CLASHER_OUTPUT=$CLASHER_NVME/clasher-output
export CLASHER_CLOCK=$CLASHER_REPO/tools/recognize_public_clock.py
export CLASHER_DOTNET=/usr/share/dotnet/dotnet
install -d -m 0750 "$CLASHER_SCRATCH" "$CLASHER_OUTPUT"
```

Then use the exact H200 smoke command below. Do not use spot for the first
smoke. Spot becomes eligible only after an on-demand interruption/resume drill
proves that the same pinned job reuses its `JOB.json`/`SCRATCH_JOB.json`,
rebuilds an owned partial safely, and reaches a hash-valid `COMPLETE.json`
without duplicate or mixed-contract output. When later testing spot, explicitly
configure attached-volume discontinuation to keep the volume detached rather
than delete it, and retain the same copy-off/checksum/teardown gates. This
runbook does not create, modify, or discontinue any cloud resource.

## Exact H100 smoke

```bash
cd "$CLASHER_REPO"
PYTHONPATH=src:. uv run python scripts/run_tv_royale_youtube_cuda_shard.py \
  --repository "$CLASHER_REPO" \
  --metadata-manifest datasets/source_metadata/tv_royale_youtube_canary_20260817/manifest.json \
  --pins datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json \
  --scratch-root "$CLASHER_SCRATCH" \
  --output-root "$CLASHER_OUTPUT" \
  --clock-adapter "$CLASHER_CLOCK" \
  --dotnet "$CLASHER_DOTNET" \
  --seed 1064201 --shard-count 1 --shard-index 0 \
  --mode smoke --smoke-video-id hTG8dM4KtM4 \
  --allowed-device-class H100 \
  --batch-size 16 --benchmark-repetitions 3 \
  --max-download-queue 1 --minimum-scratch-free-gib 20
```

## Exact H200 smoke

The workload and gates are identical; only the explicit device allowlist
changes:

```bash
cd "$CLASHER_REPO"
PYTHONPATH=src:. uv run python scripts/run_tv_royale_youtube_cuda_shard.py \
  --repository "$CLASHER_REPO" \
  --metadata-manifest datasets/source_metadata/tv_royale_youtube_canary_20260817/manifest.json \
  --pins datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json \
  --scratch-root "$CLASHER_SCRATCH" \
  --output-root "$CLASHER_OUTPUT" \
  --clock-adapter "$CLASHER_CLOCK" \
  --dotnet "$CLASHER_DOTNET" \
  --seed 1064201 --shard-count 1 --shard-index 0 \
  --mode smoke --smoke-video-id hTG8dM4KtM4 \
  --allowed-device-class H200 \
  --batch-size 16 --benchmark-repetitions 3 \
  --max-download-queue 1 --minimum-scratch-free-gib 20
```

Neither command authorizes scale automatically. A valid
`shard-00000-of-00001/SMOKE_GATE.json` requires exact detector-repeat stability,
the Linux clock publication, contract-v2 nontrivial label-independent masks,
and a zero-failure independent verifier report.

## Explicit post-smoke scale gate

Bulk remains blocked even after a successful one-video H200 smoke. The command
below is the eventual two-shard form, but the launcher rejects it while
`bulk_gate.replay_disjoint_clock_validation` is `pending`. After independent
replay-disjoint clock validation passes, its report SHA must be pinned before
this command becomes eligible. Each worker then gets one shard index and the
same immutable smoke gate; eventual shard-0 form:

```bash
cd "$CLASHER_REPO"
PYTHONPATH=src:. uv run python scripts/run_tv_royale_youtube_cuda_shard.py \
  --repository "$CLASHER_REPO" \
  --metadata-manifest datasets/source_metadata/tv_royale_youtube_canary_20260817/manifest.json \
  --pins datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json \
  --scratch-root "$CLASHER_SCRATCH" \
  --output-root "$CLASHER_OUTPUT" \
  --clock-adapter "$CLASHER_CLOCK" \
  --dotnet "$CLASHER_DOTNET" \
  --seed 1064201 --shard-count 2 --shard-index 0 \
  --mode run \
  --smoke-gate "$CLASHER_OUTPUT/shard-00000-of-00001/SMOKE_GATE.json" \
  --allowed-device-class H100 --allowed-device-class H200 \
  --batch-size 16 --benchmark-repetitions 3 \
  --max-download-queue 1 --minimum-scratch-free-gib 20
```

Run shard 1 separately with `--shard-index 1`. Do not increase shard/GPU count
until the canary shows a sustained prepared-frame queue and greater than 80%
detector utilization. If GPU idle time exceeds 20%, add CPU/HUD or independent
egress capacity instead. These are scale-decision rules, not throughput claims.

## Copy-off and teardown checklist

1. Require every selected video directory to contain a valid `COMPLETE.json`,
   every shard to contain `shard_manifest.json`, and every verifier report to
   have `failed_gates=[]` and mask contract version 2.
2. Record SHA-256 for pins, smoke gate, shard manifests, completion markers,
   v3 manifests, verifier reports, detector benchmarks, and stage telemetry.
3. Copy only completed output to durable storage with a configured credential-
   safe remote; do not place credentials in the command line or logs:

   ```bash
   rclone copy --checksum --transfers 8 "$CLASHER_OUTPUT/" do-spaces:clasher-youtube-cuda/
   rclone check --checksum "$CLASHER_OUTPUT/" do-spaces:clasher-youtube-cuda/
   ```

4. Confirm the remote object count and checksum check succeeded. Preserve the
   populated v2 pins and smoke gate with the outputs.
5. Stop launchers and verify no acquisition/extractor process remains.
6. Remove only the explicit launcher-owned scratch root after copy-off. Scratch
   source videos are then gone; durable structured outputs remain recoverable
   from the checked remote copy. Never delete the repository or output root as
   part of scratch cleanup.
7. Destroy the DigitalOcean droplet only after remote verification. Revoke or
   remove any temporary cloud credential through its normal secret-management
   surface; never print it.

## Local validation

```bash
PYTHONPATH=src:. uv run pytest -q \
  tests/test_acquire_tv_royale_youtube_fullmatch.py \
  tests/test_apply_tv_royale_youtube_clock_adapter.py \
  tests/test_run_tv_royale_youtube_cuda_shard.py \
  tests/test_extract_tv_royale_youtube_fullmatch.py \
  tests/test_build_tv_royale_youtube_fullmatch_masks.py \
  tests/test_verify_tv_royale_youtube_fullmatch_contract.py \
  tests/test_rl_public_action_mask.py

uv run ruff check \
  scripts/acquire_tv_royale_youtube_fullmatch.py \
  scripts/apply_tv_royale_youtube_clock_adapter.py \
  scripts/run_tv_royale_youtube_cuda_shard.py \
  scripts/extract_tv_royale_youtube_fullmatch.py \
  scripts/perf/benchmark_tv_royale_youtube_detector.py \
  tests/test_acquire_tv_royale_youtube_fullmatch.py \
  tests/test_apply_tv_royale_youtube_clock_adapter.py \
  tests/test_run_tv_royale_youtube_cuda_shard.py

PYTHONPATH=src:. uv run mypy --follow-imports skip \
  --disable-error-code no-any-return --disable-error-code var-annotated \
  tools/recognize_public_clock.py \
  scripts/acquire_tv_royale_youtube_fullmatch.py \
  scripts/apply_tv_royale_youtube_clock_adapter.py \
  scripts/run_tv_royale_youtube_cuda_shard.py \
  scripts/perf/benchmark_tv_royale_youtube_detector.py

git diff --check -- \
  scripts/acquire_tv_royale_youtube_fullmatch.py \
  scripts/apply_tv_royale_youtube_clock_adapter.py \
  scripts/run_tv_royale_youtube_cuda_shard.py \
  scripts/extract_tv_royale_youtube_fullmatch.py \
  scripts/perf/benchmark_tv_royale_youtube_detector.py \
  tests/test_acquire_tv_royale_youtube_fullmatch.py \
  tests/test_apply_tv_royale_youtube_clock_adapter.py \
  tests/test_run_tv_royale_youtube_cuda_shard.py \
  datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json \
  reports/tv_royale_youtube_cuda_package_20260817.md
```
