# Human-prior capacity scan

Frozen plan/configs committed and pushed **841c44b0** before fitting.
Operational staging/guards committed **e496385e**. Arms288/384/480, fixed6heads;
192control reusesT11seed21 and replays11000→11615 only.

Detached pipelines started2026-10-09T19:49Z. Supervisors:
13=793922 (288),14=543994 (384),15=434735 (480),16=4049421 (192).
Perhost work `/mpac/sdicks02/repos/clasher-lease/capacity-scan-20261009-v1/`.
Each10second guard enforceslease/reclaim,≤16Clasherprocesses,48GBPSS,8GiBGPUreserve,
nice≥10, ownedSTOPfile, hardstopOct11T03:30Z. NoCPU sims or08/Mac use.

04studentworker reports259/259storefilesSHAequal and authorizes read-onlypulls.
Copyonlytrain/dev/publicmask; cap153600KiB/s perreceiver (~450MiB/s total),
sendernice10.16rehashesitsoriginalverifiedstore. Every130requiredfilesmust
hashbeforefitting. OriginalT11trainers/checkpoints remainunchanged.

Light05stdlibcontroller source `control.py` reads only smallreceipts/logtails,
relays192quarterNLL, and stops at39.8conservativeGPU-hours (includingstaging)
orOct11T03:00Z. State `/mpac/sdicks02/jobs/clasher/capacity-scan-control-20261009-v1/state.json`;
completion `complete.json`. GPUactualwall uses trainer `scan-segments.jsonl`.
Controller r2 adds boundedrelay retries/cachedaccountingafterunreachablehost;
r1 ownPID1548805stopped, nofitting restarted.

Scientificquartertarget95,142,909rows; firsteffectivebatch95,144,680/step11615.
NLLgain<0.005kills. Widerarms areoffline-only. Fullcurvesrequiredforsurvivors,
resourcecensoringexplicitif40GPU-hour/leasedeadlinepreventscompletion.
NoNLLoutcomeyet; stagingandpreflightinprogress.

Temporary ten-minute same-worker continuation enabled. First next run
2026-10-09T20:02:12.126Z; exact schedule ID in `continuation.json`.
Disable after terminal report. Scientific results still pending.

Before any fitting, operational exact-resume repair committed/pushed **b80151fe**.
Active adapter SHA `e82ca22fe1eb5f3df3dd2ed1b2bfcac48182212d4cfdc417a8314795e7b0e174`.
Configs and scientific choices unchanged; see dated resume amendment.16's own
verifier briefly paused during the commit/deployment, then resumed. No fitting
restart. Wide resumes require explicit checkpoint SHA and own output directory;
quarter recovery preserves the exact boundary and saved NLL; scientific kills
cannot resume. Small `collect.py` will gather final curves/costs/SHA pointers.

2026-10-09T19:58Z:16completed all130train/dev/publicmask SHA checks and entered
control replay successfully. Observedstep11016,32.9GBPSS,29.1GiBpeakGPUreserved;
allguardcapsPASS. Earlyloader-inclusive2,226rows/s includes startup/sampling and
is not the settled rate. Threewidecopiesremainactive with sixprocesses/<0.5GBPSS
each. NoquarterNLL orkilldecisionyet. `first-fit-receipt.json` records this sample.
The temporary continuation owns the remaining originaltask; results report pending.

2026-10-09 20:02Z: All four original pipelines and the sole controller remain
healthy. Width 192 reached step 11,157 / 91,392,744 rows at 4,624 loader-inclusive
rows/s. Peak borrower PSS remains below 37.5 GB, with more than 19 GiB GPU free
at the sample. Each wide receiver has approximately 124.3 GB present; copies
remain active at the frozen rate limit, six processes and below 0.5 GB PSS.

Control replay validation PASS: steps 11,001, 11,020, 11,050, 11,100 and 11,150
are bit-identical to the original T11 log for rows, cursor, all six loss terms,
gradient norm and learning rate. This directly validates the unchanged control
trajectory despite allocator cleanup and loader parallelism. Evidence is in
`control-replay-trajectory.json`. No capacity dev-NLL or kill decision yet.
No jobs restarted; scientific freeze and active source pins unchanged.

