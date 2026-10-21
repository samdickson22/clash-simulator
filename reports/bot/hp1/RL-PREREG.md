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

## Amendment 1 (2026-10-18 10:15Z): search-replacement gate G-S, search opponent in the league

**Why:** Sam (binding, via the coordinator): "the search is a bad idea; if our bot is worse without it, that's a
problem with the bot." This track is now the main bot track, with one goal: a **policy-only** bot that beats the live
search bot (`res-lb-RF-wintp` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF + wint port, serial twin, deadlines
cleared) head-to-head and against strong opponents, on Sam's deck at account levels **and** at L16. G-S is the gate
for replacing search live. G-B (vs v2) is unchanged. Registered before any G-S game.

**Driver additions** (`bot/livediag/l16_cadence.py`, default-off): `fast-<label>` arms with `--fast-spec` (PF1's
policy-alone decode, ported); opponent `SEARCH` with `--search-opponent <arm>` (the live search at the other seat,
built and configured exactly like a `res-…` arm); `--mirror` (the opponent plays our deck too, at our levels).

**Launch (G-S rows and the G-S screen; NOT the PF1 wrapper, whose driver copy lacks these options):**
`bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh <W+2> bot/rl/hp1_l16.sh <TREE> --workers <W> --out <out> --base <base> --cases <n> <row arguments>`,
where TREE = `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/repo-<sha12>/` is a git archive of the commit that
registered this amendment (or a reviewed descendant), with `STAGED-REV`. `hp1_l16.sh` is `bot/pq/l16.sh` (the
play-quality owner's runner for this driver) with the HP1 job dir: runtime live16402b-r3, deck-search helpers and
lopp-fp models, PYTHONHASHSEED=0, `python -m bot.livediag.l16_cadence`. Common arguments for every G-S row:
`--vocab /mpac/sdicks02/jobs/clasher/bot-livediag/vocabv3/vocab-full.json --noise clean --own-deck SAM --fast-spec
"<vN and v2 specs as §4>"`, plus `--players` per row below. The G-S search arm and opponent are `res-lb-RF-wintp`.

**Bank:** S-CONFIRM1 = `3262629447693008` (drawn 2026-10-18 10:15:35Z on 127x05 with os.urandom, > 10⁹ from every
registered bank). Used once; later G-S confirms draw fresh banks, recorded in RL-RESULTS.md before the first game.

**G-S rows** (common arguments as §4, `--own-deck SAM`, `--vocab vocab-full`; account levels =
`HogRider=8,Archers=8,Cannon=9,Skeletons=7,Fireball=7,Zap=9,ElectroSpirit=8,Valkyrie=7,King=7`):

| row | arguments | arms | cases | base offset |
|---|---|---|---|---|
| H2H-16 | `--mirror --levels l16 --opponents SEARCH --search-opponent res-lb-RF-wintp` | fast-vN, fast-v2 | 200 | +0 |
| H2H-acct | `--mirror --levels account --our-levels <acct> --opponents SEARCH --search-opponent res-lb-RF-wintp` | fast-vN, fast-v2 | 200 | +100000 |
| STR-16 | `--pool POOL --levels l16 --opponents LIVE-K4CW-r16-fp,R3a` | fast-vN, res-lb-RF-wintp | 200 per opponent | +200000 |
| STR-acct | `--pool POOL --levels account --our-levels <acct> --strata "<PF1 53-row strata>" --opponents LIVE-K4CW-r16-fp,R3a` | fast-vN, res-lb-RF-wintp | 150 per opponent | +300000 |

**Pass, i.e. the policy replaces search (all must hold):**
1. Head-to-head: fast-vN's score vs SEARCH pooled over H2H-16 + H2H-acct, with a 95% case-bootstrap lower bound
   > 0.5 (4,000 draws, Random(0), sorted[100]/[3899]), and each row's point estimate > 0.5.
2. Strong opponent: fast-vN − search vs LIVE-K4CW-r16-fp, paired by case, point estimate > 0 in STR-16 **and**
   STR-acct.
3. R3a: fast-vN − search point estimate ≥ −0.03 in both STR rows.
4. Sanity: every row of all four G-S rows is clean (the driver's `problems(row)` empty; with opponent SEARCH, a
   rejected command of the search opponent is also an issue), and fast-vN's mean plays/game is in [25, 60] on each of
   the four rows. No relative play-rate check applies in G-S.

fast-v2 is reported in the H2H rows as the reference. A policy that passes is reported to the coordinator at once;
the live A/B and rollout are the coordinator's/loop owner's call.

**G-S screen (DEV; selection only):** H2H-16 with `--cases 60` at base DEV+300000, arm fast-vN (fast-v2 once). Plus
the search arm `res-lb-RF-wintp` run once on the existing DEV Sam-L16 cases, so every G-E screen also reports
vN − search vs K4CW-fp/R3a on the same cases. A snapshot goes to G-S when its DEV H2H ≥ 0.5 **or** it passes G-B.

**League (this run, from the learner restart with `--extend-league`):** names appended, never reordered:
LIVE-K4CW-r16-fp .18, R3a .15, f1a2 .17, rl5 .08, v1 .05, self .20, **SEARCH .17**. SEARCH =
`livesearch:LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-wint` (serial twin with the interruptible-wait facade = the driver's `res-lb-RF-wintp`, f1a2 fast tier). Its games use a mirror of
Sam's deck on both seats and always run in RoyaleSim 16.402 at L16 (`BOT_RL_MIRROR_ENGINE`; in our engine the level
planner would replace the search's RF root), i.e. the gate's H2H-16 opponent exactly. Old actor blocks may finish on the old
shares; the critic's new SEARCH embedding row starts at zero.

**Init switch (unchanged rule, §1):** P1-lag replaces v2 only if it is clearly better on the S0 cases. If it does,
the new run starts with this league.

## Amendment 2 (2026-10-18 10:27Z): G-S judged against every deck; Amendment 1's mirror rows become secondary

**Why:** Sam: "It should also factor in playing against every deck, not just mirrors", and "Opponents should also be
random known decks — we haven't seen all cards and decks in ladder yet." The coordinator fixed the primary as a paired
comparison on identical cases. Registered before any G-S game (none has run).

**Opponent deck distribution ("all-deck mix", training and G-S alike):** `bot/rl/decks.py` sources, per case by hash:
- 40% corpus: a deck from the human corpus deck table, ∝ its count. The table holds every 8-card deck in the
  v2/T11 replay store (both perspectives, engine names, evo/hero forms as base cards) plus the LIVE Battle Log decks
  (91-deck list and pool v3.2), and is built once by a Sol data job into `$JOB/models/corpus-decks-v1.jsonl`. It
  stays outside git (corpus licence: internal use), and its SHA256 is recorded in RL-RESULTS.md and the bank
  before the first game that uses it;
- 30% the frozen LIVE frequency table `fullpool:11433651:freq=b53b02a1fde4`;
- 30% random legal decks `fullpool-uniform:11433651` (at most one champion).
- In RoyaleSim, GoblinHut, Graveyard and SuspiciousBush are redrawn on both seats. Their public rows are
  unmappable in vocab-full: 1,793 of 1,793 RL RoyaleSim errors to 10:20Z were `unmapped_unit:SpearGoblin_Dummy`
  (Goblin Hut), and review found Graveyard/SuspiciousBush motion-7 gaps. The excluded share of each source is
  reported. Any new unmapped key still voids its game/row and is added here before further use.

**G-S primary rows** (replace Amendment 1's table). Our deck: Sam's live deck (`--own-deck SAM`), opponent deck
`--opp-decks "corpus@.4|fullpool:11433651:freq=b53b02a1fde4@.3|fullpool-uniform:11433651@.3" --corpus-decks
<table> --opp-exclude GoblinHut,Graveyard,SuspiciousBush`, arms **fast-vN and res-lb-RF-wintp on identical cases**
(plus fast-v2 as reference), opponents **SEARCH** (`--search-opponent res-lb-RF-wintp`, i.e. the live search
piloting the opponent deck), **LIVE-K4CW-r16-fp** and **R3a**:

| row | levels | cases per opponent | base offset |
|---|---|---|---|
| ALL-16 | `--levels l16` | 200 | +400000 |
| ALL-acct | `--levels account --our-levels <acct> --opp-level-table reports/bot/fullpool/lv2/opp-levels-dist.json` (sha `81e1f4b0…`, King 9) | 150 | +500000 |

**Pass (the policy replaces search):**
1. vs the SEARCH pilot: the paired difference [fast-vN − res-lb-RF-wintp], pooled over ALL-16 + ALL-acct SEARCH
   cases, has a 95% case-bootstrap lower bound > 0 (4,000 draws, Random(0), sorted[100]/[3899]).
2. vs LIVE-K4CW-r16-fp: the paired difference ≥ 0 (point estimate) in ALL-16 **and** in ALL-acct.
3. vs R3a: the paired difference ≥ −0.03 (point estimate) in ALL-16 **and** in ALL-acct.
4. Sanity: every row clean (`problems(row)` empty; opponent rejections and `no_template` translator drops included); fast-vN plays/game in [25, 60] per row.
- ALL-acct opponent levels: the LV2 table level, raised to the card rarity's first level where lower (`bot/levels/profile.FLOOR`; RoyaleSim rejects lower levels).
- Reported always: every cell's score with CI, per-archetype breakdown (`bot/fullpool/archetype.classify` of the
  opponent deck) of every paired difference, and fast-v2 alongside.
- **Secondary:** Amendment 1's H2H-16 / H2H-acct mirror rows (Hog mirror head-to-head) and its STR rows on the
  Battle Log pool. Not part of the pass rule.

**Off-deck sanity row (generalisation, descriptive):** `bot.eval.headline --engine ours --levels max`, candidates
`student:vN@τ0` and `student:v2@τ0`, opponents R3a and K4C-r16, 100 cases each, base OFF1 = `2746836719317424`
(drawn 2026-10-18 10:27:06Z on 127x05, os.urandom, disjoint), twice: `--decks fullpool:11433651:freq=b53b02a1fde4`
(ladder-table decks) and `--decks fullpool-uniform:11433651` (random decks, base OFF1+200000). Reported as
vN − v2 paired per opponent; a point estimate below −0.05 is flagged as overfitting to Sam's deck.

**G-S screen (DEV):** ALL-16 at `--cases 60` per opponent, base DEV+400000; fast-v2 and res-lb-RF-wintp run once,
fast-vN per snapshot. A snapshot goes to G-S when its screen [vN − search] vs SEARCH ≥ 0, or it passes G-B.

## Amendment 3 (2026-10-18 10:27Z): RL deck mix for our side; deck fine-tune folded into RL

**Why:** Sam: v2 is a general pretrain, so "we should still fine tune it on the deck"; then "It should still self
play plenty with other known decks and random decks too", and "Isn't fine tuning after just RL?" The coordinator
decided that RL with about 50% Sam's deck **is** the deck fine-tune. No separate supervised deck stage is built. The
init choice stays v2 vs P1-lag (§1).

**Our deck per game** (`BOT_RL_ENVS`, kinds from `bot/rl/decks.py`):

Overall shares below include the SEARCH games (17% of the league, always `sam`); the non-SEARCH environment weights
are `sam` .398 / RoyaleSim `meta` .181 / our-engine `meta` .180 / `rand` .241, so the totals are 50.0 / 30.0 / 20.0%.

| share | engine | our deck | opponent deck |
|---:|---|---|---|
| 50% | RoyaleSim 16.402, L16 | `sam` = Sam's live deck (`OWN_DECK` launch input, now HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie) | all-deck mix |
| 15% | RoyaleSim 16.402, L16 | `meta` = a corpus deck ∝ count (includes Hog 2.6 and every archetype) | all-deck mix |
| 15% | our engine, L16 | `meta` | all-deck mix |
| 20% | our engine, L16 | `rand` = random legal deck | all-deck mix |

- Games vs SEARCH always run as RoyaleSim / L16 / `sam` (the deployed twin of the search only exists there).
- **Following the live deck:** if the live account's deck changes (`reports/live/loop/ACCOUNT-LOG.md`), the helper
  relaunches actor blocks with the new `OWN_DECK` (new block numbers) and records it in RL-RESULTS.md. Gates always
  use the deck live at gate time, recorded in the bank.
- The league of Amendment 1 (with SEARCH) applies from the learner restart with `--extend-league`. Amendment 1's
  mirror-deck SEARCH games are dropped: SEARCH pilots the all-deck mix.

## Amendment 4 (2026-10-18): data-derived RoyaleSim exclusion set; Sam's deck also in our engine

**Why:** the new-mix smoke voided a game on `unmapped_spell:SkeletonBalloon/0`. Rather than chase single cards, a
probe used the reviewed actor (RoyaleSim, L16, Sam's deck vs uniform-random opponent decks with no exclusion, vs R3a).
It stopped at 677/1,024 games: 433 voided by translator gaps (64%), plus 5 OwnCycle "card not in list" exceptions.
Per-card draws: min 26, median 45. Table: 08/01 `$JOB/probe-rsim1/coverage.json`, SHA256
`d1666d7cad127fc3b871968042571e13b3823c472e8a7f241f8851ae6dd4164c`.

**RoyaleSim exclusion set** (replaces Amendment 2's three cards, for training `BOT_RL_RSIM_EXCLUDE` and every G-S
row's `--opp-exclude`). Every card voiding ≥ 1 probe game or raising the OwnCycle exception:
`Fisherman,GiantBuffer,GoblinCurse,GoblinDemolisher,GoblinDrill,GoblinGiant,GoblinHut,Graveyard,MegaKnight,MovingCannon,Phoenix,RamRider,SkeletonBalloon,SuspiciousBush,ThreeMusketeers,WitchMother,ElectroGiant,Tombstone,GoldenKnight`.
- 50.97% of the corpus deck weight contains at least one of them. **G-S therefore judges the RoyaleSim-playable half
  of the meta only**; this limit is reported with every G-S result. The fix is translator/vocab coverage for these
  cards (outside this track; reported to the coordinator).
- Any further unmapped key still voids its game/row and extends this set by a dated note before more G-S games.

**Training:** so that Sam's deck also meets the excluded half, the `sam` share is split across engines. Non-SEARCH
weights: RoyaleSim `sam` .25, our-engine `sam` .148, RoyaleSim `meta` .181, our-engine `meta` .180, our-engine
`rand` .241. Overall shares stay 50/30/20, with SEARCH games RoyaleSim/`sam`. Our-engine games use the full
all-deck mix with no exclusion.
- **Note to Amendment 4 (2026-10-18T12:11:43Z):** the amendment-4 smoke/rotation games raised 6 OwnCycle "card not in list" errors in 214
  games, on RoyalHogs, Berserker, Heal, Assassin, Miner and SpearGoblins (01 `$JOB/helper-amendment4-errors.json`). Per the
  rule above, these 6 join the RoyaleSim exclusion set (training and every G-S `--opp-exclude`):
  `Fisherman,GiantBuffer,GoblinCurse,GoblinDemolisher,GoblinDrill,GoblinGiant,GoblinHut,Graveyard,MegaKnight,MovingCannon,Phoenix,RamRider,SkeletonBalloon,SuspiciousBush,ThreeMusketeers,WitchMother,ElectroGiant,Tombstone,GoldenKnight,RoyalHogs,Berserker,Heal,Assassin,Miner,SpearGoblins`.
  Training tolerates residual RoyaleSim errors (recorded, no rollout) up to 5% of RoyaleSim games per hour; above that
  the helper stops the new blocks and reports. A G-S row that errors is rerun with `--only` (rows are
  deterministic) after the card joins the set by a dated note here.
- **Note to Amendment 4 (2026-10-18T12:39:31Z), source fix replaces the 6-card extension:** the G-S DEV reference hit the same
  OwnCycle error on Barbarians (a C56 card), so the error isn't card-specific. Cause: the frozen own-cycle tracker
  refills on a fixed clock, but RoyaleSim (authoritative: the executed slot held the card) can refill earlier.
  `bot/players/royalesim_translate.OwnCycleView.play` now moves such a card from the tracker's queue into the empty
  slot, counts `mismatch['early_refill']`, and still raises on any other desync. This changes only matches that
  previously crashed. The exclusion set reverts to the 19 probe cards. Rows/games that errored before this fix are
  rerun (G-S: `--only`), never dropped.
- **Note to Amendments 2/4 (2026-10-18T12:53:32Z):** the early-refill fix still failed (Rage, Barbarians): the frozen
  tracker's queue order drifts from RoyaleSim's. `RsimMatch.execute` now passes RoyaleSim's pre-step own hand, and
  `OwnCycleView.play` resyncs the tracker to it when the played card isn't in the tracked hand (`mismatch['resync']`;
  the rest of the queue keeps its tracked order). Matches without drift are unchanged.
  Rejected commands of the SEARCH **opponent** are now recorded per row (`opp_rejections`, reported) instead of
  voiding the row. The same deterministic opponent faces every arm of a case, so the paired difference stays fair.
  Our seat's rejections still void the row. Amendment 2's sanity item 4 is amended accordingly.
- **Note to Amendment 2 (2026-10-18T13:01:57Z), unclean rows:** with SEARCH opponents, RoyaleSim's card cycle sometimes departs
  from the ordinary cycle. The live search's own models then log errors (`live_errors`: "not in list", "public play
  inconsistent with ordinary cycle"; DEV case 0-0015). This is a simulator-fidelity limit, not fixable in this track.
  G-S rows therefore run with `--keep-going` (default off): an unclean row is kept with its issues, and the
  readout **drops that case from every arm** (case-level, so the comparison stays paired). Each row reports its
  dropped count and causes. **A G-S row with more than 5% of its cases dropped is invalid** (no pass/fail claim). G-E/G-B
  rows are unchanged.
- **Note to Amendment 2 (2026-10-18T13:46:12Z), drop limit recalibrated on DEV, before any G-S confirm game:** the DEV
  reference's SEARCH row dropped 4/60 cases (6.7%, all live_errors from the search players' cycle models; cases 0-0015,
  0030, 0039, 0047). The validity limit becomes **10% of cases for rows whose opponent is SEARCH** and stays 5% for
  K4CW-fp/R3a rows. Every G-S result lists dropped cases with their opponent-deck archetypes. If the dropped cases
  concentrate in one archetype (> 50% of drops), that archetype's paired difference is reported separately and the
  pooled claim is labelled accordingly.
- **Note to §4 G-E (2026-10-18T15:36:01Z):** the original DEV Sam-L16 rows (Battle Log pool v3.2) are invalid under the current
  driver: Goblin Hut decks cause SpearGoblin_Dummy translator omissions in 14/60 K4CW-fp and 18/60 R3a cases (main
  cdb3d08f5). From now on, G-E screens use the amendment-2 ALL-16 DEV rows (opponents SEARCH, K4CW-fp and R3a, all-deck
  mix with the RoyaleSim exclusion set, base DEV+400000, 60 cases per opponent) plus the dd1 row. Screen = mean of the
  paired differences vN − v2 over the K4CW-fp, R3a and dd1 rows. vN − search is reported per row. Candidate rule
  as before (screen ≥ +0.03, every difference ≥ 0, sane plays).
- **Note to §4 (2026-10-18T16:56:33Z), dd1 rows dropped:** dd1's fixed decks contain Goblin Hut decks, so 16/60 DEV cases void on
  SpearGoblin_Dummy translator omissions (main 7bb3451cb). Redrawing would change DD1's definition. dd1 is removed from the
  G-E screen (screen = mean of vN − v2 over the ALL-16 K4CW-fp and R3a rows) and from G-B (row C). Deck diversity is
  judged by the amendment-2 off-deck sanity row (our engine, every card). G-B now passes on row A's primary rule with
  no other row below −0.03.

## Recovery on 127x04 and additional Hog 2.6 account row (2026-10-20T06:43:05Z)

Coordinator b4f05b1c, direct Sam authorization on 2026-10-20: migrate the learner from unreachable 127x01 to 127x04; preserve source, algorithm, hyperparameters, league, environment mix and reward. The newest complete off-host state is the hourly mirror v327/update330 (policy, critic and both optimizers), SHA256 `c4957128464516a8416701c60bee1078756bd760156a0587e7814fb666d824cb`. Recovery uses `JOB/recovery04-20261020/run`, a separate version lineage, retaining original snapshots/results and newer policy-only caches unchanged. The v334 cache is not combined with older optimizer state. 01 is excluded from all operational dependencies and is not probed or changed by this migration. Actor deck follows the standing live-deck rotation rule, with fresh block numbers; production bank and 50/30/20 deck-kind shares remain unchanged.

**ADDITIONAL G-S row, registered before any further G-S game:** `HOG26-acct`, own deck `Skeletons+Musketeer+IceGolem+Cannon+Fireball+Zap+IceSpirit+HogRider`, our levels Skeletons8, Musketeer7, IceGolem7, Cannon9, Fireball8, Zap9, IceSpirit8, HogRider10; King9/Princess9. This row uses account levels, the same pinned opponent account-level table (rarity-floor rule retained), all-deck mix, 19-card RoyaleSim exclusion set, three opponents SEARCH/LIVE-K4CW-r16-fp/R3a, and three paired arms fast-vN/res-lb-RF-wintp/fast-v2. It has 150 cases per opponent at fresh confirmation-bank base+600000. Every candidate's entire bank is freshly drawn and dated/published before any game, disjoint from all used/closed banks; no existing bank is reused. The original ALL-16 and ALL-acct rows and their deck/level inputs are retained.

**Registered pass rule unchanged:** the primary SEARCH paired bootstrap remains pooled over the original ALL-16 + ALL-acct SEARCH cases, 4,000 draws, Random(0), sorted[100]/[3899], lower>0; original per-row K4 nonnegative and R3>=-0.03 requirements remain. The additional Hog 2.6 row reports the same paired contrasts, per-opponent CIs, archetype/drop details, fast-v2 reference and plays; it does not replace or reweight that primary estimator. Apply the existing 10% SEARCH / 5% other drop validity limits and plays25..60 to the new row. Report its K4>=0/R3>=-0.03 checks explicitly. A failed/invalid additional row is disclosed to the coordinator and cannot be presented as evidence of current-deck readiness. Every promotion candidate requires coordinator-owned independent review and LIVE swap; the helper never touches the Mac.

G-E screens continue on new recovery snapshots under the existing two-row definition, with the recovery lineage and checkpoint SHA explicit; original completed screens/results are immutable. OFF1 invalidity/source hold and closed v230/GB10 banks remain unchanged. No HealPulse fix is adopted here.

## Fresh G-B recovery04 v330 bank 423607048545216 (2026-10-20T15:36:07Z)

Registered before any game at 2026-10-20T15:36:04.212067+00:00: fresh G-B bank **423607048545216**, drawn on127x05 by `int.from_bytes(os.urandom(6),'big')<<4`; checked >10^9 from540 retained bank/constants, nearest distance3879371132518. CONFIRM1=2715349865347232 was consumed by the closed v10 VALID/FAIL confirmation and is never reused. Prior v10 readout SHA256646590cf92c07784f9d21b28e57c1164abf03363a3a5edb5e05b7928494aac51 remains immutable.

Candidate: **RECOVERY04 v330**, selected by §4's **best eligible G-E screen** rule over completed valid recovery-lineage v330/340/350/360 as of the coordinator's direct authorization. Their registered two-row DEV selection scores are .21666666666666667/.15833333333333333/.19166666666666665/.16666666666666669; all have both differences nonnegative and sane plays. The maximum selects330; these are biased DEV selection numbers, not gains. The candidate is frozen at `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/evals/checkpoints/recovery04-policy-00330.pt`, SHA25673bbbd860625a24e4e61f15dd30596c78542d04c4eedfcf2ab1346183de2c70e, recovered lineage only. Qualifying G-E artifact SHA256ec6904d683dcd1318ec92b91b2950ec8caf939efead28abfb3bdb5722d7d4a30.

**Registered G-B rows, arms, cases and rules unchanged:** Sam L16 base423607048545216,300cases per LIVE-K4CW-r16-fp/R3a; account base423607048645216,150cases per opponent, exact PF1 53-row strata copied verbatim, own levels HogRider8/Archers8/Cannon9/Skeletons7/Fireball7/Zap9/ElectroSpirit8/Valkyrie7/King7. Own deck HogRider,Archers,Cannon,Skeletons,Fireball,Zap,ElectroSpirit,Valkyrie. Each case has fast-v330/fast-v2/fast-f1a2 paired arms (2700 arm rows total). dd1 remains retired. Candidate/v2 thresholds .019753086419753086, f1a2 uses its registered calibration. Original pinned PF1 driver/pool/vocab/factory/models/runtime/source retained. No retries/redraws/drops; zero errors required. Primary A is Sam L16 K4CW-fp v330-v2, paired bootstrap4000 Random(0), sorted[100]/[3899], lower>0; no other retained row point<-.03; candidate Sam plays25..60 and within10ofv2; all registered PF1 reaction/idle/undefended metrics and secondary v330-f1a2 contrasts reported.

This registration changes no gate, G-S rule or OFF1 source hold. A G-B pass offers a search-prior/fast-tier candidate to the coordinator for independent review/A-B; helper never touches the Mac. No game/readout/result is claimed by registration. Unique receipt/output namespace: `gb-recovery04-v330-b423607048545216-confirm`, `evals/gb-recovery04-v330-b423607048545216-sam` and `-account`; no original snapshot/checkpoint/readout receipt overwritten. Admission uses existing48GiB/load90/console0/OWN08 temporary-guard-pause practice; minimum early RAM rotation only if needed, survivor resume through existing guards, restore64 after eval.

## Joint calibrated runtime and bounded-cache actor rollout (2026-10-21T02:50:56Z)

# Joint calibrated-runtime and bounded-cache actor amendment

Finalized 2026-10-21T02:50:27.793665+00:00. The coordinator accepted the cache validation and authorized this combined amendment. Both hosts completed the checks below before publication and before any production game from the new root or source.

The common main commit is `0dcab45f713c96613a5eb790b75b28367e726b8b`. It contains engine calibration `1831241d2a3e127d056b0f754c475f803d591375` and the Sol-approved bounded fast-prep cut-cache fix in `bot/search/lopp_fast.py`, `bot/cards/fc_cut.py`, and `bot/levels/configs.py`. The actor/learner algorithms, learner process and flags, hyperparameters, reward, mixture, league, models, bank, tau, deck and levels remain unchanged. `bot/rl` and the player code at this commit are byte-identical to the frozen 8f actor source. The new private source adds only a runtime pin declaration and matching root/pin selections in the launch shell, beyond main's reviewed cache fix.

Runtime on 04 and 08: `/mpac/sdicks02/repos/clasher-rl-runtime-0dcab45f7-joint`. Actor source: `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/source-0dcab45f7-joint`. Launch facade: `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/launch-0dcab45f7-joint`. Runtime content manifest `380c8141ab1c3cc26ea9490869b0023be9e37481532cdbeda75817462410bd30`; actor source manifest `43c20b2df9880af8634e1cd3efefb8ae369e3dad615af7f75bc830b59a9c6583`. The full manifests and file digests are in `joint-manifest.json` on each host. All engine/runtime assembler inputs are byte-identical between main 1831241d2 and main 0dcab45f7: the refresh privately copies the already built calibrated engine-cards+16.402 overlay root, verifies every file, and retains Fireball/Poison crown pins. Native `358cf506031bde59519fbb7ec59f07d3823112311b8d3192dbebd7a8871ef144`, gamedata `ccd2a5f18f49e23ad316d8ffecd32278fe9994fcdc74936c7410223b2faef756`, original v1/R3a/model7/corpus checkpoints unchanged. Separate writable host-local Numba caches belong to the new facade; old roots and sources are untouched.

Private launch declaration SHA256s: `bot/rl/hp1_run.sh` `44ca821130dfa755c6a49969210ad76433b66eaa94b8968af8c6566a0b98a615` and `bot/players/runtime.py` `551485b558466aef4300ae289a4325e3760a93aaa9b37c9f2a6877b09e9a7301`. The latter only adds `hp1rl-joint-0dcab45f7` with the new native/gamedata digests and the existing checkpoint/crown/scope options. No existing pin is replaced.

Accepted coordinator validation: `/mpac/sdicks02/scratch/rl-leak-20261020/REPORT.md` on 04, SHA256 `8c965005e4be6d2b664ec3d171e2324c30e063ee20a306923c8c2bf16338040b`. Original private-memory slope over minutes 10 to 120 was +5.26MiB/min; fixed was +0.71 over that same interval and +0.12 over minutes 60 to 120. The unchanged-root leak-only comparison had 131 common identical summary games and 130 identical rollout NPZs, digest `203c4781b7a0bd0fd6295d86999911f76964ed6544e3d02eec38cbacc7ab72ac`; one shared pre-existing RoyaleSim unmapped error is disclosed in that report. These are validation results for the cache fix, not a strength claim for the calibrated environment. The report records Sol approval, and the coordinator explicitly accepted it.

Both-host verification completed before publication. Each host passed all 13 native/Python parity cases and all 9 cache regression tests. CPU deployed decode parity passed, log-probability maximum absolute error was 1.9073486328125e-06, and self-KL was 0. Each host completed eight frozen K4CW level 16 smoke games, four ours and four RoyaleSim, with zero exceptions or unmapped diagnostics. All 16 cases/results are retained, with no failed-game retry or dropped case. Smoke generated no training NPZs. Calibration changes ours trajectories by design; old-root production games remain valid history. Verification timestamps: 04 2026-10-21T02:49:52.400040+00:00, 08 2026-10-21T02:49:54.295488+00:00. All 9409 runtime file digests and 17010 actor-source digests matched on both hosts, and complete before/after file hashes confirmed the running old root unchanged. Evidence directory: `/mpac/sdicks02/repos/clasher-rl-joint-0dcab45f7-20261021`. Readiness receipt SHA256 `15ab23320de4da40951e19bff0df500552c5d559051c837f20b1985e627011dc`; full raw observation SHA256s 04 `d14cc8d09060dab2e93a0c63ca0f33e878f61d27a716d8aa866122a9be84de0b`, 08 `a977260abe4bbd1ef06db45192b378a2e0bf5d9fba66be98ff5e37d0bd432da5`.

Rollout is by attrition. Every new replacement after this amendment uses both components together. Existing worker blocks retire under the unchanged oldest-first 1.75GiB RSS rule or existing memory protection; no forced retirement solely to switch source. Pre-GO gated attempts 160/162/164/166 had no actor Python, metadata, release, games or BLOCKS entries and were cancelled before games; their spent IDs/receipts/logs are retained. Their four already-consumed retirement credits 144/146/148/150 transfer once to fresh 168/170/172/174, with no additional credit consumption. 08's unconsumed 145->161 and 147->163 credits and all further 08 refills stay held until the original external window's EVAL-DONE or expiry. Then restore 64 using new source/runtime under normal 48GiB CPU/load/console admission and exact memory plus central-error receipt coverage before games.

The existing recovery04 learner 1183289/Python 1183349/source 095785f4422079f048a0d9503e714c7fe4e38683 continues the same recovered policy, critic and both optimizers. Mixed old/new-root rollouts stay valid, with each block's immutable runtime/source identity recorded. Preserve raw logs, NPZs, old cases, readouts, frozen checkpoints, bank ledgers and completed results. No history deletion, relabelling, redraw, reference rerun, OFF1 source-hold release, gate change, OFF1 retry, G-S confirmation or LIVE/Mac action is authorized by this amendment.

Capacity can rise only after approximately one hour of observed flat RSS on actual new-source workers, measured on the same PIDs with warm-up identified. Raise one fresh W8 block per admitted step above 64 toward load <=90, retaining 20 GiB floor, 24 GiB preemption and 28 GiB resumption, normal 48 GiB admission, existing console policy, nice 15, CPU leases and BOTH coverage before games. Keep 1.75GiB rotation as the safety backstop. The accepted diagnostic's RSS does not substitute for production observation. No new agent, monitor, thread or schedule; the same enabled 30-minute watch records the evidence and advances the rollout.

Reviewed cache implementation SHA256s, verified on both hosts:

- `bot/search/lopp_fast.py`: `fcdc9614c284894c35e73a9a973232c6d6a562358eedf308359a57899cd53b2b`
- `bot/cards/fc_cut.py`: `0e1ecb00bf681221cd96010dd56b31267615c4229ef719004200e0771547b358`
- `bot/levels/configs.py`: `ebcf24a2af29bf06042f604000e1a1b312852c8f507ee89a74b8c567a4d4d402`

## Joint actor amendment evaluation scope clarification (2026-10-21T03:39:53Z)

Coordinator clarification dated 2026-10-21, after joint amendment 3bf68f9297ea0d0ba17091572c0f7df5cc1cd67f.

The joint amendment changes ACTOR training source/runtime ONLY. Registered G-E, G-S and G-B screens keep the SAME registered evaluation runtime/source as v330 through v360, so the snapshot series stays comparable. Evaluation source remains 8f5272934f456e930aa250bba45eaa9b3c259b71 and runtime remains live16402b-r3. Original cases, cached reference rows, masks, statistics, gates and learner settings remain unchanged. A later evaluation on the calibrated engine requires its own dated registration and is not authorized now.

The first v370 DEV attempt, PGID2428417, was stopped after an ambiguous instruction was interpreted as requiring the joint evaluation source. Its 17 partial rows, checkpoint, logs and abort evidence remain preserved as excluded history. They will not be reused or scored. The coordinator explicitly authorizes a fresh v370 DEV execution on the registered evaluation source/runtime, with a distinct receipt and output namespace. No old-root training games are invalidated.
