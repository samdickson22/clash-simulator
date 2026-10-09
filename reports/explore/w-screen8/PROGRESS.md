# W-screen8 completed

Freeze `d0e9dc2f` was pushed before all games; config SHA `f044f822bc3d13912e19ce61b065d35d8995d94232cd91b94bd04782421ec126`. Fresh range: 4503599677370496–4503599677371095, no prior/helper intersections.

All 1,800 reporting games terminal, 600 paired seeds per arm, 25 balanced matchups / alternating seats. Screen8 loss 19.33%; full W 19.50%; baseline 50.83%. Screen8−full W −0.17 pp, paired CI [−1.00,+0.67]; preregistered +3 pp upper-bound criterion PASS. Full-decision wall p95: screen8 330.2 ms / full W 491.4 ms / baseline 343.7 ms. Complete metrics, paired CIs, counts and CPU latency in results.json and METRICS.md.

Native baseline `f9d3b454`: 47 tests; exact 1,000 games / 7,000 rollouts plus 1,000 d27 roots / 3,000 traces; Resources equality. W implementation `59454e1a` + versioned-library startup `62044189`: default OFF, 54 tests, OFF 250/250 score/action/trace checks, ON 125/125 frozen choices and retained scores. No prohibited files changed; no runtime patch needed. New binary `native-w-screen8-v1`, SHA 06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10.

03 only; nice 10 / SCHED_IDLE, setsid; peak sampled combined processes 58, own 54. Reporting CPU 29.05 core-hours. Cache/raw artifacts under `/mpac/sdicks02/jobs/clasher/w-screen8-20261009-r1`; no raw game logs committed. Initial zero-game smoke launcher classification corrected; final smoke/reporting exits 0. All lane simulation jobs exited (shutdown receipt).

Aggregate report committed/pushed as `d6f5c29f`. All requested work complete; default OFF retained.

## Adoption qualified

Coordinator accepted PASS and authorized offline default ON. Before changing it, read-only /proc audits covered 01/02/03/04/05/08/09/13/14/15/16; no checkout native mappings or planner config paths. Gate (c), capture workers and trainers use private code snapshots; capture/transport/backup processes may inherit checkout PYTHONPATH without using search. Full path receipt: process-paths.json. No process signaled or changed. Offline C56/S6 construction now defaults ON; live RustPlanner still passes explicit OFF. Qualification on 03 passed under setsid/nice10/SCHED_IDLE, one process, with versioned W binary and /mpac caches: explicit OFF 250/250 comparisons (unchanged baseline digest), default C56 and S6 constructors each 125/125 equal to explicit ON and frozen screen8; 47 unit/native tests passed. Receipt: adoption-parity.json. Qualification exited; no games launched. Final read-only audit also covered newly started capture workers on 08 (v4-match-queue-status-08r2) and 09 (v4-match-queue-status-09r2), with no checkout native/config mappings. Recommended live profile documented; Mac E4 real-search/GIL-thread measurement plan in RESULTS, live default OFF retained.
