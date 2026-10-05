# TV Royale YouTube source plan — 2026-08-17

## Decision

The channel is potentially much larger and more recent than the existing
Hugging Face corpus. On 2026-08-17 the user reported personally obtaining the
channel owner's explicit approval to use the videos. Record this exactly as
`permission_basis=user_attested_channel_owner_approval`; do not reinterpret it
as a public Creative Commons license.

The bounded ten-video canary is now authorized. The 10,000-video wave remains
operationally blocked until the canary passes and H100 access is coordinated.

The supplied inventory reports:

- channel: `https://www.youtube.com/@TVroyale-tv1sn`;
- 10,234 videos;
- 728.48 total hours;
- upload range at least 2024-03-29 through 2026-08-09;
- 22 subscriber-only entries; the remainder appear public;
- portrait Clash Royale recordings, sampled at 59-60 fps and resolutions from
  888 x 1920 through 1182 x 2560;
- mostly complete three-to-five-minute top-200/top-10 matches.

These full-inventory counts came from the upstream metadata handoff and were
not regenerated in this task. This task made only bounded metadata requests:
ten flat playlist entries and full `--skip-download` metadata for those same
ten videos. It downloaded no video, audio, or thumbnail media.

## Bounded channel confirmation

Tool: `yt-dlp 2026.07.04` through `uvx`.

The latest ten metadata records were all:

- uploaded 2026-08-09;
- public;
- 1182 x 2560 at 60 fps;
- 194-321 seconds long;
- `license: null`;
- 1,592,472,652 aggregate estimated bytes for 2,587 seconds.

The sample's implied best-format bitrate is 4.9245 Mbps. This is only a recent
ten-video sample, not an estimate with a statistical confidence interval.

Flat playlist metadata alone is insufficient for splitting: the bounded flat
records had null upload dates, availability, dimensions, fps, and license.
The full inventory plan therefore requires full metadata JSON, still with
`--skip-download`, before assigning chronology or access status.

## Final metadata canary selection

A second bounded metadata pass selected age-quantile indices across the full
playlist rather than using ten adjacent recent uploads. All ten are public:

| Playlist index | Video ID | Upload date | Seconds | Format |
| ---: | --- | --- | ---: | --- |
| 1 | `hTG8dM4KtM4` | 2026-08-09 | 320 | 1182x2560@60 |
| 1,138 | `i4WTQPAh0_E` | 2026-05-15 | 213 | 1182x2560@60 |
| 2,275 | `BL0s-x4E_ZQ` | 2026-02-24 | 321 | 1182x2560@60 |
| 3,412 | `i1AyFVBDsPE` | 2025-12-03 | 221 | 886x1920@60 |
| 4,549 | `iW_07-RIjJk` | 2025-08-25 | 293 | 886x1920@60 |
| 5,686 | `nXNp3GRdFks` | 2025-05-23 | 319 | 886x1920@60 |
| 6,823 | `yS3akCAdr6A` | 2025-02-21 | 205 | 886x1920@60 |
| 7,960 | `aVnmZEXSgiI` | 2024-11-17 | 209 | 886x1920@60 |
| 9,097 | `Xf8Y9GdxlLo` | 2024-08-07 | 191 | 888x1920@60 |
| 10,234 | `0aBzIYe-FaA` | 2024-03-29 | 241 | 888x1920@59 |

Selected-format estimates total 1,132,101,073 bytes, below the 5 GiB canary
cap even if full videos were needed. The clip downloader is stricter and only
acquires bounded temporal sections. Metadata artifacts:

- `datasets/source_metadata/tv_royale_youtube_canary_20260817/metadata.jsonl`,
  SHA-256 `8bd638c28092deafe27fb2ca5b0091305d48769e2d2295ac0d03e54507db6275`;
- `datasets/source_metadata/tv_royale_youtube_canary_20260817/manifest.json`,
  SHA-256 `c272d523b8038df26bfed0aaf9c331ce5c27ffabdad7aeeeffac89534615259c`.

No media, audio, thumbnails, comments, or subtitles were downloaded during
metadata selection.

## Rights gate

