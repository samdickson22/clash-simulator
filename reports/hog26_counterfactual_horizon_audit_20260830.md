# Hog 2.6 counterfactual horizon audit

Decision: reject 24-decision and 128-decision labels as policy-improvement
authorities. Require first-terminal branch returns before another fit.

## Why this audit was required

The 24-decision strategy-proposal corpus passed offline gates twice, first with
six accepted train roots and then with 61 unique accepted roots. Both trained
policies regressed the unchanged paired gameplay matrix while preserving the
parent's play cadence. This isolated the remaining mismatch to conditional
card/tile labels rather than timing.

## 24 versus 128 decisions

Nine roots were rerun with identical histories and identical 12-action
candidate sets at a 128-decision horizon.

- identical best action: 2/9;
- 24-decision winner still beat the parent at 128 decisions: 5/9;
- mean 128-decision rank of the 24-decision winner: 5.56/12;
- four short-horizon winners became worse than the parent.

The exact root results were:

| Root | H24 best | H128 best | H24 winner rank at H128 | Beats parent at H128 |
|---|---:|---:|---:|---|
| w013 bridge | 172 | 172 | 1 | yes |
| w027 bridge | 1368 | 1224 | 9 | no |
| w041 bridge | 212 | 212 | 1 | yes |
| w013 balanced | 1971 | 172 | 2 | yes |
| w013 split | 172 | 1971 | 6 | yes |
| w027 spell | 1395 | 1944 | 4 | no |
| w027 split | 211 | 1854 | 8 | no |
| w041 balanced | 1386 | 823 | 8 | yes |
| w041 split | 1386 | 1806 | 11 | no |

## Terminal-scale continuation

The three bridge-pressure roots were rerun at 512 decisions. All 12 branches
per root reached a first terminal.

| Root | H24 best | H128 best | H512 terminal best |
|---|---:|---:|---:|
| w013 bridge | 172 | 172 | 1854 |
| w027 bridge | 1368 | 1224 | 1224 |
| w041 bridge | 212 | 212 | 1800 |

Only one of three 128-decision winners remained terminal-best. Horizon 128 is
therefore better aligned than horizon 24 but still not an acceptable label
authority.

## Exact terminal early stop

The generic rectangular collector originally simulated all 512 decisions even
after every branch had terminated. Chunked collection now stops when every
branch has reached its first terminal, then pads post-terminal reward/done rows
with exact zeros before reduction so the declared-horizon floating-point
reduction order is unchanged.

On w013 bridge:

- fixed horizon: 512 decisions, 1490.082 seconds;
- early stop: 416 decisions, 723.561 seconds;
- speedup: 2.059x;
- candidate set, parent action, rankings, and every serialized return row:
  bit-exact.

Focused validation: Ruff clean, module mypy clean, and five counterfactual
teacher tests passed. Commit: `b8c3675a`.

## Next gate

Collect terminal-aligned train and replay-disjoint validation roots only at
productive play phases 13, 27, and 41. Preserve the parent hazard timing gate,
train same-mode complete-action preferences once, and require the unchanged
seven-opponent paired gameplay matrix before any broader evaluation.
