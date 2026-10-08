# ClashAI deep dive: what "way far in trophies" actually means

Research snapshot: 2026-10-08. Author: research sub-agent for the 127x05 coordinator. Read-only; nothing was run
from the ClashAI tree.

- **Repo inspected:** [vegetableleaf/ClashAI @ `8d4053d`](https://github.com/vegetableleaf/ClashAI/tree/8d4053dfea1be589c4b487154ed2da1b98d6aa9e)
  (2026-10-08 16:47 EDT). Cloned to `/mpac/sdicks02/tmp/clashai-research/repo` on 127x05.
- **Previous look:** `5595ab0` (2026-08-07), in `reports/public_clash_royale_bot_comparison.md`. Since then there are
  1,529 commits, 10,984 files changed and about 3.5M lines inserted, mostly journals, logs and card templates. 133
  commits landed on 2026-10-08 alone. GitHub shows 182 stars, 26 forks, 7 open issues, no releases and no
  Discussions.
- **Citations:** `HANDOFF.md:3676` means line 3676 of that file at `8d4053d`. HANDOFF is newest-first in its top part
  but not strictly so; blocks dated 10-02…10-08 live at lines 3637–4950.
- **Evidence labels:**
  - **measured:** a number in their committed logs or ledgers.
  - **claimed:** stated by the author or their agents, with no raw artifact we can check.
  - **inferred:** my reading of several facts together.

## 1. Summary

- **The trophies are real but mostly inherited.** ClashAI's bot plays Trophy Road on the owner's *main, human-built
  account*, which was already at about 10,000 trophies when the bot's first live win rate was ever measured
  (2026-09-18). Its best reading is **11,272 on 2026-10-08**, up from 10,364 on 2026-10-02.
- **The climb is an equilibrium, not a ramp.** Over about 1,136 valid ladder matches (09-25…10-08) every checkpoint
  sits at about 50%: R1 51% (n=303), R1e 51% (n=390), latest stack 54% (n=102). The bot holds roughly 11k and climbs
  slowly at best. The project's own verdict: "No new model has … demonstrated sustained progress beyond 11,000
  trophies" (`HANDOFF.md:47`). Their goal is 11k→14k.
- **Nothing is externally verifiable.** There is no player tag, no public profile, no public full-match video and no
  social post. We have only committed per-match summaries (`L74/loss_review/matches.jsonl`, 1,169 logs) and cropped
  trophy screenshots ("11222", "-30") with names masked. Those records are internally consistent, but the screen
  trophy delta doesn't reconcile with the logged W–L (§2.3).
- **How they got to about 50% at 11k:** they changed many things at once:
  - perfect state from a **read-only memory reader** on MuMu, replacing their pixel/YOLO stack, which managed 35% live;
  - an all-deck "gen" imitation transformer (about 1.3M params) trained on **3.5M rows from 14.8k pro replays
    re-driven inside the real game binary** (`libg.so` via `IMAX9D/cr-native-sandbox`);
  - small PPO gains in a third-party Rust sim (RoyaleSim, MIT);
  - many live-plumbing fixes;
  - a single X-Bow deck at **level 15–16 cards**.

  Decision-time rollout search was **null or negative** for them.
- **What Clasher should take is method, not mechanism.** The memory reader, the native sandbox, logged-in RoyaleAPI
  crawling and botting a main account all break our rules or are ToS-sensitive. What transfers:
  - their live evaluation discipline: ladder win rate is useless at equilibrium, so use trophies or interleaved A/B,
    plus a power calculation;
  - their loss-review ledger with pro-baseline behaviour metrics;
  - their measured latency and actuation facts: tap→card rotation is a median 1.4 s, plus tap-snap and confirmation
    rules;
  - their warning that train/serve skew in latency compensation produced a live-only overspending habit, the main
    measured loss mechanism;
  - the "ghost screen" instrument;
  - their negative search result, which should become a gate for ours.

## 2. Evidence table

### 2.1 Trophy and win-rate claims

| # | Date | Claim | Account / arena | Source | Evidence type | Verifiable? |
|---|---|---|---|---|---|---|
| 1 | 2026-09-18 | First live win rate ever: **35.1%** (13W-22L-2D, n=37, CI 21.8–51.2) with the pixel/YOLO "S1" policy | Main account; an opponent shown at 10,000 trophies; Trophy Road | `GAUNTLET_LOG.md:2025-2034` | measured (session ledgers; 3 sessions at 33/37.5/33%) | No: logs not public; sample tiny |
| 2 | 09-18 | "Engine-to-live gap ~39 points": same checkpoint scored 74% on engine ghosts | — | `GAUNTLET_LOG.md:2029` | measured | Internal only |
| 3 | 09-25…10-04 | First memory-reader + generalist model `gen_v1_s0`: **40%** (40-59-2, n=101) | Main | `L74/loss_review/report.md` §1 | measured (per-match rows committed) | Partly: `matches.jsonl` committed |
| 4 | 10-02 21:26 | **10,364 trophies** (passed the 10,325 milestone; Trophy Road reward screen) | Main | `HANDOFF.md:3676` | claimed in journal (screen-observed) | No |
| 5 | 10-02…10-03 | league1c_u0075: **51%** (102-99, n=201) | Main | report.md §1 | measured | Partly |
| 6 | 10-03…10-04 | rseries_r1_u0155: **51%** (155-148, n=303) | Main | report.md §1 | measured | Partly |
| 7 | 10-04…10-08 | R1e: **51%** (198-192, n=390). Owner's supervisor says "W 367 / L 354 total" for the run, which doesn't match | Main (some second-account games may be mixed in, `HANDOFF.md:4057-4060`) | report.md §1; `HANDOFF.md:4942` | measured, with an inconsistency | Partly |
| 8 | 10-07 00:2x | **11,222 trophies**, read by their digit matcher | Main | `HANDOFF.md:3937`; screenshot crop `L73/trophies/img/main_live_idle.png` | measured (crop committed; name and tag masked) | Weak: a cropped number, no identity |
| 9 | 10-08 ~09:44 | stack2k (R3c+barrel2k+CellRefine): **54.8%** over 73, trophies **11,127 → 11,272** | Main | `HANDOFF.md:4890` | measured | No (trophy deltas logged for only 4 matches, report.md header) |
| 10 | 10-08 | Current live (TowerRefine w2): 38% (6-10, n=16) | Main | report.md §1 | measured | Partly |
| 11 | 10-07 | "Live win rate cannot separate models: every checkpoint sits ~50% … matchmaking equalises at the held trophy level" | — | `HANDOFF.md:3941-3943` | the author's own conclusion | — |
| 12 | 10-06 | "No new model has … demonstrated sustained progress beyond 11,000 trophies" | — | `HANDOFF.md:47-48` | the author's own conclusion | — |
| 13 | 10-07 | A second account ("ClashAI") will be "ground" from low trophies with R1e | Second account | `HANDOFF.md:4052-4060` | plan; started by the owner 10-07; no results logged | No |
| 14 | 2026-10-04 (ours) | "ClashAI ~11k trophies via full-corpus BC + live loop" | — | our `COORDINATOR.md:63`; `HANDOFF_F35_20261005.md` §5.3 | our paraphrase | **Needs correction** (§2.3) |

### 2.2 Simulator claims

All of these are measured in RoyaleSim. None is live.

| Instrument | Result | Source |
|---|---|---|
| Ghost screen (299 held-out pro replays, opponent = recorded commands), paired pp | R1 u0155 vs gen_v1: +3.0 [−0.3, +6.4]; R1e vs gen_v3.1c: +4.35 [+1.34, +7.69] | README "Results"; `HANDOFF.md:3940` |
| Reactive (frozen policy opponents) | R1 u0155: 14/24 vs gen_v1, 24/24 vs S1 | README |
| Benchmark v3 (960 paired) | "live setup beats R1e +8 pp (p .0001)"; lethal-Rocket option 652 → 660 wins | commits 2026-10-08 11:41, 15:41 |
| Search S0 / option 1 (rollout search over the policy) | null vs gen; **−7 wins/24 vs S1** when the opponent model is wrong | `HANDOFF.md:5636, 5638` |

### 2.3 What the trophy numbers do and don't show

- **Start point (inferred, high confidence):** the main account was about 10k before the bot was any good.
  - On 09-18 the pixel bot was already meeting 10,000-trophy opponents while winning 35%.
  - The deck plays at "real account levels": X-Bow 16, Knight 16, Skeletons 15, Tornado 15
    (`HANDOFF_ARCHIVE.md:824`, `log.txt:946`).
  - The owner calls it "the MAIN account (11k)", as distinct from a new "ClashAI" second account
    (`HANDOFF.md:4052`).

  So the 10k is the owner's own human play. Nothing in the repo says the bot climbed from a low start.
- **The delta doesn't reconcile.**
  - Screen readings go 10,364 (10-02 21:26) → 11,272 (10-08 morning), +908 trophies. At ±30 a match (the committed
    result crop shows "-30"), that needs about 30 net wins.
  - The logged families in that window add up to about +13 net wins (league1c +3, R1 +7, R1e +6, candidate −7, stack2k
    +8, towerref −4), or about +400 trophies.
  - Possible explanations (none tested): matches missing from the logs, the owner's manual games on the same account
    (it's also open on the owner's phone, `HANDOFF.md:3684`), deltas other than ±30, or mislabelled family windows.
  - **Treat +908 as an upper bound on the bot-driven climb.**
- **Opponent mix is unknown.** Their own note: "Cannot distinguish real players from bots … trophy road serves both"
  (`GAUNTLET_LOG.md:1977`).
- **Card-level advantage is unmeasured.** Level-16 X-Bow and Knight at 10–11k is a plausible advantage, but nobody has
  measured it.
- **Correction for our records:** "ClashAI ~11k via full-corpus BC + live loop" should read: *"ClashAI's bot holds
  about 50% at 10–11k Trophy Road on the owner's human-built main account (level 15–16 X-Bow deck, memory-read state).
  The best net bot-driven gain is ≤ +900 trophies over about 1,000 matches, and no external verification exists."*

## 3. What changed since `5595ab0` (2026-08-07 → 2026-10-08)

At `5595ab0` the repo held `icebow/` (pixel/YOLO bot, BC + DDQN/PPO on a hand-written sim), `trol/`, `config/`, the
README and `log.txt`. There was no `pipeline/`. Changes, roughly in order:

1. **Aug: second deck and sim-parity work.**
   - Added the `hogeq/` deck (a copy of the icebow tooling).
   - Added `research/sim_parity/`, a wiki-sourced card-data ledger for their own hand-written sim.
   - Added X-Bow and spell "doctrine" research from YouTube guides.
2. **Early Sep: the real-engine era.**
   - Adopted `IMAX9D/cr-native-sandbox`, which runs the **original Android x86_64 `libg.so` headless** at a frozen
     build. Its README describes JNI/RVA relocation per game version.
   - Pro replays are re-driven "tick by tick in the real game engine" to produce exact public observations.
   - Their own hand-written sim and pixel-CNN RL path were retired: RL "never improved on its imitation starting
     point".
3. **09-18: first live win-rate ledger.** 35% with the pixel/YOLO S1 policy. Most of the work up to then was live
   plumbing failures: occluded capture, deck mismatch, broken health checks (`GAUNTLET_LOG.md:1965-2034`).
4. **09-24: live memory reader.** The MuMu read-only reader from the same upstream reads tick, **both players'
   hand/next/elixir**, and per-entity side/x/y/card/level/HP (`HANDOFF.md:5622`). The model gets own state plus public
   opponent events; opponent elixir comes from a public-event counter (`pipeline/opp_elixir_count.py`).
5. **09-24/25: generalist imitation.**
   - `pipeline/` was created (177 files, 109 test files): obs contract, dataset_gen, `model_gen.py` ("GenModel"),
     `train_gen.py`, `live_gen.py`.
   - gen_v1: 1.34M params, 4 epochs, about 6.5 h on a laptop GPU. It matches the icebow specialist on the specialist's
     own validation set and covers all decks.
6. **09-29…10-01: switch to RoyaleSim.**
   - RL and acceptance moved to RoyaleSim/RoyaleGym, a third-party MIT Rust engine (20 Hz, integer, 18,000 units per
     tile, 133/145 cards loadable), with a pinned-runtime fingerprint.
   - They measured the live condition (26-tick action delay plus 26-tick look-ahead) and ran a tau sweep (gate
     threshold 0.35).
   - S0 search was null.
   - Live fixes: confirm on slot rotation, affordability mask, quarter-tile inset for 2×2 buildings, wait for the
     battle clock.
7. **10-02: unattended ladder.** `ladder_nav.py` handles Play Again, daily chests, Trophy Road rewards, promos and the
   "another device" stop. A supervisor restarts the run up to 10 times. Discord clips go out every 30 minutes.
8. **10-01…10-04: R-series PPO and gen_v3.x.**
   - PPO from gen with GAE, critic warm-up, a KL leash, and a league of snapshots + S1 + census decks.
   - Feature v4 "public observation": projectiles with time-to-impact, spell areas, recent opponent plays.
   - Full re-drive of 14,818 recordings, giving 3,517,863 rows.
   - R1e went live 10-04.
9. **10-04…10-06: Codex autopilot.** Heavy audit and receipt bureaucracy; the HANDOFF top shows the style. Added a
   public opponent-hand belief (`pipeline/opponent_hand.py`, FIFO cycle from public plays) and a Hero Ice Wizard
   identity fix. The owner retracted a "tower" model for over-defending.
10. **10-06…10-08: Claude lead again.**
    - Decode options: tau by phase, X-Bow class sampling, anti-leak, hazard gate.
    - Add-on heads: CellRefine (fine cell scores), TowerRefine (tower tokens for chip Rockets), lethal OT Rocket option.
    - R2/R3/R4 PPO variants; a GCP 128-vCPU VM for training.
    - **L74 loss review over 1,169 live logs**, **L74 latency budget over 6,721 confirmed plays**, and an opt-in
      persistent adb shell (`--fast-input`).

## 4. How it works now

| Dimension | ClashAI at `8d4053d` | Evidence |
|---|---|---|
| **Perception** | **None in the live path.** State comes from a read-only memory reader (MuMu, rooted adb, game build 160402012 pinned; "do NOT accept an APK update"). The pixel/YOLO stack is retired; it reached 35% live. Pixels are still used for hero-ability button state, menu navigation templates and the trophy digit reader. Live opponent-elixir counter error: MAE 1.34 with +1.14 bias early (09-29), later over-reading by 0.34 on average, checked against `opp_elixir_true_EVAL_ONLY` from memory. | `HANDOFF.md:5622, 5625, 3649`; report.md factor 5 |
| **Action space** | Gate (play/wait), then a pointer over the 4 hand cards, then a per-cell head conditioned on card identity over a **36×64 half-tile lattice**, plus "wait for card X". Add-ons: CellRefine (finer cell scores), TowerRefine (tower tokens). An affordability mask on extrapolated elixir and a legality guard. 2×2 buildings are tapped a quarter tile inside the corner because the official client snaps them (34/35 Tesla taps landed one tile off). | README "The models"; `model_gen.py:63`; `HANDOFF.md:5625` |
| **Model** | Transformer over entity tokens plus 2×2-tile patch tokens plus a global token (`S1Model` trunk). Heads: gate, card pointer, cell, wait-for-X, value. About **1.34M params**. Card identity inputs mean one network plays any deck. CPU inference: decide median 72 ms, p95 117 ms. | README; `HANDOFF.md:5622` block; `L74/latency/budget_20261008.txt` |
| **Data** | **14,818 pro recordings / 14,661 replays / 4,283 decks** from RoyaleAPI (crawled with logged-in throwaway session tokens; they declined IP rotation) plus Hugging Face `VanguardX101/IL_Replay`. Re-driven in the native engine, giving **3,517,863 rows**. Pro icebow sides: 2,244. No own-play BC in the current lineage; the original record-yourself BC is retired. | README; `CODEX_BRIEF.md:52`; `HANDOFF.md:10057`; `tools/README.md:10` |
| **BC → RL** | PPO in RoyaleSim from the gen checkpoint. Per-match LOO advantage, then GAE (γ 0.999 per row, λ 0.95) with critic warm-up. Terminal win/loss reward; tower/crown potential shaping was tried and "drifted the gate away from the pros". KL leash to the imitation model (a KL-free run degenerated). League: latest 0.35 / older snapshots 0.25 / init 0.2 / S1 specialist 0.2, over 183 census decks. Rollouts sample at T=0.5; live is greedy argmax. Gains are small: about +3–4 pp ghost, reactive not significant. | `pipeline/rl_royale.yaml`; README "Negative results"; `HANDOFF.md:3940-3944` |
| **Deck** | **One deck live: "icebow"** (X-Bow, Rocket, Tornado, Log, Skeletons, Evo Knight, Evo Tesla, Hero Ice Wizard) at the owner's levels 15–16. Hog/EQ is secondary and not live. No in-ladder deck switching. The second account would use the generalist reading its deck from memory; untested. | `GAUNTLET_LOG.md` L67ce; `HANDOFF.md:4053` |
| **Latency** | Live play extrapolates the board **26 ticks** (1.3 s) before deciding. R8 extended this to projectiles and effects: pre-emptive Log 23.5% → 49.8%, pros 39.1%. Measured over 6,721 plays: tap → hand-slot rotation median **28 ticks (1.40 s)**, p95 44. Their code is about 0.3 s of that (decide 72 ms + adb tap 150 ms); "1.13 s outside our code". Each extra second of their latency adds only about 12 ticks of gap (OLS), so most of the delay is fixed game/emulator pipeline. CPU starvation from training on the same laptop pushed decisions from 40 ms to 101–120 ms; they now stop live while training. | `L74/latency/budget_20261008.txt`; `CODEX_BRIEF.md` §2; `HANDOFF.md:3903` |
| **Hardware** | Windows laptop (GPU about 8 GB, shared with the desktop), MuMu emulator on the same machine, two Android VMs for re-drive (16 engine slots), and since 10-07 a GCP n2 VM with 128 vCPU and 503 GB (free credits). | `HANDOFF.md:3700ff, 4070, 4155` |
| **Live volume** | About 1,169 logged live matches (1,136 valid) from 09-25 to 10-08, at about 17–19 matches/h. Plus 37 pixel-era matches on 09-18 and friendly matches. | report.md header; `GAUNTLET_LOG.md:1977` |
| **Matchmaking** | Plain Trophy Road "Play Again". Daily chests and Trophy Road rewards are collected automatically. No trophy-band control. They concluded win rate converges to about 50%, so they compare models by trophies or interleaved A/B: "~400 matches per arm for a 10-pt gap, ~170 for 15 pts". | `HANDOFF.md:4031, 3941` |
| **Evaluation** | Pre-registered, paired, one change per experiment, behind opt-in flags whose defaults are byte-identical. Instruments: ghost screen, reactive vs frozen policies, benchmark v3 (960 paired), behaviour telemetry vs a pro baseline (Rocket share, elixir at play, defensive X-Bow share, pre-emptive Log). Blind verifier agents check merges. | `CODEX_BRIEF.md` §1 |

### 4.1 Information and ToS posture versus our rules

| Practice | Our fair-information rule | ToS-sensitive beyond screen+input? |
|---|---|---|
| Read-only **memory reader** of the live client. It sees the opponent's hand, next card and elixir; they say these are never model inputs and use them only for evaluation | **Conflicts.** Not screen-derived. It also exposes hidden state to the pipeline, so leakage depends on discipline, not architecture | **Yes:** client memory inspection on a rooted emulator |
| **Native sandbox** running Supercell's `libg.so` outside the client, with reverse-engineered offsets, for replay re-drive | Not a play-time information issue | **Yes:** reverse engineering and executing the proprietary binary. Off-limits for us |
| RoyaleAPI crawl with **logged-in session tokens** and `cf_clearance` (they refused IP rotation) | n/a | **Yes**, toward RoyaleAPI's terms |
| Training rows for gen_v1…v3 and R-series carried the **recorded** opponent elixir. They label these "privileged-input"; v4 switched to the counter | Mostly fair under our rule, since exact elixir is derivable. Unsafe as practice because recorded truth ≠ derivation | — |
| S0 search rollouts started "from the true state incl. the opponent's hand" (disclosed) | **Conflicts** (hidden hand) | — |
| Public hand belief (FIFO from revealed plays; 97% precision on full-hand claims at about 42–44% coverage on re-drives) | **Consistent** with our rule; equivalent to our derived-state tracker | — |
| Unattended ladder botting on the **owner's main account**, with chest and reward collection | Our authorization covers a throwaway account on the Mac emulator only | **Yes** (automation), as for any live bot |
| Detection evasion | None found in the live path (keyword grep, not an audit). Taps are plain `adb input` | — |

## 5. Lessons for Clasher, ranked

Ranking is by (expected impact on reaching human-level *live* play) ÷ cost. Impact and cost are rough estimates.
"Rule check" flags conflicts. For each item I say whether it's what made ClashAI strong or just co-occurred with it.

### L1. Treat ladder win rate as a non-instrument; pre-register a trophy-trajectory and interleaved A/B protocol

**Impact: high. Cost: low** (a day of protocol plus a trophy digit reader). **Rule check:** none.

- **Evidence:** every ClashAI checkpoint sits at 50–54% at its held level (§2.1 rows 5–11). After about 1,100 matches
  they still can't rank models live.
- **Why it matters for us:** on a fresh throwaway account, win rate will look good early (weak and bot opponents at
  low trophies) and then converge to 50%. The metric we want is **trophies versus matches from a fixed start** and
  **paired, interleaved A/B** (alternate arms per match on the same account and time window).
- **What to do:**
  - Write it into the L3 protocol now.
  - Log trophies every match from day one, with a results-screen delta plus the main-menu total. Their digit matcher
    is 65/65 correct in-sample.
  - Use their power numbers to size runs: about 400 matches per arm for a 10 pp gap.
  - Record our card levels and trophy band with every block.
  - Keep L2-v4's controlled oracle-vs-pixels arms as the primary strength instrument. Live ladder is for validation,
    not selection.

### L2. Adopt a standing loss-review ledger with pro-baseline behaviour metrics

**Impact: high. Cost: low–medium** (we have native-truth replays and C56 human data to build the baselines).
**Rule check:** none.

- **Evidence:** their L74 report found the dominant live loss mechanism without any new training.
  - The bot meets **70% of pushes with < 4 elixir** (pros 24%). A push met that way is lost 16.5 pp more often, within
    the same match.
  - It plays cheap cards at < 5 elixir 2–3× as often as pros.
  - Factors they assumed mattered turned out *contradicted*: slow first answer, placement error ≥ 1 tile.
- **What to do:** for Clasher, compute the same metrics on (a) C56/S122 human replays, (b) our search player in sim,
  and (c) L2-v4 pixel arms:
  - elixir at push arrival;
  - plays per minute at < 5 elixir;
  - share of pushes met while short;
  - X-Bow/siege placed into a full opponent bar;
  - lethal-spell windows missed.

  Use them as **diagnostics next to win rate**, never as reward. This also tests whether our search overspends: a
  delay-aware planner with a 200 ms deadline can drift toward cheap immediate answers.

### L3. Make latency compensation train/serve identical, and measure tap→execution on our Mac emulator

**Impact: high. Cost: medium.** It fits T2 (the actuation bench) already in `live-loop/v4/DESIGN.md`. **Rule
check:** none.

- **Evidence:**
  - Their measured tap → card-rotation is a median **1.40 s (28 ticks), p95 2.2 s**. Only about 0.3 s is their code.
  - Their 26-tick look-ahead fixed late reactions (pre-emptive Log 23.5 → 49.8%) but **raised the gate's p_play by
    +0.05–0.09 live only**. That's the leading suspect for the overspending economy above.
- **What to do:**
  - Our delay-aware planner must use the *measured* execution-delay distribution of the official client on the Mac
    emulator, not the L2 renderer figure.
  - Any "advance the board by Δ" transform must be applied identically in imitation training rows, search and live.
  - Add a T2 output: the distribution of tap → own-card execution tick, and its dependence on emulator, input method
    and CPU load.
  - Separate the live machine from heavy jobs; they measured 40 → 110 ms decisions under contention.

### L4. Gate our search on human-like opponents, not only scripts

**Impact: high. Cost: low**, as an addition to gate (b) in `imitation/DESIGN.md`. **Rule check:** none.

- **Evidence:** ClashAI's rollout search over its own policy was **null against imitation opponents** and
  **significantly worse (−7/24 wins, t −3.2) when the opponent model was wrong** (`HANDOFF.md:5636-5638`).
- **Context:** our search's evidence (Stage 5: 0.875 vs C56 scripts) is against scripts. L2 lost 27/48 with pixels.
  Theirs is a weaker search (12 s heuristic scorer, 4 cards × 3 cells, a 240-tick horizon). But the failure mode, a
  search that trusts a wrong opponent model, is exactly what our hypothesis-stratified roots (ELT, K=4) aim at.
- **What to do:** add a pre-registered arm in which the search player faces (a) the v1/v2 imitation policy as
  opponent and (b) human-ghost replays (L5), with the search's opponent model deliberately mismatched. If search ≤
  policy there, our "search actor + imitation prior" direction needs rethinking before L3.

### L5. Add a "ghost screen": play our player against recorded human command streams

**Impact: medium. Cost: low** (C56 replays and native-truth sim already exist). **Rule check:** none.

- **What it is:** they replay a held-out pro opponent's commands open-loop and score the candidate paired over 299
  pinned replays. It's a cheap, deterministic, human-distribution opponent with tight paired CIs.
- **Caveats:**
  - Ghosts don't react: 29% of their engine matches "outlive the scripted opponent", and the 74% engine vs 35% live
    gap shows how flattering it can be.
  - Use it as a screen and regression test, never as the strength claim.
  - It complements L4 and our existing script opponents.

### L6. Imitation design: keep our factorization, sample proposals rather than argmax, and expect weighting tricks to do little

**Impact: medium. Cost: low** (design tweaks to the v1/v2 heads and proposer usage). **Rule check:** none.

- **Confirmed by their data:**
  - A card-identity generalist equals a deck specialist on the specialist's own data.
  - Gate → card pointer → card-conditioned cell plus "wait for X" is a workable factorization; ours is the same shape.
  - Wait-label tweaks, evolution tags and 2–4× context weighting on rare events gave **no measurable gain**.
- **Their main imitation failure was decoding:**
  - Rocket had calibrated P = .24 at pro Rocket moments (AUC .84) but was argmax only 22% of the time. Live Rocket use
    was 1–2% of plays against 5.8% for pros.
  - X-Bow argmax collapsed to 2 cells (93% vs pros 74%).
- **For us:** the imitation model is a *proposer*. Gate (b) should check that rare high-value actions (spells on
  towers, win-condition placements) appear in the top-k proposals at roughly pro frequency. That's a cheap offline
  metric.
- **On the half-tile lattice:** our DESIGN already decided tile resolution from our data (100% tile-centred labels).
  Their lattice evidence doesn't contradict that. The relevant fact is client tap snapping (2×2 buildings to corners),
  which belongs in actuation (L8), not the policy head.

### L7. Model in-flight projectiles and effects with time-to-impact in state and search

**Impact: medium–high. Cost: medium** (perception must time projectiles from pixels). **Rule check:** none, since
projectiles are public.

- **Evidence:** advancing projectiles and effects in the look-ahead doubled their pre-emptive Log rate to above-pro
  levels. Their v4 observation adds projectiles with target and time-to-impact, and spell areas with remaining time.
  Barrel-type answers depend on it.
- **What to do:** confirm the v4 perception spec emits projectile identity and age (the temporal event head already
  regresses event age), and that the search rollout state is seeded with them.

### L8. Steal the actuation and confirmation rules

**Impact: medium. Cost: low.** **Rule check:** none, as long as it isn't evasion.

- **Their rules:**
  - Confirm a play on **hand-slot rotation alone**. Elixir-drop confirmation fails for cheap cards in 2×/3× because
    regen hides the cost; that bug froze their bot for 3 s per false miss.
  - Mask to cards affordable at the *extrapolated* elixir.
  - Never act on the first frame or before the battle clock runs.
  - Inset 2×2 building taps by a quarter tile.
  - Keep one persistent input channel (`--fast-input`).
- **Our numbers:** L2 had 77% of known deployments rejected. Their 288/310 confirmed (93%) is a realistic target.
  Fold these rules into T2.

### L9. Opponent elixir and hand derivation: account for bodiless spells and bias

**Impact: medium. Cost: low.** **Rule check:** consistent.

- **Evidence:** even with *perfect* events from memory, their public counter had MAE 1.34 with +1.14 bias early.
  Their notes blame bodiless spells and abilities. Their FIFO hand belief was right on 97% of full-hand claims, but
  could make a claim only about 42–44% of the time.
- **For us:** our ELT design (exact derivation, multiple hypotheses) is better founded. Add explicit tests for spells
  that leave no body, champion and hero abilities, and Collector-style grants. Report coverage (how often the belief
  is certain), not just accuracy.

### L10. Deck strategy for the throwaway account

**Impact: medium. Cost: low** (a decision plus a sim check). **Rule check:** none.

- **Co-occurrence, not cause:** ClashAI's level-16 X-Bow deck at 11k is a high-skill-floor siege deck with maxed
  cards. We can't copy that: a fresh account has low levels and few cards.
- **What to do:**
  - Pick the deck by where our engine fidelity and search are strongest (C56 coverage, Stage 5 per-family results).
  - Prefer decks whose key interactions our sim has verified.
  - Freeze it for an entire evaluation block. Deck changes confound trophy trajectories.
  - Record opponent card levels where visible, since levels are a strong confounder at low trophies.

### L11. Live operations: navigation, supervisor and stop rules

**Impact: low–medium. Cost: low.** **Rule check:** the throwaway account only; no purchases.

- **What exists:** they built and field-tested handlers for content-update modals, Trophy Road reward trees, chest
  flows, "another device connecting", and loading stalls. There's a STOP file and a capped restart supervisor. Each
  unhandled screen cost them hours of downtime.
- **For us:** list these screen types for the official client and have the L3 navigator stop on unknown screens and
  save frames, rather than tapping through blindly.

### L12. RL last, leashed

**Impact: low (confirms the current plan). Cost: n/a.** **Rule check:** none.

- **Evidence:** PPO from BC gave them +3–4 pp ghost and nothing distinguishable live. KL-free degenerated; shaped
  reward drifted from pros.
- **For us:** this supports our "PPO is the last stage, v7r3 held" direction. When we get there, keep a KL anchor to
  the imitation prior and judge with L1/L2 instruments.

### What made them strong vs. what merely co-occurred

| Likely causal (some evidence) | Co-occurred or unmeasured |
|---|---|
| Exact state from memory; a pixel-era 35% vs memory-era 40–51%, confounded with model changes | Starting at a human-built 10k |
| Large native-fidelity pro corpus (3.5M rows) for imitation | Level 15–16 cards |
| Live plumbing fixes (confirmation, affordability, clock, tap snap) | X-Bow specifically |
| Gate threshold tuning (tau 0.35) | Most RL variants, add-on heads and decode options: all inside ±4 pp in sim, invisible live |
| Projectile look-ahead | The audit-receipt apparatus |

No single factor has been isolated. Their path from 35% to about 51% changed reader, model, RL and fixes all at
once.

### Do not copy

These conflict with our rules or the ToS:

- the memory reader;
- `cr-native-sandbox` and anything that loads `libg.so`;
- logged-in or rate-limit-evading crawls;
- search from true hidden state;
- live play on a personal main account;
- hand-written card-specific assists (they banned these themselves; see `CODEX_BRIEF.md` §1.4).

## 6. Licensing

- **ClashAI has no license.** There is no LICENSE file at root or depth ≤ 3, and the GitHub API reports
  `license: null`. Default copyright applies: **all rights reserved**, and contributor PRs (e.g. craftingbrick112's)
  add more copyright holders.
  - **We may:** read it, cite it with links, and re-implement *ideas*. Ideas, metrics, protocols and published
    numbers aren't copyrightable. Examples: the loss-review metric definitions, the ghost-screen protocol, power
    calculations.
  - **We may not:** copy code, configs, templates, card crops, screenshots, docs text or data files into our public
    repo, even with attribution, without the author's permission.
  - **Recommendation:** re-implement from scratch, cite the commit, and quote no code.
- **RoyaleSim / RoyaleGym** (PyPI `royalesim` 0.1.22, GitHub `RoyaleGym/RoyaleSim`): **MIT**. We could reuse it with
  attribution, for example as an independent cross-check of our engine's interactions. Check its game-data provenance
  before redistributing any derived tables.
- **`IMAX9D/cr-native-sandbox`:** its code is **MIT**, but it exists to run Supercell's proprietary binary and read
  client memory. Under our rules we may not use it, whatever its license.
- **`VanguardX101/IL_Replay`** (Hugging Face): **no license declared.** ClashAI issue #21 (2026-09-08, open) asks
  exactly this. **This affects us too:** our C56/S122 corpus derives from IL_Replay at the *same*
  revision `059d43a0…` that issue #21 asks about (`imitation/DESIGN.md` T9, `COORDINATOR.md:368-372`). Publishing derived datasets or weights from it is legally unclear. Raise this with Sam.

## 7. Open questions

1. **How much of the +908 trophies is the bot?** Logged W–L implies about +400 (§2.3). Only their per-match trophy
   log (merged 10-07) can settle it going forward. Re-check their `matches.jsonl` in about a week.
2. **The second account.** Will R1e climb from a low start? That's the closest analogue to our throwaway account and
   would be the most informative number they could publish. Nothing logged yet.
3. **Level and bot confounds:** opponent card levels and the bot-opponent share at 10–11k Trophy Road are unmeasured
   on their side and unknowable from the repo.
4. **Would their policy survive pixels?** Their only pixel-era number is 35% (n=37), with an older model. Our L2-v4
   oracle-vs-pixels comparison answers the analogous question for us. They have no such arm.
5. **Is their 1.13 s non-code latency game-inherent or emulator/adb-specific?** If game-inherent, our renderer-based
   latency budget (frame→tap p99 400 ms) is the small part. T2 should measure execution tick, not tap submission.
6. **Why did their search fail?** Their weak 12 s scorer, the policy's own exploitation, or a real limit of shallow
   search at this game's timescale? Their recommended "scorer check" was never run. If it is, re-read.
7. **IL_Replay licensing** (§6) for our own corpus.

## Appendix: sources

- [ClashAI repo @ 8d4053d](https://github.com/vegetableleaf/ClashAI/tree/8d4053dfea1be589c4b487154ed2da1b98d6aa9e):
  - `README.md`, `HANDOFF.md`, `GAUNTLET_LOG.md`, `CODEX_BRIEF.md`;
  - `scratchpad/gauntlet/L74/loss_review/report.md`, `scratchpad/gauntlet/L74/latency/budget_20261008.txt`;
  - `scratchpad/gauntlet/L73/trophies/img/`;
  - `pipeline/rl_royale.yaml`, `pipeline/model_gen.py`.
- [ClashAI issues](https://github.com/vegetableleaf/ClashAI/issues) (#21 IL_Replay license; #1–#22 otherwise
  technical). No releases or Discussions exist.
- [IMAX9D/cr-native-sandbox](https://github.com/IMAX9D/cr-native-sandbox) README (MIT; native `libg.so` runtime; MuMu
  ARM64 read-only observation).
- [RoyaleSim on PyPI](https://pypi.org/project/royalesim/) / [RoyaleGym/RoyaleSim](https://github.com/RoyaleGym/RoyaleSim) (MIT).
- **Web searches** (2026-10-08) for the author, the project name, trophy claims, Reddit, YouTube and Instagram found
  **no posts or videos by the author.** The only YouTube links in the repo are third-party strategy guides. The README
  mentions an Instagram, and issue #1 refers to an Instagram comment, but no handle is given and none was found.