2026-10-09 20:12Z: The control reached exactly step 11,615 / 95,144,680 rows,
saved its quarter checkpoint, and entered the full 11,776,480-row dev pass.
No extra optimizer step was taken. Training replay processed 5,038,080 new rows;
last loader-inclusive rate was 5,481 rows/s. Checkpoint SHA and row evidence are
in `control-boundary.json`. No quarter NLL has been published yet.

All three wider LAN transfers completed and their original SHA verification
phases are active. No duplicate launch or training restart. The sole controller
and every lease/resource guard remain healthy. Wide hosts use three processes
and below 0.5 GB PSS during checks; control peak PSS remains below 37.5 GB.
Conservative pipeline accounting was approximately 1.55 GPU-hours, including
staging; final actual GPU wall cost remains pending trainer segment completion.

2026-10-09 20:22Z: Control quarter full-dev NLL sealed at **0.27726436294161033**
for exactly 95,144,680 rows (all 11,776,480 dev rows). Its sole segment used
0.3742555 actual GPU-hours, including replay, initialization and dev. Last replay
training rate was 5,481 loader-inclusive rows/s. Exit0; GPU16 compute-process
list independently empty, released for coordinator reuse. Control NLL relayed to
13/14/15. Complete evidence and checkpoint SHA are in `control-complete.json`.

All three wide stores passed 130/130 SHA checks and their original fits started.
Early rates:288=4,213,384=3,496,480=4,150 rows/s (startup still contributes).
No wide dev outcome or scientific kill yet.

Width480's cached peak46,082MiB briefly breached8GiB reserve between guard checks.
Its own trainer434818 was checkpointed at175 /1,433,600rows and exited0; all old
six PIDs verified gone. This is a technical pause, not a scientific kill. Exact
checkpoint/RNG/model/optimizer/scheduler/config/hash audit PASS, SHA pointer in
`480-allocator-stop.json`. Pre-wide-dev allocator amendment/operations freeze
committed **e8b4473b**. Microbatch2048 and every scientific setting stay fixed.

Width480 resumed with hard allocator fraction0.78 under label**width480-v2**,
supervisor**568625**, preserving all original artifacts. Observed resumed step198,
6 processes,26.6GBPSS,15.3GiBGPUfree; no OOM or further headroom breach. Sole
controller r3 reads active-label pointers and cumulative guard history to retain
all original/continuation costs.288/384fits were never stopped. Ten-minute
continuation remains enabled; final matched-wide NLL comparison still pending.

2026-10-09 20:32Z: All three wide fits and the sole controller are healthy.
Width288:4.56Mrows/5,547rows/s;384:3.39M/4,086;480:3.01M/4,301. Each has six
processes; sampled PSS is31–36GB and peak PSS≤40.3GB. AllGPUheadroom checksPASS.
Width480's hard allocator ceiling is holding: peak reserved37,756MiB, below its
38,338MiB ceiling, with no OOM. Its resumed trajectory continues past step367.
No additional stops/restarts or scientific changes. No wide dev/kill decisions
are due before95,144,680rows. Control NLL0.27726436294161033 remains sealed.
Conservative cumulative pipeline cost2.625hours includes staging and both480
segments; actual final per-arm GPU wall costs remain pending completion.
Compact evidence: `monitor-20261009T2032Z.json`. Monitoring continues.

2026-10-09 20:43Z: Width480-v2 failed CUDA OOM after step598; full FFN-dropout
traceback confirms a1.41GiB request exceeded allocator0.78 allowance despite
9.68GiBphysicalfree. This is a technical failure, not a scientific kill. Latest
durable checkpoint is175 /1,433,600rows; failed176–598work will be replayed.
Coordinator explicitly authorizes micro1024 with batch8192; dated amendment,
new config/freeze and full failure receipt are being committed before any480dev
outcome or relaunch. If that cannot fit,480is infeasible under lease limits.
288/384continue healthy; controller and cumulative accounting remain active.

2026-10-09 20:45Z: Micro1024 amendment committed/pushed **f8dd81a6** before
width480-v3 launch20:44:27Z, supervisor637497/trainer637517. Resume is175 /
1,433,600rows from originalSHA-pinnedcheckpoint. Runtime start confirms micro1024,
effective8192batch and identical source/data hashes; first update176 /1,441,792rows
proves saved cursor restoration. Observedstep199 with sixprocesses,36.0GBPSS and
>34GiBGPUfree; no traceback or stop. All prior failure/allocator artifacts remain.
The changed summation/dropout order is disclosed in the dated amendment.
Controller r3 follows v3 and retains all guard segments. Existing ten-minute
continuation updated with explicit infeasibility fallback; next20:52:19Z.
No wide devNLL or scientific kill yet; control remains0.27726436294161033.

