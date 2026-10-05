# Rejected visible-pressure imitation weighting

## Question

Would doubling supervised imitation loss for human decisions with a visibly
detected enemy troop or building in the canonical near-tower quarter improve
defensive behavior without damaging broader generalization?

## Matched experiment

- Parent: `tv_raw1000_spatial_value_rl_seed1044801` update 40.
- Corpus: the first-1,000-game training split.
- Identical seed, episode split, initialization, training order, five epochs,
  batch size 32, learning rate 2.5e-4, sequence length 8, and action-type-head-only
  training.
- Control treatment: every supervised row weight 1.
- Candidate treatment: visible near-tower pressure rows weight 2; every other row
  weight 1. There were 900 pressure rows in the training episodes.
- Evaluation: untouched validation, held-out-archetype, and chronology splits.

## Evidence

Action-type NLL (lower is better):

| Split | Context | 1x | 2x | 2x - 1x |
|---|---:|---:|---:|---:|
| validation | all | 1.301674 | 1.304101 | +0.002427 |
| validation | tower zone | 1.189993 | 1.184062 | -0.005931 |
| validation | own-half pressure | 1.308994 | 1.306454 | -0.002540 |
| validation | remote or clear | 1.296521 | 1.302444 | +0.005923 |
| held-out archetype | all | 1.358866 | 1.364446 | +0.005580 |
| held-out archetype | tower zone | 1.433332 | 1.435469 | +0.002137 |
| held-out archetype | own-half pressure | 1.394084 | 1.396899 | +0.002815 |
| held-out archetype | remote or clear | 1.337342 | 1.344611 | +0.007269 |
| chronology | all | 1.314382 | 1.320569 | +0.006187 |
| chronology | tower zone | 1.295799 | 1.307054 | +0.011255 |
| chronology | own-half pressure | 1.324226 | 1.326930 | +0.002704 |
| chronology | remote or clear | 1.308586 | 1.316824 | +0.008238 |

Rare-card action-type accuracy changed from 0.045685 to 0.050761 on validation,
0.079930 to 0.083406 on held-out archetypes, and 0.030075 to 0.022556 on the
chronology split. These very low raw-fit rare-card accuracies are also a reminder
that the full imitation fit is not itself a safe gameplay candidate; the main
pipeline screens conservative blends instead.

## Decision

Reject the 2x weighting. Its only meaningful directional win was a 0.0059
near-tower NLL reduction on one split. It worsened every aggregate split,
remote/clear behavior on every split, and near-tower NLL on both held-out
archetype and chronology data. No gameplay evaluation is warranted.

The reusable visible-pressure evaluator remains valuable as a diagnostic and a
required no-regression gate. The training weight option was removed from the
main implementation rather than preserving an unhelpful tuning knob.

Raw artifacts:

- `reports/tv_raw1000_*_update40_pressure_ab_recurrent.json`
- `reports/tv_raw1000_*_update40_pressure_ab_defensive.json`
- `reports/tv_raw1000_*_update40_pressure_ab_card_frequency.json`
- `reports/tv_raw1000_update40_headonly_pressure{1,2}_seed1046901_epoch5_manifest.json`
