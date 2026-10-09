# Gate (b): imitation proposals in C56 fair search — FROZEN

DESIGN §5.2 and §7; fixed1152games.

## Arms and matching

A is the Stage 5b deadline fair player: script choice, no-op, script top four,
ability and 16 sampled public-legal placements; 200 ms absolute wall deadline,
two Rust workers. B is identical except its sampled slots use imitation top eight
joint p(card) p(tile|card), deduplicated against scripts, then random fill.
Gate probabilities never enter search proposals; no-op remains explicit.
D1 is deck-free and uses timestamped accepted public events and known own order.
Sensor conversion, event updates, D1, feature building, inference, candidates,
root construction, native workers and worker joins all count inside the deadline.
Only initialization and warmup before games are excluded.

Count convention (needed to preserve the existing A implementation): A draws 16
placements BEFORE deduplicating scripts. Its actual unique addition may be less
than 16. B exactly matches that root's A post-dedup count, never adding extra
candidates. A's random draw determines the count and supplies B's random fill;
B substitutes up to eight distinct legal imitation proposals at the front of
those slots. When legal support is small, both arms exhaust the same count.
This preserves A byte-for-byte; candidate-count equality is asserted per B root.

Common CPU implementation qualification: both arms use the evaluation adapter's
`ExactFastPrior`, whose column-wise posterior updates are state/weight/resource/
derived-fact/RNG equivalent to the Stage 5 tracker. This is shared by A/B; it
changes no engine/gamedata or search scoring. Eight recorded-stream parity
checks precede its use. The original row-wise tracker exceeded 250 ms before
inference on the fleet CPUs; those plumbing failures remain in the receipts.
Confirmation freezes the final model/evaluation snapshot tree SHA256 in this
registration. 

## Schedule and fresh seeds

Primary: 320 seeded worlds × two controller swaps = 640 games. Physical decks
and seeded world remain fixed across each pair; only A/B controller seats swap.
Use Stage 5b role-held-out planning, its seven family strata and
train opponent catalog. Both deck identities must be supported by the Stage 5
train-only prior. This is role holdout, not deck-identity holdout. Family pair
counts are 46,46,46,46,46,45,45 in Stage 5b's family order.
Secondary: each of A and B plays 256 games against balanced/pressure/defense C56
scripts on identical seeds/decks/seats: 128 pairs per arm, both seats per pair.
Family pair counts 19,19,18,18,18,18,18; styles cycle in fixed order. For these
script pairs the held-out planning deck follows the candidate across seats,
matching Stage 5b continuity. Total 1,152 games.

The coordinator approved a fresh hash-committed namespace before any gate
outcome, because f35's sole archived readiness-root history has unknown master
seeds for getrandbits(32), with no surviving launch receipts. The old4356seed
audit remains history. World/helper/deck/bootstrap seeds are all shifted by the
same base>=2^40 and stay below2^48, away from the exploration lane.

<!-- BEGIN HASH-COMMITTED SEED SECTION -->
Gate(b) formulas: world_i=base+2817600001+1009*i, i=0..447;
primary i=0..319, secondary i=320..447. Derived helper seeds are world+100000,
world+100001 and world+100002. The deck schedule RNG is base+2817590001;
the PCG64 bootstrap seed is base+2817590002. Both arms retain identical worlds,
physical deck order and paired controller swaps as specified above. The newly
committed schedule has42 distinct primary own deck identities,320 primary and
128 secondary eval-role worlds,0 eval_ood worlds. No identity-holdout claim.

Commitment H (SHA256): `e730c9f1f71f4402b47a8dff2593e5b659c947fd7b0184c3cdeafa2799f49f50`.
Common additive base: `1359319908352`.
Canonical bytes SHA256: `8c7f0f401d3b3004d0df643d2aa76841aa9fd168c74516395d587bd814087594`.

Construction: take each complete UTF-8 PREREG, replace this entire section,
including both HTML delimiter lines, with `<CLASHER_GATES_BC_V1_SEEDS>`.
Normalize only the registration heading FROZEN to DRAFT and remove only the
registration-added final `Confirmation snapshot SHA256: <64 hex>` line (and
its preceding newline). Serialize the object {"b":canonical_b,"c":canonical_c}
with Python json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False).
H = SHA256(UTF8("clasher-gates-bc-v1|") || these bytes).
base = 2^40 + (int(first six H digest bytes, big-endian) mod 2^24) * 2^14.
Every original world/helper/deck/bootstrap seed gains this same base exactly;
there is no modulo truncation and no seed search or outcome-based selection.
The namespace receipt preserves both exact canonical document strings.

