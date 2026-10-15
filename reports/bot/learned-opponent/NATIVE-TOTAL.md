# Total card-config lookups in the pinned native (deliverable 4, exploration)

Status as of 2026-10-15T11:24:52Z (`date -u`). The patched native is built and passes parity. **No pin or env is
switched.** The runtime proposal is at the end. The patch is in `NATIVE-TOTAL.diff` beside this file. Tools and
result summaries are in `native-total-tools/`.

**Verdict**
- The pinned native `44874fd6` was rebuilt **byte for byte** from an identified source tree.
- The patched build is `681b5f2c…`. It is bit-identical to the pinned native on every valid input tested:
  - 577 fixtures, 1.01 M ticks;
  - 300 real search roots × {full, cut} config;
  - every value the pinned native returns on the panic regression roots.
- It never panics where the pinned native panics.

## 1. Source provenance

| question | evidence | answer |
|---|---|---|
| What source is `44874fd6` built from? | r1's `reports/explore/s1/receipts/runtime-pin.json` → `native_source` lists 77 file sha256s. `native_sha256` = `44874fd6…`. | That 77-file manifest. |
| Is `r1/engine-rs` that source? | Checked against `native_source`: `src/e1_commands.rs` and `e1-source-manifest.json` are **missing**. `src/scripts.rs` is `df849040…`, but the manifest has `127c6980…`. The r1 copy has no `rollout_e1`: its diff is exactly the E1 overlay (`mod e1_commands` + the `rollout_e1` method). | **No.** It is the pre-E1 base tree. |
| Where is the exact tree? | 127x03 `/mpac/sdicks02/jobs/clasher/e1-20261009-r1/native-source-v2`. All 77 hashes match and there are no extra files (`native-total-tools/check_src.py`). It is the base tree plus `reports/explore/e1/stage_native.py`. Identical copies sit in the `native-source/` of k-anytime-20261010-r1, k2-20261010-r1, k-v2-20261010-r1, t1-20261010-r1, x4s-20261011 and x4s2-20261011. Each of those jobs holds `native/clasher_core.abi3.so` = `44874fd6…`. | Found. |
| Build flags? | `k-anytime-20261010-r1/native/target/release/.fingerprint/clasher_core-*/lib-clasher_core.json` has `features ["extension-module", "gil-release"]` and `rustflags []`. PROGRESS-K (k-anytime) records rustc 1.97.1. | **`gil-release` is ON** in the pinned native. |
| Reproducible? | I copied the tree to `127x03:/mpac/sdicks02/jobs/clasher/bot-native-total/repro/src-orig` and built it with `build.sh` (§3), unpatched. sha256 = `44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2`, and `cmp` against `r1/native/clasher_core.abi3.so` says byte-identical. | **Yes, bit-exact.** |
| `source_manifest_sha256` `84c8fe33…` (build-tiers.json) | I tried five obvious serializations of the `native_source` dict and none hashes to it. `e1-source-manifest.json` hashes to `dc4c137b…`. | Not reproduced. Not needed, because the bytes reproduce. |

The patch is applied to that exact tree. It is not applied to `r1/engine-rs` or to any newer tree.

## 2. Patch sites (line numbers are in the pinned source)

When an entry is missing, the patch skips the effect. For a valid state, each site takes the same branch as before. Only
the branch that used to panic changes. The "pinned panic seen" column counts panics in the scrub totality run (§4c),
where each site panicked at the exact `file:line` shown.

