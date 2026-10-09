# Delay fixes exploration — 2026-10-08

Exploration only; no preregistration, no training, no eval/heldout data or frozen edits.
Separate from search-ab (candidate coverage/reserve leaf); no d-sweep beyond the
requested d0/d27 latency contrast.

Task-owned files: loss_review/delay_{fixes,simulate,runtime}.py, native
engine-rs/src/delay_commands.rs plus additive opt-in method in scripts.rs,
tests/analysis/test_delay_fixes.py, reports/explore/delay-fixes/.
Existing S6, gate proposer, gate seeds and live-runtime default behavior unchanged.

Eight paired arms U0/U27 (opponent immediate); S0/S27 (opponent d22, cadence10,
4 pending slots); N2/N4 (own outstanding capacity2/4, S27 baseline); I0/IF
(released v1 CPU fp32 T1 matched-count proposals, current vs fair modeled t+27,
both with opponent d22). Physical and rollout scheduling change together.
All game seeds 2**48+50000+i; helper seeds +100000/+100001/+100002; seed-only
legacy exclusion file audited before sim. Matchups are five train-catalog
archetypes, three script styles, both seats, balanced on paired seed.

Build succeeded on13 via wrapper v2, isolated lease-local runtime. First
preflight wrapper failed supervision (missing aggregate key) and exited; fresh
label retry retained separately. No wrapper bypass.

Coordinator clarification: opponent decision→execution22-tick lag is invisible.
Physical opponent reservations live only in the experiment driver, never in the
battle's public packets, accepted-event stream or planner root. Only an accepted
physical execution publishes its card event. Search constructs fresh hypothetical
future opponent commands, and never imports true pending opponent commands.
Added both-seat public-packet equality test for all ticks0..22 before execution;
accepted execution then changes the public board and emits the event at22.

23:45Z coordinator deployed wrapper v2 hotfix (47 tests +09 smoke). Fresh
host16 admission succeeded for p1000 (25 extra paired seeds). A bounded task-only
controller will extend that host to1250 total scheduled seeds if successive
admissions pass; all existing primary foreground shards continue. Home08 GPU
recovered to100% and its26 workers resumed.11 remains GPU-paused intermittently.

At 23:58–00:02Z the coordinator superseded the original host allocation:
13/15 completely closed until explicit release, 09/14 ≤15 workers, 11/16 ≤30,
home08 ≤32. The original controller was stopped before another launch. 13 and
15 drained to zero within ten minutes; their last shards finished and were
collected. 09/14 pools were stopped and resumed at15 with completed games
preserved. Their technical-stop receipts retain consumed CPU. 11's stalled
26-worker pool was similarly restarted under the repaired wrapper.

The initial three-high-sample GPU resume guard aliased against repeating
100/100/0 device readings. New jobs resume on one high sample; idle GPUs without
any compute process permit CPU work. During the 13/15 drain, all verified own
pool workers were resumed only after nvidia reported no GPU compute process.
Monitor-reported pause counts during that brief manual idle-GPU drain can
therefore overstate actual paused time. No GPU owner jobs were signalled.

16's p1000 restart was refused for an existing Clasher process below the nice
minimum. No bypass. The original zero-completion p1000 attempt was stopped for
the guard correction (136.84 observed process CPU seconds; receipt preserved).
The replacement controller targets1250 pairs using 09/14 (15), 11 (26) and
home08 (26), starting with same-schedule resumptions of200/75/25 respectively.
All paths remain lease-local on leased nodes. `launch-recovery.json` supersedes
the original controller's stale unstarted list. Semantic resume requires the
same cases, simulation options and checkpoint SHA, while allowing task-owned
path migration. Frozen data/registrations remain untouched.

At00:08Z, SSH to11 returned "No route to host". Its recovery job had been
admitted and had26 paused workers with zero completed games at the last
reachable sample. No duplicate job was launched while its status is unknown.