The full union contains4356 distinct integers:1794 for(b),2562 for(c), with no
cross-gate intersection. Minimum `1362137498353`, maximum `1362537972901`.
Canonical full seed-list SHA256 (json.dumps(sorted integers), default separators):
`c92f33839665d705e1579ae9f758c8ca621b895cefeab992f438d8d2752e58a8`.
The merged audit PASS retains26434 observed historical integers,94 raw errors
with their pinned resolutions,0 unresolved errors and0 intersections, including
all derived seeds and reviewed formula/job ranges. Its completeness means the
authorized direct scans plus disclosed off-host bounds, not inaccessible full
filesystems. The unknown f35 getrandbits(32) worlds are strictly below this
namespace; exploration>=2^48 and wide qualification>=2^44 are strictly above it.

History: old4356 seed-set SHA256
`be64ed484ec3bd52f4dd29f915482170004cb9e23ff5d228b841061f3e47809c` is retained.
The first wide commitment H
`bdc74e65675a9d55e6634f5c6ff03b12f08fedaa249bc44ff9c980aea97b8816`,
base1208393039872, and all its schedules remain in `prospective-wide-r3/`.
It was superseded before any gate outcome after documenting the coordinator's
04 mirror-loop root cause and corrected archive provenance. No gate games used
either historical namespace. Coordinator approved recomputation before freeze.

Current small artifacts under `imitation/gates-bc/receipts/prospective-wide-r3-final/`:

| Seed-dependent artifact | SHA256 |
|---|---|
| namespace.json | `b82f52925e0bdad16f8e75d7ef514396292ad1899ca44e052235d0a42ed2801b` |
| combined-seeds.json | `d37ddc8fd0c05d1f782825b81a019bb3d43e07b921fcb12ab6cc6ff5693a2b4e` |
| merged-audit.json | `44af35a20b912933ecab37ff44794632af9f92565af0ceaefc76ebcf5b1ad4e1` |
| gate-b/schedule.json | `f17291fc953cc61d18f0acb16bb08c03cce2febc1cb882d38522b9db06427102` |
| gate-b/proposed-seeds.json | `7635dd18eeda76251cbf6974e4f16e37cf7a73d3121f6ad5381fc9e561cb59b7` |
| gate-c/schedule.json | `24776955db66a1d43c82b4069e75c44ec084258cd7179793413169a12698e763` |
| gate-c/proposed-seeds.json | `5c182a036f97c7b18a335c6be1a07f5783976bf5abe3f4fa262fb2b9ce667c89` |
| checkpoint-stage-verification.json | `6a8a60881f7e1e2e4b90a74e3e53b562946316d6fa015c52f4be894a390abce9` |
<!-- END HASH-COMMITTED SEED SECTION -->

## Analysis and pass bars

Win=1, draw=0.5, loss=0. Primary score is the mean of the 320 two-game B pair
means. Two-sided 95% percentile paired-matchup bootstrap, 10,000 resamples of
whole worlds with both controller swaps retained. Report score, interval,
W/D/L, pair-mean counts and decisive fraction, per-family and role descriptions.
The fixed schedule has320 primary and128 secondary eval-role worlds, zero
eval_ood worlds, and a fixed number of distinct primary own decks recorded in the seed section. Inference is conditional on
this deck schedule and makes no deck-population or eval_ood generalization claim.
A decisive pair has mean0 or1; split pairs have mean0.5; draws can yield0.25/0.75.
Report all five counts and decisive fraction q.

All three conditions are required:
1. Primary point score >=0.53 AND bootstrap lower bound >0.50.
2. Secondary B minus A point score >=-0.03, using all 256 paired games per arm.
   Report paired interval descriptively; no extra significance bar.
3. Zero B decisions >250 ms and B p99 <= A p99 +15 ms. Pool all candidate
   decisions (searched and forced waits), in milliseconds; report p50/p99/max,
   overshoots, truncations/fallbacks, worker count/nice/host load. A comparison
   uses the same gate schedule, not the historical Stage 5b p99.

Sample-size premise: effective threshold max(.53,.5+1.96*SE). At320 pairs,
power at true.55 is about.91,.82,.72 for decisive fractions.3,.4,.5. The80% MDE
is.543–.555 and false-pass rate at.50 <=.025. These are design premises.
A FAIL does not exclude improvements smaller than about+.04. Fixed640 primary
games; no optional stopping. These power figures concern condition1 alone.
Condition2 is a point bar over256 paired games withSE about.03–.045, varying with
within-seed B/A correlation. It fails with probability about.14–.25 at true
Delta=0, and passes with about the same probability at trueDelta=-.06. Joint
power for conditions1–2 atmu=.55,Delta=0 is about.62–.71 before condition3.
A condition2 FAIL does not demonstrate a regression of that size; a PASS does
not demonstrate non-inferiority. The03 B-vs-A pilots have120467 B decisions
with0>250ms, bounding the event rate only below about2.5e-5 (rule of three).
Over about790000 B gate decisions, condition3 passes with probability about.92
at true rate1e-7 and.46 at1e-6. These are operating-characteristic premises,
not permission to change the zero-tolerance timing bar.

