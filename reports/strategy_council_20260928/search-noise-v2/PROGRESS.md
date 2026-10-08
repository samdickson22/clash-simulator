# S1 progress

2026-10-07: implementation started. No confirmation games launched. Read approved DESIGN, predecessor RESULTS/noise/player/runner, srp-public exact derivation, and fleet instructions. Shared engine edits are owned by another worker and remain untouched.

Scope: B/E1/E4/E4R at N64/N90/N97, clean A, latency/failure/identity sensitivities and head-to-head. Only 127x02 (<=48 workers), 127x07 and 127x08 (<=100 each). Await peer smoke exit receipts before compute. Mac is code authority; runtime will be isolated and hash-pinned on fleet.

Next: implement ELT and runner, exact replay/privacy tests, pilot timing, freeze PREREG and manifest, detached confirmation, complete-only analysis.

2026-10-07 22:47 UTC: implemented ELT, fair-information tests, fixed-budget multiple-root player, cells/noise, own pending-state adapter, resumable workers, complete-only analysis, collector and sealing scripts. Mac budget pilot chose 63 candidate-style rollouts. All 24 original srp-public full-game replay checks passed on Linux with ELT compared to the exact reference at every observation; all original terminal parity assertions retained. Linux unit/boundary tests passed. Additional mean-over-roots test passes on Mac.

Pilot incidents, all before confirmation: r1 exposed missing Counter import; a concurrent retry r2 was rejected by the worker lock; r3 exposed own-state packet hand-level metadata inconsistency; fixed it and added packet validation to the pending-state test. r4 E4/N64 completed 1,200 ticks, 72.26 game CPU seconds, 1.16 GB peak RSS. Maximum decision wall time 9.43 seconds, dominated by belief work; no live latency claim. All failed logs/exit receipts remain on hub.

Seed registration passed on 925,487 seed fields and 3,939 available NPZ archives, zero overlap. Six dangling historical NPZ links are disclosed in the audit and PREREG. Registered 192 paired worlds and 4,992 confirmation games. E4/N90 target latency is reused for the secondary latency comparison.

Full-game timing pilots for all 18 cells are detached on 127x02 under s1-pilot-full-<index>-r1; outputs suppress outcomes. No confirmation games launched. Peer fan-out is still running; no peer S1 compute launched.

2026-10-07 22:58 UTC: final protocol has 248 fixed partitions, with 48 on hub and 100 per peer, executed by fleet_run-owned fork supervisors. Shared-prior regression preserves actions. Thirteen Mac tests pass. All full-game pilots suppress outcomes; a preliminary identity pilot exposed unsupported script-body tokens, now restricted to the intersection of public model and script support and covered by a regression test. A variable-latency FIFO artifact was corrected before freeze; final 18-cell pilots are running as s1-final-full-pilots-r1 with child labels s1-fullpilot-36 through 53-r1. Earlier pilot receipts remain retained. Peer fan-out remains active and no peer S1 work has begun. No confirmation games have started.

2026-10-07 23:02 UTC: optimized ELT's rejection path before freeze. It now checks exact affordability before copying support arrays and skips latent spends that cannot repair an unaffordable event or a card absent from that hypothesis's deck support. A framewise regression validates the batched resource calculation at phase boundaries and caps. An additional full E4/N64 pilot, s1-optimized-full-pilot-r1, must match the unoptimized final pilot's action digest before sealing. No strength outcomes are inspected. The final fair-information test varies two possible unrevealed decks, their initial hand/cycle and RNG while preserving publicly derivable elixir.

2026-10-07: all preflight gates passed, including 24 replays / 23,058 checks, 14 tests, 18 terminal pilot cells and full-game action-digest equality of optimized and reference E4/N64. Frozen manifest 253aba47a826e6dbb2d951114d0f7596b0d45bd3eee294d65e6c032c0513c849. Manifest, Linux source pins and preflight receipt copied to Mac before confirmation. No further frozen-code changes are permitted.

2026-10-07 23:19 UTC: confirmation launched on 127x02 with 48 forked workers, supervisor label s1-confirm-node-127x02-r1, PID 3309512. The complete-only collector is detached as s1-collect-r1, PID 3309878. Runtime sharing leaves over 110 GB available on the hub at launch. Peers 07/08 remain behind the coordinator's fan-out and their smoke gates; no peer confirmation was launched. Only operational status and timing are monitored. Frozen code and engine remain unchanged.

2026-10-07T23:29:46.805212+00:00: BLOCKED by fleet availability. Direct hub Tailscale SSH timed out. One LAN attempt through reachable 127x07 returned No route to host. No network daemon was restarted and no retry loop was used. Both 07 and 08 are reachable but their required smoke exit receipts are absent; 08 also has no S1 supervisor PID/exit. Last observed hub count was 0 terminal receipts / 0 completed partitions. Current hub process state and confirmation CPU usage are unknown. Do not infer job termination.

The operational peer-ready launcher is s1-peer-ready-launch-r2 on hub. Its source is preserved locally under operations/peer-ready-launch.source.txt. r1 failed with exit 127 after scp/SFTP closed before transfer; rsync transferred the script, and r2 launched. This operational failure changed no frozen experiment files. Once connectivity is restored, inspect all named job locks, ancestry, exits and receipts before resuming. Preserve any terminal games. No strength outcomes have been inspected; RESULTS.md/result.json have not been generated. Preconfirmation metered Linux CPU: 9.8764 core-hours.

## 2026-10-08 r2 deviation — lost runtime and replacement fleet

