# TV Royale public-state HP extraction pilot (2026-08-13)

## Decision

Visible HP is recoverable cheaply enough to include in the next replay corpus.
The earlier corpus limitation was caused by the sparse importer, not by the
source video. The pilot is not yet broad enough to justify training: it covers
one replay, one arena skin, and normalized visible bar fill rather than a
formally labelled multi-arena accuracy set.

The next replay schema must carry a value and a confidence/missingness signal.
Low-confidence measurements must not be silently converted to full health.
Simulator observations used in the same training run must be degraded into the
same public/noisy domain so that imitation and RL do not train on incompatible
state semantics.

## Source and command

- Host: Apple M4 Pro Mac mini
- Replay: `arena_24/25848212-ea7a-48c9-bd4a-f1c27206396f`
- Source rows: 522
- Sample: 64 uniformly spaced frames
- Detector: the two pinned KataCR v0.7.13 weights already stored in the repo
- Detector device: MPS
- Shared-host condition: RoadForge was using approximately one CPU core during
  the run; no attempt was made to claim an uncontended detector maximum.

```bash
env PYTHONPATH=src:. uv run python scripts/perf/benchmark_tv_royale_public_state.py \
  --input-parquet datasets/external/tv_royale_raw_pilot/arena_24/25848212-ea7a-48c9-bd4a-f1c27206396f/frames.parquet \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --batch-size 16 --frames 64 --scan-repetitions 200 \
  --audit-samples 12 \
  --output-dir reports/tv_royale_public_state_hp_audit_arena24_25848212 \
  --report reports/tv_royale_public_state_hp_benchmark_arena24_25848212.json
```

## Measured result

- Detector: 7.641945 seconds, 8.374832 frames/second.
- Visible bar measurements: 332 total: 80 unit bars, 178 Princess Tower
  bars, and 74 King Tower bars.
- One-to-one body associations: 303.
- Health measurement plus body association: median 0.016729 seconds for all
  64 frames, or 3,825.72 frames/second.
- The health stage is therefore negligible next to object detection. The
  timing is conservative because the benchmark re-measures bars once for the
  standalone count and again during association.
- Health digest:
  `2fe43a576d00865465c2baa989d6eee8147787226dd59fb462ed9033a2779b79`.
- Associated-entity digest:
  `6e3311474c4bb19842f8200a9157ef361701a086d14beb89f89211fb189a398a`.
- JSON report SHA-256:
  `cd751cb04ffc7b10ec31c1a1289dc62712eb6e5898d0958c3d0ee0db676768e0`.

Associated classes included Baby Dragon, Bomber, Cannon, Dark Prince, Giant,
Giant Skeleton, Goblin Cage, Goblin Giant, Hog Rider, Ice Wizard, Mega Knight,
Royal Recruit, Skeleton, Skeleton Dragon, Spear Goblins, and both
tower kinds. Spell/effect detections were excluded through the data-derived
card taxonomy rather than card-name exceptions.

## Visual gate

All 12 audit frames were inspected at 2x nearest-neighbour scale. The overlays
draw the detected bar, its measured fraction/confidence, the matched body
centre, and a bar-to-body line.

The visual pass found two association/segmentation bugs and one expected
uncertainty case:

1. A Fireball detection could initially steal a nearby Giant's bar. The final
   matcher accepts only catalog-derived troop/building bodies; a focused test
   locks this down.
2. A bright effect-lit red troop bar was initially classified as empty. The
   team-colour mask now accepts the pale red appearance and has a focused
   regression test.
3. A blue Princess Tower at frame 181 was visibly near full (3796/4032) while
   a freeze/impact overlay interrupted the colour prefix and yielded a 0.48
   estimate with only 0.44 confidence. This is evidence for confidence-aware
   temporal fusion, not for broadening a colour threshold until it invents
   fill. Stable neighbouring frames recover the tower near full.

Manual, non-formal numeric spot checks were directionally correct in ordinary
lighting: 2995/4032 was measured near 0.71, 910/4032 near 0.20, 2345/4032 near
0.54, and 475/6408 near 0.07. These checks are visual evidence only; they are
not a labelled MAE benchmark.

