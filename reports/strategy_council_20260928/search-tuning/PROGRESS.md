# Search tuning progress

2026-10-04: setup in progress. Read required project instructions and srp-public design, preregistration, report, planner, derived-state, runner and statistics; read exit confirmation and paired-seat setup.

No evaluation games started. Deadline requested but not yet supplied. Workspace is dirty; all writes for this task remain under search-tuning. Existing C56 workers 31691, 64317, 31697 remain untouched. Host has 12 physical cores and about 19 GiB free. No tuning workers launched yet.

Next: copy reusable public machinery, validate candidate configuration and fair head-to-head deck pairing, audit fresh seeds, measure whole-decision latency after warmup. Confirmation will be preregistered before its first game.

2026-10-04T13:23:23.521179+00:00 PID 98950: Seed audit passed: 906440 fields, 11321 distinct historical seeds.

2026-10-04T13:26:09.518387+00:00 PID 1873: Timing current: p99 0.0569s, max 0.0574s, eligible True.

2026-10-04T13:26:12.804280+00:00 PID 1873: Timing h320: p99 0.0781s, max 0.0822s, eligible True.

2026-10-04T13:26:16.231468+00:00 PID 1873: Timing h600-i20: p99 0.0974s, max 0.1013s, eligible True.

2026-10-04T13:26:19.337208+00:00 PID 1873: Timing h160-i20: p99 0.0546s, max 0.0552s, eligible True.

2026-10-04T13:26:22.679136+00:00 PID 1873: Timing h320-i20: p99 0.0771s, max 0.0801s, eligible True.

2026-10-04T13:26:26.255569+00:00 PID 1873: Timing h600-i10: p99 0.1060s, max 0.1116s, eligible True.

2026-10-04T13:26:29.603211+00:00 PID 1873: Timing k2: p99 0.0727s, max 0.0749s, eligible True.

2026-10-04T13:26:33.115254+00:00 PID 1873: Timing k4-i20: p99 0.0970s, max 0.0986s, eligible True.

2026-10-04T13:26:36.328787+00:00 PID 1873: Timing policy16: p99 0.0667s, max 0.0691s, eligible True.

2026-10-04T13:26:39.478401+00:00 PID 1873: Timing script8: p99 0.0592s, max 0.0595s, eligible True.

2026-10-04T13:26:42.658034+00:00 PID 1873: Timing wide: p99 0.0702s, max 0.0722s, eligible True.

2026-10-04T13:26:45.946670+00:00 PID 1873: Timing mixture: p99 0.0852s, max 0.0901s, eligible True.

2026-10-04T13:26Z: Initial benchmark PID 99427 exited with no artifact or error output. Verified it was absent before retrying. Active retry PID 1873. Copied 1.2 MiB native runtime and snapshot helpers under search-tuning/native to isolate upcoming runs from concurrent Rust rebuilds; no upstream writes. Existing stage-4 PID 97904 and RoadForge workers remain untouched.

2026-10-04T13:26:48.989946+00:00 PID 1873: Timing tower: p99 0.0534s, max 0.0539s, eligible True.

2026-10-04T13:26:52.142603+00:00 PID 1873: Timing h320-tower: p99 0.0744s, max 0.0780s, eligible True.

2026-10-04T13:26:55.190628+00:00 PID 1873: Timing terminal4: p99 0.0542s, max 0.0552s, eligible True.

2026-10-04T13:26:55.190774+00:00 PID 1873: Initial timing complete. No evaluation games used for latency screening.

2026-10-04T13:27:41.763794+00:00 PID 3873: Validation passed: 11 original-player comparisons; 44 native-loop leaf comparisons.

2026-10-04T13:28:49.681836+00:00 PID 5081: Validation passed: 11 original-player comparisons; 44 native-loop leaf comparisons.

2026-10-04T13:30:47.330349+00:00 PID 6884: Timing current: p99 0.0547s, max 0.0562s, eligible True.

2026-10-04T13:30:50.507851+00:00 PID 6884: Timing h320: p99 0.0772s, max 0.0811s, eligible True.

