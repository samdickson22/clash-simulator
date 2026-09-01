# Hog 2.6 terminal-outcome v4 training audit

Status: training-side collection complete; no policy has been fit or promoted.

## Authority and inventory

- parent checkpoint SHA-256:
  `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`;
- 24 exact roots at warmups 13, 27, and 41;
- six deterministic StrategyBots sampled once per phase and random sampled
  twice per phase;
- 12 legal candidate actions per root, horizon ceiling 768 decisions, exact
  first-terminal win/draw/loss authority;
- 48 JSON/NPZ artifacts, 273,643 bytes;
- sorted name-plus-file-digest aggregate SHA-256:
  `0baf976e4a7233c8c08a270e378221647c09c90cb768a451f395be644b15d586`.

Every root has 12 terminal candidate rows, outcomes in `{-1, 0, 1}`, and zero
critic bootstrap. Eleven roots pass the predeclared same-mode acceptance gate:
the selected action differs from parent and is strictly better than both parent
and no-op by terminal outcome, or by at least 0.02 observed discounted reward
within an equal outcome class.

## Timing evidence

Independent play/wait classification produced:

- play: 15 roots;
- wait: 3 roots;
- inconclusive: 6 roots.

All three wait roots are slow-push, one at each warmup. In every case no-op
wins while the retained parent placement loses. This is a consistent timing
defect and is excluded from the frozen-timing card/location repair.

## Outcome-class corrections

Several random roots contain alternatives that win while parent and no-op both
lose, including actions 36, 1971, and 1926 at different phases. Bridge-pressure
roots contain multiple wins and losses, allowing within-win card/location
ranking. Reactive-defense roots are uniformly losses with improvements below
the margin. These distinctions were invisible to the discarded dense-only
label contract.

Next authority is the 21-root held-out collection at warmups 20, 34, and 48.
Training remains prohibited until it is fully terminal, duplicate-free, and
exact-input-disjoint from all 24 roots above.
