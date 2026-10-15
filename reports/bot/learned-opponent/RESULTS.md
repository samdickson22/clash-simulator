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

## Live-tier speed: results (2026-10-15, worker of the BOT LEAD, 127x04/08)

**Answer: yes.** LIVE-K4L-R-gs-rw-fc-w200-t4-p4 makes exactly K4L-R-gs's decisions whenever its search completes.
- On 4 pinned physical cores of quiet 127x03 the complete search takes p50 79 ms and p95 126 ms. It finishes within
  the 192 ms budget on 99.1% of decisions.
- That is 2.6× faster than serial K4L-R-gs at p50 (205 ms) and 2.7× at p95 (343 ms).
- The numbers in the next two bullets come from the earlier 5-core run on contended hosts.
- **Design.** Native rollouts on 4 threads; learned rollouts in 4 persistent worker processes; a row-wise opponent
  forward; output-identical preparation caches. Code: `bot/search/lopp_fast.py`.
- **Wall-mode cutoff defaults:** 2.5%, vs 13.1% for K4CW-r16-w200-t4 in the same run.
- **Live tier:** it5s2 defaults on 6.6% of decisions, vs 24.1% for LIVE-K4CW-r16-w200-t4.
- **Strength, unbounded twin:**
  - in ours, +0.045 [+0.012, +0.077] vs K4C-r16, with all 600 command hashes equal to K4L-R-gs's games;
  - fresh bank 2 in RoyaleSim, **+0.053 [+0.040, +0.066]**.
- **Strength under a real 200 ms deadline on 4 cores:** **+0.058 [+0.020, +0.095]** vs K4CW-r16-w200-t4.
  - At 150 ms the gap is +0.160 [+0.120, +0.200].

### What was slow, and the fixes (tokens on `K4L-R...` names)

| finding | fix | exactness |
|---|---|---|
| Learned rollouts do not scale with threads: 69.6 ms sequential → 79.3 ms on 4 threads. (Corrected 2026-10-15 by `bot.search.lopp_gil`: the native does release the GIL in BattleState.step (3.52× on 4 threads), NativeScripts.select_action (3.69×) and rollout_e1 (3.75×). What serialises the loop is the opponent's Python/numpy decide step (json.loads + featurize 1.07×, one-row forward 0.71×) plus native calls that do not scale (clone 0.25×, evaluate 0.32×, public_mask 0.63×, public_view 0.70×, apply_discrete 0.94×). The earlier note that the `gil-release` feature is off was wrong.) | `p<P>`: learned rollouts in P forked or spawned worker processes, started once per process. `t<N>`: native rollout_e1 on N threads (it does release the GIL). | Pool == serial, bit for bit (below). |
| The opponent net's float32 forward depends on batch composition: OpenBLAS rows change when re-batched. A 2-row call costs 0.26 ms vs 0.038 ms for 1 row, because each call streams W1 (0.9 MB). | `rw`: one row per forward. | Values no longer depend on batching; 600/600 screen games equal K4L-R-gs. |
| The root snapshot is 2.1 MB, of which 2.07 MB is the 56-card config. | Workers rebuild roots from the ~60 KB dynamic part plus a config holding only the cards in hand and cycle. Parse 1.1 vs 7.1 ms. | 0 mismatches on 3,800 checked rollout values. |
| Preparation re-serializes the 2 MB config on every root, and K4C-r16's r16 list re-runs R3a's forward. | `fp`: cached config JSON (byte-identical payload) and an exact-input memo of R3a's outputs. `fc`: deck-card configs in the main process too. | `fp`: verify mode asserts equality. `fp`/`fc` games have the same command hash as K4L-R-gs. |

**Exactness checks** (`bot/search/lopp_fast_check.py`, real K4C-r16 roots on HEADLINE cases 0 and 3).
- Scripted opponent: rollout_e1 == serial Python loop == 4 threads == pool, bit for bit (2,940 rollouts).
  - Same with spawned workers: 861 rollouts.
  - Same on roots rebuilt from the deck-card config.
- Learned opponent with `rw`: pool == the unchunked serial batch (980 values).
- End to end, these arms reproduce K4L-R-gs's command_sha256 (03's games):
  - K4L-R-gs-t4, -c4 and -t4-p4 (case 0);
  - K4L-R-gs-rw-fc-t4-p4 (cases 2 and 5 vs v1);
  - all 600 HEADLINE games of K4L-R-gs-rw.