## What video can and cannot provide

Recoverable public state includes visible unit/tower HP, shield state, visible
rage/slow/freeze/stun/stealth effects, deployment clocks, positions and
velocities, attack animation phase, public hand, own elixir, and battle time.
Some fields require temporal inference and should have lower confidence than a
direct UI read.

The video cannot reveal the opponent's hidden starting hand, unrevealed cards,
internal RNG, or exact engine-only sub-frame clocks. Those should be modelled
as belief/unknown state rather than fabricated labels.

## Acceptance gate for scale-up

Before importing the 1,000-game raw set into imitation training:

1. Freeze a versioned public-state schema containing feature values plus
   confidence/missingness.
2. Add fixed-identity tower tracking and generic entity re-identification so
   low-confidence frames can use temporal evidence without leaking future
   hidden state.
3. Build a labelled validation slice spanning multiple arenas, tower skins,
   teams, effect overlays, crowding, and damaged/empty bars.
4. Measure coverage and error by feature, not just detector throughput.
5. Generate matched simulator observations with the same omissions/noise.
6. Only then run a disjoint replay-imitation pilot and the existing held-out
   balanced/reactive/Hog/broad safety gates.

## Schema-v2 production smoke

The sparse raw-cascade extractor now writes `public_state_v2.npz` next to, and
without modifying, its legacy `corpus.npz`. The sidecar is row-aligned by source
index/frame and contains values plus confidence arrays for entity identity,
all 32 entity features, hand identity, all 18 actor globals, public history,
and seen-card identity. Missing values are zero with zero confidence; validation
rejects fabricated nonzero values under a missing mask.

An end-to-end run on the arena-24 replay produced:

- 23 aligned action/no-op samples;
- 163 visible enabled-scope entities after fail-closed unknown filtering;
- 108 entities with measured HP (66.26% coverage);
- 0.6929 mean confidence among measured entity HP values;
- 59 entities with causal motion direction (36.20% coverage), recovered from
  the immediately preceding frame without future-state leakage;
- 91 tower-HP measurements;
- exact source-frame alignment between v1 corpus and v2 sidecar;
- finite arrays with shapes `(23, 128, 32)` for values/confidences;
- sidecar SHA-256
  `c182e5f98cc9b1c1374bc631fb29720c9d4cdb89fe4b1dca5b58924f75f4a385`;
- 94 selected vision frames, including 32 causal predecessor frames;
- 21.04 seconds total local extraction excluding download, or 171.1 games/hour
  for this replay. The temporal enrichment remains above the 100-game/hour
  local target before source-download time.

## Second-arena validation

A second retained raw replay (`arena_29/d0417583-...`) was scanned with the
same frozen code and detector weights: 64 of 1,009 frames, 370 visible bars,
and 307 final body associations. HP scan/association remained negligible at
3,501.86 frames/second; detector throughput was 8.33 frames/second. The final
JSON SHA-256 is
`6617fbce3c85271f938b2ade898748210c282e2b9795849b9b71d408022c59c7`.

All 12 second-arena overlays were inspected at 2x scale. Ordinary tower checks
remained directionally consistent across level-15 towers and a different skin:
4123/4424 was measured around 0.91--0.93, 4258/4424 around 0.95, 3965/4424
around 0.87, and 733/4424 around 0.15. Crowd/effect cases for Cannon, Archer
Queen, Ice Spirit, Royal Hogs, and evolved troops kept their visible bars on
the correct supported bodies.

This second pass exposed an out-of-vocabulary `clone` effect that the legacy
converter would map to the generic unknown token and classify as a troop. V2
now fails closed on unknown detector identities; rerunning removed Clone,
Elite Barbarian, Fire Spirit, and Rascal Girl false/unsupported associations
without card-name exceptions. Supported evolution labels still normalize to
their enabled base identities. The health digest stayed unchanged while the
association digest changed to
`afd8cb1b99f8721a7e509a013870575e64723abbe8b1c24e332507e1da5b8f87`,
showing that only body assignment/filtering changed.

