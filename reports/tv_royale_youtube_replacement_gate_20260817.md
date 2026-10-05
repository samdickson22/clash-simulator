# YouTube versus Hugging Face replacement gate — 2026-08-17

## Predeclared decision

Do not blend the permission-cleared YouTube channel into Hugging Face training
data by default.

If YouTube passes every safety-critical gate below and materially wins
freshness plus public-state/card coverage, all future human-video training
splits will be built from YouTube only. Hugging Face will remain only as a small
immutable out-of-domain regression/chronology set and will have zero sampling
probability during training.

If the ten-video canary cannot produce enough audited events for a threshold,
the result is `insufficient_evidence`, never an assumed pass. The 10,000-video
wave remains blocked until this gate passes and H100 execution is coordinated.

## Fixed comparison inputs

YouTube canary:

- ten public videos spanning playlist indices 1 through 10,234;
- upload dates 2024-03-29 through 2026-08-09;
- 191-321 seconds;
- 886/888x1920@59/60 and 1182x2560@60;
- estimated full selected-format bytes 1,132,101,073;
- permission basis `user_attested_channel_owner_approval`, dated 2026-08-17;
- no public Creative Commons claim.

HF comparison must use ten games matched as closely as possible by duration,
deck/archetype after extraction, and battle phase. Selection is fixed before
seeing outcome metrics. Existing HF type/location/public-state test splits may
provide labels, but no train split can tune the comparison.

## Existing HF baseline

The strongest current 1,000-game HF public-v2 run has:

- 29,722 public decision rows;
- clock/phase/own-elixir confidence on all rows;
- 20,713 own card-play identities and 9,009 no-ops;
- 4,610 strict visual placements from 663 games;
- 262,240 visible entity instances;
- measured entity HP on 148,153 instances (56.495%);
- measured motion on 101,329 instances (38.640%);
- 121,137 tower-HP measurements;
- 5,952 visible area-effect instances;
- zero measured stun/slow/haste/stealth/effect-progress fields;
- opponent-history and opponent-seen-card tensors of width zero;
- local public-v2 throughput 95.835 games/hour;
- raw acquisition median 19.166 seconds/game and extraction median 33.027
  seconds/game;
- average source transfer about 709.18 MB/game.

The held-out extraction evidence recovered all 62 upstream own-action events
at their source frame and identity, but this is not a complete opponent-event,
status, or placement-recall benchmark. Those fields remain `unknown`, not 100%.

## Safety-critical gates — every row must pass

| Gate | Predeclared YouTube threshold |
| --- | --- |
| Permission/access | Exact permission provenance retained; 10/10 public; zero subscriber/private/unknown media |
| Source integrity | Metadata, every downloaded section, decoded frame, overlay, and published manifest have verified SHA-256 |
| Layout | 10/10 videos either normalize to a versioned portrait layout or receive a typed rejection; no silently warped arena |
| Causality | Current policy inputs use only current/past public pixels; future-confirmed Next/action labels remain label-only |
| Split leakage | Zero replay/fingerprint group overlap; chronology newest 10%; validation and chronology never tune thresholds |
| Within-YouTube dedup | Confirmed duplicate/repost groups are atomic and cannot cross train/heldout splits |
| Card-event quality | Precision >=98%, recall >=95%, duplicate rate <=0.5%, p95 absolute timestamp error <=100 ms, at least 50 audited events |
| Clock/HUD | Clock coverage >=99% with MAE <=0.25 s; four-hand/Next identity precision >=99% and recall >=98%, at least 300 audited HUD frames |
| Strict placement | At least 30 audited labels; exact-tile accuracy >=90%, within-one-tile >=98%, false-label precision >=99% |
| Entity geometry | At least 300 audited entities; center inside visible body >=98%; boxes remain sprite bounds, never hitboxes |
| HP | Coverage no worse than HF by >2 percentage points; normalized bar-fill MAE <=0.08 on at least 100 audited bars |
| Opponent public events | Precision >=95%, recall >=85%, duplicate rate <=1% on at least 30 audited enemy play onsets |
| Status onset | Precision >=95%, recall >=80% on at least 20 visible status/effect onsets; no invented hidden remaining timer |
| Editing hazards | Every cut, caption overlap, speed change, orientation change, and end screen is detected or manually typed; zero accepted corrupted spans |
| Runtime bound | No >5 GiB canary; peak scratch and RSS recorded; no hidden full-video fallback |

