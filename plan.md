## Executive Summary
This roadmap walks you from blank repo to a blazing‑fast **Clash Royale battle engine** in nine incremental phases.  It cherry‑picks proven ideas from open‑source private servers like **RetroRoyale** and **Ultrapowa Royale Server** for fidelity, borrows pure‑Python helpers from projects such as **Build‑A‑Bot**, **clash‑royale‑gym**, and **py‑clash‑bot** for convenience, and anchors every numeric constant to authoritative game data from **RoyaleAPI** and community research.  Follow the order, run unit tests at each checkpoint, and you will finish with a head‑less simulator that can execute thousands of battles per minute and plug directly into Gymnasium‑based RL stacks.  

---

## Phase 0 — Gather References & Tooling
1. **Clone reference servers**: RetroRoyale’s .NET Core repo exposes a `BattleState` tick loop and full physics; reading the code clarifies edge cases. ([github.com](https://github.com/retroroyale/ClashRoyale?utm_source=chatgpt.com))  Fork Ultrapowa Royale Server (UCR) for an alternative design of `BattleManager`. ([github.com](https://github.com/matbest1/UCR?utm_source=chatgpt.com))
2. **Download static card data**: Grab the latest `cards.json` from RoyaleAPI’s `cr-api-data` repository to avoid hard‑coding stats. ([github.com](https://github.com/RoyaleAPI/cr-api-data?utm_source=chatgpt.com))
3. **Record arena geometry**: Community measurements peg the main battlefield at roughly **32 × 18 tiles** with 3‑tile bridges and a centre river. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/75q9mc/strategy_touchdown_arena_tilemeasurements_grid/?utm_source=chatgpt.com))
4. **Confirm elixir timings**: Elixir regenerates every **2.8 s**, halving to **1.4 s** after the 2‑minute mark; triple‑elixir modes drop to ≈0.9 s. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/4h5umi/strategy_elixir_continues_to_regen_after_you_hit/?utm_source=chatgpt.com))
5. **Set up Python 3.10+ environment** with `mypy`, `pytest`, and optional `Numba` for later optimisation.

---