2026-10-04T13:30:54.213270+00:00 PID 6884: Timing h600-i20: p99 0.1050s, max 0.1066s, eligible True.

2026-10-04T13:30:54.816399+00:00 PID 7356: Seed audit passed: 906440 fields, 11321 distinct historical seeds.

2026-10-04T13:30:57.326303+00:00 PID 6884: Timing h160-i20: p99 0.0626s, max 0.0655s, eligible True.

2026-10-04T13:31:00.497523+00:00 PID 6884: Timing h320-i20: p99 0.0737s, max 0.0768s, eligible True.

2026-10-04T13:31:03.881104+00:00 PID 6884: Timing h600-i10: p99 0.1024s, max 0.1068s, eligible True.

2026-10-04T13:31:07.160448+00:00 PID 6884: Timing k2: p99 0.0717s, max 0.0740s, eligible True.

2026-10-04T13:31:10.800460+00:00 PID 6884: Timing k4-i20: p99 0.1035s, max 0.1064s, eligible True.

2026-10-04T13:31:14.182211+00:00 PID 6884: Timing policy16: p99 0.0735s, max 0.0774s, eligible True.

2026-10-04T13:31:17.411264+00:00 PID 6884: Timing script8: p99 0.0626s, max 0.0642s, eligible True.

2026-10-04T13:31:20.638786+00:00 PID 6884: Timing wide: p99 0.0704s, max 0.0722s, eligible True.

2026-10-04T13:31:23.999396+00:00 PID 6884: Timing mixture: p99 0.0867s, max 0.0912s, eligible True.

2026-10-04T13:31:27.089044+00:00 PID 6884: Timing tower: p99 0.0569s, max 0.0590s, eligible True.

2026-10-04T13:31:30.299872+00:00 PID 6884: Timing h320-tower: p99 0.0768s, max 0.0798s, eligible True.

2026-10-04T13:31:33.404816+00:00 PID 6884: Timing terminal4: p99 0.0556s, max 0.0571s, eligible True.

2026-10-04T13:31:33.404906+00:00 PID 6884: Initial timing complete. No evaluation games used for latency screening.

2026-10-04T13:31:53.430039+00:00 PID 7708: Two full current/current paired-seat smoke games passed.

Pinned native P16 check passed all eight full games: 42950 ticks, exact actions/state digests/RNG. Native pin differs from historic srp-public, so this is explicit current-runtime requalification, not reuse of the old binary certificate. Initial and pinned benchmark results are both retained.

2026-10-04T13:32:20.912893+00:00 PID 9359: stage1 launched owned worker PIDs [9368, 9374, 9380]; 672 games planned.

2026-10-04T13:35Z: Found an alternative-leaf edge case in review: terminal draws return native value zero and must bypass the added tower term. Requested owned workers stop between games with search-tuning/STOP. All v1 tournament receipts will be retained but excluded; patch, terminal regression, source refreeze and fresh-seed restart required. No confirmation games have started.

2026-10-04T13:35:21.069033+00:00 PID 9359: ERROR: see error.json. No success claim.

2026-10-04T13:36:41.375988+00:00 PID 14424: Seed audit passed: 907836 fields, 11323 distinct historical seeds.

2026-10-04T13:36:46.899888+00:00 PID 14430: Validation passed: 11 original-player comparisons; 44 native-loop leaf comparisons.

2026-10-04T13:37:11.621841+00:00 PID 14435: Timing current: p99 0.0785s, max 0.0785s, eligible True.

2026-10-04T13:37:15.276383+00:00 PID 14435: Timing h320: p99 0.0944s, max 0.0950s, eligible True.

2026-10-04T13:37:19.258394+00:00 PID 14435: Timing h600-i20: p99 0.1154s, max 0.1170s, eligible True.

2026-10-04T13:37:22.570178+00:00 PID 14435: Timing h160-i20: p99 0.0751s, max 0.0756s, eligible True.