### Timing on 4 and 6 cores, quiet 127x03 (primary, under the coordinator's 4–6 core rule)

Setup: 2026-10-15 04:19Z, 8 games per arm (HEADLINE cases 0–3 × R3a, v1).
- One pinned group per game: each 4-core group is one CCX, each 6-core group sits inside one CCD.
- Cores 64–127 were unused; measured SMT sibling busy share ≤ 0.005.
- **Default** = the cutoff default was played.

| cores | arm | wall p50 / p95 / p99 / mean (ms) | within 192 ms | default |
|---|---|---|---|---|
| 1 | K4C-r16 (unbounded, serial) | 238 / 401 / 486 / 218 | 36% | – |
| 1 | K4L-R-gs (unbounded, serial) | 205 / 343 / 426 / 183 | 46% | – |
| 4 | **K4L-R-gs-rw-fc-t4-p4** (complete search, no deadline) | **79 / 126** / 170 / 77 | **99.1%** | – |
| 4 | K4L-R-gs-rw-fc-t4-p3 | 83 / 135 / 184 / 80 | 99.1% | – |
| 4 | K4L-R-gs-rw-fc-t2-p3 | 102 / 173 / 240 / 95 | 97.8% | – |
| 4 | **K4L-R-gs-rw-fc-w200-t4-p4** | 84 / 124 / 180 / 79 | – | **0.9%** |
| 4 | K4CW-r16-w200-t4 (reference) | 138 / 192 / 192 / 128 | – | 2.4% |
| 4 | LIVE-K4L-R-gs-rw-fc-w200-t4-p3 | 108 / 159 / 192 / 103 | – | 0.9% |
| 4 | LIVE-K4CW-r16-w200-t4 (reference) | 157 / 192 / 192 / 142 | – | 3.9% |
| 6 | K4L-R-gs-rw-fc-t4-p4 (complete) | 72 / 115 / 159 / 71 | 99.1% | – |
| 6 | K4L-R-gs-rw-fc-w200-t4-p4 | 76 / 115 / 167 / 72 | – | 0.9% |
| 6 | K4CW-r16-w200-t4 (reference) | 123 / 186 / 192 / 117 | – | 1.5% |

- **Speedup on 4 cores.** The complete K4L search is 2.6× faster than serial K4L-R-gs at p50 (205 → 79 ms) and 2.7× at
  p95 (343 → 126 ms). It is also faster than K4C-r16's own wall search, which runs into its budget.
- **4-core phases, p50/p95** (t4-p4): preparation 22/37, native scan 39/69, learned 17/26, root shipping 1.9/6.8.
- **Mac.** No per-core ratio is assumed. Compare against the LIVE LEAD's Mac benchmark when it lands, by rerunning
  `bot.search.lopp_time` with these arms on 4 cores.

### Strength under a real wall deadline, 4 cores (quiet 127x03; primary)

Setup:
- Harness: `bot.live.headline_wall --group 4`. Each game is pinned to one CCX (4 physical cores) with SMT siblings
  idle.
- Engine ours; HEADLINE cases 0–299 × R3a, v1; 600 games per arm; 0 errors. The R3a cutoff default applies, as in
  K4CW.
- Pairing: same cases, win 1 / draw 0.5, 95% bootstrap CIs, pooled = equal weight per opponent.

| comparison | pooled | R3a | v1 |
|---|---|---|---|
| **K4L-R-gs-rw-fc-w200-t4-p4 vs K4CW-r16-w200-t4** | **+0.058 [+0.020, +0.095]** | +0.047 [−0.010, +0.103] | +0.070 [+0.023, +0.113] |
| **K4L-R-gs-rw-fc-w150-t4-p4 vs K4CW-r16-w150-t4** | **+0.160 [+0.120, +0.200]** | +0.183 | +0.137 |
| K4L w150 vs K4CW w200 | +0.043 [+0.007, +0.080] | +0.007 | +0.080 |
| K4CW-r16-w200-t4 vs unbounded K4C-r16 | −0.027 [−0.060, +0.007] | −0.003 | −0.050 |
| K4CW-r16-w150-t4 vs unbounded K4C-r16 | −0.143 [−0.183, −0.102] | −0.180 | −0.107 |
| K4L w200 vs unbounded K4L-R-gs | −0.013 [−0.045, +0.017] | −0.023 | −0.003 |
| K4L w150 vs unbounded K4L-R-gs | −0.028 [−0.060, +0.003] | −0.063 | +0.007 |
| K4L w200 vs unbounded K4C-r16 | +0.032 [−0.005, +0.067] | +0.043 | +0.020 |