2026-10-09 20:52Z: Sole controller and all three current fits remain healthy.
Width288: step1497, 12,263,424rows, 5991loader-inclusive rows/s.
Width384: step1053, 8,626,176rows, 4199loader-inclusive rows/s.
Width480: step428, 3,506,176rows, 4597loader-inclusive rows/s.
Width480-v3 has not yet reached the previous failing batch599; no new OOM,
stop or restart. Every arm uses sixprocesses, currentPSS<38GB, peakPSS≤41.5GB
and ≥8GiBfree. Frozen configs and authorized480micro1024 remain unchanged.
All wide quarter NLLs/kill decisions still pending95,144,680rows; control sealed
at0.27726436294161033. Conservative cumulative pipeline cost3.561GPU-hours,
including staging and both previous480segments; actual total cost remains
pending completed trainersegments. Evidence: `monitor-20261009T2052Z.json`.
Temporary continuation remains enabled;16 stays finished/released.

2026-10-09 21:02Z: Width480-v3 successfully replayed the previously failing
step599 /4,907,008rows with micro1024/effective8192/cap0.78. Independently
verified through784; no new OOM, stop or restart. PeakGPUreserved23,142MiB.
Width288: step2002, 16,400,384rows, 6098loader-inclusive rows/s.
Width384: step1395, 11,427,840rows, 4239loader-inclusive rows/s.
Width480: step798, 6,537,216rows, 4668loader-inclusive rows/s.
Sole controller and all current guards healthy, sixprocesses/arm, peakPSS
41.47GB, sampledGPUfree≥29.1GiB. Control stays sealed0.27726436294161033;
wide quarter NLLs and every scientific kill decision remain pending.
Conservative cumulative pipeline cost4.096GPU-hours includes staging
and all480segments; final actualcost pending segmentcompletion. No config,
data or trainer edits. Evidence: `monitor-20261009T2102Z.json`. Existing
ten-minute continuation remains enabled and16 stays released.

2026-10-09 21:13Z: All three fits and the sole controller remain healthy.
Width 288: step 2472, 20,250,624 rows, 6136 loader-inclusive rows/s.
Width 384: step 1763, 14,442,496 rows, 4366 loader-inclusive rows/s.
Width 480: step 1151, 9,428,992 rows, 4688 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
at least 28.5 GiB. No OOM, stop, restart or recipe change. Width 480 has
a new durable scheduled checkpoint at step 1,000 / 8,192,000 rows, SHA
`0020fe54b538e55d2718884a8766f7119543aaa3b652c14500d1c9450e898bef`.
Verified on 15; original step-175 checkpoint and failed artifacts retained.
No weights copied to 05 or git. Receipt: `480-step1000-checkpoint.json`.
Wide quarter NLLs/kill decisions remain pending; control stays sealed at
0.27726436294161033. Conservative cumulative pipeline cost 4.606 GPU-hours
includes staging and every 480 segment; final actual costs await completion.
Monitoring evidence: `monitor-20261009T2112Z.json`. Temporary continuation
remains enabled; 16 stays released.

2026-10-09 21:23Z: Controller and all three fits remain healthy.
Width 288: step 2872, 23,527,424 rows, 6109 loader-inclusive rows/s.
Width 384: step 2094, 17,154,048 rows, 4446 loader-inclusive rows/s.
Width 480: step 1468, 12,025,856 rows, 4697 loader-inclusive rows/s.
Six processes per arm, peak PSS 41.47 GB, sampled GPU free memory
≥31.4 GiB; no new OOM, stop or restart. Micro1024/batch8192/cap0.78
for 480 and both original smaller-arm configs remain unchanged. Wide quarter
NLLs and kill decisions are pending; matched 192 control remains sealed at
0.27726436294161033. Conservative cumulative pipeline cost 5.064 GPU-hours
includes staging and every 480 segment; final actual costs await completion.
Compact evidence: `monitor-20261009T2122Z.json`. No trainer or data edits.
Temporary continuation remains enabled; 16 stays released.

