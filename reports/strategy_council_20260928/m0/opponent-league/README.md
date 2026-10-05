# Per-match opponent adapter

`council_opponents.py` plugs into the existing stationary-opponent collector. Each environment samples an opponent when its new match starts and retains that opponent's weights and recurrent state until the match ends. Updating learner weights or publishing a new opponent manifest cannot change an active opponent.

The initial phase uses equal script and frozen-initial-policy probabilities. The league phase uses 25% scripts, 50% retained checkpoints and 25% a snapshot of the current learner. Scripts fill missing historical slots. The manifest supplies checkpoint file hashes, the game-data hash and the exact policy-configuration hash. Checkpoint semantic buffers must match the builder's data. Random and no-op opponents are not part of this reward pool.

Opponent action sampling has a separate Torch RNG state and does not consume the learner's RNG. Repeated reads of one frame do not advance opponent memory. Assignments record the pool generation/hash, sampled role, model identity, learner version and experience count. Initial mixtures cannot silently change; generation or phase rollback is rejected. Pool changes take effect only at subsequent match boundaries.

This implementation supports the local CPU actor path. The tested initial and league behavior uses public-v4 observations and legal masks. Scripted opponents receive actor-only observations. Learned opponents use the existing actor input path, with zero previous rewards and the model's separated critic.

Validation: 11 focused tests pass, including actual scalar steps, frozen current-opponent weights after learner mutation, new-match pool changes, checkpoint/data tampering, exact sampling regions, missing-history fallback, independent RNG, duplicate frames and manifest mutation. Targeted mypy and Ruff pass. The pilot owner is integrating this adapter into workers and checkpoint publication. No gameplay fitting or actual league experiment has run.