Pass: B becomes default C56 fair player and live-loop v4 P3 uses it.
Fail: A stays; imitation remains fallback and a base for later work. No tuning
on these games. The sole predeclared retry is v2, with fresh seeds.
Report all results including failures; interruption rules below are authoritative.


Every >200ms decision is applied unchanged; simulated time pauses during the
controller call. Lateness affects only timing bar3. B's pool is every decision
in896games; A includes640primary-opponent and256secondary games. Report A>250ms
as host-noise control. Report strength bars1–2 and timing bar3 separately; bar3
failure is gate FAIL whatever cause, with no rerun. Remedies need fresh registration.
Secondary order B0,B1,A0,A1 in one worker; report timing per arm/host descriptively.
Seat0 decides first; swaps balance controller order. Belief seat0 seed equals
planner seat1 seed; this coupling is fixed and symmetric, not a new random stream.


## Sealed primary and serving

Checkpoint SHA256: `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`.
Primary main-2026100802, step22552; dev-selected and sealed before heldout.
Gates(b)/(c) are independent of gate(a)'s verdict; no gate(a) outcome payload,
RESULTS, prediction or statistic is opened or used. Stage only a byte-identical
released checkpoint; verify its hash before freezing and every game start.

Serve EMA at T=1. Sealed dev temperatures are provenance only:
[1.0635037422180176,1.1410114765167236,1.0741008520126343]. For(b), the policy
ranks top8 proposals; these temperatures calibrate gate(a) NLL/ECE, not strength.
For(c), T=1 sampling is prespecified and matches training. Calibration now would
be an unqualified post-design serving change. No calibrated arm or secondary run.

Model source is exactly the post-T5 gate4 scorer source, resource-r2 executable
manifest2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13,
specified by gate4-scoring-launch.json and its adapter freeze. Tile width64,
entity cap128, unpadded batch1 CPUfp32 serving. The model and D1 source equality
receipt records snapshot, expected manifest, host/time and T2 dependency hashes.
e3c60ef3 is historical plumbing only. ed42/1fed/506e/d992 and P16 full-cell/world
parity document post-T5 requalification; r13 is final gate(b) admission evidence.
The final code successor adds c-only replay audit fields and full-width NumPy
seed-array compatibility, plus scheduler offset plumbing and stricter freeze
validation. No model, public mask, search decision or engine code changes.
The coordinator explicitly retains timing/host admission across namespace
changes: these qualify code/hosts rather than particular gate seed values.

Dev-only forward check: seed2026100826,4096 recorded row IDs, up to2048 rows with
>100entities (all if fewer; actual dev population has0 such rows). Scorer
load_model(main,EMA), padded CPUfp32 batches128, versus serving load_policy(EMA),
single_features, unpadded CPUfp32 batch1, one thread. Temperatures1 in both.
Predeclared pass: identical legal masks; max legal gate/card/tile logprob delta
<=1e-4; identical top8 joint list except swaps separated by<1e-5 in both paths.
PASS: max deltas2.3842e-6/3.8147e-6/1.144409e-5, zero mask/top8 mismatches, no tie
exceptions. Mean dev jointNLL0.34585835 over4089 supervised rows. First helper
attempt failed on a NumPy/Torch scalar-type error; retained, fixed without
changing sample/model/thresholds. Coordinator22:38Z waived descriptive GPUbf16
comparison: serving is CPUfp32 and required CPU equality passed; no added validity.

## Fair information and integrity

Neither arm nor v1 reads the opponent's unrevealed hand/cards, deck order or
engine RNG. D1 uses timestamped accepted public events and known own order;
opponent elixir/revealed cycle facts are public-event derivations. Search samples
opponent states from the train-only public prior using its own planner/belief
seeds. T1 public-information audits, train/serve D1-skew checks and exact prior
parity are evidence. Legacy policies/scripts retain unchanged public v4 inputs.
Receipt collectors cannot feed hidden state back to a controller.