2026-10-09 21:33Z: All three fits and the sole controller remain healthy.
Width 288: step 3413, 27,959,296 rows, 6265 loader-inclusive rows/s.
Width 384: step 2492, 20,414,464 rows, 4567 loader-inclusive rows/s.
Width 480: step 1821, 14,917,632 rows, 4704 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥27.1 GiB. No new OOM, stop, restart, source, config or data edits.
Width 480 retains micro1024/effective8192/cap0.78; failure artifacts remain.
Wide quarter NLLs and kill decisions await 95,144,680 rows; sealed 192 control
NLL stays 0.27726436294161033. Conservative cumulative pipeline cost is
5.574 GPU-hours, including staging and all 480 segments; final actual
costs await completion. Evidence: `monitor-20261009T2132Z.json`.
Temporary continuation remains enabled; 16 stays released.

2026-10-09 21:43Z: Controller and all three fits remain healthy.
Width 288: step 3963, 32,464,896 rows, 6397 loader-inclusive rows/s.
Width 384: step 2865, 23,470,080 rows, 4619 loader-inclusive rows/s.
Width 480: step 2174, 17,809,408 rows, 4707 loader-inclusive rows/s.
Six processes per arm, peak PSS 41.47 GB, sampled GPU free memory
≥30.8 GiB. No new OOM, stop, restart or scientific change. Width 480
keeps micro1024/effective8192/cap0.78; original and failed artifacts retained.
Wide quarter NLLs and kill decisions remain pending at 95,144,680 rows.
The matched 192 control stays 0.27726436294161033. Conservative cumulative
pipeline cost 6.084 GPU-hours includes staging and every 480 segment;
final actual costs await completion. Evidence: `monitor-20261009T2142Z.json`.
No trainer, config or data edits. Continuation remains enabled; 16 stays released.

2026-10-09 21:53Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 4472, 36,634,624 rows, 6477 loader-inclusive rows/s.
Width 384: step 3219, 26,370,048 rows, 4656 loader-inclusive rows/s.
Width 480: step 2510, 20,561,920 rows, 4712 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥36.3 GiB. No new OOM, stop, restart or recipe change. All wide quarter
NLLs and scientific kill decisions remain pending at 95,144,680 rows; the
matched 192 control stays sealed at 0.27726436294161033. Conservative cumulative
pipeline cost 6.568 GPU-hours includes staging and every 480 segment;
actual final costs await completion. Evidence: `monitor-20261009T2152Z.json`.
No source, config or data edits; failure artifacts retained, continuation
enabled and 16 still released.

2026-10-09 22:03Z: Controller and all three fits remain healthy.
Width 288: step 4979, 40,787,968 rows, 6507 loader-inclusive rows/s.
Width 384: step 3598, 29,474,816 rows, 4698 loader-inclusive rows/s.
Width 480: step 2863, 23,453,696 rows, 4714 loader-inclusive rows/s.
Six processes per arm, peak PSS 41.47 GB, sampled GPU free memory
≥22.2 GiB. No new OOM, stop, restart or scientific change. Width 480
continues with authorized micro1024/effective8192/cap0.78. Wide quarter
NLLs and kill decisions await 95,144,680 rows; matched 192 control remains
0.27726436294161033. Conservative cumulative pipeline cost 7.078 GPU-hours
includes staging and every 480 segment; final actual costs await completion.
Evidence: `monitor-20261009T2202Z.json`. No source, config or data edits.
Failure artifacts retained; temporary continuation enabled; 16 remains released.

