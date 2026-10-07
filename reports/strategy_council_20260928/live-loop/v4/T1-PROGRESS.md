# T1 progress

Implementation started on 2026-10-07 on the Mac mini. No Phase A match has started yet. T2 holds the one owned emulator until its bench and stale-frame reproduction finish.

The retained L2 launcher's historical base config had been removed with old artifacts. Launch reached the verified attestation, then failed reading that missing file. Recovered the same owned emulator using L2 pair 00's retained setup config, rechecked both UID firewall rules and the exact attestation, and wrote `base-config.json` and `emulator-host/complete.json`. No APK or hook changes were made. `launch.py` makes this repair repeatable without changing old L2 files.

Current owner is emulator-5584, adb 5042, gRPC 8558 and probe 26794. Backend is host GPU, with two emulator cores and 3 GiB. The other project's UTM VM, Stage 6 workers, old adb 5041 and transfer jobs are untouched. One emulator keeps Phase A at about 24 hours of active collection wall time, plus setup and transfer.

The split is prepared in `split.json`. The pipeline freezes the final content manifest before smoke or Phase A. Smoke uses three separate seeds at normal, double and triple-elixir starts. No training is launched. Data buffer is `~/.cache/clasher-live-v4/buffer`; finalized data goes only to `127x02:/mpac/sdicks02/repos/clasher-v4-data/matches/`. Local `data/` holds compact checksummed receipts. The hub's first real two-file checksum rehearsal passed. Negative checksum and local-mutation tests preserve all local media.

The collector checks a 400 MiB new-match reserve against the 6 GB buffer cap and 15 GiB free-disk floor. It checks a 32 MiB reserve every second while encoding. Transfer failures pause new matches. Partial matches retain their files and rerun the same frozen seed. Matches are complete only after atomic `receipt.json`; local media deletion follows a hub recomputation of every SHA256 and a matching acknowledgement.

## Resume

First inspect `pipeline-state.json`, `pipeline.log`, the stage logs and process commands. Do not start a duplicate driver. The persistent driver uses a file lock and serially completes T2, reproduction, freeze, three smoke matches, and Phase A.

```sh
reports/strategy_council_20260928/pilot/detach.sh \
  reports/strategy_council_20260928/live-loop/v4/pipeline.log \
  reports/strategy_council_20260928/live-loop/v4/run.sh pipeline \
  .venv/bin/python -u reports/strategy_council_20260928/live-loop/v4/pipeline.py
```

Read counts without touching the renderer:

```sh
.venv/bin/python scripts/collect_l1_stream_v4.py --status
```

If the owned emulator died, use the same detach/run wrapper with `launch.py NEW_RECEIPT_DIRECTORY`. It refuses to adopt an existing foreign serial. It writes the new complete owner receipt to `emulator-host/complete.json`. If startup stopped during adbd root restart, use a fresh output directory and `--resume-owned PREVIOUS_LAUNCH_DIRECTORY`, matching L2's recovery protocol. Do not kill a shared adb server.

If smoke fails, Phase A is not admitted. Fix the infrastructure defect, record the incident here, archive the old freeze and smoke evidence, and refreeze before Phase A. Once Phase A starts, source changes require a dated deviation and preserved old manifests. Neither a prepared runner nor a successful checksum rehearsal is an accepted smoke match.

2026-10-07 15:32:11 -0700: Frozen 404 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 15:37:08 -0700: T1 freeze remains intact. T2 restarted with public-mask legal placements; prior fixed-tile trials are diagnostic only. New bench worker 8559. The serial driver waits before smoke and Phase A. No collection match has started.

2026-10-07 15:45:49 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

The converter accepts either one finalized match or the hub's `matches/` directory. It excludes smoke and metadata receipts from a bulk conversion. Its output contains `manifest.json`, `videos/`, and `audit/`, ready for the unchanged v3 trainer's dataset and audit arguments. A two-match test decoded real H.264 outputs and checked frame/event label round trips. Source-only amendments occurred before any collector smoke; prior registration bundles remain on the hub.

2026-10-07 15:51:47 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:05:16 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:08:01 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:11:33 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:20:38 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

Coverage note for the coordinator: 21,000 total deployments with roughly symmetric seats and a 10% heldout split implies about 1,050 heldout opponent events, below DESIGN's 1,500 minimum. Actual counts may be higher, so the runner measures and reports that gate. It preserves the frozen 80/10/10 split and stops at 24 active emulator-hours; it does not silently extend Phase A or alter heldout sampling. If coverage falls short, additional acquisition needs a prospective coordinator decision.