R19 admission criterion (binding coordinator restatement): zero model-command
rejections attributable to **timing, staleness or host load**. Deterministic
mask–engine occupancy rejections (TimedExplosive/blocks_deployment and
building-footprint guards; public maskv1 misses them) are **part of play**.
The same fallback applies to every arm: the engine drops the command and the
decision becomes a no-op wait. No serving/mask change; maskv2 is for future users.
Each qualification rejection must reproduce under exact recorded-action replay
on03 without search/inference/wall deadline and classify as one of the occupancy guards enumerated in the pinned census
`reports/mask-v2/BLOCKERS.md` (SHA256 3e7de4497897cbc122efed757c1c1cc0872c4383103c24c06351e4a1361d4d87) and
`reports/mask-v2/blocker-census.json` (SHA256 c9f23ffd3cdf4232e60f51d4cae6b44a27ed63a9d1df29745b77bb583d48aab1):
a TimedExplosive blocks_deployment payload (BalloonBomb, GiantSkeletonBomb,
BombTowerBomb, SkeletonContainerNew/SkeletonContainer, MightyMiner ability bomb),
live-building footprint or air collision, or crown-tower command exclusion.
Any other guard is unclassified and treated as non-reproducing. The criterion
concerns the engine's determinism for the recorded command. The command's
selection under the wall deadline is part of play.
A non-reproducing rejection counts as timing-attributable and blocks admission.
Never rerun pilots just to obtain a clean rejection sample.

After all games of a gate complete and before any outcome analysis, every
model-command rejection in every protocol is replayed by exact recorded-action
replay, without inference/search/deadline. Replay reports only reproduce/classify
per rejection. A rejection that does not reproduce or does not map to a known
occupancy guard is non-deterministic. Any such B rejection fails gate(b)
condition3 (integrity), whatever its count. For(c), any such rejection is an
exact-replay mismatch underR12 and is reported with the affected protocol verdict.
No rejection-excluded, mask-adjusted or what-if score is computed or used for
any decision. Analysis refuses a missing replay receipt or changed game hashes.


All4 r12 rejects reproduced: RoyalHogs813 at5970/5980/5990/6000, live
TimedExplosive blocks_deployment; all186 recorded commands replay exactly.
The shared A/B apply loop records false, does not retry/replace, and advances
simulation; guard returns before card/elixir/cycle mutation. The analogous02r9
six rejects also reproduce occupancy;02 remains excluded from(b) for latency.
Report rejection counts/rates by arm, protocol and card, abilities separately;
denominator is non-wait command attempts including rejected commands. Report
pooled B-minus-A rejection rate descriptively, never a gate bar. Audit counters
run outside controller deadlines. Preserve every reject in outcomes/timing.
Predeclared descriptive, never a bar or adjustment: per arm/protocol, non-wait
command attempts, rejected commands/rate, rejection episodes, affected games,
per-card counts, replay guard class, B-minus-A rejection rate and episode count.
An episode is a maximal run of the same rejected command in one controller's
non-wait command stream in one game; intervening waits do not issue a command,
while a different or accepted command ends the episode. Also report decisions
lost. The exact two-sided episode-count test exchanges A/B labels jointly per
seeded world, counts the absolute total episode difference, and enumerates its
sign distribution by integer dynamic programming. This paired-world descriptive
test makes no independence claim about consecutive rejected commands.
Rejections arise from the shared mask-v1/engine occupancy gap, with identical
fallback; cost falls on the arm that chose the command. Gate(b) measures B under
maskv1. No conclusion about maskv2 is drawn; no adjusted score is computed.

## Fixed execution, interruption and reporting rules

Home CPU only. Gate(b):03,16 processes, workers0..15, three-CPU tasksets0..47,
nice10,2Rust threads/game,1Torch/BLAS thread. Reserve SMT siblings64..111;
remaining48..63,112..127 are co-tenant/headroom cores. Keep>=16threads headroom
throughout gate(b). The coordinator keeps the v4 CPU threshold grid OFF03.
From first to last world no own seed scans, builds or bulk copies run on03;
receipt mirroring below1MB/s is the only I/O-workload exception. Gate workers use
physical cores0–47; siblings64–111 host no own co-tenant. Cache servicePID3838563
is verified on48–63,112–127 only, receipt `imitation/gates-bc/receipts/r17-cache-affinity-r1.json`.
Before first world capture lscpu topology and non-gate process/thread affinities;
refuse launch if a competing workload overlaps0–47 or64–111. Reverify the cache
identity and affinity at launch; the receipt is evidence, not an exemption. Load1 ceiling20; pause new games above it.
r13 qualified32 B-vs-A games,30352 decisions,p99200.296566ms,max202.229559ms,
0>250/illegal/rejected,7965 exact D1 rows, peakload18.0. Earlier qualified bound
p99200.362424ms. Candidate counts match; final counter-code qualification complete.

Gate(c):02,16 processes, workers0..15, taskset0..15,nice10,1Torch/BLAS thread,
load1 ceiling64. No concurrent(b)/(c) on a host. No leased games. No extra/spare
hosts in this registration; changed host/concurrency/affinity requires reviewed
pre-freeze change, never timing-driven reassignment. All worker partitions are
world-index modulo16. The allocation is coordinator-approved22:38Z.