## Multi-arena coverage checkpoint

At 204 completed public-v2 replays, an independent sidecar scan covered 5,973
policy rows and 53,548 visible entity instances. Aggregate measured-HP coverage
was 56.02% and causal-motion coverage was 38.89%. Every confidence tensor was
finite and inside `[0, 1]`.

All 20 arenas had 9--11 completed games. Per-arena HP coverage stayed between
50.79% and 61.27%; motion coverage stayed between 33.82% and 43.73%. The lowest
HP arena still exceeded half of visible bodies, and neither the different arena
skins nor the arena-31 chronology partition showed a perception collapse. This
is a drift screen, not a substitute for the final 1,000-game digest verification
and eight-sheet visual audit.

## Matched simulator domain and policy integration

The simulator-side projector now produces the same schema-v2 values and
confidence arrays instead of training on privileged exact actor state. A
fixed-seed 512-row smoke from the diverse simulator teacher corpus produced
4,272 visible public bodies, 2,807 HP observations (65.71%), and 1,545 motion
observations (36.17%). The aligned sidecar SHA-256 is
`2d3f2647b58657d7963bccdd6af3f6f4951198d27b6ae3829deb9ab7884df41f`.
These rates prove the configured degradation profile is reproduced; they are
not yet a detector-recall calibration.

The policy has an opt-in confidence residual for entity identity/features,
hand identity, and actor globals. Legacy configurations allocate no new
parameters and retain their original strict state layout. When explicitly
upgraded, the twelve new projection tensors are the only permitted missing
checkpoint keys and their final layers initialize to zero. A regression test
loads a legacy checkpoint into the confidence-aware model and obtains
bit-identical policy logits and values before training, even with nonuniform
confidence inputs.

The imitation loader overlays the public sidecar without modifying the v1
corpus, verifies schema, shapes, sample counts, action/episode alignment,
finite confidence bounds, and carries confidence through packed entity
trimming and recurrent batches. The combined public-state, replay, extraction,
model, and imitation focused gate is 109 tests passing. This establishes a safe
training path; it does not yet establish a promotion-worthy policy.

## Full matched simulator sidecars

The smoke profile was expanded, without changing its frozen probabilities, to
four disjoint simulator-teacher splits:

| Split | Rows | Visible entities | HP coverage | Motion coverage | Sidecar SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| train | 56,271 | 581,407 | 66.14% | 36.04% | `895e3bec84fae2138200d60470dc54d097ebb83131e270eaa4c07c8202220ae1` |
| validation | 12,976 | 135,483 | 65.75% | 36.00% | `60f3b7f64c58be890fab4170d339698f937984206a29556a40d876db6f4829e6` |
| held-out archetype | 24,419 | 274,627 | 65.97% | 36.06% | `f8cb12b9395866f60c53e88c7a92090cfcf9db9139046398ec7f02d6763a42ce` |
| later chronology | 8,641 | 88,892 | 65.86% | 35.99% | `034e71d1de1be25055cf47206c81447065b1920a81eb5741c777eb22928133a1` |

These are public-domain projections of exact simulator observations. They do
not claim that the detector has those exact coverage rates on every arena; the
purpose is to train against the measured missingness regime rather than exact
state.

## Rejected direct imitation arms

Two one-epoch arms trained only the new confidence projections against human
action labels: unweighted seed 1055202 and card/action-type-balanced seed
1055203. Both learned the dominant no-op label rather than a useful uncertainty
adapter. On ordinary validation, the frozen control played on 14.00% of rows
and recalled 19.52% of human plays; the unweighted arm played on 0.18% and
recalled 0.20%, while the balanced arm played on 1.43% and recalled 1.88%.
The same collapse appeared on held-out archetypes and chronology. Aggregate
accuracy increased only because 86--88% of labels are no-op. Both arms were
rejected before gameplay.

## Exact-to-public policy distillation

