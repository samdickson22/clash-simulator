# Opponent model inside K4C-r16's rollouts: design (exploration)

2026-10-14, bot-lead implementation sub-agent. Exploration tier, not preregistered. Log: [PROGRESS.md](PROGRESS.md).

**Hypothesis.** K4C-r16 scores WAIT, the timed waits and its top-8 coarse plays by the *mean* of three 160-tick
`rollout_e1` values, one per scripted rollout opponent (balanced / pressure / defense; every other play gets only
the balanced coarse value). Those scripted opponents are bots our search beats ~100%, so the rollout opponent may
be mis-specified for real opponents, and the equal-weight mean may be the wrong reduction.

**Code.** `bot/search/oppmodel.py`, names `K4O-<tokens>` in `make_player`. It re-implements the single-thread,
no-deadline path of the frozen `s1/anchor.anytime` (the only path K4C uses) with a pluggable reduction. Candidates,
rollout order, coarse balanced scan, top-8 refine, timed-wait bonus, tie-breaks and the S-default are unchanged.
`K4O-mean` uses the frozen arithmetic and reproduces K4C-r16's `command_sha256` (20/20 games, `bot-opp-eq`).

| arm | token | reduction |
|---|---|---|
| A0 | `K4O-mean` | frozen mean (= K4C-r16) |
| A1 | `K4O-min` | min over the 3 styles (pessimistic) |
| A2 | `K4O-w<b>.<p>.<d>` | fixed weights; weights fit on outcomes by a grid on a separate FIT bank (BASE 2249738988533344), never on HEADLINE. Zero-weight styles are not rolled out. |
| B | `K4O-inf…` / per-opponent weights | online inference from the opponent's public plays (elixir at issue, placement depth) |
| C | `K4O-x<pct><style>[d<D>][i<I>]` | extra rollout opponent from `NativeScripts.rollout_commands` with a slower opponent (command delay D and/or decision interval I ticks); no Rust change. Timed waits 2401/2402 get the base style's value plus that spec's WAIT residual. |

**Protocol.** Screen in our engine on the FIT bank (R3a, v1; 300 cases each), paired vs K4O-mean on the same cases.
The selected arm(s) then run HEADLINE-v1 cases 0–299 vs R3a, v1 in ours, paired vs K4C-r16's existing games
(`bot-headline-r16-ours`). Arms ≥ +0.02 go to RoyaleSim 15.535 (R3a, v1, rext-bc; vs `bot-headline-r16-rsim15535`),
then to a fresh bank (new `os.urandom` BASE recorded before any result; 1,200 cases per opponent vs R3a, v1,
rext-bc, arm and K4C-r16). Win 1, draw 0.5, loss 0; 95% bootstrap CIs (4,000 draws); "both"/"pooled" = equal
weight over opponents, cases resampled within opponent. CPU = candidate process time inside `act` per searched
decision (load-dependent; compare within a run) and rollouts/decision (load-free).

**Fairness.** Arm B uses only public opponent card events and the opponent's exact elixir, both opponent-derivable
(fair-information rule).
