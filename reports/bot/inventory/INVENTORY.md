# Bot inventory: strongest bots, the paired harness, engine calls, and `bot/players/`

Written 2026-10-13 by the bot-lead research sub-agent on 127x05. This is read-only research; there are no commits.
- Code lives in `bot/players/`.
- The smoke receipts are `reports/bot/inventory/smoke-b48-1200*.json`.
- The progress log is [PROGRESS.md](PROGRESS.md).
- All `file:line` references are to the `bot/lead` worktree (commit dbf31faf5), unless marked **[untracked]**. Untracked files are in the main checkout only, or in the runtime root R below.

**Runtime root R** = `/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1` on 127x05 (592 MB, read-only for us). It is the Mac E4 v3 runtime and carries exactly the X4S pins:
- native `clasher_core.abi3.so` 44874fd6…;
- `main02.pt` = v1, d77005d5…;
- `R3a.pt` = 37509a43….

It also holds the files git lacks:
- `src/clasher/analysis/loss_review/{delay_fixes,search_ab,tempo,…}.py`. These are untracked in `/mpac/sdicks02/repos/clasher` too, and byte-identical there.
- `reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json`, the deck prior and belief prior;
- `student-source/exit_r3`, which holds the R3a network class.

Everything else that matters is byte-identical to this worktree. I checked 21 key files with `cmp`.

---

## 1. Ranked strongest playable bots

"Loss" means the bot loses to the **v1 policy**, the standard opponent. Draws count as non-losses, and there were none in any study below. All rows come from the same harness family (§2), with 600 fresh paired seeds per arm unless noted. Each seed fixes:
- the decks;
- the seat;
- the shuffle.

Settings shared by every row:
- 5 decks giving 25 matchups;
- alternating seats;
- symmetric command lag d = 27 ticks and capacity 1;
- 5,000-sample paired-seed bootstrap, 95% CIs.

A "win rate" is about 100 − loss.

| # | Bot (config) | Best measured loss vs v1 | n / seeds | Study |
|---|---|---|---|---|
| 1a | **K4-200**: 4-thread anytime W-screen8, WAIT-first, v1 sample if nothing completes, 200 ms | **18.50% [15.33, 21.50]**; with honest lateness, also 18.17% (V200) and 19.33% (K4) | 600 / 4503604807370496+[0,600) (X4S); 4503601407370496+[0,600) (K) | `reports/explore/x4s/RESULTS.md:9-12`, `k-v2/RESULTS.md`, `k-anytime/RESULTS.md:9-11` |
| 1b | **K4S-200** (= K4 + S-default, R3a cutoff default) | 20.67% [17.50, 23.83]; 18.17% at 160 ms; 17.2% at 180 ms. K4S−K4 pooled at 1.0× is +0.6 pp [−0.8, 2.2] (ns) | 600 (X), 1,668 pooled X+G | `x4s/RESULTS.md:9`, `x4s2/RESULTS.md:107` |
| 1c | **KU**: the same W-screen8 scorer with **no deadline**, 1 thread. Deterministic, and the "ceiling" | **19.33% [16.17, 22.50]** (KU had no deadline, so no lateness was charged) | 600 / 4503601407370496+[0,600) | `k-anytime/RESULTS.md:11,29` |
| 2 | **K4S at slower cores** (budget-equivalent 140/120 ms) | 22.2% / 26.0% (X4S); 22.1% at K4S-120 over 1,167 seeds (X4S-3) | 600 / 1,167 | `x4s/RESULTS.md:11-12`, `x4s3/RESULTS.md:21` |
| 3 | **K2-200** (2 threads) | 25.00% (K2), 29.00% (S1) | 600 | `k2/RESULTS.md`, `s1/RESULTS.md:15` |
| 4 | **S-200**: 1 core, coarse-first W, R3a as top-8 proposer and cutoff default | 28.17% [24.67, 31.67]; 26.6% in X4S-3 | 600 / 1,167 | `s1/RESULTS.md:12`, `x4s3/RESULTS.md` |
| 5 | **K0 / K0c-200** (1 core, v1 or cached-v1 default) | 43–47% | 600 | k-anytime, k-v2, x4s |
| 6 | **v1 policy** (main-2026100802 step 22552). This is the opponent itself | ≈50% by symmetry. Gate (c): P16 49.7% vs 17.2%; H2H 66.4% vs s2902 | – | `imitation/RESULTS-gate-c.md:9` |
| – | **R3a student alone** (no search) | **Never measured vs v1.** R3 Stage 2 was skipped after Stage 1 KILL | – | `strategy_council_20260928/imitation/exit-r3/RESULTS.md:47-49` |

