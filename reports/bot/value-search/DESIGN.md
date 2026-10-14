# Value-search: better leaf evaluation for K4S-st (exploration)

2026-10-14, bot-lead implementation sub-agent. Exploration tier: no preregistration.

## Problem
K4S-st scores each candidate with 160-tick scripted rollouts (`rollout_e1`) and the
hand-written leaf potential phi (`engine-rs/src/leaf.rs`). The best-vs-second gap is
~0.0005 phi units (search-scaling/RESULTS.md), and more compute along any rollout axis was
neutral or harmful. Hypothesis: the leaf evaluator is the bottleneck.

## Plan (cheapest convincing first)
1. **Leaf access.** `NativeScripts.rollout_commands(...)` returns `(phi, events, sim)` with the
   leaf state. Check that it reproduces `rollout_e1` bit for bit for plays and WAIT (and how
   timed waits 2401/2402 map), so the only change in a variant is the leaf value.
2. **Data.** Play K4S-st vs {R3a, v1} on a *fresh bank* (not HEADLINE) and dump, at every
   searched decision, features of the public search root (`R.root`, built from public info +
   a belief sample: fair) plus, for a subset, the leaf states of the rollouts; attach the final
   outcome. Features: phi's 7 `evaluation_parts`, elixir both sides, tick/time left, tower HP,
   per-side board summaries from `BattleState.snapshot()`.
3. **Fit.** (c) logistic regression of outcome on phi parts (+ tick interactions);
   (a) small MLP / GBM on richer features. Split by game; report held-out log-loss/AUC vs
   phi alone.
4. **Deploy.** Leaf value = fitted logit converted to phi units (divide by the slope of a
   phi-only logistic fit), so the frozen WAIT bonus (0.01·…), the |x|<2 terminal rule and
   ties keep their meaning. Terminal leaves keep ±2. Variants: `V` at the 160-tick leaf,
   phi+V mixes, and shorter rollouts (80 ticks + V).
5. **Judge.** HEADLINE-v1, 300 cases, vs R3a and v1, both engines, paired vs K4S-st by case
   (bot/eval/pair_by_name.py). Report CPU s/decision.

Fair information: V sees only the planner's root/leaf (public info + sampled hidden hand);
outcomes are used only as training targets. The data bank is disjoint from HEADLINE.
