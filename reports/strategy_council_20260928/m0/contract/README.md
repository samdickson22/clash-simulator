# M0 public actor contract

Implemented `public_contract_version=4` with fresh checkpoint parameters for own-card levels. Versions 1–3 retain their prior configuration and parameter structure. The structured builder opts in with `public_entity_levels=True, public_hand_levels=True`; both flags default to false.

The contract carries `entity_levels` and `entity_level_confidence` for visible bodies and Crown Towers, plus `hand_levels` and `hand_level_confidence` for four own hand slots and the visible next card. Levels use int64; confidence uses float32. Missing values have level 0 and confidence 0; known levels are 1–127 with confidence in (0, 1]. Absent card slots cannot carry levels. Simulator values come from the player's card-level API and the visible body's actual level metadata. Visual degradation retains missing levels rather than inventing them.

`project_council_public_observation` preserves level and sensor confidence while masking features to the existing real-play-v2 subset. The v4 model repeats this mask at its boundary and ignores previous rewards in every observation domain. The critic receives its separate payload. Hand and next-card levels have a learned projection into the actor's card tokens; they affect both logits and recurrent state.

`PublicPolicySequence` writes archive v6 for the full level contract, rejects inconsistent version/field combinations and preserves v3–v5 loading. New archive policy inputs zero previous rewards. Version 4 requires explicit observation confidence and the exact token vocabulary. Reusing historical weights without a versioned conversion is not supported.

Validation:

- `focused-pytest.log`: 123 passed, including 13 new tests covering round trips, actual hand/next-level influence, missingness, malformed inputs, and actor invariance to hidden enemy state, privileged critic state, previous reward and unsupported feature channels.
- `pytest.log`: earlier integration run had 190 passed and 9 failed. Eight exposed collector compatibility while the learner agent was editing: legacy v1 policies received v2 accepted-play fields. Sent to learner agent for repair. The remaining test requires the unavailable historical checkpoint `checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt`.
- Focused `git diff --check` passed.

This receipt covers contract checks with fresh untrained networks. It does not establish playing strength, Tier A admission, native calibration, camera level recognition or the full M0 sequence/benchmark acceptance criteria. Collection/imitation/PPO/evaluation integration is coordinated separately.