### Readings
- **Strongest:** K4-200 ≈ K4S-200 ≈ KU, at about 18–21% loss, i.e. roughly 80% wins vs v1. All three run the same W-screen8 scorer; they differ only in how cutoffs are handled.
  - On held-out opponent decks (G population, 1,068 seeds) K4-200 is 26.7% and K4S-200 is 26.4% (`x4s2/RESULTS.md:81`).
  - Separately, W-screen8 (KU) vs the *baseline search* is 19.33% vs 50.83% for baseline-vs-baseline (`w-screen8/RESULTS.md:7-9`).
- **Most robust:** K4S, i.e. the S-default. It removes the WAIT-spiral cliff once compute is short: K4-120 loses 89%, K4S-120 26%.
- **Student variants:**
  - R3a-rep, R3a-rep2, R3a-rep3 and R4-D all sit within about 1–2 pp of R3a (X4S-3/3b; σ_fit ≈ 0.6–0.8 pp).
  - R5/R5-rep/R5W (X4S-4, on-policy labels) were mid-run on 2026-10-14 and are **not cited**.
  - SD1 = R3a remains the frozen default.
- **Excluded:** K4S-confirm, T1 and TIERS outcomes are sealed. They were not read, and none are cited here.

### Exact sources (frozen X4S arms; harness `reports/explore/x4s/run.py`)

**Arm table:** `x4s/plan.json` "arms".
- K4: `kernel: K4-anytime`, `policy: v1-unmodified`, `threads 4`, `deadline_seconds 0.2`.
- K4S: `kernel: K4-anytime-sdefault`, `policy: R3a-cached`.
- Shared: `coarse_horizon 160`, `return_reserve_seconds 0.008`.

**Player construction:** `x4s/run.py:54-76` `make_player()`. The class stack, top-down:
1. `x4s/sdefault.py:30-36` (S-default rule `apply_default`, :15-27);
2. `s1/anchor.py:167-192` (`anytime()`, :19-164);
3. `e1/planner.py:81-111`;
4. `w-screen8/planner.py:12-109`;
5. `clasher.analysis.loss_review.search_ab` [untracked];
6. `delay_fixes.planner_class` [untracked, :112-168];
7. `search-noise-s6/delay.py:75-143` `DelayAwarePlanner`;
8. `src/clasher/rl/c56_rollout_planner.py:50` `C56RolloutPlanner`.

Public player wrapper: `engine-speed/stage5/fair_player.py:161-179` `PublicPlanner`, with `p.belief.__class__ = s1/belief.py:Belief`.

**Flags** (run.py:69-75):
- `C56SearchConfig(threads=1, horizon=160, wait_screen8=False)`;
- `command_delay=27, delay_aware=True, symmetric_opponent=True, opponent_delay=27, opponent_interval=10, opponent_capacity=1, max_outstanding=1`;
- `arm='W', variant='screen8'`;
- `search_threads=4, coarse_horizon=160`.

**Seeds:**
- search seat `seed+100000` (planner) and `+1` (core rng);
- belief rng `seed+100001`;
- policy pollers `seed+271828+seat`.

