# Public SRP progress

2026-10-04: Read project guidance, OQ protocol/results, native Stage 3 and canonical
data reports, DAgger diagnosis, planner/observation/native import source. Wrote
DESIGN.md before implementation. Existing Git HEAD 95feeb0e525ee1665360df6e28116b01c3436ecf;
workspace has extensive unrelated changes. No existing files changed. Disk 20 GiB
available. No task workers started. Public-v4 also masks combat clocks and shield
state; the design reconstructs these rather than sanitizing a privileged clone.

Implementation step: added public_planner.py with a no-BattleState planner API,
exact finite deck/order posterior, public elixir/refill tracker, public-board
reconstruction, shared candidates across K, and recurrent policy top-eight variant.
Copied only OQ setup/statistics into support.py/statistics.py. Initial constructor
and one native decision passed. Added partial-trajectory checks and K benchmarks;
no evaluation games played. The 19-deck prior has 766,080 initial order states.

Checks step: fixed test-only seat ordering, policy adapter critic placeholders, and
public body/projectile aliases before evaluation. Partial trajectories pass 800
elixir/refill/exact-cycle checks; eight paired hidden mutations preserve full
candidate scores/actions, and original live snapshots remain unchanged. First cost
pass: K=1/4/8 CPU 0.0363/0.1004/0.1859 s for public random candidates and
0.0324/0.0749/0.1308 s for policy candidates. K=8 random wall max 0.2565 s.
Choose K=4 with margin, subject to final check. Added explicit forbidden-read guards
and faster posterior sampling. No evaluation started. Check runs 57431/57989/60906/
61424/62976 exited; failed early development logs retained. Added run.py/analyze.py.

Final pre-evaluation checks: check-complete.log PASS, eight hidden-mutation and
eight forbidden-read-denial cases across both seats/variants; 800 resource/cycle
checks; live-state purity. Benchmark includes measured public sensor extraction,
public root conversion, belief conditioning, search and policy inference. K=1/4/8
core-s: srp-pub 0.03579/0.09599/0.17748; srp-pub-pol
0.03219/0.07068/0.12178. K=4 max wall 0.13603/0.09703 s. Native/Python regressions:
54 tests plus 20 subtests PASS, no engine edits. Sampled public-legal placements
were accepted in reconstructed roots. All development/check PIDs exited.

Evaluation frozen before first game: PREREG.md, config.toml, manifest.json,
manifest SHA256 db70970b21d3e31de41df39d6faf3088018119f7256902bd72f5574a49a9196f.
896 unique specs validated. Three workers launched with detach.sh, nice 10 and
single-thread CPU libraries. PIDs recorded in subsequent entry. No outcome tuning.

Active evaluation PIDs: 68370, 68376, 68381, worker indexes 0/1/2. Initial completed games have valid terminal receipts; no exceptions observed. Swap 2.38 GiB, task directory 1.1 MiB.

Technical review found a public-consistency defect: damaged shielded bodies were
reconstructed with full spawn shields. Visible HP damage implies shield depletion
for P16. STOP requested between games for task-owned workers only. Early evaluation
will be preserved as invalidated development evidence, never pooled into the fixed
run. Amendment will fix only this deterministic public implication, then restart
all planned games without changing seeds, candidates, K, or pass bars.

The first workers had already exited on an unsupported public identity,
FreezeIceGolemite/AreaEffect, before STOP was written. All three logs retain the
exception. Preserved all 14 completed games, original source, manifest, design and
preregistration under invalidated-v1/. Fixed that static public buff alias and the
damaged-body shield rule. No strategy, search budget or statistical rule changed.
The revised run starts every game from scratch, with this contamination disclosed.

Amendment 1 frozen; revised manifest 19006230083f494391df304f7d420140a10c07065452eeaa6815a2146a950b1d. Fresh template/policy/timeline checks all pass: 1600 roots, 16 policy cases, 6002 ticks. All prior worker/check PIDs exited. Starting revised 896-game run.

Revised evaluation active PIDs: 74826, 74832, 74837, workers 0/1/2 respectively.
All are task-owned, detached, nice 10, single-threaded. No other processes touched.

2026-10-04 08:24Z: revised run 100/896 complete. No exceptions, rejected actions,
or measured wall/CPU decisions over 250 ms; current wall max 0.22068 s.
All 320 privileged comparison records were hashed in results/reference-manifest.json.

2026-10-04 08:34Z: 212/896 revised games complete. Zero exceptions, rejected
actions, wall overruns and CPU overruns; maximum decision wall 0.22366 s.