2026-10-04T13:37:26.117735+00:00 PID 14435: Timing h320-i20: p99 0.0891s, max 0.0895s, eligible True.

2026-10-04T13:37:30.075876+00:00 PID 14435: Timing h600-i10: p99 0.1212s, max 0.1218s, eligible True.

2026-10-04T13:37:33.680459+00:00 PID 14435: Timing k2: p99 0.0916s, max 0.0920s, eligible True.

2026-10-04T13:37:37.747299+00:00 PID 14435: Timing k4-i20: p99 0.1261s, max 0.1267s, eligible True.

2026-10-04T13:37:41.257407+00:00 PID 14435: Timing policy16: p99 0.0862s, max 0.0871s, eligible True.

2026-10-04T13:37:44.685780+00:00 PID 14435: Timing script8: p99 0.0817s, max 0.0830s, eligible True.

2026-10-04T13:37:48.344337+00:00 PID 14435: Timing wide: p99 0.0928s, max 0.0937s, eligible True.

2026-10-04T13:37:52.274135+00:00 PID 14435: Timing mixture: p99 0.1126s, max 0.1152s, eligible True.

2026-10-04T13:37:55.677239+00:00 PID 14435: Timing tower: p99 0.0760s, max 0.0768s, eligible True.

2026-10-04T13:37:59.216382+00:00 PID 14435: Timing h320-tower: p99 0.0893s, max 0.0901s, eligible True.

2026-10-04T13:38:02.547342+00:00 PID 14435: Timing terminal4: p99 0.0750s, max 0.0757s, eligible True.

2026-10-04T13:38:02.547422+00:00 PID 14435: Initial timing complete. No evaluation games used for latency screening.

2026-10-04T13:38:44.422605+00:00 PID 16323: stage1 launched owned worker PIDs [16344, 16350, 16356]; 672 games planned.

2026-10-04T13:45:08.731213+00:00: stage1 52/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:45:58.809004+00:00: stage1 58/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:46:48.884564+00:00: stage1 72/672 receipts; owned running workers [16344, 16350, 16356].

Timing disclosure: detached driver runs at nice 10; its worker launches invoke nice -n 10 again, so worker niceness is 20. Initial timing probes ran at nice 10. This is lower scheduling priority than requested, not an extra CPU allocation; report the distinction with timing results.

2026-10-04T13:47:38.972150+00:00: stage1 79/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:48:29.051080+00:00: stage1 89/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:49:19.127847+00:00: stage1 92/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:50:09.229964+00:00: stage1 101/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:50:59.330919+00:00: stage1 105/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:51:49.428005+00:00: stage1 114/672 receipts; owned running workers [16344, 16350, 16356].

2026-10-04T13:51Z: One baseline-opponent rejected play in tower-hog26-search-006. All actions passed pre-action public masks. Requested owned workers stop between games for read-only deterministic replay. Retain all v2 games; no strength exclusions. Existing exit/REPORTING_AMENDMENT.md documents the same class of simultaneous Cannon conflict; diagnosis is pending. Driver reporting currently has an unrequested zero-rejection assertion that must not become a new experimental gate.

2026-10-04T13:52:25.166522+00:00 PID 16323: ERROR: see error.json. No success claim.

2026-10-04T13:52:39.512842+00:00: stage1 118/672 receipts; owned running workers [].

2026-10-04T13:52:59.669080+00:00 PID 31649: Rejected-command game replay reproduced exact decks, outcome, ticks and failure counts. See rejected-play-diagnosis.json.

2026-10-04T13:54:06.027456+00:00 PID 33152: stage1 launched owned worker PIDs [33275, 33281, 33287]; 672 games planned.

