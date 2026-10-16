# Level-aware search: worth a bounded pilot

2026-10-16. Code read on **127x05**, after `git fetch origin`: initial `origin/main` **8034a6713**; subsequent main **041196328** has no changes in the engine/search files cited below. Paths/lines refer to the bot repo at that revision. **No repo code changed; no commits. Runtime probes have NOT RUN.** The eight-worker admission request on 03 was cancelled before execution, following the user's instruction to finish the scope now. Scripts/source snapshot are in this job directory on 03 and 05. The raw process counts previously reported included YOLO loaders; they are not the updated admission script's count.

## Feasibility and limits

- **Python engine: yes, per card per player.** `src/clasher/player.py:35–59` owns `card_levels` (canonical names; unspecified cards default to 11); `battle.py:1152–1175` resolves each play without changing the shared loader, including spell levels. Actual troop HP/damage use those stats (`battle.py:2022`). Existing tests cover independent sides at 10/12 (`tests/test_player_card_levels.py:22–55`), not our whole 3–7 deck. Some non-11 spell overrides deliberately reject unreconciled data (`dynamic_spells.py:39–53,97–110`): validate the selected cards.
- **Python towers: per side, but low levels currently no.** `PlayerState.tower_level` controls all three towers for that side (`battle.py:250–285,314`); separate king/princess levels are not configurable. `tower_scaling.py:19` rejects everything outside 10–12. Extend/validate the existing tower curve for lower levels; setting player fields after construction does not recreate towers. **`bot/players/ours.py:34–47` does not expose levels**: its factory constructs level-11 players (`engine-cards/stage2_matches.py:63–73`). Add harness arguments. Runtime imports its own pinned Python copy (`bot/players/runtime.py:152`), so package a new experimental runtime rather than only editing repo `src`.
- **Native `clasher_core`: yes for arbitrary imported bodies/towers; partial for future plays.** It consumes numeric entity stats. A card already has `units[seat]` (`engine-cards/src/lib.rs:654–655,3867`), so different troop levels on opposite sides can be represented **without rebuilding Rust**. But spells and secondary payload tables are shared by key (`lib.rs:665–688,2939`; `spawn.rs:88`); there is no ordinary per-player level selector, and Mirror hardcodes level 12 (`lib.rs:3695–3703`). The exporter has a global `config(..., level=11)` (`engine-cards/differential.py:387`), not per-side/per-card arguments.
- **RoyaleSim 0.1.34: yes, already per card and per side, including towers.** Installed binary reset signature explicitly accepts `levels=[[...8 levels...],[...8 levels...]]`, parallel to each deck, and `tower_levels=[own,opp]`. Evidence: [royalesim-reset-api.txt](royalesim-reset-api.txt); identical binary SHA256 `97e03055…` on 03/08. This is API/code evidence, **not an executed match**. Clasher currently omits those reset arguments (`bot/players/royalesim_match.py:54–55`) and constructs global defaults 11 (`royalesim_vocab.py:67–71`). Thread the arguments through; use RoyaleSim as the first true-game engine. Its translator already uses actual HP/max HP fractions (`royalesim_translate.py:162,275`), while static policy columns/level labels remain 11 (`:125–132,237`).

## What search needs

**LevelRoot** copies public templates, scales seven stat fields plus shield/bomb damage, then sets HP = observed fraction × scaled max HP (`bot/live/levels.py:24–25,53–63,78–90`). Defaults/overrides are by **body token**, not card (`:38–41`; Archers needs the `Archer` body). It neither changes rollout config nor policy packets (`:126`). All-11 bypasses to the old root (`:128–132`).

Correct two things even for a root-only trial: use exact level stats instead of rescaling already-truncated level-11 values; use **tower-specific curves**, not card multipliers (`src/clasher/tower_scaling.py:1–5,21–37`). Attach the hook to the actual K4L search: the generic LivePlayer installs it, but `make_live_lopp` subsequently replaces that search object (`bot/live/player.py:263–265`; `bot/search/lopp_fast.py:735–737`). Prefer observed HP fractions; the live absolute-HP conversion still divides by a level-11 template (`bot/live/translate.py:343–370`).

