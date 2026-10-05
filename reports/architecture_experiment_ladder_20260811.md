# Architecture and throughput experiment ladder (2026-08-11)

## Decision rule

The current promoted policy and its checkpoints remain controls. No architecture
or simulator optimization is accepted because it is simpler, faster, or has a
lower training loss. Each candidate must be isolated first, evaluated with the
same seed/data/budget, and then pass the relevant independent replay and exact
simulator parity gates. Promising combinations are separate experiments rather
than assumed additive wins.

## Architecture screen

Fixed imitation screen: `human_safety_balanced_v1.npz`, seed 1041001, one epoch,
sequence length 32, spatial-v1 objective, d_model 192, 5 actor layers, 3 critic
layers, memory size 384, and identical left/right augmentation.

| Variant | Question | Status |
| --- | --- | --- |
| attention + LSTM + hybrid card inputs | matched reference | control |
| DeepSets + attention decoder + LSTM + hybrid | is entity self-attention needed? | trained; promising independent action-type/NLL result, placement regressions; needs repeat seed |
| DeepSets + global decoder + LSTM + hybrid | is all attention needed? | trained; placement-NLL candidate with type regressions; needs hybrid-decoder follow-up |
| DeepSets + global decoder + GRU + hybrid | does cheaper recurrent memory suffice? | trained; independently dominated by LSTM, reject repeat |
| DeepSets + global decoder + feedforward + hybrid | is recurrent memory useful with current observations? | trained; raw stateless lower-bound rejected, explicit-belief version unresolved |
| attention + LSTM + card identity only | do explicit static mechanics improve transfer? | trained; strongest matched and independent result so far; repeat candidate |
| attention + LSTM + zero-initialized mechanics residual | can mechanics add value without perturbing identity at initialization? | trained; excellent local validation but independent type regression, reject repeat |
| attention + global decoder + LSTM + hybrid | can attention preserve action choice while a simpler decoder improves placement? | trained; severe independent regression despite excellent matched validation, reject repeat |
| 272-wide DeepSets + global decoder + LSTM + hybrid | is the pooled type regression structural or caused by halving capacity? | trained; strong independent likelihood/type gains with small placement-tolerance tradeoff; repeat candidate |
| DeepSets + global decoder + LSTM + identity only | do the pooled model's location-likelihood gain and identity-only model's type gain combine? | trained; independent NLL/type candidate with hard-placement tradeoff; repeat candidate |
| unchanged attention policy with batch-level trailing-padding trim | can dense attention avoid work on masked entity slots without changing semantics? | verified behind explicit imitation flag; pre-transfer end-to-end MPS step 0.491 to 0.172 s (2.85x), zero action changes |

The feedforward row is deliberately a lower-bound memory ablation, not yet the
full proposed explicit-state alternative. Current actor observations contain
the public board, own hand/next card, own elixir, and previous own action/reward,
but intentionally exclude hidden opponent hand/elixir/cycle. The existing human
corpora also do not contain exact opponent action histories. A fair explicit
tracker experiment therefore needs a new public belief feature and corpus
reconstruction/collection; a feedforward loss here would not by itself prove
that an LSTM is necessary.

First matched result:

| Metric | attention/LSTM/hybrid control | DeepSets/attention/LSTM/hybrid |
| --- | ---: | ---: |
| validation loss | 1.685698 | 1.721686 |
| validation exact accuracy | 0.669234 | 0.583350 |
| validation action-type accuracy | 0.794404 | 0.690973 |
| validation within 1 tile | 0.321046 | 0.225922 |
| validation within 2 tiles | 0.348098 | 0.288942 |
| reported training wall time | about 765.5 s | 453.1 s |

The speedup is real, but the held validation regressions are too large to call
this architecture a replacement. Independent replay evaluation nevertheless
contradicts the local validation split in a useful way. Relative to the matched
seed-1041001 attention control, DeepSets improves chronology NLL from 10.736882
to 10.677832 and action-type accuracy from 22.293% to 23.381%; on the broad
Arena-28 set it improves NLL from 10.886231 to 10.735255 and action-type accuracy
from 27.870% to 29.255%. Those gains are not clean no-regressions: chronology
within-one-tile accuracy falls from 4.405% to 1.816% and broad within-two-tile
accuracy falls from 10.587% to 8.795%.

