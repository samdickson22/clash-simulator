# TV Royale YouTube canary metadata — 2026-08-17

## Outcome

Ten public videos were selected by sparse playlist age quantiles, including the
newest index 1 and reported oldest index 10,234. All ten full metadata pages
resolved as public; no inaccessible candidate needed replacement. No video,
audio, thumbnail, comment, or subtitle media was downloaded.

The sample spans 191–321 seconds and four observed portrait signatures:
1182x2560@60, 886x1920@60, 888x1920@60, and 888x1920@59. The selected
highest-resolution video-only formats total an estimated 1,132,101,073 bytes
for 2,533 seconds. This estimate is metadata-derived, not bytes transferred.

## Selected videos

| Playlist index | ID | Upload date | Duration | Dimensions/FPS | Selected format estimate |
| ---: | --- | --- | ---: | --- | ---: |
| 1 | [hTG8dM4KtM4](https://www.youtube.com/watch?v=hTG8dM4KtM4) | 2026-08-09 | 320 s | 1182x2560 @ 60 | 184,451,016 B |
| 1,138 | [i4WTQPAh0_E](https://www.youtube.com/watch?v=i4WTQPAh0_E) | 2026-05-15 | 213 s | 1182x2560 @ 60 | 138,690,318 B |
| 2,275 | [BL0s-x4E_ZQ](https://www.youtube.com/watch?v=BL0s-x4E_ZQ) | 2026-02-24 | 321 s | 1182x2560 @ 60 | 235,615,929 B |
| 3,412 | [i1AyFVBDsPE](https://www.youtube.com/watch?v=i1AyFVBDsPE) | 2025-12-03 | 221 s | 886x1920 @ 60 | 78,106,938 B |
| 4,549 | [iW_07-RIjJk](https://www.youtube.com/watch?v=iW_07-RIjJk) | 2025-08-25 | 293 s | 886x1920 @ 60 | 97,264,929 B |
| 5,686 | [nXNp3GRdFks](https://www.youtube.com/watch?v=nXNp3GRdFks) | 2025-05-23 | 319 s | 886x1920 @ 60 | 113,187,313 B |
| 6,823 | [yS3akCAdr6A](https://www.youtube.com/watch?v=yS3akCAdr6A) | 2025-02-21 | 205 s | 886x1920 @ 60 | 64,099,478 B |
| 7,960 | [aVnmZEXSgiI](https://www.youtube.com/watch?v=aVnmZEXSgiI) | 2024-11-17 | 209 s | 886x1920 @ 60 | 68,048,603 B |
| 9,097 | [Xf8Y9GdxlLo](https://www.youtube.com/watch?v=Xf8Y9GdxlLo) | 2024-08-07 | 191 s | 888x1920 @ 60 | 71,772,618 B |
| 10,234 | [0aBzIYe-FaA](https://www.youtube.com/watch?v=0aBzIYe-FaA) | 2024-03-29 | 241 s | 888x1920 @ 59 | 80,863,931 B |

Titles were deliberately omitted from sanitized artifacts and were not used to
make card, deck, arena, or gameplay claims.

## Permission and access provenance

- Channel: `https://www.youtube.com/@TVroyale-tv1sn`
- Permission basis: `user_attested_channel_owner_approval`
- Attestation date: `2026-08-17`
- Public Creative Commons license claimed: **no**
- YouTube license metadata: null on all ten selected pages
- Subscriber-only, private, and unavailable entries: excluded

The permission attestation is distinct from YouTube license metadata and is not
reinterpreted as a Creative Commons grant.

## Reproduction

Tool: `yt-dlp 2026.07.04` through `uvx`.

Sparse candidate enumeration:

```bash
uvx yt-dlp --flat-playlist \
  --playlist-items 1,1138,2275,3412,4549,5686,6823,7960,9097,10234,10200,10000,9500,8500 \
  --dump-json --skip-download --no-write-thumbnail --no-write-comments \
  --no-warnings 'https://www.youtube.com/@TVroyale-tv1sn/videos'
```

The selected public watch URLs were resolved together with:

```bash
uvx yt-dlp --dump-json --skip-download --no-write-thumbnail \
  --no-write-comments --no-warnings --no-playlist \
  'https://www.youtube.com/watch?v=hTG8dM4KtM4' \
  'https://www.youtube.com/watch?v=i4WTQPAh0_E' \
  'https://www.youtube.com/watch?v=BL0s-x4E_ZQ' \
  'https://www.youtube.com/watch?v=i1AyFVBDsPE' \
  'https://www.youtube.com/watch?v=iW_07-RIjJk' \
  'https://www.youtube.com/watch?v=nXNp3GRdFks' \
  'https://www.youtube.com/watch?v=yS3akCAdr6A' \
  'https://www.youtube.com/watch?v=aVnmZEXSgiI' \
  'https://www.youtube.com/watch?v=Xf8Y9GdxlLo' \
  'https://www.youtube.com/watch?v=0aBzIYe-FaA'
```

Temporary raw metadata hashes:

- sparse flat JSONL: `0e3f6bbd2b2ccd9695d3b8fa0d287bdd8b19fb879d86e6196b34f219b9d555f6`
- full selected JSONL: `473bf5b0890873e75d93f98af4dc1c1249e2b010fe486346c014eec3a96d982b`

Raw yt-dlp metadata is intentionally not retained in the repository because it
contains large transient format URL fields. The sanitized JSONL and manifest
retain only stable identifiers, access, date, duration, format, estimate, and
permission fields.

Sanitized artifact hashes before this report embedded them:

- `datasets/source_metadata/tv_royale_youtube_canary_20260817/metadata.jsonl`:
  `8bd638c28092deafe27fb2ca5b0091305d48769e2d2295ac0d03e54507db6275`
- `datasets/source_metadata/tv_royale_youtube_canary_20260817/manifest.json`:
  `c272d523b8038df26bfed0aaf9c331ce5c27ffabdad7aeeeffac89534615259c`
