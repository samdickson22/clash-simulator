# HP1 S0: v2 human full-pool policy as a policy-only player. Pre-registration (exploration)

Registered before any S0 game; **game count at registration: 0**. BOT LEAD GO received 2026-10-17 ~22:52Z.
Design context: `reports/bot/hp1/DESIGN.md` (main 1a6983396), §7 S0. This is a **screen**, not a claim. Results are
reported as they land, with nothing sealed.

## Bank (drawn before registration; `date -u` Sat Oct 17 22:56:21 UTC 2026)

- **Screen BASE `1192128049223264`**, from `python3 -c "import os;print(int.from_bytes(os.urandom(6),'big')<<4)"`.
  - Scored cases 0–99; smoke cases 100–101.
  - Seed = BASE + index; seat = index mod 2; HEADLINE x4s C56 deck schedule.
  - Checked disjoint (indices 0–101) from:
    - HEADLINE (+100k);
    - every `bot/fullpool/banks.py` eval bank;
    - NS1 `3441877571898016` and NS2 `1587927595246112`;
    - TRAIN1 `874184153281168` (+1e8);
    - FP-TRAIN1 `2613058991490864` (+1e8).
- **Calibration cases:** TRAIN1 base `874184153281168`, start **46359089** (drawn as
  `int.from_bytes(os.urandom(4),'big') % (10**8-1000)` at the same time), 64 cases [46359089, 46359153). The same
  cases are used every round (common random numbers). They are disjoint from all eval banks.

## Source, runtime, models

- **Source:** `git archive` of origin/main **`1e933ddc3eda1005d00182be429e79c125712260`** into the job directory.
  Never the shared checkout. No local code changes.
- **Runtime and environment:** as NS2 (`NOSEARCH-NS2-20261017.md`), except the host and two output-only settings:
  - ROOT `~/repos/clasher-bot-runtime/live16402b-r3`, PINS `live16402b-r3`, `source bot/fullpool/run/env.sh`;
  - extended v1/R3a through `BOT_FULLPOOL_POLICIES`;
  - `BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4`;
  - `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, all numerical threads 1, a per-job NUMBA_CACHE_DIR.
  - Output-only: `BOT_PLAYLOG=1` (raw play log in rows for behaviour diagnostics; decisions unaffected,
    `bot/eval/headline.py:162`).
  - `CLASHER_LIVE_FAST`: the 04 copy of rl5-v10 (sha `e188e2ae…`, same bytes as NS2's). No S0 player reads it.
- **Models:** copied unchanged into `$JOB/models/` and SHA256-checked before use.
  - v2 = `best-dev-step-00046459.pt`, `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae`;
  - f1a2 = `step-001200.pt`, `0c03f79ffe5aa19e2310f9a959c96c98eb98678fe4c1f10352f9eb9566b58736`.
  - The extended v1 and R3a hashes are recorded at preflight.

## Protocol (identical to NS1/NS2 HEADLINE settings)

`python -m bot.eval.headline --engine rsim16402 --levels max --decks x4s`: RoyaleSim 0.1.34 / 16.402, every card and
tower L16 on both sides, C56 x4s decks, 27-tick command lag, abilities off.

| arm | `--candidate` spec | decoding |
|---|---|---|
| H | `student:$JOB/models/v2-best-dev-step-00046459.pt@τ*` | threshold gate, greedy legal card/tile, 5-tick cadence |
| E | `student:$JOB/models/f1a2-step-001200.pt@0.5375` | exactly NS2 arm e |
| F | `v1` (extended v1-fp, stock sampled T = 1) | exactly NS2 arm f |

- **Opponents:** `R3a` and `K4C-r16` (literal CandidateSearchPlayer, as NS1/NS2). K4C-r16 is strong and kept separate,
  never pooled.
- 100 cases × 3 arms × 2 opponents = **600 scored games**, plus a **12-game smoke** (cases 100–101, every cell) that
  must have zero errors before scored games. The smoke is excluded from all estimates.

## Calibration of τ* (before arm H scores; arms E/F may run meanwhile, since they don't depend on τ*)

- **Target:** f1a2@0.5375's mean candidate plays/game (`plays[str(seat)]`) vs R3a on the 64 calibration cases, same
  engine settings. Measured once, as round T.
- **Round k:** v2@τ_k vs R3a on the same 64 cases.
  - τ_0 = 0.10.
  - Without a bracket: τ_{k+1} = τ_k × 1.5 if plays > target, else τ_k / 1.5. The step is multiplicative because
    human P(play) is ~0.04 at a typical poll: v1-τ 0.1387 gave 6.9–13.9 plays/game.
  - With a bracket: secant inside it, as in `bot.exit.calibrate` rate mode.
  - Stop when |plays − target| ≤ 1.5, or after 6 rounds.
  - τ* = the round τ closest to the target, frozen before any scored H game.
- This is `calibrate --mode rate`'s algorithm, run with explicit headline flags: its `run_rate_round` can't pass
  `--engine/--levels`, so rounds are invoked directly. Calibration games are never scored.

## Readout (fixed now)

- **Score:** win 1, draw 0.5, loss 0. Per arm and opponent, the score with a 95% CI (4,000-draw case bootstrap,
  Python Random(0), sorted[100]/sorted[3899]).
- **Paired contrasts:** H−E and H−F per opponent, resampling matched case indices.
- **Descriptive:** plays/game, accepted plays, reaction fields and undefended Giant pushes from `reaction.metrics`,
  CPU s/game, and `behaviour_diag` sim measures where the rows allow.
- **No primary claim** (n = 100 per cell; half-width ≈ 9–12 pp). The use is to choose the RL init (v2 vs the P1 arms)
  and to place v2 against NS1/NS2 (rl5-alone 0.77 vs R3a and 0.52 vs K4C-r16 on NS1's bank).
- P1 arms (P1-cap, P1-lag) may be added later as a separate, dated amendment with their own calibrations, on these
  same cases. They are never compared with rows run before the amendment unless same-case.

## Hosts, priority, resources

- **Hosts:** 04 (lab user present: load cap **70**, `BOT_CPU_CAP=70`), and 08 if room. 08 is currently blocked by
  WINT-ACC1.
- **Workers:** at most **16** S0 game workers in total, in detached setsid blocks (`bot/detach.sh`) through
  `bot/exit/cpu_job.sh N nice -n 15 …`.
- **Priority:**
  - below deckopt3, LVG2 and LV2; equal to NS2; above PT1/HZ1/K1;
  - no S0 admission takes room the higher-priority jobs need;
  - only verified S0 PGIDs are ever signalled. No foreign job is signalled or reniced.
- Raw rows stay in `04:~/jobs/clasher/bot-hp1-s0-20261017/`. No data, checkpoints or game bytes are committed.

## ETA

- **Compute:** ≈26 CPU-h. Calibration ≈5 CPU-h (≈5 rounds × 64 policy games × ≈55 CPU-s). Screen ≈21 CPU-h:
  - 300 R3a games × ≈55 s;
  - 300 K4C-r16 games × ≈200 s.
- **Wall:** ≈2 h of admitted time at 16 workers.
- **Queue:** at registration 04 sits at its cap (load ≈70; deckopt3, LVG2 and lower-priority K1 shards hold the
  room), so admission wait comes on top and can't be bounded yet.
