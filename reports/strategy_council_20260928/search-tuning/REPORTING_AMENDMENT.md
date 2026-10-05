# Reporting-only amendment

Before any stage ranking or confirmation game, deterministic replay found one legal simultaneous Cannon placement conflict at tick 5650. Both commands were legal in the pre-action public and engine masks; seat 0 placed first and blocked seat 1. The replay reproduced exact world decks, outcome, ticks and failure counts. All 118 completed v2 games are retained.

The requested gates do not require zero rejected commands. resume.py replaces only the extra zero-rejection reporting assertion with explicit rejection counting. The frozen evaluator, planner, runtime, candidate slate, game seeds, scores, selection rules and confirmation thresholds are unchanged. The original manifest remains intact and still binds every evaluation receipt. reporting-manifest.json separately hashes the reporting adapter and replay diagnosis. Confirmation will bind the reporting adapter hash before its first game. No v2 outcomes are discarded or restarted.
