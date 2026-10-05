# TV Royale YouTube/Hugging Face deduplication gate — 2026-08-17

## Result

The exact cross-source matcher is ready, but the HF three-point index cannot be
completed locally or within fifteen minutes. Reconstructing it requires the
2,000 original source parquets: 1,458,083,876,741 bytes in total.

No source video was downloaded in this audit. The supplied MIT dataset-card
declaration is preserved as MIT and is never represented as Creative Commons.

## Corrected retained-evidence audit

The previous inventory mistakenly inferred temporal percentages from retained
audit filenames. Source inspection proved `_select_audit_frames` deliberately
prefers accepted card labels and only uses temporal spacing as a fallback.
Those 4,279 rendered JPEGs are event-oriented extraction audits—not certified
10%, 50%, or 90% frames.

The corrected inventory is:

- 2,000 completed source records and 2,000 game manifests present;
- zero certified 10/50/90 HF fingerprints;
- 4,279 retained event-oriented audit images, usable for extraction QA but not
  this temporal dedup contract;
- structured NPZ corpora contain no source pixels;
- the retained 1.3 GB placement parquet overlaps 66 source replays, but its
  selected deployment PNGs lack source-sequence endpoints and cannot be
  relabeled as 10/50/90 evidence; and
- 1,469 replay IDs have assignments in the chosen existing split manifest.

The corrected machine-readable inventory is
`reports/tv_royale_hf_dedup_evidence_inventory_20260817.json`.

## Why exact local or HTTP-range reconstruction is impossible

The two retained original replay parquets were inspected structurally. Each
has one row group; `image.bytes` occupies one enormous dictionary page; and
neither a page offset index nor column index exists. The sampled compressed
image columns are 430,859,126 and 818,519,064 bytes. Retrieving one exact
midpoint image therefore requires reading/decompressing the image dictionary,
not a small row-level HTTP range.

The Hugging Face Dataset Viewer independently rejects even the 1.3 GB converted
placement parquet with `Scan size limit exceeded` and specifically reports the
absence of a page index/smaller row groups. It cannot provide a server-side
one-row shortcut for this layout.

The full historical source inventory is 1.458 TB across 2,000 files (median
663.4 MB, maximum 1.733 GB). A complete exact reconstruction is not a bounded
fifteen-minute task.

## Shardable exact reconstruction

`scripts/reconstruct_tv_royale_hf_fingerprint_shard.py` now provides both the
explicit missing-path inventory and a resumable bounded runner. For each
replay it:

1. verifies the downloaded byte size and historical SHA-256 from the original
   run manifest;
2. reads the ordered public `frame_id` values;
3. chooses the nearest row to 10%, 50%, and 90% of the exact `[min,max]`
   frame-clock interval;
4. decodes the three selected PNGs and applies the established raw arena crop
   `(left=57, top=137, width=428, height=757)`;
5. emits normalized-pixel SHA-256 and 64-bit DCT pHash;
6. atomically publishes after every replay; and
7. deletes the temporary source parquet after fingerprints are retained.

The complete 2,000-entry plan is
`reports/tv_royale_hf_fingerprint_reconstruction_plan_20260817.json`. It uses
200 deterministic hash shards. Each invocation should process at most five
games, which is below 8.67 GB even at the observed maximum file size.

Dry-run one bounded shard without network access:

```bash
PYTHONPATH=src:. uv run python \
  scripts/reconstruct_tv_royale_hf_fingerprint_shard.py \
  --run-manifest \
    datasets/derived/tv_royale_raw_cascade_1000_v1/run_manifest.json \
  --dataset-card datasets/external/tv_royale_parquet_download/README.md \
  --shard-count 200 --shard-index 0 --max-games 5 \
  --max-total-download-bytes 12000000000 --dry-run \
  --output reports/tv_royale_hf_fingerprint_shard_000.json
```

Execute that same bounded shard later, after CPU/network coordination, by
removing only `--dry-run`:

```bash
PYTHONPATH=src:. uv run python \
  scripts/reconstruct_tv_royale_hf_fingerprint_shard.py \
  --run-manifest \
    datasets/derived/tv_royale_raw_cascade_1000_v1/run_manifest.json \
  --dataset-card datasets/external/tv_royale_parquet_download/README.md \
  --shard-count 200 --shard-index 0 --max-games 5 \
  --max-total-download-bytes 12000000000 \
  --output reports/tv_royale_hf_fingerprint_shard_000.json
```

Rerunning the command resumes the same shard and selects the next five missing
games. Change only `--shard-index` and the output suffix to operate another
shard. Never run all 200 without an explicit network/storage window.

## Cross-source matching and split safety

`scripts/deduplicate_tv_royale_sources.py` accepts completed fingerprint shard
files through repeated `--hf-fingerprint-shard` arguments. It:

- normalizes frames to 288 x 512 RGB;
- compares exact decoded-pixel SHA-256 and pHash at all three percentages;
- incorporates duration, player-name, and deck evidence where present;
- requires at least two of three close pHashes plus duration compatibility to
  create a candidate;
- requires a separately named visual review to confirm a duplicate;
- quarantines unresolved candidate components; and
- quarantines every YouTube artifact until fingerprint shards cover all 2,000
  HF source records.

Confirmed groups receive one atomic split, so a duplicate can never cross
training and held-out partitions.

## Permission provenance

The local dataset card SHA-256 is
`a7e2f6df420895aa58ed7d8fc03b33917ffc1b1c9c5f79eeec46533ec4a10e0a`
and declares `license: mit`. Shard outputs retain that declaration and source
hash. The YouTube authorization record remains a separate opaque provenance
object. Neither is converted into a CC claim.

## Validation

```text
Ruff: clean
mypy: clean (both scripts independently)
pytest: 7 passed
```

Tests cover exact pixel/pHash determinism, candidate versus confirmation state,
atomic split assignment, incomplete-index quarantine, rejection of
event-oriented audits as percentage evidence, source SHA verification,
frame-clock percentage selection, and MIT-without-CC provenance preservation.
