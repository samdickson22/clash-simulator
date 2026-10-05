# Lexicographic actor-adapter decision (seed 1061801)

## Decision

Reject every contextual action-type adapter and keep the frozen accepted actor:

`checkpoints/student_state_symmetry_dagger_seed1056901/iteration2.pt`

The smallest promising adapter scale, 0.125, passed the first 24-game smoke
screen but failed the independent 48-game expansion. It reduced wins from
40-8 to 36-12, reduced crown differential from +72 to +60, rescued one loss,
and turned five parent wins into losses. It must not be promoted or sent to
fresh quarantine.

## Data and model

- Train corpus: 369 counterfactual states from 865 unique decks.
- Validation corpus: 205 counterfactual states from 217 unique decks.
- Exact train/validation deck-signature overlap: zero.
- Train preferences: 717 (370 corrective, 347 safety).
- Validation preferences: 393 (202 corrective, 191 safety).
- Preference order: terminal outcome, then crown differential, then net tower
  damage.
- Full adapter: 3,462 parameters on frozen recurrent actor features.
- Selected smoke candidate: scale 0.125, checkpoint SHA-256
  `030c9625bec20bc92ddf9e48823a2bec9f9c21e08c371b6363edb04386af6ab8`.

The original frozen actor scored 48.35% overall on validation preferences
(42.08% corrective, 54.97% safety). The scale-0.125 adapter scored 47.33%
overall (41.58% corrective, 53.40% safety), so the scale was deliberately a
small trajectory-level experiment rather than an offline promotion.

## Matched gameplay

### Six-strategy smoke, 24 matchups

| Policy | Record | Crown differential |
| --- | ---: | ---: |
| Frozen parent | 17-7 | +18 |
| Adapter 0.125 | 20-4 | +28 |

The adapter rescued three losses, caused zero win-to-loss regressions, and had
one crown regression. That earned only the independent expansion.

### Six-strategy independent expansion, 48 new matchups

| Policy | Record | Crown differential | Playable no-op rate | Threatened defensive-action rate |
| --- | ---: | ---: | ---: | ---: |
| Frozen parent | 40-8 | +72 | 88.66% | 6.24% |
| Adapter 0.125 | 36-12 | +60 | 86.86% | 6.81% |

Paired changes:

- Loss to win: 1.
- Win to loss: 5.
- Crown differential improved: 3 games.
- Crown differential regressed: 8 games.
- The five lost wins occurred against balanced (1), reactive-defense (2), and
  split-lane (2) opponents.

The adapter did make the policy act slightly more and defend slightly more,
but those local behavioral changes did not translate into safer play.

## Interpretation and next move

Both attempted post-hoc repairs now fail for the same structural reason. A
small value override and a small contextual adapter can alter an immediate
choice, but that choice changes the frozen recurrent trajectory in ways the
counterfactual terminal labels do not cover. Smoke improvements are real but
unstable across new matchups.

Do not keep shrinking the adapter until it becomes inert, and do not add
card-name exceptions. The next model experiment should use the exact
counterfactual corpus as an auxiliary loss while training a fresh compact actor
end-to-end, anchored on the larger set of safety preferences and evaluated
against whole held-out decks. The frozen actor remains the control and accepted
checkpoint.
