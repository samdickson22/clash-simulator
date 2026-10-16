# Training / teacher fix plan for the hoarding and elixir-dump policy (bot lead live-diag, exploration tier)

This file is the plan, scoped to what we would A/B in the next ~24 h. Evidence is in [RESULTS.md](RESULTS.md).

## Why a back Giant or a banked Fireball loses to cheap bridge chip

The K4L-R score for a candidate is (balanced scripted rollout + learned-opponent rollout)/2 over **160 ticks (8 s)**, plus the
timed-wait bonus. Both rollouts end in the same leaf potential, phi (`engine-rs/src/leaf.rs`):

    phi = 0.55·crowns + 0.25·princess_pressure + 0.10·king_pressure + tiebreak − 0.20·early
        + 0.08·board + 0.12·danger + elixir_weight·0.08·(own − enemy elixir)/16

How each candidate scores at the leaf:
- **A bridge MiniPekka or Minions can reach the tower within 8 s.** It scores through princess_pressure (weight 0.25 on tower HP lost) and danger
  (ETA to a tower).
- **A back Giant has not reached the bridge at 8 s.** It scores only as board value (0.08 × cost-share × HP), against −5 elixir.
  Elixir is worth 0.08/16 = 0.005 per point, so the −5 costs 0.025. Its damage lands after the horizon.
- **A banked Fireball scores nothing while held.** The leaf has **no term for cards in hand or for cycle position**. Casting it pays only for what dies, or for
  tower damage, within 8 s. The opponent's elixir **is** in the leaf (exact elixir is fair), so that is not the gap.
- **Elixir is the only thing the leaf banks**, at 0.005 per point. That is too cheap for 3–4 elixir to outweigh one chip hit, so search
  spends ~9 elixir in the first second and meets the Giant at ~3 (RESULTS §3). The -gf result confirms this: Giant and Fireball get learned
  values and still never win, so the leaf and horizon are the cause, not candidate pruning.

## What was tried before (and why it didn't stick)

- **Learned leaf value** (`reports/bot/value-search/RESULTS.md`; `bot-value-screen1–3`, `bot-value-fit1`, `bot-value-models` on 03/04/08):
  - Results: replacing phi with an outcome-fitted V (linear or MLP, AUC ≈ phi's 0.80) cost −26 to −43 pp paired. Blending at λ = 0.25 was null
    (+0.003 [−0.057, +0.063]).
  - **Cause: confounding.** On-policy outcome data makes elixir and board co-vary, so V put a *negative* weight on own elixir and re-ranked
    about 25% of decisions on spurious terms. More games would not fix the sign. That study recommended action-conditioned targets instead.
- **The corpus-pretrained RL critic** (EV ~0.5 vs RL r3's 0.23; `bot/rl/critic_pretrain.py`, exit PROGRESS):
  - It is a state value on it5s2-behaviour v5 packets, so it carries the same on-policy confounding.
  - It cannot read a native rollout leaf: clasher_core has no v5 encoder, so it would need a Python packet path at ≥3× CPU.
  - Not usable as a leaf in the next 24 h.
- **Horizon:**
  - K4S-h320 hurt (−0.062 [−0.107, −0.017]): 16 s of scripted play inside the rollout diverges from real opponents.
  - Here, K4L -h240 was null (+0.015 [−0.034, +0.064]), as was -h240-gf.
- **Elixir weight:**
  - phi ew ×0.5 and ×2 were null; ×4 hurt (value-search).
  - K4L -ew30 here: −0.039 [−0.098, +0.015]. It plays more Giants (0.62 a game) but worse.
  - A global price on elixir is the wrong shape.

## Candidates for the next 24 h (ranked)

1. **Outcome-fitted reserve term (`-res` family).** This is the only arm that moves the mechanism: elixir at the Giant's cross goes
   2.95 → 3.54, with no per-opponent loss on bank 1, +0.015 [−0.034, +0.064].
   - **What it is:** a penalty on *non-defensive* plays (no enemy unit on our half) that leave elixir below R, where R is derived from the deck's
     cheapest ground answer. It is a state-conditional exchange rate, unlike ew, which applied a global one.
   - **Fitting λ from outcomes instead of hand-setting it:** run λ ∈ {0.0075, 0.015, 0.03} (and R, R+1) on the now-used bank 1 as a dev bank, pick the best
     pooled arm, and confirm on a NEW fresh bank. Bank 2 is in use for the λ = 0.015 confirmation.
   - **Data and compute:** about 4 arms × 204 games (≈ 50 core-hours, ~45 min on 04 + 08 at 16 workers each), then 2 × 408 confirmation games (~45 min).
   - **Hosts:** 04/08, or 03/01 when the full-pool owner frees them.
   - **Relabel: not needed for live.** Search decides 100% of live moves (RESULTS §1). The rl5 fast tier only polls, and serves as the
     cutoff default that never fires. So -res deploys as a search-tier change.
   - **Full-pool student:** its G1 teacher is K4C-r16. Switching the teacher to K4L-res means relabelling G1 (bot lead's decision). The full-pool student
     hoards like its teacher (rl5 alone plays 0.07 Giants a game), so relabel only after -res confirms.
   - **Pin fit:** pure Python. It is the same insertion in `lopp.reduce_learned` and in the deployed `lopp_fast.reduce_fast` (after its
     `_bonus` loop), so it is independent of r1-total / r3 / live16402c. It is re-checked on the live16402c root at the A/B, and it adds about 1 µs per key.
2. **Action-conditioned leaf correction:** the value-search recommendation, scoped down.
   - **Target:** at ~2k live-like roots (sim_diag, live deck), record paired continuations to game end for "dump" (best cheap non-defensive play) vs
     "bank" (best wait), played by the real players.
   - **Model:** fit a small correction on leaf features that phi lacks: own hand cost/composition, elixir, enemy elixir, time, whether a threat is on our half.
     Use it as an additive term on the leaf (≤ 0.02).
   - **Data:** each root costs 2 full games (~2 min of CPU), so 2k roots ≈ 130 core-hours, about 4–5 h on 2 hosts at 16 workers.
   - **Fit and A/B:** 1 h to fit plus 1.5 h for a fresh-bank A/B. **Realistic ETA ~8–10 h; it does not fit 24 h comfortably if
     hosts stay contended.** No relabel for live, and the same pin story as (1).
3. **Longer horizon, cheaper rollout.** Not recommended now. h240 is null and h320 hurts, so the bottleneck is the leaf, not reach.

**Not in 24 h:** a critic leaf (needs a native→v5 encoder and is confounded), or a full teacher retrain.

## Honest ETA to a fresh-bank A/B

- **-res at λ = 0.015 on BASE2:** running (`ab5/`), results ~19:35Z.
- **Outcome-fitted λ/R** (candidate 1): grid on the bank-1 dev bank ~45 min, then confirmation on a new bank ~45 min. About **2 h** from the
  go, given ~32 free cores on 04/08.
- **Action-conditioned correction** (candidate 2): about **8–10 h**.
