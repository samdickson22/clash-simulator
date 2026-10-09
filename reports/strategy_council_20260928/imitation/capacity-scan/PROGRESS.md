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
