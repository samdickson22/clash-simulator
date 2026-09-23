# TV Royale structured replay acquisition feasibility

Date: 2026-08-17 (America/Los_Angeles)

Scope: determine whether public TV Royale matches can yield structured action labels—card IDs, play times/ticks, and placement coordinates—without rendered-frame extraction. Investigation was limited to documented interfaces, public source material, passive metadata designs, and local read-only checks. No account was created or used, no credential or token was accessed, no form or message was sent, no emulator was started, no traffic was captured, no APK/tool was downloaded, and no client was modified.

## Decision

**No-go for ordinary public API, share-link, client-transport, and decoded-client acquisition. Permission-pending for a documented advanced/partner replay interface. A permission-cleared YouTube TV Royale archive is now the primary rendered-capture fallback; generic ADB capture from an owned physical device remains the gap-filling fallback.**

Structured replay commands would be materially more accurate than vision if acquired through an approved interface: they can directly encode a card global ID, native tick/time, actor side, and arena coordinates without animation, occlusion, frame loss, or UI-scaling error. However, no such interface is available to ordinary public API users today. The basic API exposes deck membership and match summaries, not action chronology. Passive modern-client traffic is expected to remain encrypted, while obtaining decoded objects would require methods that are contractually risky, version-fragile, and inside the predeclared stop boundary.

The one-day stop condition is therefore already met for technical extraction: do not continue into protocol-encryption defeat, invasive account-token extraction, hidden endpoints, client hooking/decompilation, APK repackaging, or per-version binary patching.

## Evidence

### 1. Ordinary official API: summaries and deck IDs only