2026-10-04T13:56:51.296963+00:00: stage1 149/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T13:57:41.373002+00:00: stage1 156/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T13:58:31.449724+00:00: stage1 168/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T13:59:21.527962+00:00: stage1 173/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:00:11.615928+00:00: stage1 182/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:01:01.709993+00:00: stage1 189/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:01:51.786349+00:00: stage1 197/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:02:41.863807+00:00: stage1 201/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:03:31.943170+00:00: stage1 210/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:04:22.040476+00:00: stage1 215/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:05:12.134113+00:00: stage1 223/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:06:02.229220+00:00: stage1 228/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:06:52.324722+00:00: stage1 237/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:07:42.405237+00:00: stage1 243/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:08:32.480522+00:00: stage1 252/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:09:22.576260+00:00: stage1 258/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:10:12.654728+00:00: stage1 268/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:11:02.732067+00:00: stage1 276/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:11:52.805675+00:00: stage1 285/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:12:42.880901+00:00: stage1 292/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:13:45.814540+00:00: stage1 302/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:14:35.891987+00:00: stage1 311/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:15:25.968781+00:00: stage1 316/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:16:16.064748+00:00: stage1 325/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:17:06.166443+00:00: stage1 328/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:17:56.268594+00:00: stage1 334/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:18:46.348866+00:00: stage1 340/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:19:36.427523+00:00: stage1 349/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:20:26.505922+00:00: stage1 353/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:21:16.584453+00:00: stage1 362/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:22:06.659076+00:00: stage1 367/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:22:56.747974+00:00: stage1 375/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:23:46.825819+00:00: stage1 382/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:24:36.902706+00:00: stage1 390/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:25:27.000119+00:00: stage1 395/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:26:17.087378+00:00: stage1 403/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:27:07.179348+00:00: stage1 408/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:27:57.251055+00:00: stage1 417/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:28:47.326306+00:00: stage1 423/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:29:37.403688+00:00: stage1 432/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:30:27.483351+00:00: stage1 437/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:31:17.560453+00:00: stage1 445/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:32:07.636896+00:00: stage1 451/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:32:57.715279+00:00: stage1 462/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:33:47.792803+00:00: stage1 468/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:34:37.889355+00:00: stage1 479/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:35:27.968344+00:00: stage1 486/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:36:18.076451+00:00: stage1 499/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:37:08.169606+00:00: stage1 505/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:37:58.275227+00:00: stage1 513/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:38:59.746460+00:00: stage1 521/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:39:49.827381+00:00: stage1 528/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:40:39.903169+00:00: stage1 537/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:41:29.980001+00:00: stage1 549/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:42:20.054600+00:00: stage1 557/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:43:10.129984+00:00: stage1 569/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:44:00.203898+00:00: stage1 577/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:44:50.289753+00:00: stage1 589/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:45:40.371483+00:00: stage1 593/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:46:30.448648+00:00: stage1 602/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:47:20.542885+00:00: stage1 607/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:48:10.618451+00:00: stage1 615/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:49:00.694026+00:00: stage1 623/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:49:50.782862+00:00: stage1 637/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:50:40.861408+00:00: stage1 644/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:51:30.942832+00:00: stage1 655/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:52:21.020071+00:00: stage1 661/672 receipts; owned running workers [33275, 33281, 33287].

2026-10-04T14:53:11.096639+00:00: stage1 670/672 receipts; owned running workers [33281].

2026-10-04T14:53:49.026229+00:00 PID 33152: stage1 complete: 672/672 games; all owned workers exited.

2026-10-04T14:53:49.776206+00:00 PID 33152: Receipt audit: 672 games, 3 candidate and 2 opposing rejected commands, all outcomes retained.

2026-10-04T14:53:50.442596+00:00 PID 33152: Stage 1 ranked. Advancing ['mixture', 'h320', 'h160-i20', 'k2', 'policy16', 'terminal4', 'h600-i10'].

2026-10-04T14:53:50.515118+00:00 PID 33152: stage2 launched owned worker PIDs [97003, 97009, 97015]; 672 games planned.