**Rollouts:** `NativeScripts.rollout_e1` has no levels argument; it clones/runs the supplied root/config (`engine-cards/src/scripts.rs:616–629`). Build level-specific config templates once per match/estimate, not per rollout. A promising **no-Rust pilot** is seat-specific troop/carrier templates plus qualified spell/payload keys: Mirror already exports such keys (`engine-cards/mirror_snapshot.py:4–5,45–58`), and projectile impacts look up their stored spell key. This may cover Fireball/Arrows; **unverified until the impact probe runs**. A general implementation should add per-player level selection, qualify every child/death/production/chain/spell payload, and remove Mirror's fixed-12 assumption. Preserve those keys through `fc` cuts and pool config caches (`bot/search/lopp_fast.py:88–107,174–189,391–414`). Native scripted spell/proposal scores still use level-11 metadata (`engine-cards/src/c56_scripts.rs:54,88–129`); tower leaf fractions use fixed metadata maxima (`leaf.rs:69–75`). Audit these too, retaining the game's absolute-HP tiebreak semantics.

**Policies:** the learned rollout opponent consumes cost × HP/max HP and tower fractions, with **no level or damage input** (`bot/search/lopp_feat.py:19–58`; native fractions: `engine-cards/src/scripts.rs:181–203,239`). Scaling HP and max HP together is consistent, but identical fractions hide unequal strength; changed combat trajectories are out of its training distribution. R3a/it5s2 inputs also contain damage and explicit level fields (`imitation/model/features.py:11,97–110`). For the first physics A/B, freeze their weights, level-11 static columns/labels and candidate generation in both arms, retain actual HP fractions, and report this limitation. Fully level-aware learned policies require level/damage features plus mixed-level training; **not required to test better search physics**.

## Build estimate (judgment, includes focused checks)

| Work | Hard logic — Opus | Plumbing/fixtures — Sol |
|---|---:|---:|
| Narrow-deck pilot: RoyaleSim truth, corrected roots, per-seat templates/projectile-key prototype, K4L hook/cache handling | 150–300 LOC, 4–8 h | 250–450 LOC, 6–10 h |
| General native selector, all secondary effects/Mirror, scripted metadata and tower evaluator audit — additional | 200–400 LOC, 8–16 h | 400–700 LOC, 10–20 h |
| Explicitly level-conditioned learned policies — optional, additional | 100–200 LOC, 4–8 h | 300–600 LOC, 8–16 h, plus data/training |

Pilot: **roughly 1–2 engineer-days**, conditional on the no-Rust spell probe; otherwise budget the native extension. Start with chosen decks, not full-pool mechanics. Require all-11 parity, same card/different sides, spell impact damage, tower stats, and snapshot/cut/pool preservation.

## Honest A/B and cost

Use **one immutable true-game level profile for both arms**, initially RoyaleSim 16.402 with the matching `live16402b-r2` planning runtime. Record all eight actual own levels (the five supplied are insufficient for a complete deck), split Archers 6/7 into declared scenarios, and use actual tower levels. Opponent truth contains mixed 6/7/8 levels, assigned independently of the planner; this distribution is a scenario assumption, not a measured trophy-band distribution.

**A:** K4L roots/config assume 11. **B:** exact own levels and an explicitly fixed opponent estimate (e.g. 7), corrected root towers/bodies, plus rollout templates if validated. An existing-LevelRoot-only B is a cheap diagnostic; it must be labelled **root-only**, since its candidate deployment still spawns at 11. Do not interpret a null root-only result as rejecting level-aware search. A separate king-level estimator may use the number shown at match start; never pass opponent true card levels, hidden deck/order, or future observations into either search.

Pair seeds, decks/opening order, seat, opponent controller, true levels, perception and RNG streams. Use a fresh bank, equal seats, fixed opponent mix, sampled-opponent common random numbers, and the same candidate/work budget. Start with the deterministic K4L twin, one process/thread per game; then check the 200 ms live variant for changed default share/latency. Keep fallback/proposal policy inputs identical between arms. Report paired win/draw score, tower damage, decision changes and defensive/spell threshold errors; cluster seat swaps under their seed if using both.

