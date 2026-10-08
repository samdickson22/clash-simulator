# Clasher leased hosts — 2026-10-08

Binding policy: `/mpac/sdicks02/cc/FLEET-SHARING.md`, rules 1–7 and its lease table.
Coordinator: `0523ae6f-baa3-4d4e-b233-b392671670db`.
Leases expire **2026-10-09 05:30 UTC**, or sooner on reclaim. No work after expiry.
The older fleet README host exclusion is superseded only for the seven explicitly
leased hosts below. Do not contact 127x10/12/17 or 127x02/07 for this work.
127x05 remains a command center: no builds, tests, games, training or bulk transfers.

## Qualification result

Final receipts collected **2026-10-08 05:42 UTC**: all seven hosts are qualified.
Every CPU host passed **P16 12/12, 15,949 boundaries, zero mismatches**. All seven
passed the nine required GPU probes; the optional compile probe failed on each
with `Triton Error [CUDA]: device kernel image is invalid`. Eager CUDA is qualified.

All setup jobs exited 0. Each peaked at seven sampled processes and less than
10.6 GB resident memory. Final GPU memory use was 16 MiB on 09/11/13/14/16,
105 MiB on 18 and 144 MiB on 15, leaving more than 8 GiB free everywhere.
All five rebuilt extensions have SHA-256
`df267084dc3c422a6cbcf135b869dcec2d43c252b173ba669cde03ec63fd24f5`.
Final audits checked all 3,963 source files, verified only the documented
environment-path adaptations, and found no external symlinks in any footprint.

**Training store not copied on any host:** the hub's T3-PASS certificate was still
absent at final collection. All seven receipts explicitly record
`data_copied: false` and `ready_for_gpu_training_on_c56_store: false`.
No host was refused or skipped. No production job or Git commit was started.

## Paths and caps

Every host has its own `/mpac/sdicks02/fleet-leases/<host>.json`. Read it before
launching. Refusal, another borrower, reclaim, a missing lease, or expiry blocks
launch. The lease was written before provisioning; all initial `who` outputs
were empty.

| Host | Lease | Total Clasher process cap | CPU evaluation |
|---|---|---:|---|
| 127x11 | full CPU+GPU | 96 | P16 12/12, 0 mismatches |
| 127x13 | shared CPU+GPU | 64 | P16 12/12, 0 mismatches |
| 127x14 | shared CPU+GPU | 64 | P16 12/12, 0 mismatches |
| 127x16 | shared CPU+GPU | 48 | P16 12/12, 0 mismatches |
| 127x18 | shared CPU+GPU | 48 | P16 12/12, 0 mismatches |
| 127x09 | shared GPU only | 8 | Not permitted |
| 127x15 | shared GPU only | 8 | Not permitted |

If `who` shows a console user, use the smaller of the lease cap and **16 total
processes**. Include supervisors, shell launchers, data workers and compiler
subprocesses in that count. Reserve at least two processes for supervision and
monitoring; GPU-only hosts should use one DataLoader worker unless their complete
process tree has been measured. Every process runs at **nice 10 or higher**.
Shared-host Clasher resident memory is limited to **64,000,000,000 bytes**.
Leave at least **8192 MiB GPU memory free**, including on the full host.

All workload files, tools and caches are under this host-local footprint:

```text
/mpac/sdicks02/repos/clasher-lease/
  env.sh                        # source before using tools
  run.sh                        # detached, locked, lease-aware launcher
  lease_watch.py                # checkpoint/exit supervisor
  repo/                         # hub working-source snapshot; no .git
    .venv/                      # CPU hosts only; uv sync --frozen
    engine-rs/clasher_core.abi3.so  # CPU hosts only; rebuilt locally
  envs/clasher-gpu/             # all seven; pinned CUDA 11.8 environment
  tools/uv/                    # own uv 0.12.23
  tools/uv-python/              # own managed Python 3.12.13
  tools/{cargo,rustup}/         # CPU hosts; own Rust 1.97.1
  cache/, config/, share/, tmp/, build/, jobs/
  data/decoded-logic-1e505767/   # evaluation catalog
  data/c56-store-v1/            # only after T3 certificate and checksum copy
```

