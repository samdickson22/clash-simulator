# B1 empirical corruption and missingness schedule

Decision: **B1 may replay joint own-HUD/clock missingness as a one-replay diagnostic. No entity, HP, tower-HP, identity-confusion, elixir-value, or position noise is justified.**

## Measured retained evidence

| Channel | Coverage / correctness | What is not established |
|---|---:|---|
| Entity typed identity | 28.987% of detector boxes | Entity recall and population false-identity rate |
| HP visible/accepted | 19.451% of detector boxes | HP value error and entity-conditional miss rate |
| Tower HP visible/accepted | 80.113% of typed tower boxes | Tower recall and HP value error |
| Clock | 83.489% of frames | Replay-disjoint value calibration |
| Hand slots | 64.201%, 55.134%, 59.691%, 67.228% | Replay-disjoint card confusion |
| Next | 67.946% of actor rows | Replay-disjoint card confusion |
| Elixir | 98.174% of actor rows | Continuous value error |
| Accepted card gold | 54/55 correct, 1 miss | Withheld identities are unknown, not negatives |
| Accepted deployment gold | 89/89 exact tiles | Candidate-conditioned, one replay |

Confidence values above are detector/HUD scores, not calibrated correctness probabilities.

## B1 transform

Status: `bounded_one_replay_diagnostic_only`. For each simulator actor row, select one whole retained actor-frame pattern within the same media-time quartile and entity-load tercile. Apply hand, Next, elixir, and clock presence plus their observed scores together. Present fields retain the clean simulator value; missing fields use their normal missing sentinel and zero confidence. Application probability is 1.0, which matches a live observation on every actor step rather than inventing a clean/corrupt mixture.

The selector is counter-based and may use only seed, epoch, episode ID, row index, entity count, and within-episode progress. It may not inspect an expert action, reward, target mask, future frame, or opponent-private HUD.

## Explicitly disabled

- `entity_dropout`: no exhaustive arena-entity ground truth.
- `entity_false_identity`: selected proposal review is not a random sample.
- `entity_or_deployment_position_noise`: no independent continuous-position ground truth.
- `hp_or_tower_hp_value_noise`: no independent HP ground truth.
- `hp_or_tower_hp_dropout`: HP bars are visibility-conditional, not random entity misses.
- `card_identity_confusion`: accepted gold has no wrong identities and only one miss; no confusion distribution.
- `elixir_value_noise`: no independent elixir gold.
- `clock_value_noise`: same-replay teacher comparison is not replay-disjoint calibration.
- `temporal_run_length_model`: one replay is insufficient.

## Provenance and limits

This is a deterministic analysis of one retained permissioned replay plus current simulator-derived causal corpora. It performs no detector inference, download, training, or target-label read. The one-replay schedule is suitable only for a bounded B1 diagnostic; replay-disjoint calibration remains a promotion blocker.

Schema: `clasher.empirical_corruption_analysis.v1`; schedule schema: `clasher.actor_augmentation_schedule.b1.v1`; pattern digest: `758ed908503732d6816495065af2eb2b1650523252338c216a83edeeea4bbf25`.
