# Expanded card-balanced deck curriculum (2026-08-13)

## Decision

Use the expanded pool only for future diversified league training. Keep the
existing v2 validation and whole-archetype held-out pools frozen for every
comparison so the larger curriculum cannot move the goalposts.

## Generation and separation

`scripts/generate_deck_curriculum.py` generated 2,652 unique structurally valid
decks from the 33 project decks plus eight compatible public common decks. Each
variant preserves its inferred archetype, contains eight unique enabled cards,
has a valid elixir range, a win condition, a spell, at least two air answers,
and at least three troops/champions. Sixty-four variants per seed deck and a
12-card semantic neighbor pool produced:

- 1,758 initial training decks across eight training archetypes;
- 312 new same-archetype validation decks;
- 582 new whole-archetype held-out decks;
- source report SHA-256
  `9884cc19920ef6ca05c271e56c093e5925f54ce130f80cea5918fe1e849ec344`.

Before training, exact signatures from the original frozen v2 validation and
held-out pools were removed. This excluded 38 collisions and retained 1,720
training decks with zero overlap against all 82 v2 validation decks and all
151 v2 whole-archetype held-out decks. The strict pool SHA-256 is
`c6e14eefb543f8db630537723a3baebffa88b3b24442b39158f4dfbc53e1b5e1`.
The four deliberately unseen win conditions remain `Graveyard`, `LavaHound`,
`RoyalHogs`, and `Xbow`; the training pool covers the other 62 cards.

## Bounded card-exposure balancing

The original archetype-balanced sampler still overrepresented ubiquitous
cards. A deterministic bounded multiplicative transform now changes only
sampling weights, never deck membership. It preserves exactly one-eighth total
mass for every training archetype and limits every deck to `[0.1x, 10x]` its
prior probability. Two thousand fixed iterations at learning rate `0.03`
changed weighted card exposure as follows:

| Metric | Before | After |
|---|---:|---:|
| Minimum card inclusion probability | 0.01675 | 0.05306 |
| Maximum card inclusion probability | 0.39385 | 0.30930 |
| Maximum/minimum ratio | 23.51x | 5.83x |
| Coefficient of variation | 0.6388 | 0.3409 |

The transformed pool SHA-256 is
`005a47d3c191d5c554d3804304a80fe8f178d0a864ec680b28ee2c8709c79da2`.
The full per-card frequencies and exact source/output binding are in
`datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.report.json`.
The implementation, signature-exclusion utility, curriculum generator, and
weighted sampler pass 15 focused tests; Ruff and mypy are clean.

PFSP opponent weighting uses a separate 308-deck tuning pool. Four exact
signatures overlapping the frozen v2 evaluation pools were removed from its
312-deck source, leaving zero overlap; SHA-256 is
`80984dd166904fdef0421867a21cdf72363bb41aa3ea46f447b04372da164b27`.
This prevents even opponent-allocation weights from indirectly selecting on a
frozen promotion deck.

This improves exposure diversity but is not evidence of policy strength. It is
an input to the bounded PFSP pilot after the final mechanics candidate passes
its offline and complete-game gates.