`env.sh` routes UV, Cargo, Rustup, XDG, CUDA, Triton, Torch, Hugging Face,
Matplotlib, YOLO, pip, Numba and temporary files into this footprint. It leaves
`HOME` and shared environment files alone. Never source `/mpac/sdicks02/env.sh`
on borrowed hosts or use the original `fleet_run.sh`, whose paths are shared.
Never read or write any roader repository, jobs or caches. Do not write to
`/mpac/sdicks02/tools`, `/mpac/sdicks02/envs`, shared caches or NFS home.

## Readiness receipts

Authoritative per-host receipts are on **127x01**:
`/mpac/sdicks02/jobs/clasher/lease-ready-<host>.json`.
A receipt's `qualified` flag requires a valid lease, completed setup, all required
GPU probes, and P16 12/12 with zero mismatches on CPU hosts. Read the live lease
again before using a receipt. `ready_for_gpu_training_on_c56_store` additionally
requires a certified, checksum-verified data copy; qualification alone does not
make that training store available.

Host-local raw evidence is `jobs/p16.log`, `jobs/p16.json`,
`jobs/native.sha256`, `jobs/source-verified.json`, `tmp/gpu-check.json`,
`jobs/gpu-env.log`, `jobs/final-audit.json` and `jobs/setup-20261008-r1.exit.json`.
Exit receipt absence means unfinished, never success.

The source snapshot is
`127x01:/mpac/sdicks02/jobs/clasher/lease-source-20261008/`: 3,963 files,
109,380,356 bytes, tracked working code plus current engine/imitation source and
necessary P16 inputs. `source-sha256.json` pins the actual snapshot. Each host
checks every file before adaptation. No bulk datasets/checkpoints or APK archives
were copied. The historical hub source pins differed for `engine-rs/src/hook.rs`,
`engine-rs/src/lib.rs` and the stage6 `seal_final.py`; this is recorded in
`historical-pin-drift.json`. CPU hosts therefore rebuild the Linux extension from
the snapshot instead of reusing the historically qualified binary. This task's
P16 gate does not establish a new full engine or S122 qualification.

Only environment paths are adapted in the copied P16 checker and identity shell:
repository root, receipt/output directory and projectile catalog. GPU scripts
retain all 49 dependency pins and required probes from `fleet/gpu_env.sh` and
`fleet/gpu_check.py`; adaptations are the lease host allowlist, lease-local paths,
Python 3.12.13, one DataLoader/YOLO worker, one Torch/BLAS thread, and a 12 GiB
pre-probe free-memory gate. `torch.compile` is optional and has the known old-driver
failure; use eager CUDA. The project `.venv` is for CPU evaluation; use the
separate cu118 GPU environment for GPU work.

## Launching authorized jobs

These are launch templates for the worker assigned the actual job. Provisioning
ran only P16 qualification and the synthetic GPU checker, with no production games
or training. Use fresh labels, absolute executable/script paths, and resumable
outputs inside `clasher-lease/`. The supervisor starts commands in `repo/`.

Inspect readiness on the hub, then the live lease and console users on the target:

```bash
ssh 127x01 'cat /mpac/sdicks02/jobs/clasher/lease-ready-127x11.json'
ssh 127x11 'who; cat /mpac/sdicks02/fleet-leases/127x11.json'
```

CPU job template (substitute the assigned script and arguments):

```bash
ssh 127x11 'bash -s' <<'REMOTE'
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
bash "$CLASHER_LEASE_ROOT/run.sh" UNIQUE-LABEL \
  "$CLASHER_ROOT/.venv/bin/python" -B "$CLASHER_ROOT/PATH_TO_JOB.py" JOB_ARGUMENTS
REMOTE
```