The stronger seed-1011001 clean attention policy still wins decisively (9.373745
chronology NLL and 9.761567 broad NLL). The large control-seed gap means a
single seed cannot decide the architecture. If DeepSets remains among the top
two variants after the full screen, rerun it at seed 1011001 before any league
training.

Repeat trials now use the new `--split-seed` control: the episode split stays
fixed while `--seed` varies initialization, batch order, and augmentation. This
prevents the earlier 1011001-versus-1041001 comparison from silently conflating
model stochasticity with a different train/validation episode partition.

The fully no-attention LSTM variant is also mixed rather than an automatic win.
It improves seed-matched joint NLL much more strongly (10.736882 to 10.153861 on
chronology; 10.886231 to 10.121569 broad), but action-type accuracy falls from
22.293% to 21.948% and from 27.870% to 27.688%, respectively. Record-level type
changes are 212 improvements/225 regressions on chronology and 438/451 broad.
This is a calibration/likelihood candidate, not a behavioral promotion. The
expanded evaluator now reports action-type NLL and conditional-location NLL so
later decisions can identify which factor drives joint NLL.

That decomposition confirms the mechanism on both independent sets. On
chronology the no-attention LSTM worsens action-type NLL 4.824298 to 4.941405
but improves conditional-location NLL 10.731511 to 9.460758; broad moves
4.228118 to 4.319441 and 10.806212 to 9.416934. The GRU is dominated by the
LSTM independently (chronology 10.601932 versus 10.153861 joint NLL and 21.258%
versus 21.948% type accuracy; broad 10.546138 versus 10.121569 and 27.143%
versus 27.688%). GRU is rejected from repeat-seed follow-up unless a later
gameplay screen supplies contradictory evidence.

The raw feedforward lower-bound does not beat the LSTM. Chronology joint NLL is
10.324057 versus 10.153861, action-type NLL is 5.074574 versus 4.941405, and
type accuracy is 21.842% versus 21.948%; broad is 10.298067 versus 10.121569,
4.416892 versus 4.319441, and 27.828% versus 27.688%. Feedforward does recover
slightly better within-two-tile accuracy (11.300% chronology and 10.653% broad),
but not enough to offset the likelihood/type tradeoff. Reject the raw stateless
variant from repeat-seed training. This does not reject a future feedforward
model with an explicit public opponent-cycle/elixir belief, which is a different
observation experiment.

Identity-only attention/LSTM strongly beats the matched hybrid on both
independent sets. Chronology improves joint NLL 10.736882 to 10.510384,
action-type NLL 4.824298 to 4.713870, type accuracy 22.293% to 25.239%, and
within-two-tile accuracy 11.190% to 14.090%; record-level type changes are
394 improvements and 283 regressions. Broad improves 10.886231 to 10.533334,
4.228118 to 4.109458, 27.870% to 30.401%, and 10.587% to 12.057%, with 779 type
improvements and 598 regressions. It still trails the seed-1011001 clean policy
on joint/type metrics, so it is not promoted. It earns a fixed-split repeat and
a zero-initialized mechanics-residual follow-up. The latter tests whether the
current hybrid loses because mechanics are intrinsically unhelpful or because a
full random stat projection perturbs identity from the first update.

The attention-encoder/global-decoder hybrid is a particularly clear warning
against selecting on the local validation split. It produced the best local
numbers in the screen (1.465494 loss, 75.531% exact accuracy, and 87.317%
action-type accuracy), yet regressed on both independent corpora. Chronology
joint NLL moved 10.736882 to 10.813495, action-type accuracy 22.293% to 19.692%,
and within-two-tile placement 11.190% to 8.625%. Broad moved 10.886231 to
11.096241, 27.870% to 24.976%, and 10.587% to 8.007%. Although action-type NLL
improved on both sets, record-level chosen-type changes were net negative
(215 improvements/313 regressions chronology; 462/669 broad). Reject this
variant from repeat-seed training and do not infer that the simpler decoder is
a safe substitute for tile attention.

