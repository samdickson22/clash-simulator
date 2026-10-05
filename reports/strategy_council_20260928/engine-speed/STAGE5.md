# Stage 5: NO-GO for srp-pub-mix-C56

Implementation and the registered 256-game evaluation are complete. Python remains the default and the byte-identity reference.

Statistical gate: PASS. Strict 250 ms wall gate: FAIL. These verdicts are independent. No confirmation outcome was used to retune the player, schedule or gate.

## Registered evaluation

Pooled: 0.875000 [0.828125, 0.917969], 256 games. Required score >= 0.55 and lower 95% bound > 0.50.
Defense: 0.880952 [0.797619, 0.952381], 84 games. The same thresholds apply.

| Family | Games | Wins | Draws | Score | Matchup 95% CI | Abilities accepted |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Hog 2.6 | 38 | 27 | 0 | 0.7105 | [0.5263, 0.8684] | 0 |
| Hog EQ/Firecracker/MM | 38 | 34 | 0 | 0.8947 | [0.7895, 0.9737] | 19 |
| Royal Hogs/Furnace | 36 | 36 | 0 | 1.0000 | [1.0000, 1.0000] | 0 |
| X-Bow | 36 | 33 | 0 | 0.9167 | [0.8333, 1.0000] | 0 |
| bait | 36 | 35 | 0 | 0.9722 | [0.9167, 1.0000] | 2 |
| Goblinstein | 36 | 32 | 0 | 0.8889 | [0.7500, 1.0000] | 6 |
| AQ | 36 | 27 | 0 | 0.7500 | [0.5833, 0.8889] | 22 |

| Opponent style | Games | Score and 95% CI |
| --- | ---: | --- |
| balanced | 86 | 0.872093 [0.790698, 0.941860] |
| pressure | 86 | 0.872093 [0.779070, 0.953488] |
| defense | 84 | 0.880952 [0.797619, 0.952381] |

Intervals use 10,000 percentile bootstrap resamples of paired matchup means, RNG 40404041. Both seats stay together. Family intervals are descriptive. The fixed schedule has 128 matchups with swapped planning seats, role-held-out eval/eval_ood human planning perspectives, and train-frequency opponents. Common deck identities can occur in both train and eval roles; this is role holdout, not a claim of deck-identity holdout. Both actions are selected before fixed seat 0/seat 1 application.

PREREG-C56.md predates every confirmation game. schedule.json fixes all decks/styles/seeds. The initial audit scanned 915,788 historical seed fields and 3,945 NPZ archives; the embedded-metadata supplement checked 1,924 seed occurrences from 1,922 archives plus textual report matches, with no collision. Pickled roots are covered through their JSON plan/gate provenance. All 256 receipts are present; no outcome was excluded.

## Timing and abilities

One execution thread per game process, nice 10, pregame initialization/warmup excluded. Whole decisions include public sensor conversion, history assimilation, candidates, reconstructed root and native search. 209,575 decisions / 22,913 searches. All-decision p99 0.123381593 s, max 0.311304875 s. Searched p99 0.170169812 s, max 0.311304875 s. Overruns: 16. Three independent evaluation processes shared the host with unrelated jobs; quiet-core isolation was not established.

Eight development games on the final driver passed the observed budget before confirmation: p99 0.119796398 s, searched p99 0.164559547 s, max 0.242517875 s. They are not part of strength estimates and do not override confirmation timing.

| Champion | Legal decision opportunities | Attempts | Accepted |
| --- | ---: | ---: | ---: |
| MightyMiner | 192 | 21 | 21 |
| Goblinstein | 184 | 6 | 6 |
| ArcherQueen | 152 | 22 | 22 |

Rejected non-no-op commands: planner 2, opponent 31; all outcomes retained. Script opponents retain their declared rule of never activating abilities. Legal opportunities count decisions where the own active champion could activate; they are not independent cooldown windows.

## Native parity and public-state accuracy

All 200 searchable C56 roots match selected actions, ordered candidates, exact scores, continuation digests and full 624-word MT state plus index: 3993 candidates, 11979 three-style rollouts, 1916640 ticks, 359370 continuation actions. Six additional roots exercise AQ/MM/Goblinstein in both seats, 36 rollouts; each ability also activates in the public reconstructed model.

