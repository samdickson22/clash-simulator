# Zero-mechanics PFSP parent selection (2026-08-14)

## Decision

Use the 6,194,196-parameter human-imitation plus safety policy only as the
parent of a bounded mechanics-query repair pilot. Do not promote it as the
champion, and do not use either the 522,068-parameter compact policy or the
1,285,428-parameter update-28 policy as the PFSP parent.

The selected parent is
`checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt`
(SHA-256
`cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305`).
Its zero-initialized mechanics query is exactly behavior-preserving relative to
`checkpoints/human_safety_tvclock_timing_expanded_seed1032008/epoch1.pt`:
all 184 inherited tensors are unchanged, every candidate-only output is zero or
bitwise redundant, and all policy outputs, recurrent states, and 713
deterministic actions match. The equivalence evidence is
`reports/accepted6m_zero_mechanics_rl_initializer_seed1056701/exact_equivalence.json`
(SHA-256
`269352338fbbf6d3784eb370e2a9d8583addda9d6077bc811f361d240b5c8c5f`).

## Matched 72-game screen

Every row below uses the same seeds, mirrored seats, decks, strategy opponents,
reward profile, and evaluator. The aggregate comprises 12 random, 12 balanced,
12 reactive-defense, 6 bridge-pressure, 6 slow-push, 6 spell-control, 6
split-lane, and 12 Hog-deck balanced games.

| Exact zero adapter | Parameters | W-L | Crown diff | Playable no-op | Worst workload | Hog W-L | Hog zero-use games | Hog window conversion | Mean Hog probability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Compact public parent | 522,068 | 15-57 | -123 | 96.98% | 99.88% | 3-9 | 7/12 | 50.00% | 23.52% |
| Update-28 human/broad league | 1,285,428 | 29-43 | -9 | 0.08% | 0.98% | 2-10 | 8/12 | 100.00% | 45.97% |
| Accepted human+safety parent | 6,194,196 | 51-21 | +78 | 67.75% | 77.00% | 10-2 | 3/12 | 69.23% | 67.32% |

The 6.17M parent workload record is random 10-2, balanced 6-6,
reactive-defense 5-7, bridge-pressure 5-1, slow-push 6-0, spell-control 5-1,
split-lane 4-2, and Hog 10-2. Its waiting rate is high but not frozen: it acts
when doing so wins, and no workload exceeds the predeclared frozen-policy
boundary. The compact parent is instead almost completely inert. Update 28
eliminates passivity but loses 43/72 games and therefore cannot be selected on
activity alone.

## Gate interpretation

`reports/parent_selection_seed1056503/compact_vs_accepted6m_v3.json` records
`targeted_repair_pilot_authorized`, not `challenger_selected`. The broad gates
pass: matched protocol, winning aggregate, at least 12 wins beyond the compact
incumbent, random robustness, meaningful passivity reduction, and no frozen
workload. The absolute Hog-utilization gates fail because three games contain
no Hog use and promotion allows at most one.

That failure is narrow enough for a repair experiment because the model still
wins 10/12 Hog games, converts 69.23% of affordable Hog windows, and assigns
Hog 67.32% mean conditional probability. This is evidence of a targetable card
selection defect, not permission to relax the promotion threshold. The pilot
must reduce zero-use games to at most one while preserving the full parent
matrix.

Decision-level inspection confirms that diagnosis. The three zero-use games
contained 8, 2, and 2 legal affordable Hog decisions respectively; the policy
selected another hand slot on all 12. The first game still won, but the latter
two lost. Hog's slot-conditioned record is especially revealing: 0/23 plays
when legal and affordable in slot 0, versus 18/20 in slot 1, 4/4 in slot 2, and
32/32 in slot 3. This is not an unlucky draw or a lack of affordable windows;
it is a card-choice/slot-score defect that the shared mechanics query can
causally address while timing and geometry remain frozen. The descendant gate
therefore also requires at least two affordable observations, at least one
play, and at least 25% conversion independently in every hand slot. Aggregate
Hog use cannot hide an intact slot-0 failure. The bound decision/game hashes
and exact missed-choice table are recorded in
`reports/accepted6m_hog_slot_diagnosis_20260814.md`.

