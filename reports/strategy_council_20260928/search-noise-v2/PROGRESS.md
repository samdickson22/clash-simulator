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


# S1 r2 STOP: sealed inputs overwritten externally

Recorded 2026-10-08 01:47:27 UTC. Latest preservation checkpoint 2026-10-08 01:46:29 UTC.

**Do not launch migration, restart failed partitions, restore sealed paths, or analyze until the overwrite source and the protocol recovery are resolved.** This supersedes all earlier runnable recovery instructions. No outcomes have been inspected; no RESULTS.md or result.json has been generated by this task.

## Integrity finding

The authoritative r2 manifest is `3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677` (468 files). All three current hosts were verified at task start, and 04/08 were reverified at about 01:33:55 UTC. At 2026-10-08 01:40:56 UTC, the hub manifest, execution.json and launch_node.py inode-change timestamps show replacement; the resulting manifest is the old r1 `253aba47a826e6dbb2d951114d0f7596b0d45bd3eee294d65e6c032c0513c849`. Against preserved r2 hashes, 41 sealed files differ on both 01 and 04, including runtime Python files. 08 still has all 468 exact r2 files. The native binary on 01/04 still has r2 hash 13e908c5..., so the current directory is a mixed r1/r2 tree, not a valid r1 restoration.

Original worker 2 on 04 stopped at `worker.py:46 -> verify(manifest)` with `RuntimeError: Frozen file changed: launch_node.py`. All 48 original 04 workers subsequently exited 1; their supervisor exited 1. The collector stopped immediately on the first observed worker failure and never submitted any migration launch. The failed logs/exit receipts are preserved. An inbound whole-repository rsync server (PIDs 3366802/3366803 in the saved process inventory) was observed on 01; its initiating source is not established. The existing hub mirror copies this study directory onto 04 every 30 minutes. No unrelated transfer or mirror process was signaled or edited.

## Preserved authority and migration proof

An exact copy of all 468 sealed r2 files plus the r2 manifest was fetched from intact 08 to the separate hub path:
`/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-v2/operations/incident-seal-overwrite-r2b/frozen-r2/`
Every file hash was verified after copying. This archive includes the runtime binaries and remains on the fleet. The conflicting hub files are retained under `operations/incident-seal-overwrite-r2b/overwritten-hub-*`. Per-host full drift audits and process evidence are beside them. Nothing was deleted, re-sealed, or restored over a sealed path.

Migration mechanism remains reviewable: `operations/migration_r2b.py` gives only launch_node/analyze a module-local replacement of their execution.json parse. Frozen worker/evaluate retain original modules and original disk bytes. The deterministic prelaunch split is 48–85 to 04 (38 partitions/760 games) and 86–147 to 08 (62 partitions/1,240 games). `migration-split-r2b.json` includes the wrapper hash; `migration-proof-r2b.json` pins each game's full original inputs. `launcher-dry-proof-r2b.json` executes the actual frozen launcher main AST with no-op resources/processes and proves exactly 38/62 children, workers=248, pilot=False; actual worker.jobs enumeration matches every partition digest. **Zero migrated games were launched.** PREREG.md is sealed, so its authorized dated amendment is in PREREG-r2b-DEVIATION.md.

## Exact processes and receipts

- 127x04: `s1-confirm-node-127x04-r2`, former launcher PID 2218782, EXIT 1; all original indices 0–47 EXIT 1. No restart or signal by this task.
- 127x08: `s1-confirm-node-127x08-r2`, launcher PID 3375468, ACTIVE at this checkpoint; original indices 148–247. Left unchanged. Last audit: 468/468 r2 hashes match.
- 127x07: original launcher PID 3322105 remains UNKNOWN. One bounded read-only probe returned No route to host. No quarantine receipts/comparisons; no restart or signal.
- 127x01: `s1-collect-r2c`, launcher PID 3355179, EXIT 1 on the 04 worker failure. The earlier `s1-collect-r2` exited 1 on 07 transport failure. Temporary backup `s1-reachable-backup-r2` and superseded collector `s1-collect-r2b` retain exit 143 from verified, documented light-process retirement.
- 127x01: **`s1-receipt-preserve-r2d`, launcher PID 3369776, ACTIVE**, nice 10. Script: `operations/preserve_after_drift_r2d.py`. It only copies immutable receipts into `operations/incident-seal-overwrite-r2b/preserved-receipts/<transport-host>/`, validates identities against the authenticated archived r2 inputs, deduplicates exact backup replicas for counts, and preserves failure logs/status. It admits nothing, launches nothing, runs no analysis, and stops on the first transport failure, when both reachable supervisors exit, or after six hours (approximately 07:45 UTC). It mirrors only its small technical status to 05. Its latest state is `operations/preservation-monitor-r2d.json`; inspect its exact PID/ancestry/log/exit before acting.