- The K4L live variant keeps nearly all of its unbounded strength at 200 ms and most of it at 150 ms. K4C's wall
  search loses 0.14 at 150 ms.
- K4L at 150 ms beats K4C at 200 ms.
- 5-core context run on the contended 04/08: K4L w200 vs K4CW w200 was +0.117 [+0.077, +0.155]. K4CW lost −0.092
  there vs unbounded, because contention starves the K4C search.

### Fresh bank 2: result (RoyaleSim 15.535, BASE 203119344380352, pre-registered above)

| | R3a | v1 | rext-bc | pooled |
|---|---|---|---|---|
| K4C-r16 win rate | 0.754 | 0.873 | 0.885 | |
| A = K4L-R-gs-rw-fp win rate | 0.808 | 0.938 | 0.925 | |
| **A − K4C-r16, paired** | +0.054 [+0.027, +0.082] | +0.065 [+0.043, +0.086] | +0.040 [+0.018, +0.062] | **+0.053 [+0.040, +0.066]** |

- 1,200 cases per opponent, 7,200 games, 0 errors.
- This replicates fresh bank 1's +0.055 on new cases.
- **B = K4L-R-gs-rw-i10-fp** on the same bank (3,600 games, 0 errors):
  - win rates 0.809 / 0.937 / 0.938;
  - **B − K4C-r16: +0.057 [+0.044, +0.071]** (R3a +0.055 [+0.027, +0.083], v1 +0.064 [+0.043, +0.087], rext-bc +0.052
    [+0.032, +0.074]);
  - B − A: +0.004 [−0.008, +0.017].
- **Deviation:** the bank was paused 03:00–04:07Z for the wall-clock eval and run before the fit gate resolved, as
  logged. Every game is reported.

### Recommendation
- **Live search tier:** `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` (`bot.search.lopp_fast.make_live_lopp`).
  - 4 cores: decision p50/p95 108/159 ms; the complete K4L search alone is 79/126 ms.
  - Strength: +0.058 vs K4CW-r16-w200-t4 at the same deadline. Unbounded twin +0.053 on fresh bank 2.
- **If the Mac budget is tighter:**
  - w150 keeps −0.028 vs unbounded and beats K4CW at 200 ms;
  - `-i10` is as strong (B − A +0.004) with less learned work.
- **Mac check:** rerun `bot.search.lopp_time` on the Mac's 4 cores with these arms and compare with the LIVE LEAD's
  benchmark.

### Timing on the shared, contended hosts (5 cores; context only, superseded by the table above)

Method:
- One game per pinned group of physical cores (`bot/search/lopp_time.py`). HEADLINE cases 0–3 (time1: 0–9) vs R3a and
  v1.
- The hosts are shared with the ExIt owner's jobs. `sibling busy` is the measured busy share of the groups' SMT
  sibling CPUs.
- **Default** = the cutoff default was played (S-default, a preparation cutoff, or a LIVE default).

