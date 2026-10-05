# Native observation throughput profile

The subsequent [verified branch-session change](branch-session.md) reduces repeated attestation while explicitly changing its frequency to session boundaries. The original per-read transport measurements below remain preserved.

The measured bottleneck is repeated attestation plus ADB/device process overhead. The optional persistent reader reduces late-frame median level-read time from **1.66 s to 1.31 s**, about **21%** in three alternating comparisons. It preserves the existing checks and does not change engine state, clocks, decision frequency or observations. It is not yet wired into the readiness runner.

## Evidence

The v6 reference game recorded 703 decisions and took about 24.8 minutes. Its archived frames contain 6–18 objects, averaging 11.05, and 6–16 bodies, averaging 10.43. The existing reader structure implies 33,985 Android `dd` invocations for that game and 11 host ADB subprocesses per frame. Its actual bounded memory payload totals only about 1.61 MB. These process counts are derived from the archived object/body counts and reader control flow, not an operating-system trace of v6.

On the owned paused six-tower initial frame, three batched level reads took 1.19–1.73 seconds. The measured components were:

- Attestation: 0.43–0.57 seconds per frame.
- Memory ADB calls: 0.67–0.76 seconds.
- PID lookup: about 0.041 seconds warm, 0.319 seconds on the first call.
- Ordinary snapshots and status together: about 0.05 seconds.

The coordinator then restored an opened development frame at tick 3090 using 59 recorded commands. It matched the archived gameplay fields. The profiler issued no configure, play, step, pause or resume commands.

| Reader | Samples | Host subprocesses/read | Read time |
| --- | ---: | ---: | ---: |
| Serial | 1 | 72 | 4.77 s |
| Existing batched | 3 | 11 | 1.44–1.97 s; median 1.66 s |
| Optional persistent | 3 | 1 | 1.16–1.47 s; median 1.31 s |

All seven reads returned exactly equal ordinary snapshots, 16 body/tower level values and attestation dictionaries. Neither transport needed recovery. The tick and final ordinary snapshot remained unchanged. The resulting both-seat public projections passed the existing checks. Paired improvements ranged from roughly 9% to 30%; these are three measurements on one crowded frame, not a general throughput confidence interval or a full-game timing comparison.

## Implemented change

`scripts/read_native_public_levels.py` now supports `persistent=True`. It creates one `adb shell -T sh` process for a single paused-frame read. Bounded requests use the device's verified `dd iflag=count_bytes,skip_bytes` support with a 4096-byte block size. Base64 framing separates arbitrary memory bytes from request delimiters. Each response has a size bound and timeout, and the owned shell process is reaped on success or failure.

The reader still reattests each call and checks ordinary frame equality, process identity on retry, object identities, owner/card metadata, body component layout, HP backlinks, level bounds and final paused-manager identity. It caches no identities, addresses, levels or attestation across frames. Existing serial and batched behavior remain the defaults. A caller can opt in with:

```python
read_levels(adb, port=26789, serial="emulator-5580", batched=True, persistent=True)
```

The probe binary and source were not modified. No auxiliary binary was built or installed. The only native child commands introduced are the read-only shell, `dd`, `base64` and framing output.

Validation: 116 focused transport and public-level tests passed. They include binary delimiter collisions, response bounds, timeout/EOF cleanup, short-read recovery, identity and backlink faults, stale frames and public level projection. Live parity covers one crowded paused frame; a new prospective full-game development run is still needed to establish end-to-end benefit.

## Large rich telemetry payloads

The v6 native JSONL expands to 4.44 GB. Near tick 3090, a row contains about 8.46 MB, mostly cumulative `phaseRuntime`, `combatEvents` and `remainingRuntime` traces. The live rich request at the restored late frame took 0.15–0.26 seconds for 8.36–8.44 MB. Diagnostic trace bytes grew between repeated requests while ordinary gameplay stayed identical. No payload was trimmed during live profiling.

Offline, parsing the late archived row took about 71 ms, re-encoding 46 ms and gzip level 9 about 40 ms. Thus host gzip is not the largest measured cost. On three archived frames, retaining only the rich object records and required epoch/coverage metadata reduced rows to 24–52 KB and preserved both public projections for the same own-history input. That experiment establishes a possible storage optimization; it does not remove native rich construction/transfer cost, and it has not changed the runner's logging contract.

The inspected pinned probe source has an exact `observe-rich` command and unconditionally appends the cumulative traces. `observe-atomic` calls the same rich builder, and `session-v1` delegates to the same command handler. No object-only or trace-disable command was found. No undocumented option was sent.

## Remaining work

The current change provides a measured improvement, but does not by itself make a large readiness study fast. Attestation still costs roughly half a second per read, and Android still launches one `dd` child per range. A separately pinned, read-only bounded memory helper could avoid those child processes without changing probe bytes, but that would be a separate implementation and validation decision. No attestation or level caching was introduced.

Artifacts: `fixed-cost.json`, `late-parity.json`, `offline-cost.json` and their corresponding profiling scripts. Runtime ownership and late-frame restoration are recorded separately under `m0/readiness/native-profile-startup-20260928/` and `m0/native-throughput/late-frame-3090/`. Existing v6 evidence remains unchanged.
