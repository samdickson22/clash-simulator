# Hog 2.6 capacity-48 causal corpus

Date: 2026-08-28

## Method

The source train and held-out validation corpora were resized from 128 to 48
entity slots without truncating any crowded observation. If any row in an
episode exceeded 48 live entities, the entire episode was removed from both the
corpus and its aligned public-observation sidecar. Retained episode IDs were
then remapped contiguously. Source files were hash-checked before and after the
operation and were not modified.

The resulting artifacts retain:

- the current 494-token typed vocabulary;
- public feature contract v2;
- public action-mask contract v2;
- exact episode, source-frame, expert-action, and action-mask alignment;
- causal public-observation confidence arrays;
- whole recurrent trajectories only.

## Train split

- source: 167,631 rows / 336 episodes / maximum 54 entities
- output: 163,291 rows / 330 episodes / maximum 48 entities
- raw over-capacity rows: 10
- whole episodes removed: 6 (`12, 26, 80, 107, 291, 324`)
- rows removed with those episodes: 4,340 (2.5890%)
- rows retained: 97.4110%
- corpus SHA-256:
  `d265ac181fff0c5770aa5dc2164362442cbc9d1869bc5b41e5f7941203ad4231`
- public sidecar SHA-256:
  `0b9c1466629b993ba9e3a52a10147c67e760a8664cf62986b4c13151ed441bab`

## Held-out validation split

- source: 54,333 rows / 112 episodes / maximum 51 entities
- output: 53,583 rows / 111 episodes / maximum 46 entities
- raw over-capacity rows: 4
- whole episodes removed: 1 (`14`)
- rows removed with that episode: 750 (1.3805%)
- rows retained: 98.6195%
- corpus SHA-256:
  `2bfaaab6be9ec5a3857a6d6cda054b73e1ed232c3b5b01cbcb581adee97eee78`
- public sidecar SHA-256:
  `58fc111ce666e0aef3b27c5091332462e3738cc40e4dfaac6edc87b2805ac016`

## Interpretation

This proves that capacity 48 preserves nearly all currently collected Hog 2.6
behavior data without manufacturing clipped states. It does not prove that 48
is sufficient for every future free-running battle. Runtime promotion therefore
still depends on the exhaustive CUDA deck-pair audit and later stochastic/
strategy stress evidence.

## Validation

- converter tests: 2 passed
- converter Ruff and focused mypy: clean
- both output splits independently inspected for 494 tokens, capacity 48,
  maximum live counts, contract v2, and aligned IDs/actions/frames