**Policy and student loading** (`run.py:27-51`):
- `imitation.model.load_policy(main02.pt)`, checked as temperatures [1,1,1];
- `s1/proposals.py:71-78` `load_student(R3a.pt, threshold=0.5005528330802917)`, wrapped by `s1/cached_policy.py:CachedPolicy`;
- `e1/policy.py:V1Policy`, which wraps `imitation/evaluation/standalone.py:StandalonePlayer`.

### Checkpoints (sha256 computed this session)

| Artifact | SHA-256 | 127x05 (usable now) | Fleet copies |
|---|---|---|---|
| v1 (main-2026100802 s22552) | d77005d59d6ed40c… | `R/main02.pt` (36 MB) | 01: `/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013/inputs/main02.pt` and `x4s3-student-scale-20261012/inputs/` |
| R3a = SD1 | 37509a4331bd02ae… | `R/R3a.pt` (36 MB), calibration `R/R3a-calibration.json` | 01: same inputs dirs |
| R3a-rep / -rep2 / -rep3 / R4-D | 8d537a78… / 72d73375… / 43621ce4… / 99813802… | – | 01: `x4s3b-fitseed-20261013/inputs/` |
| native clasher_core (e1 rollout build) | 44874fd6047aa53f… | `R/native/clasher_core.abi3.so` | – |

127x04 `/mpac/sdicks02/repos/clasher-checkpoints/v2/` holds only main-2026100821/t11 runs, not main-2026100802. No copy to 05 is needed.

---

## 2. The paired evaluation harness (K-v2 / K2 / S1 / X4S): minimal loop

Source: `reports/explore/x4s/run.py:79-282`. `s1/run.py` and `k2/run.py` are the same loop with fewer arms.

**Match construction**
- **Physics: our Python engine.**
  - `engine-rs/stage2_matches.py:63-73` `battle()` builds `clasher.battle.BattleState(players=[PlayerState(deck, hand=deck[:4], cycle_queue=deck[4:])], rng=random.Random(seed))`.
  - Levels are the defaults: card level 11, towers level 11, king 4,824 HP and princess 3,052 HP (`src/clasher/player.py:31-37`).
  - Elixir starts at 5. Matches end at game over or at `max_ticks` 6001.
- **Card pool: C56.** That is the 56 cards in `engine-rs/c56_controller.py:CARDS`, all at level 11; the native model refuses anything else (`c56_rollout_planner.py:94-96`).
  - P16 is used only by the imitation gate (c), not here.
- **Decks.** For each archetype in (bridge_wincon, siege, beatdown, bait, chip), take the most frequent human deck in `human_deck_catalog.json` (`run.py:304-307`):
  - bridge_wincon: Cannon, Fireball, HogRider, IceGolem, IceSpirit, Log, Musketeer, Skeletons;
  - siege: Archers, ElectroSpirit, Fireball, Knight, Log, Skeletons, Tesla, Xbow;
  - beatdown: Arrows, FireSpirits, Giant, HogRider, Knight, Minions, Valkyrie, Wizard;
  - bait: BlowdartGoblin, Cannon, GoblinBarrel, IceSpirit, Princess, SkeletonArmy, Valkyrie, Wallbreakers;
  - chip: DarkPrince, ElectroSpirit, Log, Miner, Rocket, RoyalDelivery, Skeletons, Tesla.