| # | site | reached from | before | missing entry now → | pinned panic seen |
|---|---|---|---|---|---|
| 1 | `c56.rs:265` `electro_land` | step / rollouts | `config.cards[key].chain.clone().unwrap()` | no chain is spawned. Damage, stun and the spirit's death are kept, as in `dragon_chain_hit`. | 91 (the live crash) |
| 2 | `c56.rs:466` `c56_area_tick` | step | `cards[spell_name].spell.unwrap()` | no effect. The area still expires at `effect_duration`. | 280 |
| 3 | `c56.rs:583-584` `delivery_tick` | step | `cards[spell_name]`, `.spell.unwrap()` | the delivery is removed with no impact and no spawns. | 175 |
| 4 | `c56.rs:625` `ranked_strike_tick` | step | `cards[spell_name].spell.unwrap()` | no strikes. It expires at `effect_duration`. | 70 |
| 5 | `lib.rs:1043` `rolling_tick` | step | `cards[name].spell.unwrap()` | the rolling projectile is removed. | 168 |
| 6 | `lib.rs:1106` rolling end spawns | step | `cards[cast.name].spawns[owner]` | no children. Unreachable after #5; kept for totality. | – |
| 7 | `lib.rs:2856` `pending_casts` | step | `cards[cast.name].spell.unwrap()` | the cast is dropped. | 7 |
| 8 | `lib.rs:2945` spell-carrying projectile impact | step | `cards[name].spell.unwrap()` | no spell effect at impact. Projectile handling is otherwise unchanged. | 252 |
| 9 | `scope.rs:263` `curse_spawn` | step | `cards[spell_name].spawns[owner][0]` | no child. | not exercised (no curse card in r1 config) |
| 10 | `scope.rs:406` spawn-area child | step | `cards[spell_name].spawns[owner].first()` | no child. The counter advances, as it already did for an empty template list. | not exercised |
| 11 | `spawn.rs:86` `production_child` | step | `config.production_children[unit key]` | no child this wave. | 133 |
| 12 | `champions.rs:299` Mighty Miner ability | step | `config.ability_bombs[unit key]` | no bomb. The tunnel and other ability state are unchanged. | 7 |
| 13 | `scripts.rs:180` `view` bodies | public_view / select_action / mask / rollouts | `meta.bodies[e.stats.name]` | the body is omitted from the view. | 16 (metadata cut) |
| 14 | `scripts.rs:249` `view` hand tokens | same | `meta.cards[s].token` | token 0, as for an empty slot. | seen in the first (unscrubbed) metadata run |
| 15 | `scripts.rs:296` `mask` | public_mask / select_action | `meta.cards[name]` | the slot is masked out. | – |
| 16 | `scripts.rs:152` `anchored_building_occupied` | mask | `b.config.cards[name]` | treated as occupied, so illegal. | – |
| 17 | `public_mask_v2.rs:56` building mask v2 | mask | `b.config.cards[name]` | illegal. | – |
| 18 | `scripts.rs:394`, `scripts.rs:533` scripted styles | select_action / rollouts | `meta.cards[name]` | the card is skipped. | – |
| 19 | `scripts.rs:403` spell scoring | select_action | `b.config.cards[name].spell.unwrap()` | the action is skipped. | – |
| 20 | `scripts.rs:808` rollout WAIT test | rollout | `meta.cards[n].cost` | counted as unaffordable. | – |
| 21 | `c56_scripts.rs:54` C56 scripted choice | select_action / rollouts | `meta.cards[name]` | the card is skipped. | – |
| 22 | `leaf.rs:33-35` `remaining_value` | evaluate / rollouts | `leaf_elixir_share.expect(..)` / `meta.bodies[name]` | share 0, which falls back to the existing intrinsic value. | – |
| 23 | `delay_commands.rs:61`, `e1_commands.rs:67`, `wait_screen8.rs:64` submit cost | rollout_e1 / rollout_commands / score_wait_screen8 | `meta.cards[&card].cost` | `PyValueError("submitted card absent from metadata")`. Only a caller-supplied own action can reach this, because #18/#21 never choose such a card. | – |

Total: 12 files, +79/−59 lines. All 26 textual replacements asserted exactly one match (`patch_total.py`). The build has
0 warnings.

