# Hog 2.6 win-condition utilization gate

The paired win/loss promotion gate is necessary but does not prove that a repaired
policy uses its deck's win condition. This independent gate is frozen before the
phase-balanced ranker results exist. It consumes the same paired gameplay JSON
reports and requires `HogRider` to be used in at least 75% of repaired games,
at least 50% of games against every strategy, and at least once per game on
average. At least four ranker overrides must select Hog Rider, across at least
two placement tiles, with no tile exceeding 75% of those overrides.

The card is a CLI/configured policy objective, not a simulator card-name branch.
Failure rejects promotion even if aggregate crowns or win rate pass. Passing does
not prove placement quality or human-level play; recorded gameplay still needs
the existing paired screen, quarantine, and visual/behavioral review.