2026-10-04T14:54:01.172286+00:00: stage2 0/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:55:41.190915+00:00: stage2 12/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:56:31.269393+00:00: stage2 21/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:57:21.363236+00:00: stage2 28/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:58:11.439573+00:00: stage2 40/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:59:01.518533+00:00: stage2 47/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T14:59:51.592071+00:00: stage2 55/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:00:41.670317+00:00: stage2 59/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:01:31.745987+00:00: stage2 67/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:02:21.823972+00:00: stage2 72/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:03:11.900528+00:00: stage2 81/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:04:01.977683+00:00: stage2 87/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:04:52.050672+00:00: stage2 95/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:05:42.146538+00:00: stage2 101/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:06:32.238861+00:00: stage2 112/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:07:22.313490+00:00: stage2 120/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:08:12.389668+00:00: stage2 129/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:09:02.468508+00:00: stage2 134/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:09:52.546078+00:00: stage2 143/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:10:42.625727+00:00: stage2 148/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:11:32.704664+00:00: stage2 158/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:12:22.783482+00:00: stage2 161/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:13:12.858883+00:00: stage2 170/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:14:02.944947+00:00: stage2 175/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:14:53.037242+00:00: stage2 183/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:15:43.133528+00:00: stage2 188/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:16:33.235735+00:00: stage2 199/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:17:23.333200+00:00: stage2 205/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:18:13.422935+00:00: stage2 216/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:19:03.510194+00:00: stage2 221/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:19:53.589773+00:00: stage2 230/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:20:43.665452+00:00: stage2 236/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:21:33.744787+00:00: stage2 243/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:22:23.843612+00:00: stage2 251/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:23:13.921893+00:00: stage2 261/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:24:04.000074+00:00: stage2 266/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:24:54.077934+00:00: stage2 275/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:25:44.157406+00:00: stage2 282/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:26:34.234264+00:00: stage2 289/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:27:24.311605+00:00: stage2 295/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:28:14.410452+00:00: stage2 303/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:29:04.509132+00:00: stage2 310/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:29:54.585666+00:00: stage2 322/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:30:44.664677+00:00: stage2 330/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:31:34.739319+00:00: stage2 340/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:32:24.813749+00:00: stage2 347/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:33:14.902078+00:00: stage2 357/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:34:05.000826+00:00: stage2 364/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:34:55.104254+00:00: stage2 371/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:35:45.186473+00:00: stage2 375/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:36:35.264986+00:00: stage2 384/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:37:25.342132+00:00: stage2 390/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:38:15.434970+00:00: stage2 398/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:39:05.525448+00:00: stage2 405/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:39:55.600885+00:00: stage2 414/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:40:45.680745+00:00: stage2 421/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:41:35.756407+00:00: stage2 429/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:42:25.833575+00:00: stage2 435/672 receipts; owned running workers [97003, 97009, 97015].

Expanded seed audit passed: 302 ignored NPZ game archives inspected through metadata only; every seed equals its previously scanned JSON sidecar, no overlap. No compressed game files of the other searched formats found.

2026-10-04T15:43:15.913373+00:00: stage2 443/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:44:05.993209+00:00: stage2 450/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:44:56.075176+00:00: stage2 463/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:46:32.084014+00:00: stage2 475/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:47:22.162669+00:00: stage2 487/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:48:12.255715+00:00: stage2 496/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:49:02.355257+00:00: stage2 505/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:49:52.455132+00:00: stage2 513/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:50:42.545150+00:00: stage2 521/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:51:32.664252+00:00: stage2 527/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:52:22.781290+00:00: stage2 539/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:53:12.855579+00:00: stage2 545/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:54:02.933922+00:00: stage2 552/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:54:53.022582+00:00: stage2 558/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:55:43.114457+00:00: stage2 568/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:56:33.208152+00:00: stage2 575/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:57:23.306540+00:00: stage2 586/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:58:13.397839+00:00: stage2 590/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:59:03.500213+00:00: stage2 599/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T15:59:53.595815+00:00: stage2 605/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:00:43.674510+00:00: stage2 612/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:01:33.751879+00:00: stage2 617/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:02:23.847131+00:00: stage2 624/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:03:13.926116+00:00: stage2 630/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:04:04.004002+00:00: stage2 638/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:04:54.083577+00:00: stage2 649/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:05:44.160289+00:00: stage2 656/672 receipts; owned running workers [97003, 97009, 97015].