2026-10-09 22:13Z: All three fits and the sole controller remain healthy.
Width 288: step 5475, 44,851,200 rows, 6521 loader-inclusive rows/s.
Width 384: step 3939, 32,268,288 rows, 4686 loader-inclusive rows/s.
Width 480: step 3216, 26,345,472 rows, 4716 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥21.8 GiB. No new OOM, stop, restart or recipe change. Width 480
retains micro1024/effective8192/cap0.78. Wide quarter NLLs and scientific
kill decisions remain pending at 95,144,680 rows; matched 192 control is
0.27726436294161033. Conservative cumulative pipeline cost 7.587 GPU-hours
includes staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261009T2212Z.json`. No source, config or data edits.
Failure artifacts retained; continuation enabled; 16 remains released.

2026-10-09 22:23Z: Controller, all three fits and all guards remain healthy.
Width 288: step 5937, 48,635,904 rows, 6520 loader-inclusive rows/s.
Width 384: step 4370, 35,799,040 rows, 4794 loader-inclusive rows/s.
Width 480: step 3553, 29,106,176 rows, 4720 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥21.7 GiB. No new OOM, stop, restart or scientific change. Width 480
retains authorized micro1024/effective8192/cap0.78. Wide quarter NLLs and
kill decisions await 95,144,680 rows; matched 192 control remains sealed
at 0.27726436294161033. Conservative cumulative pipeline cost 8.071 GPU-hours
includes staging and every 480 segment; final actual costs await completion.
Evidence: `monitor-20261009T2222Z.json`. No source, config or data edits.
Failure artifacts retained; continuation enabled; 16 remains released.

2026-10-09 22:33Z: Controller and all three fits remain healthy.
Width 288: step 6413, 52,535,296 rows, 6509 loader-inclusive rows/s.
Width 384: step 4749, 38,903,808 rows, 4816 loader-inclusive rows/s.
Width 480: step 3906, 31,997,952 rows, 4720 loader-inclusive rows/s.
Six processes per arm, peak PSS 41.47 GB, sampled GPU free memory
≥29.1 GiB. No new OOM, stop, restart or scientific change. Wide quarter
NLLs and kills remain pending at 95,144,680 rows; matched 192 control stays
0.27726436294161033. Conservative cumulative pipeline cost 8.581 GPU-hours
includes staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261009T2232Z.json`. No source, config or data edits.
Authorized 480 micro1024/effective8192/cap0.78 and all failure artifacts retained.
Temporary continuation remains enabled; 16 stays released.

2026-10-09 22:43Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 6860, 56,197,120 rows, 6472 loader-inclusive rows/s.
Width 384: step 5085, 41,656,320 rows, 4793 loader-inclusive rows/s.
Width 480: step 4261, 34,906,112 rows, 4723 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥30.0 GiB. No new OOM, stop, restart or scientific change. Wide quarter
NLLs and kill decisions remain pending at 95,144,680 rows; matched 192 control
stays 0.27726436294161033. Conservative cumulative pipeline cost
9.091 GPU-hours includes staging and every 480 segment; final actual
costs await completion. Evidence: `monitor-20261009T2242Z.json`. No source,
config or data edits; 480 micro1024/effective8192/cap0.78 remains fixed.
Failure artifacts retained; continuation enabled; 16 stays released.

2026-10-09 22:53Z: All three fits and the sole controller remain healthy.
Width 288: step 7259, 59,465,728 rows, 6419 loader-inclusive rows/s.
Width 384: step 5400, 44,236,800 rows, 4772 loader-inclusive rows/s.
Width 480: step 4596, 37,650,432 rows, 4723 loader-inclusive rows/s.
Six processes per arm; peak PSS 41.47 GB and sampled GPU free memory
≥32.7 GiB. No new OOM, stop, restart or scientific change. Wide quarter
NLLs and kills remain pending at 95,144,680 rows; matched 192 control is
0.27726436294161033. Conservative cumulative pipeline cost 9.575 GPU-hours
includes staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261009T2252Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 stays released.

2026-10-09 23:04Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 7721, 63,250,432 rows, 6346 loader-inclusive rows/s.
Width 384: step 5781, 47,357,952 rows, 4747 loader-inclusive rows/s.
Width 480: step 5003, 40,984,576 rows, 4724 loader-inclusive rows/s.
Six processes per arm; peak PSS 42.38 GB and sampled GPU free memory
≥21.8 GiB. No new OOM, stop, restart or scientific change. Wide quarter
NLLs and kills remain pending at 95,144,680 rows; matched 192 control is
0.27726436294161033. Width 288 is approaching its first epoch dev evaluation;
the frozen kill decision remains at the quarter boundary.
Conservative cumulative pipeline cost 10.161 GPU-hours includes
staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261009T2302Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 stays released.

