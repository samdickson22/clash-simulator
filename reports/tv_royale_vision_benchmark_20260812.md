# TV Royale vision extraction benchmark — 2026-08-12

## Decision

Use a multi-stage cascade, not full-frame detection. A fixed-region UI stage
identifies the visible hand, fractional elixir, and exact played-card changes;
the pinned two-model KataCR detector runs only on accepted action states and
sparse no-op states. Generic deployment clocks and first-appearing entity
centers both failed the held-out spatial gate, so the raw archive contributes
type/timing/no-op supervision only. No location is invented: played-card rows
are valid only with `type-head-v1` (`location_loss_coef=0`).

Use a fixed detector batch size of 16 and stream raw files with one-download
lookahead. Verify every download against the repository LFS SHA-256, publish
and reload each compact corpus, then delete the recoverable raw payload. The
production run is stratified round-robin across arenas 12 through 31.

## Cascade throughput and quality gate

The held-out arena-29 replay contains 1,009 frames. The UI extractor recovered
all 62 upstream action events at the exact source frame and card identity; one
additional gray-card transition was correctly excluded. Ambiguous simultaneous
events are now rejected rather than arbitrarily ordered.

One complete local extraction retained 51 unambiguous type labels and 27 exact
no-ops from only 78 detector frames. It took 28.8446 seconds excluding source
download, or 124.81 games/hour. A live five-game streamed canary across arenas
12 through 16 included source download, SHA verification, one-frame lookahead,
extraction, audit rendering, raw deletion, and corpus validation:

- 5/5 games completed
- 140 type labels and 50 exact no-ops (190 samples)
- 138.665 seconds total
- 129.81 completed games/hour
- scratch raw data returned to zero after completion

The production 1,000-successful-game run is resumable at
`datasets/derived/tv_royale_raw_cascade_1000_v1/run_manifest.json`; its owned
tmux session is `clasher-tv1000`. An initial nine-game production probe exposed
one terminal `Tiebreaker` no-op during visual review. That probe was rejected
and moved to Trash, a 50-frame terminal no-op exclusion was added and tested,
and production restarted cleanly. Scratch holds at most the active raw file and
one bounded prefetch. The clean restart's first five games completed without a
failure in 90.84 seconds (198.15 games/hour); this short warm-server sample is
reported separately from the more conservative five-game canary above.

Visual audits were inspected across arenas 12, 13, 14, 15, 16, 24, and 29.
Visible hand identities, gray/playable state, elixir, card event, arena crop,
grid, and detector centers agreed with the screenshots. Detector boxes are
explicitly labeled as sprite/UI bounds, never combat hitboxes.

## Hardware and pipeline

- Apple M4 Pro, 12 CPU cores, 24 GiB unified memory
- Python 3.12.13, torch 2.10.0
- two pinned KataCR detector checkpoints, 43,695,375 parameters each
- 87,390,750 detector parameters total
- inference size: 896 x 576
- confidence: 0.4; NMS IoU: 0.6
- exact source arena crop: left 57, top 137, width 428, height 683

## Results

### Representative cropped action frames

64 frames, three timed repetitions after warmup:

| Device | Batch | Median detector FPS |
| --- | ---: | ---: |
| MPS | 1 | 10.575 |
| MPS | 4 | 11.308 |
| MPS | 8 | 11.338 |
| MPS | 16 | 11.433 |
| MPS | 32 | 11.280 |
| CPU | 1 | 10.411 |
| CPU | 4 | 11.244 |
| CPU | 8 | 10.762 |
| CPU | 16 | 11.320 |
| CPU | 32 | 11.004 |

PNG decode alone reached 243.67 frames/s. Model load was approximately 0.840
seconds and peak RSS was 2,432,679,936 bytes. All runs produced 2,022
detections. CPU and MPS produced the same digest at matched batch sizes.

### Representative raw replay frames

128 evenly sampled frames, exact crop, three timed repetitions:

| Device | Batch | Median detector FPS |
| --- | ---: | ---: |
| MPS | 4 | 11.343 |
| MPS | 16 | 11.459 |
| CPU | 4 | 11.285 |
| CPU | 16 | 11.379 |

Decode and crop alone reached 155.86 frames/s. All repetitions produced 3,886
detections, with exact CPU/MPS agreement at matched batch sizes. MPS was only
0.7% faster than CPU at batch 16.

### Complete raw replay

The pilot replay contains 522 frames spanning 52.2 seconds at nominal 10 FPS.
Two full MPS/batch-16 repetitions produced:

- median detector time: 47.1378 seconds
- median detector throughput: 11.0739 frames/s
- detections: 15,965 in each repetition
- exact digest: `15edbdc5cd9b91a4fcbed2fb454ff4f57593a155206547b385b67a1211d16898`
- decode/crop median: 3.7304 seconds, 139.93 frames/s
- model load: 0.8767 seconds
- peak RSS: 3,977,645,376 bytes

One full pass including decode and one-time model load is therefore roughly
the replay's own wall-clock duration. Scale estimates should use actual
retained frame counts because replay lengths and archive file sizes vary.

## Visual extraction audit

The raw-frame audit draws the exact full-frame crop and the 18 x 32 arena grid.
The action-pair audit draws before/after detections, detector centers, source
placement labels, recovered deployment clocks, the river, and blocked terrain.

Important semantics:

- detection rectangles are pixel-space sprite/UI bounds, not combat hitboxes
  and not occupied tile footprints;
- only a rectangle's center is converted into an observed arena position;
- combat collision radius and deployment occupancy come from simulator/game
  mechanics, never from rectangle width or height;
- the overlay now labels this explicitly and marks each detector center;
- imported Crown Tower observations now receive the same runtime stat payloads
  as live simulator towers instead of zero static geometry.

The visual audit caught one Archer Queen sample where the recovered clock was
on the other lane: source tile 254 versus clock tile 260, 143 pixels apart.
That row must fail closed. In accepted examples, source and recovered clock
labels agreed exactly at the tile level with center differences of 0 to 5
pixels.

## Reproduction

Production cascade:

```bash
PYTHONPATH=src:. uv run python scripts/run_tv_royale_raw_cascade.py \
  --target-games 1000 --max-attempts 1600 \
  --arena-min 12 --arena-max 31 --seed 1044201 \
  --scratch-dir datasets/external/tv_royale_raw_stream_1000_v1 \
  --output-dir datasets/derived/tv_royale_raw_cascade_1000_v1 \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --batch-size 16 --noop-stride 20 --audit-samples 2
```

Benchmark driver:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_tv_royale_vision.py \
  --input-parquet datasets/external/tv_royale_raw_pilot/arena_24/25848212-ea7a-48c9-bd4a-f1c27206396f/frames.parquet \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --batch-size 16 --frames 522 --sample-mode even \
  --crop 57 137 428 683 --repetitions 2
```

Grid audits:

```bash
PYTHONPATH=src:. uv run python scripts/render_tv_royale_extraction_audit.py \
  --input-parquet datasets/external/tv_royale_parquet_download/training_offset_1_all_arenas.parquet \
  --output-dir reports/tv_royale_extraction_grid_audit_seed1044001 \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --samples 16 --batch-size 16

PYTHONPATH=src:. uv run python scripts/render_tv_royale_raw_vision_audit.py \
  --input-parquet datasets/external/tv_royale_raw_pilot/arena_24/25848212-ea7a-48c9-bd4a-f1c27206396f/frames.parquet \
  --output-dir reports/tv_royale_raw_grid_audit_arena24_25848212 \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --samples 12 --batch-size 12
```