02/03 match Python3.12.13,Torch2.10.0+cu128,numpy2.3.5, Torch config and uv-pip
freeze hashes exactly. Verify native/runtime manifests before every game. CPU
cross-host P16/C56 action-hash comparison on disjoint plumbing worlds is required
before freeze. Console users halt new starts; active games finish. During gates
inspect liveness, exits and resource receipts only, not outcomes or timing.
Co-tenant load cannot exceed the qualifying envelope. Slow completed games stay.

A technical interruption is only an external stop of an otherwise healthy
process: operator/supervisor signal, host reboot/loss, kernel OOM, filesystem
failure. Any game/engine/script/search/model/candidate/legality/D1 exception is
not technical: preserve traceback and world identity and stop new games of that
gate. A B-attributable exception or matching assertion is gate(b) integrity FAIL.
Other in-game exceptions require written outcome-blind reviewed amendment before
further games. Never replay an exception to remove its failure.

C56 publishes atomic per-game receipts; P16/H2H publishes two-seat worlds.
Completed receipts remain. Before technical resume, record exact interrupted
world/arm/seat/host/log plus external cause and evidence. prepare_resume requires
that incident, refuses live workers, archives incomplete directories and HALT
under technical-interruptions/ATTEMPT, and recreates only missing canonical
world/game paths on the same host/concurrency. It never discards a completed
receipt. This accurately describes the implemented canonical-path recovery;
failed artifacts stay outside the sole canonical games analysis root. Any
additional replay root must be ledger-authorized and duplicate-free. No outcome
analysis at any incomplete stage. If incomplete, report not completed/no verdict
without an outcome summary. No rerun removes slow/rejected/illegal/lost games.

C56 plays through terminal including overtime/tiebreak; draws score0.5.
P16/H2H max_ticks6001 resolves300s tiebreak; terminated=false is retained using
evaluator score, draw0.5/non-win, with truncation counts reported. Four(b) spot
replays must match initial decks/state/seeds/candidates up to first truncated
search root; wall-clock-dependent outcomes need not match. Gate(c) spot replays
must match action streams; audit command-stream hashes enable this comparison.
Qualification games stay unscored until both gates publish and never enter
analysis. Report all statistics/CIs, legality/role/candidate audits, protocol
failures, interruptions, per-host compute and raw receipts, regardless of bars.

## Fresh-seed audit and freeze prerequisites

Inventory01/02/03/04/05/07/08/13/14/15, including aborted jobs: filenames, JSON,
JSONL/gzip, NPZ seed metadata, logs, manifests and source seed formulas/ranges.
Read metadata only on01/08; exclude gate(a) eval/eval_ood predictions/statistics,
RESULTS and gate4 scoring output paths before opening. Preserve the exclusion
list, every input hash, raw match/error and explicit evidence-based resolution.
Own prospective seeds/drafts/scanner-command echoes are excluded only with
content/field-level proof; other metadata in those files remains in the audit.
07 has no historical export and remains offline: use disclosed off-host job
bounds, including possible interrupted S1 waiter, all4356 proposed seeds checked.
If07 returns before freeze, scan/reconcile. Any unboundable job/formula or overlap
blocks freeze; only coordinator may change seeds, prospectively before outcomes.

The complete merged seed/formula audit is pinned in the delimited seed section; its raw errors and evidence-based resolutions are retained.
The new schedules preserve counts, pairing, strata and seat order; cross-gate seeds are disjoint.
High-seed plumbing checks (>=2^40,<2^48) cover every route without strength
analysis; static review checks all integer consumers/derived streams. Pin those
receipts before freeze. Source formulas and new launches after scan cutoff need
explicit range reconciliation; partial scan completion never certifies freshness.
Synthetic analysis-contract fixtures use prospective numbers only as fake row
identifiers; no simulator runs, exclude them with pinned source/receipt evidence.

Neither this draft nor partial approval authorizes gate games.
Independent review must cover this document's exact hash, final source/analysis,
audit resolutions, schedules and all prerequisites before register.py freezes
both PREREGs. Frozen external PREREGs are authoritative; snapshot-internal draft
copies are historical inputs. No optional stopping, tuning or gate(a)-dependent
selection. No game starts before both freezes.

## Content pins

