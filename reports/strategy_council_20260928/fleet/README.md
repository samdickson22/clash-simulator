# Clasher fleet

Hub: **127x01**. Backup mirror: **127x04**. Recovery is in progress; measured
results are in `HUB-127X01.md`. The readiness barrier is
`/mpac/sdicks02/jobs/clasher/hub-ready.json`, written only after hub qualification,
peer checksum verification, every peer P16 smoke pass, and a zero-difference
Mac bulk-offload dry-run against both 01 and 04.

127x02 went off LAN and tailnet around 23:25 UTC on 2026-10-07. Do not write to
it or use it as a source if it returns; report its return for reconciliation.
Active compute hosts: **127x01, 03, 04, 07, 08**. **127x05 is the shared T3
command center:** docs/scripts and SSH coordination only, no builds, tests,
identity checks or bulk transfers. Do not use 127x06 or 127x09–18. Run `who`
before launching and leave headroom for console users. Host 03 has no working
GPU. These gates qualify CPU simulation, not GPU training.

## Layout and jobs

Everything lives under `/mpac/sdicks02`: `env.sh` selects local caches/toolchains;
`tools/` holds Rust 1.97.1 and Python 3.12.13; `repos/clasher/` holds the repo,
Linux venv and extension; `repos/clasher-local-data/` holds `clasher-engine-speed`
and `decoded-logic-1e505767`; `repos/clasher-v4-data/` receives the Mac collector;
`jobs/clasher/` holds logs, locks, PIDs and atomic exit receipts.

NFS home has an almost-full 5 GB quota. Only the two existing legacy cache
symlinks belong there. Never touch Tailscale, its scripts/state or crontab.
Never copy private-server APK archives. No commits/pushes by recovery workers.

```sh
ssh 127x01 'who; bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh unique-label .venv/bin/python -B path/to/job.py'
ssh 127x01 'tail -40 /mpac/sdicks02/jobs/clasher/unique-label.log; cat /mpac/sdicks02/jobs/clasher/unique-label.exit'
```

Every long job uses `fleet_run.sh`: nohup, setsid, nice 10, per-label flock,
local scratch and thread limits. Missing exit means unfinished/interrupted,
never success. Completed labels retain their exit status; use fresh labels for
retries. Verify PID, command and ancestry before stopping a job. No `pkill -f`.

## Recovery and provenance

The dirty Mac `/Users/sam/Desktop/code/clasher` tree is authoritative and
read-only to this worker. `recover_hub.sh` pulls directly from 127x01 via
`macmini-fleet`, resuming the partial tree and restoring both local-data dirs.
It reuses the original excludes: root .venv, targets, native binaries,
bytecode, node_modules, .DS_Store; APK/apks/xapk exclusions are mandatory.
It performs a final sweep and checksum dry-runs. Counts, bytes and itemized
results are in `jobs/clasher/recovery-verify-*.log`. No deletion or Git cleanup.

`recovery-source-mac.json` pins the historical source scope plus newly added
engine/Python/test files. Whole-tree coverage is separately checksum-verified
by rsync. The source-manifest and rebuilt Linux extension hashes are recorded
in `transfer-ready.json`. `verify_inputs.py` supports explicit
`CLASHER_FLEET_SOURCE_MANIFEST` and `CLASHER_FLEET_NATIVE_SHA256` overrides while
retaining replay-input and historical certificate checks. Historical
`source-mac.json` and `evidence/environment-linux.json` remain untouched.

## Build and qualification

Source `/mpac/sdicks02/env.sh` on the hub. `bootstrap.sh` runs frozen uv sync
with Python 3.12.13, the existing engine build, import setup and Cargo tests
with `PYO3_PYTHON` set. Cargo historically has zero tests; Python differential
suites provide meaningful engine coverage.

```sh
fleet=reports/strategy_council_20260928/fleet
bash "$fleet/fleet_run.sh" recovery-bootstrap-20261008 bash "$fleet/bootstrap.sh"
bash "$fleet/fleet_run.sh" recovery-gates-20261008 bash "$fleet/gate_sequence.sh"
bash "$fleet/fleet_run.sh" recovery-recorded-20261008 bash "$fleet/recorded.sh"
bash "$fleet/fleet_run.sh" recovery-stage6-info-20261008 bash "$fleet/regressions.sh" stage6
```

`recovery_qualify.sh` is the detached continuation waiting for transfer
verification; do not duplicate its jobs. The sequence uses the original
admitted P16/C56/random commands, then fast, Stage 2, Stage 4, Stage 3/5/5b,
full 200-root Stage 5 replay and speed regressions. It stops on an identity
failure. Recorded replay executes eight actual games in four shards, then
runs the original checker over the merged rows. Required identities:
**P16 12/12, C56 7/7, random 24/24, recorded 8/8**, with zero mismatches.
Stage 2/4/5/5b regressions must pass. Diagnose failures without engine/data edits.

The current source includes build-45 changes and an unfinished private46
Inferno Dragon dash-channel draft. Cumulative Stage 6 is **informational only**.
Its list includes the four new BeamDash/ChainStagger/MirrorLeaf/HookPlanner
classes from the Mac final_controls.sh, plus the original cumulative list.
Stage 6 admission belongs to its owner. Saved-root source hash failures may
use only the existing audited cleanup mapping; never relax comparisons.
`PARITY-LINUX.md` records the earlier 127x02 run, not this recovered hub.

## Fan-out and mirror

After hub gates pass, run `fanout.sh` through `fleet_run.sh`. It copies tools,
repo including Linux venv/extension, and local-data from 01 over LAN to
**03/04/07/08**. Exclude targets, bytecode and APKs; preserve existing files.
Each scope is checksum-verified before smoke. Per-node labels are
`recovery-copy-127xNN-20261008` and `recovery-smoke-127xNN-20261008`; receipts
live in `/mpac/sdicks02/jobs/clasher/`. Copy exit alone does not certify smoke.

`hub_mirror.sh` runs as `hub-mirror-127x04-20261008-r2` every 30 minutes at nice 19,
with a 50 MiB/s limit and no --delete. It mirrors v4-data, hub jobs, C56 recon,
search-noise-v2 and engine-speed receipts under the same paths on 127x04.
Inspect its log and `hub-mirror-heartbeat.json`. This is a copy-only backup,
not bidirectional synchronization or automatic failover.

Before authorizing Mac bulk cleanup, run `pilot/offload_mac_bulk.sh` on the Mac
in its default **dry-run mode only**, through a detached hub job. Never pass
`--delete`. Record its stamp, file count, bytes and both host difference counts
in hub-ready.json and HUB-127X01.md. Untracked/ignored bulk directories are in
the transfer scope; never delete their fleet copies or overwrite newer data.