The replacement objective freezes every legacy policy parameter and teaches
only the confidence projections to reproduce the frozen incumbent's exact-state
distribution from its degraded public observation. The first implementation
(seed 1055204) improved public-state KL but allowed learned confidence biases to
perturb fully exact simulator observations. It changed matched stochastic
gameplay from 9--3 to 8--4 against balanced and from 8--4 to 6--6 against
reactive-defense, so it was rejected.

The corrected architecture gates every confidence residual by field
uncertainty. When all confidences are 1.0, the residual is mathematically zero
regardless of learned weights or biases. Seed 1055205 retained the public-state
improvement:

| Evaluation | Control joint KL | Gated adapter joint KL | Control agreement | Adapter agreement | Teacher / adapter play rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| internal validation | 0.012813 | 0.008315 | 97.57% | 97.99% | 15.69% / 15.88% |
| disjoint validation | 0.011499 | 0.007328 | 97.64% | 97.86% | 13.97% / 13.63% |
| held-out archetype | 0.016847 | 0.010369 | 96.10% | 96.54% | 20.92% / 21.10% |
| later chronology | 0.025931 | 0.013395 | 93.73% | 95.27% | 26.31% / 25.86% |

The exact-state gate replayed all 12 stochastic balanced games at seed 1051402.
The incumbent and gated adapter game-record JSON files are byte-identical with
SHA-256
`c92c12d4cd3590b058ffe741b3f7af20bf5a09de1f351fbb232f9d1cf3824ff1`:
both score 9--3 with +0.4167 crowns/game, 0.9151 overall no-op rate, and
0.7381 no-op-when-playable. This proves the adapter preserves the incumbent in
the exact simulator domain while reducing the measured public-domain mismatch.
It does not yet prove that adding noisy human labels improves playing strength.

## Thousand-game production collection

The versioned raw-cascade collector is running toward 1,000 retained games at
`datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201`. Each game
must independently pass corpus/public-sidecar provenance, schema, row, action,
frame, and digest validation before it counts. At the latest report snapshot it
had completed 35 games with zero failures at 98.55 observed games/hour. The
collector remains live; final corpus statistics and a multi-arena visual audit
are required before human-label training.

## Frozen 38-game public-state snapshot and card-choice pilots

A validated prefix was frozen without interrupting the production collector.
The 38-game snapshot contains 1,088 aligned decisions and 10,072 visible entity
observations. Visible HP was measured for 5,658 entities (56.18%) and causal
motion for 3,899 (38.71%); missing measurements retain zero confidence rather
than fabricated values. The corpus SHA-256 is
`a19bc33bde6598101829e209647807e9ec7e4c4a05dcad1d27f0279144ca74a6`
and the public-state sidecar SHA-256 is
`7e02a2c52b60d033d986785f52a06bf1467f49fae8c67ceeb2659778609d6fb4`.

Two timing-safe residual card-choice heads were rejected. A global four-slot
head and a first card-semantic residual both reduced conditional NLL while
worsening held-out top-1 slot accuracy. The semantic residual fell from 19.32%
to 15.46% on 207 held-out placements and made nine full-corpus action-type
regressions while fixing five. These results close the residual-on-legacy-slot
formulation rather than motivate an epoch or coefficient sweep.

A replacement semantic scorer was then required to reconstruct the incumbent's
conditional card choice before seeing human labels. It scores each current hand
card from the frozen learned identity plus data-derived mechanics embedding and
renormalizes only the four legal placement slots. Total placement probability,
wait/ability logits, and placement geometry remain unchanged by construction.
The collector was extended so the vocabulary path can remain fixed while a
separate procedural deck pool supplies episodes.

The fixed curriculum contains 455 training decks, 82 disjoint validation decks,
and 151 whole-archetype holdouts (Graveyard, Lava Hound, Royal Hogs, and X-Bow).
From 100,000/30,000/30,000 dense decisions, the incumbent produced
1,752/446/650 placement labels. A single five-epoch semantic fit reached 77.60%
internal held-out slot accuracy, 83.86% on the separate validation decks, and
83.85% on the unseen archetypes. Play/wait recall remained exactly 1.0 because
the head cannot alter timing. This proves transferable semantic structure but
still leaves too much disagreement for direct gameplay replacement.

