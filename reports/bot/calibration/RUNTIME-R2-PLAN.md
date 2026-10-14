# Plan: bot runtime r2 (calibrated engine + rebuilt native). Not executed; bots stay on r1.

**What r1 is.** On 127x03, `clasher-bot-runtime/r1` is a frozen root that `bot/players/runtime.py` loads via `CLASHER_BOT_RUNTIME`. It holds:
- its own copy of `src/clasher`, `gamedata.json` and the `engine-rs/` Python glue (`differential.py`, which builds the Rust config from the Python engine);
- a pinned native `native/clasher_core.abi3.so` (sha256 `44874fd6…`);
- pinned checkpoints `main02.pt` (v1, `d77005d5…`) and `R3a.pt` (`37509a43…`);
- untracked planner pieces (`student-source/`, loss_review modules, the human deck catalog).

**Checked 2026-10-14 (read-only):**
- All 437 engine files in r1 are byte-identical to bot/lead HEAD `a4a4a97bf`, the base of calibration batch 1: `src/clasher/**/*.py`, `gamedata.json`, `engine-rs/differential.py`, `engine-rs/src/*.rs`.
- The r1 native behaves exactly like a fresh build of HEAD `engine-rs`. Over 120 train fixtures (`bot/fidelity/rs_parity.py`), the first Python↔Rust mismatch tick is the same in 120/120, with full-length digest parity in 88/120.

So batch 1 applies to an r1 copy as a pure source diff, and the rebuilt native replaces 44874fd6 like for like.

## Steps (run as bot lead; nothing writes into r1)

1. **Copy.** `cp -a clasher-bot-runtime/r1 clasher-bot-runtime/r2` on 03. Mark r2 read-only after step 4.
2. **Apply the batch-1 diff** from the 127x05 worktree (`git diff a4a4a97bf -- src/clasher gamedata.json engine-rs`):
   - `gamedata.json`: spirit HP;
   - `src/clasher/formations.py` and `balance.py`: lane-2 mirror, Goblinstein, furnace start;
   - `src/clasher/cards/goblin_hut.py`;
   - `src/clasher/battle.py`: Miner snap and the Miner deploy-end path;
   - `src/clasher/pathfinding.py` and `src/clasher/cards/miner.py`: tunnel route and emergence;
   - `engine-rs/differential.py`: `mirror_x` 5/6/15, `skip_deploy_snap` for enemy-side deployers, `tunnel_path` export;
   - `engine-rs/src/{astar,c56,lib,spawn}.rs`: blocked A* cells, routed tunnel, GoblinHut wake gate.

   Check each file's md5 against the worktree after copying.
3. **Rebuild native** from `r2/engine-rs`. Use `/mpac/sdicks02/jobs/clasher/bot-calib-r1/build.sh` semantics with its own `CARGO_TARGET_DIR`, then copy into `r2/native/clasher_core.abi3.so`. Record its sha256 in `r2/native/build-tiers.json` (`provenance: calibration batch 1`).
4. **New pins.** `bot/players/runtime.py` hard-codes `PINS['native_sha256']` (r1). Add a per-runtime pin table, or a pin file in the runtime root, so r1 keeps its pin and r2 gets its own. Checkpoints are unchanged.
5. **Gates before any bot uses r2**, all on 03/04 with nice, results under `jobs/clasher/bot-r2-*`:
   - a. Fidelity harness on r2's Python (`bot.fidelity.run`, 577 fixtures). It must reproduce `c5d-minerend`: train no-tower ≤¼ 62.26, HP exact 71.98.
   - b. Python↔Rust parity (`bot.fidelity.rs_parity`, all 577) with r2's native.
     - The target is no new mismatch class beyond the pre-existing ones listed in BATCH1.md §6: IceGolemite, and the boundary-shot cases.
     - These are digest parity on the full-game replay. Planner rollouts are shorter, so they diverge less.
   - c. Planner smoke: `bot.eval.headline` K4S-b64 on 60 cases vs R3a with `CLASHER_BOT_RUNTIME=r2`. No crashes, decision latency within 10% of r1.
   - d. HEADLINE-v2 on RoyaleSim (primary) for K4S-b64 with planner model r2 vs r1, paired on the same cases. This is the actual question: does a more faithful planning model play better on the faithful engine? Report the paired difference with its CI. Switch only if it is not worse.
6. **Switch** (lead's call): point `CLASHER_BOT_RUNTIME` at r2 for new runs. Never mutate r1. ExIt labels generated on r1 stay r1-labelled.

## Caveats
- The Rust config is precomputed from the Python engine. The formation templates come from lane-1 deploys plus `mirror_x`, which keys on unit count, not native slot count. They agree for every corpus card.
- Rust decides lanes with `x < 9`, Python with the native path map. They are identical for tap tiles.
- The 7–14-slot formations, the MightyMiner ability tunnel, HealSpirit and GoblinDrill are unchanged and unverified.
- The calibrated engine is still ~63% within ¼ tile on non-tower units, against RoyaleSim's 79%. r2 improves the planner's model; it does not replace RoyaleSim as the trusted evaluator.

## Executed 2026-10-14 (calibration batch 2 agent)

- **r2 built** at `127x03:/mpac/sdicks02/repos/clasher-bot-runtime/r2`. r1 was not modified (mtimes Oct 10).
  - It is a copy of r1 plus the engine diff vs `a4a4a97bf`: 22 files (`src/clasher`, `gamedata.json`,
    `engine-rs/{differential.py, spawn_snapshot.py, test_stage4_spawners.py, src/*.rs}`).
  - Every file's r1 base md5 was checked equal to `a4a4a97bf` before copying, and its md5 after copying equal to the
    worktree. Manifest: `jobs/clasher/bot-calib2-r1/rtstage/final/manifest.tsv`, also embedded in
    `r2/native/build-tiers.json`.
- **The native recipe is not a plain `engine-rs` build.** r1's `44874fd6` is `engine-rs` plus the E1 stage
  (`reports/explore/e1/stage_native.py`, which adds `NativeScripts.rollout_e1`; K4S calls it), built with `cargo --locked
  --release --features extension-module,gil-release` and no RUSTFLAGS.
  - `jobs/clasher/bot-calib2-r1/build_e1.sh` reproduces `44874fd6` byte for byte from `r1/engine-rs`.
  - The same recipe on r2's sources gives **`c50cb06622e42c5ba9bd43854e9bdf10b615ce84a3d08309e5067d82e776ef27`**.
  - An E1 build behaves like the plain build: same first mismatch on 64/64 validation fixtures (checked on the `c10`
    candidate).
- **Pins:** `bot/players/runtime.py` `PIN_SETS = {r1: PINS (unchanged), r2: PINS with native c50cb066}`, selected by
  `CLASHER_BOT_RUNTIME_PINS` (default `r1`).
  - Use r2 with `CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r2 CLASHER_BOT_RUNTIME_PINS=r2`.
  - The checkpoints are r1's (v1 `d77005d5`, R3a `37509a43`).
- **Gates:**
  - a. Fidelity on r2's Python: identical sources to the batch-2 final (`c12-spawn`). Train no-tower ≤¼ 72.26,
    HP 80.51 (BATCH2.md).
  - b. Python↔Rust parity on the same sources (tree `c12r`): **574/577**. The 3 left are pre-existing HEAD classes.
  - c./d. HEADLINE in RoyaleSim and in ours, r2 vs r1: see `R2-AB.md`. No game errored. Planner CPU per 1,000 ticks in
    RoyaleSim is the same as r1's.