| Input | SHA256 |
|---|---|
| executable source tree (excludes snapshot-internal PREREG copies) | `e35e83bf5029720e51102c7bc2cd28d38ef1aefeed7b374d3ccf0b1d7a71d76a` |
| selection | `1cbb2bf54c98dc570eb1715950f9ec21e9f4459560727bb4ac26c0d63789fc69` |
| release | `c8a44c8dcb04e07f582570bdf994e9c8c576c256f201a7f7b53de4b44412d3c5` |
| pre-heldout seal | `8a8929326dc2d1313fcd10e4422cb770e9bc246eccd28d7ed2e5b746fbbae681` |
| gate4 adapter freeze | `d77419e38ab193d14a17134955843aa1384b5a45d0e867f99aa912cc4a771816` |
| imitation/t5/receipts/gate4-scoring-launch.json | `6a4f63395872e8a39b88db5c64a91067654ff7d7105977e23bbc072e31f46053` |
| imitation/receipts-t6t8/prior-parity-r1.json | `f357afffda676b12addcc42206ed70236f0a5cfe0c689e8c4a648e80b40b1b35` |
| imitation/gates-bc/receipts/runtime-inputs.json | `cbd8bc934700ed68ae49be02dd20847ddf9d50f271383425da437ad0256fc114` |
| imitation/gates-bc/receipts/final-source-parity-r4.json | `973abb6913c9e4d6f953d2bd1400cf24323e055e1d16388b17845229928b767a` |
| imitation/gates-bc/receipts/source-r14-delta.json | `e64d69bcc1c8275430a53c49ccca2c614fb5f93a7180ca7e5f0d6f1e06a6aba5` |
| imitation/gates-bc/receipts/dev-forward-r2/plan.json | `a147955f5d44a57ebbd03fc9d0940983d2dbb1750eb3b92bd009170ffa359122` |
| imitation/gates-bc/receipts/dev-forward-r2/result.json | `63fcada9c134ce50058d47d72c6190bd3e9fab1e35af7c6a7c8b1adf31bc5f5d` |
| imitation/gates-bc/receipts/final-pilot-03-r13.json | `a33441585872d2d559de458aa9d4df1ef7d07dbe52dc3be08a3083a0abb07205` |
| imitation/gates-bc/receipts/rejection-03-r12-replay.json | `09dfed64948d4383904662518fbd119413f4e92e22cd2ecbd6630bdb957052a4` |
| imitation/gates-bc/receipts/host-stack-02-r2.json | `93215cab7e2ad7d4379ab4d61fbdebd378730181d622a05b94ad34b5912d11cc` |
| imitation/gates-bc/receipts/host-stack-03-r2.json | `1a4be254cffe20b35fd5e468c218f0f780f28c51d9f3f59c276c340378245259` |
| imitation/gates-bc/operations/analyze_gates.py | `8710ab6b5baa6b02761bae408e7d8e5e0ed215650917e25f7270e8fe108ad85a` |
| imitation/gates-bc/operations/render_reports.py | `63b8dc3603a17752fb551ee7728bd7c550fef43e146214cbfd140b85f66d8d06` |
| imitation/gates-bc/operations/run_host.py | `e7ab12851f8ae5909643b8868a1881ead28dfdaed167d3a2cc5f4753f98cca97` |
| imitation/gates-bc/operations/prepare_resume.py | `3411c029f188a2173f3b4284fb38683288f2dd8a6c17e0dddd45d748e03cfb3d` |
| imitation/gates-bc/operations/test_analysis.py | `6cc10b290cf50ae0e530f454770167733a4d5ac08936da0b73ffa0b463e9fe92` |
| imitation/gates-bc/operations/test_analysis_c.py | `7a11932dfda9442385f73e25dbf2bc51af87f3999d07f1350c1fd8a676c399c1` |
| reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json | `80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a` |
| reports/strategy_council_20260928/human-prior-p16/checkpoints/human-bc-natural-seed2903.pt | `49be14806a7e7e6ab26621e25230d3f6f7f0be4d84aabd480cbb8097de4ab482` |
| reports/strategy_council_20260928/human-prior-p16/scripts/compare.py | `54530eec977c9513a52091b37e1a1b933178220d1b622d67c43c8293b6a05bf1` |
| reports/strategy_council_20260928/pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt | `e6bc82c4d357ee6b17a3c266b221b2786494a2752880616101f2fc1340c980a3` |

Qualified code bundle `/mpac/sdicks02/repos/clasher-eval-snapshots/1cc0c74203987756`;
the confirmation manifest pins a metadata-only successor containing these drafts;
runtime `.../runtime-bc-v1`; checkpoint `.../inputs-bc-v1/main02.pt`.
Merged-audit pins are in the seed section. Cross-host action parity and co-tenant affinity receipts are pinned below. All operations and evidence files are included
in the freeze manifest; no mutable shared checkout is a serving dependency.

