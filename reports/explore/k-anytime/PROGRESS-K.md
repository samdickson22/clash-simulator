# K anytime W progress

Updated 2026-10-10T00:21:20Z. Coordinator0523ae6f. Exploration; no live/Mac/heldout.

- Spec63b2d6d7 §1–2 and E1/W/perf read; no games started.
- Owned runtime03 `/mpac/sdicks02/jobs/clasher/k-anytime-20261010-r1`, copied sealed E1 sources read-only.
- Generic current-gil + E1 cancellable method compiling nice19/CPU0.
-03 CPUs0–59;01 overflow0–39; no SMT. X4 reserved parent/loader CPUs and siblings excluded; caches stay up.
-Original pilot/detach.sh BSD mktemp emitted Linux PID errors; detached build confirmed PID1298841. No duplicate. Owned Linux-compatible copy planned.

Next: freeze commit; implementation;125-state qualification and injected clocks; smoke40; reporting3000; reduce exact decision rules.

2026-10-10T00:24:18Z: freeze0f2a9ec8 pushed. K1/K4 exact125/125; scores identical125/125; K4h114/125; cancellation immutable125/125;12 clock tests pass. Qualification PID/PGID1307900 finished. Native SHA44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2. Owned setsid-f wrapper replaces unavailable/incompatible old pilot. Next smoke40 games.

2026-10-10T00:24:21Z smoke launched03 supervisor PID/PGID1313203; single pool PID/PGID1313223,20 physical cores0–19. Native qualification complete; no reporting games yet. Staging01 owned runtime with same source/binary; requested X4 CPUs and SMT siblings excluded.

2026-10-10T00:28:09Z: thread smoke pool03 PID/PGID1319155,4 games ×5 physical cores0–19. Inherited native source exactly matches E1 source manifest; build fingerprint confirms features(extension-module,gil-release),rustflags[]; rustc1.97.1.01 staged pins exactly match03 binary/plan/sealed adapters. Reporting split:03 pair indices0–399;01 indices400–599; all five arms for each seed on same host. Both pools nice10/SCHED_IDLE.

2026-10-10T00:30:16Z: all40 smoke terminal; audits pass; reporting launched after smoke with frozen configuration. Smoke excluded, no tuning.
-127x03 reporting supervisor PID1331806,PGID1331806, launched2026-10-10T00:29:47Z.
-127x01 reporting supervisor PID1137848,PGID1137848, launched2026-10-10T00:29:47Z.

Resume: inspect owned job/progress.json and reporting/*/{launch,receipt,supervisor-exit}.json on each host; inspect exact recorded PID cmdline before assuming active/dead. Supervisor automatically skips terminal receipts and reruns only pending scheduled cases. If supervisor exited, invoke owned detach.sh with a new log/PID receipt and same supervise.py --phase reporting --pairs400 --offset0 --cpus60 on03, or --pairs200 --offset400 --cpus40 on01. Do not reuse launch.sh claim or duplicate an active supervisor. No global process kills. STOP file is owned-job-only; minimum-memory pause24GiB/resume28GiB.

2026-10-10T00:35:31Z: reporting single pools03 PID/PGID1331813,01 PID/PGID1137886. Read-only host audit passed63/43 owned Python processes (game pools60/40 plus supervisors/manager/auditor); all assigned affinity stays within60/40 physical cores, nice≥10/SCHED_IDLE.03 cache PID1655741 remains alive in its original PGID1655728. No game/plan/scorer edits after launch. Added compact status reader without outcomes; reporting reducer explicitly suppresses decisions for excluded smoke.

2026-10-10T00:43:34Z:01 all600 single-core games terminal; stage exit0.01 K4/K4h pool PID/PGID1183934, launched2026-10-10T00:43:19Z,8 workers×5 physical cores0–39. Threaded host audit passes; still no pauses.03 single900/1200 at00:43:24Z.

2026-10-10T00:48:36Z:03 all1200 single-core games terminal, stage exit0.03 K4/K4h pool PID/PGID1393695, launched2026-10-10T00:48:09Z,12workers×5physical cores0–59. All1800 single-core games now terminal;01 thread59/400 at00:48:22Z. No pauses/failures; thread01 audit verifies8 masks of5physical cores.

2026-10-10T01:19:28Z:01 all1000 reporting games terminal; both stage exits0, supervisor/pool exited, no owned Python except final auditor.01 K physical cores0–39 released. Raw01 evidence copied read-only to owned03 input-01; originals retained.03 reporting1792/2000 (208remaining) at01:19:09Z. No pauses/failures.

2026-10-10T01:34:23Z: complete3000 reporting+40 excluded smoke, no restarts/paused census samples.03 finished01:30:20Z,01 finished01:18:49Z; all K pools/supervisors exited and cores released. Cache PID1655741 remains alive. Paired audit600 seeds/25 matchups/both seats/cadence/affinity/capacity passes. K0 loss46.50%; K1 loss96.50% (+50.00pp[46,54]); K4/K4h/KU each19.33%. K4/K4h advance (−27.17pp CIs[−31.67,−22.50]/[−31.67,−22.83]); kill false. Retention100% point each; fallback0.75%/0.72%; K4/K4h wall114.6/187.9/193.3 and115.7/183.3/193.1ms. K1 legal-play-but-no-complete-play cutoff85.80%. MacE4-v2 note and L2 draft prepared; no Mac/live/heldout work.03 stale supervisor pin corrected explicitly against prelaunch8237f993 and01 pin; original preserved; scorer/game/plan/native unchanged.
