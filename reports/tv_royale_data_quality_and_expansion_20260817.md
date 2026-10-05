# TV Royale data quality and expansion — 2026-08-17

## Decision

Only corpora with the exact source label
`tv-royale-raw-cascade-location-visual-strict-v3` may train deployment
coordinates. Type-only corpora remain useful for play timing and card identity,
but their action encoding uses tile zero as a placeholder and must run with no
location objective.

The next extraction wave should not start while the shared host is saturated by
PyTorch simulator work. When a clean window exists, re-extract a replay-disjoint
second wave with the current public-state pipeline, then rebuild all four splits
from the combined current-quality waves.

## What the audit proves

`scripts/audit_tv_royale_supervision.py` reads the final NPZ artifacts rather
than trusting a split's claimed diversity. It reports card-play/no-op counts,
card and tile coverage, clock coverage, source replay/frame coverage, label
provenance, and replay/deck/archetype/chronology isolation. With
`--require-spatial`, it fails closed when provenance says `type-only`, all play
rows decode to tile zero, or strict visual-location provenance is absent.

The repository inventory contains eleven pre-existing TV Royale split families:

- ten type-only families; every placement-shaped play label uses exactly one
  tile, tile 0;
- one old strict-location family, with 1,395 assigned samples and genuine tile
  diversity;
- zero detected replay/deck/held-out-archetype leakage in the audited manifests.

The complete machine-readable inventory is
`reports/tv_royale_supervision_inventory_20260817.json`.

### Concrete invalid-spatial example

`tv_royale_public_v2_post260_split_seed1056502` is valid type/timing
supervision but invalid location supervision:

| Split | Samples | Play rows | Unique encoded tiles | Tile-0 fraction |
| --- | ---: | ---: | ---: | ---: |
| Train | 8,877 | 4,719 | 1 | 100% |
| Validation | 1,518 | 763 | 1 | 100% |
| Held-out archetype | 2,957 | 1,524 | 1 | 100% |
| Chronology | 539 | 266 | 1 | 100% |

The rejection artifact is
`reports/tv_royale_typeonly_supervision_rejection_20260817.json`.

### Genuine spatial data already present

The old `tv_royale_raw_cascade_2000_locations_split_seed1045801` family passes
strict provenance and spatial checks:

| Split | Samples | Replays | Cards | Unique tiles |
| --- | ---: | ---: | ---: | ---: |
| Train | 592 | 103 | 49 | 166 |
| Validation | 223 | 27 | 43 | 84 |
| Held-out archetype | 359 | 44 | 39 | 132 |
| Chronology | 221 | 31 | 29 | 100 |

Its audit is `reports/tv_royale_location_supervision_audit_20260817.json`.

## Better four-way location split built from the current 1,000-game run

The current public-v2 run actually contains 4,610 strict visual deployment
labels from 663 games. A new type split and matching location split were built
without running detector inference:

- type manifest:
  `datasets/derived/tv_royale_raw_cascade_public_v2_1000_type_split_seed1064001/split_manifest.json`
  (`486a59c9c51fba1fc46472be8322b68c6ffd47500e4275e4beff4c9c2025c2d3`);
- location manifest:
  `datasets/derived/tv_royale_raw_cascade_public_v2_1000_location_split_seed1064001/split_manifest.json`
  (`aff7f95d01cb3c2578e7c3f9591296faa1ac838b404a063a32a12010ae11241b`).

| Split | Samples | Replays | Cards | Unique tiles |
| --- | ---: | ---: | ---: | ---: |
| Train | 2,617 | 393 | 53 | 240 |
| Validation | 695 | 101 | 48 | 184 |
| Held-out archetype | 996 | 126 | 52 | 211 |
| Chronology | 302 | 43 | 41 | 107 |

The strict verifier and independent audit both pass. Replay overlap, deck-hash
overlap, and held-out-archetype-to-train overlap are zero. The validation output
is `reports/tv_royale_public_v2_1000_location_split_verification_seed1064001.json`
(`a9d083d513bf5588db767e4160ffad7804dc56a816124af05038caeea406c528`).

Five retained audit frames were also inspected directly: Electro Wizard at
tile 267, Poison at tile 255, Skeleton Barrel at tile 268, a late Mega Knight
type event, and a terminal no-op. The 18 x 32 grid aligned with the playable
arena; deployment crosses/area centers were plausible; the terminal overlay
did not become a false action. Detector rectangles remained correctly labeled
as sprite/UI bounds rather than combat hitboxes. The Skeleton Barrel frame was
visually crowded, reinforcing the need for the existing two-frame agreement
gate rather than trusting one detector center.

## Current public-state coverage

The current 1,000-game public-v2 corpus has:

- 29,722 decision rows;
- 20,713 own-player card-play identities and 9,009 exact no-ops;
- public clock/phase/own-elixir confidence on all 29,722 rows;
- 262,240 visible entity instances;
- 148,153 measured entity-HP instances (56.495%);
- 101,329 measured motion instances (38.640%);
- 121,137 tower-HP measurements;
- 5,952 visible area-effect entity instances;
- no measured stun, slow, haste, stealth, or effect-progress fields;
- opponent-history and opponent-seen-card arrays of width zero.

The last two points are important. The corpus provides strong own-action and
board-state supervision, but it does not yet supervise the opponent card-play
events needed by an internal opponent-elixir/cycle tracker. Visible area effects
are identified, but attached status presence and remaining duration are not.

