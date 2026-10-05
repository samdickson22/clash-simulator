# TV Royale YouTube extraction throughput audit — 2026-08-17

## Bottom line

The full YouTube semantic pipeline now has a one-match measured rate:
9.735 semantic games/hour, or 9.541 games/hour including the measured source
download, on the 12-core M4 Pro. The independently verified 320.353-second
match produced 3,204 neutral snapshots, 1,602 rows for each actor, and 7
visually plausible filtered card-plus-deployment-tile events. This proves the
end-to-end transport,
PTS, schema, dense detector, both-HUD, clock, projection, hash, and fail-closed
causality path. It is a one-match smoke proof, not a quality/yield benchmark.

The older sparse Hugging Face public-v2 pipeline completed 1,000 games at
95.835 games/hour. That workload selected a mean 143 detector frames/game from
nominal 10 FPS sources; it did not decode both spectator HUDs or produce dense
entities, projectiles, effects, and two actor trajectories.

For the YouTube source, acquisition and decode are faster than semantic
inference. The pinned two-model KataCR detector is the measured local
bottleneck: 300.525 of 369.817 semantic seconds. The earlier 8–10 games/hour
planning range is now confirmed by one match, but scaling remains an
extrapolation until the 100-game pilot measures duration/layout/yield variance,
failures, throttling, and persistent-worker batching.

The one-match semantic proof has passed, so one H100 worker is now justified
for the 100-game pilot. Benchmark the exact two-model portrait workload before
renting a fleet. Two to four H100 workers are a plausible later bulk shape;
more GPUs are unlikely to help until independent-egress acquisition and CPU
HUD/OCR feeding are proven.

## Proven measurements

### One full semantic match

The independent contract report is
`reports/tv_royale_youtube_fullmatch_semantic_contract_masks_v3_hTG8dM4KtM4_20260817.json`,
SHA-256
`d0ed32ec7b3cd761b8a0fa54edc0e845979a2939adf72ee879e3bed83fed63f0`.
It has no failed structural gates.

The corrected event-filtered, public-mask v3 manifest SHA-256 is
`a22ade6d8a96ad8b6f7b9c3ee4ee3d8951de1f0c7050c5601b4c60e287de93e1`.

| Stage | Wall seconds | Share of semantic wall |
| --- | ---: | ---: |
| Video decode | 1.896 | 0.5% |
| HUD model load | 0.536 | 0.1% |
| Both-HUD current-frame matching | 31.916 | 8.6% |
| Detector model load | 0.648 | 0.2% |
| Dense two-model arena detector | 300.525 | 81.3% |
| Native clock OCR including compile | 8.818 | 2.4% |
| Serialization and other | 25.478 | 6.9% |
| **Semantic total** | **369.817** | **100%** |

Measured resource and output counts:

- 8.664 sampled frames/s end-to-end; 10.661 detector frames/s;
- 9.735 semantic games/hour; 9.541 games/hour with the 7.52-second download;
- peak RSS 2,764,390,400 bytes and peak current MPS allocation 715,878,400
  bytes;
- 3,204 neutral records and 1,602 rows in each same-split actor trajectory;
- 3,114 clock-valid frames and 6,408 HUD player-frames with explicit per-head
  validity/confidence;
- 89 snapshots with both actor HUDs strictly complete;
- 89,009 detections, 17,313 valid HP observations, 18,761 typed tower
  observations, 618 typed effects, and 6 typed projectiles;
- 164 filtered offline deployment-marker candidates, of which 7 have both a
  valid card identity and deployment tile (player 0: 3; player 1: 4).
- 243/243 eligible actor-0 rows and 226/226 eligible actor-1 rows have
  nontrivial current-public-evidence masks; target fields are absent and
  identical public/own-HUD inputs deterministically produce identical masks.
- exact public-mask recomputation matched all 3,204 rows, and poisoning
  future/target fields changed zero of 3,204 masks.

The final structured output is about 15.2 MiB compressed, excluding the source
video. The neutral sequence is 7.6 MiB; v3 actor trajectories are about 3.9 and
3.7 MiB.

Important limits remain despite the passing structural contract: status
validity and projectile-target validity are zero; unsupported ability or
occupancy cases still fail closed; only 7/164 filtered deployment-marker
candidates have complete card identity plus tile; one of those seven is
independently illegal under the public mask; and only 89/3,204 snapshots have
both HUDs strictly complete. Detector/HUD
semantic accuracy has not yet been scored against human ground truth. These
outputs prove one full pipeline execution, not promotion-quality labels.

Every one of the seven retained actions was manually inspected at its exact
source frame and was visually plausible. The v2 event contact sheet SHA-256 is
`330a7048a075cc278501104e24f4b3bb14d78509f8da83bfa4689ae2191da35b`.
This is a precision spot check over one match, not a held-out recall estimate.

