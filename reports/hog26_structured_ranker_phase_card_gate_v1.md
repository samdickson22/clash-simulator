# Hog 2.6 structured ranker phase/card gate

The frozen three-seed ranker finalizer measures aggregate held-out accuracy,
terminal-outcome pair accuracy, optimal-action rate, clustered confidence bounds,
and zero thresholded regressions. This independent audit is frozen before fit
results exist to prevent an aggregate pass from hiding a phase collapse or a
failure to learn the deck's win-condition corrections.

For the selected seed, the audit reloads the exact checkpoint and validation
corpus, uses only the game-disjoint holdout partition, recomputes thresholded
candidate selection, and reports early, mid, late-regulation, and overtime
metrics separately. Every phase requires at least 15 roots, 35% exact-optimal
action selection, 35% safe-improvement recall, and zero terminal regressions.
At least ten holdout roots must have Hog Rider as the terminal-optimal card, and
the selected candidate must also be Hog Rider on at least 35% of those roots.

Passing is necessary, not sufficient. It cannot replace paired free-running
gameplay, the 48/96-game safety gates, win-condition utilization/placement
checks, or human-level evidence.