## Phase 1 — Static Data Layer
* Define a `CardStats` dataclass mirroring RoyaleAPI fields (`hitpoints`, `damage`, `range`, `speed`, etc.).  Load it once at startup. ([github.com](https://github.com/RoyaleAPI/cr-api-data?utm_source=chatgpt.com))
* Encode arena constants (tile grid, tower coordinates, deploy zones) in a `TileGrid` helper using the 32 × 18 schema. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/75q9mc/strategy_touchdown_arena_tilemeasurements_grid/?utm_source=chatgpt.com))
* Translate textual speeds (e.g., *Medium*, *Fast*) to numeric tiles‑per‑second using fandom tables or Build‑A‑Bot’s loader for consistency. ([github.com](https://github.com/Pbatch/ClashRoyaleBuildABot?utm_source=chatgpt.com))

---

## Phase 2 — Core State Model
* Create base `Entity` → subclass into `Troop`, `Building`, `Projectile`, `Aura`.
* Implement `PlayerState` holding `elixir`, 4‑card `hand`, `cycle_queue`, and `tower_hp`; py‑clash‑bot offers a minimal reference. ([github.com](https://github.com/pyclashbot/py-clash-bot?utm_source=chatgpt.com))
* Compose these into a master `BattleState` that owns the clock, entity dict, two players, and elixir‑mode flags.

---

## Phase 3 — Fixed‑Timestep Loop
* Adopt RetroRoyale’s **33 ms tick** (≈30 FPS) for deterministic updates. ([github.com](https://github.com/retroroyale/ClashRoyale?utm_source=chatgpt.com))
* On each tick:
  1. Increment `time` and `tick` counters.
  2. Regenerate elixir via `PlayerState.regen(dt, 2.8 or 1.4)`. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/4h5umi/strategy_elixir_continues_to_regen_after_you_hit/?utm_source=chatgpt.com))
  3. Iterate over `entities.values()` calling `e.update(dt, state)`.
* Flip `double_elixir` at 120 s; enable `triple_elixir` flag for special modes.

---

## Phase 4 — Movement, Aggro & Combat
* **Path‑finding (v1)**: Straight‑line toward the nearest legal target, respecting bridge/range checks; refine later with A* over the tile grid.
* **Attack cadence**: Give every entity a local cooldown; apply damage when it hits zero, then reset to `hit_speed`.  Build‑A‑Bot’s JSON snapshots illustrate expected field names. ([github.com](https://github.com/Pbatch/ClashRoyaleBuildABot?utm_source=chatgpt.com))
* **Target rules**: Towers attack nearest hostile; *building‑only* troops ignore units; keep logic modular for easy test cases.

---

## Phase 5 — Full Game Rules
* **Hand & cycle**: Replicate the four‑card hand, `next_card_queue`, and Mirror mechanics using py‑clash‑bot’s logic. ([github.com](https://github.com/pyclashbot/py-clash-bot?utm_source=chatgpt.com))
* **Spells & projectiles**: Introduce a `Projectile` class with travel speed and splash radius.
* **Win conditions**: End when a King Tower HP ≤ 0 or higher crown count after 5 minutes.
* **Sudden‑death overtime**: First tower destroyed wins; elixir at x3 as per Supercell seasonal rules. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/4h5umi/strategy_elixir_continues_to_regen_after_you_hit/?utm_source=chatgpt.com))

---

## Phase 6 — Turbo Mode & Head‑less Execution
* Remove all rendering; drive `state.step(dt * speed_factor)` to run 10× or faster.
* Dump each tick to JSON via `msgspec` for offline analysis or replay.
* Optionally embed the engine behind a thin gRPC layer to mimic how ZrdRoyale isolates its battle micro‑service. ([github.com](https://github.com/Zordon1337/ZrdRoyale?utm_source=chatgpt.com))

---

## Phase 7 — Testing & Validation
1. **Unit tests**: Knight‑vs‑Knight mid‑bridge should leave identical HP on both sides.
2. **Cross‑check with private‑server replays** from RetroRoyale/UCR for deterministic tower HP after scripted seeds. ([github.com](https://github.com/retroroyale/ClashRoyale?utm_source=chatgpt.com), [github.com](https://github.com/matbest1/UCR?utm_source=chatgpt.com))
3. **Performance benchmarks**: Profile with `cProfile`; optimise hotspots with Numba when a tick exceeds 1 ms at 10× speed.

---

## Phase 8 — Reinforcement‑Learning API
* Wrap `BattleState` with Gymnasium via `clash-royale-gym`’s `(obs, reward, done, info)` interface to stay compatible with Stable‑Baselines and RLlib. ([github.com](https://github.com/MSU-AI/clash-royale-gym/?utm_source=chatgpt.com))
* Observation: compress tile grid to a 128×128×3 tensor (owner mask, troop type, HP).
* Action: encode `(hand_idx, x_tile, y_tile)` into `Discrete(2304)` per the gym repo. ([github.com](https://github.com/MSU-AI/clash-royale-gym/?utm_source=chatgpt.com))

---

## Phase 9 — Polish & Future Work
* **Path quirks**: Implement bridge‑switch logic and tile snapping noted by community researchers. ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/75q9mc/strategy_touchdown_arena_tilemeasurements_grid/?utm_source=chatgpt.com))
* **Advanced mechanics**: Add knock‑back, stun, death‑spawns, and king‑activation river triggers.
* **Versioning**: Link card‑stats loader to balance‑patch tags in RoyaleAPI so you can run historical simulations for meta analysis. ([github.com](https://github.com/RoyaleAPI/cr-api-data?utm_source=chatgpt.com))
* **License diligence**: RetroRoyale and UCR are GPL‑3—keep your engine MIT/BSD if you want permissive reuse by avoiding their source code in final distribution. ([github.com](https://github.com/retroroyale/ClashRoyale?utm_source=chatgpt.com), [github.com](https://github.com/matbest1/UCR?utm_source=chatgpt.com))

---

### References (quick links)
* RetroRoyale Clash Royale Server ([github.com](https://github.com/retroroyale/ClashRoyale?utm_source=chatgpt.com))  
* Ultrapowa Royale Server (UCR) ([github.com](https://github.com/matbest1/UCR?utm_source=chatgpt.com))  
* RoyaleAPI Card Data ([github.com](https://github.com/RoyaleAPI/cr-api-data?utm_source=chatgpt.com))  
* Elixir Regeneration Discussion ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/4h5umi/strategy_elixir_continues_to_regen_after_you_hit/?utm_source=chatgpt.com))  
* Arena Tile Measurements ([reddit.com](https://www.reddit.com/r/ClashRoyale/comments/75q9mc/strategy_touchdown_arena_tilemeasurements_grid/?utm_source=chatgpt.com))  
* Build‑A‑Bot State Generator ([github.com](https://github.com/Pbatch/ClashRoyaleBuildABot?utm_source=chatgpt.com))  
* clash‑royale‑gym Environment ([github.com](https://github.com/MSU-AI/clash-royale-gym/?utm_source=chatgpt.com))  
* py‑clash‑bot State Class ([github.com](https://github.com/pyclashbot/py-clash-bot?utm_source=chatgpt.com))  
* ZrdRoyale Micro‑service Example ([github.com](https://github.com/Zordon1337/ZrdRoyale?utm_source=chatgpt.com))  

