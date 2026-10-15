# Learned rollout opponent inside K4C-r16: results (exploration)

2026-10-14, bot-lead implementation sub-agent, all games on 127x03. Exploration tier, not preregistered.
Design: [DESIGN.md](DESIGN.md); log: [PROGRESS.md](PROGRESS.md). Code: `bot/search/lopp*.py` (`K4L-*`).

**Answer: yes.** K4C-r16 with a learned rollout opponent, `K4L-R-gs`, beats K4C-r16 at equal CPU.
- Its pressure/defense refine rollouts are replaced by an opponent net imitating v1 and R3a, so the work set is
  scored (balanced + learned)/2.
- **HEADLINE, ours:** +0.045 [+0.012, +0.077].
- **HEADLINE, RoyaleSim:** +0.028 [+0.000, +0.054].
- **Fresh bank, RoyaleSim:** **+0.055 [+0.041, +0.068]** (1,200 cases per opponent). It is positive against every
  opponent: R3a +0.049, v1 +0.055, rext-bc +0.060.
- **Recommendation:** K4L-R-gs becomes the strongest bot in the turn-based tiers. It is not yet live-tier ready (see
  Cost).

## Validity
- **Rollout exactness.** On real K4C-r16 roots, the Python-driven rollout loop with a scripted opponent equals
  native `rollout_e1` bit for bit.
  - 6,561 rollouts on 90 HEADLINE roots, all candidates and all 3 styles; max |diff| 0.0.
  - Same cost: 6.4 ms per rollout either way.
  - End to end, `K4L-X` (every rollout by the Python loop) reproduces K4C-r16's `command_sha256` on 100/100 games,
    and `K4L-M0` on 59/59.
- **Data does not perturb games.** The recording runner's 600 FIT-bank games equal the earlier `bot-opp-fitA`
  K4O-mean games by `command_sha256` (600/600).
- **Banks.**
  - Training data comes from the FIT bank (BASE 2249738988533344), never HEADLINE.
  - The fresh bank (BASE 2195817639077040) was drawn with `os.urandom` and recorded, with its decision rule, before
    any RoyaleSim result.
- **Errors.** None in any run.

## Opponent network
- **Data.** 1,200 games of K4C-r16 vs R3a/v1: 695,089 free polls, 40,792 plays.
- **Model.** A numpy MLP on native `public_view` (9×16 board grid, towers, elixir, tick phase, hand
  embeddings): play gate → card → tile.
  - Dropout 0.3, early stopping on validation loss.
  - Validation = held-out cases with index % 10 == 9.

| model | val on | gate AUC | card top-1 | tile top-1 | tile ≤2 tiles | card ∧ tile ≤2 |
|---|---|---:|---:|---:|---:|---:|
| R3a | R3a | 0.85 | 0.85 | 0.46 | 0.65 | 0.57 |
| v1 | v1 | 0.60 | 0.47 | 0.13 | 0.30 | 0.13 |
| pool | R3a | 0.81 | 0.84 | 0.45 | 0.64 | 0.55 |
| pool | v1 | 0.55 | 0.47 | 0.10 | 0.30 | 0.11 |

R3a is deterministic and well imitated. v1 samples its gate, card and tile at T=1, so single decisions are close
to unpredictable; only its distribution can be matched.

**Behaviour inside 160-tick rollouts** (60 HEADLINE roots):

| opponent | plays per rollout | elixir at play |
|---|---:|---:|
| real R3a | ~2.3 | 4.06 |
| real v1 | ~1.45 | 7.85 |
| scripted styles | – | ~2.9 |
| pool, threshold gate | 0.60 | 5.7 |
| **pool, sampled gate (`gs`)** | **1.53** | **5.0** |
| R3a model, `gs` | 2.00 | 4.3 |
| v1 model, `gs` | 1.26 | 5.3 |

- The calibrated threshold gate is too passive inside rollouts, because rollout states differ from game states.
- The sampled gate uses the same uniforms for every candidate (common random numbers), so the comparison between
  candidates stays fair.

## Cost
- **Learned-opponent rollout:** about 10–11 ms vs 6.4 ms native. `public_mask` is only built when the gate plays.
- **`K4L-R-gs`:** about 22 native coarse + 2 native wait rollouts, plus 11 learned rollouts on the work set (WAIT,
  timed waits, top-8).
  - 33.2 rollouts and **0.415 s CPU per decision**.
  - Load-matched K4C-r16 (`K4L-M0`, same run): 0.412 s and 41.3 rollouts.
  - So it is equal-CPU; no compute was added. Wall per decision is 0.416 s vs 0.414 s.
  - All of these were measured on 03 at about 100 busy processes. No uncontended single-thread measurement was
    possible: 03 went to the LIVE LEAD.