Transplanting that scorer into the accepted confidence-aware policy improved
zero-shot human slot accuracy on all 788 snapshot placements from 11.17% to
12.82%, with 29 corrected action types versus 16 regressions and exactly
unchanged play timing. Fine-tuning on the small human prefix was nevertheless
rejected: held-out slot accuracy fell from 28.50% to 27.05%, despite improved
cross-entropy. The simulator-pretrained semantic prior is retained as an
experimental initialization; no human-tuned checkpoint is promoted before the
full corpus is available.

## Live collector schema restart

At 73 accepted games, the long-lived parent still held the pre-extension
`CorpusMetadata` class while new extractor subprocesses emitted the new optional
`sampling_decks_path` field. Extraction succeeded, but the stale parent rejected
26 post-extraction records. The parent was stopped and restarted so it loaded
the backward-compatible schema. Accepted games were preserved, failed records
remain excluded, and the restarted process immediately advanced to 75 accepted
games with no new schema failures. The 1,100-attempt ceiling still permits the
target of 1,000 independently validated accepted games.

## Mechanics-only card transfer and duration-weighted timing audit

The learned-identity semantic scorer was not the simplest successful card
representation. A separate frozen-feature probe removed card identity entirely
and scored each legal hand slot from only 16 normalized, data-derived card
mechanics. The linear v1 scorer was repeated at seeds 1055410--1055412. Mean
conditional slot agreement was 86.77% on disjoint procedural validation decks
(0.39 percentage-point sample standard deviation), 84.36% on whole held-out
archetypes (1.13 points), and 49.41% on public human placements (0.94 points),
versus 45.05% for the incumbent on the same conditional human metric. This is
direct evidence that Giant/Royal-Giant-like mechanical similarity transfers
without an identity lookup. A richer v3 descriptor and a 64-wide MLP produced
no justified trade: v3 lowered all three transfer metrics, while the MLP's tiny
simulator gain came with human NLL 2.086 versus 1.292 for the linear probe.

Five-epoch human fine-tuning on the 38-game prefix was not repeatable across the
three simulator-pretrained seeds: one arm changed validation accuracy by one
example, one selected the unchanged epoch-zero model, and one preserved top-1
while trading away simulator margins. Human fine-tuning is therefore rejected
at this sample size. The mechanics-only linear prior is retained for the final
corpus, but remains an offline probe rather than a gameplay promotion.

The corpus's raw 788-play/300-no-op ratio is intentionally case-controlled and
must not be read as a 72.43% human play rate. The new duration audit uses each
replay manifest's actual frame count, a 10 Hz source clock, and the live 4 Hz
policy clock. Across 38 games it estimates 13,283 decision opportunities and a
5.93% human play rate. Eleven games retained no valid no-op at all and are
excluded from checkpoint calibration rather than assigned fabricated states;
the remaining 27 games represent 9,702 effective decisions and a 6.71% play
rate. Each accepted no-op carries a replay-local importance weight ranging from
10.88 to 547.0 (median 43.44).

Under those weights the accepted public checkpoint deterministically plays on
11.52% of decisions, recalls only 26.88% of human play moments, recalls 89.58%
of no-ops, and assigns mean play probability 36.52%. The semantic-card control
has identical timing by construction. This shows genuine timing
miscalibration, but the extreme weight variance plus the 11 no-op-empty games
make this prefix unsuitable for another direct timing-head fit. Previous
visual/native timing adapters already demonstrated that improved offline timing
can reduce complete-game strength. The next full-corpus experiment therefore
keeps deploy/wait timing frozen and evaluates the mechanics-only conditional
card scorer first; timing remains an outcome-grounded league-RL responsibility
unless the final corpus supplies materially stronger coverage.

The authoritative audit is
`reports/tv_royale_snapshot38_duration_weighted_timing_seed1055501.json`,
SHA-256
`09cf6c9716597d7d02b2e620e8f443baa7d5a988845556ce0e93aa4ed7cf2ac8`.
The reusable driver is `scripts/audit_tv_royale_action_timing.py`; focused
tests cover dense-rate restoration and the exclusion of episodes with no
representative no-op. At the latest collection check the production run had
108 accepted games, 26 preserved fail-closed records, and 134 attempts at
96.37 accepted games/hour.