At the coordinator's actual00:10Z update,11 was declared down and rerunning
lost shards explicitly authorized. It is no longer targeted. The new adaptive
controller adopts the still-running09/14/home08 shards without duplicating them,
reruns the zero-completion11 block on13, and uses the newly specified caps:
13/15=10,09/14=15,16=26 (30 whole-job processes),08=12 after its current shard
drains. All three new leased admissions passed, including16, whose earlier nice
refusal had been accepted. `resource-policy.json` is read before each new launch
so later cap/closure updates can apply without another controller replacement.
Old controllers were stopped without signalling their remaining remote jobs.
`launch-adaptive.json` and `launch-recovery-r2.json` retain the lineage.

At00:24Z the wrapper's declared12GB PSS stop on16 was accepted (sampled
peak13.09GB). Its main had exited while supervised workers remained; only
verified descendants of that labelled supervisor were resumed/terminated.
103 completed games were preserved. The same25-seed shard resumed on16 with
16 workers, and future16 pools use16. Consumed child CPU and the wrapper stop
receipt are retained. Future shards were reduced to5 paired seeds to support
quicker drains under smaller pools; ongoing25-seed shards were adopted without
duplication. `fine_launch.py` / `launch-fine.json` are current. New labels include
the hostname to keep retry receipts distinct. `resource-policy.json` applies
before each new launch. The empty, stopped p1000 attempt was archived lease-local
before the same seed range could be assigned in5-seed shards.

00:46Z coordinator throughput-policy amendment: shared throughput_guard.py implemented and coordinated with A/B owner. Active pause-clock JSON is atomic; strict >5% interval-rate comparator, idle/missing/stale exemption, no utilization trigger; SCHED_IDLE and periodically refreshed GPU-thread/feeder core + SMT exclusions. Nine current/new invariants passed on08, bringing relevant suite to19 with previously passed loss-review checks. New delay decisions record active wall/raw wall/CPU; legacy wall kept separately. Fixed-work arms have no search deadline. A/B owner handles its own opt-in CPU deadline producer/consumer changes. Staged to all available lease hosts/home08. All old shards drained, final14p400200terminal. 08p0515 ended40terminal, processcount0 confirmed00:49Z, policy0 held for A/B owner’s00:51–01:21Z coexistence measurement; no reduction duringbaseline. Leasev4 job logs lack intervalfps/baselines: metric-unknown exemption disclosed, idle scheduling/affinity active, no fabricated baseline or GPU>=80claim.

00:53Z complete relevant suite executed through wrapperv2 on16:21passed in2.34s, labelcpu-delay-fixes-throughput-tests-r5. Exactcount supersedes earlier19estimate.

00:58–00:59Z16 idle-sim baseline:40 fresh unique T11 training interval steps over38.09s; median of10-step medians12147.3988rows/s. Explicit job PID4092118 and intervalfield configured,10-step median comparator threshold95%. No cumulative metric. Baseline receipt retained. Resumed16pool26/whole-job30/declared18GB PSS under authoritative wrapper. Controller handoff preserves running shards and queued offsets (launch-fine-r4.json → launch-throughput-v5.json). A launch-script label replacement was corrected before adoption completed; no duplicate sim launched. Full relevant suite22passed under wrapper. Other leasev4 logs have no intervalfps/measuredbaseline, missing-metric exemption remains explicit. Home08 stays0 through A/B coexistence. Background reduced-shard rsync transfers disclosed to A/B owner; no reduction/sim activity on08 during measurement.

## Matched-cadence control amendment, before outcome inspection

The code audit found legacy S6 opponent rollout cadence 3 versus enabled cadence 10. Add R0/R27 controls: run the existing S0/S27 enabled native path with `--opponent-delay 0 --opponent-interval 10`, capacity 4 (nonbinding at lag 0). Use the same 1,250 paired seeds in a separate lag-only directory. No implementation, checkpoint, budget, original arm or stopping schedule changes. This isolates lag under the same rollout implementation/cadence; the original U contrasts remain legacy-protocol comparisons. No outcomes were inspected before this method-based addition. All fleet caps and deadlines continue to apply.