## Future-confirmed player Next-card labels

The card that later fills a vacated hand slot reconstructs the player's
previously visible `Next` card. This is legitimate offline hindsight labeling
of a public HUD element, but it is never valid as a live input before the HUD
made it visible.

`recover_future_confirmed_next_card_labels` enforces all of the following:

- the next evidence row is in the same replay and episode;
- source frame time increases;
- the other three visible hand slots are unchanged;
- the refill is known and differs from the played card;
- the output contract records `label_only_future_confirmed=true` and
  `live_policy_input_before_observation=false`.

On the new leakage-safe 1,000-game type split it recovers 7,919 of 9,783 play
rows (80.947%):

| Split | Eligible plays | Recovered | Coverage |
| --- | ---: | ---: | ---: |
| Train | 5,538 | 4,464 | 80.607% |
| Validation | 1,432 | 1,127 | 78.701% |
| Held-out archetype | 2,150 | 1,786 | 83.070% |
| Chronology | 663 | 542 | 81.750% |

Recovery occurs only after split assignment, so no future evidence is read
across a replay or split boundary.

## Actual throughput bottleneck

The current public-v2 run completed 1,000 games in 34,822.37 seconds, or
95.835 trustworthy labeled games/hour.

| Stage per successful game | Median | Mean |
| --- | ---: | ---: |
| Raw parquet download | 19.166 s | 21.918 s |
| Public-v2 extraction | 33.027 s | 35.957 s |
| Selected detector frames | 129 | 143.167 |

Raw games averaged 709.18 MB, totaling 709.18 GB downloaded for the 1,000-game
run. One-download lookahead overlaps acquisition with extraction, so detector
and vision processing is currently the wall-clock bottleneck. Network becomes
the next bottleneck if CUDA makes extraction faster than roughly 22 seconds per
game. Validation and compact artifact writes are small by comparison.

Raw files are SHA-verified, streamed, and deleted after publication. The three
combined artifacts are only 3.31 MB (type/no-op), 10.14 MB (public state), and
0.568 MB (locations). The 504 MB retained run directory is mostly per-game
compact corpora and audits, not raw video. Peak detector evidence from the
existing benchmark is about 4.0 GB RSS.

Source availability is a separate hard cap: the pinned arena-12-through-31
inventory contains 2,123 eligible games. The current public-v2 run covers
1,000; the older mixed-quality run covers 2,000. Expansion therefore means
re-extracting approximately the remaining 1,000 available games with the
current pipeline, not scraping an unlimited source.

## Next extraction batch

### Required outputs

For every retained decision/event frame:

1. **Clock and HUD:** visible battle timer, phase, own elixir, four hand cards,
   and confidence.
2. **Own card play:** identity, source frame, vacated slot, and strict event
   de-duplication.
3. **Player Next label:** future-confirmed refill sidecar with the contract above.
4. **Deployment location:** strict two-frame deployment-clock agreement or
   persistent-area spell center; reject projectile and ambiguous events.
5. **Entity state:** identity, team, center, HP bar, motion, and confidence.
6. **Opponent play event:** a new public-event label derived from newly visible
   enemy deployment/spell evidence. This must be a current-frame public event,
   not hidden deck metadata or simulator state.
7. **Status evidence:** visible area effect and attached stun/slow/haste/stealth
   cues with onset confidence. Remaining duration can be an internal model
   countdown only after a trustworthy visible onset.

### Replay-disjoint wave command

The runner now supports `--exclude-run-manifest`, which excludes all completed
replays from a prior wave before downloading anything:

```bash
nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/run_tv_royale_raw_cascade.py \
  --target-games 1000 --max-attempts 1123 \
  --arena-min 12 --arena-max 31 --seed 1064101 \
  --exclude-run-manifest \
    datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201/run_manifest.json \
  --scratch-dir datasets/external/tv_royale_raw_stream_public_v2_wave2 \
  --output-dir datasets/derived/tv_royale_raw_cascade_public_v2_wave2_seed1064101 \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --batch-size 16 --noop-stride 20 --audit-samples 2
```

At the measured local rate, 1,000 current-quality games require about 10.43
hours and roughly 709 GB of streamed network traffic. Scratch normally holds
only the active game and one prefetched game; allow at least 6 GB. Do not launch
this command until the other PyTorch tasks release a sustained-compute window.

Before a full wave, run 25 replay-disjoint canaries and require:

- at least 95% successful extraction;
- exact clock/HUD confidence accounting;
- nonzero opponent-event and status-onset coverage in the new contract;
- strict spatial labels with more than one tile and visually inspected grids;
- no replay/deck overlap with wave 1;
- full artifact SHA verification and raw scratch returned to zero.

After both waves, rebuild type and location splits from one combined source
manifest, then run `audit_tv_royale_supervision.py --require-four-way` for type
labels and again with `--require-spatial` for location labels. Keep entire
archetypes and the chronology component outside training.

## Validation commands

```bash
PYTHONPATH=src:. uv run python scripts/audit_tv_royale_supervision.py \
  --manifest \
    datasets/derived/tv_royale_raw_cascade_public_v2_1000_location_split_seed1064001/split_manifest.json \
  --require-spatial --require-four-way

PYTHONPATH=src:. uv run pytest -q \
  tests/test_audit_tv_royale_supervision.py \
  tests/test_verify_tv_royale_location_split.py \
  tests/test_run_tv_royale_raw_cascade.py
```