License metadata is null/default and was not itself the permission basis.
YouTube's official license documentation says the Standard YouTube license is
the default and distinguishes it from Creative Commons Attribution. It also
states that permission for someone else's upload must be handled with the
rights holder, not granted by YouTube:
[YouTube license types](https://support.google.com/youtube/answer/2797468?hl=en).

Permission provenance:

- basis: `user_attested_channel_owner_approval`;
- date: `2026-08-17`;
- source: `https://www.youtube.com/@TVroyale-tv1sn`;
- bounded ten-video canary authorized: **yes**;
- public CC license claimed: **no**;
- bulk wave operationally authorized: **no**, pending canary and H100
  coordination;
- external contact performed by this task: **no**;
- subscriber-only videos: excluded under every plan;
- the user's attestation is preserved separately from YouTube license metadata.

## Reproducible metadata inventory

The inventory is deliberately two-stage. The first command cheaply freezes
the channel IDs/titles/durations/thumbnails. The second resolves full metadata
without downloading media and may issue one metadata request per video, so it
should run as a resumable, low-rate job rather than while shared training is
saturated.

```bash
mkdir -p datasets/source_metadata/tv_royale_youtube_20260817

uvx --from yt-dlp yt-dlp \
  --flat-playlist --skip-download --dump-json \
  --ignore-errors --no-warnings \
  'https://www.youtube.com/@TVroyale-tv1sn/videos' \
  > datasets/source_metadata/tv_royale_youtube_20260817/flat.jsonl

uvx --from yt-dlp yt-dlp \
  --skip-download --dump-json \
  --ignore-errors --no-warnings --sleep-requests 0.25 \
  'https://www.youtube.com/@TVroyale-tv1sn/videos' \
  > datasets/source_metadata/tv_royale_youtube_20260817/full.jsonl

shasum -a 256 \
  datasets/source_metadata/tv_royale_youtube_20260817/flat.jsonl \
  datasets/source_metadata/tv_royale_youtube_20260817/full.jsonl
```

No such full-channel command was run during this task.

After metadata is pinned:

```bash
PYTHONPATH=src:. uv run python \
  scripts/plan_tv_royale_youtube_source.py \
  --metadata-jsonl \
    datasets/source_metadata/tv_royale_youtube_20260817/full.jsonl \
  --hf-run-manifest \
    datasets/derived/tv_royale_raw_cascade_1000_v1/run_manifest.json \
  --hf-run-manifest \
    datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201/run_manifest.json \
  --enabled-decks-json decks.json \
  --permission-basis user_attested_channel_owner_approval \
  --permission-date 2026-08-17 \
  --seed 1064201 --chronology-fraction 0.10 \
  --validation-fraction 0.10 --canary-count 10 \
  --output reports/tv_royale_youtube_source_manifest_seed1064201.json
```

The planner records every selected ID, source digest, access status, date,
duration, format metadata, recency weight, candidate duplicate group, split,
rights gate, storage estimate, and ten-video canary choice.

## Recent-patch weighting and channel splits

Upload date is only a patch proxy; it does not prove which client or balance
version produced a match. The plan uses it conservatively:

1. Drop subscriber-only, unavailable, date-missing, and duration-missing rows.
2. Form candidate-duplicate groups by normalized title + rounded duration +
   upload date. The group is atomic across splits, but this weak key is never
   called proof of duplication.
3. Put the newest 10% into a chronology test. Nothing in that test can train or
   tune the policy.
4. Hash remaining groups with seed 1064201: 10% validation and 90% training.
5. Within training sampling, weight videos relative to the newest upload:
   0-90 days = 4, 91-365 days = 2, older = 1.
6. Keep media-fingerprint groups atomic after stronger deduplication; if a
   duplicate spans an existing split boundary, move the entire group out of
   training and rebuild the manifest.

This supplies recent-patch emphasis without leaking the most recent matches
into training. An eventual verified client-version OCR field should replace
upload-date weighting when available.

## Card and deck coverage

No enabled-card or deck coverage is certified from current metadata.

Titles primarily contain player names, not decks. One of the ten latest titles
contains `MiniPekka`, but it is part of a player handle; counting it as card
usage would be false evidence. Exact card-name token matches are therefore
reported only as `uncertified_title_card_candidates`.

Thumbnail URLs are metadata, not card labels. Until thumbnail pixels are
visually classified and audited, they contribute zero certified card/deck
coverage. Even a visible troop is evidence of one deployed card, not the full
eight-card deck. Full deck coverage needs in-match hand/cycle reconstruction or
an independently authoritative deck source.

## Deduplication against the Hugging Face corpus

The two existing HF run manifests contain 2,000 completed UUID replay IDs and
zero explicit YouTube IDs. There is therefore no metadata key that can prove
or disprove overlap with this channel.

Cross-source status: **unresolved until bounded media fingerprints exist**.

Required fingerprint after clearance:

- normalize the arena crop at 10%, 50%, and 90% of match duration;
- store exact normalized-frame SHA-256 and perceptual hash for each point;
- pair candidates by duration within two seconds;
- call a duplicate only after at least two of three close perceptual matches
  plus visual confirmation of player/tower/clock state;
- place every confirmed duplicate group atomically in one split;
- never use title similarity alone to delete or merge a replay.

Because old HF raw files were intentionally deleted after compact publication,
building the HF side of this index may require bounded re-fetching of three
frames per replay. That must be planned separately; it was not performed here.

## Storage, transfer, and decode estimate

For 728.48 hours:

| Assumed average bitrate | Video bytes | 100 Mbps transfer | 1 Gbps transfer |
| ---: | ---: | ---: | ---: |
| 1.5 Mbps | 491.7 GB | 10.9 h | 1.09 h |
| 3.0 Mbps | 983.4 GB | 21.9 h | 2.19 h |
| 5.0 Mbps | 1,639.1 GB | 36.4 h | 3.64 h |
| Latest-ten observed 4.9245 Mbps | 1,614.3 GB | 35.9 h | 3.59 h |

These are decimal bytes and ideal link rates; real transfer will be slower.
A persistent bulk archive plus a full temporary copy would need roughly
1.0-3.3 TB depending on format. Streaming one match at a time and deleting raw
after verified compact publication avoids that peak, but does not resolve the
rights gate.

At 60 fps the corpus contains roughly 157.35 million frames. Full-frame
detection at the measured local 11 fps would take about 3,973 hours, so a full
decode/detector pass is not viable. The existing sparse UI/event cascade must
select frames before heavy detection; rented CUDA compute should be benchmarked
on the exact portrait crop rather than assumed to solve network or decoding.

## Bounded ten-video visual compatibility canary

The user-attested permission authorizes this bounded canary. The metadata
planner selects ten public videos deterministically to
cover:

- oldest and newest dates;
- shortest and longest durations;
- every observed resolution/fps signature where ten slots permit;
- deterministic fill across the inventory;
- both training-side and chronology-side metadata strata when available.

For each video, acquire only three five-second sections centered at 10%, 50%,
and 90%; no full-match download. Hash each section and record exact yt-dlp and
ffmpeg versions. Render audit frames with:

- detected arena crop and 18 x 32 logical grid;
- clock, phase, own elixir, four hand cards, and visible Next card;
- entity centers, HP bars, public status/effect cues, and confidence;
- candidate deployment point versus sprite box, explicitly noting that the box
  is not a hitbox;
- portrait overlay/letterbox masks so channel captions never enter the arena.

Acceptance requires all ten videos to have a stable crop or a typed rejection;
no silent rescaling. Manually inspect at least the three audit points per video.
Record orientation, HUD ownership, clock OCR error, card-event recall, strict
location agreement, HP coverage, overlays, edits/cuts, end screens, and any
spectator UI differences.

Before any training use, also require:

- zero subscriber-only media;
- full source/section SHA-256 provenance;
- explicit split and dedup-group assignment;
- no opponent/current policy input created from future-confirmed labels;
- cross-source HF duplicate audit completed or the videos quarantined;
- permission provenance remains exactly the user-attested basis above;
- the 10,000-video wave remains blocked until the canary passes and H100 access
  is coordinated.

## Validation

```bash
uv run ruff check \
  scripts/plan_tv_royale_youtube_source.py \
  tests/test_plan_tv_royale_youtube_source.py

PYTHONPATH=src:. uv run mypy \
  scripts/plan_tv_royale_youtube_source.py

PYTHONPATH=src:. uv run pytest -q \
  tests/test_plan_tv_royale_youtube_source.py
```