### YouTube acquisition

| Workload | Result | Scope and limit |
| --- | ---: | --- |
| Low-resolution canary | 10 videos in 98.984 s, 363.7 games/hour | Ten full format-18 transfers, 30 section cuts, probes, and audit frames; 144.17 MB transferred |
| Original-resolution source | 184.45 MB in 7.52 s, 24.53 MB/s | One 320.353 s, 1182×2560@60 VP9 full match |
| Original-resolution section processing | 1.999 s | One 10 s H.264 retained section plus audit artifacts |

The exact full-match artifact is
`datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4`.
Its source SHA-256 is
`89817c51cb83689e210b19b41444be6928483c915c5582b5ad144f05f00b4d5b`.
The successful original-resolution transfer is one observation. An earlier
all-ten retry failed before media bytes when the public endpoint became
temporarily unavailable. No multi-worker acquisition scaling has been proven.

The ten-video metadata sample totals 2,533 source seconds and 1.132 GB of
estimated selected-format media. The channel estimate used by the source plan
is 1.614 TB at the observed recent-video bitrate. At the single successful
24.53 MB/s transfer rate, that would take about 18.3 hours with one continuously
successful connection. This is a bandwidth calculation, not a rate-limit-safe
forecast.

### Exact full-match VP9 decode and 10 Hz index

The published full-match decoder selected 3,204 frames at 10 Hz from 19,202
VP9 packets. It produced contiguous PTS 0–3203 at time base 1/10 and a SHA-256
for every selected decoded frame without retaining raw pixels.

| Metric | Result |
| --- | ---: |
| Wall time | 27.17 s |
| User / system CPU | 70.01 / 1.12 s |
| Mean process CPU | 261.8% |
| Peak RSS | 332,873,728 bytes |
| Selected output rate | 117.92 frames/s |
| Source realtime factor | 11.79× |
| Uncompressed selected bytes hashed, not retained | 14.54 GB |
| Retained frame index | 359,068 bytes |

This is now the production-shaped decode/index measurement. It includes
full-frame SHA-256 work that normal semantic inference need not repeat on every
stage, so it is conservative for decode alone. Its index SHA-256 is
`ebbb0be0b39a234dc4294a0e5df0b0ca7d060e3b0230802289bd0b493e5b2d4d`.

### Retained original-resolution section decode

Input:
`datasets/external/tv_royale_youtube_explode_highres_canary_20260817/section_p10.mp4`

The retained file is 9.993316 s, 599 frames, 1182×2560, H.264/yuv420p, and
5,895,263 bytes. Three timed CPU repetitions produced:

| Operation | Median wall time | Effective rate |
| --- | ---: | ---: |
| Full decode to null | 0.40 s | about 1,498 decoded frames/s; 25.0× realtime |
| Decode, select 10 FPS, scale 576×896, BGR output | 0.49 s | 20.4× source realtime |
| Decode, select 5 FPS, scale 576×896, BGR output | 0.43 s | 23.2× source realtime |
| Decode, select 2 FPS, scale 576×896, BGR output | 0.40 s | 25.0× source realtime |

The 10 FPS conversion used about 2.53 CPU-seconds in 0.49 wall-seconds, or
roughly five cores. The machine had other CPU work active, so this is not an
isolated capacity benchmark. The retained section is H.264 and is therefore
secondary to the exact full-match VP9 measurement above. Together they show
that decode/crop is unlikely to dominate one local semantic worker.

### Existing local UI and detector stages

The strongest old public-v2 run has 1,000 completed games and 1,023 retained
per-game timing manifests. Aggregate manifest timings are:

| Stage | Mean seconds/game | Median seconds/game | Resource |
| --- | ---: | ---: | --- |
| Deck discovery | 4.67 | 4.24 | CPU image decode/template matching; serial within game |
| UI state scan | 10.49 | 9.48 | CPU fixed-ROI matching; serial event state within game |
| Selected-frame decode | 1.14 | 1.04 | CPU/decode/I/O |
| Detector model load | 1.02 | 0.99 | CPU/RAM; avoidable with persistent workers |
| Sparse two-model detector | 16.45 | 14.78 | MPS/CPU; dominant old semantic stage |
| Other conversion/tracking/write | about 0.55 | not isolated | CPU/I/O |
| Total excluding download | 34.32 | 31.46 | End-to-end per-game extractor timing |

The run's acquisition median was 19.166 s/game, extraction median was
33.027 s/game, and the one-download lookahead pipeline completed at 95.835
games/hour. Acquisition and extraction overlapped.

The 1,023 timing manifests processed 146,803 selected frames in 16,830.1 s,
or 8.72 frames/s. The controlled warm benchmark measured 11.07–11.46
frames/s at batch 16. Planning should use the lower production rate until the
new workload is benchmarked. MPS was only 0.7% faster than CPU in the matched
controlled test; multiple MPS processes should not be expected to scale.

