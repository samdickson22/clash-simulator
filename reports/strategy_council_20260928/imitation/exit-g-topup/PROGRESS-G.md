# G teacher-generation top-up

Updated 2026-10-10T01:23:10Z. Coordinator: 0523ae6f. Exploration only. Target: 6,000,000 additional scored roots; deadline: 2026-10-11 03:00Z. Final generation and packing remain pending.

Freeze `cb784cd3` was committed, secret-scanned and pushed before any game. The fresh 04 provenance audit passed 144,265 files and 53,506 formula contexts with zero overlaps or errors. All 1,402 original B2 runtime source pins, the native binary and the explicit v1 checkpoint were verified. Audit PID/PGID 3865071 exited successfully on core 47 under nice 19/SCHED_IDLE. Full pins and the disjoint r1/K/X interval review are in [FREEZE.json](FREEZE.json).

G reserves `4503601607370496+[0,1000000)`. Indices 0–7 are smoke only; 8–63 remain unused; production begins at index 64. Deck, seat and opponent schedules retain the original index formulas. Outputs exist only under `127x04:/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/`.

The eight-seed smoke finished at 01:19:34Z. Supervisor PID/PGID 3886095 and all eight children vacated with exit 0. All 68 columns match r1 dtype, trailing shape, endian and memory order. All 6,020 rows passed gate-c byte checks; the 930 roots and all eight games passed exact replay. Source-file SHAs and packed-row equality passed. Smoke packed manifest SHA: `c097d240bb412b86738bf501fc60e9dcb7436e6f66d30ea241178ee441154984`. Smoke is excluded from production. [Compatibility receipt](receipts/smoke-compatible.json).

Four operational checks passed without real games: finish current game before STOP, STOP before admission, exact sealed-game resume, and STOP during low-memory admission. The B2 snapshot predates the packer, so the unchanged r1 student packer is imported from the owned ops directory. B2 scientific sources remain unchanged. Qualification and operational admission were secret-scanned, committed and pushed as `dbb45795` before production. [Operations admission](receipts/operations-admission.json).

Production launched at 2026-10-10T01:21:11Z. Supervisor PID/PGID: 3908611. Packer PID: 3908895, PGID: 3908611. The 47 workers share PGID 3908611; each has one distinct physical core from 0 through 46. Supervisor and packer use core 47. [Exact worker PIDs and cores](receipts/launch-04.json).

The 01:21:24Z host audit passed all 49 owned processes and their threads: nice 19/SCHED_IDLE, affinity within physical cores 0–47, MemAvailable 96,963,969,024 bytes. G does not use SMT siblings 64–111, A1 cores 52/116 or X5 CPUs 118–126. Host 01 remains unallocated while K owns its pool; no G simulations run on 03, 08, leased hosts or 05. [Host audit](receipts/host-audit-04.json).

The 01:22:15Z live snapshot had one terminal production game, 105 roots and 721 rows; all 47 workers were active, with no pause or failure. MemAvailable was 86,929,330,176 bytes. Initial loading and incomplete games are excluded from these counts; a warm rate remains pending.

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