The current first-party developer bundle says that the API provides near-real-time game data, requires a developer account and per-application key, binds keys to allowed IP addresses/rate limits, and requires a JWT on requests. See the [current Clash Royale developer bundle](https://developer.clashroyale.com/bundle.ffe769.js) and [developer portal](https://developer.clashroyale.com/).

Live unauthenticated checks on 2026-08-17 returned exactly:

```text
GET https://api.clashroyale.com/v1/cards
HTTP 403, 59 bytes
{"reason":"accessDenied","message":"Missing authorization"}

GET https://api.clashroyale.com/v1/players/%2300000000/battlelog
HTTP 403, 59 bytes
{"reason":"accessDenied","message":"Missing authorization"}
```

No credential was supplied. The public battle-log operation is documented as a list of recent battle results. Its schema includes match time, arena/mode, teams, opponents, and deck cards, but no per-play action list, timestamps, or coordinates. The older public Swagger snapshot is useful only for this interface distinction, not as a current exhaustive schema: [battle-log operation and schema](https://gist.github.com/loganlinn/d813ba0f9ccb47f34462ec8abeab8e14#file-swagger-yml).

Current operator evidence is more direct: a January 2026 RoyaleAPI response says chronology endpoints are not available to basic users and may be available only to advanced users such as tournament organizers or content creators. [RoyaleAPI operator answer](https://discuss.royaleapi.com/t/question-regarding-the-better-replay-interfaces-api/48611). A December 2025 response says there is no alternative public chronology source and explicitly asks developers not to scrape the user-facing replay tool. [Match chronology response](https://discuss.royaleapi.com/t/match-chronology-data/48260).

The ordinary API remains useful as side information if separately authorized: exact eight-card deck IDs can constrain vision classification and match-level metadata can validate a capture. Deck membership does not say which card was played, when, where, how often, or whether a champion/hero ability was used.

#### Authenticated portal inspection

With the user's explicit read-only authorization, the signed-in official developer portal was inspected on 2026-08-17 without opening any key detail, copying any credential, executing an API request, or changing account state. The visible documentation exposed these operations:

- Clans: `GET /clans`, `GET /clans/{clanTag}`, `GET /clans/{clanTag}/members`, `GET /clans/{clanTag}/warlog`, `GET /clans/{clanTag}/currentwar`, `GET /clans/{clanTag}/riverracelog`, and `GET /clans/{clanTag}/currentriverrace`.
- Players: `GET /players/{playerTag}`, `GET /players/{playerTag}/upcomingchests`, and `GET /players/{playerTag}/battlelog`.
- Cards and tournaments: `GET /cards`, `GET /tournaments`, and `GET /tournaments/{tournamentTag}`.
- Locations/rankings: `GET /locations`, `GET /locations/{locationId}`, `GET /locations/{locationId}/rankings/clans`, `GET /locations/{locationId}/rankings/players`, `GET /locations/{locationId}/rankings/clanwars`, `GET /locations/{locationId}/pathoflegend/players`, `GET /locations/global/seasons`, `GET /locations/global/seasonsV2`, `GET /locations/global/seasons/{seasonId}`, `GET /locations/global/seasons/{seasonId}/rankings/players`, `GET /locations/global/pathoflegend/{seasonId}/rankings/players`, and `GET /locations/global/rankings/tournaments/{tournamentTag}`.
- Events/leaderboards: `GET /events`, `GET /leaderboards`, `GET /leaderboard/{leaderboardId}`, and `GET /globaltournaments`.

No TV Royale, replay retrieval, battle chronology, per-action, partner, advanced, scope-request, or access-request operation was visible. Expanding the Swagger model list did reveal model names `Replay`, `VerifyTokenRequest`, and `VerifyTokenResponse`; critically, no visible operation referenced a replay retrieval or token-verification endpoint. A model name in the schema is not callable API access.

The account UI showed no current API keys. The blank key-creation UI exposed only `Key Name`, `Description`, and `Allowed IP Addresses`, with a maximum of five IP entries. It offered no scope selector or replay/partner toggle. The page states that generated keys cannot be edited; changing configuration requires creating a new key. The authenticated documentation says a JWT must be passed in every request through the Bearer `Authorization` header. No form field was populated, no IP was entered, and the empty form was discarded without submission.

### 2. Structured replay data exists, but access is privileged

Supercell's own profile of RoyaleAPI describes its Replay feature as a timeline view with detailed game statistics and post-game analysis. [Supercell Creator Spotlight](https://supercell.com/en/games/clashroyale/blog/community/creator-spotlight-royaleapi/). The user-facing RoyaleAPI replay page requires login, and its operator says it is for direct user use rather than third-party data extraction. This supports a crucial distinction: structured chronology exists, but existence is not public API authorization.

No documented public resource was found for:

- listing the current TV Royale feed;
- resolving a TV Royale entry to a public replay ID;
- retrieving a replay action stream by ID; or
- converting an in-game replay share into an externally fetchable payload.

The current public Clash Royale link-service HTML contains action keys for `add_friend`, `copy_deck`, `join_clan`, `scid_friend`, `support_creator`, and `voucher`, but no replay/TV Royale action. This is negative evidence, not proof that no private in-game share object exists.

### 3. Client transport: passive capture is unlikely to produce labels

The current Google Play listing states that Clash Royale data is encrypted in transit. [Google Play listing](https://play.google.com/store/apps/details?id=com.supercell.clashroyale&hl=en_US). A passive packet capture can reveal endpoints, ports, sizes, and timing but cannot by itself turn ciphertext into card IDs/ticks/coordinates.

Historical community implementations show both the value and fragility of decoded messages. Old protocol definitions model a TV Royale replay request and a compressed response: [HomeBattleReplay](https://github.com/royale-proxy/cr-messages/blob/master/client/HomeBattleReplay.json) and [HomeBattleReplayData](https://github.com/royale-proxy/cr-messages/blob/master/server/HomeBattleReplayData.json). Another archived implementation represents a replay with battle data, end tick, commands, events, random seed, and time; its placement command includes card/global ID and `px`/`py`, while the base command supplies ticks: [Replay.cs](https://github.com/BerkanYildiz/ClashRoyale/blob/master/ClashRoyale/Logic/Replay/Replay.cs), [DoSpellCommand.cs](https://github.com/BerkanYildiz/ClashRoyale/blob/master/ClashRoyale/Logic/Commands/DoSpellCommand.cs), and [Command.cs](https://github.com/BerkanYildiz/ClashRoyale/blob/master/ClashRoyale/Logic/Commands/Command.cs).

Those sources are from 2016–2018 and do not establish current message IDs, compression, field names, tick rate, or command IDs. Historical tooling explicitly required patched clients for payload decryption and became obsolete after protocol changes: [encrypted-payload limitation](https://github.com/weeco/supercell-packet-listener/blob/master/README.md#decrypting-the-payload) and [obsolete patched-client proxy](https://github.com/Galaxy1036/RC4toSodiumProxy#note). They are architectural clues, not a modern decoder.

Android's Network Inspector supports only `HttpsURLConnection` and `OkHttp`, so it is not a dependable observation point for a native/custom transport. [Android Network Inspector limitations](https://developer.android.com/studio/debug/network-profiler#troubleshoot-network-connection). Runtime hooks, memory dumps, repackaged instrumentation, crypto/socket interception, and binary-offset discovery are outside this study's allowed boundary.

### 4. Legal and operational boundary

Supercell's current Terms prohibit emulators and unauthorized software that modifies or interferes with the service, security-control circumvention, reverse engineering/decompilation/deciphering, and obtaining game information by methods not expressly permitted. They reserve account termination and say client updates may occur without notice. [Supercell Terms of Service](https://supercell.com/en/terms-of-service/).

The Fan Content Policy permits ordinary noncommercial guides, guide apps, and gameplay videos, but does not grant permission to extract or redistribute unpublished protocol/replay payloads. It also prohibits fan content promoting hacks, mods, automation, or interfering software. [Supercell Fan Content Policy](https://supercell.com/en/fan-content-policy/).

Player names/tags, clans, chat, device/network identifiers, and other identity-bearing fields should not enter the training dataset. Supercell treats player tags and gameplay/activity data as personal data. [Supercell Privacy Policy](https://supercell.com/en/privacy-policy/). Retain only deidentified action facts when the source authorization is clean.

This is operational and contract-risk triage, not jurisdiction-specific legal advice.

## Reliability comparison

| Target label | Ordinary API | Approved structured replay | Generic ADB + vision |
|---|---|---|---|
| Eight-card deck IDs | Exact | Exact | Inferable; API sidecar preferable |
| Card actually played | Absent | Direct | Observable with classification errors |
| Play time/tick | Absent | Native tick/time | Frame-derived; capture jitter applies |
| Placement coordinates | Absent | Native arena coordinates | Screen-derived; calibration/scaling error |
| Repeated card cycles | Absent | Direct command sequence | Observable but error-prone |
| Champion/hero ability | Absent | Potentially direct if schema includes it | Difficult and sometimes ambiguous |
| Version robustness | Public schema stable | Unknown until approved | High for capture; vision may need UI tuning |
| Current authorization | Basic API only, no chronology | Permission pending | Lower-risk when manual on owned physical device |

An approved structured feed would clearly beat vision. A client-derived structured feed does not beat vision operationally today because there is no verified modern decoding boundary and the likely escalation path is prohibited and brittle. The permission-cleared channel archive materially improves the vision option by supplying a large, consistent, high-frame-rate corpus without requiring replay acquisition from a live game client.

## Strongest safe candidate: permission-first advanced replay scope

No external contact or account action is authorized in this turn. The exact future authorization needed from the user is:

> I authorize Codex to create or use an account I control for the Clash Royale developer portal and/or RoyaleAPI, contact Supercell and RoyaleAPI, submit their access forms, and request written advanced/partner replay access for public TV Royale matches. The request may ask for card/global ID, actor side, play tick/time, placement x/y, and champion/hero ability actions, plus permission for automated collection, retention, deidentification, and private ML training. Do not access a game-account session/token, accept materially broader terms, publish raw payloads, or send credentials. Return any approval terms to me before using the endpoint.

Only if written scope is granted, run one conditional schema probe:

- **Budget:** at most 15 minutes wall time, one CPU core peak and less than 0.25 core average, 128 MiB RAM, 5 MiB network, and 20 MiB temporary disk; no GPU/MPS.
- **Requirements:** approved developer/partner account, scoped API key, and allowlisted public egress IP. No game account, root, emulator, capture proxy, client/APK change, or account-token extraction.
- **Success:** one public TV Royale replay returns direct card/global ID, actor/side, tick/time, and x/y values for at least five visible plays, with field meanings documented or confirmed by the provider.
- **Stop:** the scope is denied or unavailable; target fields are absent; retention/ML use is not authorized; or the next step would require scraping, hidden endpoints, encryption defeat, invasive tokens, hooks/decompilation, or version-specific patches.

Approval latency is external and may exceed a day; that does not justify technical circumvention. Until approval, this path remains permission-pending, not implemented.

## Permission-cleared YouTube rendered-capture fallback

The user reports that they personally contacted the owner of the public [TV royale YouTube channel](https://www.youtube.com/@TVroyale-tv1sn) and received explicit approval to use its videos. This report therefore treats reuse of that channel's videos as permission-cleared by the video owner.

User-supplied inventory evidence:

- 10,234 videos;
- approximately 728.5 total hours;
- coverage from 2024-03-29 through 2026-08-09; and
- predominantly complete portrait TV Royale matches at 59–60 frames per second.

That is an average of approximately 4.27 minutes per video and roughly 156 million source frames at 59–60 fps. It is large enough to become the primary rendered-data source for card-play timing and placement-label extraction, with the physical-device ADB path reserved for missing game versions, UI variants, or targeted validation captures.

The permission applies to the channel owner's videos; it does not grant a Supercell/RoyaleAPI developer account, API scope, replay payload, hidden endpoint, client instrumentation, or protocol-extraction permission. Those external account/contact actions remain expressly denied. Use of visible game assets also remains subject to Supercell's [Fan Content Policy](https://supercell.com/en/fan-content-policy/).

Before any bulk transfer, separately coordinate network/storage/CPU timing with the training task. Preserve the owner's permission evidence and a provenance manifest containing at least video ID, canonical URL, publication time, download time, source format, duration, dimensions, frame rate, and file digest. Do not retain comments, account cookies, viewer identifiers, or unrelated channel/account data. Deidentify visible player names/tags/clans before publishing or sharing derived data.

Recommended staged validation, once resource clearance is granted:

1. Select a deterministic 10-video sample spanning the date range and visible UI variants; do not optimize the sample against model performance.
2. Preserve source timestamps and frames without interpolation; derive play times from presentation timestamps rather than assuming exactly 60 fps.
3. Hand-label a held-out subset for card identity, play time, arena coordinate, missed/duplicate action, and champion/hero ability use.
4. Proceed to a larger batch only if decode is complete and the measured label error is suitable for training. Do not describe the corpus as ground truth merely because the videos are high-frame-rate.

No channel video was downloaded or inspected in this study. The inventory and permission facts above are user-provided; only the public channel identity was independently confirmed.

## Physical-device generic-ADB fallback

Use a user-owned physical Android device, an ordinary user-owned/guest game session, manual navigation to public TV Royale, USB debugging, and screen-only capture. Do not automate gameplay/UI input, install certificates, proxy traffic, inspect app storage, or use an emulator.

Android documents `adb shell screenrecord` as an MPEG-4 screen recorder with selectable resolution/bitrate and a maximum of 180 seconds per recording. [Android Debug Bridge screen recording](https://developer.android.com/tools/adb#screenrecord).

For a replay that may exceed three minutes, obtain continuous observable coverage with two manual passes of the same replay:

1. Record pass A from replay start through 180 seconds.
2. Replay the same item and record pass B beginning around visible game-clock 150 seconds through the end.
3. Align the 30-second overlap using the visible game clock and events; retain the higher-quality frames in the overlap.
4. Extract frames and infer plays offline. Calibrate the arena once per resolution/orientation; use deck IDs as classification candidates only when separately available through an authorized source.

Suggested capture settings: 1280x720, 6 Mbps, fixed orientation, taps hidden. Two full 180-second recordings are at most about 270 MB of video before container overhead. Expected per-replay acquisition is 10–15 minutes wall time, less than 0.5 host CPU core average, less than 256 MiB host RAM, no host GPU/MPS, and at most about 300 MB of device-to-host transfer. Vision preprocessing/training cost is separate.

Success criteria for the fallback should be measured, not assumed: on a hand-labeled held-out set, report card identity accuracy, play-time error, coordinate error in arena tiles, missed/duplicate action rate, and champion/hero ability accuracy. The fallback is operationally feasible but cannot claim structured-feed equivalence without those measurements.

## Artifacts and preservation

- No prototype was created because no safe public structured interface was found.
- No emulator, packet capture, account action, APK inspection/download, or client instrumentation was performed.
- No credentials or secrets were printed or stored.
- Training checkout, checkpoints, and PyTorch simulator were not touched.