Peak RSS was 2.43 GB for representative detector frames and 3.98 GB for the
old 522-frame full pass. Each detector has 43,695,375 parameters; the pair has
87,390,750 parameters and 168 MiB of checkpoint files.

## Extrapolations, not measured rates

The channel contains about 26.23 million samples at 10 Hz or 157.35 million
frames at 60 Hz. The mean video duration from 728.48 hours / 10,234 videos is
256.25 seconds.

At the production-observed 8.72 detector frames/s:

| Arena detector cadence | Approximate detector-only rate | Full channel detector time |
| --- | ---: | ---: |
| Sparse old mean, 143 frames/game | 220 games/hour | 46.6 hours |
| 5 Hz | 24.5 games/hour | 17.4 days |
| 10 Hz | 12.3 games/hour | 34.8 days |
| Full 60 FPS | 2.0 games/hour | 209 days |

The controlled 11 FPS rate gives the previously reported 165.5-day full-60-FPS
estimate. The production rate is deliberately used above because it includes
content-dependent postprocessing. Neither full-60-FPS path is viable.

The 100 ms play-timestamp gate needs at least a 10 Hz lightweight HUD scan.
The arena detector does not necessarily need every HUD frame: a practical
cascade can run HUD/event scanning at 10–20 Hz, arena state at 5–10 Hz, and
short detector bursts around play transitions. The exact cadence must be set
by held-out event, projectile, HP, and effect recall, not throughput alone.

For an H100, no rate is proven. A useful capacity formula at a 10 Hz dense
arena cadence is:

`games/hour = H100 dual-model frames/s × 3600 / 2562.5`

| Measured future H100 dual-model FPS | Detector games/hour/GPU | One-GPU channel time | Four-GPU channel time, ideal |
| ---: | ---: | ---: | ---: |
| 50 | 70 | 145.7 h | 36.4 h |
| 100 | 140 | 72.8 h | 18.2 h |
| 200 | 281 | 36.4 h | 9.1 h |

These rows are scenarios, not forecasts. They exclude download throttling,
HUD/OCR, tracking, failures, validation, and manual QA. Halving arena cadence
approximately doubles detector capacity but may fail semantic quality gates.

At 10 Hz, a 24-hour full-channel detector target requires about 304 aggregate
dual-model frames/s. That is seven H100s if the exact benchmark returns 50 FPS,
four at 100 FPS, or two at 200 FPS. A 48-hour target requires about 152 FPS.
This is why one measured H100 pilot must precede the fleet decision.

Moving the 1.614 TB media estimate in 24 hours requires about 18.7 MB/s
(150 Mbps) of sustained useful transfer; 12 hours requires 37.4 MB/s, and six
hours 74.7 MB/s. Bandwidth alone is feasible, but the observed endpoint
unavailability means independent egress, retry yield, and request pacing—not
nominal link speed—will decide acquisition scaling.

## Stage resource and scaling model

| Stage | Serial dependency | Parallel/batch opportunity | Scaling constraint |
| --- | --- | --- | --- |
| Metadata/access gate | Per-video request | Independent videos | Endpoint request limits and retries |
| Original media transfer | One stream per game | Separate games/egress | CDN throttling, network, per-IP behavior; currently the least reliable scaling stage |
| Decode/layout normalization | PTS order per game | Separate games; streamed frame batches | CPU cores and memory bandwidth; never retain full raw-frame arrays |
| Clock and both HUDs | State transitions are chronological | Batch fixed crops across games, then restore per-game order | CPU template/OCR cost and current-card template coverage |
| Arena detector | None between frames for raw inference | Large batches across games, one pass per model | GPU throughput and NMS; strongest H100 target |
| HP/body association and tracking | Chronological per game | Many game-local tracker instances | CPU; lightweight compared with detector if detections stay bounded |
| Play/deployment reconstruction | Chronological per game | Parallel games | Requires small past-only ring buffers; future evidence may be label-only |
| Neutral record and actor projections | Per-frame conversion | Parallel games/chunks | Do not duplicate neutral tensors; actor views share split and reference one neutral record |
| Hash/validation/publication | Per artifact/chunk | Parallel files | SSD I/O; atomic publication and bounded scratch |

One full-resolution raw BGR frame is about 9.08 MB. A batch of 16 is about
145 MB before resized model inputs. The actual decoder's native YUV420 sample
is 4,538,880 bytes, and the 3,204 selected full-match samples would occupy
14.54 GB uncompressed. A 576×896 BGR frame is 1.55 MB. Streaming and bounded
rings are mandatory; caching a full match's raw frames would use tens to
hundreds of GB depending on cadence and representation.