2026-10-04T16:06:34.235989+00:00: stage2 666/672 receipts; owned running workers [97009, 97015].

2026-10-04T16:07:24.306797+00:00: stage2 668/672 receipts; owned running workers [97009].

2026-10-04T16:08:14.205058+00:00 PID 33152: stage2 complete: 672/672 games; all owned workers exited.

2026-10-04T16:08:14.380655+00:00: stage2 672/672 receipts; owned running workers [].

2026-10-04T16:08:15.030587+00:00 PID 33152: Receipt audit: 672 games, 3 candidate and 1 opposing rejected commands, all outcomes retained.

2026-10-04T16:08:15.705606+00:00 PID 33152: Stage 2 ranked. Advancing ['mixture', 'k2', 'policy16'].

2026-10-04T16:08:15.777817+00:00 PID 33152: stage3 launched owned worker PIDs [75274, 75280, 75286]; 576 games planned.

2026-10-04T16:09:04.456423+00:00: stage3 4/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:10:48.535254+00:00: stage3 18/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:11:38.626157+00:00: stage3 29/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:12:28.726429+00:00: stage3 35/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:13:18.819543+00:00: stage3 45/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:14:08.895248+00:00: stage3 52/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:14:58.989429+00:00: stage3 61/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:15:49.086088+00:00: stage3 66/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:16:39.184120+00:00: stage3 73/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:17:29.281713+00:00: stage3 80/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:18:19.380384+00:00: stage3 89/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:19:09.470292+00:00: stage3 94/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:19:59.562230+00:00: stage3 105/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:20:49.657793+00:00: stage3 110/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:21:39.755455+00:00: stage3 119/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:22:29.854921+00:00: stage3 124/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:23:19.945770+00:00: stage3 134/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:24:10.022377+00:00: stage3 141/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:25:00.097820+00:00: stage3 150/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:25:50.176514+00:00: stage3 157/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:26:40.255164+00:00: stage3 166/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:27:30.331314+00:00: stage3 172/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:28:20.418488+00:00: stage3 183/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:29:10.516723+00:00: stage3 187/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:30:00.602464+00:00: stage3 195/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:30:50.678179+00:00: stage3 203/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:31:40.766667+00:00: stage3 213/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:32:30.861314+00:00: stage3 218/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:33:20.937027+00:00: stage3 227/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:34:11.016966+00:00: stage3 232/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:35:01.094368+00:00: stage3 241/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:35:51.172635+00:00: stage3 246/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:36:41.264707+00:00: stage3 257/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:37:31.340229+00:00: stage3 263/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:38:21.433767+00:00: stage3 272/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:39:11.534692+00:00: stage3 279/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:40:01.639657+00:00: stage3 286/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:40:51.768205+00:00: stage3 291/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:41:41.869146+00:00: stage3 300/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:42:31.963240+00:00: stage3 305/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:43:22.057750+00:00: stage3 314/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:44:12.157784+00:00: stage3 319/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:45:02.255903+00:00: stage3 326/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:45:52.332306+00:00: stage3 332/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:46:42.412446+00:00: stage3 345/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:47:32.489171+00:00: stage3 350/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:48:22.567513+00:00: stage3 358/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:49:12.645769+00:00: stage3 365/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:50:02.746633+00:00: stage3 372/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:50:52.824482+00:00: stage3 378/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:51:42.902016+00:00: stage3 389/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:52:32.977317+00:00: stage3 396/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:53:23.053169+00:00: stage3 403/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:54:13.125832+00:00: stage3 410/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:55:03.202798+00:00: stage3 417/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:55:53.289234+00:00: stage3 422/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:56:43.368231+00:00: stage3 431/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:57:33.448039+00:00: stage3 437/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:58:23.524294+00:00: stage3 447/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T16:59:13.598796+00:00: stage3 454/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:00:03.680649+00:00: stage3 462/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:01:12.911989+00:00: stage3 470/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:02:02.988050+00:00: stage3 480/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:02:53.063414+00:00: stage3 488/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:03:43.138945+00:00: stage3 495/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:04:33.217368+00:00: stage3 501/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:05:23.294752+00:00: stage3 511/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:06:13.370818+00:00: stage3 516/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:07:03.448524+00:00: stage3 525/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:07:53.525032+00:00: stage3 532/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:08:43.604611+00:00: stage3 541/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:09:33.682018+00:00: stage3 549/576 receipts; owned running workers [75274, 75280, 75286].

