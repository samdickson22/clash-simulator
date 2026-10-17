# Hasty-CR deep dive, 2026-10-17

- **Repo:** https://github.com/hastylmao/Hasty-CR, MIT.
- **Clone:** `/mpac/sdicks02/tmp/hastycr-research/repo`, read only; none of its code was run.
- **Commit:** HEAD `ac4ef71194167e97f34550fc91c026b6d707a0cd`, dated 2026-10-10 11:04 +0530, "Live memory-reader bot, navigation port, self-play training, lane guard".
- **Size:** 1.7 GB, mostly about 1.2 GB of VOD detection tracks plus a 93 MB `demo.mp4`.

**Earlier review.** We reviewed this repo before, at `913608b` (2026-08-30), in `clasher: reports/external_review_20260928/hasty-cr.md`. That report covers their old engine against native data, their PPO recipe and their evaluation flaws, and it still holds. This note covers what changed since then (the 27 commits up to `ac4ef71`) and maps it to our live problems.

Paths below are relative to the Hasty-CR root unless they start with `clasher:`. Line numbers refer to `ac4ef71`.

---

## Summary

1. **Their bot is not strong live.** The only committed ladder record is from their hand-written rule bot: **W14 L118 D72** (`docs/RUN_JOURNAL.md:1277`), with trophies stuck at 5501 (`:697`).
   - No RL checkpoint had played a live match as of 08-26 (`docs/RL_SPRINT4_DECISIONS.md:329-330`). The README says "No trained policy has beaten a human" (`README.md:390`).
   - Their newest live bot (imitation model plus memory reader) was cleared for ladder on 10-10 (`scripts/gamestate/live_play.py:16`). No result from it is committed.
2. **They gave up on their own simulator.** Re-driving 2,000 IL_Replay matches, their engine agrees on the winner 49.5% of the time against 62.6% for RoyaleSim, and on exact crowns 24.2% against 49.0% (`docs/PROGRESS_2026-10-09.md:77-83`). RoyaleSim now generates their training data (`:90-94`).
3. **Their pivot was pro imitation, and it worked better than PPO did.**
   - The policy is an entity-token transformer trained on IL_Replay re-driven through RoyaleSim.
   - It picks the pro's card 66.8% of the time and the exact tile 31.7% on held-out Hog 2.6 decisions.
   - Against a reactive simulated opponent playing the real opponents' decks, it wins 49.7% [44.0, 55.3]. The real players won 48.7% of those same matches (`PROGRESS:365-374`).
4. **The finding most relevant to us is about lag.**
   - A tap lands **25-27 ticks (about 1.3 s)** after the decision, measured live (`live_play.py:59-62`).
   - In simulation that lag costs about 12 pp (`PROGRESS:199-211`).
   - Deciding on a board rebuilt from public information and run forward by the lag wins back **+15 to +16 pp**: 32.0% → 47.0%, and 24.3% → 40.3% against a stronger reference (`PROGRESS:288-294, 339-348`).
   - It **only worked after they stopped dropping evolved and hero units** from the rebuild. Before that fix the same method scored 23.0%, worse than no compensation (`PROGRESS:275-294`).
   - Our own forward-projection test came out null (+0.00 pp), but only against saturated scripted opponents, where we win 88-95% (`clasher: reports/explore/delay-fixes/interpretation.md`). Their result says the question deserves a re-test against a strong opponent.
5. **Reuse:**
   - **Code:** MIT, so it can be copied if we keep the notice.
   - **Weights:** no policy, detector or side-classifier weights are shipped (`.gitignore:19, 33, 44, 89`).
   - **Data:** we already use IL_Replay and know RoyaleSim (`clasher: reports/clashai_deepdive_20261008.md:136-169, 397-403`).
   - **Memory reader:** their live bot reads game memory as root. That conflicts with our fair-information and no-evasion rules, so it is not a candidate for live decisions.

---

## (a) Results: what is measured and what is only claimed

### Live

