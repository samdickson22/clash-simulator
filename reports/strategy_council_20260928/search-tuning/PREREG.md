# Search tuning confirmation preregistration

Frozen UTC 2026-10-04T17:18:00.392842+00:00, before any confirmation game.
Winner: {"horizon": 160, "interval": 10, "k": 1, "name": "mixture", "opponent": "mixture", "policy_top": 8, "script_top": 4, "terminal": 2.0, "tower_weight": 0.0}
Current: {"horizon": 160, "interval": 10, "k": 1, "name": "current", "opponent": "sb-balanced", "policy_top": 8, "script_top": 4, "terminal": 2.0, "tower_weight": 0.0}
Experiment manifest SHA256: 76d695b3590f45347303f210f65f354b97e249a970f3b2863201dab744880bbf
Checkpoint SHA256: e6bc82c4d357ee6b17a3c266b221b2786494a2752880616101f2fc1340c980a3
Confirmation schedule SHA256: 06c46146796abb995c3c715638cb00ff8e925ef1b324a34568a09af377001e6d

The 256 H2H games use seed 1753000003 plus pair index times 1009, paired world decks and swapped controllers. There are 86 Hog26 games and 170 holdout games. Score is win 1, draw .5, loss 0. Primary PASS requires score >= .55 and lower 95% matchup-cluster bootstrap bound > .50. Bootstrap uses copied statistics.boot, 10,000 resamples and seed 20261001, retaining both seats. No optional stopping, outcome exclusions, retuning or second confirmation attempt.

Secondary winner/current script comparisons use identical seeds/decks, each 128 holdout games across balanced/pressure/defense 44/42/42 and each 64 Hog26 games across 22/22/20. Report every style and role. A pooled role drop greater than .05 blocks recommendation. Head-to-head statistical pass is reported separately from secondary and latency gates. Any candidate wall decision > .25 seconds blocks one-core deployment recommendation. Warmup precedes every worker's games, with recurrence reset for every game. Report full p99/max and concurrent load; remeasure the winner without concurrent tuning workers. Four-thread results are descriptive only.

All 640 games and complete pairs must be present for a final verdict. Source/data/native/checkpoint pins are verified for every receipt. Unexpected failures retain their artifacts and block completion. Seed audit precedes all experiments; confirmation seeds are disjoint from tournament and probe seeds. No confirmation outcome has been observed at registration.

Reporting-only amendment: all public-legal simultaneous-placement rejections are counted and all game outcomes retained. Zero rejected commands is not an acceptance gate. Exact replay diagnosis is in rejected-play-diagnosis.json. Frozen evaluation sources and game receipts are unchanged.
Reporting adapter SHA256: dff28ea9ef55e82e0828ada501a22fe98ac2018d172fbfc6b75c33efd0e99d0a