2026-10-04T08:35:15.701342+00:00: Coordinator amended public-information rule. STOP requested between games for owned workers 74826/74832/74837; 229 revised games currently complete. Must expose derived hand/cycle certainty, add full-game truth audits, freeze amended preregistration, and restart every evaluation game. Existing exact elixir/cycle posterior will be extracted into a dedicated module.

Coordinator amendment implementation: extracted derived_public_state.py, added
explicit posterior certainty and deterministic use of resolved hand/queue, retained
exact elixir with zero estimate fallbacks in P16. Added five unit tests (PASS) and
audit_derived.py, replaying 24 complete prior recorded games across both players,
seats and all three styles. Audit PIDs 791/797/806, at most three heavy processes.
Updated privacy checks to mutate only unrevealed deck identities and true RNG;
denied-read guards still forbid opponent resources/hand/cycle. Evaluation receipts
will count determined-hand and determined-cycle decisions for the complete run.

Coordinator amendment frozen before restart. Revision-3 manifest 9d83e63c46f4ff9a5729efc26d24f8b2f83746ec8fbf08225dacd5b664b38a2c. Six unit tests PASS; 24 full recorded-game replays PASS, 0/23058 elixir errors, 0/18516 determined-hand errors, 0/21913 queue/next errors. Hand determined 80.3018%, cycle 95.0343%. No estimate fallback. Revised privacy and benchmarks PASS. All audit/check PIDs exited.

Revision-3 evaluation PIDs: 4760, 4766, 4771 (worker indexes 0/1/2), all launched
through detach.sh at nice 10 with single-thread CPU libraries. Log prefix eval-v3-.
Full target remains 896 games; superseded results are excluded from analysis.

Revision-3 early timing gate failed: srp-pub-pol balanced g0 wall 0.32196 s / CPU
0.26365 s; pressure g0 wall 0.29527 s / CPU 0.24707 s. No state-tracking errors.
STOP requested between games for 4760/4766/4771. Profile exact-state bookkeeping
before continuing; retain these receipts and disclose any performance amendment.

Profile corrected the preliminary attribution: the spike was tick-0 PyTorch lazy
attention-validation imports, not posterior bookkeeping. Recorded profile in
logs/profile-derived.log. Added one synthetic public-policy warmup at Resources
construction; discard its recurrent state. Preserve all 18 revision-3 games and
source under cold-start-v3/. Revision-4 will explicitly exclude this one-time
model setup from per-decision timing, as checkpoint loading already is excluded.

Amendment 3 frozen. Revision-4 manifest 34c37729937ba2646d677dd99fb6e8f892afe1332ad88062b2c0655eb0145054. Warmup replay 100/100 identical actions, first decision 0.07878 s and max 0.08376 s; Resources setup 0.9463 wall-s. Privacy/bench checks PASS. Restarting all 896 games.

Revision-4 active PIDs: 10028, 10034, 10039, workers 0/1/2. These are the only
active heavy processes started for this task. Log prefix eval-v4-. Earlier runs
are preserved and excluded; current target is still 896 complete games.

2026-10-04 08:57Z: revision 4 reached 100/896 complete games. No errors,
rejected actions, wall or CPU deadline overruns. Maximum decision wall 0.22793 s.

2026-10-04 09:07Z: revision 4 reached 212/896 games. No exceptions, rejected
actions, wall or CPU overruns; largest decision wall remains 0.22793 s.

2026-10-04 09:13Z: revision 4 reached 302/896 games. No errors, rejected
actions or measured deadline overruns. Maximum decision wall remains 0.22793 s.

2026-10-04 09:22Z: revision 4 reached 406/896 games. Zero errors, rejected
actions and deadline overruns. Maximum decision wall now 0.23174 s.

2026-10-04 09:31Z: revision 4 reached 510/896 games; group counts {'holdout': 502, 'hog26': 8}. Zero errors, rejected actions or deadline overruns. Maximum decision wall 0.23843 s.

2026-10-04 09:33Z: K=4 exceeded the strict decision budget: max wall 0.271016 s and a CPU overrun. Stop requested for 10028/10034/10039 between games. No strength analysis has been run. Select benchmarked K=1 solely on the latency gate and restart all evaluation games under an explicit amendment; preserve this entire K=4 run.