| Bot | Matches | Record | Source |
|---|---|---|---|
| Rule bot, all-time ladder at that point | 204 | **W14 L118 D72** (about 7% wins) | `docs/RUN_JOURNAL.md:1277` |
| Rule bot, earlier snapshot | 136 | 14W 76L 46D; trophies "stuck at 5501", tower levels matched at 12 | `RUN_JOURNAL.md:685-699` |
| Rule bot after switching to their YOLO detector | about 95 | W7 L35 D53 | `docs/OVERNIGHT_STATUS.md:83` |
| Rule bot, corrected tower reader | 41 | W6 L20 D15; "conceded 98%" | `OVERNIGHT_STATUS.md:49-51` |
| PPO policy | 0 ladder matches | "No RL checkpoint has played a live match yet" (08-26) | `docs/RL_SPRINT4_DECISIONS.md:329-330` |
| Imitation model plus memory reader (`rs_big_hog`) | unknown | Ladder cleared 10-10, no record committed (`reports/live_play/` absent) | `scripts/gamestate/live_play.py:13-16` |

- **Trophies.** They never recover from 5501. The only other trophy mention is "`clone_pilot`, the one that pushes trophies" (`docs/STATE_2026-08-31.md:15`), with no number attached.
- **What "live" includes.** The README's "plays live" covers five friendly matches against a person, reported as behaviour only in our earlier review. "No trained policy has beaten a human" (`README.md:389-390`).

### Simulator win rates

All of these are against opponents in their own engine (or in RoyaleSim, where marked).

| Policy | vs rule engine | vs "meta decks" | n per cell | Source |
|---|---|---|---|---|
| Behaviour clone | 18.3% | 78.3% | 60 | `README.md:380` |
| PPO, 6.1M steps (README headline) | 93.3% | 86.7% | 60 | `README.md:381-384` |
| `physA_best`, first run on the speed-corrected engine | 92.0% [87.4, 95.0] | 75.0% [68.6, 80.5] | 200 | `checkpoints/physA_best.json` |
| Hog mirror specialist (trained before the speed fix) | 94% | 91% (99.5% mirror) | 200 | `checkpoints/hogmirror/hogmirror_sel_301056.json` |
| Imitation `bc` + 3 s search in the same engine | 87.5% | — | 200 | `PROGRESS:141-151` |
| Imitation `rs_big_hog`, RoyaleSim, reactive opponent | 49.7% | (real players: 48.7%) | 300 | `PROGRESS:365-374` |

Caveats from our earlier review still apply:

- The "rule engine" is the behaviour-cloning teacher and half the PPO training diet.
- The "meta decks" are the training pool.
- Every game is one fixed seat with one fixed deck.

They also found that **simulator win rate and placement quality come apart**. `physA_best` scores 92% but puts Ice Golem and Ice Spirit behind its own King, 13 tiles from where the pro puts them (`docs/STATE_2026-08-31.md:9-26`).

---

## (b) Simulator

### Fidelity approach
- Integer millitiles, 50 ms ticks and a fixed seven-phase tick (`README.md:95, 325-341`).
- Card stats decoded from the client's tables, which they pull from the APK. Those tables are not shipped. They overlay RoyaleAPI tables (`data/royaleapi/*`).
- Tested by:
  - "check" claims you can verify against a real match (`sim/check.py`);
  - cross-checks against Jason-XII's simulator (`tools/diff_scenarios.py`);
  - VOD tracking of YouTube and Twitch matches with a per-match affine fit anchored on the towers. Fits with residual over 0.75 tiles are dropped; typical residual is 0.36 tiles (`docs/VOD_CALIBRATION.md:31-46`).

### Coverage
- **Their claim:** `sim.coverage` reports "116 of 116" families, which they say "is not a fidelity claim" (`docs/SIM_MECHANICS.md:52-54`).
- **IL_Replay:** 83.5% of matches have all 16 cards in their engine (`PROGRESS:36-38`).
- **Fixes since our last review:**
  - **Movement speed** was 20% slow for every unit. Now 1 `Speed` unit = 1 millitile per 50 ms tick, so Medium is 1.2 tiles/s and the Hog 2.4 tiles/s (`docs/SPEED_SCALE_CORRECTION.md:4-12, 60-70`).
  - **Pathing:** troops walked sideways for 3 s before turning (`STATE_2026-08-31.md:81-88`).
  - **Elixir Collector** income was never read (`PROGRESS:25-29`).
  - **Lightning** radius was 0 (`PROGRESS:50-56`).
  - **Start elixir:** 6 measured from replays (`PROGRESS:30-32`).
  - **Our engine already matches** on the points we checked: speed is read as logic units per tick (`clasher: src/clasher/gamedata_normalization.py:15-31`), and default starting elixir is 6.0 (`clasher: src/clasher/balance.py:23`).

