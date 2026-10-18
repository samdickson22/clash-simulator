# HP1 RL (b): PPO from the human v2 init. Pre-registration (exploration)

Owner: HP1 RL owner (Opus), for the coordinator. Design: `DESIGN.md` §3.3(b), §4 G-B/G-E, §7.3. Registered before any
RL game or snapshot evaluation; **RL games at registration: 0**. Results are reported as they land; nothing is sealed.

## 1. Init decision (2026-10-18)

- **Init = v2** `best-dev-step-00046459.pt`, SHA256 `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae`,
  decoded at **τ0 = 0.019753086419753086** (S0 on-policy rate calibration; S0-RESULTS.md).
  - Why: S0 (100 paired cases, L16): v2@τ* .77 vs R3a and .51 vs K4C-r16, against f1a2 .63 / .45, at about half the
    CPU per game. It is the best standalone policy we have, and 01's GPU is free now. P1 has not reported.
- **KL anchor = the init** (human policy), β = 0.05, as DESIGN §3.3(b) (ClashAI recipe; KL-free runs degenerate).
- **Switch rule for P1-lag (fixed now):** when `P1-RESULTS.md` lands, switch the RL init to P1-lag only if its S0-bank
  screen (same cases 0–99, its own on-policy rate-calibrated τ) beats v2's S0 H rows paired, equal-weight over R3a and
  K4C-r16, with the 95% bootstrap lower bound > 0 (4,000 draws, Random(0), sorted[100]/[3899]).
  - If it switches and no v2 snapshot has cleared G-B yet: stop this run (keep every checkpoint) and start `run-lag`
    from P1-lag under this same document (new τ0, new run dir, same banks except a fresh RL bank).
  - Otherwise this run continues, and P1-lag joins the league as a frozen opponent (a dated amendment here).
  - P1-cap passing G-A only matters for a later full HP1-IL-M run; it doesn't change this run.

## 2. Banks (drawn 2026-10-18 04:53:51Z on 127x05, `int.from_bytes(os.urandom(6),'big')<<4`, before any game)

| bank | base | use |
|---|---|---|
| RL | `2746899445152544` | training games g = block·10⁶ + k·W + w (`BOT_RL_BANK`); never evaluated on |
| DEV | `3690083941500208` | G-E snapshot screen; selection allowed (biased by construction) |
| CONFIRM1 | `2715349865347232` | the first G-B confirm, used **once** |

- Each was checked > 10⁹ away from HEADLINE, TRAIN1, FP-TRAIN1, both earlier RL banks, NS1, NS2, the S0 screen bank,
  the PF1 base and every `bot/fullpool/banks.py` eval bank (`actor.check_bank` re-checks RL at actor start).
- **Every further G-B confirm draws a fresh bank** the same way at launch time and records it here (dated) before its
  first game. A bank that has seen one confirm is never used for a second claim.

## 3. Training run

- **Code:** `bot/rl/{actor,learner,dist}.py` (rl5/rlfp1 machinery) with four additions, all default-off:
  `BOT_RL_TAU0` (the init's τ; learner rejects rollouts with another τ0), `BOT_RL_ENVS` (per-game mixture of engine /
  levels / decks), `BOT_RL_LEAGUE_SPECS` (named student opponents) and the `LIVE-K4CW-r16-fp` opponent
  (`bot/livediag/k4cw_fp.py`, fast tier f1a2, as PF1 / deckopt3). Launcher `bot/rl/hp1_run.sh`; hourly mirror
  `bot/rl/mirror.sh`.
- **Match environments (training = evaluation conditions: 27-tick command lag, 5-tick polls, L16 both sides):**

  | share | engine | decks |
  |---:|---|---|
  | 50% | RoyaleSim 16.402 (vocab-full `f588168f…`, as PF1) | Sam's live deck (HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie) vs the 91 Battle Log decks |
  | 50% | our engine (`bot/levels/match.py` max levels) | both decks from the full-pool sampler `fullpool:11433651:freq=b53b02a1fde4` |

  A RoyaleSim full-pool row was dropped at review: vocab-full lacks some sampled cards (Graveyard, SuspiciousBush).
  Any RoyaleSim game with unmapped/missing translator rows is recorded as an error and keeps no rollout (PF1's rule);
  the smoke reports that rate for the Battle Log decks.

- **League (opponent drawn per game by hash; never a single opponent):** LIVE-K4CW-r16-fp 20%, R3a-fp 20%,
  f1a2@0.5375 20%, rl5-v10-fp@0.5375 10%, v1-fp 10%, own snapshots 20% (v2 itself until the first snapshot).
  Strong search opponent + three different fast students + past selves, so no single opponent is overfit.
- **PPO (r5/rlfp1 settings):** terminal ±1 reward only; γ 1, λ 0.95; clip 0.2; lr 1e-5; KL(π‖v2) β 0.05 on the full
  explore distribution; gate q = σ((logit p − logit τ0)/κ), κ 0.1, card/tile T 0.1 (the mode is the deployed decode);
  ≥ 240 games per update (≤ 480), staleness ≤ 2 versions, 2 epochs; critic = separate v2 trunk copy, 3 critic-only
  warm-up updates. Snapshot every 5 versions (league + screen queue). Seed 2026101490.
- **Compute:** learner on 127x01's GPU (≤ 16 GB, 4 threads). Actors: one block on 01 (≤ 16 workers; 01 throttles, keep
  load ≤ 60) and blocks on 08/04 only through `bot/exit/cpu_job.sh` admission, nice 15 (NS2, play-quality A/Bs and
  deckopt3 final2 keep priority). PYTHONHASHSEED=0, NUMPY_MADVISE_HUGEPAGE=0, detached setsid launches.
