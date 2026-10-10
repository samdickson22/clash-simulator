# G teacher-generation top-up

Updated 2026-10-10T01:35:47Z. Coordinator: 0523ae6f. Running on 04 and 01. Combined target: 6,000,000 roots; deadline: 2026-10-11 03:00Z. Final packs and manifest remain pending.

Freeze `cb784cd3` was committed, secret-scanned and pushed before any game. The fresh 04 provenance audit passed 144,265 files and 53,506 formula contexts with zero overlaps or errors. All 1,402 original B2 runtime source pins, the native binary and the explicit v1 checkpoint were verified. Audit PID/PGID 3865071 exited successfully on core 47 under nice 19/SCHED_IDLE. Full pins and the disjoint r1/K/X interval review are in [FREEZE.json](FREEZE.json).

04 reserves `4503601607370496+[0,1000000)`; the released 01 host uses `[2000000,3000000)` on the same base. Indices 0–7 are smoke only; 8–63 remain unused; production begins at index 64. Deck, seat and opponent schedules retain the original index formulas. Both hosts write only to their own `/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/` tree; r1 and other worker trees remain read-only.

The eight-seed smoke finished at 01:19:34Z. Supervisor PID/PGID 3886095 and all eight children vacated with exit 0. All 68 columns match r1 dtype, trailing shape, endian and memory order. All 6,020 rows passed gate-c byte checks; the 930 roots and all eight games passed exact replay. Source-file SHAs and packed-row equality passed. Smoke packed manifest SHA: `c097d240bb412b86738bf501fc60e9dcb7436e6f66d30ea241178ee441154984`. Smoke is excluded from production. [Compatibility receipt](receipts/smoke-compatible.json).

Four operational checks passed without real games: finish current game before STOP, STOP before admission, exact sealed-game resume, and STOP during low-memory admission. The B2 snapshot predates the packer, so the unchanged r1 student packer is imported from the owned ops directory. B2 scientific sources remain unchanged. Qualification and operational admission were secret-scanned, committed and pushed as `dbb45795` before production. [Operations admission](receipts/operations-admission.json).

Production launch receipt was sealed at 2026-10-10T01:21:15Z. Supervisor PID/PGID: 3908611. Packer PID: 3908895, PGID: 3908611. The 47 workers share PGID 3908611; each has one distinct physical core from 0 through 46. Supervisor and packer use core 47. [Exact worker PIDs and cores](receipts/launch-04.json).

The 01:21:24Z host audit passed all 49 owned processes and their threads: nice 19/SCHED_IDLE, affinity within physical cores 0–47, MemAvailable 96,963,969,024 bytes. G does not use SMT siblings 64–111, A1 cores 52/116 or X5 CPUs 118–126. Host 01 was initially withheld until K released it at 01:19Z; no G simulations run on 03, 08, leased hosts or 05. [Host audit](receipts/host-audit-04.json).

The 2026-10-10T01:23:46Z live snapshot had 59 terminal production games, 6,829 roots and 44,003 rows; all 47 workers were active, with no pause or failure. MemAvailable was 92,413,001,728 bytes. Initial loading and incomplete games are excluded from these counts; a warm rate remains pending. [Startup snapshot](receipts/startup-progress-04.json).

Runtime paths, relative to the owned job prefix:

- `generation-r1.log`, `generation/workers/NN.log`: supervisor and per-worker logs.
- `generation/progress.json`: atomic counts, active workers, memory and stop reason.
- `generation/launch.json`, `generation/exit.json`: identities and final worker exits.
- `packing.log`, `packing-progress.json`: streaming pack progress.
- `packed/batch-NNNNN/`: SHA-verified packs of up to 2,048 terminal games.
- `concat-manifest.json`: consumable verified G shards and parent r1 corpus SHA `1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b`.

Preempt by creating `127x04:/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP`. Workers close admission and finish their current game; the frozen emitter receives `stop=None`. Packing interrupts at its game-copy boundary. Confirm worker exit receipt plus absence of the recorded process group. STOP is externally owned and is never cleared automatically. Memory pauses owned workers at 26 GiB and resumes at 28 GiB; the required floor is 24 GiB.

