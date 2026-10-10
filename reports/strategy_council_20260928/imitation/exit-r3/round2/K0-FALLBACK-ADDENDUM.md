# R3 deployment fallback evaluation amendment

Coordinator decision dated 2026-10-10 06:50Z, recorded before any R3 descriptive
or round-2 Stage-2 game. This supersedes the S-default game protocol in the
original evaluation and round2/PLAN.md. The immutable training freeze 7e939c06,
fits, checkpoints, Stage-1 gates, calibration, scorer and seed banks are unchanged.
The original R3a/b experiment is complete; both arms remain killed.

Use the frozen r1(b) runner `imitation/exit_r1/screen.py` (SHA
17d1b4086585840f5073285c9345355b4187c8342963963360213c3a9cff176e), with
the E1 coarse-first W-screen8 deadline kernel and qualified reporting native
f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8.
The historical execution freeze is
ff4ae6ef20cda181f09ff3dcadaedb0a4435bf92c0ce388e3adc466c75f813fa.
Retain its 1-core, 200 ms end-to-end deadline, 8 ms return reserve, horizon160,
search cadence10 ticks, fallback cadence5 ticks, d27/capacity1, abilities off,
same five archetype decks, deck/index/seat schedule, independent fair roots,
balanced coarse scan then completed three-style scores, W wait bias, and
same-packet fallback if no root completes. Partial or late roots never count.

As in r1(b), the student supplies the cutoff fallback and top8 legal play
proposals; the opposing W player uses released v1. The control, labelled K0,
is the r1(b) common init-W reference: v1 fallback/proposer on both sides, with
the same coarse-first deadline W kernel. K0 here is not the X study's anytime
ordering. R3 uses its frozen calibrated gate and deterministic ranked play
choice; v1 retains the original stochastic T=1 gate(c) sampler. Both fallback
and proposer inference are inside the unchanged full-decision timer.

The R3a descriptive lane uses its final2500 EMA and existing calibration,
600 fresh paired seeds `4503602507370496+[0,600)`, excluded qualification
`4503602517370496+[0,32)` (initial indices0/1). It is ALWAYS NEVER-ADOPTABLE,
including if its paired CI favors the student. Preserve the original Stage-1
kill receipts; never relabel R3a a survivor or use these outcomes for selection.

Round-2 Stage 2 includes only c/d/e arms that pass the unchanged complete
Stage 1: recall>=.6375, binary agreement>=allWAIT+.10, positive W regret<=.010.
Use `4503602407370496+[0,600)` paired reporting and excluded qualification
`4503602417370496+[0,8)` (initial indices0/1). Regret remains the common-root
`4503602427370496+[0,65536)` bank. All helpers remain
0/13/100000..100003/271828..271829; the pre-fit seed audit remains applicable.

On each seed, run K0 and every included student consecutively on the SAME
physical core, rotating the complete arm order by index. No pre-run controls,
no killed round-2 arms, no partial-block reuse. All interrupted/replayed work
is retained and charged. Each reporting lane requires600 complete paired
terminal blocks before reduction. Draw loss is0, as in r1(b). Report student
minus K0 loss and paired percentile95% CI using5000 seed-bootstrap resamples,
R3's existing bootstrap seed80991013; kill if upper CI>=0. Exploration lane,
no multiplicity adjustment. Descriptive R3a never becomes adoption eligible.

Games run only on home127x01 physical cores0–39, manager39, nice10/SCHED_OTHER,
Torch/BLAS/native threads1, own setsid-f wrappers, home MemAvailable>=24GiB,
owned STOP and Oct11 05:15Z stop. X explicit release06:47:05Z is a prerequisite:
independently verify the SHA-bound release, all recorded PGIDs absent, locks
free, no X/K-v2/K2/G runtime, and retain G STOP/STOP-01. Fresh admission must
precede staging or scientific work. Original04 was returned and is not reused.

An implementation freeze must bind this addendum, exact inherited source and
native hashes, student/checkpoint/calibration hashes, adapter, interleaving,
admission, qualifications, reducers and seed audit. Commit, secret-scan and
push that freeze and verify its actual committed bytes before any game.
Record PID/PGID journals, every whole-tree CPU meter, case/command hashes,
deadline hits/fallback use/completed roots/overruns/proposer latency, final
vacancy and once-only SHA-deduplicated costs. No native, array or model work
on command-center05.

K2 explicitly released03 at07:00:38Z, with its PROGRESS notification07:01:18Z.
The independent R3 audit07:06:29Z confirms all seven released PGIDs absent
and no K2/K-v2/X/G runtime. Regret replay may use admitted03 physical0–59,
manager59 and eight scoring workers0–7, nice10/SCHED_OTHER, home24GiB floor,
owned STOP/lease deadline and durable PID/PGID journal. Its1412 frozen scorer,
native and heldout pins passed base staging07:06:52Z. This slot runs only
64 common command-exact replay games after all final C/D/E GPU proposals;
both paired timing protocols remain on01. Regret uses the original frozen
scorer native06d8e539..., distinct from the r1(b) deadline reporting native.
