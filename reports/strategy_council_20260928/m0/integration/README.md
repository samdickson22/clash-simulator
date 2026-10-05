# M0 cross-pipeline sequence receipt

`tests/test_council_pipeline.py` passes: one v4 sequence survives actual scalar collection, scripted-demonstration transport, recurrent imitation input construction, PPO minibatch input construction, public archive round-trip, checkpoint loading and stepwise evaluation.

The fixture uses a fresh untrained actor, one scalar environment, two seats and three five-tick decisions: 15 actual simulator ticks and six seat transitions. Card levels vary from 10–12; Crown Tower levels are 10 and 12. There is no optimizer, native execution, paid resource use, training corpus publication or expert-label claim. The scripted adapter container is used in memory with supervision disabled for every row; this is a partial transport fixture, not a complete scripted game. Complete-game collector semantics have separate synthetic tests owned by the data agent.

Checks on the same captured sequence:

- Every common public tensor, level/confidence pair, action mask, previous action and episode boundary matches exactly across PPO, imitation and archived inference inputs.
- Public outputs and final recurrent state match exactly when built through those three input paths. Removing padded entities in the actual imitation builder preserves outputs and state within 2e-6.
- The collected action log probabilities replay within 2e-6; no update is performed.
- Checkpoint-loaded evaluation on each captured battle snapshot reproduces the stored public mask, actor logits and final recurrent state within 2e-6. Every sampled evaluation action is legal under that public mask.
- Unsupported feature channels and previous rewards are zero. Actor results agree despite the PPO path carrying a separate privileged critic payload and imitation/inference omitting it.
- Model weights remain bit-identical to their initial values.

Result: **1 passed in 1.91s**, recorded in `pytest.log`. Focused `git diff --check` passed. No production changes were needed during this independent integration check. This provides software-contract evidence; it does not establish playing strength, native transfer, Tier A admission or completion of the full M0 benchmark/protocol requirements.
