# Search tuning results

Primary confirmation: **PASS**. Secondary no-drop checks: **PASS**.

The selected profile is the equal mixture of balanced, pressure and defense public-script opponent models. It uses one sampled hidden completion, one rollout per style per candidate, and averages their scores.

Configuration: K=1; horizon 160 ticks; rollout interval 10; policy top-8 plus script top-4, script choice and no-op; balanced public-script own continuation; defense-v2 plus elixir; terminal +2 / -2, draw 0. Prewarm policy inference and reset recurrence for each game.

This is the best of 14 predeclared profiles, not an exhaustive search over interactions. Policy continuations were not implemented: the typical inference-only estimate exceeded 250 ms, and no validated native-to-policy observation adapter was available.

## Tournament

| Stage | Profile | Score | Hog26 score | Search core-s | Wall p99, s | Wall max, s | Overruns |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | mixture | 32/48 = 0.6667 | 13/16 | 0.04500 | 0.06492 | 0.13408 | 0 |
| 1 | h320 | 32/48 = 0.6667 | 12/16 | 0.03348 | 0.04562 | 0.10455 | 0 |
| 1 | h160-i20 | 30/48 = 0.6250 | 9/16 | 0.02088 | 0.02910 | 0.07476 | 0 |
| 1 | k2 | 27/48 = 0.5625 | 11/16 | 0.03465 | 0.04944 | 0.11213 | 0 |
| 1 | policy16 | 25/48 = 0.5208 | 8/16 | 0.02926 | 0.04062 | 0.09668 | 0 |
| 1 | terminal4 | 24/48 = 0.5000 | 8/16 | 0.02075 | 0.02862 | 0.12780 | 0 |
| 1 | h600-i10 | 24/48 = 0.5000 | 5/16 | 0.05345 | 0.07477 | 0.11789 | 0 |
| 1 | h320-i20 | 23/48 = 0.4792 | 7/16 | 0.03211 | 0.04458 | 0.09834 | 0 |
| 1 | wide | 23/48 = 0.4792 | 5/16 | 0.03222 | 0.04422 | 0.11195 | 0 |
| 1 | h320-tower | 22/48 = 0.4583 | 7/16 | 0.03192 | 0.04420 | 0.10679 | 0 |
| 1 | k4-i20 | 22/48 = 0.4583 | 7/16 | 0.05713 | 0.08150 | 0.15589 | 0 |
| 1 | script8 | 22/48 = 0.4583 | 7/16 | 0.02473 | 0.03412 | 0.09545 | 0 |
| 1 | h600-i20 | 19.5/48 = 0.4062 | 5/16 | 0.05098 | 0.07072 | 0.14294 | 0 |
| 1 | tower | 18/48 = 0.3750 | 3/16 | 0.02174 | 0.02936 | 0.09387 | 0 |
| 2 | mixture | 61/96 = 0.6354 | 22/32 | 0.04469 | 0.06397 | 0.13223 | 0 |
| 2 | k2 | 59/96 = 0.6146 | 18/32 | 0.03398 | 0.04796 | 0.10234 | 0 |
| 2 | policy16 | 54/96 = 0.5625 | 18/32 | 0.02893 | 0.04012 | 0.11695 | 0 |
| 2 | h160-i20 | 52/96 = 0.5417 | 15/32 | 0.02036 | 0.02830 | 0.09700 | 0 |
| 2 | h320 | 51/96 = 0.5312 | 19/32 | 0.03302 | 0.04556 | 0.13137 | 0 |
| 2 | terminal4 | 48/96 = 0.5000 | 16/32 | 0.02081 | 0.02889 | 0.09055 | 0 |
| 2 | h600-i10 | 35/96 = 0.3646 | 6/32 | 0.05283 | 0.07324 | 0.15079 | 0 |
| 3 | mixture | 115/192 = 0.5990 | 44/64 | 0.04469 | 0.06340 | 0.14678 | 0 |
| 3 | k2 | 112/192 = 0.5833 | 39/64 | 0.03381 | 0.04736 | 0.13307 | 0 |
| 3 | policy16 | 85/192 = 0.4427 | 19/64 | 0.02892 | 0.03988 | 0.12139 | 0 |

Scores count wins as 1 and draws as 0.5. Stage-specific scores determine advancement, with Hog26 score and then name breaking ties. Fresh seed blocks are shared across profiles within a stage; stages and confirmation are disjoint. Terminal magnitude 4 at K=1 is a behavior-equivalent control and scored exactly 0.5.

## Preregistered confirmation

All intervals below are 95% matchup-cluster bootstraps, 10,000 resamples, RNG 20261001. Both seats remain in each cluster.

Primary head-to-head: 161/256 = 0.628906 [0.578125, 0.679688]. Required score >= 0.55 and lower bound > 0.50.
Hog26 head-to-head: 62/86 = 0.720930 [0.627907, 0.802326].
Holdout head-to-head: 99/170 = 0.582353 [0.523529, 0.641176].