2026-10-04T17:10:23.755600+00:00: stage3 554/576 receipts; owned running workers [75274].

2026-10-04T17:11:13.830217+00:00: stage3 556/576 receipts; owned running workers [75274].

2026-10-04T17:12:03.905569+00:00: stage3 559/576 receipts; owned running workers [75274].

2026-10-04T17:12:53.978945+00:00: stage3 561/576 receipts; owned running workers [75274].

2026-10-04T17:13:44.053316+00:00: stage3 564/576 receipts; owned running workers [75274].

2026-10-04T17:14:34.128196+00:00: stage3 566/576 receipts; owned running workers [75274].

2026-10-04T17:15:24.200721+00:00: stage3 569/576 receipts; owned running workers [75274].

2026-10-04T17:16:14.298468+00:00: stage3 570/576 receipts; owned running workers [75274].

2026-10-04T17:17:04.377084+00:00: stage3 573/576 receipts; owned running workers [75274].

2026-10-04T17:17:54.449769+00:00: stage3 575/576 receipts; owned running workers [75274].

2026-10-04T17:17:59.087163+00:00 PID 33152: stage3 complete: 576/576 games; all owned workers exited.

2026-10-04T17:17:59.801710+00:00 PID 33152: Receipt audit: 576 games, 2 candidate and 2 opposing rejected commands, all outcomes retained.

2026-10-04T17:18:00.386324+00:00 PID 33152: Stage 3 ranked. Advancing ['mixture'].

2026-10-04T17:18:00.405965+00:00 PID 33152: Confirmation preregistered for mixture; no confirmation games started.

2026-10-04T17:18:00.484915+00:00 PID 33152: confirmation launched owned worker PIDs [48369, 48375, 48381]; 640 games planned.

2026-10-04T17:18:44.545473+00:00: confirmation 5/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:22:22.854875+00:00: confirmation 35/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:23:12.954738+00:00: confirmation 41/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:24:03.048292+00:00: confirmation 49/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:24:53.145501+00:00: confirmation 55/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:25:43.241744+00:00: confirmation 64/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:26:33.332193+00:00: confirmation 69/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:27:23.427613+00:00: confirmation 78/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:28:13.522127+00:00: confirmation 83/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:29:03.619157+00:00: confirmation 93/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:29:53.722917+00:00: confirmation 97/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:30:43.818531+00:00: confirmation 107/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:31:33.909311+00:00: confirmation 112/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:32:24.003921+00:00: confirmation 119/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:33:14.081362+00:00: confirmation 124/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:34:04.159912+00:00: confirmation 130/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:34:54.238436+00:00: confirmation 136/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:35:44.314638+00:00: confirmation 144/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:36:34.394025+00:00: confirmation 150/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:37:24.486064+00:00: confirmation 160/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:38:14.565344+00:00: confirmation 167/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:39:04.642709+00:00: confirmation 175/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:39:54.719282+00:00: confirmation 182/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:40:44.793709+00:00: confirmation 190/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:41:34.878864+00:00: confirmation 195/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:42:24.956208+00:00: confirmation 203/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:43:15.034568+00:00: confirmation 208/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:44:05.114277+00:00: confirmation 217/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:44:55.192820+00:00: confirmation 222/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:45:45.269035+00:00: confirmation 230/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:46:35.365673+00:00: confirmation 236/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:47:25.469676+00:00: confirmation 243/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:48:15.565862+00:00: confirmation 251/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:49:05.644767+00:00: confirmation 264/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:49:55.722113+00:00: confirmation 274/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:50:45.800857+00:00: confirmation 288/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:51:35.877320+00:00: confirmation 300/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:52:25.956369+00:00: confirmation 316/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:53:16.035157+00:00: confirmation 325/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:54:06.109312+00:00: confirmation 342/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:54:56.186311+00:00: confirmation 353/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:55:46.262092+00:00: confirmation 368/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:56:36.339576+00:00: confirmation 378/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:57:26.416094+00:00: confirmation 391/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:58:16.497325+00:00: confirmation 403/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:59:06.577771+00:00: confirmation 421/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T17:59:56.657726+00:00: confirmation 431/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:00:46.733253+00:00: confirmation 447/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:01:36.810289+00:00: confirmation 458/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:02:26.884352+00:00: confirmation 471/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:03:16.963113+00:00: confirmation 480/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:04:07.042724+00:00: confirmation 493/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:04:57.120851+00:00: confirmation 501/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:05:47.196772+00:00: confirmation 514/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:06:37.272574+00:00: confirmation 522/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:07:27.349843+00:00: confirmation 533/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:08:17.425974+00:00: confirmation 542/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:09:07.502326+00:00: confirmation 555/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:09:57.577442+00:00: confirmation 564/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:10:47.654958+00:00: confirmation 577/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:11:37.731295+00:00: confirmation 586/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:12:44.610060+00:00: confirmation 604/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:13:34.685688+00:00: confirmation 612/640 receipts; owned running workers [48369, 48375, 48381].

