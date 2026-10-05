# Phase B design note: in-probe public level read (not implemented)

Status: design only. No probe source, binary, APK or attestation pin was changed.

## Why

After Phase A, the level read is most of each decision. It takes about 10 dependent ADB shell round trips (4 pointer hops, count, vector, headers, HP components, backlinks, level words) plus one combined pid+stat trip at each end, about 0.18 s in total. The probe already walks the same object vector in-process for `observe`, where each field read costs nanoseconds.

## Measured cost structure after Phase A (host GPU, 8 full branches)

| Component per decision | Legacy | Phase A (fast + snapshot) |
| --- | ---: | ---: |
| ADB memory reads (10 exchanges) | 158 ms | 159 ms |
| pid + process start-time checks | 29 ms | 21 ms (combined into one exchange) |
| `observe-rich` transfer and parse | 65 ms | 53 ms |
| Frame compaction (full-frame hash) | 43 ms | 34 ms |
| Other probe calls (observe, status, step) | 18 ms | 7 ms |
| Total | 324 ms | 285 ms |

The micro-benchmark (`micro-bench-i1.json`) shows an idle ADB exchange takes about 5.3 ms, and each extra `dd` range inside a batch adds about 2.4 ms (16 ranges: 43 ms). The batched reads spawn one `dd` per body per batch, roughly 40–50 per decision, so device process spawns dominate the level read, not ADB latency. Phase A cannot remove that without changing the reader's device-side mechanism.

Rich payloads grow from about 1.1 MB to 8.2 MB over a game because the probe always retransmits all retained cumulative hook-telemetry events. The readiness runner already compacts those events away and never projects them. There is no transmit cursor (`transmit_from = retained_oldest` in `combat_event_telemetry.inc:1591`, `phase_runtime_telemetry.inc:968`, `remaining_runtime_telemetry.inc:2041`, `visibility_runtime_telemetry.inc:379`).

## Intermediate option without a rebuild (not implemented)

A single device-side reader process could perform the whole pointer walk and all range reads per frame and return the raw bytes. The host would then re-validate every pointer hop, identity, backlink and level bound from those bytes. That would remove about 45 `dd` spawns and 9 round trips per decision (inference: 185 ms down to roughly 10–20 ms). It needs a pinned helper (or a toybox shell script using `od`) and its own dual-read equivalence study. The probe binary and APK stay unchanged.

## Command

Add one new read-only command, **`observe-levels`**. Leave `observe` unchanged so historical ordinary-frame hashes stay comparable. The response would be:

```json
{"ok":true,"schema":"native-public-levels.v1","generation":G,"stateEpoch":E,"tick":T,
 "count":N,"objects":[{"slot":i,"nativeObjectId":id,"owner":o,"cardId":c,
 "hpComponentBacklink":true,"levelRaw":r,"level":r+1}, ...]}
```

- Include only objects whose HP component passes `read_hitpoints`: component slot 2 exists and its backlink `components[2]+0x08 == object`. That is the same body/character layout proof the host reader checks today with its `component_count` and backlink validation.
- `levelRaw` is `read_object_field<int32_t>(object, 0x120)`. The host adds 1 and bounds the result to 1..127, exactly as `scripts/read_native_public_levels.py` does now.
- Build the response under `g_control_mutex` with `observation_capture_identity_locked()`. It then shares identity and consistency semantics with `observe-atomic`.
- Also add `observe-rich-objects`: the same rich builder without cumulative trace arrays (or with a caller-supplied `since` sequence). Readiness frames are compacted to these objects anyway. The compact storage record must then change its `full_frame_json_sha256` provenance; declare that before any fresh use.
- Better still, add a `"levels"` array inside `build_atomic_observation_json_locked` (`cr_replay_probe.cpp` ≈5342). Ordinary objects, rich objects and levels would then come from one locked capture, which removes the host-side frame-equality bracket. The atomic payload still carries the cumulative telemetry traces, so a trace-free variant (for example `observe-atomic-lite`) would be needed to cut rich transfer cost as well.

## Where in `cr_replay_probe.cpp` (FirstLight 28d66cc)

- Command dispatch: `handle_control_command`, next to `observe` (≈6727) and `observe-atomic` (≈6781). The resident-mode prefix guard (≈6452) must list the new command too.
- Object loop to reuse: `build_observation_json` (≈4398). The per-object loop at ≈4566–4615 already calls `read_native_entity_identity`, checks `native_object_id_is_unique_in_vector` and calls `read_hitpoints` (≈4312).
- Level word: `object+0x120`. This is the host reader's `address + 0x120`, currently validated only on 15.535.86 / libg `110aa2b5…`.

## Rebuild and pins

The rebuild needs the NDK restore (10–30 min, see `cleanup-20260925.json`). It produces a new `probe_sha256`, a new full-attestation canonical SHA (replacing `864227bf…`) and a new runtime freeze, followed by fresh identical-execution floors. The APK and libg stay unchanged.

## Equivalence plan (gate before adoption)

1. **Dual read on live frames.** On opened development roots, at every decision of at least 4 roots × 2 candidates, run both the current host reader (`VerifiedNativeReadSession.read_levels`) and `observe-levels` on the same paused frame. Require identical `{nativeObjectId: level}` maps and identical body sets. The host reader stays the reference.
2. **Archived frames.** Restore late frames, such as the tick-3090 frame and the Phase A snapshot roots, and compare them the same way.
3. **Negative probes.** Use a frame with non-body objects (spells/projectiles, `hp: null`), destroyed towers, and objects spawned between reads. The host must reject a response whose generation, stateEpoch or tick differ from the bracketing `observe`.
4. **End to end.** Repeat the Phase A study with the in-probe read: identical public packet hashes, accepted-command streams and terminals versus the host-read path.
5. **Keep the old path.** The host reader remains behind a flag until a separate review accepts step 1–4. Level values are still read from native memory on every frame; nothing is cached.

## Expected effect

About 0.18 s of ADB reads would become one in-process call of a few milliseconds. With a trace-free rich variant, the remaining 87 ms of rich transfer and compaction would shrink to a few milliseconds too. The Phase A fast path would drop from about 0.285 s to roughly 0.02–0.04 s per decision, 7–14× (inference from the measured breakdown, not a measurement).