2026-10-09 23:13Z: All three arms, guards and the sole controller remain healthy.
Width 288: step 7745, 63,441,640 rows, 6342 latest loader-inclusive rows/s.
Width 384: step 6066, 49,692,672 rows, 4736 latest loader-inclusive rows/s.
Width 480: step 5305, 43,458,560 rows, 4726 latest loader-inclusive rows/s.
Width 288 has reached its first epoch dev boundary at 63,441,640 rows.
Independent 13 observation at 23:12:54Z: GPU utilization 99%, all three owned
processes nice10, no traceback or dev NLL logged yet. No restart is indicated.
Sampled processes per host [3, 6, 6]; peak PSS 42.38 GB;
sampled GPU free memory ≥34.0 GiB. No new OOM, stop or scientific change.
Wide quarter NLLs and kills remain pending at 95,144,680 rows; matched 192
control remains 0.27726436294161033. No decision is made from epoch-one scoring.
Conservative cumulative pipeline cost 10.595 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261009T2312Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; failed artifacts retained.
Continuation remains enabled; 16 stays released.

2026-10-09 23:23Z: Width 288 completed its first epoch dev measurement and resumed training.
At matched 63,441,640 rows / step7745: NLL288 0.27972973786549959,
NLL192 0.28317389229603407, gain 0.003444154430534474.
This is an epoch curve point, not the frozen quarter decision; no kill fired.
Evidence: `width288-epoch1.json` (bounded own log tail).
Width 288: step 8030, 65,776,360 rows, 5944 loader-inclusive rows/s.
Width 384: step 6375, 52,224,000 rows, 4715 loader-inclusive rows/s.
Width 480: step 5641, 46,211,072 rows, 4727 loader-inclusive rows/s.
All guards and the sole controller remain healthy; six processes per arm;
peak PSS 42.38 GB; sampled GPU free memory ≥27.1 GiB.
No new OOM, stop, restart or recipe/data change. Wide quarter NLLs and kills
remain pending at 95,144,680 rows; quarter control is 0.27726436294161033.
Conservative cumulative pipeline cost 11.079 GPU-hours includes
staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261009T2322Z.json`. 480 micro1024/effective8192/cap0.78 stays fixed;
failure artifacts retained; continuation enabled; 16 remains released.

2026-10-09 23:33Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 8404, 68,840,168 rows, 5909 loader-inclusive rows/s.
Width 384: step 6696, 54,853,632 rows, 4706 loader-inclusive rows/s.
Width 480: step 5978, 48,971,776 rows, 4728 loader-inclusive rows/s.
Six processes per arm; peak PSS 42.38 GB; sampled GPU free memory
≥32.7 GiB. No new OOM, stop, restart or scientific change.
Width 288 epoch-one NLL stays 0.2797297378654996 at 63,441,640 rows;
its matched 192 gain is 0.003444154430534474. Quarter decisions remain pending
at 95,144,680 rows against 192 NLL 0.27726436294161033; no kill has fired.
Conservative cumulative pipeline cost 11.563 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261009T2332Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-09 23:43Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 8806, 72,133,352 rows, 5883 loader-inclusive rows/s.
Width 384: step 7038, 57,655,296 rows, 4700 loader-inclusive rows/s.
Width 480: step 6332, 51,871,744 rows, 4729 loader-inclusive rows/s.
Six processes per arm; peak PSS 42.38 GB; sampled GPU free memory
≥28.5 GiB. No new OOM, stop, restart or scientific change.
Width 288 epoch-one NLL remains 0.2797297378654996 at 63,441,640 rows;
its matched 192 gain is 0.003444154430534474. Quarter decisions remain pending
at 95,144,680 rows against 192 NLL 0.27726436294161033; no kill has fired.
Conservative cumulative pipeline cost 12.073 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261009T2342Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-09 23:53Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 9216, 75,492,072 rows, 5864 loader-inclusive rows/s.
Width 384: step 7429, 60,858,368 rows, 4725 loader-inclusive rows/s.
Width 480: step 6687, 54,779,904 rows, 4730 loader-inclusive rows/s.
Six processes per arm; peak PSS 43.12 GB; sampled GPU free memory
≥27.1 GiB. No new OOM, stop, restart or scientific change.
Width 384 is approaching its first epoch dev boundary. No new dev point;
width 288 epoch-one NLL remains 0.2797297378654996 at 63,441,640 rows.
Quarter decisions remain pending at 95,144,680 rows against 192 NLL
0.27726436294161033; no scientific kill has fired.
Conservative cumulative pipeline cost 12.583 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261009T2352Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-10 00:03Z: All three arms, guards and the sole controller remain healthy.
Width 288: step 9574, 78,424,808 rows, 5816 latest loader-inclusive rows/s.
Width 384: step 7745, 63,441,640 rows, 4760 latest loader-inclusive rows/s.
Width 480: step 7040, 57,671,680 rows, 4730 latest loader-inclusive rows/s.
Width 384 has reached its first epoch dev boundary at 63,441,640 rows.
Independent 14 observation at 00:03:01Z: GPU utilization 100%, three owned
processes nice10, no traceback or dev NLL logged yet. No restart indicated.
Sampled processes per host [6, 3, 6]; peak PSS 43.12 GB;
sampled GPU free memory ≥32.7 GiB. No new OOM, stop or scientific change.
Wide quarter NLLs and kills remain pending at 95,144,680 rows against matched
192 NLL 0.27726436294161033. Width 288 epoch-one NLL remains
0.2797297378654996 at 63,441,640 rows. No epoch-one kill decisions.
Conservative cumulative pipeline cost 13.093 GPU-hours includes
staging and all 480 segments; actual final costs await completion.
Evidence: `monitor-20261010T0002Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; failure artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-10 00:13Z: Width 384 completed its first epoch dev measurement and resumed training.
At matched 63,441,640 rows / step7745: NLL384 0.27839803498631882,
NLL192 0.28317389229603407, gain 0.0047758573097152479.
This is an epoch curve point, not the frozen quarter decision; no kill fired.
Evidence: `width384-epoch1.json` (bounded own log tail).
Width 288: step 9948, 81,488,616 rows, 5781 loader-inclusive rows/s.
Width 384: step 7764, 63,597,288 rows, 4509 loader-inclusive rows/s.
Width 480: step 7392, 60,555,264 rows, 4730 loader-inclusive rows/s.
All guards and the sole controller remain healthy; six processes per arm;
peak PSS 43.12 GB; sampled GPU free memory ≥34.0 GiB.
No new OOM, stop, restart or recipe/data change. Wide quarter NLLs and kills
remain pending at 95,144,680 rows; quarter control is 0.27726436294161033.
Conservative cumulative pipeline cost 13.602 GPU-hours includes
staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261010T0012Z.json`. 480 micro1024/effective8192/cap0.78 stays fixed;
failure artifacts retained; continuation enabled; 16 remains released.

2026-10-10 00:23Z: All three fits, guards and the sole controller remain healthy.
Width 288: step 10293, 84,314,856 rows, 5745 loader-inclusive rows/s.
Width 384: step 8010, 65,612,520 rows, 4468 loader-inclusive rows/s.
Width 480: step 7728, 63,307,776 rows, 4730 loader-inclusive rows/s.
Six processes per arm; peak PSS 43.12 GB; sampled GPU free memory
≥34.0 GiB. No new OOM, stop, restart or scientific change.
Width 480 is approaching its first epoch dev boundary; no new dev point.
Matched epoch-one NLLs at 63,441,640 rows remain 192 0.28317389229603407,
288 0.2797297378654996 and 384 0.2783980349863188.
Quarter decisions remain pending at 95,144,680 rows against 192 NLL
0.27726436294161033; no scientific kill has fired.
Conservative cumulative pipeline cost 14.086 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261010T0022Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; all failed artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-10 00:33Z: All three arms, guards and the sole controller remain healthy.
Width 288: step 10690, 87,567,080 rows, 5728 latest loader-inclusive rows/s.
Width 384: step 8280, 67,824,360 rows, 4434 latest loader-inclusive rows/s.
Width 480: step 7745, 63,441,640 rows, 4730 latest loader-inclusive rows/s.
Width 480 has reached its first epoch dev boundary at 63,441,640 rows.
Independent 15 observation at 00:33:02Z: GPU utilization 100%, three owned
processes nice19, no traceback or dev NLL logged yet. No restart indicated.
Sampled processes per host [6, 6, 3]; peak PSS 43.12 GB;
sampled GPU free memory ≥40.5 GiB. No new OOM, stop or scientific change.
Wide quarter NLLs and kills remain pending at 95,144,680 rows against matched
192 NLL 0.27726436294161033. Matched epoch-one NLLs remain 192
0.28317389229603407, 288 0.2797297378654996 and 384 0.2783980349863188.
No epoch-one kill decisions.
Conservative cumulative pipeline cost 14.595 GPU-hours includes
staging and all 480 segments; actual final costs await completion.
Evidence: `monitor-20261010T0032Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; failure artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-10 00:43Z: Width 480 completed its first epoch dev measurement and resumed training.
At matched 63,441,640 rows / step7745: NLL480 0.27781619329307483,
NLL192 0.28317389229603407, gain 0.0053576990029592375.
This point uses the pre-dev authorized micro1024 amendment f8dd81a6:
effective8192/cap0.78 unchanged; summation and dropout are not bit-identical.
Epoch curve point only; no quarter survival decision or scientific kill yet.
Evidence: `width480-epoch1.json` (bounded own log tail).
Width 288: step 11156, 91,384,552 rows, 5747 loader-inclusive rows/s.
Width 384: step 8587, 70,339,304 rows, 4422 loader-inclusive rows/s.
Width 480: step 7872, 64,482,024 rows, 4408 loader-inclusive rows/s.
All guards and the sole controller remain healthy; six processes per arm;
peak PSS 43.12 GB; sampled GPU free memory ≥21.7 GiB.
No new OOM, stop, restart or recipe/data change. Quarter NLLs and kills remain
pending at 95,144,680 rows; quarter control is 0.27726436294161033.
Conservative cumulative pipeline cost 15.104 GPU-hours includes
staging and all 480 segments; final actual costs await completion.
Evidence: `monitor-20261010T0042Z.json`. Failure artifacts retained;
continuation enabled; 16 remains released.

