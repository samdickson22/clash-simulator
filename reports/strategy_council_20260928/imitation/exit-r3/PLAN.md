# R3 root-only student with optional advantage head

Authority: coordinator0523ae6f, user R3 brief and noise-ceiling §4 at136a1285.
Exploration lane; no multiplicity adjustment or adoption claim. Freeze plan,
seed audit, trainer/head/tests and operational recipe; commit and push before fit.

R3a on127x09 and R3b on127x16 initialize released v1 main-2026100802
step22552 EMA at width192 (SHAd77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed).
Both train2500 optimizer steps×8192=20,480,000 root rows with replacement,
trainseed2026101013 and FINAL EMA only. No intermediate checkpoint selection.
R1 corpus1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b
has6,009,681 eligible roots; exclude continuation wait kinds1/2, pending3,
unsupervised rows and rows without candidate scores. Require teacher_root true
and wait_kind0. Uniform sampling over concatenated eligible root indices.

G decision frozen before fit: INCLUDE all five packed shards from paused
04 manifest4e8faf7edc7164a6676f76e4f7a7d6ea237d4eba88d19252a0921c40cf409ef8.
Schema, all355 shard-file SHAs, five shard manifests and three host manifest SHAs
passed verification;212,542 extra roots. Union6,222,223 roots (~3.29 sampled epochs).
Both own09/16 copies were SHA-verified before freeze; trainer verifies again.
Never resume G or remove coordinator stops. Held-out/evaluation games never train.

Both: listwise softmax over VALID completed candidates T=.003, playweight1,
valueweight0. Existing R2 gate/card/tile loss and conditional full8192 denominators.
R3b additionally learns per-candidate score minus completed ordinary WAIT score,
unbounded advantage outputs, Huberδ=.01, auxiliary weight1. Average regression
loss over valid scored candidates using whole-effective-batch weighted denominator;
padded/unscored candidates contribute zero. The head shares encoded hand/tile
features and adds a small tile MLP plus two WAIT logits; no second encoder pass.
R3a head-off exactly matches R2 T=.003 loss, gradients, AdamW update and outputs.
R3b ranks all legal play proposals by advantage, descending with action-ID ties;
R3a ranks by conditional card+tile logprob. Both top8 are offered regardless of
timing gate; W completes WAIT scores and decides using its frozen scoring rule.

AdamW lr3e-4, decay.05, warmup2000, existing qualified cosine(total2500),
clip1, EMA.999, bf16 autocast CUDA; teacher micro≤128 (human flag3584 irrelevant
for teacher-only batches). Scientific Torch1; loader6/prefetch4/no random mmap
advice; exact per-step index vectors checked. Parent118/119/126, workers120–125.
Checkpoints every250; exact optimizer/scheduler/EMA/RNG continuation only.

Gate calibration after final fit: use all eligible roots of the frozen r1
held-out64 slice (SHA0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f).
Choose a scalar threshold on P(gate=play), requiring a legal play, that yields
nearest possible34.6% deterministic root play prevalence (midpoint between sorted
adjacent probabilities; choose smaller threshold on exact distance ties).
No teacher action labels, recall, regret or game outcomes choose this threshold.
Same held-out slice is reused for exploratory diagnostics; disclose calibration
reuse. Deterministic default is WAIT below threshold or without legal plays,
otherwise highest-ranked legal play; keep frozen S-default timing/scoring/default
behavior and include full inference inside its wall timer. GPU float32/TF32off
for offline inference; CPUfloat32 in deployment.

Stage1 on ALL8088 eligible roots in the r1 heldout64 games:
- calibrated deterministic play recall≥.75×.85=.6375;
- calibrated binary play/WAIT agreement≥all-WAIT agreement+.10
  (teacher WAIT5290/8088, threshold.754055391; exact value from slice);
- mean positive W-score regret≤.010 score units. For each replayed root, rebuild
  public observation and fresh frozen W belief/root with fixed independent RNG;
  fully score the recorded W candidates UNION student's top8 on the SAME root.
  Comparator is the best complete score among recorded W candidates; student
  score is best complete of its top8 PLUS always completed WAIT/WAIT10.
  Regret=max(0,comparator−student); also report signed regret, play-root-only
  regret, percentiles and exact-tile top8 recall descriptively. Including WAIT
  matches deployment's veto; no valid play yields WAIT-only proposal set.
  Every root must complete; missing/SHA-invalid diagnostics cannot pass.
Whole-game5000-resample percentile95% intervals, seed80991013. Gates use point
estimates. A timing failure kills Stage2 eligibility but still complete/report
regret once home CPU admitted; no old exact-tile gate and no standalone h2h gate.

Stage2 survivors: S-default1-core600 fresh paired seeds vs C-v1, plus K0 anchor,
using X's frozen d0264ec9 S-default adapter/runner. R3 adds only own model loading
and calibrated proposal/default inference hook. Full-package contrast; no claim
to isolate gate/head/default effects. Seeds4503601907370496+[0,600), smoke
4503601917370496+[0,8) excluded; regret helper RNG4503601927370496+[0,65536).
Own interval/formula audit expands offsets0/13/100000..100003/271828..271829,
checks all K/K-v2/K2/X/X-descriptive/G reservations and inherits SHA-pinned prior
exact inventories. X descriptive20/201 coordinator04:05Z, K2report23/smoke231.

No control pre-run. Each seed's [C-v1, eligibleR3a, eligibleR3b, K0] runs
back-to-back on SAME host/physicalcore/nice10/SCHED_OTHER/Torch1 class, with order
rotated by index modulo armcount. Entire incomplete block archived/replayed;
all attempts metered. Symmetricd27/capacity1/abilitiesoff, frozen5 train-archetype
decks/25matchups, own=i%5/other=floor(i/5)%5/seat=i%2, opponent releasedv1.
Kill if upper paired95%CI(lossR3−lossC-v1)≥0, using5000 shared bootstrap
resamples seed80991013. Report R3−K0 descriptively. No DAgger or adoption here.

Stage2 and scorer replay: home CPU only, 03physical0–59 after explicit K2 release
in reports/explore/k2/PROGRESS*.md AND zero K2 PGIDs;01physical0–39 fallback
after X descriptive explicit release/no study PGIDs. No G anywhere on admitted
host. Check physicalaffinity/no SMT duplication, homeMemAvailable≥24GiB and
resource admission continuously. No games or frozen-scorer CPU sims on leased
GPU hosts. Stage1 GPU diagnostic/calibration may run there after cleanfit exit.

Own /mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1; owned setsid-f wrapper,
PID/PGID/log receipts, FIT.STOP and later owned eval stops. ≤16 totalClasher
processes, nice≥10, aggregatePSSguard46GB/hard48GB, GPUfree≥8GiB. Read live
lease/reclaim before launch/every10s; checkpoint stop at Oct11 05:15Z, guarantee
vacate before Oct11 05:30Z. Never touch roader paths/mirrors, tailscale or cron;
never pkill-f. All caches/tmp under own/mpac tree;05command center only.

RESULTS.md includes every arm/gate/skip/case count/inputSHA, finalEMA, throughput,
GPU-wall and whole-treeCPU hours, failures/replays/resource censoring. PROGRESS-R3
carries exact launch/resume/admission commands and durable state. Coordinator
milestones<150words. Git commits use ONLY explicit owned file paths (shared
staging may contain others' files); secret-scan before EVERY push.