The parameter-matched 272-wide pooled model shows that much of the narrow
pooled model's action-type weakness was under-capacity rather than a structural
failure of permutation-invariant pooling. Chronology improves matched-control
joint NLL 10.736882 to 10.115900, type NLL 4.824298 to 4.759557, type accuracy
22.293% to 24.045%, and within-two-tile placement 11.190% to 11.258% (245 type
improvements/179 regressions). Broad improves joint NLL 10.886231 to 10.202258,
type NLL 4.228118 to 4.186153, conditional-location NLL 10.806212 to 9.764222,
and type accuracy 27.870% to 30.052% (527/371), while within-two-tile accuracy
slips slightly to 10.191%. It remains behind the clean seed-1011001 policy on
joint/type metrics, but earns a fixed-split repeat alongside identity-only.

Aggregate results are not sufficient to decide identity-only versus mechanics
residual because the reference imitation corpus is extremely imbalanced at the
card level. Of 420,672 decision rows, only 17,338 are expert placements. Golem
and Lava Hound appear once, Mega Knight and X-Bow twice, and several other
enabled cards fewer than five times, while Ice Spirit appears 2,582 times. The
new `scripts/evaluate_card_frequency_generalization.py` groups independent
placement decisions by reference-corpus card frequency (unseen, 1-9, 10-99,
100-999, and 1000+) and reports exact/type/tolerant accuracy. Residual mechanics
must demonstrate a rare-card benefit there; aggregate NLL alone cannot justify
retaining extra static inputs.

Zero-initializing the mechanics residual improves optimization on the matched
split but does not rescue independent generalization. It beats identity-only
locally (1.325937 versus 1.435103 validation loss and 86.859% versus 85.767%
type accuracy), then regresses chronology to 11.051959 joint NLL, 5.270135 type
NLL, and 19.904% type accuracy. Broad similarly reaches 11.112506, 4.606600,
and 26.178%. Record-level type changes versus the matched hybrid control are net
negative on both sets (154/244 chronology and 359/480 broad). Reject this
residual form from repeat-seed or league training; retain the frequency audit
only to determine whether a future auxiliary mechanics objective is warranted.

The frequency audit does not find the hypothesized rare-card advantage for the
residual. On chronology cards with 1-9 reference placements, type accuracy is
40.0% residual, 42.3% attention identity-only, and 43.1% wide pooled hybrid; at
10-99 it is 33.1%, 40.2%, and 41.2%. Broad confirms the ranking: 41.5%, 40.7%,
and 45.2% at 1-9, then 40.9%, 47.0%, and 48.9% at 10-99. The wide pooled hybrid
is the rare-card candidate. Attention identity-only remains strongest for
moderately represented cards and hard placement. A future mechanics approach
should use an explicit auxiliary/contrastive objective rather than simply
injecting static features into the policy stream.

The narrow pooled plus identity-only factorial reverses a weak matched split on
independent data but remains mixed. Chronology reaches 10.106307 joint NLL,
4.570075 type NLL, and 24.124% type accuracy; broad reaches 10.165637, 4.002646,
and 29.674%. Those likelihoods narrowly beat the wide pooled hybrid, while
conditional-location NLL and hard tolerance are worse (9.856% and 9.130%
within two tiles). It is also the cheapest viable learner at 3.12M parameters
and 4.79x the measured training-step throughput of attention. It earns one
fixed-split repeat as a speed/likelihood candidate, not promotion.

Matched MPS step timing (8 sequences x 32 steps, seven repetitions) measures
0.512020 s for attention/LSTM/hybrid, 0.506331 s for attention identity-only,
0.184744 s for the 6.30M-parameter wide pooled hybrid (2.77x), and 0.106886 s
for narrow pooled identity-only (4.79x). These are learner-kernel timings, not
end-to-end simulator throughput, and do not count as behavioral evidence.

