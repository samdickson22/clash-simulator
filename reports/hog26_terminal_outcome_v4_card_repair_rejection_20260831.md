# Hog 2.6 terminal-outcome v4 card repair rejection

Decision: reject the frozen-timing card/location repair. Retain the original
Hog parent. Do not tune learning rate, preference coefficient, margin, epoch
count, or trainable head set on this lineage.

## Inputs

- train corpus: 24 terminal roots, 11 accepted probes, 106 same-mode
  preference pairs, SHA-256
  `17e8f83943265a2a82a3db203dbecec85caf53adb5768338c0e7ae4a6b8e8d77`;
- held-out corpus: 21 terminal play-aligned roots, 14 accepted probes, 140
  same-mode preference pairs, SHA-256
  `cefeb529a2f6da1c2afe8d4e53a929eacaf4439e2056ee2cc14fde899e72ecd2`;
- exact policy-input train/validation overlap: zero;
- parent play/wait hazard and all non-action heads frozen.

## Offline rejection

The initial held-out corrective preference accuracy was 5.63%, safety
preference accuracy 95.65%, and non-root exact action retention 100%.

The strongest late epochs reached 22.54% corrective accuracy, but:

- non-root exact action retention fell to 98.08%, below the required 99%;
- safety preference accuracy fell to 91.30%, more than the allowed one-point
  regression from 95.65%;
- no epoch satisfied all three predeclared gates.

The trainer selected epoch zero, wrote an audit report, and published no
checkpoint. The paired gameplay matrix therefore did not run.

## Interpretation

Terminal outcome authority corrected the teacher, and the held-out corpus
contains genuine win/loss-flipping alternatives. However, jointly moving the
current card and tile heads enough to learn those sparse corrections disturbs
too many unrelated actions and safety rankings. This is not fixed by another
coefficient or learning-rate screen.

The same v4 probes independently expose a coherent play/wait problem: all
three early slow-push phases prefer waiting, while later roots show state-
dependent play opportunities. The next bounded hypothesis is therefore a
timing-only hazard-head repair with card/tile logits frozen. If that cannot
improve terminal timing preferences while preserving exact actions outside
timing roots, discard the repair pipeline and restart the decision architecture.
