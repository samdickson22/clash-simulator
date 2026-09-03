# Hog 2.6 actor-visible outcome gate: 128-game crossed training set

## Decision

The 128-game crossed corpus is accepted as complete-game training evidence. The
free structured-summary head and both bounded structured residual candidates are
rejected. The public-global control has the best aggregate development score,
but a larger-window audit rejects it too: held-out early-game decisive AUC is
0.4808. It is not authorized for search or policy updates.

The next evidence step is broader matchup diversity, not more epochs on the
same 32 streams: collect additional current supported decks across every
strategy style and both seats, then repeat the frozen-baseline residual screen.
An untouched holdout and additional seeds remain deferred until a contextual
candidate beats the public-global baseline.

## Corpus authority and audit

- Corpus: `datasets/derived/hog26_crossed_train4_seed1276001/corpus.npz`
- SHA-256: `62aa1bbf6ff59dc020992a9f4c3e3dd030797389a842e73ed528cd9ff21ffa1a`
- Policy checkpoint SHA-256:
  `f609b60b3e7b7b574e084b15255e0fc247447e3c18d8552714213ccd0c709336`
- 128 complete episodes, 59,287 actor decision rows, four episodes in each of
  32 strategy/deck/seat streams.
- Outcomes: 91 losses, 37 wins, zero natural draws. Controlled draw corpora
  remain separate.
- Seats: seat 0 = 44 losses / 20 wins; seat 1 = 47 losses / 17 wins.
- Episode length: minimum 141, median 450, maximum 628 decisions.
- Independent checks passed: exact terminal winner to actor-relative outcome,
  exact episode label repetition on every row, terminal margin repetition,
  one start and one terminal per episode, ordinal 0-3 for every stream, finite
  numeric arrays, and no critic arrays.

## Experiments

| Candidate | State width | Trainable parameters | Selected epoch | Held-out decisive AUC | ECE | Decision |
|---|---:|---:|---:|---:|---:|---|
| Free structured summary | 398 | 8,098 | 18 | 0.4683 | 0.2126 | reject |
| Public globals, old NLL selection | 18 | 646 | 29 | 0.6087 | 0.1282 | selection policy superseded |
| Public globals, old aggregate gate | 18 | 646 | 14 | 0.6733 | 0.1214 | reject; early AUC 0.4808 |
| Frozen-global + bounded full structured residual | 398 | 7,145 | 0 | 0.6733 | 0.1214 | reject; no positive gain |
| Frozen-global + compact tactical residual | 118 | 1,905 | 0 | 0.6733 | 0.1214 | reject; no positive gain |

The public-global checkpoint is
`checkpoints/hog26_actor_outcome_public_globals_fullgate_seed1276201/candidate.pt`
with SHA-256
`1fad639704256691fd4fa696a0ad548397d8c3884e9b0d1e83848f52bee4d750`.
It is a historical control, not an accepted warm-start or promoted search value
function under the corrected across-phase gate.

## Correctness changes

1. Epoch selection now maximizes decisive ranking only among epochs that pass
   the complete development gate. Previously, monotonically improving NLL
   selected epoch 29 even though decisive AUC had already degraded materially.
2. Structured residual heads have a separate normalization boundary, begin at
   exactly zero context contribution, warm-start from an accepted public-global
   head, freeze that head, and bound the context correction.
3. The structured candidate must improve decisive AUC over its frozen baseline;
   reproducing the baseline is not a promotion.
4. Actor feature tensors, losses, and gradient norms now fail immediately on
   non-finite values. This was added after an MPS zero-upstream LayerNorm
   gradient produced NaNs; the context branch no longer uses that unsafe
   normalization pattern.
5. Aggregate AUC is no longer sufficient: early, middle, and late held-out
   decisive AUC must each clear 0.55. This rejects the globals-only shortcut
   that looked strong mostly because tower state makes late outcomes obvious.
6. Model selection and acceptance now use one representative midpoint row per
   episode per reached phase. Full row-weighted metrics remain diagnostic only;
   long games can no longer contribute hundreds of correlated copies of one
   terminal label. The training prior is likewise computed from episodes, not
   decision-row counts.
7. Final development and holdout acceptance require a deterministic 2,000-draw
   nonparametric bootstrap lower 95% bound above 0.50 for decisive AUC in each
   phase. Point estimates alone are not treated as evidence of above-chance
   generalization.

## Interpretation

The corpus increased repeated outcomes per original matchup, but it did not add
enough independent matchup diversity. The free structured model learned
training-specific entity/deck correlations, especially against the held-out
Valk Log Bait family. Constraining the context prevented catastrophic drift but
did not make those features useful. More epochs or more copies of the same
matchups would strengthen the shortcut rather than solve it.

No search, policy update, PPO, or self-play improvement is authorized by this
gate.
