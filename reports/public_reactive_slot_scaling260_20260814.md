# Public card-choice scaling gate at 260 games

Date: 2026-08-14

## Decision

Reject both the linear mechanics adapter and the new 38,129-parameter direct-public
reactive scorer on this development prefix. Neither produces a repeatable external
validation gain. Do not promote, materialize a gameplay policy, or use the direct
reactive scorer as an RL initializer.

This result does not consume the final 1,000-game gate. It is an architecture-scaling
screen on the first 260 completed replays while the production collector continues.
If this prefix is used to choose a replacement architecture, it must be reserved from
the final selection/evaluation partitions.

## Frozen split

The replay/deck/archetype/chronology splitter retained 200 of the first 260 source
replays after the complete-visible-hand filter:

| Split | Replays | Placement rows |
| --- | ---: | ---: |
| train | 117 | 1,337 |
| validation | 34 | 326 |
| held-out archetype | 37 | 626 |
| later chronology | 12 | 222 |

The split has zero replay overlap, zero conservative deck-signature overlap, and zero
held-out-archetype/train overlap. Split-manifest SHA-256:
`69921129b879cb67fcd6151169c7059c338f192e0f8a44716a6b34b8ee34f778`.
Confidence-aware sidecar-manifest SHA-256:
`fc0bfd6a70575d273d813e31a3e759cc72ac5793249b48c0c765d976b3bb6c97`.

## Linear mechanics adapter

The final-gate protocol was repeated without modification: three simulator-pretrained
linear seeds, three guarded five-epoch human fine-tunes, 0.005 blend increments, at
least one point of human-validation gain for every seed, and at most 1% disagreement
on both disjoint simulator guard sets.

Only source seed 1055411 passed its individual fine-tune gate. Seeds 1055410 and
1055412 did not. Neither the zero-shot nor fine-tuned family had a cross-seed-safe
alpha. Selection SHA-256:
`bef58227fdbb8d05247cb627d24465b5fb66a0585aa67fd2bc6119f962902169`.

Equal-weight parameter averaging was then tested as one predeclared variance-reduction
alternative. It is deterministic, card-name-free, and averages all three source seeds
rather than selecting a favorable seed. It also failed:

| Arm | Best simulator-safe alpha | Human validation | Incumbent | Validation disagreement | Held-out disagreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| zero-shot mean | 0.135 | 38.96% | 38.34% | 0.67% | 0.92% |
| fine-tuned mean | 0.140 | 38.96% | 38.34% | 0.67% | 0.92% |

Both arms gained only two net examples out of 326, below the four-example one-point
gate and too weak to justify gameplay mutation. Sweep SHA-256 values are
`6f62bc836aa06288a42bd147b22e97360cbbe99c69982dfe16cec5e466783ebe`
and `404647ca5b6d7c3e95bf35132f5e4c07777ce3ad8550b7fa0edce6e2c1126526`.

## Direct-public reactive scorer

A separate 38,129-parameter probe removed the frozen incumbent-state bottleneck. It:

- reads all confidence-masked public entity features directly;
- combines data-derived static mechanics with a learned identity residual;
- mean/max pools entities with a permutation-invariant DeepSets encoder;
- scores the four hand candidates with a shared permutation-equivariant head; and
- is purely reactive, with no timing or placement model.

Three fixed seeds used the same architecture and schedule. Internal training epoch was
selected without the external validation, held-out-archetype, or chronology splits.

| Seed | Selected epoch | Train | External validation | Held-out archetype | Chronology |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1056400 | 2 | 38.51% | 36.50% | 42.97% | 33.78% |
| 1056401 | 7 | 41.53% | 34.36% | 39.62% | 40.99% |
| 1056402 | 6 | 42.25% | 32.21% | 39.30% | 35.59% |
| incumbent | -- | -- | 38.34% | 38.34% | 35.59% |

The seed improvements on held-out archetypes or chronology are not repeatable and come
with validation regressions. Equal-logit ensembling worsened external validation to
30.37% (held-out 38.82%, chronology 40.99%). Checkpoint SHA-256 values:

- seed 1056400: `d179ef480aab51aad88e4459ffb1b6ae1aebf1bdada2e745b1aeddf6968a5f78`
- seed 1056401: `20576c8d6752a62a07e5d3ee81bfee1d6de8a905dfe67fc01b1b37f529dd10e1`
- seed 1056402: `7f3560eaca0942766e0d653f5d59a6ba683b76e2ceee93034a7c61e73262cbf9`

## Interpretation and next action

Human replay card choice is multimodal: lower conditional cross-entropy has repeatedly
failed to improve exact held-out top-1 choice. The first 260 games therefore do not
support replacing or globally blending the incumbent card selector. More epochs,
hidden width, or alpha search would be unprincipled follow-up tuning.

Continue the final confidence-aware collection and retain the final human partitions
as no-regression evidence. In parallel, decouple the bounded diversified PFSP pilot
from mechanics-adapter promotion: outcome-based league learning from the accepted
confidence-aware parent is the next useful causal test. Human imitation should remain
a rehearsal/evaluation constraint unless the final corpus produces a repeatable
held-out gain.