## Throughput candidate triage

| Candidate | Current evidence | Decision before integration |
| --- | --- | --- |
| direct scalar clipping (`adce131`) | +4.74% random, +3.64% strategy; exact hashes | strong isolated A/B candidate |
| direct entity range clipping (`9821f3b`) | +2.43% random, +1.36% strategy after scalar clipping; exact hashes | test after scalar clipping, then retain only if incremental gain reproduces |
| deployment blocker snapshot (`9736a32`) | +1.49% random, +2.11% strategy, +1.04% oracle; exact parity | strong isolated A/B candidate |
| direct strategy action geometry (`76727f9`/`237d5fa`) | +6.71% to +10.09% strategy rollouts; exact parity | test alone, strategy workloads only |
| cached strategy tile fits (`746c970`) | +2.01% to +3.05% strategy rollouts; exact parity | test alone, then factorial with direct geometry |
| reusable CPU observation buffers (`a4724d3`) | +0.46% to +0.55%; larger overlapping collector patch | defer unless a production trainer benchmark shows a clearer win |

After isolated screens, benchmark only these combinations:

1. scalar clipping + entity range clipping, then that winner + deployment blocker snapshot (shared rollout path);
2. direct strategy geometry + tile-fit cache (strategy-only path);
3. both winning groups together in a production-shaped trainer benchmark.

Every simulator combination must retain fixed-seed scalar/off, shadow, and
optimized/on state hashes with zero shadow mismatches. A combination that is
neutral or negative end to end is removed even if its microbenchmark wins.

The 8-way clipping/deployment factorial used 8 environments x 32 decisions,
seven alternating repetitions, with every random row sharing rollout SHA-256
`8bcf6125...fce432` and every strategy row sharing
`67faf6c5...f22844d`. Random improves from 194.252 decisions/s for NumPy clips
plus unconditional payload scans to 204.379 for the scalar clip pair (+5.21%);
the deployment guard is neutral there at 204.549 (+0.08% incremental). Strategy
improves 200.275 to 210.791 for the clip pair (+5.25%), then to 215.419 with the
guard (+2.20% incremental, +7.56% total). Integrate scalar unit/range clipping
and the capability-based deployment-blocker snapshot. Continue deferring the
larger reusable observation-buffer patch.

Trailing packed entity padding is separately accepted behind
`--trim-entity-padding` for imitation sequence batches. On the production MPS
batch it trims 128 slots to 15 before device transfer; construction plus
forward/backward falls from median 0.490873 s to 0.172188 s (2.85x). Legal
argmax actions are identical and maximum legal-logit drift is 2.86e-6. The
seed-1041002 repeat tournament is the production training trial; the default
loader remains unchanged.

The first production repeat supplies the more conservative epoch figure:
attention/LSTM/hybrid at batch size 32 (one 32-step sequence per optimizer
step) completed in 529.1 s versus about 765.5 s without trimming, a 1.45x
speedup and 30.9% time reduction. The corpus sequence-width median is 13,
95th percentile 20, maximum 50; the gap from the 8-sequence microbenchmark is
therefore per-step MPS launch overhead rather than untrimmed crowded batches.
Use the production 1.45x figure for scheduling, while retaining the 2.85x
measurement as a larger-batch kernel result.

The fixed-split seed-1041002 wide pooled/hybrid repeat completed in 395.6 s.
Its local validation loss was 1.586504, exact accuracy 67.781%, action-type
accuracy 75.921%, and within-two-tile accuracy 25.208%. This reverses much of
the first seed's weak local placement result, but is not promotion evidence:
the queued chronology, broad, and card-frequency evaluations still decide
whether the improvement repeats outside the training corpus.

The seed-1041002 attention/identity-only repeat completed in 516.3 s with local
validation loss 1.601904, exact accuracy 68.093%, action-type accuracy 76.896%,
and within-two-tile accuracy 26.516%. Unlike seed 1041001, it does not beat the
same-seed hybrid control locally (1.524332 loss and 81.439% type accuracy),
confirming material initialization/order variance. It remains in contention
only until the two independent human evaluations determine whether its first-
seed transfer advantage repeats.