2026-10-10 00:53Z: Width 288 reached the frozen quarter boundary.
Own 13 log observation at 00:53:31Z: step11615 / 95,144,680 rows;
quarter-step-00011615.pt present (76,849,050 bytes observed). Full-dev
scoring is underway; quarter NLL, checkpoint SHA and kill decision pending.
No survival, scientific kill or resource-censoring claim is made.
Controller sample width 288: step 11615, 95,144,680 rows, 5768 latest loader-inclusive rows/s.
Controller sample width 384: step 8898, 72,887,016 rows, 4413 latest loader-inclusive rows/s.
Controller sample width 480: step 8123, 66,538,216 rows, 4366 latest loader-inclusive rows/s.
All guards and the sole controller remain healthy;
sampled processes per host [7, 6, 6]; peak PSS 43.34 GB;
sampled GPU free memory ≥43.8 GiB. No new OOM, stop or restart.
All three matched epoch-one points are retained. Quarter control remains
0.27726436294161033 at 95,144,680 rows; gain<0.005 rule remains frozen.
Conservative cumulative pipeline cost 15.614 GPU-hours includes
staging and every 480 segment; actual final costs await completion.
Evidence: `monitor-20261010T0052Z.json`. No source, config or data edits.
480 micro1024/effective8192/cap0.78 stays fixed; failure artifacts retained.
Continuation remains enabled; 16 remains released.