| run (cores per game, sibling busy) | arm | wall p50 / p95 / p99 / mean | within 192 ms | default |
|---|---|---|---|---|
| time1 (1 core, 0.00) | K4C-r16 | 273 / 462 / 656 / 253 | 32% | – |
| time1 (1 core, 0.00) | K4L-R-gs | 242 / 383 / 463 / 222 | 35% | – |
| time4 (5 cores, 0.10–0.16) | K4CW-r16-w200-t4 | 183 / 192 / 194 / 153 | – | 13.1% |
| time4 (5 cores, 0.10–0.16) | LIVE-K4CW-r16-w200-t4 | 192 / 192 / 193 / 164 | – | 24.1% |
| time4 (5 cores, 0.10–0.16) | K4L-R-gs-rw-fc-t4-p4 (complete, no deadline) | 97 / 188 / 254 / 104 | **95.6%** | – |
| time4 (5 cores, 0.10–0.16) | K4L-R-gs-rw-fc-w200-t4-p4 | 102 / 184 / 193 / 104 | – | **2.5%** |
| time4 (5 cores, 0.10–0.16) | LIVE-K4L-R-gs-rw-fc-w200-t4-p4 | 121 / 193 / 194 / 123 | – | **6.6%** |
| time4 (5 cores, 0.10–0.16) | K4L-R-gs-rw-i10-fc-t4-p4 (complete) | 98 / 195 / 264 / 103 | 94.4% | – |
| time2 (5 cores, 0.20–0.50) | K4CW-r16-w200-t4 | 192 / 193 / 195 / 178 | – | 27.5% |
| time2 (5 cores, 0.20–0.50) | LIVE-K4CW-r16-w200-t4 | 192 / 193 / 200 / 177 | – | 35.9% |
| time2 (5 cores, 0.20–0.50) | K4L-R-gs-rw-fp-t4-p4 (complete) | 137 / 233 / 325 / 139 | 83.6% | – |
| time2 (5 cores, 0.20–0.50) | K4L-R-gs-rw-fp-w200-t4-p4 | 160 / 194 / 194 / 148 | – | 9.5% |
| time2 (5 cores, 0.20–0.50) | LIVE-K4L-R-gs-rw-fp-w200-t4-p4 | 192 / 194 / 195 / 166 | – | 28.2% |

- **Threads, 1 vs 4** (`lopp_threads`, time1 conditions, 30 roots × 8 keys):
  - native rollout_e1: 36.8 → 24.0 ms;
  - learned batch (pre-`rw`, in-process threads): 69.6 → 79.3 ms (CPU 128).
- **time3** (5 cores, 0.23–0.29), complete-search configurations; share within 192 ms:

  | config | within 192 ms |
  |---|---:|
  | t4-p4 | 89.6% |
  | t4-p3 | 85.9% |
  | t2-p4 | 66.7% |
  | i10 | 89.7% |

  So t4-p4 is the best split of 5 cores.
- **time4 phases, p50/p95** (A complete):
  - preparation 28/49;
  - native coarse scan 46/98 (~20 rollouts on 4 threads);
  - learned 25/47 (8 plays over 4 workers, waits overlapped with the scan);
  - root shipping 2.4/9, worker parse 2.4/9.
- **Preparation caches for K4CW too.** `--fast-prep` in time2 cut K4CW-r16-w200-t4's preparation p50 from 89 to
  47 ms. Its defaults fell from 27.5% to 24.6% (LIVE: 35.9% → 26.7%). These caches are free for the LIVE lead's
  tier as well.

**Fit verdict (fresh-bank rule, condition 2).** Two runs give different answers on 2b:
- time2 (contended): condition 2a holds, 2b fails (83.6% < 90%).
- time4: both hold (2.5% ≤ 13.1%; 95.6% ≥ 90%).
- Both runs are reported. Absolute fit on these shared hosts depends on the ExIt load. In every run the K4L live
  variant defaulted far less often than the accepted K4CW tier.
- **Definitive check:** the dedicated Mac (`lopp_time` with the arms above). The pool starts with `spawn` there,
  verified exact on Linux.

### Strength screens (ours, HEADLINE cases 0–299 × R3a, v1; paired; 95% bootstrap CIs)

| arm | vs K4C-r16, pooled | R3a | v1 | vs K4L-R-gs, pooled | command hashes = K4L-R-gs |
|---|---|---|---|---|---|
| K4L-R-gs-rw (twin of the live variant) | **+0.045 [+0.012, +0.077]** | +0.067 | +0.023 | 0 | 600/600 |
| K4L-R-gs-rw-i10 (learned opponent every 10 ticks) | **+0.055 [+0.022, +0.090]** | +0.063 [+0.007, +0.123] | +0.047 [+0.013, +0.080] | +0.010 [−0.020, +0.042] | 1/600 |

- i10 is as strong as K4L-R-gs within noise, with less learned work (time4 learned phase p50 20.6 vs 24.8 ms). Keep it
  as the fallback for slower per-core hardware.