GPU job template, after the job's data and readiness gates pass:

```bash
ssh 127x13 'bash -s' <<'REMOTE'
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
# Only for trusted, locally generated Ultralytics checkpoints, when required:
# export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
bash "$CLASHER_LEASE_ROOT/run.sh" UNIQUE-GPU-LABEL \
  "$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python" -B \
  "$CLASHER_ROOT/PATH_TO_CUDA_JOB.py" JOB_ARGUMENTS
REMOTE
```

Use `envs/clasher-gpu/bin/python` explicitly; activation is optional. Older MPS-only
training entry points still need their assigned worker's CUDA port. Do not assume
installing this environment changes those scripts. Logs and receipts:

```bash
ssh 127x13 'tail -40 /mpac/sdicks02/repos/clasher-lease/jobs/UNIQUE-GPU-LABEL.log'
ssh 127x13 'cat /mpac/sdicks02/repos/clasher-lease/jobs/UNIQUE-GPU-LABEL.exit.json'
```

`run.sh` uses `nohup`, `setsid`, nice 10 and a host-wide `flock`, so only one
supervised workload runs at once on a host. It returns a launch PID immediately.
The supervisor writes atomic `.state.json` and `.exit.json` receipts and records
peak sampled process count/RSS. Jobs must keep subprocesses attached to their
supervised tree; do not launch independent daemons. Cap your job before launch;
one-minute resource checks are a backstop, not a hard kernel quota.

## Reclaim and return

The wrapper rereads the host lease every **60 seconds**, including its expiry,
borrower identity, refusal and `"reclaim": true`. An invalid/unreadable lease also
requests a stop. On reclaim it signals the job's main PID with **SIGTERM**. Jobs
must implement checkpoint-and-exit on SIGTERM, or explicitly set
`CLASHER_CHECKPOINT_SIGNAL=SIGUSR1` before launch when their checkpoint handler uses
SIGUSR1. Such a handler must save and exit; saving and continuing is insufficient.

After 24 minutes from detection, the wrapper sends SIGTERM to every verified
remaining descendant. At 25 minutes it sends SIGKILL to remaining verified PIDs.
With the one-minute detection bound, the workload is freed within **26 minutes**,
inside the 30-minute requirement. It tracks PID start times before signaling and
never uses `pkill -f`. Detached checker subprocesses are tracked through ancestry.
It removes only this coordinator's reclaimed/expired lease after tracked children
are gone. Forced termination can lose changes since the last checkpoint.

A reclaim message to the coordinator is equivalent to the lease flag: the
coordinator must promptly set `reclaim` on the matching host lease. If the host is
idle, return it immediately by verifying there are no Clasher jobs and deleting
only that lease. There is no persistent idle daemon or cron job. On planned return,
request checkpoint/exit, verify all borrower processes stopped, then remove the
lease. Data may remain; data larger than 200 GB must move off within one day of
return. Never touch Tailscale, its scripts, or crontab.

The wrapper's hub-side integration tests exercise normal completion, refusal,
checkpointing on reclaim and forced cleanup with accelerated deadlines. Test
receipts are under `/mpac/sdicks02/jobs/clasher/lease-watch-test-*/` on 127x01.

## Training data gate

Wait for the actual hub certificate at
`reports/strategy_council_20260928/imitation/data/receipts/T3-PASS.json` (or a
certificate placed in the store itself). The data contract specifies the receipts
location. Do not copy an unfinished store or infer PASS from a progress note.
Source store:
`127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/c56-store-v1/`.
Destination on every GPU host: `clasher-lease/data/c56-store-v1/`.

At handoff, consult each receipt's `data_copied` and `data_note`. If the certificate
is still absent, environment qualification is complete but store staging remains
pending. The assigned data worker should transfer directly over LAN under the
same lease-aware wrapper, preserve the certificate, checksum every file against
the hub, and update the hub readiness receipts. No training or games are started
by this setup task.
