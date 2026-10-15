# Learned rollout opponent inside K4C-r16: design (exploration)

2026-10-14, bot-lead implementation sub-agent. Exploration tier, not preregistered. Log: [PROGRESS.md](PROGRESS.md).

**Hypothesis.** K4C-r16's 160-tick rollouts use three scripted opponents. Against our bot they play alike (about
2.9 elixir at play), while real opponents differ sharply (v1 about 7.6, R3a about 4.2;
[opponent-model/RESULTS.md](../opponent-model/RESULTS.md)). A rollout opponent that imitates a real policy should
fix the scorer's opponent model.

**Rollout.** `bot/search/lopp.py` `batch_rollouts` drives the native Rust clone from Python with
`BattleState.clone/step` and `NativeScripts.select_action/apply_discrete/evaluate`:
- It uses the `rollout_e1` loop: capacity-1 channels, command delay 27 for both sides, own `balanced` every
  10 ticks, 160 ticks, leaf = the native `phi`.
- All candidates of a decision run in lockstep, so the learned opponent's forward pass is batched.
- With a scripted opponent it must equal `rollout_e1` bit for bit. This is checked on real roots
  (`lopp_check`) and end to end: arm `K4L-X` must reproduce K4C-r16's `command_sha256`.

**Learned opponent.** A numpy MLP over native `public_view` + `public_mask` of the opponent's own seat.
- **Inputs:**
  - a 9×16 cell grid of own/enemy troop and building value;
  - towers, elixir and tick phase;
  - hand card embeddings.
- **Heads, in order:**
  1. play gate;
  2. card among the legal hand slots;
  3. tile among the slot's legal tiles.
- **Gate:** the calibrated threshold (the train-set play rate, as R3a), or sampled with common random numbers
  across candidates (`gs`).
- **Card and tile:** argmax.
- **Cadence:** every 5 ticks when its channel is free, which is the real players' poll cadence.
- **Fairness:** the opponent sees only what the planner's root contains (public reconstruction + sampled hidden
  hand).

**Data.** `lopp_record` plays K4C-r16 vs R3a and vs v1 on the FIT bank (BASE 2249738988533344), cases 0–599.
- At every free poll of the opponent, it records native `public_view`/`public_mask` of the opponent's seat and the
  action taken.
- The Rust state comes from `Resources.root` on the opponent's own Information, which is the same
  reconstruction the planner uses.
- Recording does not change the games (`command_sha256` equal to the earlier FIT-bank games).
- Validation = cases with index % 10 == 9.

**Arms** (`K4L-*`; candidates, S-default and timed-wait bonus as K4C-r16):

| arm | scoring |
|---|---|
| `X` | frozen 3-style mean, all rollouts by the Python loop (exactness) |
| `M<pct>` | frozen mean s on the work set (WAIT, timed waits, top-8 by coarse) → (1−w)·s + w·L |
| `R` | balanced coarse scan; work set scored (balanced + L)/2 (pressure/defense replaced by L) |
| `L` | learned opponent only, every candidate (no coarse/refine split) |
| modifiers | `m<model>` (pool / R3a / v1), `gs` sampled gate, `h<N>` learned for N ticks then scripted balanced, `i<I>` cadence |

**Protocol.**
1. Screen in ours on HEADLINE cases 0–299 vs R3a and v1, paired vs K4C-r16's games (`bot-headline-r16-ours`).
2. Arms with a pooled gain of at least +0.02 go to RoyaleSim (R3a, v1, rext-bc; vs `bot-headline-r16-rsim15535`).
3. Then a fresh bank (new `os.urandom` BASE recorded before any result; 1,200 cases per opponent, both arms).

Win = 1, draw = 0.5, loss = 0, with 95% bootstrap CIs. CPU = process time in `act` per searched decision, and
rollouts per decision.