Control config frozen for this exploration addition at actual `date -u` **2026-10-09T02:02:09Z**, before any outcome reduction/inspection. SHA256 `9e0cf7befc10bd99f145148b2e72ff68997beed1c6de00ff21d67efc3fac44b6`; [config](lag-controls-config.json), [addition receipt](receipts/lag-controls-addition.json). Coordinator explicitly approved both controls. Original and cadence-matched contrasts will be reported side by side. No new starts after 04:15Z; exit by 04:30Z; incomplete controls will be labeled partial without extending.

Before outcome inspection, include the supplemental paired N4−N2 comparison to assess whether capacity 4 adds value beyond 2. This uses the same bootstrap weights and existing games; no new arm or outcome-dependent change.

At 2026-10-09T02:20:30Z, accepted new admissions refused on09 p1205 and15 p1200 because an existing Clasher process was below the nice minimum. Both lanes retired, their offsets requeued elsewhere; live policy sets09/15=0 also for controls. No owner process modified, no admission retry. Remaining14=15,13=10,08=12;16=0 after PSS refusal;11=0 down.

At actual02:24:10Z, read-only wrapper-classifier checks on09/15 found no same-UID Clasher process below nice10 (including launchers). Coordinator conditionally authorized re-admission after tempo-horizon exec-nice fix. Restored09=15,15=10 for controls only; original lanes remain retired. Safely replaced only the waiting control controller, before any control job launched, to add the same check before every leased control admission. A failed check waits without attempting admission. Receipt: nice-readmission-09-15.json. No16 retry, no11.

At 2026-10-09T02:35:43Z, original controller exited safely with zero queued/unknown jobs. Filename coverage on08 is exactly10,000 game files/1,250 indices per original arm. Controls started only after full original drain. A per-host handoff optimization was considered but not applied because controls had already started safely; the running r2 controller and its source snapshot were preserved. No control processes interrupted or duplicate launches. No outcomes inspected.

Coordinator early lease drain effective now: allleased caps set0 atomically; running shards drain only. Remaining controls routehome08≤12;03/01 additionally authorized if needed with their caps and GPU protection. No newleased shards; hardexit04:30 remains.

At actual 2026-10-09T03:04:53Z, named09/p1050 and14/p0925 reservations were verified absent after successful natural completion (03:01:01Z/03:00:11Z). Only14/p1100 remained; no newleased admission since alllease caps0 at03:00:44Z. Remaining offsets are queued sequentially on08≤12; no03/01 staging is needed for the short remainder. Exit receipts and registry checks retained.

All own leased work drained naturally: last14/p1100 pass/0 at03:06:04Z. Fresh registry and NUL-delimited module process checks at03:06:50Z confirm zero own reservations and sim workers on09/13/14/15/16. Named09/p1050 and14/p0925 both absent, before03:20 deadline. Receipt: receipts/early-leases-clear.json. One earlier substring process probe counted itself; corrected module-token checks are retained. No raw kills, wrapper stop or accounting writes were necessary.

At actual 2026-10-09T03:14:40.434747+00:00, all50 control shards completed exit0 with queue/failed/unknown empty;2500 control files and last receipt present on08, zero own delay_simulate processes. Original10000 +controls2500 terminal files complete. All sim-launch caps now0. Beginning strict paired reduction and final24checks on one idle guarded08 CPU child, before any study outcome inspection. No heavy work on05.

Final reduction completed exit0: exactly12500 terminal games,1250original and control pairs/arm,5000 paired bootstrap draws; no incomplete original/control shards. The initial08 reduction ran21 checks because earlier test copies had not been synchronized; runtime source hashes matched05/08. Synchronized current tests, then24passed in1.09s (receipts/final-tests-r2.log). Observed CPU144.7608hours is a lower bound. Plot generated with task-localMatplotlib3.7.5; project venv unchanged. Outcome interpretation and prospective amendments written; no registration edits or commits. At03:19:49Z own08 sim/reducer processes0; allleased registries/workers previously0. Checkpoint remains0444.