## First 112-game multi-arena visual gate

The next live prefix contains 112 accepted manifests and all 20 requested
arenas (12 through 31), with four to six games per arena. It contains 3,065
retained public decisions and 844 accepted no-op observations; 29 games have no
accepted no-op and remain unsuitable for duration-weighted timing calibration.
Across games, mean visible entity-HP coverage is 57.35% (median 57.39%, range
39.13--85.00%) and mean causal-motion coverage is 39.92% (median 41.11%, range
15.00--64.29%). Per-arena mean HP coverage ranges from 50.45% to 68.35%; there
is no arena-specific detector collapse in this prefix.

One early and one late audit frame from every arena were assembled and visually
inspected at full contact-sheet scale. The 18-by-32 overlay remains registered
to the arena and river across all skins; team-colored bodies and health bars are
aligned in both sparse and crowded frames. The yellow detector rectangles are
explicitly sprite/cross-clock/area centers, not simulator hitboxes, so a tower's
large rendered rectangle is not interpreted as a 4-by-3 collision footprint.
The reviewed artifacts are
`reports/tv_royale_public_v2_first112_arena_contact_sheet.jpg` (SHA-256
`f75fca32575860f9018835654950ea871304b3c088c926111806616b32123572`)
and `reports/tv_royale_public_v2_first112_arena_contact_sheet_late.jpg`
(SHA-256
`16d025f70a0da8d305d76914a68186ca47eba81b89065637fb967196aa5c480b`).
This is an early perception gate, not the final 1,000-game audit.

## Conservative mechanics-logit blend rejection

A normalized geometric mixture tested whether the mechanics-only scorer could
improve human card choice without wholesale replacement. The sweep used all
three simulator seeds, alpha spacing 0.005, a maximum 1% conditional-slot
disagreement on both disjoint validation decks and whole held-out archetypes,
and a minimum one-percentage-point human accuracy gain. Timing and placement
geometry are absent from this experiment and therefore invariant.

No alpha passed. The best point inside the simulator disagreement budget was
alpha 0.005; it flipped one of 788 human examples, yielding only 0.127 points
and no simulator changes. The first point meeting the human-gain floor was
alpha 0.215. Across seeds it changed 5.20--5.58% of human slot predictions for
19--21 fixes and 11--12 regressions, while regressing 1.35--1.79% of disjoint
validation choices and 1.38--1.85% of whole-archetype choices. That trade is too
large for the small net human signal, so no blended policy checkpoint was
created. The authoritative sweep is
`reports/mechanics_slot_blend_sweep_fine_snapshot38_seed1055502.json`, SHA-256
`ea751c06501f95a45d563c1caa2a435ae9dfaddc25e934558a54c07b63e5337a`.
The blend remains eligible for a fresh gate only after the final human corpus
can demonstrate a materially larger and statistically stable benefit.

## 120-game checkpoint: signal persists, adaptation still rejected

A collector-safe snapshot at 120 accepted games contains 3,365 aligned rows,
2,443 human placements, 922 sampled no-ops, and all 120 episode boundaries.
Its corpus SHA-256 is
`04b073e43d463d10d2783214a273407f54eabe9d3b3a9db15243f5b34e53a424`;
the aligned public-state-v2 sidecar SHA-256 is
`8f13ef617680e8e273772198f74454868cb2f7f5a942ecfdbab512b3b2dae3b0`.
Visible-entity HP coverage is 56.81% and causal-motion coverage is 39.49%,
consistent with the earlier multi-arena prefix rather than evidence of
perception drift.

The mechanics-only signal also persists zero-shot. The incumbent conditional
slot accuracy is 45.56%; the three independently pretrained linear scorers
reach 46.62%, 48.59%, and 47.69% without seeing these games. However, the
conservative blend remains unsafe. At alpha 0.10 every simulator guard stays
within 1%, but the human gain is below one point for at least one seed. The
first alpha giving every seed at least one point, 0.21, changes 1.35--1.79% of
disjoint simulator validation choices and 1.38--1.69% of held-out-archetype
choices. The authoritative sweep is
`reports/mechanics_slot_blend_sweep_snapshot120_seed1055602.json` (SHA-256
`73974175648769e6a0adabb7e3f7cb3bfba949330b6f02dacb847f06245d5407`).