- **Artifacts:** `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/` on 01 (`source/` = git archive of the registered
  commit, `models/` sha-checked, `run/`). Mirrored hourly to 127x04 `/mpac/sdicks02/jobs/clasher/bot-mirror/01/hp1-rl/`.

## 4. Gates

Both use the PF1 driver (`cadence-pf1/l16_cadence.py`, SHA256 `cda77034…`, read-only), i.e. RoyaleSim 16.402 and the
**live fast-tier decode** (`LivePlayer(tier='fast')`, label `fast-<x>`), on Battle Log pool v3.2 rows
(`01732d23…`), clean perception, 27-tick lag. Arms are paired on every case. Opponents: **LIVE-K4CW-r16-fp** (strong;
never pooled with others) and **R3a**.

Arms: `fast-vN` = RL snapshot N at τ0; `fast-v2` = the init at τ0 (= RL v0); `fast-f1a2` = the current live fast tier
(its calibration file, 0.6444).

### Exact driver arguments (every row; `run-l16-cadence.sh <source> <W> …` as PF1)

Common: `--vocab <bot-livediag>/vocabv3/vocab-full.json --noise clean --players <arms> --fast-spec "<specs>"`, with
`--fast-spec` labels `vN=student:<snapshot>@0.019753086419753086`, `v2=student:<v2>@0.019753086419753086`,
`f1a2=student:<f1a2 step-001200.pt>` (no threshold: its calibration file, as PF1). `SAM` =
`HogRider,Archers,Cannon,Skeletons,Fireball,Zap,ElectroSpirit,Valkyrie`; `POOL` = `pools/battlelog-pool-v3.2.jsonl`.

| row | arguments | cases |
|---|---|---|
| Sam L16 | `--pool POOL --own-deck SAM --levels l16 --opponents LIVE-K4CW-r16-fp,R3a` (no `--strata`: uniform over all pool rows) | `--cases` per opponent |
| account | `--pool POOL --own-deck SAM --levels account --our-levels HogRider=8,Archers=8,Cannon=9,Skeletons=7,Fireball=7,Zap=9,ElectroSpirit=8,Valkyrie=7,King=7 --strata "<PF1's strata string, copied verbatim from bot-livediag/pf1/s0/bank.json: all=<53 indices>>" --opponents LIVE-K4CW-r16-fp,R3a` | `--cases` per opponent |
| dd1 | `--decks dd1 --levels l16 --opponents LIVE-K4CW-r16-fp` (no `--pool`, no `--own-deck`: DD1 is defined on the v1 pool) | `--cases` |

Bases: a row's `--base` = bank base + offset, offsets Sam L16 +0, account +100000, dd1 +200000 (seeds never shared
across rows). Fixed `--base`/`--cases`/row arguments give identical cases whatever `--players` is, so an arm can be
run later on the same cases. Rows are clean only if the driver's `problems(row)` is empty (0 errors required).

### G-E: snapshot screen (DEV bank; selection only, never a claim)
- Every 10th version (v10, v20, …): Sam L16 row `--cases 60` (K4CW-fp + R3a) and dd1 row `--cases 60` (K4CW-fp), base
  DEV. fast-v2 runs once on these cases at the start (the decode is deterministic); each snapshot runs `fast-vN` only.
- Screen score = mean of the three paired differences (vN − v2). The best screen snapshot with all three differences
  ≥ 0 and plays/game sane (below) is the G-B candidate.
- **Kill rule:** no snapshot by v40 with screen score ≥ +0.03 → stop the run, keep checkpoints, report.
- **Collapse rules (r5):** mean KL(π‖v2) > 0.5 nats/transition, or deploy plays/game outside [20, 65] for 3
  consecutive updates, or train score rising while the screen drops below −0.05 twice → stop and report.

### G-B: confirm (fresh bank, once per bank)
- Rows, arms fast-vN / fast-v2 / fast-f1a2, base = the confirm bank:
  - **A (primary):** Sam L16 row vs LIVE-K4CW-r16-fp, `--cases 300`.
  - A′: the same run's R3a cases (300).
  - B (account levels): account row, `--cases 150` per opponent (PF1's 53 complete-level rows at their logged
    levels; our account levels).
  - C (deck-diverse): dd1 row, `--cases 200`.
- **Primary:** vN − v2 on row A; **pass if the 95% paired bootstrap lower bound > 0** (4,000 draws over cases,
  Random(0), sorted[100]/[3899]).
- **Clears the gate** = primary pass **and** no other row's vN − v2 point estimate below −0.03 **and** the sanity
  checks pass. vN − f1a2 is reported on every row (secondary; decides the fast-student hand-off).
- **Sanity:** 0 errors; vN plays/game on rows A/A′ within [25, 60] and within ±10 of fast-v2's; reaction p50/p90,
  idle-play share and undefended share reported as in PF1.
- Power: 300 paired cases give a half-width ≈ 6–7 pp against the strong opponent.

## 5. Readout and hand-off

- A Sol helper runs the screens and confirms and reports to the RL owner; the RL owner reports gate results to the
  coordinator (≤ 6 lines). A snapshot that clears G-B is offered to the play-quality owner as the search prior/fast
  tier candidate (their A/B decides use inside search) and as the fast student.
- Per the RL snapshot-bias lesson, DEV-screen numbers are never quoted as gains; only G-B rows on a fresh bank are.