**Deliberately unchanged:**
- `leaf.rs:70-71` `meta.bodies["Tower"/"KingTower"]` are fixed metadata keys and don't depend on the state.
- `.unwrap()` on fields of a card that is present (`crown_tower_damage`, `projectile_volley`'s spell) is a
  config-shape invariant, not a missing key.
- `apply_action`'s existing `ValueError("unsupported card absent from imported pilot configuration")` for a **hand**
  card that isn't in the config is a deliberate, catchable API error, and the cut config always keeps hand+cycle cards.
- These lookups already used `.get` and were not touched: `c56.rs:203`, `c56.rs:284`, `lib.rs:1003`,
  `lib.rs:3299-3364`, `spawn.rs:45`.

**Cross-check against LIVE `reports/live/integration/PANIC-FIX.md` (origin/main 45658350):**
- Every site it lists is in the table: c56.rs:265/466/583/625, lib.rs:1043/1106/2856/2945, scope.rs:263.
- It says "no other lookup on a unit key is unchecked". That holds only for `config.cards`. #11
  (`production_children[unit key]`), #12 (`ability_bombs[unit key]`) and #13 (`meta.bodies[unit name]`) are
  unit-keyed. Today's `fc` cut trims only `cards` and keeps the full metadata, so they don't fire in live play. The
  pinned native does panic on them when those entries are missing (§4c), and they are patched.

## 3. Build receipt

- **Patched tree:** 127x03 `/mpac/sdicks02/repos/clasher-bot-native-total/engine-rs`. It is `native-source-v2` plus
  `NATIVE-TOTAL.diff` (sha256 `96f280727b4c684a825f6005fa079fa87a639805aea37d6668e714a29469ace2`).
  - `patch -p1 < NATIVE-TOTAL.diff` on a fresh copy reproduces the tree (`diff -r` is empty).
  - Generator `patch_total.py`: `48da4cafaad4e5442ea753f9b1a979cf363c703912d446ce4122e6311111c8d1`.
- **Toolchain:**
  - rustc 1.97.1 (8bab26f4f 2026-07-14), LLVM 22.1.6; cargo 1.97.1 (c980f4866 2026-06-30);
  - `RUSTUP_HOME=/mpac/sdicks02/tools/rustup`, `CARGO_HOME=/mpac/sdicks02/tools/cargo` (offline registry);
  - `PYO3_PYTHON=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python` (3.12.15);
  - pyo3 =0.23.5 (abi3-py312), from the pinned Cargo.lock.
- **Command** (`native-total-tools/build.sh`, sha256 `c73846682ce6f0361d4e10ae5b3bf92e77196840777a3616f8ffdfcf39dfcea4`):
  `CARGO_TARGET_DIR=<out>/target CARGO_INCREMENTAL=0 nice -n 15 cargo +1.97.1 build --offline --manifest-path <src>/Cargo.toml --release --features extension-module,gil-release -j 16`.
  The `.so` is copied from `target/release/libclasher_core.so`.
- **Unpatched rebuild** (127x03, started 10:33:21Z): `44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2`.
  This is the provenance check.
- **Patched build** (127x03, 10:37:16Z–10:38:03Z): **`681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`**
  - at 127x03 `/mpac/sdicks02/repos/clasher-bot-native-total/native/clasher_core.abi3.so`, with `target/`;
  - a copy without `target/` is at the same path on 127x04.

## 4. Parity and totality (pinned `44874fd6` vs patched `681b5f2c`, each loaded by path in its own process)

| gate | inputs | pinned | patched | equal? |
|---|---|---|---|---|
| (a) 577-fixture gate, `bot.fidelity.rs_parity.run_one` (Python r1 `src` ↔ Rust lockstep digest) | all 577 train+val fixtures | 429/577 full-length parity | 429/577 | per-fixture records identical 577/577 |
| (a') Rust-only full trajectories | same 577 fixtures and plays, Rust only, to the recording's end. sha256 chain over every tick's `digest()`, `apply_action` results, `snapshot()` every 100 ticks and at the end. | 1,010,680 ticks, 0 errors | same | chains equal **577/577**. The whole output file is byte-identical (sha256 `f5a2665b…5c670` for both). |
| (b) recorded real search roots | 1,043 K4S-m2 roots (12 games vs R3a, all deck pairings, ticks 140–5,570). Random 300, each as the recorded `full` root and the `ConfigCache` `cut` root (the pool-worker build). | – | – | **600/600 records identical** |
| ↳ rollout_e1 | WAIT, timed WAIT 2401, ≤4 legal plays × 3 styles, frozen budget (h160, i10, ew1, delays 27) | 9,336 values | same | bit-equal (`float.hex`) |
| ↳ select_action / apply_discrete+step40 / step(1,50,200) digest+snapshot sha / evaluate / evaluation_parts / public_view / public_mask (both seats) / root snapshot sha | | 1,800 / 478 / 1,800 / … | same | all equal |
| (c) totality, crafted (`totality.py --scrub`). 17 scenarios: each card played into a real root, then cut from config (and hand/cycle) at 22 tick offsets, 19 probes per state. One scenario cuts the card from metadata instead. | 6,707 probes | **1,199 PanicException** at the 10 sites marked in §2 | **0 failures** | – |
| (c') same without scrubbing hand/cycle | 6,707 probes | 1,196 panics + 169 ValueError | **0 panics**. 244 ValueError: apply_action's existing "card absent from imported pilot configuration" for the cut card still in a hand. | – |
| regression: `crafted-fc-root.json` (sha256 737bd049…) | `rollout_e1_args` (seat 0, WAIT, balanced, h200, i5, ew0) | fc: **PanicException**. full: −0.10562149106854207 | fc: −0.10562149106854207. full: **−0.10562149106854207** (`-0x1.b0a0291e4e6a4p-4`) | full is bit-equal. On this root the fc value also equals full exactly. |
| regression: `repro/a/fail-3994559-1.json` (ab8a2f47…, tick 1410) | 4 candidates × 3 styles + step400 + view/mask/evaluate/select | 13/25 calls panic | 0/25 | both values the pinned native returned are bit-equal |
| regression: `repro/c/fail-3994582-1.json` (ec8c75ff…, tick 870) | 36 candidates × 3 styles + the same probes | 6/121 calls panic | 0/121 | all 104 values the pinned native returned are bit-equal |

Where the runs happened:
- (a)/(b)/(c) ran on 127x03 under `nice`, cores 56–63/112–119 after the core order, with ≤8 processes. The phases
  were: fixtures 10:48:03Z–11:23:24Z, roots until 11:24:08Z.
- The regression roots ran on 127x04 under `cpu_job.sh 2` and finished at 10:55:55Z.
- Nothing of this job is running on 03 or 04 now.

Commands:
- `native-total-tools/parity_all.sh` runs `parity_fixtures.py` then `parity_roots.py`, followed by `compare.py`.
- `record_all.sh` and `record_roots.py` recorded the roots.
- `totality.py` + `totality_table.py`; `regress_both.sh` + `regress.py`.
- Raw outputs are in `127x03:/mpac/sdicks02/jobs/clasher/bot-native-total/` (fixtures-*.jsonl, roots-*-?.jsonl,
  roots/) and `127x04:/mpac/sdicks02/jobs/clasher/bot-native-total/` (regress-*). The summaries are in
  `native-total-tools/results/`.

Totality per scenario (`results/totality-table.md`):

| scenario | cut states × probes | pinned panics (scrub / no-scrub) | patched panics (scrub / no-scrub) | patched ValueError (scrub / no-scrub) |
|---|---|---|---|---|
| arrows | 22 × 19 | 77 / 77 | 0 / 0 | 0 / 2 |
| barblog-rolling | 22 × 19 | 77 / 77 | 0 / 0 | 0 / 13 |
| earthquake | 22 × 19 | 91 / 91 | 0 / 0 | 0 / 7 |
| electro-spirit | 22 × 19 | 91 / 88 | 0 / 0 | 0 / 126 |
| fireball-projectile | 22 × 19 | 77 / 77 | 0 / 0 | 0 / 14 |
| firespirit-hut-production | 22 × 19 | 133 / 133 | 0 / 0 | 0 / 0 |
| goblin-barrel-delivery | 22 × 19 | 91 / 91 | 0 / 0 | 0 / 4 |
| goblin-hut-production | 22 × 19 | 0 / 0 | 0 / 0 | 0 / 0 |
| lightning-strike | 22 × 19 | 70 / 70 | 0 / 0 | 0 / 0 |
| log-rolling | 22 × 19 | 91 / 91 | 0 / 0 | 0 / 31 |
| meta-electro-spirit | 1 × 19 | 16 / 16 | 0 / 0 | 0 / 0 |
| mighty-miner-bomb | 22 × 19 | 7 / 7 | 0 / 0 | 0 / 36 |
| poison-area | 22 × 19 | 126 / 126 | 0 / 0 | 0 / 0 |
| rocket-projectile | 22 × 19 | 98 / 98 | 0 / 0 | 0 / 0 |
| royal-delivery | 22 × 19 | 84 / 84 | 0 / 0 | 0 / 0 |
| tornado | 22 × 19 | 63 / 63 | 0 / 0 | 0 / 1 |
| zap | 22 × 19 | 7 / 7 | 0 / 0 | 0 / 10 |

Limits:
- Sites 9 and 10 are covered by review only. No card in the r1 config reaches them.
- "Equal on valid states" is shown on the inputs above: fixtures, real roots in both config variants, and the
  non-panicking calls on the regression roots. It is not a proof.
- The behaviour when an entry is missing is a choice: skip the effect. It is not a model of the real game. A
  misperceived unit now keeps its body, its damage and its stun.

## 5. Proposed runtime pin (proposal only; nothing created under clasher-bot-runtime, no pin or env changed)

1. Copy only the `.so` and this receipt into a new read-only dir:
   `/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1/`, holding `clasher_core.abi3.so`, `NATIVE-TOTAL.md` and
   `NATIVE-TOTAL.diff`. Expected sha256 `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`. Do this on
   each host (03, 04, 08, …) from 127x03 `/mpac/sdicks02/repos/clasher-bot-native-total/native/clasher_core.abi3.so`.
2. Add `r1-total=dict(PINS, native_sha256='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b')` to
   `PIN_SETS` in `bot/players/runtime.py`. Keep `CLASHER_BOT_RUNTIME=…/clasher-bot-runtime/r1`. Select it with
   `CLASHER_BOT_RUNTIME_PINS=r1-total CLASHER_DELAY_NATIVE_DIR=…/clasher-bot-runtime/native-total-r1`.
   - In `Runtime._bootstrap_paths`, the only `sys.path` entries ahead of `native_dir` are r1's `engine-rs`,
     `engine-speed/stage5` and `search-noise-s6`. I checked that none of them holds a `clasher_core` `.so`.
   - I checked that `clasher_core.__file__` resolves to the chosen dir for both natives.
3. The r1 checkpoints, config and Python are unchanged, so HEADLINE results made under r1 stay comparable for every
   game that never hit a panic. Games that would have panicked under r1 now continue.
