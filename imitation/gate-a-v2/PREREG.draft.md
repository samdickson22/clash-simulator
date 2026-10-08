# V2 gate (a) registration

This draft becomes binding only when PREREG.md and freeze.json are published
before either v2 training run or any v2 held-out scoring. Authority: DESIGN
sections 2.8, 3, 4.3, 4.4, 5.1 and T11. No extractor, role assignment, held-out
specification, qualified T4 file or T5 loader is changed. Scientific changes
after freezing are prohibited; any output-identical technical repair requires
a separately hashed amendment before use, preserving the original artifacts.

## Corpus and immutable inputs

C56 union the 333,934 new S122 perspectives, using s122_roles_v2.json. All
82,231 v1 assignments are unchanged. Excluded-leak perspectives are dropped.
The 2,361 frozen C56 entries marked actor-ineligible by T9 are also omitted
because their opponent has Three Musketeers; this changes v2 eligibility,
not their frozen roles. Report raw role counts and excluded counts separately.
Both-side Three Musketeers exclusion and Battle Healer/Mirror flags follow
T9/T10. The actor scope is 121 cards. No additional card exclusion or repair.

Store rows preserve every original array and aligned sidecar value, except
for the explicitly selected S122 train waits and the documented packed mask
indices/entity offsets. Source identities remain available. C56 train retains
all rows; S122 train retains every non-wait and a fixed 50% hash-selected wait
sample. The selection is SplitMix64 of the perspective-local original row
ordinal XOR the little-endian first eight SHA256 bytes of
`t11-s122-store-waits-v1:match|side`, keeping high bit zero. Its wait weights
include inverse probability x2. Dev/eval/eval_ood retain every eligible row.
The store release requires a deterministic random 1% perspective round trip
exact in dtype, shape, bytes and decoded masks, complete eligible-role count
reconciliation, zero train/held-out match leakage, unchanged v1 roles, all
input hashes and dev-only frequency baseline receipts.

Frequency counts are fitted from every supervised row of eligible v2 train
perspectives in the original source, BEFORE wait thinning, with natural unit
weight. The phase/elixir gate table, card counts, add-one per-card tile
histograms, legality masking and zero-mass fallback match T3/T5 exactly.
No dev or held-out row contributes to fitting. Only dev is scored before the
held-out release. V1 baseline summary numbers were already visible in the
required T3 progress document; they do not change any v2 rule or selection.

## Runs and selection

Exactly two fresh v2-main seeds: **2026100821** and **2026100822**. Initial
hosts 127x16 and 127x18, respectively. One run per A6000. No extra fitted
trial, ablation, architecture search or throughput fitting trial.

Use qualified T4 code SHA
`301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`,
including its full 128-entity contract, 192-token bucket and prescribed
tile-width64 latency fallback. Import T5 resource-r2 BoundedBatchedStore
unchanged: one loader worker and MADV_DONTNEED after independent tensor
copies. The v2 adapter changes only mixed-corpus sampling, guards and lease
deadline handling around the unchanged T4 optimization loop.

Each epoch includes all supervised plays/abilities, a fresh 25% of C56 waits,
and a fresh 50% of retained S122 waits. T4 row IDs remain
`source_unit << 32 | source_row` with globally unique unit numbers. Apply its
hash of row ID XOR seed XOR (epoch+1)*0x9e3779b9 with thresholds 2^30/2^31
on the high 32 bits. Keep ascending selected indices before the unchanged
PCG64 SeedSequence([seed,epoch]) shuffle and within-effective-batch stable
entity-count bucketing. Store S122 wait x2 times adapter x.5 times T4 x4
equals total x4; C56 wait x1 times T4 x4 also equals total x4. Quality factors
and the minimum train-only inverse-square-root proxy/family caps are unchanged
in definition and computed across the eligible union. No wait bias tuning.

AdamW lr3e-4, weight decay .05, cosine schedule and 2,000-step warmup,
gradient clip1, effective batch8,192, microbatch7,168, eager CUDA bf16,
EMA .999. At most **six epochs**, early stopping patience three on pooled
v2 dev natural-row uncalibrated EMA joint NLL. T4 derives scheduler length
from seed-specific epoch-zero sampled row count times six. Interrupted runs
retain this schedule, optimizer, model/EMA, RNG and exact sampler cursor.

Select each seed's checkpoint by lowest pooled v2 dev joint NLL; ties choose
earliest step. Choose the primary seed using the same dev statistic; equal
statistics choose the smaller seed. Both seeds receive all gate diagnostics;
the other seed cannot replace a failing primary based on held-out outcomes.
Seal selected checkpoint hashes, dev scores and run completion evidence
before held-out release. No eval/eval_ood result can influence selection.

Fit separate gate/card/tile temperatures on pooled dev only after selection,
using the unchanged T4 deterministic uniform reservoir of at most 100,000
dev rows (PCG64 seed1), head-specific eligibility, log-temperature [-4,4]
and LBFGS recipe. Seal temperatures and their input hashes before held-out
inference. Calibrated metrics are primary; uncalibrated metrics are reported
from the same forward pass. No additional calibration on C56/S122 slices.