## Mechanical audit appendix and invalidators (RC-5/RC-7)
Before freeze, review: each01/02shard merged once, inventory hashes, unchanged
single-process comparisons, raw errors/resolutions;08formula content coverage
against04 and truncated-trace byte equality; merged10host direct/bounded audit;
all explicit and derived seed formulas/invocations; own-input seedset proof;
post-scan seeded-job ledger from each host's scan START; RC5 supplementary roots
and off-host history bounds; and RC8 high/low-seed differential/type evidence.
The04historical-docs.json and live parallel inventory/shards00–06 were replaced
by the coordinator's hub-mirror-127x04-20261008-r2 loop (01→04 live paths,
every30min fromOct7until23:33ZOct8). The coordinator stopped it by verifiedPIDs
and moved backups to /mpac/sdicks02/mirrors/hub01/. Use the preserved original
04merged archive on03 (245683files,31original shard hashes);24individual parts
still match,7original shard blobs were replaced. The complete merged seed
evidence is intact. Original historical-docs receipt on05 SHA169cc550c954251435c536ec1eec0805fc3b10fd2f0f8308398ae7e1174c2d08
is preserved. Coordinator23:36Z explicitly approved this archive-based audit.
Eleven truncated traces are bound by recomputed execution identities plus plan
hashes; two standaloneepisode11traces rely on an adjacent declared plan, a
weaker disclosed bound. Raw errors stay in the receipts, with byte-identity
transfers of these bounds and literal synthetic-fixture resolutions.
08has no new formula contents beyond04: evidence is identical source content
hash coverage, not merely an empty new-formula review file.
History outside direct scans: f35 sole archives `artifacts/worktree-data` and
`live-loop/l1/v3` plus possible f35 jobs; leased09/11/16/18. Use pinned off-host
job-group bounds and committed script/config history, never assume completeness.
11includes T6/T8's20synthetic-checkpoint search games in addition to identity and
training. Supplemental direct roots: src/scripts/experiments/configs/tests/
checkpoints/datasets on home hosts, with explicit absent/symlink receipts.
Any unboundable history goes to coordinator before freeze.
Invalidators: exact/formula intersection with any proposed/derived seed;
unresolved unreadable file; missing/duplicate shard; undeclared roots; unexplained
changed compared hash;07returns (real scan then required); schedule/proposed-seed
edit; or executed-code edit after qualification. Each returns to review.
High-seed differential evidence includes the earlier3900000001/1752516353 and new >=2^44 values: different
initial decks/state required, all recorded/derived seed fields exact intended
integers. Static review lists every consumer and type; acceptance alone is not
proof against silent truncation. No qualification strength analysis is used.

## Full-width random-seed compatibility
P16's NumPy legacy global seed API accepts a32-bit scalar or a uint32 seed array.
For an integer>=2^32, the pinned adapter calls
SeedSequence(full_integer).generate_state(624,dtype=uint32) and supplies that
array; it never truncates the integer modulo2^32. For every older scalar<2^32,
it calls the original API unchanged. This fixes seed-input compatibility only.
Python random.Random and NumPy default_rng accept the full integer; Torch CPU
manual_seed receives the complete integer below2^64. The engine's public initial
deck/state differential and recorded seed fields verify the namespace through
all six routes. Model source, EMA buffers, T=1 and public masks are unchanged.

## Final qualification and review evidence

Admission evidence: r12 on798e,32terminal B-vs-A games,29744Bdecisions,
p99200.270ms,max201.499ms,peakload18.1,0>250ms/illegal,4replay-reproduced
occupancy rejects. r13 on2110:32terminal games,30352Bdecisions,p99200.296566ms,
max202.229559ms,peakload18.0,0>250ms/illegal/rejected,7965exactD1rows,
exact candidate-count equality. Both receipts remain; neither replaces the other.
Admission requires at least20terminal games and8exactD1-skew games, the qualified
p99 bound,0>250ms/model-illegal,matched candidates,peakload<=20 and every rejection
exactly replayed/classified. Failure requires coordinator decision, not a clean
resample. Coordinator preserves this timing admission across the seed offset.

RC2b: four games per five c routes, real checkpoint, on02and03, exact initial
decks/seeds/seats/ticks/action streams; current versus798e/2110 also exact.
Full-width compatibility repeats20games per host at2^44+3900000001: exact
02↔03streams,0illegal/rejections. The scalar32-bit NumPy path is unchanged;
large-integer SeedSequence expansion is pinned and tested. All six routes pass
wide-seed plumbing. Rejection replay passes20route games/1328commands and all4r12
known payload rejections. These are qualification receipts, not gate outcomes.

The executable tree hash excludes only internal draft copies. The final full
snapshot hash is recorded by the independent review receipt and appended by
register.py to each frozen PREREG. This avoids requiring a document to contain
its own content-derived snapshot hash; all serving source bytes remain pinned.