### Tests
- The badge says 1,635 tests (`README.md:8`): 109 files and 910 `def test_` functions, many of them parametrised.
- Their own last full run was **53 failed, 1,640 passed** (`PROGRESS:62-69`).
- Files are named for the failure they prevent (`README.md:405`).

### The three mechanics you asked about

- **Building pull.**
  - Pull is gated by sight range, so a Hog cannot be pulled across the map by a Cannon 17 tiles away. Crown towers are lane-committed (`sim/engine.py:2479-2520`).
  - They have **no measured pull map**: "this remains a primary RL uncertainty" (`reports/MECHANICS_TRUTH_TABLE.md:166-175`).
  - Our engine is sight-gated with native fallback-crown logic (earlier review §3). Nothing here suggests a bug in ours.
- **Hog body-block.**
  - Their one real measurement: unblocked Hog **7 tower hits**, Hog blocked by Skeletons **2 hits** (`sim/engine.py:47-63`).
  - Their engine still cannot reproduce how sharply the block depends on timing. It gives 3-4 hits across block delays, where Jason's engine gives 6→2 (`sim/engine.py:84-101`). Four attempts at a fix failed (`:65-121`).
  - Charging units still deadlock (`README.md:420`).
  - Our engine gave 7 unblocked and 2 blocked in the earlier review (§2.4 row 8). That matches their single real clip.
  - Retargeting is a placeholder: "re-evaluate only when the target dies or leaves sight, plus a 500 ms sweep" (`sim/engine.py:41-44`).
- **Deploy and cycle timing.**
  - FIFO hand reconstruction is confirmed on 1,206 replay rows (`PROGRESS:39-41`).
  - RoyaleSim models the client command delay as 21-22 ticks; live they measure **25-27 ticks** from tap decision to unit on board (`PROGRESS:195-197`; `live_play.py:59-62`).
  - Our HP1 design uses 27 ticks (1.35 s), which agrees.

**Conclusion on (b):** their engine is **less** faithful than ours, by their own measure (it loses to RoyaleSim), and the earlier review found five divergences from native. What carries over from their simulator work is the measurement method:

- the forward-projection-by-delay result (below);
- the paired re-drive of replays as a fidelity score (winner and exact-crown agreement);
- the "body-block delay sweep" shape test.

---

## (c) RL

- **PPO stack:**
  - **Observation:** 8 spatial planes on 32×18 (ally and enemy counts, HP/1000, air, buildings) plus 47 scalars (`sim/env.py:73-81`).
  - **No unit identity:** "could not tell a Skeleton from a Golem", which is why they later moved to tokens (`sim/model_tokens.py:1-13`).
  - **Actions:** 1 + 4×576 placements + 16 ability slots, masked, one decision every 500 ms (`sim/env.py:59-66`).
  - **Network:** 3 conv layers then a flatten into 512 units, 20.2M parameters, 94% of them in that flatten layer (`sim/train_ppo.py:104-117`).
  - **Reward:** ±10 × tower fraction per step, plus crowns and the result (`sim/env.py:234-235, 527-539`).
  - **PPO settings:**
    - learning rate 5e-5, entropy 0.03, target-KL 0.02;
    - 300k-step critic warm-up with the policy frozen;
    - opponents: 204 meta decks plus a league of 4 past selves, with 40-50% scripted episodes (`reports/FIRST_RL_PILOT.md:15-27`; `README.md:179-197`).
  - **Compute:** one RTX 4070 Ti SUPER, about 2 h per 6M steps.
- **How it "played 2.6 well":** it did so only in their own engine, and the placements collapsed (above).
- **The imitation path that replaced it:**
  - **Model:** entity-token transformer with d=256, 6 layers, 8 heads. Heads: wait/play gate, card pointer, a tile head conditioned on the chosen card, and a value head on 10 s outcome and win (`sim/model_tokens.py:24-46`; `PROGRESS:365-374`).
  - **Data:** 13.7M rows from 252k IL_Replay matches (`docs/MORNING_2026-10-10.md:14-19`).