Amendment 4 selects K=1 solely after K=4 failed the strict full-game latency gate. Preserved 542 K=4 games in over-budget-k4, 512 primary plus 30 Hog. No strength analysis performed. K=1 privacy tests PASS; max benchmark wall 0.05658/0.05259 s. Revision-5 manifest 03411237449095e8111a3d87e1fb2ac5362ec7f6497114dd50e1ebb337251904. Restarting all 896 games.

Revision-5 K=1 active PIDs: 56427, 56433, 56438 (workers 0/1/2). All task-owned,
detached, nice 10, single-threaded. Final evaluation log prefix eval-v5-.

2026-10-04 09:42Z: final K=1 run reached 101/896 games. Zero errors, rejected
actions and deadline overruns. Largest decision wall 0.09033 s.

2026-10-04 09:48Z: final K=1 run reached 209/896 games. No errors, rejected
actions or deadline overruns. Maximum decision wall remains 0.09033 s.

2026-10-04 09:52Z: K=1 reached 302/896 games. Zero exceptions, rejected actions
and wall/CPU deadline overruns; maximum decision wall remains 0.09033 s.

2026-10-04 09:58Z: final K=1 run reached 415/896 games. Zero errors, rejected
actions or wall/CPU overruns. Maximum decision wall remains 0.09033 s.

2026-10-04 10:03Z: K=1 reached 503/896 games; groups {'holdout': 498, 'hog26': 5}. No errors, rejected actions or deadline overruns; maximum wall 0.10275 s.

2026-10-04 10:10Z: K=1 reached 613/896 games; groups {'holdout': 512, 'hog26': 101}. Zero errors, rejected actions and deadline overruns; max wall 0.10275 s.

2026-10-04 10:17Z: final K=1 run reached 709/896 games; head-to-head evaluation
is underway. No errors, rejected actions or deadline overruns. Max wall 0.10275 s.

2026-10-04 10:23Z: K=1 reached 796/896 games, with the last 100 head-to-head
games pending. Zero errors, rejected actions and deadline overruns; max wall 0.11205 s.

Primary analysis complete: srp-pub K=1 PASS, 207/256 score 0.808594 CI
[0.753906,0.863281], defense 0.797619 [0.690476,0.892857]. srp-pub-pol K=1
PASS, 204/256 score 0.796875 [0.734375,0.855469], defense 0.785714
[0.666667,0.892857]. Hog secondary complete: 0.40625 and 0.515625. Head-to-head
still incomplete; preliminary summary will be regenerated at full completion.
Integrity checks: 411 frozen dependencies verified, 397 non-task dependencies
unchanged from initial freeze, all 320 privileged reference records unchanged.

## Complete

2026-10-04 10:34Z: all 896 final K=1 games complete (448 per player: 256 primary,
64 Hog26, 128 policy head-to-head). All workers 56427/56433/56438 exited normally
with completion receipts. No task processes remain. No rejected actions, out-of-mask
actions, wall or CPU deadline overruns over 815,085 decisions. Maximum wall:
srp-pub 0.112048 s; srp-pub-pol 0.096829 s. Mean core-s/search decision:
0.026867 / 0.020779. Mean core-s across all decisions: 0.003805 / 0.007004.

Final frozen analysis is results/summary.json, full verification and per-record
hashes in results/final-verification.json. Both players PASS primary and defense.
Head-to-head versus s2902 1M: pub 75/128, 0.585938 [0.484375,0.679688]; pol
81/128, 0.632813 [0.546875,0.718750]. Recommend prewarmed srp-pub-pol K=1;
Hog26 remains a weakness (0.515625, CI [0.390625,0.640625]). No significant direct
pub-versus-pol superiority claim is made. Paired gaps vs privileged are in summary.

Hand membership determined in 327627/409790 pub decisions (79.94997%) and
321384/405295 pol decisions (79.29632%). Cycle determined 93.4264% / 93.4759%.
Truth audit remains zero errors over 24 complete recorded-game replays and 23,058
observed decisions; no elixir estimate fallback was used. Public-private UI slot
ordering distinction is documented in DESIGN.md and derived_public_state.py.

All 411 frozen dependencies and all 320 reference records verified; 397 non-task
dependencies unchanged from the initial pre-evaluation freeze. No engine, Rust,
gamedata, pilot, C56, frozen runtime, oracle-qualification or srp-dagger files edited.
No Git mutations. Total directory about 6.5 MB, below 1 GiB. REPORT.txt is the
requested <=250-word plain-text final report. All four amendments and prior runs
are retained, with final chosen-K results isolated in games/.