**Pilot: 100 independent pairs = 200 games.** With paired-score variance about 0.2–0.4, 95% uncertainty is approximately **±9–12 percentage points**: detects large gains, cannot settle a 3–5 pp gain. Around **650–1,300 pairs** gives ~80% power for 5 pp under that variance assumption; estimate variance from pilot and preregister the confirmation size. Do not pick the winning level estimator on the confirmation bank.

Planning allowance **0.03–0.08 CPU-hours/game**, not newly measured: existing K4L costs ~0.415 CPU s/decision (`reports/bot/learned-opponent/RESULTS.md:66–79`), multiplied by roughly 200–600 decisions plus game-loop overhead. Pilot **6–16 CPU-hours**; an 800-pair confirmation **48–128 CPU-hours** (~12–32 h at four single-thread workers). Measure ten complete games before reserving the larger run. Extra root-only/estimator arms add games; the faster process pool reduces wall time, not CPU accounting.

## Mechanics effect size — table arithmetic, not probe results

The serialized Common ladder is 1.21/1.33/1.46/1.60/1.76/1.93/2.56 at levels 3/4/5/6/7/8/11 (`engine-cards/py/gamedata.json:83751`; exact truncation: `src/clasher/stat_scaling.py:28–30,51–61`). Musketeer bases are 282 HP/85 damage (`gamedata.json:1189,1201`); Fireball base damage is 269 (`:9329`). Thus:

- **Musketeer L4: 375 HP. Enemy Fireball L6/7/8: 430/473/519 damage: lethal in all 3 level cases. Uniform L11: 688 damage vs 721 HP: lethal in 0/3.** This is conditional on a full-health target being hit; it is not encounter frequency or win-rate uplift. At equal low levels Fireball also fails to kill: relative levels matter.
- Musketeer L4 hits a tower for **113 vs 217** at L11 (**48% less**). Our L3–7 ordinary card HP/damage are approximately **47–69%** of the L11 assumption, before integer rounding.
- Princess tower L6: **2,030 HP, 72 damage/hit**, versus L11 **3,052 HP, 109/hit** (tower curve in `tower_scaling.py:21–37`). A full L4 Musketeer takes **6** such L6 tower hits, versus **7** in the uniform-L11 model. Tower HP/damage do not follow the Common card ladder.

**Recommendation: yes, fund the narrow 1–2 day pilot.** The mechanics discrepancy is large and directly testable; the strength gain is unknown. Prioritize true mixed-level games and rollout spawns. Do not spend on retraining or deploy root-only scaling as a proven improvement before the paired test.

## Deferred probes (NOT RUN)

`probe.py main` checks Python mixed deployment, spell resolution and level tables; `rsim` checks mixed per-card levels and tower levels through an actual reset/deployment; `runtime` checks native per-seat troop payloads, qualified Fireball impact lookup, learned-feature fraction invariance and 160-tick rollout CPU cost. These are exploratory scripts, not validated tests. Runtime uses the authorized r1/r1-total pins; the proposed A/B should use one matching live16402b-r2 setup in both arms.

On **127x03**, exact follow-up using the **current repo lease scripts**, **N=4**, with a 30-minute overall timeout (therefore also bounds admission):

```bash
ssh 127x03 'timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 bash /mpac/sdicks02/jobs/clasher/bot-levels/run_all.sh'
```

`run_all.sh` sets `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, disables CUDA, sets BLAS/OpenMP/Rayon to one thread, and selects `CLASHER_BOT_RUNTIME=.../r1`, `CLASHER_BOT_RUNTIME_PINS=r1-total`, `CLASHER_DELAY_NATIVE_DIR=.../native-total-r1`. It runs the three modes serially and writes `main-probe.txt`, `rsim-probe.txt`, `runtime-probe.txt` here. No queued or running probe is intentionally left behind by this scope.