If the canary does not contain 50 own events, 30 opponent events, 30 strict
placements, 100 HP bars, or 20 status onsets, extend only the bounded audit
sample after coordination. Do not weaken the denominator.

## Material-win gates

After all safety gates pass, YouTube must also satisfy all of these:

1. **Freshness:** at least four canary videos from the latest 365 days and
   visually compatible current-client HUD/mechanics; upload date remains a
   proxy unless exact client version is visible.
2. **Resolution/compression:** no worse OCR/card/event accuracy than HF and at
   least 2x linear arena/HUD pixel resolution on the recent layouts, without
   compression artifacts causing a safety regression.
3. **Coverage:** no public field regresses more than five relative percent from
   matched HF, and YouTube materially improves at least two of opponent-event,
   status-onset, strict-placement, enabled-card, or HP coverage.
4. **Enabled cards:** at least 25 distinct enabled played cards across the ten
   full matches, or `insufficient_evidence`; player-name/title tokens do not
   count.
5. **Deck/archetype diversity:** at least eight distinct reconstructed deck
   signatures and five archetypes across ten matches, with unresolved decks
   marked unknown rather than guessed.
6. **Neutral record and actor projections:** each spectator snapshot is stored
   once in absolute simulator/world coordinates. Two actor projections from the
   same record always share a split; each retains only that actor's own hand,
   Next, and elixir. Opponent HUD fields are excluded from actor tensors and may
   exist only as offline labels or privileged critic data. No image flipping.
7. **Cost:** normalized seconds and transferred bytes per accepted public event
   are <=1.5x HF locally, or an H100 benchmark proves the large-wave cost is
   lower. GPU speed alone cannot waive a quality gate.

## Matched result table to fill

| Metric | HF matched 10 | YouTube matched 10 | Winner/pass |
| --- | ---: | ---: | --- |
| Upload/client freshness | pending | 2024-03-29..2026-08-09 | pending |
| Arena/HUD effective resolution | pending | 886-1182 x 1920-2560 | pending |
| Clock coverage / MAE | pending | pending | pending |
| Hand/Next precision and recall | pending | pending | pending |
| Own card-event P/R/duplicate/p95 error | pending | pending | pending |
| Opponent-event P/R/duplicates | absent in current HF tensors | pending | pending |
| Strict placement yield/exact/within-one | pending | pending | pending |
| Entity center accuracy | pending | pending | pending |
| HP coverage / audited MAE | 56.495% corpus coverage / pending | pending | pending |
| Status onset P/R | no current scalar status labels | pending | pending |
| Cuts/captions/speed changes | pending | pending | pending |
| Accepted labels per transfer GB | pending | pending | pending |
| Distinct enabled played cards | pending | pending | pending |
| Deck signatures / archetypes | pending | pending | pending |
| Within-source leakage/dedup groups | pending | pending | pending |

## Dedup scope correction

Cross-source HF-versus-YouTube dedup is **not** a promotion blocker because HF
will never be mixed into YouTube training. The proposed 1.458 TB HF fingerprint
reconstruction is cancelled and must not be launched.

HF compact holdouts remain frozen with zero training sampling. YouTube still
requires within-source replay/repost grouping so duplicate channel videos
cannot cross train, validation, archetype, or chronology splits. Candidate and
confirmed YouTube groups are atomic.

## Replacement outcome

- `youtube_replace_hf`: every safety gate passes and all material-win
  conditions pass. Build YT-only train/validation/
  archetype/chronology manifests.
