# Bounded transport proof, prepared offline

Nothing in this plan starts automatically. The lead ended the capture block at04:09Z; no further emulator boot is currently authorized. A measured emulator/Mac-to05 rate requires a separately authorized short test with the ladder stopped, a fresh pause marker and all runtime gates passing. The one-core05 replay result is only a component test.

The prepared artifact is `/mpac/sdicks02/scratch/nulls/build/transport-proof-offline01`, manifest SHA256 `260a7c02eec03c24a0c999c3b4135edbfa9f9a44a16e49b77db124e99d9e2318`; separate05 tools are in the adjacent `transport-proof-offline01-tools`. It was built and manifest-verified offline, not deployed. It uses the reviewed24 runtime logic with a new namespace and an explicit eight-scenario test plan. The new artifact itself has no independent Sol GO. Source plan: `live/nulls/transport-proof-plan.json`.

Rebuild into unused directories with the05-only builder:

```sh
python -B live/nulls/full_bundle.py \
  --out /absolute/unused/bundle-directory \
  --profile grpc-burst \
  --namespace full-fresh-proof-name \
  --plan live/nulls/transport-proof-plan.json
```

For an authorized test, use at most five minutes including cold boot and cleanup, one windowed1536MiB/two-core/nice10 reference instance, adb5049/emulator5596/probe26795/gRPC8596. Supply fresh absolute lease times to the reviewed runtime and start exactly one checksum importer first. Keep the10GiB disk floor, normal pressure, zero-swap memory rule/allocated500MiB floor, marker/no-driver/shared-lock proof and all shipping limits. No retries, app resets, package changes or live-client input. End immediately on a safety failure or expiry; confirm PID exit and empty own adb devices, then stop the owned adb server by identity/PID.

Capture the full physical1080×2280RGB888 framebuffer with no scaling or crop. The candidate logical1080×1920 game viewport is x0–1080/y180–2100; `frame_geometry.py` reports this as unverified. Inspect actual orientation and letterboxing against the six tower composite centres. Keep full source images and native-pixel calibration; any QA crop must retain its transform and source hash. Do not reuse the pilot07 offset or silently flip owner mapping.

Measure the actual frames passing05 checksum verification per second since the first verified frame, along with native SDK production rate, sequence gaps, shipping latency, spool size and pressure/disk. A useful pass is several verified real frames/s sustained for at least30s, ideally300 or more verified native frames, with headroom maintained and all data held. Record failures as failures; the fixture replay does not satisfy this pass. Give r3 the first real burst for independent orientation, camera and team checks. Pose boxes, phase/cue audits and complete=true admission remain separate gates.

The test plan tries explicit card/team/seed scenarios with eight bursts each and skips unavailable starting-hand cards honestly. These are queued scenarios, not automatic lifecycle retries. Runtime returns through cleanup when work finishes; a short externally supplied lease bounds the whole test. After a successful measured test, estimate the121-card/two-team sweep from the measured delivery and admission rates before proposing another capture block.