| Script population | Current | Winner | Winner minus current, paired CI |
|---|---|---|---|
| holdout | 102/128 = 0.796875 [0.710938, 0.882812] | 117/128 = 0.914062 [0.859375, 0.960938] | +0.117188 [+0.054688, +0.187500] |
| holdout, balanced | 34/44 = 0.772727 [0.590909, 0.931818] | 38/44 = 0.863636 [0.750000, 0.954545] | descriptive |
| holdout, pressure | 35/42 = 0.833333 [0.690476, 0.952381] | 41/42 = 0.976190 [0.928571, 1.000000] | descriptive |
| holdout, defense | 33/42 = 0.785714 [0.619048, 0.928571] | 38/42 = 0.904762 [0.785714, 1.000000] | descriptive |
| hog26 | 44/64 = 0.687500 [0.546875, 0.812500] | 53/64 = 0.828125 [0.734375, 0.921875] | +0.140625 [+0.000000, +0.281250] |
| hog26, balanced | 12/22 = 0.545455 [0.318182, 0.772727] | 16/22 = 0.727273 [0.545455, 0.909091] | descriptive |
| hog26, pressure | 18/22 = 0.818182 [0.590909, 1.000000] | 22/22 = 1.000000 [1.000000, 1.000000] | descriptive |
| hog26, defense | 14/20 = 0.700000 [0.450000, 0.950000] | 15/20 = 0.750000 [0.600000, 0.900000] | descriptive |

The secondary gate uses the pooled point-score drop in each population, at most 0.05. Paired difference intervals are descriptive and do not change the registered gate.

## Timing

One-thread evaluation settings throughout all scored games. Policy warmup and per-game initialization precede measured decisions; sensor conversion, history assimilation, policy proposals and search are included. Each full-game receipt stores every decision wall/CPU time and search flag.

| Confirmation controller | Decisions | Search core-s | Wall p99, s | Wall max, s | Overruns |
|---|---:|---:|---:|---:|---:|
| winner | 421400 | 0.04458 | 0.06315 | 0.12784 | 0 |
| current | 430597 | 0.02097 | 0.02862 | 0.08924 | 0 |

Across all tournament and confirmation candidate decisions: 0 overruns. The selected profile maximum over every scored stage was 0.146781 s.

| Isolated whole-game repeat | Winner search core-s | Winner wall p99, s | Winner max, s | Current wall p99, s | Current max, s |
|---|---:|---:|---:|---:|---:|
| 1 Torch threads, 4 games | 0.04357 | 0.06269 | 0.09362 | 0.02772 | 0.04278 |
| 4 Torch threads, 4 games | 0.04610 | 0.06342 | 0.12646 | 0.02884 | 0.04252 |

Four Torch threads are descriptive. They parallelize eligible neural operations; native rollout search remains serial under the GIL. This is not a four-worker native-search benchmark. Both thread settings use identical fresh seed pairs, one holdout and one Hog26 matchup. These eight timing outcomes are excluded from every strength estimate and acceptance gate.

Only one owned worker ran the isolated repeats. Unrelated host jobs were left running; their process/load snapshots are in timing-games-summary.json. Hard quiet-core isolation was not verified. Evaluation workers inherited nice 20 from a nice-10 driver plus nice -n 10 child launches; timing repeats ran at nice 10. Public-root replay measurements are retained separately in winner-timing.json.

## Audit and scope

Validated 2560 scored receipts: {'stage1': 672, 'stage2': 672, 'stage3': 576, 'confirmation': 640}. Every pair is complete, controller seats swap correctly, and script-comparison seeds/decks match. Rejected commands across scored games: 9 candidate and 7 opponent, all outcomes retained. A replay confirmed the simultaneous Cannon-placement conflict; see REPORTING_AMENDMENT.md.

The first 24-game run was invalidated after review found an alternative-leaf terminal-draw bug. Its source, manifest and receipts remain under invalidated-v1. The corrected tournament uses fresh seeds. No confirmation data was used to retune a configuration.

Seed audit: all report JSON/JSONL seed fields, plus 302 ignored NPZ game archives whose seeds match the scanned JSON sidecars; zero overlap. Native runtime is pinned locally, with eight complete P16 action/state/RNG parity games. Baseline action/score comparisons, native-leaf loop checks and terminal regressions passed.

Experiment manifest: 76d695b3590f45347303f210f65f354b97e249a970f3b2863201dab744880bbf
Confirmation manifest: 5919aab0c6fcaa6321be3b502c1655aa1b9e59dea0dbdf826e30d13e40527e79
Scored receipt aggregate SHA256: c59228ca684fbc3fc92fa14f059004766edec86252ce2b322ce1db2ec71f981b

Recommendation: the opponent-style mixture is statistically confirmed and passes the observed one-thread budget. Retain the stated quiet-core limitation; no quiet-core or four-core native-search certification is claimed. All persistent task writes are under search-tuning/.