The strategy-only factorial was rerun on the authoritative branch while the
MPS repeat tournament remained active. All 28 measured rollouts produced the
same SHA-256 `f6f4a6a8...8a24`. Median rates were 128.903 decisions/s for
decoded/uncached, 138.486 for direct/uncached (+7.43%), 131.483 for
decoded/cached (+2.00%), and 140.833 for direct/cached (+9.26%). The two narrow
changes are therefore complementary and retained; the optimizer worktree's
separate card-feature precomputation was deliberately not copied into this
factorial. The full raw rows are in
`reports/strategy_optimization_factorial_seed2301.json`.

Later optimizer candidates are triaged separately rather than accumulated:
`torch.inference_mode` has a credible roughly 0.6-1.3% rollout signal and earns
an authoritative trainer-path A/B; cached targetability primarily helps oracle
generation (2.69% oracle, under 1% rollout) and is deferred until the next
oracle campaign; direct target-kind reads (about 0.25%) are below the current
complexity threshold; and the single-pass Crown fallback (about 0.6-1.0%
rollout, 1.2% oracle) needs a combined targeting factorial before integration.

The first authoritative inference-mode A/B under the active MPS tournament was
mixed: random improved 130.463 to 132.847 decisions/s (+1.83%), while balanced
strategy fell 120.707 to 119.440 (-1.05%); hashes matched within both workloads.
That conflicts with the optimizer worktree's positive strategy result, so the
experimental switch remains disabled pending an idle-host repeat. This is not
an accepted production optimization.

Trimming only trailing padded entity slots at CPU policy inference is a much
larger candidate, but is intentionally distinct from exact simulator changes.
At 8 environments x 16 steps, random improves 162.584 to 203.654 decisions/s
(+25.26%) and balanced strategy 141.290 to 172.383 (+22.01%). Dense and trimmed
attention have slightly different floating reductions, so byte hashes that
include old log-probabilities and values differ. Their action/reward/done and
terminal-state digests are identical. A longer 8 x 128 screen also retains
identical behavior digests for both workloads while improving random 118.388 to
158.201 (+33.63%) and strategy 126.019 to 172.714 (+37.05%). The switch stays
off by default until it is wired as an explicit new-lineage trainer option and
tested in the multi-process actor path; it is not represented as bit-exact
checkpoint inference.

The trim gain is architecture-dependent rather than automatically additive.
For the 192-wide pooled model it improves random 198.829 to 204.647 (+2.93%)
and strategy 163.626 to 168.195 (+2.79%); for the 272-wide pooled model it
improves 176.184 to 184.411 (+4.67%) and 148.293 to 155.767 (+5.04%). Behavior
digests still match. Pooled inference already avoids quadratic entity attention,
so its absolute dense rate is much higher and padding trim has less headroom.
Architecture selection must therefore count both policy quality and the dense
rollout baseline, not multiply the attention trim percentage into every model.

The persistent multi-process actor path confirms the same interaction. With
four actor workers and eight environments, attention improves 337.4 to 409.6
decisions/s against random (+21.41%) and 354.8 to 431.1 against strategy
(+21.50%). The 192-wide pooled model starts faster and moves only 445.0 to
458.4 (+3.00%) and 434.0 to 442.4 (+1.94%). All seven consecutive paired
behavior traces match for every workload/architecture. The explicit
`--trim-rollout-entity-padding` trainer flag now reaches spawned actor workers,
but remains opt-in because full log-probability/value bytes differ slightly.

The seed-1041002 pooled/identity-only repeat completed in 389.0 s. Local
validation loss is 1.589401, exact accuracy 68.512%, action-type accuracy
76.223%, and within-two-tile accuracy 25.476%. It is locally similar to wide
pooled/hybrid (1.586504) and attention/identity-only (1.601904), so its much
smaller 3.12M parameter count and faster actor/learner paths matter only if the
queued independent evaluations do not expose the first seed's harder-placement
regression.

