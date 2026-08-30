# Hog 2.6 partial play-gate distillation screen

Decision: keep a 16x rare-play weight for the full four-phase distillation,
but do not publish a checkpoint from this partial screen.

## Inputs

- retained hazard parent SHA-256:
  `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`
- converted factorized initial checkpoint SHA-256:
  `320544425abddcb57dca800f635b1db4a189172604607e7ec2d4072692116ce3`
- training snapshot: 63 completed probes, 1,127 recurrent behavior rows,
  42 parent plays and 1,085 waits
- replay-disjoint validation snapshot: complete 8- and 20-decision phases,
  28 probes, 420 behavior rows, 14 parent plays and 406 waits
- only the `hierarchical_mode_gate` parameters were trainable

The validation labels are retained-parent actions. Counterfactual root actions
are stored separately and never replace behavior targets.

## Results

The original 4x play weight converged to the all-wait shortcut. Its strongest
epoch recovered 1/14 plays while retaining all waits.

| Play weight | Best play recall | Wait accuracy | Exact action accuracy | Result |
|---:|---:|---:|---:|---|
| 4x | 7.14% | 100.00% | 96.90% | reject |
| 16x | 50.00% | 100.00% | 98.33% | reject |
| 32x | 57.14% | 96.80% | 95.48% | reject |

The predeclared publication gates were at least 85% exact action accuracy, 60%
play recall, and 90% wait accuracy. No arm passed all three, so no checkpoint
was published. The 16x arm is retained as the best tradeoff for the completed
four-phase corpus because it preserved every held-out wait while recovering
half the rare plays. The 32x arm recovered only one additional play and caused
thirteen false plays.

This is architecture feasibility evidence only. It is not gameplay,
promotion, or mid-ladder evidence.