- **Index i → case** (`run.py:313`, `:95-100`):
  - seed = base+i;
  - bot seat = i%2;
  - own deck = X[i%5], opponent deck = X[(i//5)%5];
  - one `random.Random(seed)` shuffles own, then other;
  - `decks=[own,other]` if seat 0, else `[other,own]`.
- **Abilities** are disabled for both sides: action 2305 is never submitted.

**Per-tick loop** (`run.py:156-249`)
1. Complete due commands: `CommandQueue.ready(tick)` → `space.apply_action`. The engine validates again at execution time; a rejection is recorded and is not refunded, since no debit happened. On acceptance, `PublicEvent(tick,'card',card)` is added to the opponent's event list.
2. From tick 90, every 5 ticks, for each seat:
   1. `observe()` (`fair_player.py:31-35`) builds `Information`: the v5 public packet via `builder.build_public(battle, seat)`, own HUD (elixir/hand/cycle/refill), and the accepted enemy card events.
   2. `ch.own_packet()` applies own unexecuted reservations (`delay_fixes.py:89-104`).
   3. Every seat's policy is polled every 5 ticks, **even when blocked**, because StandalonePlayer enforces the cadence (`standalone.py:20-21`). The poll's action is the v1 player's move and the search seat's fallback.
   4. If the channel is busy, a timed wait is running, or the seat is late, skip.
   5. A v1 seat submits its sample. A search seat acts only at `tick%10==0`:
      - `belief.update`;
      - optional student proposals → `coarse_order`;
      - `core.candidates`;
      - `belief.sample` (hidden opponent hand/cycle/RNG);
      - `R.root()` (`fair_player.py:111-158`, a clasher_core state from public info plus the sample);
      - `core.score_candidates(root, …, deadline, fallback)`;
      - submit the play, or set `waits = tick + selected_wait_ticks` for a timed WAIT (2400/2401/2402 = 10/20/40 ticks).
3. `b.step()`.

**Lag (latency model)**
- `CommandQueue(27, capacity 1)` (`delay_fixes.py:33-109`): a play is reserved at decision tick t and executes at t+27.
- **Symmetric:** the search's internal model assumes the same 27-tick delay for self and opponent (`opponent_delay=27`, `opponent_capacity=1`).
- **Honest lateness** (`s1/latency.py:5-15`): if a decision's wall time exceeds the deadline, overrun ticks = ceil(overrun × 20). They are added to the reserved command's due tick and to the wait end, and the seat is unavailable until then. The v1 opponent has no deadline and is never charged.

**Scoring**
- `loss = winner is not None and winner != seat`. Draws are separate.
- The bootstrap resamples paired seeds (all arms of one seed together), 5,000 resamples, percentile 95% CIs.
- Per-game JSON also records `command_sha256`, the per-decision `deadline_stats` and the latencies.

**Wall-clock dependence vs node budget**
- Wall-dependent, in timed arms: the 200/160/140/120 ms decision deadline. It covers observation, the poll, belief, candidates, root and rollouts, with an 8 ms return reserve.
  - The **native rollout's own wall check** (`rollout_e1(…, remaining_seconds)`; `e1/stage_native.py`) aborts a rollout at the deadline.
  - Belief preparation is cancellable (`s1/belief.py`).
  - Multi-thread scheduling (K4) and honest lateness also depend on wall time.
  - Cutoff rates therefore depend on host speed and load: X4S-3b saw 55% vs 64% cutoffs at K4S-120 on 03/04 vs 01.
- **Not wall-dependent:** with `deadline_seconds=None`, every step is deterministic given the seed. Evidence:
  - X4S qualification: K4 and K4S no-deadline command hashes are identical;
  - my smoke repeat (§5) gives an identical command hash.

### Deterministic budget-based variant (implemented)
`bot/players/search.py:25-56` replaces the wall clock inside the frozen `anchor.anytime()` with a **virtual clock that counts complete 160-tick rollouts**. It uses `anytime(…, clock=, evaluate=)`, the injection hooks the K tests use, and calls `rollout_e1(…, 1e6)` so the native wall check never fires. Everything else is unchanged:
- the same scorer, phase order (WAIT → timed waits → coarse scan → top-8 refine) and admission (only roots with all 3 styles complete count);
- the S-default rule (`sdefault.apply_default`);
- one thread.

Configurations:
- `SearchPlayer(rt, mode='unbounded', default='R3a'|'v1')`: KU, the frozen W-screen8 result. This is the recommended engine-comparison bot: deterministic and the strongest.
- `SearchPlayer(rt, mode='budget', budget=N, default='R3a')`: deterministic anytime with N rollouts per decision, which emulates slower cores without wall time.
  - A full decision needs about 45 rollouts at 24 candidates (smoke: 44–45, mean 39 over a game prefix).
  - A cut before the coarse scan finishes keeps only wait scores, so use `default='R3a'` (K4S) at small N. K1 shows that WAIT-default collapses to 96% loss.
  - **Mapping N ↔ ms is uncalibrated.** Calibrate by matching X4S cutoff rates (K4-200 4.0%, K4-160 18.6%, K4-140 45.5%, K4-120 88.6%) over a few hundred decisions. Then validate one N against its X4S arm on ~200 paired seeds.
  - Rough guide: one core spends about 4.5 ms per rollout on 05 (smoke: about 200 ms per decision at 39 rollouts).
- `mode='wall', wall_ms=200, threads=4`: the original X4S arms. Lateness is charged and the run is not reproducible.
- Honest lateness applies only when `deadline_seconds` is set, so the deterministic modes are untimed, like KU.

---

## 3. What the search player needs from the engine

The physical game runs in the **Python engine**. The planner's internal model is the **Rust `clasher_core`**: a public reconstruction, never the live battle. Our own harness is therefore already a mild "model mismatch" setting, with the two engines parity-tested against each other.

**Planner calls on `clasher_core`** (K4/K4S/KU path):

| Call | Where | Purpose |
|---|---|---|
| `clasher_core.BattleState(json_payload)` | `fair_player.py:155-158` (`Resources.root`) | Build the root from public entities (via `R.templates`), own HUD, sampled opponent hand/cycle/elixir, and a fresh RNG state |
| `root.clone()` | `s1/anchor.py:45` (threads>1 only) | Private copy per worker thread |
| `NativeScripts.rollout_e1(root, seat, action, style, delay, opp_delay, horizon=160, interval=10, elixir_weight=1.0, remaining_seconds)` | `s1/anchor.py:52`, `e1/planner.py:31` | One complete rollout (see below) |

**Inside `rollout_e1`** (Rust; generated by `reports/explore/e1/stage_native.py` from `engine-rs/src/wait_screen8.rs` `wait_command_simulation`), each rollout:
1. clones the root;
2. queues the candidate with delay 27;
3. every 10 ticks lets the scripted policies act: own `balanced`, opponent `style`, with symmetric delay 27 and capacity 1;
4. steps 160 ticks;
5. returns `phi(sim, seat, elixir_weight)`, the tower HP/elixir potential.

Timed waits (2401/2402) hold own commands for 20/40 ticks inside the same call.

Other native methods exist but are unused on this path: `select_action`, `apply_discrete`, `evaluate`, `rollout_commands`, `score_wait_screen8`, `search_candidates`, `public_mask`, `public_view`. `score_wait_screen8` is the whole W-screen8 batch in one Rust call, used by the live RustPlanner.

**Non-engine pieces (pure Python, engine-agnostic once the v5 packet exists)**
- **Candidates** (`c56_rollout_planner.py:73-89`), producing about 24 candidates:
  - the public action mask (`PublicActionMaskInput.from_confidence_observation`);
  - the scripted `balanced` bot's ranked plays and decision;
  - 16 random legal samples from the planner rng;
  - WAIT plus the timed waits.
- **Belief:** `derived_public_state.DerivedPublicState`. It tracks the opponent's hand/cycle posterior from public card events and the human deck prior, plus the elixir clock.
- **Startup:** `Resources.__init__` (`fair_player.py:39-109`, ~15 s CPU) runs isolated **Python-engine** demos to build the entity templates. So the Python engine stays a dependency even when the match runs elsewhere.

**Consequence for RoyaleSim**
- **Model mismatch (keep `clasher_core` as the planner model):** no planner change is needed. It needs only a public-view translator (§4).
- **RoyaleSim-native planner:** replace exactly two things:
  1. `R.root()` → build a RoyaleSim `Battle` from public state plus the sampled opponent via `reset(..., spawns=…)` or a constructed `load()` blob;
  2. `rollout_e1` → `save()`/`load()` clone, plus `step()` loops with the delayed commands, plus two scripted rollout policies (balanced/pressure/defense), plus a phi evaluator.

  RoyaleSim has no scripted policies or phi, so they must be ported from `engine-rs/src/c56_scripts.rs`/`scripts.rs`. There is also a fidelity question about reconstructing unit internals (attack clocks, targets) from public state, which `fair_player.root` defaults with templates. That is a multi-day port, while model mismatch is about a day of translator work.

---

## 4. `bot/players/` design

### Interface (`bot/players/base.py`)
- `Player.start(MatchContext)` → `Player.act(PublicView) -> Decision(action, wait_ticks, stats)` → `Player.close()`.
- `act` is called every 5 ticks from tick 90 for both seats, including blocked polls (`view.can_act=False`), because the policy cadence needs it.
- Actions are the repo's 2304 own-frame tile actions (slot*576 + row*18 + col) or WAIT=2304. A timed wait is returned as `wait_ticks`.
- `PublicView` holds only fair information:
  - the v5 public packet (raw and reservation-adjusted);
  - own HUD;
  - accepted public events of both seats;
  - own pending reservations.

  Unrevealed opponent cards and RNG never appear in it.
- The harness owns lag (CommandQueue), timed waits and honest lateness: it charges any player with `deadline_seconds`.

### Our-engine adapters (implemented; they wrap existing code)

| Player | Class | Wraps |
|---|---|---|
| v1 policy | `PolicyPlayer(rt,'v1')` (`policy.py:33`) | `e1/policy.V1Policy` → StandalonePlayer, seed+271828+seat |
| R3a student alone | `PolicyPlayer(rt,'R3a')` | `CachedPolicy(STUDENT, 0.50055)` in V1Policy; top-1 legal play if P(play) ≥ threshold, else WAIT |
| Search: K4S / K4 / KU / budget | `SearchPlayer(rt, mode=…, default='R3a'\|'v1')` (`search.py:59`) | x4s/run.py:184-237 body on `PublicPlanner` + `sdefault`/`anchor` kernels |
| Match | `ours.play_match(rt, players, seed, decks, max_ticks)` (`ours.py:34`); `x4s_setup(rt, i, base)` (`ours.py:19`) | x4s/run.py:79-282 loop |
| Runtime | `runtime.Runtime()` (`runtime.py:41`) | Reproduces the x4s import path against R and verifies the 3 pins |

### RoyaleSim adapter (sketch: `bot/players/royalesim_adapter.py`)
Verified in a scratch venv (`/mpac/sdicks02/cache/botinv-royalesim-venv`, royalesim 0.1.34):
- `Battle(card_names, [[0,1,2],[0,1,2]], level=11)` plus `reset(seed, decks_ids, 0, 0, [5000,5000], [[4824,3052,3052]]*2, [])` constructs all 25 X4S matchups.
- Tower HP and the 6,000-tick clock (3,600 regular + 2,400 overtime) match ours.
- Blue (team 0) king is at (9,3) tiles, the same as our seat 0.

Work items:
- **R1 cards (done).** C56 → RoyaleSim: 53 names identical; `Archers→Archer`, `IceGolem→IceGolemite`, `IceSpirit→IceSpirits`.
- **R1 actions (done).** `action_to_command(a, seat)` = tile centre × 18,000 subtiles, with the seat-1 flip (17−x, 31−y).
- **R2 public-view translator (the real work).** Map `state_json` to a v5 packet using `delay_fixes.hypothetical_packet` (`delay_fixes.py:171-223`) as the template; it already projects a native snapshot onto v5:
  - Entity rows: from `entities` + `spells` + `projectiles`, mapping RoyaleSim `unit_type` names to our template names.
  - Entity fields: x, y, own/enemy, kind one-hot, hp_fraction, static columns 23-26 and 30 from `builder.card_stat_features`, and motion from `facing`.
  - Globals: indices 0-5, 8-13 and 17.
  - Hand, next card, and `opponent_seen_card_ids`.

  Also build the own HUD and the public events. Opponent plays come from the commands the harness applied, as `dict(seat,tick,kind='card',name,amount,x,y)`.
  - **Never read** the opponent's `hand`/`next_card`/`deck`/`pending`/`elixir_milli`.
  - Check RoyaleSim's card-refill timing against our `refill` field (1,000/500/350 ms).
  - Check entity-name coverage on a C56 corpus, and fail closed on an unknown name, as `fair_player.root` does.
- **R3 lag.** Keep it harness-side: `set_command_delay_ticks(0,0)` and submit at the due tick, which keeps semantics identical to ours. RoyaleSim's native delay is a separate, testable variant. Do not mix the two.
- **R4 validation.** Run v1-vs-v1 and KU-vs-v1 inside RoyaleSim on the X4S cases, in the deterministic modes. Compare with ours paired by seed: the loss shift is the engine/model-mismatch effect.

**Recommendation:** start with model mismatch (planner on `clasher_core`, match in RoyaleSim) and the deterministic `unbounded` or `budget` mode. Build a RoyaleSim-native planner only if the mismatch costs a lot.

---

## 5. First implementation and smoke (done on 127x05)

```
cd /mpac/sdicks02/repos/clasher-bot
source bot/env.sh && ~/.local/bin/uv sync        # done once; .venv: py3.12.12, torch 2.10.0, numpy 2.3.5
bot/players/run.sh -m bot.players.smoke --ticks 1200 --budget 48 --check-equivalence 3 --out reports/bot/inventory/smoke-b48-1200.json
```

`run.sh` uses nice 19, `taskset -c ${BOT_CPU:-2}`, all thread pools at 1, `PYTHONHASHSEED=0` and no bytecode writes.

**Result:** K4S-b48 (seat 0) vs v1 on X4S smoke-bank index 0 (bridge mirror), 1,200 ticks (not terminal):
- 40 search decisions, 0 budget cutoffs, about 39 rollouts per decision, about 201 ms per decision;
- 11 plays vs v1's 7;
- the bot took one enemy princess tower to 13 HP;
- command hash b6e0d3e0….

Checks:
- **3/3 equivalence checks passed:** the budget run reproduced the unbounded frozen choice on the same root.
- **The repeat run reproduced the identical command hash,** so the run is deterministic.

CPU cost per run is 29 s: 15 s of `Resources` setup, then 14 s of match.

**Estimated full-game cost** (6,001 ticks, 1 core): about 55 s CPU per search-vs-v1 game. KU's fleet figure was 9.2 CPU-h per 600 games. Setup is paid once per process, so batch games per process.

### Caveats / to-dos for the lead
- **Dependency on R:** git lacks the loss_review modules, the native .so, the deck catalog and student-source. To own it, copy R once:
  ```
  rsync -a /mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/ /mpac/sdicks02/jobs/clasher-bot/runtime-r1/
  ```
  This is 592 MB on local NVMe. Then `export CLASHER_BOT_RUNTIME=…`. The SHA pins are verified at start.
- **`.venv` interpreter:** `uv sync` resolved `.venv/bin/python` to `/mpac/sdicks02/jobs/clasher/e4-guard-race-fix-20261012/py/cpython-3.12.12…`, another job's directory. Re-create it with a managed Python under `/mpac/sdicks02/tools/uv-python` before relying on it.
- **Fresh seed bank needed:** the smoke used the X4S smoke bank. For reporting games, reserve a fresh bank with the repo's seed-audit routine (`x4s/audit_seeds.py`).
- **Lateness:** deterministic modes charge no lateness, as with KU. Wall mode with threads=4 needs 5 dedicated physical cores per game, i.e. fleet hosts, not 05.
- **`mode='budget'` with default `'v1'`** is the K4 WAIT-first variant. It is deterministic only because the v1 poller uses a seeded generator, which it does.
