# TV Royale GH200 throughput audit — 2026-08-18

## Machine and boundary

Prime Intellect/Lambda on-demand `gpu_1x_gh200`:

- NVIDIA GH200, 96 GiB dedicated GPU memory;
- 64 physical Neoverse-V2 aarch64 cores;
- 432 GiB advertised memory (525 GiB visible unified/host memory);
- 4 TiB local disk; and
- $2.29/hour at the time of the audit.

The workload is the exact retained 320.353-second `hTG8dM4KtM4` source,
sampled at 10 Hz into 3,204 semantic frames. The source SHA-256 is
`89817c51cb83689e210b19b41444be6928483c915c5582b5ad144f05f00b4d5b`.

This is currently a throughput proof, not a semantic promotion. The Lambda
host image supplies CUDA Torch 2.7.0/torchvision 0.22.0 on aarch64, while the
accepted x86 smoke pins Torch 2.10.0/torchvision 0.25.0. The GH run differed
by two borderline detector classifications (one extra Bat Evolution and one
fewer Lumberjack), so its structured artifacts must remain quarantined until
the exact/new runtime gate passes.

## Pipeline changes under test

1. Exact PIL interpolation is retained, but equal-shaped HUD crops are resized
   in an eight-thread pool and tensor conversion/normalization is batched.
2. The tensor given to CUDA is contiguous NCHW. This was required for exact
   equality to the accepted x86 smoke.
3. Raw actor trajectories are deferred. The following clock stage already
   discards them, and the public-mask stage deterministically rebuilds actor
   projections from the neutral sequence. This avoids serializing about
   59 MB of redundant uncompressed JSON per match.
4. FFmpeg 8.1.2 is used instead of Ubuntu 22.04's FFmpeg 4.4. The exact
   decode/scale probe improved from roughly 45 seconds to 17.26 seconds.

## Single-worker result

With FFmpeg 8.1.2, batched-PIL preprocessing, and deferred raw actors:

- semantic wall: 58.573 seconds;
- rate: 61.461 games/hour;
- HUD/card stage: approximately 15 seconds (239.16 HUD-limited games/hour);
- detector rate: 122.65 frames/second; and
- all H200-reference HUD validity counts were preserved.

The earlier FFmpeg 4.4 run took 91.253 seconds internally because the decode
wait alone consumed 35.418 seconds.

## Concurrency screen

| Processes | Outer wall | Aggregate games/hour | Mean GPU util | Peak VRAM |
|---|---:|---:|---:|---:|
| 1 | 58.573 s | 61.461 | not sampled | ~3.2 GiB observed |
| 3 | 85.975 s | 125.618 | 55.9% | 9,442 MiB |
| 4 | 104.794 s | 137.412 | 69.5% | 12,590 MiB |
| 6 | 150.545 s | **143.479** | 74.1% | 18,879 MiB |
| 8 | 200.932 s | 143.332 | 71.1% | 25,171 MiB |

Six workers are the verified optimum. Eight saturates the GPU at points but
adds queueing and is fractionally slower in aggregate. Every worker in every
completed arm preserved identical aggregate HUD counts and the same 25,804
typed-identity count under the GH runtime.

At 143.479 games/hour, 1,000 average-length games are approximately 6.97
hours of semantic extraction, or about $15.96 of GH200 time before acquisition,
clock, mask, verification, retries, and storage overhead. This is an
extrapolation from one repeated source, not a completed 1,000-game run.

## GPU-native HUD finding

The fully tensorized resize/normalize path remains much faster than PIL. On the
x86 H200 it reduced HUD work from 64.139 to 5.964 seconds and full semantics
from 116.272 to 60.121 seconds. It preserved the candidate identity for every
one of 19,404 rows accepted by both preprocessors, but changed the confidence
boundary:

- reference: 19,587 valid card rows;
- tensor: 19,812 valid card rows;
- gained valid: 408;
- lost valid: 183.

On 107 manually reviewed play events, the reference action extractor produced
35 correct identities from 40 predictions (87.5% precision, 63.64% recall).
The uncalibrated tensor path produced 35/41 (85.37% precision, same recall).
A same-replay threshold sweep reached 37/43 (86.05% precision, 67.27% recall),
but this is diagnostic overfitting and is not promoted. The tensor path needs a
replay-disjoint confidence/classifier calibration gate.

## Decision

- Prefer the 64-vCPU GH200 shape over the 44-vCPU H200 for this mixed
  detector/semantic pipeline.
- Run six concurrent videos, batch 16, eight PIL workers per process.
- Keep the all-tensor HUD backend experimental until replay-disjoint visual
  labels show no precision regression.
- Require exact/new CUDA Torch runtime parity before treating GH structured
  outputs as training data.
- The next implementation target is a dedicated current-client HUD classifier
  with native tensor preprocessing, followed by neutral-state plus actor-overlay
  storage to eliminate final actor JSON duplication.

## Public-entity hygiene follow-up

The accepted H200 neutral sequence contained 89,013 serialized detections, but
52,252 were detector support/UI primitives: HP bars, level text, tower bars,
elixir UI, emotes, or evolution icons. These remain available internally for
HP association, but the extractor now excludes them from policy-facing public
entities. Deployment-marker `clock` detections remain public/offline event cues.

An exhaustive in-memory replay over all 3,204 neutral states and both actors
proved that filtering those 52,252 rows changed 0/6,408 public action masks.
Both mask streams retained SHA-256
`f05955dc361f20d6cb8781d65885b5565c26a31ec782d757a8ce39210ef87175`.
This reduces entity noise and serialization without changing legal actions.