A corrected fine-tune selector evaluated both simulator guards at every epoch
and required a full one-point gain on the 500-placement replay-disjoint human
validation split. Selected safe epochs improved human validation by 0.8, 0.2,
and 1.8 points across the three source seeds; full-snapshot gains were only
0.08, 0.12, and 0.45 points. Only the third seed passed individually. The
cross-seed gate therefore rejects human fine-tuning at 120 games and forbids
cherry-picking that arm. Reports and SHA-256 values are:

- seed 1055410: `43b42ac625925c6f5f1368826f05e35e907a3c49db79cfcfe27d54112fd4a897`;
- seed 1055411: `a6f1fea76e6768494bc9ea4208124212541a86c194ddb720bf3e1c145b104ea8`;
- seed 1055412: `e01b8e3ea227f73bce6d2db41cd49f36d53feb0661f1516fc33fd956ca80cc5f`.

Duration weighting estimates 43,106 policy decisions and a 5.67% natural play
rate. Only 89/120 games have a retained representative no-op; their calibrated
target is 6.28%. The frozen public checkpoint plays deterministically on
10.73%, with 21.65% play recall and 90.01% no-op recall. This confirms that the
timing finding is stable but does not repair the missing-noop bias. The timing
report is `reports/tv_royale_snapshot120_duration_weighted_timing_seed1055603.json`
(SHA-256
`1b51285b1bd359d0a84469c31a8e6c585024eca3e0775cb8b345207d4e1c25c9`).
No 120-game probe is integrated into the policy; the production collector and
the final 1,000-game disjoint gate remain authoritative.

## Replay-disjoint public-state split dry run

The final training path now independently verifies every per-game
public-state-v2 digest, schema, shape, confidence bound, zero-missing contract,
padding contract, and action/frame provenance, then repeats those checks on the
combined sidecar. A 120-game dry run mirrored the existing replay-, deck-,
archetype-, and chronology-disjoint action split into exactly aligned public
sidecars. It retained 1,994 complete-visible-hand decisions from 91 replays:
1,052 train, 313 validation, 521 held-out archetype, and 108 later chronology.
Replay overlap is zero. HP coverage is 56.71%, 59.95%, 57.55%, and 57.63% in
those four splits; motion coverage is 37.98%, 38.83%, 38.65%, and 43.20%.

The stricter external validation invalidated the optimistic internal split
signal. Fine-tuning each of the three simulator-pretrained mechanics scorers on
the 55-replay training split produced **zero** top-1 gain on the separate
13-replay, deck-disjoint human validation split. Selected epochs were 3, 0,
and 1; all three promotion decisions are false. Their reports have SHA-256
values
`71a5daeef571fe3b03904d8ac0872994f5bfd7326cb0e3bf105abcc57201a31b`,
`70bb7294b3fccd1c9b146392de43a8b1e3f9e87119decc15f023a73997b66604`,
and
`6e940404802a96109f00dd27b086ea5a500583a3a9cb34c33f07af40308a0bf6`.
This is the authoritative 120-game adaptation result: zero-shot mechanics
transfer remains real, but 120 games are insufficient for human fine-tuning.

The visual gate was also widened from one early/late record per arena to four
collection quantiles times early/late across all 20 arenas: 160 retained audit
frames at collector checkpoint 151. All eight sheets were visually inspected.
Grid/river alignment, tower registration, team ownership, HP bars, and crowded
effect-heavy overtime scenes remained coherent with no chronological or arena
collapse. The sheet manifest is
`reports/tv_royale_public_v2_checkpoint151_contact_sheets/manifest.json`; it
contains the SHA-256 and exact replay provenance of every source and output.
This checkpoint does not replace the final 1,000-game visual audit.
