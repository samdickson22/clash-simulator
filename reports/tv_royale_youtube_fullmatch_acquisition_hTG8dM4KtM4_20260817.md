# TV Royale full-match acquisition evidence — `hTG8dM4KtM4`

## Result

One and only one complete public high-resolution source was downloaded from the
permissioned TV Royale channel. The pinned YoutubeDownloader/YoutubeExplode
path returned the same immutable original stream as the earlier section proof:

- source: `https://www.youtube.com/watch?v=hTG8dM4KtM4`;
- upload date: 2026-08-09, eight calendar days before acquisition;
- media: 1182x2560, nominal 60 FPS, VP9 video-only WebM;
- duration: 320.353 seconds;
- bytes: 184,451,016;
- SHA-256: `89817c51cb83689e210b19b41444be6928483c915c5582b5ad144f05f00b4d5b`.
- acquisition manifest SHA-256:
  `045b3da2bc2640126019675131ddfd2c13c797247102453ea8d00ad363925622`;
- total retained acquisition bytes, including the manifest: 185,499,904.

The source begins with the versus screen and ends with the winner/result screen.
It is a full match, not a section or a gameplay-only clip. Manual inspection was
used for this judgment; no semantic model ran.

The exact client build is **not** proven. Upload recency is a useful freshness
proxy, but neither the sanitized YouTube metadata nor the visible game HUD
identifies a client version.

## Permission and access

The permission basis is
`user_attested_channel_owner_approval`, attested 2026-08-17. The source was
public. No cookies, account, browser state, proxy, private token, or PO token was
used. YouTube license metadata was null; the permission attestation is not
misrepresented as a Creative Commons grant.

The existing wrapper enforces a 500 MiB declared and actual cap, writes through
an owned `.partial` path, and deletes that partial on failure. The successful
staging directory was published by same-filesystem directory rename only after
hash, probe, full decode, frame-index, and visual-boundary checks passed.

## Acquisition cost

The exact selected media response payload was 184,451,016 bytes: the stream's
declared size and completed file byte count match exactly. Download wall time
was 7.52 seconds, with 1.55 seconds user CPU, 0.85 seconds system CPU, and
153,092,096 bytes maximum RSS. Payload throughput was 24.528 MB/s.

The pinned wrapper does not count TLS records, HTTP headers, manifest response
bodies, or retransmissions. Therefore total on-wire traffic cannot be recovered
exactly after the run. The manifest deliberately records that wire-overhead
field as null instead of pretending the exact media payload is total network
traffic.

## Decode cadence and cost

The full file was decoded at 10 Hz because:

1. the current TV Royale vision pipeline's source cadence is nominally 10 FPS;
2. deployment and public play-event audits need 100 ms evidence resolution;
3. the exported policy's 400 ms decision cadence can aggregate later, whereas
   decoding directly at 2.5 Hz would irreversibly discard onset evidence.

FFmpeg decoded all 19,202 source packets and emitted 3,204 sequential sampled
frames at output time base `1/10`. Their PTS values are exactly 0 through 3,203,
covering target source times 0.0 through 320.3 seconds. Every sampled frame has
an individual SHA-256 in the FFmpeg framehash index, and all 3,204 hashes are
unique.

The pass took 27.17 seconds wall, 70.01 seconds user CPU, 1.12 seconds system
CPU, and 332,873,728 bytes maximum RSS. That is 117.924 sampled outputs/second,
706.735 decoded source packets/second, and 11.791x source real time.

Only the 359,068-byte framehash index was retained. Retaining decoded YUV420P
samples would have consumed 14,542,571,520 bytes (13.544 GiB). The index binds
every sampled image without duplicating that raw frame set.

## Timestamp/index contract

The retained source uses time base `1/1000`, starts at PTS 0, and reports average
and real frame rate `19001/317`. The framehash index uses output time base
`1/10`:

- `decoded_sample_index = output_pts`, zero based;
- `target_source_time_seconds = output_pts / 10`;
- `target_source_pts_milliseconds = output_pts * 100`;
- the per-row SHA-256 identifies the selected visual frame exactly.

The selected underlying source-frame PTS can differ slightly from the 100 ms
target because FFmpeg's `fps=10` filter selects from the approximately 59.94 FPS
source. Downstream code must retain source-relative time and must not interpret
the sample index as the visible battle clock. The visible clock requires its
own current-frame recognition.

## Visual constraint

The source is a spectator recording and visibly exposes both players' HUDs.
That is acceptable as offline evidence, but not as deployed actor input.
Downstream extraction must crop/mask the opponent HUD and must keep
spectator-only hand/elixir information out of the live-player feature contract.

## Artifacts

Publication root:

`/Users/sam/Desktop/code/clasher/datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4`

Important files:

- `source.webm` — complete immutable source;
- `manifest.json` — provenance, hashes, tools, commands, measurements and schema;
- `frame_index_10fps.framehash` — 3,204 timestamped SHA-256 frame rows;
- `source_probe.json` — exact stream probe;
- `audit_start_000500ms.jpg`, `audit_end_319500ms.jpg` — full-match boundaries;
- `fullmatch_contact_9up.jpg` — chronological manual-review contact sheet;
- `download_time.txt`, `decode_10fps_time.txt` — raw `/usr/bin/time -l` evidence.

No raw decoded frame directory, audio, semantic output, account state, or failed
partial remains.