At 2026-10-08 01:46:29 UTC: 1936/4,992 identity-valid preserved terminal receipts, physical counts {'127x04': 635, '127x08': 1301}; recorded completed-game CPU 85.17031672 core-hours. This is a lower bound, excluding unfinished games and unknown 07 usage. Runtime integrity around the external overwrite requires adjudication; identity validity alone does not resolve it. Successful partitions: 0/248 at this checkpoint. R2 preflight CPU was 0.71883889 core-hours. The final verdict, per-cell scores and 95% intervals are unavailable because completion gates are unmet.

## Recovery boundary

1. Coordinator must identify and isolate the inbound stale-copy source and prevent further mutation of an active study; the hub-to-04 mirror also propagates stale source files. This task did not change either process.
2. Use the separately preserved, authenticated r2 snapshot as the recovery authority. Do not use the now-r1 top-level manifest/execution on 01/04. Preserve all conflicting files and failed receipts. Do not silently re-seal, edit game code, or use r1 receipts.
3. Resolve whether this external file replacement permits an identical-input technical recovery under the protocol, including the qualification of receipts written around the replacement. A correctness defect in frozen code still requires the protocol's stop/new-study rule. No such code defect was diagnosed here.
4. After an approved, stable restoration and full 468-file verification, reconcile original 04 failures and active 08 status before any retry, with fresh attempt labels and verified PIDs/locks. The r2b collector requires changes to its operational attempt tracking to handle 04's retained failure; do not simply relaunch it. The deterministic migrated split remains recorded but unlaunched.
5. Preserve 07 receipts separately if it returns, compare identity/action digests to any eventual duplicates, admit one copy, and stop on mismatch. Never restart 07 or infer its processes have stopped.
6. Only after all 4,992 eligible terminal receipts and all 248 successful partition exit/done receipts may the pre-registered complete-only analysis run. No interim strengths or result intervals exist.

No commits, engine/gamedata edits, heavy command-center work, network/crontab changes, broad kills, or deletions were made. The task's only signals were SIGTERM to verified light backup/collector PIDs 3345142 and 3353845 before this incident. Original game supervisors were untouched.

## Latest handoff checkpoint — 2026-10-08 01:48:34 UTC

Preservation active (verified launcher PID 3369776). Identity-valid preserved receipts: 2019/4,992; physical host counts {'127x04': 635, '127x08': 1384}; recorded completed-game CPU 88.71768226 core-hours. 04 original supervisor exit 1; 08 original supervisor remains active; 07 unknown. No migration or analysis. See operations/handoff-integrity-stop-r2d.json and the live preservation-monitor-r2d.json. Earlier seal-integrity recovery boundary remains in force.

## 2026-10-08 01:58:16 UTC — authorized identical-input recovery r2e

The coordinator's adjudication (02:05 UTC entry, confirmed by the explicit recovery task) supersedes the incident stop. The stale Mac transfer is guarded. This was an external technical failure, not a diagnosed frozen-code defect. No reseal, new seeds, engine edit or outcome inspection occurred.

Restoration: all 468 sealed hashes plus manifest verified on 127x01, 127x04 and 127x08. On each of 01 and 04, 41 conflicting files plus the manifest were preserved before replacement from the authenticated frozen-r2 archive. 08 required no replacement. Audits: operations/restoration-audit-<host>-r2e.json. The hub mirror remains active (rsync -au, no deletion); correct source and direct target hash verification establish safety. Original archive and overwritten-* evidence remain intact.