The old compressed public-state sidecars occupy 14.93 MB for 30,519 samples,
about 489 bytes/sample. The new neutral schema is richer, so its output size is
unknown, but compact structured output should remain much smaller than video.

## Worker recommendation

The one-match proof is complete. If its rate scaled linearly, 100 games would
take 10.48 hours locally and all 10,234 would take 44.7 days. Those figures do
not include pilot rejection/retry/manual-QA overhead and should not be used as
a completion promise.

### Proven-local capacity table

This table uses only the measured one-match download-plus-semantic rate of
9.5405 games/hour. The larger rows are linear capacity calculations, not
multi-game measurements.

| Workload | One M4 pipeline wall time |
| --- | ---: |
| One proven match | 377.337 s measured |
| 100-game pilot | 10.48 h extrapolated |
| 1,000 games | 104.82 h / 4.37 d extrapolated |
| Full 10,234-video channel | 1,072.69 h / 44.70 d extrapolated |

### Exact first-H100 gate

Run the exact 3,204-frame, 10 Hz, production crop, two-checkpoint detector
workload three times without HUD/OCR/tracker noise:

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_tv_royale_youtube_detector.py \
  --input-video \
    datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4/source.webm \
  --source-manifest \
    datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4/manifest.json \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device cuda --batch-size 16 --repetitions 3 \
  --output reports/tv_royale_youtube_detector_h100_batch16.json
```

Success requires all three repetitions to decode exactly 3,204 frames, stable
within-H100 rounded detection digests/counts, no OOM, recorded peak VRAM, and
median dual-model detector throughput of at least 89.0 frames/s. That FPS is
the detector capacity required for 100 games/hour at this exact match length
and 10 Hz cadence. It is not an end-to-end 100-games/hour claim: the CPU HUD
lane measured only 112.8 isolated games/hour and must be kept fed in parallel.

Scale decisions after the exact benchmark and 100-game pilot:

- below 44.5 detector FPS: do not rent a fleet; optimize batching/model/runtime
  first because two identical GPUs still miss 100 detector-games/hour;
- 44.5–88.9 FPS: two H100s are the minimum 100-games/hour detector shape;
- at least 89.0 FPS: start the pilot with one H100 and 32 vCPU; add CPU lanes
  before another GPU if detector idle time exceeds 20%;
- for a 24-hour full-channel detector target, required aggregate throughput is
  304 frames/s, so the later GPU count is `ceil(304 / measured_H100_FPS)`;
- add a GPU only when detector utilization exceeds 80% with a growing prepared
  frame queue. If acquisition/HUD queues starve it, add independent-egress
  fetch or CPU workers instead.

For the 100-game pilot:

- one H100 (80 GB is ample for the two 43.7M-parameter detectors and large
  cross-game batches);
- 16–32 vCPU and 32–64 GB host RAM for VP9 decode, both-HUD extraction, OCR,
  NMS, tracking, and serialization;
- at least 200 GB local NVMe scratch, with per-game deletion only after hashes
  and structured outputs validate;
- one conservative acquisition lane, optionally a second only if independent
  egress and bounded backoff are available.

For the bulk wave, start with two H100 semantic workers and two conservative
acquisition workers on independent egress. Increase to four H100s only if the
single-H100 benchmark and queue telemetry show the detector queue remains the
bottleneck. Do not add same-IP download concurrency in response to endpoint
unavailability. Do not add multiple local MPS workers; use one persistent,
cross-game-batched detector instead.

The first pilot report must record source seconds, transferred bytes, decoded
frames, HUD frames, detector frames, accepted snapshots/events, stage wall and
CPU/GPU time, peak RSS/VRAM, queue idle time, failures/retries, and hashes. The
fleet decision should be based on seconds and bytes per accepted semantic
snapshot/event, not raw games/hour alone.

## Reproduction evidence

Retained-section decode command shape:

```bash
ffmpeg -hide_banner -loglevel error \
  -i datasets/external/tv_royale_youtube_explode_highres_canary_20260817/section_p10.mp4 \
  -f null -

ffmpeg -y -hide_banner -loglevel error \
  -i datasets/external/tv_royale_youtube_explode_highres_canary_20260817/section_p10.mp4 \
  -an -vf 'fps=10,scale=576:896' -pix_fmt bgr24 -f rawvideo /dev/null
```

Primary local evidence:

- `datasets/external/tv_royale_youtube_explode_highres_canary_20260817/manifest.json`
- `datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4/manifest.json`
- `datasets/external/tv_royale_youtube_section_canary_20260817/manifest.json`
- `datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201/run_manifest.json`
- `reports/tv_royale_vision_benchmark_20260812.md`
- `reports/tv_royale_youtube_source_plan_20260817.md`