- **Threads.** Timing test `bot.search.lopp_threads`: 8 roots, 10 work-set keys, 4 threads, run under load; values
  were identical in every mode.
  - The pinned native releases the GIL: 10 native `rollout_e1` calls take 68 ms sequentially and 24 ms of wall time
    on 4 threads (2.9×).
  - The Python-driven learned rollouts are GIL-bound: 141 ms sequentially vs 136 ms of wall time on 4 threads, at
    302 ms of CPU.
  - Single-thread, the learned part is about 115–140 ms of the 0.415 s decision.
- **200 ms deadline.**
  - K4L-R-gs does not fit single-threaded, and neither does K4C-r16 (0.41 s).
  - With threads, the native coarse scan shrinks, but the about 11 learned rollouts stay serial at about 120–140 ms,
    plus about 100+ ms of fixed per-decision overhead. So it does not fit as built.
  - Ways to make it fit, roughly in order of effort:
    1. learned decisions every 10 ticks instead of 5 (`i10`), about half the Python work; untested for strength;
    2. learned rollouts in worker processes;
    3. port the opponent's forward into Rust for a fully native, GIL-free rollout (a new native build and pin).

## Results (paired vs K4C-r16, same cases; win 1, draw 0.5; 95% bootstrap CIs; pooled = equal weight per opponent)

| arm | what | CPU s/dec | HEADLINE, ours (R3a, v1) | HEADLINE, RoyaleSim (R3a, v1, rext-bc) | fresh bank, RoyaleSim |
|---|---|---:|---|---|---|
| `K4L-R-gs` | balanced coarse scan; top-8 + waits scored (balanced + learned)/2, pool model, sampled gate | 0.415 | **+0.045 [+0.012, +0.077]** (R3a +0.067, v1 +0.023) | **+0.028 [+0.000, +0.054]** (R3a +0.010, v1 +0.033, rext-bc +0.040) | **+0.055 [+0.041, +0.068]** (R3a +0.049 [+0.021, +0.076], v1 +0.055 [+0.034, +0.076], rext-bc +0.060 [+0.037, +0.082]); K4C-r16 0.748/0.880/0.864 → 0.796/0.935/0.924 |
| `K4L-R-mR3a-gs` | same, R3a-only model | 0.391 | +0.022 [−0.012, +0.056] (R3a +0.055, v1 −0.010) | not run | – |
| `K4L-L-gs` | learned opponent only, every candidate | 0.426 | −0.012 [−0.047, +0.025] (R3a −0.023, v1 0.000) | not run | – |

- **Decisions changed.** `K4L-R-gs` changes 27% of K4C-r16's decisions on the same roots (R3a 67/240,
  v1 63/240). The K4O re-weighting arms changed only 2–9%.
- **Threshold-gate arms abandoned.** The first batch used the pool model with the threshold gate (`K4L-R`, `K4L-L`,
  `K4L-M50`). It was stopped after 176 games once the passivity diagnostic came in; the partial games are kept in
  `bot-lopp-hl1-thr-partial` and were not analysed.

Raw logs on 127x03, `/mpac/sdicks02/jobs/clasher/`:

| directory | contents |
|---|---|
| `bot-lopp-rec` | training games and recordings |
| `bot-lopp-models` | models |
| `bot-lopp-eq` | equivalence games |
| `bot-lopp-hl2` | HEADLINE, ours |
| `bot-lopp-rsim-a`, `bot-lopp-rsim-b` | HEADLINE, RoyaleSim |
| `bot-lopp-fresh` | fresh bank |

Reproduce with:
- `python -m bot.search.report <dirs> --baseline K4C-r16 --opponents …`
- runner: `bot-lopp-run.sh MODULE ARGS`

## Live-tier speed: fresh bank 2, pre-registered (2026-10-15, before any result of the arms below)

- **Drawn** 2026-10-15T01:39:04Z: BASE **203119344380352** = int.from_bytes(os.urandom(6),'big')<<4. No game has been played on it.
- **Engine and protocol:** RoyaleSim 15.535 via bot/eval/headline.py --engine rsim15535, cases 0–1199 × opponents
  R3a, v1, rext-bc, each candidate paired against K4C-r16 on the same cases (K4C-r16 is played on this bank too).
- **Candidates:** the deterministic twin of each live K4L variant (identical decisions when no cutoff hits):
  - A = K4L-R-gs-rw-fp (twin of LIVE-K4L-R-gs-rw-fp-w200-t4-p4);
  - B = K4L-R-gs-rw-i10-fp (twin of the i10 live variant).
- **Decision rule (fixed now):** a candidate runs on this bank if both hold:
  1. Strength: its HEADLINE screen in ours (cases 0–299 × R3a, v1) is ≥ +0.03 pooled vs K4C-r16, paired.
  2. Fit: in one pinned timing run (5 physical cores per game, references in the same run), its wall variant
     plays the cutoff default on no more decisions than K4CW-r16-w200-t4, and its complete search fits the
     192 ms budget on ≥ 90% of decisions.
  - A is run first. B runs only if A fails the rule or compute remains after A.
- **Reporting:** the paired delta vs K4C-r16 with a 95% bootstrap CI, pooled with equal weight per opponent, and
  per opponent.