The finalizer no longer trusts the derived utilization JSON merely because it
names SHA-matching decision and game files. It reloads those arrays, recomputes
all per-game, per-seat, per-card, per-slot, probability, window, and promotion
metrics with the production analyzer, and requires exact equality. A deliberate
edited conversion rate is rejected. Recomputing the real parent evidence yields
12 games, 54 Hog plays, and three zero-use games exactly.

Hog is no longer the only predeclared utilization probe. A frozen 12-archetype
matrix selects one source deck and one explicitly designated win condition from
each validation or whole-archetype holdout family: Balloon, Battle Ram, Giant,
Golem, Hog Rider, Goblin Barrel, Miner, Wall Breakers, Graveyard, Lava Hound,
Royal Hogs, and X-Bow. This includes building targeters, spawn spells, siege,
air pressure, and unrestricted-deployment pressure rather than forcing every
card through the Hog semantic rule. The matrix manifest is
`datasets/win_condition_utilization_v1/manifest.json` (SHA-256
`171601791f57f0d21cc443ded12d61a40e0d288252115eea4eafb1343e06e8ae`);
all 12 single-deck pools load through the production deck loader and contain
eight unique enabled cards. The production PFSP launcher now evaluates both the
parent and candidate for two mirrored games on every singleton deck and records
raw decisions, utilization, and matched game comparisons. The finalizer
re-derives every selected deck from the SHA-bound validation or held-out source
pool, recomputes utilization from raw records, and requires exact use plus
outcome, zero-use, conversion, and conditional-probability preservation in
every archetype independently. One pooled average cannot hide a collapsed win
condition or an easier substituted deck.

## Predeclared pilot

The launcher is `scripts/run_zero_mechanics_diversified_pfsp_pilot.sh`. It is
fail-closed until all 1,000 replay extractions complete, the untouched post-260
human splits exist, and a human has visually accepted all eight SHA-bound final
contact sheets.

The post-260 marker is not count-only. Its verifier proves that the reserved
IDs are exactly the first 260 successful extractions in manifest chronology,
that the four partitions contain each of games 261--1000 exactly once and none
of games 1--260, that the source manifest bytes are unchanged, and that replay,
deck-signature, and held-out-archetype overlap invariants remain zero.

The visual approval is also bound to evidence, not merely to eight output
filenames. The final contact manifest binds the exact 1,000-game run-manifest
bytes, all eight phase/quantile sheets, and all 160 arena-ordered source frames
by SHA-256. The launcher independently verifies those bindings and requires the
human audit to name exactly those eight outputs. The existing 378-game visual
audit is therefore only an extractor health check and cannot satisfy the final
pilot gate.

The pilot runs only updates 20 through 24 (16,384 rollout decisions). It trains
`mechanics_slot_choice_query`, `critic_encoder`, and `value_head`; the
action-type/timing head and all placement geometry remain frozen. Thus the
first causal experiment changes which legal hand card is selected without
changing when or where the parent acts. Training uses the 1,720-deck balanced
strict-holdout pool, eight PFSP strategy workers, random, two frozen parent
workers, update 40, rollout KL, and simulator-native recurrent rehearsal.

Promotion remains stricter than pilot authorization. The descendant must beat
the parent directly on aggregate while remaining non-losing separately on both
the validation and whole-archetype holdout pools. It must preserve every
matched outcome/crown/strategy/passivity gate, including every individual
strategy opponent rather than only their mean or worst score; gain at least two
points of defense-event success; pass the absolute Hog utilization threshold
and the independent 12-archetype win-condition matrix; and show no net
regression on the untouched post-260 validation,
held-out-archetype, or chronology split. Evaluation metadata binds the exact
checkpoint and deck-pool bytes, and every matched comparison binds both input
game-record files by SHA-256 and validates its counts and crown arithmetic. A
candidate also cannot hide increased passivity outside the two defense screens:
playable no-op is bounded independently in all eight matched workloads. A pass
creates only an expanded-evaluation development candidate, never a mid-ladder-
human claim.