### Using it in the live loop
- **Entry point:** `bot.search.lopp_fast.make_live_lopp(rt, 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4')`. It returns a
  `bot.live.player.LivePlayer` (it5s2 fast tier and cutoff default) whose search tier is the wall K4L.
  - `bot/live/player.py:make_live_player` does not know `LIVE-K4L-*` names. The LIVE lead can route the prefix
    there with 3 lines; it was not edited here.
  - `bot.search.lopp_time` already resolves these names.
- **Opponent net:** `$CLASHER_LOPP_MODELS/pool.npz`, sha256 `1e4bb6a01e06545b02a4f1632d564ef1dd76ceb9df2081273bd869af678b3f9e`.
  - Not in git. Copies live in `bot-lopp-models` on 03, 04 and 08.
  - 2.2 MB of float32 numpy; inference is numpy only.
- **Processes:** the pool is 4 worker processes plus the game process. It starts at the first `start()`, before any
  thread pool, and is reused across games.
  - Start method: `fork` on Linux, `spawn` on macOS. Override with `CLASHER_LOPP_POOL_START`.
  - A spawned worker rebuilds NativeScripts from `json.dumps(R.meta)`; verified bit-exact on Linux with
    `CLASHER_LOPP_POOL_START=spawn`.
- **Native and pins:** no new native build and no pin change; it runs on the frozen 44874fd6 runtime.
- **Lever (d) was not needed.** Moving the opponent's decide step (public features + forward) into Rust would make
  learned rollouts GIL-free in-process. That would need a new native build and pin set.
  - Corrected 2026-10-15: `gil-release` is already on in the pinned native (step and select_action scale 3.5–3.7×
    on 4 threads). The GIL-bound part is our Python/numpy decide plus clone/public_view/public_mask/evaluate.
  - In-process threads therefore do not replace the pool: on the same roots a learned batch takes 135 ms on 4 threads
    vs 66 ms with p4 (142 ms serial; values identical). See round 2 in PROGRESS.md.
- **On a 5-core budget:** keep t4-p4, which beat t4-p3 and t2-p4. If the Mac's per-core speed falls short, use
  `-i10`, which is as strong in ours and has less learned work.

## Round 2: fresh bank 3, pre-registered (2026-10-15T10:04:20Z, before any game on it)

- **Drawn** 2026-10-15T10:04:20Z: BASE **4303584859564336** = int.from_bytes(os.urandom(6),'big')<<4. No game has been played on it.
- **Engine and protocol:** RoyaleSim 15.535 via bot/eval/headline.py --engine rsim15535, cases 0–1199 × opponents R3a,
  v1, rext-bc. Each arm is paired on the same cases against **K4L-R-gs-rw-fp**, the fp twin of K4L-R-gs: identical
  decisions to K4L-R-gs (600/600 HEADLINE hashes for rw; fp cases 0 and 3 checked), played on this bank too.
- **Candidate:** **K4L-R-gs-rw-O-fp** (token O: inside the learned rollouts our own side is also driven by the learned
  net, with its own common-random-number key, instead of scripted balanced). It is the deterministic twin of
  LIVE-K4L-R-gs-rw-O-fc-w200-t4-p4; its fp games equal the serial K4L-R-gs-rw-O games (cases 0 and 3).
  - Why O: of 15 round-2 arms it is the only one positive in both screens:
    - ours, HEADLINE 0–299: +0.035 [+0.009, +0.062] vs the mean of 3 equal-strength reference runs;
    - RoyaleSim, HEADLINE 0–299 × 3 opponents: +0.024 [+0.002, +0.047] vs K4L-R-gs.
  - Details in PROGRESS.md, round 2.
- **Decision rule (fixed now).** K4L-R-gs-rw-O becomes the new best if both hold:
  1. its pooled paired delta vs K4L-R-gs-rw-fp on this bank (equal weight per opponent, 95% bootstrap CI) has a lower
     bound > 0;
  2. in a 4-core pinned timing run on 127x03 (siblings idle, K4L reference in the same run),
     LIVE-K4L-R-gs-rw-O-fc-w200-t4-p4 plays the cutoff default on ≤ 1% of decisions, and its complete search
     (K4L-R-gs-rw-O-fc-t4-p4) has p95 ≤ 190 ms.
  - Otherwise K4L-R-gs stays the best.
- **Reporting:** pooled and per-opponent deltas, win rates, and timing p50/p95/p99 and default share. Every game is
  reported.