2026-10-10 01:03Z: Width 288 scientifically killed by the frozen quarter rule.
At exact 95,144,680 rows / step11615: NLL288 0.27418144592079313,
NLL192 0.27726436294161033, gain 0.0030829170208171996<0.005.
Guard exit0 at 01:01:57Z, no resource stop. Independent 13 verification at
01:03:22Z found all seven former owned PIDs gone, no GPU compute apps,
48,666 MiB free. GPU13 is released; never relaunch the killed arm.
Actual width288 fitting/scoring cost 4.734969255 GPU-hours; final logged
loader-inclusive throughput 5768 rows/s. Both measured curve points, store
receipt, source/config pins, log SHA and quarter-checkpoint SHA are archived
in `width288-result.json`. No weights committed.
Quarter checkpoint SHA0325bef0627e82f4bf46a5abbe2255036aaa387a7a4acedd326c564ad37632f8.
Width 384: step 9212, 75,459,304 rows, 4405 loader-inclusive rows/s; quarter pending.
Width 480: step 8458, 69,282,536 rows, 4370 loader-inclusive rows/s; quarter pending.
Remaining guards and the sole controller healthy; no new OOM or restart.
Conservative total pipeline cost 16.093 GPU-hours includes
staging and every 480 segment; remaining actual costs pending.
Evidence: `monitor-20261010T0102Z.json`. Frozen recipe and reporting data unchanged;
480 micro1024/effective8192/cap0.78 stays fixed; failure artifacts retained.
Continue 384/480 to their frozen decisions; wider use offline-only.
Continuation remains enabled; GPUs13 and16 released.