- **Lessons from the imitation work:**
  - **Wait calibration matters.** A mismatched `wait_keep` made the agents overplay, at 47 plays per match against 35-40 for pros (`PROGRESS:236-245`).
  - **Outcome weighting did not help:** 37.0% vs 40.3% (`PROGRESS:189-191`).
  - **Spells are the weakest decisions:** Fireball card top-1 is 45.9%. Defensive tiles miss by about 2 tiles because pros react to exact enemy positions (`PROGRESS:249-266`).
- **Search:**
  - Top-2 cards × 3 tiles, 3 s rollouts in a RoyaleSim save/load copy: +27 pp on the true state (`PROGRESS:170-173`, 64.3%).
  - Only +5 pp, within noise, on a board rebuilt from public information (`PROGRESS:291-295`).
  - Search that ignores the delay works against the look-ahead (`PROGRESS:302-305`).
- **Newest step:** PPO self-play in RoyaleSim starting from the imitation model, with a KL brake toward it and the live delay and look-ahead included (`tools/rs_selfplay.py:1-31`). **No result is committed.**

---

## (d) Live bridge

They have had two generations of live bridge.

### Vision generation (August, rule bot)
- **Detector:** YOLOv8s, 201 classes, trained on KataCR's CR-Detection-Dataset (5,551 train / 1,388 val). P 0.949, R 0.926, mAP50 0.959 on that dataset's own validation split (`RUN_JOURNAL.md:1065-1068`). Hog AP is 0.973 (`scripts/brain/vision.py:7`).
- **Team:** a separate small side classifier trained on about 93k crops gets 94% (`OVERNIGHT_STATUS.md:72-75`).
  - It learns orientation: ally sprites face up the screen (`scripts/train_side_classifier.py:1-27`).
  - A blue-vs-red colour rule gets 52.8% in our half (same file).
  - Below 0.55 confidence they fall back to which half the unit stands in (`vision.py:320-326`).
- **Spells:** all of them, **including `goblin-barrel` and `the-log`**, are on a "not a unit" list and dropped (`vision.py:54-63`). They never had a landing-timed Zap or Log.
- **Evolved forms** are folded into the base card by stripping `-evolution` (`vision.py:118`). The KataCR dataset has no hero classes.
- **HP is not read.** Every unit carries its card's full HP (`README.md:421`).
- **Capture:** `adb screencap`, 417 ms at full resolution. Later they moved to an H.264 `screenrecord` stream with PyAV: 32 ms, against 169 ms before (commit `7e8e222`).

### Memory generation (October, imitation model)
- **Reader:** a read-only `/proc/<pid>/mem` reader running as root on MuMu, pinned to client build 160402012 (`scripts/gamestate/memread.py:1-26`; `native/hcr_reader.c:1-27`).
  - The offsets come from vegetableleaf's **unlicensed** ClashAI findings (`memread.py:17-24`).
  - It streams a JSON frame every 25 ms: tick, own elixir, hand and cycle, and for every unit its side, x, y, card, level, HP and character name.
  - The character name (e.g. `Knight_EV1`) separates evolved and hero forms.
  - Opponent hand and elixir are deliberately not read.
- **Decision** (`live_play.py:519-586`):
  1. Rebuild the board in RoyaleSim and run it **26 ticks ahead**.
  2. Sample the gate.
  3. Take the best tile that RoyaleSim's `check_deploy` accepts.
  4. Tap through one persistent `adb shell` (round trip 39 ms, about 50 ms per tap; `:110-115`).
- **Plays already sent** but not yet on the board block their hand slot and are subtracted from spendable elixir, so a second defensive card can follow at once (`:511-518`).
- **Hand-written additions, not measured in the evaluator:**
  - a 9.5-elixir "don't sit capped" rule (`:24-25, 540-543`);
  - a **Cannon wrong-lane guard**: live logs showed 24% of defensive plays within 3 s of an opponent play went to the other lane (`:68-94`).
- **Per-play diagnostics** (`:455-481`): ticks from tap to board, and where the unit landed against where it was aimed.
  - This is how they found a **screen-mirroring bug**: the bot "defended every left push in the right lane" (`:97-107`).
