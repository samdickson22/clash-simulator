# Hog 2.6 play-gate DAgger decision

Decision: reject the factorized play-gate lineage. Retain the original Hog 2.6
gameplay parent unchanged. Do not run another play-weight, learning-rate, or
residual-adapter screen on this lineage.

## Retained gameplay parent

- checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
- SHA-256: `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`

## Failed student

The factorized timing student passed replay-disjoint behavior distillation, but
failed its first free-running development screen:

- parent: 9-3, +1.083 crowns/game;
- student: 5-7, -0.583 crowns/game;
- student placement rate: approximately 12-13%, versus approximately 7% for
  the parent.

This was a policy-induced state-distribution failure, not a simulator crash or
an illegal-action failure.

## One-pass DAgger evidence

The DAgger collector ran the failed student on its own states and labeled those
exact causal histories with the frozen parent. It preserved the student's
previous actions, rewards, episode starts, public masks, and recurrent order.

| Split | Rows | Episodes | Teacher play rate | Corpus SHA-256 |
|---|---:|---:|---:|---|
| train, seed 1200501 | 5,376 | 56 | 6.101% | `3a355104761225584ad36c61f12ac3c73a520474baf8fea8209dceb0028ea5c2` |
| validation, seed 1200601 | 2,688 | 28 | 6.138% | `087aa9f7fd8e885924e80978fc78201e1e38908ac9b1bf6e1d8891e17176de0a` |

All 8,064 teacher actions were legal under the stored public mask. Across the
seven opponent styles, the student played on 7.0-8.3% of decisions while the
teacher played on 5.7-6.25%; action disagreement was 7.7-10.2%.

On the held-out student-state corpus, the unmodified student achieved 90.14%
exact mode accuracy but only 45.45% play recall and 93.06% wait accuracy. It
therefore already failed the predeclared simultaneous gate of at least 88%
exact accuracy, 55% play recall, and 95% wait accuracy.

## Conservative retraining screen

Only `hierarchical_mode_gate` was trainable. Both arms started from the same
failed student and used learning rate `1e-4`, 16 epochs, and disjoint seeds.

- play weight 1: wait accuracy reached 99.01%, but play recall collapsed to
  12.12-36.97%; no epoch was eligible.
- play weight 4: play recall reached 65.45% only while wait accuracy fell to
  87.04%; no epoch simultaneously passed the gates.

Neither arm emitted a checkpoint. The corresponding reports are
`reports/hog26_playgate_dagger_pw1_seed1200701.json` and
`reports/hog26_playgate_dagger_pw4_seed1200704.json`.

## Interpretation

The factorized gate cannot recover the parent's sparse play timing on the
student's induced states without trading missed legitimate plays for false
plays. The same failure has now appeared in free-running games, causal DAgger
validation, and two bounded correction strengths. Further scalar weighting is
not justified.

The next policy-improvement lineage must not add another global or factorized
play/wait threshold. It should preserve the retained parent's deterministic
action policy and improve complete state-conditioned actions using an
on-policy objective with an exploration distribution that remains close to
that deterministic policy, or replace the policy architecture outright.