The independent seed-1041002 screens resolve several candidates. Attention
identity-only does not repeat its first-seed advantage and is rejected: versus
the seed-matched hybrid control it lowers chronology joint NLL 10.594519 to
9.882211 but reduces action-type accuracy 25.319% to 22.054% and within-two
tiles 11.216% to 9.507%; broad similarly falls from 31.422% to 27.017% type
accuracy and 9.969% to 8.592% within two tiles. Its type changes are net
negative on both corpora.

Both pooled models repeat a large likelihood gain but expose a consistent
argmax-selection weakness. Wide pooled/hybrid reaches 9.165281 chronology and
9.224664 broad joint NLL, beating the old clean attention checkpoint on NLL,
but type accuracy is 23.461%/29.590% versus the clean checkpoint's
26.990%/32.303%. Narrow pooled/identity-only is lower still at 8.791475 and
9.043211 NLL, with type NLL 3.744210/3.306183, yet deterministic type accuracy
is only 21.842%/27.143%. The narrow model is therefore not promoted on NLL.
The isolated type-weight-2.0 run tests whether this is objective calibration
rather than an encoder ceiling; no batch, learning-rate, or architecture change
is mixed into that run.

That isolated type-weight experiment is now complete and does not rescue the
narrow pooled model.  Relative to the 1.0-weight narrow model, deterministic
action-type accuracy rises only from 21.842% to 22.824% on chronology and from
27.143% to 28.639% on the broad set.  It still trails wide pooled/hybrid
(23.461%/29.590%) and the clean attention checkpoint (26.990%/32.303%).  The
extra weight also worsens action-type NLL from 3.744210 to 4.389543 and from
3.306183 to 3.880980, while within-two-tile placement falls from 10.404% to
9.535% and from 9.256% to 9.082%.  The lower conditional-location NLL does not
offset those behavioral regressions.  Reject narrow pooled/identity-only at
both tested type weights; advance wide pooled/hybrid and the attention control
to matched held-out gameplay instead of tuning this objective indefinitely.

## Promotion ladder

1. Matched validation metrics are only a screening gate.
2. Independent broad and chronological human replays decide which architecture
   variants merit more training.
3. The best one or two variants receive equal-budget repeat-seed training.
4. Only repeatable winners enter diversified league RL.
5. Promotion still requires held-out deck/archetype gameplay gates against the
   existing policy; throughput alone never promotes a policy.

The first held-out gameplay smoke test demonstrates why that last gate is
mandatory.  Against the clean attention checkpoint on identical two-game
held-out matchups, wide pooled/hybrid lost both games with -2.5 crowns/game,
no-op'ed on 98.14% of decisions where a card was playable, and placed on only
1.74% of decisions.  The seed-matched attention control split the games,
no-op'ed on 71.76% of playable decisions, and placed on 4.78%; the clean
attention self-play control was similar at 71.64% and 4.97%.  Two games do not
estimate win rate, but the severe action-frequency failure is large enough to
require a matched 24-game confirmation before any pooled promotion.  Future
architecture gates must report playable no-op rate and defensive response in
addition to replay likelihood and selected-action accuracy.

The matched 24-game confirmation rejects wide pooled/hybrid decisively.  The
seed-matched attention control scored 10-14 (41.7%, -0.333 crowns/game), while
wide pooled lost all 24 games (0%, -2.708 crowns/game).  Wide pooled no-op'ed on
97.60% of playable decisions, placed on 2.22% of decisions, and responded on
only 1.35% of threatened decisions.  It lost every sampled Graveyard, Lava
Hound, Royal Hogs, and X-Bow matchup.  On identical matchup seeds it caused ten
outcome regressions, zero improvements, and a -57 total-crown swing relative
to attention.  Its excellent independent NLL was therefore a severe offline-
metric false positive.  Do not use the global pooled action decoder for league
training.  The next isolated repeat retains an attention decoder while replacing
only entity self-attention with DeepSets aggregation.

