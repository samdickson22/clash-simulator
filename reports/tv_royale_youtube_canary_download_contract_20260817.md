# TV Royale YouTube canary download contract

This is a bounded acquisition contract, not bulk-download authorization.

## Input schema

`scripts/download_tv_royale_youtube_canary.py` accepts JSON with schema
`clasher.tv_royale.youtube_metadata_canary.v1`:

```json
{
  "schema": "clasher.tv_royale.youtube_metadata_canary.v1",
  "permission_provenance": {
    "basis": "user_attested_channel_owner_approval",
    "attested_on": "2026-08-17"
  },
  "videos": [
    {
      "id": "elevenChars",
      "url": "https://www.youtube.com/watch?v=elevenChars",
      "availability": "public",
      "access_class": "public",
      "duration_seconds": 240.0,
      "predicted_video_bitrate_bps": 2000000.0
    }
  ]
}
```

`filesize_approx_bytes` may replace `predicted_video_bitrate_bps`; bitrate is
then derived from full duration. Unknown, private, subscriber-only, duplicate,
non-YouTube, or more-than-ten sources fail closed. Permission basis and date
must match exactly. The prediction includes a 1.25 safety factor and must not
exceed 5 GiB.

## Acquisition and publication

Remote FFmpeg section seeking, high-resolution video-only native transfer, and
bounded high-resolution byte ranges were tried first and all failed closed at
the CDN's HTTP 403/416 boundary. The only public format that transferred without
a private PO token was the mobile-web progressive format 18 (360p, transient
video plus audio). The bounded fallback downloads one such source at a time into
monitored staging with yt-dlp, Deno/EJS, curl-cffi Chrome impersonation, forced
IPv4, and `--no-playlist`. FFmpeg locally re-encodes exact video-only
eight-second sections (stream copy was rejected after a 12.35-second keyframe
overrun)
centered near 10%, 50%, and 90%, explicitly maps only `0:v:0`, and removes audio.
The transient full source is hashed and immediately deleted before the next
video. The conservative prediction counts
all transient full sources despite that sequential deletion. FFprobe rejects
any non-video
stream or an overlong section. FFmpeg extracts an audit frame every two seconds.

The output schema is `tv-royale-youtube-section-canary-v1`. It records:

- immutable input-manifest path and SHA-256;
- permission provenance and byte limits;
- yt-dlp, FFmpeg, and FFprobe versions;
- every exact argv vector;
- requested section bounds, probed duration, and stream types;
- size and SHA-256 for every section and every generated audit frame.
- size and SHA-256 of each transient video-only source, plus deletion status.
- completed/requested section coverage;
- per-source and total wall time, recorded command time, peak scratch bytes,
  retained bytes, and stabilized published total bytes for matched cost analysis.

Commands run in a uniquely owned staging directory whose total bytes are
monitored. Exceeding 5 GiB, a command/probe failure, zero frames, or any other
exception deletes that staging directory. `manifest.json` is written atomically,
the final total is checked again, and only then is the directory atomically
renamed into place. An existing destination is never overwritten.
Expiring signed media URLs are redacted from recorded stdout and error text.
The sanitized input manifest hash is checked before publication so metadata
cannot change underneath a run.

## Invocation

```bash
PYTHONPATH=src:. uv run python scripts/download_tv_royale_youtube_canary.py \
  --metadata-manifest /absolute/sanitized_canary_metadata.json \
  --output-directory /absolute/tv_royale_youtube_canary
```

No network download may begin until the sanitized manifest has passed this
validation. The resulting canary still requires visual portrait/grid audit
before any larger wave is considered.

## Executed canary evidence

The bounded run published atomically at
`datasets/external/tv_royale_youtube_section_canary_20260817`.

- manifest SHA-256:
  `db69125b82dbccd1e537962844761e1ac755166271711759a8dfe2a5d2a969d6`
- source metadata SHA-256:
  `c272d523b8038df26bfed0aaf9c331ce5c27ffabdad7aeeeffac89534615259c`
- coverage: 10/10 videos, 30/30 sections, and 120 audit frames
- retained artifacts: 150 hashed files (30 sections plus 120 frames)
- conservative predicted bytes: 1,545,649,652
- published bytes: 22,220,218
- peak scratch bytes: 36,482,909
- wall time before manifest: 98.98 seconds
- validation: all 150 size/SHA records matched and all 30 MP4s fully decoded
- cleanup: no transient full source, partial directory, or signed media URL was
  retained

The first inspected frame was a clear portrait arena at 296x640, but it exposed
spectator HUDs for both players, including both hands/elixir. Therefore this
successful acquisition is **not** visual-training approval. The downstream
portrait audit must fail closed or prove an arena-only crop/mask that removes
spectator leakage. The 360p resolution is also an explicit quality limitation.

## Pinned yt-dlp master gate

The current stable release path required the 360p mobile-web fallback, but the
same one-video section was retested with the following exact dependency set:

- yt-dlp git commit:
  `f1896c57f5ba4b92741bb509790837d6838ec99e`
- yt-dlp reported version: `2026.07.04`
- yt-dlp-ejs: `0.8.0`
- curl-cffi: `0.15.0`
- Deno: `2.9.5`

That pinned master selected VisionOS HLS format 606 and downloaded the requested
28-36 second range directly, without cookies, secrets, a PO token, or a full
transient video. The atomic evidence is at
`datasets/external/tv_royale_youtube_yt_dlp_master_canary_20260817`:

- manifest SHA-256:
  `732abf9d89b6efba191700c18e1fdbda7c5065b621f8e5a7bb8d2f8f8f8c0db8`
- section SHA-256:
  `04b88a705c8b446e973bb87bd92ce3b1a7e98b4ffd88294f0ac262dd35eb1d6b`
- media: H.264 video-only, 394x854, 29.97 fps, 8.008 seconds
- section bytes: 537,589; published bytes: 913,046
- wall time before manifest: 3.865 seconds
- four generated audit frames, each hashed

This independently solves the CDN access boundary more cleanly and improves
360p to 480p. It does not solve spectator-HUD leakage. A subsequent explicit
follow-up authorized the independent YoutubeDownloader.Core test below.

## YoutubeDownloader.Core / YoutubeExplode independent gate

After an explicit follow-up request, a minimal headless wrapper was built at
`tools/youtube_explode_canary`. It uses the exact network construction from
YoutubeDownloader.Core: a `YoutubeDownloader` user agent, YoutubeExplode, and an
empty cookie list. It does not load a GUI, cookies, an account, browser state,
or a PO token.

Pinned inputs:

- YoutubeDownloader commit:
  `bbcff039515a2ac985e3769f0243a58645a52b28`
- YoutubeExplode commit/tag/package:
  `a268db97feb1689b3f5eab18fdbc73f983a21ce5`, `6.6.1`, `6.6.1`
- .NET SDK/runtime: `10.0.100` / `10.0.0`
- dotnet-install script SHA-256:
  `082f7685e156738a1b2e2ed8381a621870d4ce8e8c59278034556f05c186eb2e`

The wrapper enforces a 500 MiB declared and actual byte cap and writes through
an owned `.partial` file. Its first real request succeeded and downloaded the
original 1182x2560, 60 fps, VP9 video-only stream: 184,451,016 declared and
actual bytes in 11.79 seconds. Later attempts were rejected before downloading
any bytes with YoutubeExplode `VideoUnavailableException`, indicating the
public player endpoint is currently intermittent/rate-limited on this host.
The wrapper therefore uses at most three manifest attempts with bounded 10- and
20-second backoff. A subsequent bounded run succeeded and atomically published:

- root: `datasets/external/tv_royale_youtube_explode_highres_canary_20260817`
- manifest SHA-256:
  `207e6af984ffba9c8de350bbe3a42b4ae2ddfe450a6ab0e3d425fe648fb5c31e`
- original video-only stream: 1182x2560, 60 fps, VP9, 184,451,016 bytes
- transient source SHA-256:
  `89817c51cb83689e210b19b41444be6928483c915c5582b5ad144f05f00b4d5b`
- retained section: 1182x2560 H.264 video-only, 9.993 seconds, 5,895,263 bytes
- retained section SHA-256:
  `89f35a98c78f5f990a1e9e9e4d7def1e7e184ffe47ebf787e4afa3dbca421dab`
- five generated and hashed audit frames; full MP4 decode passed
- successful download: 8.223 seconds; section processing: 1.999 seconds
- peak scratch: 190,346,279 bytes; published: 7,942,101 bytes

The original stream was hashed and deleted before atomic publication. No
cookies, account state, browser state, secrets, or PO token were used. All
failed staging directories were removed. This solves direct-original resolution
access, but the source remains a dual-HUD spectator recording; crop/mask QA is
still mandatory before using it as non-leaking training input.

### Full-ten high-resolution attempt

Visual QA confirmed that the proof frame's approximately 1128x1687 arena clears
the replacement-resolution gate. A compatible full-ten collector was therefore
added at `scripts/download_tv_royale_youtube_explode_canary.py`, with sequential
500 MiB transient limits, 5 GiB total limit, full section decode, hashes, and
atomic cleanup.

The authorized run stopped fail-closed at video one before downloading bytes:
the public YoutubeExplode player-manifest endpoint returned
`VideoUnavailableException` on all three attempts with bounded 10- and
20-second backoff. A one-time forced-IPv6 audit reached the same boundary. No
partial directory survived. Since the identical pinned path had already
succeeded twice at 1182x2560, this is current endpoint intermittency/rate
limiting rather than lack of high-resolution capability. No cookies, account,
PO token, proxy, or identity rotation was introduced. The collector is ready
for a later cooldown retry; acquisition was not expanded beyond the authorized
ten-video manifest.