The coordinator authorized this deviation before any confirmation outcome was
inspected. The r1 Linux runtime was lost with 127x02 after its outage around
2026-10-07 23:25 UTC. The recovered copy could not reproduce r1: 8 of 465
manifest-listed files were missing and 32 differed. The r1 manifest remains
253aba47a826e6dbb2d951114d0f7596b0d45bd3eee294d65e6c032c0513c849.
Surviving r1 documents, manifests, runtime fragments and receipts are retained
under r1-archive/. No r1 confirmation receipt is admitted to r2. If 127x02
returns, its r1 receipts must be archived unread and never merged.

Protocol r2 snapshots the current qualified 127x01 source tree into a fresh
isolated runtime. The Linux native extension is
13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309,
qualified by the hub's full Linux parity gate at 2026-10-08 00:32:53 UTC.
This build includes the Electro Spirit chain fix and the drafted Inferno
Dragon dash-channel fix. The build change applies equally to every arm.
This paragraph supersedes r1's engine-build and known-defect statements;
the hub gate is not a claim of full Stage 6 admission.

The question, arms, noise/latency models, allocation budget, all 192 paired
worlds, 4,992 games, original seeds, cell allocation, job-index modulo 248
partition, analysis, bootstrap seed and pass rules are unchanged.
execution.json moves only worker indices 0–47 from 127x02 to 127x04.
Indices 48–147 remain on 127x07 and 148–247 remain on 127x08. Maximum
concurrency is 48/100/100 respectively, reduced to four when a console user
is present. 127x01 runs the light collector; 127x05 runs no study compute.
127x04's separate C56 extraction allocation remains capped at 32.

All preflight gates are rerun on this isolated runtime before the single r2
seal: the 24 original full-game replays with ELT exact at every observation
and the original terminal assertions, the 14-test Linux study suite, the
four-child fork pilot, the 18 terminal timing-only cell pilots, and full-game
optimized-versus-slow-reference action-digest equality. The slow reference
performs the documented clone/advance/check path and tries latent repairs
without the optimized rejection short-circuits; it changes no confirmation
code and uses the original pilot inputs. Outcomes are suppressed.
Fresh r2 receipts and source hashes are required; r1 receipts earn no r2
preflight credit.

Operational scripts use the recovered peers' recovery-smoke-127xNN-20261008
receipts and -r2 job labels. Distribution continues to copy manifest-listed
files and verify every peer hash. No confirmation outcome or interim strength
aggregate is inspected before all 4,992 valid terminal receipts and all 248
successful partition exit/done receipts exist. The original technical-rerun
and post-seal correctness-bug rules remain in force. Small audit artifacts,
documents and final results are mirrored to the 127x05 checkout; runtime
binaries and raw confirmation receipts remain on the fleet.

2026-10-08 00:55 UTC: hub readiness confirmed; all who checks empty; no active S1 jobs found on 01/04/07/08. Surviving r1 artifacts archived under r1-archive/<host> on each node and 05. Qualified runtime snapshotted on 01: 459 qualified source files verified, 434 runtime copies pinned. No confirmation outcomes inspected; r2 remains unsealed.

2026-10-08T00:58:11.378262+00:00: 466 preflight input hashes verified on 127x04. Linux tests and three replay shards launched via fleet_run.sh under r2 labels; launcher PIDs 2209945, 2209955, 2209970, 2209990. No console sessions. R2 unsealed; no confirmation games launched.

2026-10-08T00:59:53.247453+00:00: Linux 14-test suite and all three original replay shards exited 0 on 127x04 (24 games, 23,058 exact checks). Four-child fork pilot submitted as s1-fork-pilot-r2. No outcomes inspected; r2 remains unsealed.

2026-10-08T01:02:33.474719+00:00: All 24 replays / 23,058 checks, 14 Linux tests and four fork-pilot children passed. Full 18-cell timing supervisor s1-final-full-pilots-r2 and standalone slow-reference pilot s1-reference-full-pilot-r2 launched on 04 with no console user, combined maximum 19 workers. Outcome fields remain suppressed. R2 unsealed.

2026-10-08 01:07:36 UTC: r2 sealed exactly once; manifest 3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677, 468 frozen files. All preflight gates passed; fresh r2 test/pilot CPU 0.71883889 core-hours. Registered design/schedule/analysis unchanged. Distribution and confirmation launch are next. No outcomes inspected.

2026-10-08T01:09:50.419270+00:00: Frozen distribution verified on 04/07/08 (all 468 hashes). Confirmation supervisors submitted: 04 PID 2218782 cap48, 07 PID3322105 cap100, 08 PID3375468 cap100; all nice10 and empty who. Collector s1-collect-r2 PID3336667 on 01. Initial technical snapshot 0/4992 terminal receipts, 0/248 done partitions; supervisors warming immutable resources. No outcomes inspected.

2026-10-08T01:18:35.712711+00:00: R2 blocked from complete analysis by 127x07 availability. Direct SSH timeout and one bounded hub check returned No route to host; 07 supervisor PID 3322105 remains unknown, not presumed stopped. Collector s1-collect-r2 exited 1 at 01:14:25 UTC on transport failure; evidence retained. 04 and 08 continue, with no observed worker failures. Light outcome-blind backup s1-reachable-backup-r2 PID 3345125 on 01 preserves their receipts without analysis or reassignment. At 01:16:58 UTC: 286 valid terminal receipts (04=110, 08=176), 0/248 completed partitions, 14.7149011330 completed-game CPU-hours; live/07 CPU unknown. Fresh preflight CPU 0.7188388889. No outcomes inspected. RESUME.md records exact recovery steps.

2026-10-08 01:19:05 UTC: handoff checkpoint 397/4992 validated receipts, 0/248 completed partitions; per-host {'127x04': 149, '127x08': 248}; completed-game CPU 20.15272840 core-hours. 04/08 and reachable-only backup remain active; 07 unresolved. No outcomes inspected.