That DeepSets-encoder/attention-decoder repeat also fails.  Although it lowers
joint NLL relative to the seed-matched attention model, chronology selected-
type accuracy collapses from 25.319% to 19.506% and broad from 31.422% to
24.556%.  It also trails the clean attention checkpoint on both sets and does
not repeat its first-seed type-accuracy improvement.  Reject it without a
costly gameplay expansion.  The repeat tournament therefore selects global
entity attention plus LSTM and hybrid card inputs as the base architecture;
subsequent experiments may optimize its training batch and objective, but must
not silently substitute a pooled encoder or decoder.

The eight-sequence (`batch_size=256`) training trial is also rejected despite
its speed.  At unchanged learning rate it completes the epoch in 272.7 seconds
versus 529.1 seconds for batch 32 (1.94x), and local validation misleadingly
improves.  Independent chronology/broad conditional-location NLL then explodes
to 15.248770/15.106554 versus 9.722424/9.805354 for batch 32, with within-two-
tile accuracy falling to 8.289%/8.264%.  Square-root LR scaling to 7.5e-4
remains worse overall, and linear scaling to 2e-3 collapses deterministic type
accuracy to 9.528%/13.579%.  Retain batch 32 and LR 2.5e-4; do not exchange
independent placement generalization for learner-kernel throughput.

## Replay provenance correction and chronological adaptation

The next data audit found that the legacy TV Royale corpus names were not a
valid leakage boundary. `tv_royale_human_sequence_newarenas_v1.npz` includes
arena 28 despite its name, and identical replay UUIDs can appear under multiple
arena-derived parquet files. Arena-level splits can therefore put alternate
views of the same game on both sides. Legacy arena-28/29 corpus results remain
useful as compatibility screens, but are no longer described as independent
generalization evidence after training on any TV Royale subset.

The missing no-op provenance for arenas 21--24 was rebuilt from the downloaded
raw parquet frames with the same two frozen KataCR detectors. Deployment and
wait moments were merged chronologically per replay, producing 126, 316, 612,
and 1,017 samples for arenas 21, 22, 23, and 24. A new global splitter assigns
each replay UUID to one side before source concatenation and retains only the
longest chronological variant when a UUID occurs in multiple sources. Focused
Ruff, mypy, and imitation-mix tests pass (7 tests).

The fixed seed-1043201 split spans 185 unique replays: 148 train replays with
3,316 decisions and 37 untouched holdout replays with 824 decisions. Replay
overlap is exactly zero. It removed 1,054 alternate replay-variant rows and
asserts one output episode per replay. The train labels contain 1,902 plays and
1,414 waits; holdout contains 471 plays and 353 waits. The manifest is
`datasets/tv_royale_replay_disjoint_split_seed1043201.json`.

Starting from the selected seed-1041002 attention/LSTM/hybrid checkpoint, a
five-epoch anchored adaptation ladder tested LR 1e-5, 3e-5, and 1e-4. The two
higher rates are rejected: both report 0% within-two-tile placement on the new
holdout even while aggregate loss improves. LR 1e-5 is the only viable
candidate. On the replay-disjoint holdout it changes joint NLL from 10.6314 to
5.5648, action-type accuracy from 26.21% to 43.33%, and within-two-tile
placement from 11.57% to 17.14%. Results on the legacy chronology and arena-28
broad corpora are compatibility checks, not independent evidence, because the
adaptation train split includes other rows from some of those replay sources.

The LR-1e-5 candidate then passed a matched held-out-deck gameplay screen
against `human_safety_student6m_v1/epoch1.pt`. Across the same 24 decks, seats,
and seeds used by the architecture control, the attention control scored 10-14
with -8 total crowns; the adapted policy scored 12-12 with zero crown
differential. Four paired outcomes improved and two regressed; paired crown
differences improved in five games, regressed in three, and were unchanged in
sixteen. Averaging the two 12-game halves, placement rate rises from 5.79% to
about 6.37% and threatened defensive response from 6.14% to about 6.64%, while
playable no-op rises from 71.84% to about 73.25%. This is a provisional
promotion for repeat-seed testing, not mid-ladder evidence. Require the
adaptation to repeat before using it as the parent of another RL phase.

