# Hog 2.6 terminal corpus integrity correction

Decision: reject the first 21-root validation collection and refuse to train on
the original 512-decision corpus. Preserve both collections as negative audit
evidence only.

## Findings

The initial terminal-oriented collection produced 24 intended training roots
and 21 intended validation roots at warmups 13, 27, and 41. Two independent
contract failures were found before optimization:

1. Five training roots and five validation roots retained at least one
   nonterminal candidate after 512 decisions. These are right-censored labels,
   not terminal outcomes.
2. Eighteen of the 21 validation root policy inputs were byte-identical to
   training roots. Changing only the seed does not create a new trajectory for
   deterministic StrategyBots. The overlap comparison covered entity IDs and
   features, masks, the visible hand, globals, the legal-action mask, previous
   action/reward, and episode-start state; provenance fields were excluded.

The original compiler aborted on the first nonterminal training probe. No
corpus, candidate checkpoint, or gameplay evaluation was published from the
invalid inputs.

## Corrected contract

- Extend only the five censored training roots from 512 to 768 decisions,
  preserving the exact root and candidate action set.
- Replace each censored result with its terminal extension; retain already
  terminal 512-decision results because their post-terminal reward is exactly
  zero.
- Collect validation at distinct warmups 20, 34, and 48 across all seven
  opponent modes, using a 768-decision ceiling.
- Require every candidate row to be terminal, with exactly zero critic
  bootstrap and total return exactly equal to observed discounted reward.
- Hash policy-visible root inputs and abort training on any train/validation
  intersection or duplicate validation root.
- Keep the parent play/wait gate frozen; any candidate fit may change only
  same-mode card and tile preferences and must subsequently pass the paired
  seven-opponent gameplay matrix.

## Enforcement

- Commit `63635dda` rejects nonterminal counterfactual corpora.
- Commit `1b2e9189` permits mixed declared horizons only after terminality and
  rejects exact train/validation root overlap.
- Commit `6967d11f` forbids critic bootstrap in terminal labels.

This correction is not evidence of a better policy. It restores the minimum
causal and outcome integrity needed for the next repair experiment to be
interpretable.
