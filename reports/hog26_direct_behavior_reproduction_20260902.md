# Hog 2.6 direct-Simple behavior reproduction

Status: passed; 56-game action-hashed closed-loop gate is exact

## Decision

The failed fresh policy did not need another reward tweak. Its randomly initialized
actor differed from the frozen direct-Simple control in 163 of 169 shared tensors,
so the small behavior corpus was being asked to relearn the entire actor. The new
arm instead preserves the control's encoder, structured memory, card pointer, and
spatial decoder, removes the separate hazard head, and replaces its timing path
with:

- one calibrated per-decision play probability; and
- one model-owned probability accumulator stored in recurrent state.

The accumulator is inside `ClasherPolicy.act`; it is not an environment-side or
inference-side calculation. The student has 1,700,276 learned parameters versus
1,712,693 in the frozen teacher, a reduction of 12,417 parameters. Only three
output-bias parameters were trainable in the accepted calibration run.

## Authoritative behavior data

Two replay/seed-disjoint complete-episode corpora were collected directly from the
frozen MPS policy boundary. They store actor observations, public mask v2, executed
action, exact previous-action/reward chronology, reset recurrent state, and the
positive-weight-corrected teacher play probability emitted by the same one-step
call that selected the action.

| split | seed | games | rows | placements | rate | Hog | Musketeer |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 1261001 | 14 | 5,373 | 380 | 7.072% | 67 | 48 |
| validation | 1262001 | 14 | 5,590 | 396 | 7.084% | 69 | 51 |

The train play probability has mean 0.0165383 and range
0.0158580–0.0168773. Validation has mean 0.0165414 and range
0.0158580–0.0168498. Reintegrating those exported probabilities from each exact
reset state at the teacher threshold 0.2 reproduces all 5,373 training decisions
and all 5,590 validation decisions' play/wait gates with zero mismatches. This
shows that the old timing behavior is nearly a constant clock; the important
state-dependent behavior lives in card and tile selection.

The exact probability band that fires on decision 14 but not decision 13 is
0.0158125–0.0170184. Every exported teacher probability in both corpora lies
strictly inside that band. The fitted constant 0.0165383 therefore preserves the
teacher's 14-decision cadence with margin; it is not a lucky rounded threshold.

Fireball appears zero times in both small corpora. That is a teacher-support
limitation, not silently repaired by class weighting. It blocks any claim that
the teacher demonstrates complete Hog 2.6 play, but it does not block the narrow
behavior-reproduction experiment.

## Offline result

Before timing calibration, the transplanted student already matched conditional
card choice at 99.21% and tile choice at 94.47%. Its inherited, previously unused
mode gate emitted play with mean probability 0.9753, isolating the defect to
timing.

The train-only closed-form Bernoulli baseline sets the play probability to the
training mean. Five epochs were allowed to update only the three final mode biases;
the selected epoch was 4. On held-out validation:

| metric | result |
|---|---:|
| play precision | 100% |
| play recall | 100% |
| wait accuracy | 100% |
| card accuracy on teacher plays | 99.24% |
| tile accuracy on teacher plays | 94.44% |
| exact flat action | 99.57% |
| recurrent burn-in max error | 0 |
| play-probability Brier vs teacher | 1.86e-8 |

The constant initialization already achieved the same action metrics before the
gradient updates. This is evidence for retaining the smallest clock baseline,
not evidence that a larger timing network helped.

## Closed-loop smoke

Teacher and student each drove their own matched 14-game Simple Gym batch across
all six strategy bots plus random, both seats, seed 1264001. The results were
identical in every reported field:

- record: 6–8 for both;
- per-opponent outcomes: identical in all seven buckets;
- total and per-game decisions: identical;
- placement rate: 0.0707162 for both;
- every per-card count: identical;
- Hog Rider uses: 85 for both; and
- card-usage total-variation distance: 0.0.

This clears the bounded smoke but not promotion. The predeclared scale floor is
56 games per arm. The scaled evaluator now additionally hashes every complete
per-game action sequence.

The first scaled seed, 1265001, is complete. Both arms scored 9–19. All 28/28
per-game action hashes match, as do every game duration, opponent outcome,
placement count, and per-card count. The second independent seed, 1266001, also
matches exactly: both arms scored 10–18 and all 28/28 action hashes match.

Across the predeclared scaled gate:

- 56 games per arm completed across two independent seeds;
- 56/56 complete-game action hashes match;
- teacher and student both scored 19–37;
- every opponent-bucket score, game duration, placement rate, and card count
  matches;
- aggregate cadence ratio is 1.0; and
- aggregate card-usage total-variation distance is 0.0.

The behavior-reproduction architecture gate therefore passes. This result does
not upgrade the policy's skill: the identical 19–37 record quantifies that the
frozen control itself remains weak.

## Gates and next action

Source validation passes 90 focused tests with five device skips, plus Ruff and
mypy on the touched modules. The reproduction stage's four gates are now met:

1. 56 matched games per arm completed;
2. action hashes, outcomes, duration, cadence, and card support matched exactly;
3. no opponent bucket regressed; and
4. the exact replacement establishes the frozen pre-update student-state baseline
   for later DAgger checks.

The reproduced policy is only the prior low-level control. The next
skill-improvement stage must address its 19–37 scaled record and absent Fireball
support with complete-outcome value evidence and conservative candidate
improvement rather than dense reward shaping. Any update must retain the current
56-game suite as a regression anchor and add student-state DAgger before promotion.