Seed 1043302 repeats that adaptation before RL. On the same untouched 37-replay
holdout it reaches 5.6228 joint NLL, 42.84% action-type accuracy, and 18.42%
within two tiles, closely matching seed 1043301 at 5.5648, 43.33%, and 17.14%.
Its first 12 held-out-deck games also reproduce the first seed's 6-6 record and
+1 crown differential; eleven games have identical crowns and duration, while
the twelfth keeps the same outcome/crowns with a different duration. The
chronological adaptation is therefore repeatable enough to become the parent
of a bounded diversified league pilot. The repeat does not turn this evidence
into a human-skill claim.

The first diversified league configuration was aborted after two updates
because its rehearsal coefficient was mis-scaled: weighted rehearsal loss was
about 0.73 while the PPO policy term was about 0.001. No checkpoint from that
run is a candidate. The corrected pilot reduced rehearsal coefficient from 0.1
to 0.002, used one 16-step replay sequence per optimizer step, and retained a
0.1 rollout-state policy KL anchor. It completed ten updates / 40,960 decisions
across the 455-deck train split at roughly 103--108 decisions/s, with all 32
optimizer steps, near-zero clipping, and rollout KL below 0.0013.

Stable optimization again did not imply promotion. On the replay-disjoint
holdout, update 5 changed 25 deterministic actions, with six action-type
improvements and ten regressions; update 10 changed 76, with sixteen
improvements and twenty-nine regressions. Update 5 gained one two-tile success
without losing one, but its matched 12-game held-out screen stayed 6-6 while
crown differential regressed from the parent checkpoint's +1 to -2. Update 10
was already worse offline and did not receive gameplay budget. Reject and do
not extend this PPO lineage; the replay-adapted LR-1e-5 checkpoint remains the
parent.

The next clean data experiment uses every converted KataCR episode rather than
the old complete-episode sample. The old balanced corpus contains 9,504
supervised human plays in its selected 190 KataCR episodes; the full 347-game
conversion contains 17,331. The new fixed corpus combines all 347 KataCR games,
the same seven 30,000-frame simulator sources, and only the replay-disjoint TV
train split. After exact deduplication it contains 596,905 rows, 794 episodes,
68,826 non-forced supervised decisions, and 27,067 plays. The 37-replay TV
holdout remains absent. A from-scratch attention/LSTM/hybrid repeat isolates
this data expansion before any further RL.

The full-human from-scratch checkpoint is not promoted. Its untouched TV
holdout improves within-two-tile placement from the old attention control's
11.57% to 18.81%, but action-type accuracy falls from 26.21% to 24.51% and
joint NLL remains 10.0044. Five epochs of the safe chronological adaptation
recover only 32.40% type accuracy. Ten epochs create another likelihood false
positive: 4.5495 joint NLL and 42.84% type accuracy, but zero deterministic
placements within two tiles.

The isolated boundary at six adaptation epochs retains the useful tradeoff:
5.2107 joint NLL and 22.86% within two tiles, versus 5.5648 and 17.14% for the
promoted small-data adapted parent, but type accuracy is lower at 39.32% versus
43.33%. In matched 12-game held-out play it scores 6-6 with -1 crown, versus
the parent at 6-6 with +1 crown. It produces two outcome improvements and two
regressions, places more often (6.1% versus 5.8%), no-ops less when playable
(71.7% versus 75.9%), and defends slightly more often (6.2% versus 5.6%). This
is evidence that the extra Hog/Golem data improves spatial execution, but it
does not preserve enough general card/timing skill to become the parent.

The larger-window conclusion is that chronological play/wait adaptation is
the only repeated improvement in this ladder. Immediate PPO erodes it, while
adding more games from the same two KataCR archetypes trades action-type skill
for placement skill. The next data campaign must add genuinely broader decks
and replay identities under a replay-level provenance split. Do not extend the
failed PPO or full-human lineages merely because their losses are smooth.
