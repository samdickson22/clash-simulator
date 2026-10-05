# M0 recurrent PPO correctness audit

The focused v4 scalar contracts pass: 14 tests, 1.97 seconds on this Mac. Run with:

```sh
.venv/bin/python -m pytest tests/test_council_ppo_contract.py -q
```

The audit found two defects in the prior path. PPO minibatches reused collection-time recurrent state after weights changed, and collection carried old-weight state through policy synchronization. A second defect treated environment time limits like absorbing match terminals, discarding the final observation's bootstrap and cancelling its shaping potential. The learner owner integrated the repairs in `train_recurrent.py` and `selfplay_env.py`.

The new `council_recurrence.py` retains episode inputs per learner seat, resets each seat's history at its true observation reset, and reconstructs state with current weights. The production integration uses full episode prefixes. This supplies an exact reconstruction reference within floating-point tolerance and detaches all prefix gradients. Its cost belongs in the actual-path benchmark. The helper also exposes a finite burn-in suffix, such as 32 steps, starting from zero. That path is explicitly approximate and the tests demonstrate that it can differ from full-history reconstruction. No code silently treats a stale hidden state as current-weight state. Prefix snapshots own their storage; changing trimmed entity widths are padded with masked zeros.

The tests independently check:

- Full scalar behavior log-probability replay in update mode, legal support, and slot probability multiplied by conditional tile probability, including wait and ability factors.
- Uninterrupted versus chunked recurrence, episode resets, changed-weight full-prefix replay, and actual scalar collector refresh after a controlled parameter intervention.
- Identical actor logits and recurrent state after privileged critic input changes. The value changes and critic gradients do not reach the actor encoder.
- Gamma-one GAE at collection boundaries, actual terminals and environment time limits. A scalar collector capture checks that time-limit bootstrap is from the final observation before reset rather than the next match.
- Potential telescoping with zero absorbing terminal potential, retained potential at time limits, and rejection logging without an illegal-action reward penalty in v4.
- Per-seat history reset, snapshot ownership and variable entity padding.

These are software-correctness checks with small fresh attention/LSTM models and short scalar rollouts. There was no gameplay optimization, saved trained checkpoint, native collection, search or paid computation. This audit establishes no playing strength, transfer ability, full-size throughput, remote worker acceptance or prospective Tier A admission. The actual architecture benchmark and remaining M0 integrations remain separate evidence.
