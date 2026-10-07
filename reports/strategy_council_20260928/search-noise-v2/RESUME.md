# Resume S1

Mac code directory: reports/strategy_council_20260928/search-noise-v2. Fleet uses the same relative path under /mpac/sdicks02/repos/clasher. Read PROGRESS.md and PREREG.md first. The manifest is the authority after freezing. Never rerun prepare.py, regenerate the schedule, replace the runtime, or sync Mac runtime binaries over a frozen Linux study.

Before any action, inspect the named fleet_run jobs, their PID ancestry, locks, exit receipts and current/done files. Do not duplicate a live partition. Only the assigned 127x02/07/08 hosts may execute this study. Do not inspect confirmation score/winner fields until all games and partitions complete. Do not commit.

The node supervisor is detached with fleet_run.sh. Each child shares immutable resources by fork, runs one-thread search/BLAS at inherited nice 10, obtains its own worker lock and writes atomic terminal receipts. execution.json maps all 248 worker indices to hosts. Worker i owns global game indices congruent to i modulo 248. Console users reduce simultaneous concurrency to four without changing assignments.

After an interruption, retain completed receipts and all failure evidence. If the old supervisor is gone, launch the same node partition through fleet_run.sh with a new attempt label and pass --attempt r2 to launch_node.py. Valid terminal games are skipped, incomplete games replay from the same seed, and the previous unfinished current file is archived under interrupted/. An invalid terminal receipt or source-hash mismatch stops the worker. Do not overwrite it or change code to bypass it.

The hub collector copies only completed JSON receipts and status files from peers. It writes monitor.json with counts and technical failures. With --wait it analyzes only after all partitions finish successfully. If a child fails, inspect its technical traceback, preserve the failed attempt, and apply the preregistered rerun rule. A correctness bug in frozen code invalidates continuation and requires a new protocol with fresh seeds.

After complete-only analysis, mirror RESULTS.md, result.json, PROGRESS.md, PREREG.md, evaluation-manifest.json, source-copies.json, preflight.json, execution.json and small audit receipts to the Mac. Keep confirmation/ and runtime binaries on the fleet. Timing-only pilot receipts can be mirrored. Raw game receipts must remain on the hub.

## Current pre-freeze completion commands

Final prerequisites are encoded in preflight.py: 24 original replays, final 14-test Linux suite, fork pilot, the 18-cell final pilot supervisor, and exact full-game action-digest equality of pilot 61 and pilot 43. The latter verifies the affordability fast path without inspecting outcomes. Labels and receipts are under /mpac/sdicks02/jobs/clasher. Poll their exit receipts and technical logs, not scores.

After all pass, finalize PREREG's status on the Mac and sync only study source/docs to the hub, excluding runtime and raw output. Run preflight.py on the hub, then seal.py exactly once. Copy the manifest, source-copies.json and preflight.json to the Mac before launching any confirmation game. Do not sync an old Mac source-copies.json over the authoritative Linux one.

Launch the hub through fleet_run.sh with label s1-confirm-node-127x02-r1 and command `.venv/bin/python -B reports/strategy_council_20260928/search-noise-v2/launch_node.py --attempt r1`. Wait for each peer's smoke exit 0, then run `distribute.py 127x07` or `distribute.py 127x08` on the hub. This copies only manifest-listed files and verifies every frozen hash on the peer. Launch each peer with its corresponding s1-confirm-node-127xNN-r1 label and the same launch_node command.

Once all nodes are launched, use fleet_run.sh on the hub to detach `collect.py --wait` under s1-collect-r1. It records counts and technical failures only until complete. If it exits on an actual failed worker, apply the technical-rerun protocol and relaunch collection with a fresh label. Preserve all failed supervisor/worker logs and exits.

## Fleet availability incident

As of 2026-10-07 23:28 UTC, hub 127x02 is unreachable on Tailscale and from 127x07 over LAN. Both peers are reachable but have no successful smoke receipt, so their S1 work is not authorized to begin yet. Do not retry the disconnected hub in a loop or touch Tailscale. Restore connectivity externally, then inspect the existing detached jobs before launching anything. The hub's actual process state is unknown.

The confirmation supervisor is s1-confirm-node-127x02-r1, collector s1-collect-r1, and bounded peer-ready launcher s1-peer-ready-launch-r2. That operational launcher waits for each peer smoke exit 0, copies only manifest-listed files, verifies inputs under nice 10, and submits the correct peer supervisor. It stops immediately on SSH failure and after at most 180 readiness polls. Its r1 attempt failed before deployment because scp/SFTP was unavailable; rsync fixed transfer, with all logs retained. The launcher source is archived locally under operations/peer-ready-launch.source.txt. No frozen source or engine changed after seal.