2026-10-04T18:14:24.762880+00:00: confirmation 624/640 receipts; owned running workers [48369, 48375].

2026-10-04T18:15:14.837960+00:00: confirmation 628/640 receipts; owned running workers [48369, 48375].

2026-10-04T18:16:04.909814+00:00: confirmation 634/640 receipts; owned running workers [48369].

2026-10-04T18:16:54.983691+00:00: confirmation 636/640 receipts; owned running workers [48369].

2026-10-04T18:17:43.403398+00:00 PID 33152: confirmation complete: 640/640 games; all owned workers exited.

2026-10-04T18:17:43.971364+00:00 PID 33152: Receipt audit: 640 games, 1 candidate and 2 opposing rejected commands, all outcomes retained.

2026-10-04T18:17:45.056951+00:00: confirmation 640/640 receipts; owned running workers [].

2026-10-04T18:18:29.590588+00:00 PID 33152: Tournament, confirmation and isolated-worker one/four-thread timing complete. No verified quiet-core measurement; external processes untouched.

2026-10-04T18:18:35.130083+00:00: confirmation 640/640 receipts; owned running workers [].

2026-10-04T18:21:44.513974+00:00 PID 13119: Descriptive timing: 1 Torch threads, game 1/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:22:08.030833+00:00 PID 13119: Descriptive timing: 1 Torch threads, game 2/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:22:35.471398+00:00 PID 13119: Descriptive timing: 1 Torch threads, game 3/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:22:51.005576+00:00 PID 13119: Descriptive timing: 1 Torch threads, game 4/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:23:18.144191+00:00 PID 13119: Descriptive timing: 4 Torch threads, game 1/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:23:43.091847+00:00 PID 13119: Descriptive timing: 4 Torch threads, game 2/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:24:12.678064+00:00 PID 13119: Descriptive timing: 4 Torch threads, game 3/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:24:29.618971+00:00 PID 13119: Descriptive timing: 4 Torch threads, game 4/4 complete. Outcome excluded from all strength tests.

2026-10-04T18:24:29.655495+00:00 PID 13119: Eight descriptive timing games complete. One/four Torch threads; native search remains serial. External host load recorded, no hard core-affinity claim.

2026-10-04T18:28:52.432806+00:00 PID 20499: Final audit and RESULTS.md complete: all 2,560 scored games plus eight separate timing games verified; primary and secondary checks passed. Quiet-core isolation remains explicitly unverified.

Final seed scan also included ignored log/checkpoint directories: 906623 seed fields, zero external overlap.