Admission closes at 02:55Z Oct11, allowing a five-minute drain. At 03:00Z the supervisor bounds any still-live PIDs it created; unfinished outputs remain unsealed. Target detection may include completed in-flight game overshoot, which must be reported separately. No new generation may start or resume after 02:55Z.

Resume only after coordinator release, a verified complete vacate and review of the stop reason. Preserve the same source, seeds and output tree. Inspect both STOP and INTERNAL.STOP; never remove an internal target/deadline stop to continue generation. Use a fresh launch name: `$job/ops/detach.sh generation-r2 $job/ops/driver.py generation`. Worker stripes skip matching sealed seed/index identities. Packing quarantines only its own unsealed output and retains raw games and all verified packs.

A 30-minute continuation is bound to this thread; next run is 2026-10-10T01:51:09.288Z. Its ID and disable instructions are in [continuation.json](receipts/continuation.json). It checks identities before any action, reports milestones under 120 words, and disables after final publication. Launch documentation was pushed as `c1e8f613`. Only documentation and small receipts enter git; no data or operational code is committed.

2026-10-10T01:35:47Z — host 01 added after coordinator release, passing smoke and pre-launch amendment `21405824`. K progress records all 1,000 reporting games complete and physical cores 0–39 released; ps confirmed PIDs 1137848/1183934 absent. No X evaluation was active. Fresh 01 audit passed 62,489 files, with zero collisions/errors; all 1,402 original B2 source pins, native and checkpoint match the frozen 04 copy.

01 seeds are `4503601607370496+[2000000,3000000)`, disjoint from 04 and all r1/K/X ranges including helpers. Deck/seat/opponent formulas are unchanged. [Host amendment](HOST01-AMENDMENT.json).

01 launched at 2026-10-10T01:30:38Z: supervisor PID/PGID 1356583; packer PID 1356885, same PGID. Its 39 workers use distinct physical cores 0–38; supervisor/packer use core 39. The 2026-10-10T01:35:00Z audit passed all 41 owned processes and threads: nice 19/SCHED_IDLE, cores 0–39, MemAvailable 88,945,213,440 bytes. G avoids CPUs 54–62, 118–126 and all SMT siblings. [Launch](receipts/launch-01.json), [audit](receipts/host-audit-01.json).

The first sealed 01 game passed the 68-column schema comparison against the 04 smoke and all game-file SHAs: seed 4503601609370517, index 2000021, 154 roots, 989 rows, NumPy 2.3.5. [Receipt](receipts/first-game-schema-01.json).

The sole fleet controller runs on 04 core 47, PID/PGID 3985130, nice 19/SCHED_IDLE. Original controller PID/PGID 3969977 was identity-checked and retired before replacement; both generation supervisors remain unchanged. Stop guard `6ed32d4d` and full-group-vacate receipt `5010386b` pin the current control transport. It samples both hosts every five seconds and applies the 6 M target to combined completed roots. [Fleet launch](receipts/fleet-launch.json).

At 2026-10-10T01:35:01Z, combined progress was 691 terminal games, 85,752 roots and 552,745 rows, with no errors or stop reason. 01 had 25 games/3042 roots; 04 had 666 games/82710 roots. All 39/47 workers remained active. [Snapshot](receipts/dual-host-startup.json).

01 detects X offline/game_pool/game_worker or agreement/H2H processes each second. Detection creates its owned STOP, closes admission, finishes current games and interrupts packing. The fleet caches 01 metadata only after its entire generation PGID exits, then makes no more 01 remote calls while 04 continues. Never clear STOP without coordinator release. A later authorized 01 resume also requires restarting the sole fleet controller to discard its cached preemption snapshot.

STOP on 04 reclaims the remaining G fleet and retires the controller after game drain. The final combined pack receipt is `04:$job/fleet-concat-manifest.json`; it binds both host manifests to r1 `1c8e1f49` and counts pending unpacked roots. Interrupted 01 raw games are retained; pack them after an allowed release, or stage them into the own 04 prefix for packing there. Never claim the full concatenation deliverable while pending roots remain.

The existing 30-minute continuation now covers both hosts, combined target and 01 preemption. Next run remains 01:51:09.288Z; no second timer was created. Final roots/packs/manifest remain in progress.