- **Opponent-play detection** removes shots, spawns and projectiles that carry the card ID. They had logged "11 Cannon plays that were cannonballs, 10 Minions that were spit" (`:423-435, 490-493`).

---

## (e) Licence and reuse

| Item | Shipped? | Reuse for us |
|---|---|---|
| Code (engine, trainer, live loop, studio, VOD tools) | Yes, MIT (`LICENSE:1-3`) | Copy is allowed if we keep the notice. Worth taking as **patterns**: persistent adb tap shell, newest-frame reader thread, per-play landed-vs-aimed and lag logging, opponent-play de-duplication. Do not import their engine semantics (they diverge from native). |
| Policy checkpoint (PPO 20.2M) | **No.** `*.pt` and `checkpoints/` are gitignored (`.gitignore:19, 33, 44`). `checkpoints/*.json` holds only metadata. | Nothing to load. For size: about 81 MB of fp32 weights; their inventory lists `clone_pilot.pt` at 231 MB with optimizer state (`reports/rl_sprint3/CHECKPOINT_INVENTORY.csv:4`). |
| Imitation models (`runs/tokens/rs_big_hog` etc.) | **No** (`.gitignore:89`) | — |
| Detector and side-classifier weights | **No** | Their data is KataCR's dataset, which we already use. Ultralytics is AGPL. |
| Card data | `data/royaleapi/*.json` | These are RoyaleAPI tables, not theirs to license, and we have native data. `scripts/gamestate/card_map.json` (native card ID → name) is a factual table, but it rests partly on unlicensed ClashAI offsets. Low value to us. |
| Tests | 109 files | Tied to their API. Reuse the **scenarios** as test ideas, especially post-tower-loss lanes and body-block delay sweeps. |
| Calibration tools | `tools/vod/*`, `tools/calibration/*`, `tools/redrive_*` | Reusable ideas: tower-anchored per-match affine fit, residual gate, paired replay re-drive scored on winner and exact crowns. |
| VOD tracks and plays (`data/vod/`, 13,566 plays) | Yes | These are derived from third-party YouTube and Twitch videos, mostly mixed decks. Licensing is unclear and the value is low; skip. |
| Memory reader | Yes (MIT code, unlicensed offsets) | **Not for live decisions** under our fair-information and no-evasion rules. Using memory as labels only is parked (owner declined RE/root). |

---

## (f) Comparison with our stack

### What they do better, or measured and we haven't
1. **Lag-aware decisions measured against a strong opponent.** They got +15-16 pp from a public rebuild run forward by the delay (`PROGRESS:288-294, 339-348`), and the gain peaks exactly at the delay (`:350-359`). Our equivalent test was null, but only against scripted opponents we beat 88-95% of the time.
2. **Per-play live accounting** of tap→board ticks and landed-vs-aimed offset in tiles (`live_play.py:455-481`). It turned a "bad defence" symptom into a one-line mirroring fix.
3. **Simulator fidelity scored on real replays.** They report paired winner and crown agreement over 2,000 matches (`PROGRESS:77-83`), not only unit fixtures.
4. **Form-aware state handling.** Missing evolved and hero forms cost them 24 pp of look-ahead value (`PROGRESS:275-294`). Their newer reader keys on character names.
5. **Honest negative results**, written down: outcome weighting, the shadow re-drive, search on a rebuilt board. Several of these save us experiments.

### What we do better
1. **Simulator:** native-anchored geometry, shields, Log pushback, Tesla hide, gait and fallback-crown logic (earlier review §2-3). Theirs loses to RoyaleSim on replay agreement.
2. **A working policy plus search stack:** full-pool search plus the rl5-v10 fast tier, evaluated at L16 on paired fresh banks with CIs. Their PPO never played live, and their imitation bot has no committed live result.
3. **A live loop on the official client from public pixels only**: YOLO detector, translator, owner model, Mac-side capture with timing gates. Theirs uses root memory reads for state, which we exclude.
4. **Evaluation discipline:** strong-opponent rows, paired seats, held-out banks, and no self-graded seed reuse.
5. **A deck-agnostic, full-pool bot.** They are locked to one classic Hog 2.6 list with Musketeer, Ice Golem, Ice Spirit and Log, not our Archers, Valkyrie, Electro Spirit and Zap.

