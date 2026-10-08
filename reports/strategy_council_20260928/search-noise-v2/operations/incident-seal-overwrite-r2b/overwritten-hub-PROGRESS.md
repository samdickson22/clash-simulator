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

2026-10-08 01:41:48 UTC: r2b collector stopped without retry: AssertionError(('worker failure', '127x04', 2, '1'))