## Held-out embargo, metrics and bars

No v2 model OR frequency eval/eval_ood scoring until both training runs have
completed, selection and calibration are sealed, and the v1 gate (a) report
has been published. Capture its exact path/hash as a release dependency.
Keep held-out files available solely for store integrity/copy verification
before that release. A training pause or a signal exit is not completion.

Score each selected seed once on eval and once on eval_ood, retaining whole
perspectives and saving identities and sufficient statistics. Split reports
by source corpus: eligible frozen **C56**, and **new S122**. Apply the same
A1–A4 definitions separately to both eval cohorts; report both OOD cohorts
with identical diagnostics. Also report pooled results and OOD-minus-eval
gaps. Recomputing statistics from sealed saved predictions is not reinference.
Technical interruptions require an explicit retained failure receipt and
resumption without rescoring completed row prefixes. No result-based retry.

Metrics follow heldout_eval_spec_v1.json: play/wait NLL/Brier, card top1/top3/NLL,
tile NLL/median error, joint NLL, ability NLL and hazard calibration. Report
top8 joint (card,tile) recall exact and within one Euclidean tile, per-card
and frozen-gamedata unlockArena slices, gate/card ECE before/after calibration,
and Battle Healer/Mirror flags. Arena codes are descriptive only.

Natural weight1 for every eligible supervised row; no training quality,
balance or sampling weights in metrics. Primary timing and gate ECE use
supervised playable rows as in DESIGN; also report the JSON spec's all-row
timing metrics as distinctly named *_all. Frequency comparisons use identical
row and metric eligibility. Conditional card/tile use supervised human plays.

- **A1:** model-minus-frequency joint NLL, play/wait NLL, card NLL and tile
  NLL must each have a paired two-sided 95% CI with upper endpoint <0.
- **A2:** on each cohort's P16 slice, card NLL and tile NLL must be at most
  the upgraded P16 BC values +.05 nats. This is a point-estimate margin.
  Require exactly matching eligible perspective/row identities; old aggregate
  baselines cannot silently substitute after the v2 actor exclusions. Reuse
  qualified saved per-perspective P16 statistics only when exact identities
  and semantics match, otherwise score the unchanged qualified upgraded P16
  after the same embargo. Empty P16 slices are explicitly N/A, never zero
  or an invented passing comparison (new S122 own decks are outside C56).
- **A3:** no own card significantly worse than its per-card frequency tile
  histogram. Significantly worse means the lower endpoint of a paired
  two-sided 95% tile-NLL difference interval is >0. No multiplicity adjustment.
  Report passing/assessed/scoped counts: out of56 for C56 and121 for S122;
  absent cards are unassessed and do not count as passing.
- **A4:** calibrated binary gate ECE <=.01, with probability
  P(play-or-ability), observed act, and ten equal-width [0,1] bins on
  supervised playable rows. Also report multiclass gate ECE and ten equal-mass
  timing calibration; neither substitutes for A4.

All applicable bars are required for each eval cohort and for the combined
v2 success claim. Missing evidence is unassessed, not a pass. Empty structural
P16 slices are labeled N/A. Report all outcomes including failures. OOD bars
are diagnostic as in DESIGN, not an additional selection opportunity.

## Statistics

Exactly10,000 whole-perspective bootstrap resamples with replacement separately
within each corpus/role cohort, PCG64 seed2026100825. Sort match|side identities
lexicographically and record the ordered hash, including zero-eligible
perspectives. Draw N perspectives from N (equivalently multinomial counts).
Use identical draws for model/frequency paired comparisons and both seeds.
Means are resampled sums divided by eligible row counts. Recompute median tile
error with replicated row multiplicities. Two-sided percentile endpoints
.025/.975 use NumPy linear quantiles. Record undefined denominator resamples
and valid counts; no imputation. No independent-row bootstrap.

## Resources, checkpoints and return

Nice>=10, all borrower processes<=96 (<=16 with console user), shared-host
summed process-tree PSS<=64,000,000,000 bytes and >=8192MiB GPU free.
Use existing lease-local env.sh/run.sh and T5's verified PSS supervisor;
check live lease/refusal/reclaim/expiry and GPU/process availability before
each launch. Every borrowed path stays inside clasher-lease. Preserve the
reclaim handler and verified-PID supervision. No broad process kills.

Checkpoint every1,000 steps and each epoch; index last3/best but preserve all
files under the no-delete rule. Interrupt during training saves exact state
and exits before dev; interrupt during dev retains the complete pre-dev
checkpoint and exits promptly. Trigger planned SIGTERM at
2026-10-09T04:20:00Z to finish checkpoint AND exit before05:00Z, ahead of the
05:30Z lease expiry. Resume unfinished seeds with identical frozen recipe,
state and inputs on available home01/04/08, verifying old exit and checkpoint
hash before migration over LAN. Nothing heavy or bulk goes through05.

Store/checkpoint files remain on compute hosts; only owned small docs, code,
receipts and reports mirror to05. Record labels, verified PIDs, exact resume
commands, observed throughput, curves and resource evidence in PROGRESS-T11.
