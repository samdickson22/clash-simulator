# TV Royale H200 extraction and saturation audit — 2026-08-18

## Scope

This audit uses the exact retained 320.353-second `hTG8dM4KtM4` source at
10 Hz (3,204 frames), the two pinned KataCR detectors, the pinned
MobileNetV3-Small card embedding weights, CUDA 12, and a single NVIDIA H200
141 GB pod with 44 vCPUs. It measures the current extraction code; it does not
claim channel-wide accuracy or authorize bulk extraction.

The accepted H200 smoke remains pinned by
`datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json` (SHA-256
`76a6e326d63ea119dbd4c9e6d6cc1309d33dd1893c53be1a39de33e7ffcc740c`).
The optimized source is intentionally not folded into that historical pin.

## Exact smoke result

- Complete marker SHA-256:
  `6e9100254a197b6fd4ea73595a36398ff06d2ca18a31a3a71d1b98751be3142b`.
- Three detector repetitions: 100.832, 104.845, and 105.546 frames/s.
- All detector repetitions produced the same digest:
  `8b1f871bbaacb4ceae7c7201c5e59adcf4ca33350aa829a3cc6972c0a85918e9`.
- Full semantic extraction: 116.272 seconds, or 30.962 games/hour before
  download and downstream clock/mask verification.
- The single semantic extractor spent 64.139 seconds in HUD/card matching and
  26.084 seconds in the arena detectors.

The previously cited local 80–118 frames/s number was decode/index throughput,
not detector throughput. The matched local detector measurement was 8.72
frames/s, so the H200 detector is roughly 12x faster, not 1.25x.

## Detector-only saturation

The detector benchmark was byte-stable across every accepted arm.

| Shape | Aggregate detector frames/s | Aggregate end-to-end frames/s | Mean GPU util | Peak VRAM |
|---|---:|---:|---:|---:|
| 1 process, batch 16 | ~103.7 | — | — | 2.27 GB allocated |
| 2 processes, batch 16 | ~164.4 | 101.6 | 46.8% | 6,011 MiB |
| 4 processes, batch 16 | ~186.2 | 138.1 | 71.0% | 12,018 MiB |
| 8 processes, batch 16 | ~193.2 | 162.0 | 83.3% | 24,034 MiB |
| 12 processes, batch 16 | ~194.8 | 160.8 | 80.8% | 36,049 MiB |

Eight batch-16 detector workers are the accepted detector-only shape. Twelve
workers add no useful throughput and reduce the CPU available to semantics.
Increasing one stream to batches 32–128 did not materially improve detector
throughput; batches 256 and 512 were stopped after the trend was negative.

## Rejected full-pipeline shape

Eight unoptimized full extractors were stopped after 1,034.963 seconds. They
had consumed only about 10% of the raw frame stream, all 44 vCPUs were busy,
and the H200 was idle at 0% utilization. Extrapolated completion would have
taken roughly 2.8 hours. This is a bounded rejected screen, not a completed
throughput measurement.

## HUD preprocessing A/B

The reference path constructs one PIL object and applies torchvision transforms
separately for every HUD crop: 32,040 crops per match.

An all-tensor resize/normalize arm reduced HUD time from 64.139 to 5.964
seconds and full semantic wall time from 116.272 to 60.121 seconds. It was
rejected: PIL and tensor interpolation changed 1,910/32,040 candidate-or-valid
rows and 591 validity decisions.

The accepted arm keeps the exact PIL resize/crop interpolation, performs those
operations in an eight-thread pool, batches conversion/normalization, and
forces contiguous NCHW memory before CUDA inference. Its full-match result:

| Metric | Reference | Accepted batched PIL | Change |
|---|---:|---:|---:|
| Full semantic wall | 116.272 s | 88.251 s | -24.11% |
| End-to-end semantic rate | 30.962 games/h | 40.793 games/h | +31.75% |
| HUD/card matching | 64.139 s | 35.260 s | -45.03% |
| Detector time | 26.084 s | 26.215 s | noise |

Row-level comparison against the accepted smoke was exact for:

- 32,040/32,040 HUD card rows;
- 6,408/6,408 elixir rows;
- 3,204/3,204 entity lists; and
- 3,204/3,204 deployment-marker lists.

The accepted arm also preserved all aggregate counts: 89,013 detections,
17,312 HP observations, seven complete play events, and every hand/Next/HUD
validity count.

Sixteen PIL workers were slower than eight (94.95 versus 88.25 seconds), so the
production per-process default remains eight.

## Full-pipeline concurrency

| Semantic processes | Outer wall | Aggregate games/hour | Mean GPU util | Peak VRAM |
|---|---:|---:|---:|---:|
| 1 | 88.251 s | 40.793 | not sampled | ~3.1 GiB observed |
| 3 | 200.267 s | 53.928 | 19.4% | 9,356 MiB |
| 4 | 249.038 s | 57.822 | 28.7% | 12,474 MiB |
| 5 | 314.930 s | 57.156 | 26.9% | 15,592 MiB |

All completed concurrent workers preserved the same semantic coverage counts.
The remaining bottleneck is CPU-side PIL/HUD preparation and serialization,
not H200 memory or detector compute.

## Code changes and gates

- `scripts/extract_tv_royale_youtube_fullmatch.py` adds explicit
  `pil`, `pil-batched`, and experimental `tensor` preprocessing backends. The
  default remains the historical `pil`; the CUDA launcher selects
  `pil-batched` explicitly.
- `scripts/run_tv_royale_youtube_cuda_shard.py` selects the accepted backend and
  preserves virtualenv interpreter symlinks instead of resolving them to a base
  Python without site-packages.
- Focused extractor/launcher tests: 13 passed.
- Ruff: clean.
- Mypy: clean for both source files.

## Decision

Use four concurrent extraction shards per 44-vCPU H200 pod, batch 16, eight PIL
preprocess workers per shard. Five workers are slightly slower in aggregate;
do not use the tensor interpolation arm and do not run eight full extractors.

The next material speedup requires separating the shared batched detector from
per-video HUD/state workers or replacing repeated JSON actor-state duplication;
larger detector batches and more VRAM alone will not solve the bottleneck.