---

## (g) Top 5 things to adopt or test, ranked by expected live impact

1. **Re-test deciding on a lag-projected board against a strong opponent, with every evolved and hero form kept.**
   - **What:** at decision time, take the translator's public board plus our own pending plays, run the native engine forward 26-27 ticks, and decide on that.
   - **Arms:** (current-state, projected) × (strong row: rl5 / K4C / human-v2 opponent, plus the existing scripted rows).
   - **Rebuild audit first:** count units lost, especially evolved and hero forms and spawned children. That bug turned their +15 pp into −9 pp (`PROGRESS:275-294`).
   - **Why first:** it is the only lever in their repo with a large measured effect (+15-16 pp, robust to opponent strength). It goes straight at two of our symptoms: late centre Cannon against a 2.4 tiles/s Hog, which moves about 3 tiles during our lag, and plays landing where a unit used to be.
   - **Cost:** low. We already have `clasher: engine-rs/src/delay_commands.rs` and the delay-fixes harness.
2. **Log every live play: tap→board ticks, and landed tile against aimed tile and against the nearest-threat lane.**
   - **Precedent:** their `awaiting` matcher (`live_play.py:455-481`) and their 24% wrong-lane statistic (`:68-72`).
   - **Why:** it separates the three possible causes of our "plays into empty spots" (35-45%):
     - a mapping or mirroring error (their bug, `:97-107`);
     - lag, where the target moved;
     - a bad policy choice.
   - Each cause needs a different fix. Diagnostic only, so no hand-written rule (per our no-hard-coded-cases rule).
3. **Keep spells in flight as board objects, with a predicted landing tick, through the translator and into the policy and search state. Goblin Barrel first.**
   - **Their evidence:**
     - Their rebuild's biggest remaining loss was "spells and projectiles in flight, attack timers, deploy timers" (`PROGRESS:183-188`).
     - Their vision dropped `goblin-barrel` and `the-log` outright (`vision.py:54-63`). They never solved this, so it is open ground, not a copy.
   - **Our symptom:** the detector already sees the barrel but the translator drops it, so a landing-timed Zap is impossible.
   - **Fix and test:** give the barrel a learned flight-time prior from our own replays, and an A/B on Zap-on-Barrel response rate and outcome.
4. **Audit evolved and hero form mapping from detector to translator to card, then fix it with data.**
   - **Their evidence:** dropping these forms cost 24 pp in their rebuild (`PROGRESS:288-294`).
   - **Our symptom:** an enemy evolved or hero Wizard is read as Knight.
   - **Steps:**
     - per-class confusion on raw live slices for every evolved and hero form in the current ladder pool;
     - label evolved and hero Wizard (and any other confused forms) through the Sol labelling path;
     - map form → base card by learned class, not by name rules.
   - **Own units:** apply the same audit to our own Electro Spirit and Hog. Since we know our own taps (card, tile, time), seed their tracks from accepted taps. That is fair information, and it is the job their own-play matcher does.
5. **Calibrate the human or imitation policy's hold rate and in-flight elixir accounting against pro behaviour, rather than adding reserve rules.**
   - **Their evidence:**
     - A wait-rate miscalibration made agents overplay, at 47 against 35-40 plays per match (`PROGRESS:236-245`).
     - Their rule bot's stacked elixir gates created a dead band where it froze for 13-23 s (`OVERNIGHT_STATUS.md:90-103`). That is a warning against fixing "spend to 0 before enemy Hog or Barrel" with another threshold.
   - **Test:** on fresh banks, compare our elixir-at-enemy-Hog-crossing distribution and plays per match with the IL_Replay pro distribution for Hog cycle decks. Then tune the learned hold (HP1 or banking) to match.
   - **Why last:** most direct for the elixir symptoms (0 elixir before Hog or Barrel; Cannon unaffordable on 167 of 210 crossings), but our banking work is already under way. This adds a pro-anchored target, not a new mechanism.

**Not recommended:**
- adopting their engine, PPO network or reward;
- their memory reader;
- their VOD data;
- treating their 93% or 49.7% simulator numbers as evidence of live strength.