- `retain_hf`: YouTube fails any safety gate or does not materially win.
- `insufficient_evidence`: denominators are too small. Run only the bounded
  missing evidence step.

No mixed-training outcome exists in this gate.

## Canary result — current verdict

**Verdict: `insufficient_evidence`; keep YouTube out of training while the
sanitized two-actor contract is validated. Dual-HUD footage is not a terminal
source rejection.**

Acquisition itself passed:

- 10/10 public videos;
- 30/30 eight-second sections at 10%, 50%, and 90%;
- 120/120 hashed frames;
- 22,220,218 published bytes;
- 36,482,909 peak scratch bytes;
- 98.98 seconds wall time;
- all 150 retained media/frame artifacts hash-verified;
- all 30 MP4 sections fully decoded;
- zero retained partials, transient full videos, signed URLs, audio, cookies, or
  account secrets.

Stable acquisition manifest:

`datasets/external/tv_royale_youtube_section_canary_20260817/manifest.json`

SHA-256:

`db69125b82dbccd1e537962844761e1ac755166271711759a8dfe2a5d2a969d6`

The first unsanitized audit correctly failed closed:

- all 120/120 frames were typed-rejected as dual-HUD spectator UI;
- both players' private hands and elixir are visible;
- stable 296x640 sections provide only about a 282x438 arena;
- pinned yt-dlp master improved one section to 394x854, about a 376x585
  arena, still below HF's 428x683 arena and far below the predeclared 2x-linear
  material-win threshold;
- within-YouTube duplicate grouping and two-arm split coupling remain to be
  validated before training.

Portrait audit manifest:

`reports/tv_royale_youtube_portrait_audit_20260817/manifest.json`

SHA-256:

`639d3a11ee0785ae9a4a4c1a68e7cbd19f546bbbbe3c01c6fc3d24be22024432`

The raw spectator frame itself must never enter live actor inference. It may be
used only inside the offline corpus extractor to create one neutral match
record:

- absolute/world arena entities, positions, HP, statuses, effects,
  projectiles, towers, and clock;
- both players' observed hand, Next, and elixir;
- detected play and deployment events;
- one stored snapshot shared by both actor projections.

Actor projection is data selection, not image transformation. `actor_id` and
team select the actor's own HUD fields; the opponent hand/elixir are excluded
from actor tensors and may be exposed only through separately typed offline
label or privileged-critic channels. Coordinates remain absolute simulator
coordinates, and existing observation/action canonicalization handles player
perspective. Bottom and top projections from a snapshot are inseparable for
split assignment. The second projection counts toward 2x only when that
player's hand, Next, and elixir are complete.

Canonicalization must call the existing `DiscreteTileActionSpace` and
`StructuredObservationBuilder` paths rather than reimplementing transforms:
actor 1 maps integer tiles `(x, y)` to `(17-x, 31-y)`, continuous positions to
`(18-x, 32-y)`, negates facing/motion vectors, swaps own/team semantics, and
uses existing action encode/decode for placement IDs. Actor 0 uses the existing
identity path. Promotion requires round-trip tests covering continuous
positions, vectors, tiles, lanes/towers, and action IDs.

Pinned master evidence:

- yt-dlp commit `f1896c57f5ba4b92741bb509790837d6838ec99e`;
- yt-dlp-ejs 0.8.0, curl-cffi 0.15.0, Deno 2.9.5;
- direct VisionOS HLS format 606;
- 394x854 H.264 video-only, 8.008 seconds, 537,589 bytes;
- one-section manifest SHA-256
  `732abf9d89b6efba191700c18e1fdbda7c5065b621f8e5a7bb8d2f8f8f8c0db8`.

Pinned current yt-dlp solved direct 480p access. An independent pinned
YoutubeDownloader.Core/YoutubeExplode gate subsequently retrieved the original
1182x2560@60 VP9 stream without cookies, accounts, or a PO token. Its sanitized
10-second proof has an approximately 1128x1687 arena, exceeding the 2x-linear
HF resolution threshold:

- high-resolution manifest SHA-256
  `207e6af984ffba9c8de350bbe3a42b4ae2ddfe450a6ab0e3d425fe648fb5c31e`;
- retained section SHA-256
  `89f35a98c78f5f990a1e9e9e4d7def1e7e184ffe47ebf787e4afa3dbca421dab`;
- five exact frames; 7,942,101 published bytes; 190,346,279 peak scratch;
- the 184,451,016-byte transient original was hash-verified then deleted.

The authorized all-ten high-resolution retry stopped before bytes when the
public endpoint became temporarily unavailable across bounded retries. No
partial survived. Continue the 120-frame low-resolution sanitizer validation
and five-frame high-resolution proof now; retry high-resolution acquisition
only after endpoint cooldown.

### Neutral-record readiness result

The corrected neutral offline architecture passes its geometry/privacy schema
gate but has not yet passed semantic extraction:

- 120/120 low-resolution dual-HUD frames are eligible as offline neutral source
  frames; zero rejected;
- ten replay split groups;
- zero structured neutral snapshots decoded;
- zero actor examples currently ready;
- 240 actor projections are potential only after both player HUDs and the
  neutral public state are decoded completely;
- five of five original-resolution proof frames are neutral-source eligible;
- high-resolution arena is 1128x1687, 2.636x/2.470x HF linearly;
- actor projection requires exactly four hand identities and positive
  confidences, Next card and confidence, and elixir and confidence;
- incomplete HUD state produces typed `incomplete_actor_hud` and cannot count
  as a second actor example;
- counterfactual changes to one player's private state cannot change the other
  actor projection.

Neutral readiness manifest SHA-256:

`360d483a8f92aefbc45cc1595ec4ef31b638eb7d2900144f7913a45b2f6354d9`

High-resolution proof manifest SHA-256:

`1f4f82a6e86edc6aad99b09a6d45e46593507661cd83a34084ad16a67c7e86f3`

A separate production-live pixel sanitizer also passes: 120/120 frames
accepted after exporting only arena, isolated clock, and bottom own HUD; 360
production artifacts hash-verified; zero raw-frame caching. Its manifest
SHA-256 is
`39708dc0663ee59432ce005900215e48771ac96333cb1e2484f7cfb995bb3979`.

This sanitizer is not the offline corpus representation. Offline extraction
uses the full spectator frame inside a separately typed extractor to create the
neutral structured record. The immediate blocker is now semantic decoding of
entities/HP/status/effects/projectiles/towers/clock, both HUDs, and play/
deployment events—not dual-HUD geometry.

## HF files: report only, do not delete

Current TV Royale/HF candidate storage groups:

| Candidate group | Top-level paths | Bytes |
| --- | ---: | ---: |
| Derived raw-cascade families | 19 | 1,319,818,568 |
| Derived public-v2 families | 8 | 37,820,826 |
| External TV Royale raw/parquet assets | 11 | 2,640,331,976 |
| Legacy top-level TV Royale corpora | 57 | 7,475,997 |
| **Total** | **95** | **4,005,447,367** |

Glob roots, to be resolved to explicit paths again immediately before any
deletion:

```text
datasets/derived/tv_royale_raw_cascade*
datasets/derived/tv_royale_public_v2*
datasets/external/tv_royale*
datasets/tv_royale_*
```

Proposed immutable HF regression allowlist after replacement proof:

```text
datasets/derived/tv_royale_public_v2_post260_split_seed1056502
datasets/derived/tv_royale_raw_cascade_2000_locations_split_seed1045801
```

Those two directories currently total 6,745,307 bytes. The maximum currently
reported removal candidate after preserving them is therefore 3,998,702,060
bytes. This number is an inventory, not deletion authorization. Recalculate
file-level paths, sizes, digests, references, and recoverability immediately
before any future removal. Existing HF files remain untouched now.