Receipt rule: admit all identity-valid 08 receipts. Admit original 04 receipts only when their own completion time (started + elapsed, the frozen receipt's time fields) is strictly before 2026-10-08T01:39:00Z and the worker terminal log entry precedes all verify failures. Unique original 04: 541 admitted, 94 excluded; excluded recorded game CPU 3.59085004 core-hours. All 94 are preserved in 04's operations/incident-seal-overwrite-r2b/excluded-post-cutoff-127x04-r2e/. The hub held 66 of those excluded replicas (2.34616438 core-hours, already included in the 94, not additive); these too were moved aside. Exact original logs are retained on 01 under operations/original-04-r2/. The collector precheck admitted 1666 unique 08 receipts, zero exclusions; 08 remains active, so this number grows. Backup copies on 04 are counted by receipt origin and deduplicated, not as additional games. Qualification audits contain the complete per-game identity/hash/time decision, without outcomes.

Fresh 04 original attempt: s1-confirm-node-127x04-r2e, indices 0–47, concurrency 45. This conservatively counts Python supervisors/trackers as well as C56's 32 workers against the cap of 80. Original 04 r2 supervisor and 48 exit-1 receipts remain preserved. Frozen workers skip the 541 valid terminal receipts and replay excluded or incomplete games. 08's original r2 supervisor is left unchanged; its grandfathered original launch is not expanded.

Migration: s1-confirm-node-127x04-r2f (48–85; 38 workers) after 04 r2e succeeds; s1-confirm-node-127x08-r2f (86–147; 62 workers) after 08 r2 succeeds. operations/migration_r2e.py is a minimal operational derivative of the reviewed migration_r2b.py: only attempt labels, the 04 successful prerequisite, and monitor filename change. The original split/proof and wrapper stay unchanged. operations/launcher-dry-proof-r2e.json validates the same 38/62 children and original full input digests. All new work uses nice 10 and frozen bootstrap's one-thread native/BLAS settings; launch checks enforce console and host caps.

Collector: s1-collect-r2e on 01, operations/collect_r2e.py. It preserves but disregards 04's superseded r2 failure, requires 04 r2e/r2f and 08 r2/r2f success, rejects any old 04 post-cutoff receipt, tracks all 248 successful done/exit receipts, and admits exactly one immutable receipt per game. It stops on first surviving-host transport/worker failure or identity/action mismatch with no retry. s1-receipt-preserve-r2d was retired only after a successful replacement collection pass, by SIGTERM to its verified Python PID 3369789 (launcher 3369776, time parent 3369788); evidence in preservation-retirement-r2e.json.

Analysis remains outcome-blind until 4992 eligible receipts and 248 successful partitions plus every required supervisor exit exist. At that barrier, one bounded 07 quarantine probe compares identities/action digests against duplicates, never restarts 07, and stops on mismatch. The sealed analysis then runs unchanged through the reviewed host-map facade. Its generated report is preserved before correcting operational engine/exclusion narrative; statistical result.json is untouched. Small docs/audits/results mirror to 05; raw game receipts and runtime binaries stay on fleet.

2026-10-08 02:30 UTC: 04 r2e exited 0, all 48 original partitions and 992 eligible games complete. All 541 admitted original receipts remain byte-identical; 451 new games include the 94 excluded replays and 357 previously unfinished games. Both migrations are launched: 08 r2f PID 3400252 (62 workers; 02:10:58Z), 04 r2f PID 2269621 (38 workers; 02:29:58Z). The 02:13:47Z hub mirror cycle exited 0 and post-cycle 01/04 468-file verification passed. No outcomes inspected.

2026-10-08 02:58 UTC: 08 r2f exited 0; all 62 migrated partitions complete, 3240 total eligible 08 receipts (2000 original + 1240 migration). 04 r2f remains active. No outcomes inspected.

Completed all 4992 games; complete-only analysis wrote RESULTS.md and result.json.

## Recovery and complete-only audit

All 468 sealed hashes and manifest matched on 01, 04 and 08 (1,404 file checks). Original 04 receipts: 541 admitted before 01:39:00Z, 94 preserved and replayed at or after the cutoff. Original 08 receipts: all identity-valid copies admitted, zero excluded. Each of the 4,992 scheduled games contributes one eligible receipt. All 248 partitions completed successfully. Attempts: 04 originals r2e; migrations on 04/08 r2f; collector r2e. Original 04 r2 failures remain preserved.

Eligible game CPU: 191.19578643 core-hours. Excluded original 04 game CPU: 3.59085004 core-hours (additional to eligible game CPU). Total observed worker CPU across failed and successful attempts: 195.14090850 core-hours, including 26.16090221 in the preserved failed 04 attempt. This total already includes eligible and excluded game work; these quantities must not be added together. The five original/recovery/migration supervisors and their workers together recorded 195.18457222 core-hours; the difference, 0.04366372 core-hours, is supervisor initialization/control overhead. R2 preflight CPU: 0.71883889 core-hours. Unknown 07 work and unmetered Mac work remain additional. Completion/quarantine and per-cell decision-timing summaries: operations/completion-audit-r2e.json.

2026-10-08 03:16 UTC final: all 4992 eligible games and 248 successful partitions complete. Original 04 recovery and both migrations exited 0; collector exited 0. Primary FAIL: E4 minus B at N64 -3.90625 pp, paired 95% CI [-9.765625, 1.953125]. Neither event gate passes; retain 95/95 provisional and require further decision-side work. The single completion-barrier 07 probe returned No route to host: zero 07 receipts or comparisons; its original process state and extra CPU remain unknown. Final all-host 468-file audit passed again. RESULTS.md, unmodified statistical result.json, completion CPU/timing audit, and final integrity audit are mirrored to 05. No further S1 launch is needed.
