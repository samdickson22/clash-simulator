# Hog 2.6 phase-balanced deck holdout audit

The ranker corpus and gameplay gates use three distinct generalization levels.

## Composition-held-out validation

- Train authority SHA-256: `005a47d3c191d5c554d3804304a80fe8f178d0a864ec680b28ee2c8709c79da2`
- Validation authority SHA-256: `76f8932aa66b13db451bf1023a91432c423aa13eebb3f1b09430e059d3637468`
- Train decks: 1,720; validation decks: 312
- Exact card-set signature overlap: 0
- Deck-name overlap: 0
- Both cover the same eight training archetypes and 32 parent families.
- Both cover 62 cards and intentionally exclude `Graveyard`, `LavaHound`,
  `RoyalHogs`, and `Xbow`.

This validation split tests unseen deck compositions inside known archetypes. It
is game-disjoint again inside the fitter for selection, calibration, and final
holdout. It must not be described as archetype-held-out evidence.

## Archetype-held-out gameplay

- Screen SHA-256: `ecbc18a6df9855eba9ca526eb44dd762a2511d00bf2198faeb6851a27c76049d`
- Quarantine SHA-256: `5590b43390b8097049d067b0a5dd462d6d2471b0fa3759e7fce298ed00e71c2c`
- Screen decks: 195; quarantine decks: 385
- Archetypes: Graveyard, Lava Hound, Royal Hogs, and X-Bow only
- Archetype overlap with train/validation: 0
- Exact deck/name overlap with train/validation: 0
- Exact deck/name overlap between screen and quarantine: 0

The screen and quarantine share the four held-out archetype labels but use
disjoint deck compositions. Together they are the current archetype-held-out
free-running evidence. They still do not prove broad learner-deck competence or
mid-ladder human skill; this staged lineage deliberately keeps the learner on
Hog 2.6 until competent play is established.
