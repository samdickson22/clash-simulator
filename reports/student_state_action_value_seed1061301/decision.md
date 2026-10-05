# Public action-value repair decision (seed 1061301)

## Decision

Reject all three action-value repair heads. Keep the frozen actor
`checkpoints/student_state_symmetry_dagger_seed1056901/iteration2.pt` as the
accepted policy. Do not run a fresh quarantine or promote any repair head.

The 64-wide head was the only candidate that earned gameplay evaluation, but
it violated the predeclared no-regression gate: on held-out Graveyard decks it
turned one baseline win into a loss. It also failed the purpose of this phase,
playing Graveyard in 0/4 opportunities and X-Bow in 0/4 opportunities.

## Data authority

- Train corpus: `datasets/derived/student_state_terminal_counterfactual_all_actions_seed1061101/train.npz`
- Train report: `datasets/derived/student_state_terminal_counterfactual_all_actions_seed1061101/train.json`
- Validation corpus: `datasets/derived/student_state_terminal_counterfactual_all_actions_seed1061101/validation.npz`
- Validation report: `datasets/derived/student_state_terminal_counterfactual_all_actions_seed1061101/validation.json`
- Exact deck signatures: 865 train, 217 validation, zero overlap.
- Train: 369 states, 1,519 lexicographic preference pairs, 40 decisive
  improvements over the frozen actor.
- Validation: 205 states, 874 preference pairs, 16 decisive improvements.
- Weak-card train candidate counts: Giant 29, Graveyard 25, Lava Hound 18,
  X-Bow 14, Royal Hogs 12, Battle Ram 32, Goblin Barrel 40.
- Weak-card validation candidate counts: Giant 11, Graveyard 16, Lava Hound 8,
  X-Bow 18, Royal Hogs 13, Battle Ram 9, Goblin Barrel 25.

The preference order is exact terminal outcome first, crown differential
second, and net tower damage third. Terminal speed is intentionally excluded.

## Offline comparison

| Width | Parameters | Validation pair accuracy | Outcome accuracy | Safe overrides | Safe improvements |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 26,699 | 56.64% | 66.24% | 2 | 2 damage |
| 64 | 62,379 | 56.52% | 61.15% | 8 | 1 crown + 4 damage |
| 128 | 164,459 | 55.38% | 61.15% | 4 | 1 crown + 3 damage |

All calibrated thresholds had zero observed lexicographic regression on the
205 validation states. The weak pair accuracy and the later trajectory-level
failure show that this calibration did not generalize reliably online.

## Matched gameplay

### Six-strategy smoke, 24 matchups

- Baseline: 19-5, crown differential +31.
- Repaired: 20-4, crown differential +37.
- One balanced-strategy 0-3 loss became a 2-1 win after two overrides.
- No win became a loss.

This result advanced the 64-wide head to expanded testing; it did not prove
promotion.

### Six-strategy expansion, 48 new matchups

- Baseline: 37-11, crown differential +43, net tower damage +39,701.
- Repaired: 37-11, crown differential +41, net tower damage +39,244.
- Only 3 overrides occurred in 595 queries.
- One 3-crown win became a 1-crown win.

### Weak-card targeted gate, 28 matchups

- Baseline: 17-11, crown differential +18.
- Repaired: 16-12, crown differential +17.
- Graveyard: baseline 4-0 became 3-1; one win became a loss; the card was
  played 0/4 in both arms.
- X-Bow: 2-2 in both arms; the card was played 0/4 in both arms; repaired net
  tower damage was worse.
- Lava Hound: 0-4 in both arms and only 1/4 decks used the card.
- Battle Ram improved from crown differential +3 to +4 without an outcome
  regression, but this local gain cannot outweigh the Graveyard failure.

Authoritative gameplay reports are under `gameplay_smoke/`,
`gameplay_expanded/`, and `gameplay_targeted/` in this report directory.

## Failure interpretation

The small ranker can occasionally break a harmful no-op loop, but it is trying
to repair a recurrent actor using a sparse one-step score learned from frozen
actor features. Its deck-disjoint pair accuracy is only slightly above chance,
and an override changes the later recurrent trajectory in ways absent from the
offline calibration state. Raising the threshold further would mostly disable
the controller and would not repair missing win-condition usage.

The next experiment should update the actor itself conservatively from exact
counterfactual preferences, with a strong behavior-cloning/KL anchor on
states where the original action is optimal. It must be evaluated from a fresh
checkpoint lineage and pass the same matched held-out gates. Do not patch this
head with card-name rules or a Graveyard-specific threshold.