Eight full native-searched core games match Python every tick, action and MT state: 29227 ticks, 651 searches, 2 accepted abilities. These core qualification games use full model roots and are not the fair evaluation. Current Stage 4 regression discovery 88/88 and P16 backend/regressions 9/9 pass.

The public tracker passes 8 C56 full games/74424 checks with exact elixir equality, 14490 determined-hand and 70,598 determined-cycle checks, 9 abilities. A separate full Collector/Heal/champion game passes 12,002 checks, 8 resource grants, 3 abilities and 38 Heal plays. Champion cycling is the reference engine's ordinary four-card cycle. Heal has no elixir effect. Confirmation adds 209,575 truth checks, 34657 determined-hand and 202,757 determined-cycle checks, all exact by assertion.

The prior reconstructs 2,925 train decks weighted by 69,380 human perspectives. The posterior removes unobservable hand-slot permutations and retains exact hand multisets/queue order. Known quantities are never resampled. Hidden hand/cycle/elixir/RNG poisoning leaves the public sensor and model unchanged. Public template coverage passes 1,232 samples across all 56 cards.

The fair player accepts only a v5 public packet, own HUD and timestamped public events. Unobserved combat clocks, targets, shields and deployment phases use deterministic synthetic defaults. This is a public model, not exact recovery of hidden combat state. Only unresolved cards/order and independent rollout RNG are sampled. Card metadata and missing carrier templates come from isolated fixed demonstrations, not the real battle.

## Implementation and evidence

New src/clasher/rl/c56_rollout_planner.py provides explicit Python/native C56 backends. Root candidates are balanced script choice/top 4, no-op, legal ability and 16 sampled public-legal placements. There is no qualified C56 policy in this run. Every candidate averages balanced/pressure/defense opponent-model rollouts at 160/10 ticks, with balanced own continuation, defense-v2 plus elixir and terminal +2/-2/0. Search runs every second 5-tick decision starting at tick 90. Native continuations do not call Python.

The development differential found one native physics omission. Stunned pushback skipped the frozen path reached-node update, diverging on RoyalHogs at tick 588 after a route difference at 580. Rust now matches entities.py:391-410. failure19.pkl, phase19.json, routephase19.json and engine-rs/test_stage5_search.py retain the reduction. C56 leaf metadata now imports per-entity cost/formation share and respects movement modifiers. C56 action 2305 is supported; C56 script behavior is unchanged.

An unrelated job changed vision/l1_training.py while the original aggregate fingerprint included vision. No historical receipt was relabelled. replay_qualified.py reproduces all 200 recorded Python trace hashes under the final scoped runtime pins, and eight core games were rerun under those pins. scoped-sources.json verifies read-back invariance. Python oracle sources outside that unrelated vision work, canonical gamedata and the original Stage 4 active native library remain entry-identical. Stage 5 uses a private extension.

The sealed analyzer required a JSON-only adapter for NumPy scalar booleans. analyze_serialize.py converts those scalars to native JSON values without changing the sealed statistical code, bootstrap draws or results. analysis-serialization.json pins both files.

Evaluation manifest SHA256: a344f739929fbe58d93d1f8b60941dee4920ff2330791ca1b6dc9c27f1e6d101. Receipt aggregate SHA256: 68fd477c7e062f02145cf903ab6824b7d27fcd82dd093832811547bcf538ad4f. Final scoped runtime fingerprint: 9422c9a77f8a12089dce4bd03d04aea57bc86e33f69a12319583a078d3515d10.

Changed files: src/clasher/rl/c56_rollout_planner.py; engine-rs/differential.py; engine-rs/src/lib.rs, scripts.rs, leaf.rs; engine-rs/test_stage5_search.py; engine-speed/PREREG-C56.md, STAGE5.md, PROGRESS.md and stage5/ implementation, drivers, receipts, private library. No Python engine/C56 script behavior, forbidden evidence directory or unrelated process was changed. No git commit or destructive git operation was performed. Build intermediates were cleaned while idle; Stage 5 outputs remain below 1 GiB.

## Open issues

The registered hard 250 ms wall limit failed. This player has no one-core budget admission; preflight timing and percentile results cannot erase the measured maxima. Recorded overruns also exceed 250 ms of process CPU time; scheduler delay alone does not explain the failure. A future performance change needs its own pinned validation.
Public combat-state reconstruction remains approximate, and quiet-core timing is unverified. Native support is an optional local extension rather than a packaged wheel.