| Required evidence / operation | SHA256 |
|---|---|
| imitation/gates-bc/receipts/source-code-tree-r3.json | `b3fe32b2fd8dac7484fc8ee0feb973ff953a6a70b7508055a43573d85164f201` |
| imitation/gates-bc/receipts/final-source-parity-r6.json | `06f0e83e431e57023e135d86a16abce7d80a616bfb395e08428ee2e64b5bf222` |
| imitation/gates-bc/receipts/source-r17-delta.json | `7fddb1c0c4d211770d7aa00ab59f9b4d8992b5e4c42c776708642a90d694b7c7` |
| imitation/gates-bc/receipts/final-pilot-03-r12.json | `9b3c9408658f30e19db486ce670ebb6c11010b37ea094b7aca9d4fb46677a745` |
| imitation/gates-bc/receipts/final-pilot-03-r13.json | `a33441585872d2d559de458aa9d4df1ef7d07dbe52dc3be08a3083a0abb07205` |
| imitation/gates-bc/receipts/rejection-rc4-r1.json | `74774d9d1aab756eeeffa83f31535da6e4cc1dfdb78f3acb97a635ec28264754` |
| imitation/gates-bc/receipts/replay-qualification-r1.json | `bc6c92544fb9e77aa327a88340e7ee7b038c96b49a41f435aab1c59f7367e8b4` |
| imitation/gates-bc/receipts/wide-seed-c-parity-r5.json | `0daaaa98e46441c7a1c35e4f6c31425cc751439a183059dc5924d6a1faeded2c` |
| imitation/gates-bc/receipts/wide-seed-search-r5.json | `0f4b350a8767b93c4f282d1342bb4361b45c12ed34de2b84d71300ce2aef2647` |
| imitation/gates-bc/receipts/seed-compat-r1.json | `efb57eb9e47f5e7c1bae5cb76336f6d39e4cf38d2cba52150d1931fd5ae76efc` |
| imitation/gates-bc/receipts/cqual-r4-host-parity.json | `98e5f109adac03c3aa4d152dfbe2ae1d5f5db1fc8ff2d71bc5ed618405bd985d` |
| imitation/gates-bc/receipts/cqual-r4-source-parity.json | `f8e375077949929480b911e704954aa349cfb03f2091d0593e795c45c1689af5` |
| imitation/gates-bc/receipts/cqual-02-topology-r5.json | `401c4a814816bdb0420f85a14431f9e01d0de17042281760ebc87ed9d5c01ada` |
| imitation/gates-bc/receipts/r17-cache-affinity-r1.json | `6581b67abc131ae2493157a537a963496a084cb4f05516185f838541d38f2664` |
| imitation/gates-bc/receipts/07-COVERAGE.md | `dce4fee7b28788349605e00daad2cb3c47c6cc6dc681d68b2710969d95cd8c3c` |
| imitation/gates-bc/receipts/inventories/127x07-offhost-candidate-r2.json | `59f65b8ed6e194febe75a70a387ac9b923f6d2f24e9492e370ddcab9a1eea7f3` |
| imitation/gates-bc/receipts/offhost-rc5-bounds-r3.json | `234c133cc99563bca68b55bd4181484ca3f0025528e1bed059ef26d276492c4d` |
| imitation/gates-bc/receipts/post-scan-launch-ledger-r6.json | `08694d5959e091597332daf0b2847cc0dc7f47d336e786b767a4734142c21aea` |
| imitation/gates-bc/receipts/own-input-proof-r3.json | `2056a00471681571f4727c3b5a95754bc5c92be1f69b105af7483a70c110efd6` |
| imitation/gates-bc/receipts/register-guard-contract-r1.json | `e9bc6effd53b604b3486eb54b3ab762285f79c0824c4986dfe2ed13f953cfa02` |
| reports/mask-v2/BLOCKERS.md | `3e7de4497897cbc122efed757c1c1cc0872c4383103c24c06351e4a1361d4d87` |
| reports/mask-v2/blocker-census.json | `c9f23ffd3cdf4232e60f51d4cae6b44a27ed63a9d1df29745b77bb583d48aab1` |
| imitation/gates-bc/operations/seed_namespace.py | `892056ed1f877472827051b6118593802be396723568f3bf2550eda35f208f07` |
| imitation/gates-bc/operations/build_fresh_audit.py | `3c97a068bd118aa5dff066c98a68c01b2f0eefa489ea517297c2f6020520cab0` |
| imitation/gates-bc/operations/replay_completed_gate.py | `9ce5852e248c4848f4fca5cac27a33ec9d7b0ad0bdf6089fab14e1d1859430ef` |
| imitation/gates-bc/operations/replay_gate_commands.py | `17bc681290003f42209d42cb9e49bb810777077a386bdc946ef6b7f6402a47d2` |
| imitation/gates-bc/operations/capture_affinity.py | `ff263fc813bde9acdf36e452a2c234cc06af94a2b5dc774b58ab765fc4e671ab` |

Confirmation snapshot SHA256: 016b42fac2c40614fa55a8bb859a80893f6bea91c189a350d2f34fb3bab1b907
