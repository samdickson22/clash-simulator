# Native panic under empirical perception noise: cause, our guards, verification (exploration tier)

Owner: panic-fix sub-agent (parent: LIVE LEAD), 127x05 worktree `live/lead`, 2026-10-15 (finished 10:46Z). No commits.
Scope: defence in depth on our side. The bot lead's `bot-lead-k4l-fix-r1` owns the `fc` config trim, pool recovery and a
non-panicking native lookup. Job dir: `/mpac/sdicks02/jobs/clasher/live-panic-fix/` on 05.

## Cause (reproduced on 05 and pinned)

On 03, `PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4` killed 6 of 10 eval workers with
`thread panicked at src/c56.rs:265:46: no entry found for key`.

**Reproduced on 05.** I ran `run-repro.sh`: headline_wall, one 4-core group, PERC games 0–4 against v1/R3a.
- 4 games passed; the worker died on job (PERC, v1, index 2). On 03 that same job killed worker 0.
- A driver dumped the root just before the panic: `failing-root-perc-emp-v1-idx2-seat0-tick1410.json`
  (sha256 `7aa64b2cace9235e0014cdd61777b94f63423f1dbc2068422ab57a6a258fc3a6`). It holds the fc snapshot as built, the
  seat, the candidates and the information's own/events.

**The failing root:**
- Seat 0 (the acting bot), tick 1410.
- Our deck: Arrows, Giant, Valkyrie, Wizard, HogRider, FireSpirits, Minions, Knight.
- The opponent had revealed 6 cards (IceGolem, Skeletons, Cannon, IceSpirit, Musketeer, HogRider). The belief's sample
  added Fireball and Log.
- The `fc` config therefore held exactly those 15 cards.
- The root had an **own-side `ElectroSpirit`** at (3.3, 19.2) and an **own-side `MinionHorde`**, neither in our deck.
  These are empirical-noise misreads. In `bot/live/empirical-val.json`:
  - FireSpirits → ElectroSpirit is 0.4% per frame;
  - Minions → MinionHorde is 4.6%;
  - own-side false positives include ElectroSpirit 75 times.
- When the spirit lands, `electro_land` does `self.config.cards[source.stats.key()].chain.clone().unwrap()`. The key
  `ElectroSpirit` is missing, so it panics.
- ElectroSpirit is the only C56 card with `chain`. Other off-config units (MinionHorde here) don't panic **today**,
  because no other lookup on a unit key is unchecked. They are still inconsistent with the config.

**Why it crashed the process:**
- `pyo3_runtime.PanicException` has the MRO `(PanicException, BaseException, object)`.
- `LivePlayer.act` caught only `Exception`. In the threaded path it surfaced at `reduce_fast` → `f.result()`.
- A panic inside a p4 pool worker (`batch_rollouts` → `step`) kills that worker process.
- Perfect sight never puts a card outside both decks on the board, which is why the `LIVE-K4L-…` arm had 0 crashes.

**Crafted twin.** `crafted-fc-root.json` (sha256 `737bd049574a025c3750dc9b502651138dbb1a5d2168b108bdf7df79fa59aa86`) builds
the same situation deterministically:
- input: an own ElectroSpirit (deck without it) and an enemy Knight, run through LiveTranslator, then `R.root`, then
  `ConfigCache` (the fc cut);
- `rollout_e1` panics on the fc payload and returns -0.1056 on the full-config payload;
- the call arguments are inside the JSON.

## Fix (our code)

1. **Card-consistency guard at the translator** (`bot/live/translate.py`, `LiveTranslator.board_card_ok`, hooked in
   `assign`). `ResyncTranslator` and `BothTranslator` inherit it.
   - **The rule** is the deck rule under fair information. It reads only our deck and the accepted public plays.
     - **Own units:** must be in our own 8-card deck (exact).
     - **Opponent units:** must be a card already seen played, or any card while fewer than 8 distinct opponent cards
       are known.
     - Everything else is **dropped** and counted in `stats['board_dropped:<owner>:<card>']`.
   - It doesn't mirror the trimmed config: a still-possible unrevealed opponent card is kept
     (`board_unrevealed_opp_kept`), and the `fc` trim is the bot lead's.
   - **Drop rather than flip:**
     - Perception reads the owner from the health-bar colour, and the measured channel's errors are in the card.
       Flipping an own misread would put a phantom enemy where our unit stands.
     - A one-frame misread of a tracked unit leaves that unit's track alive for `ttl` ticks.
     - Off-deck own units can't be an opponent card that we'd lose, because owner errors aren't modelled.
   - **Known bias:** if a spurious event revealed a wrong 8th opponent card, units of the true 8th card are dropped as a
     "9th card". This is the same rule the translator already applies to plays (`ninth_enemy_card_dropped`).
   - Card-level records only (the deployed path). The legacy `class`-body path (`card_level=False`) isn't covered.
2. **Fallback guard** (`bot/live/player.py`, `LivePlayer.act`).
   - The fast-tier and search-tier `except` clauses now catch `BaseException`. `KeyboardInterrupt`, `SystemExit` and
     `GeneratorExit` are re-raised (`_reraise_control`).
   - A panic is recorded as `source='fast-error'` with `error`, and counted in `LivePlayer.panics` (also in the
     decision stats).
   - It goes through the existing consecutive-error rule: after `max_errors` the search is disabled for the match.
   - **Dead K4L pool:** after a worker dies, every later search decision raises (BrokenPipe/EOF from
     `LearnedPool.begin`/`collect`), so the match continues on it5s2 and the search is disabled. This is tested with a
     real killed pool worker.

## Tests

New `bot/live/test_panic_guard.py`, 8 tests, all passed on 05. They used the real native: the panic was reproduced,
not skipped.
- `test_unsanitized_off_deck_unit_panics_the_fc_root`: the crash path itself.
  - With the sanitizer off, the fc root panics with `PanicException`, which is not an `Exception`.
  - The full-config root runs.
  - The test skips by itself once a native pin no longer panics there.
- `test_sanitizer_drops_off_deck_units_and_the_root_runs`: the same records with the guard. 5 drops, and the fc root's
  value equals the full root's.
- `test_board_rule_is_the_deck_rule`, `test_sanitizer_is_fair_information_invariant`, and
  `test_perfect_perception_drops_nothing` (PERC-events, 2 seats, 0 drops).
- `test_native_panic_in_search_falls_back_to_it5s2_then_disables`: the real `PanicException` class.
  - Decisions are `fast-error`, `fast-error`, then `fast-disabled`; every action is it5s2's.
  - `KeyboardInterrupt` still propagates.
- `test_fast_tier_panic_is_caught`.
- `test_k4l_dead_pool_worker_keeps_falling_back`.
  - LIVE-K4L p4; a pool worker is killed at the 3rd search decision.
  - The match finishes, with no `search` decision afterwards and `fast-disabled` reached.
  - It needs `CLASHER_LOPP_MODELS` and is skipped without it.

Existing suites with their docstring env (`CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1`):
`bot/live/test_live.py` + `bot/live/test_integration.py` gave **39 passed** (152 s, cores 2–5).

## Verification: 10 × PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4 on 05

- Command: `run-verify.sh` (games 0–4 × v1/R3a; one group, cores 2–5, nice 10).
- Per-game stats come from `verify/perc-stats.jsonl`. Rows in `verify/games-000.jsonl`.
- It covers the two 03 crash jobs inside this range: (v1, 2) and (R3a, 3).

**Result: 10/10 games terminal, 0 worker crashes, 0 error rows, 0 panics, 0 `fast-error` decisions, search never
disabled.**

Drops count unit-frames: one per 5-tick poll record that the unit appears in. "Opp-side drops" are 9th-card units (8 known).

| opp, idx, seat | score | ticks | own-side drops | opp-side drops | opp unrevealed kept | ElectroSpirit dropped own/opp | panics | sources |
|---|---|---|---|---|---|---|---|---|
| v1, 0, 0 | 1 | 4034 | 172 | 0 | 183 | 3/0 | 0 | search 119, default 6 |
| R3a, 0, 0 | 1 | 6001 | 282 | 222 | 148 | 1/3 | 0 | search 181, default 12 |
| v1, 1, 1 | 1 | 3601 | 202 | 5 | 181 | 0/0 | 0 | search 106, default 6 |
| R3a, 1, 1 | 0 | 3621 | 178 | 8 | 154 | 0/0 | 0 | search 102, default 1 |
| v1, 2, 0 | 1 | 3601 | 189 | 92 | 123 | 1/4 | 0 | search 106, default 5 |
| R3a, 2, 0 | 1 | 3817 | 192 | 67 | 154 | 3/1 | 0 | search 104, default 7 |
| v1, 3, 1 | 1 | 3601 | 174 | 88 | 46 | 1/0 | 0 | search 104 |
| R3a, 3, 1 | 1 | 3601 | 130 | 307 | 200 | 0/2 | 0 | search 107, default 6 |
| v1, 4, 0 | 0 | 3601 | 137 | 350 | 45 | 0/0 | 0 | search 99, default 4 |
| R3a, 4, 0 | 0 | 3601 | 151 | 52 | 194 | 0/1 | 0 | search 104, default 4 |
| **total** | 7/10 | | **1807** | **1191** | **1428** | 9/11 | **0** | |

- Before the fix, the same setup crashed on game 5 (v1, 2).
- The score (7/10) is not a win-rate estimate: n = 10 and wall-clock search.
- Board-drop cost wasn't measured. The drop rate is about 0.25 own-side unit-frames per poll.

## Residual risk and the bot lead's side

- **Still open on our side:**
  - an opponent ElectroSpirit of a still-possible unrevealed card (deck rule: kept) when the belief sample lacks it;
  - a card-confused opponent unit with < 8 revealed.
- Under `fc` this can still panic: 1428 unrevealed-opponent unit-frames were kept over the 10 games, and none of them
  panicked here.
- **What happens if it does:**
  - **threaded path:** caught, so one `fast-error`;
  - **p4 pool path:** the worker dies, and the search is disabled for the rest of the match (clean, but degraded).

**For the bot lead (`bot-lead-k4l-fix-r1`):**
1. **Trim:** include every on-board entity's card key in the `fc` config. Both `_ConfigJson.dumps` and
   `ConfigCache.payload` cut from hand+cycle only. Alternatively, fall back to the full config when an entity key is
   outside the cut.
2. **Pool recovery:** in `reduce_fast`/`LearnedPool`, catch `PanicException` inside `_pool_worker` (BaseException) and
   reply `vals=None`, so the worker survives. Treat EOF/BrokenPipe from a worker as a dead pool, and recreate it
   (`_POOLS.pop(n)`, then `get_pool`) at the next decision instead of raising forever.
3. **Native:** make the lookup total in `c56.rs:265`, like `dragon_chain_hit` already uses `.get(...)`. The other
   indexing sites keyed by spell/cast names (c56.rs:466/583/625, lib.rs:1043/1106/2856/2945, scope.rs:263) aren't
   reachable from perceived units, because spells aren't in the perception schema. They key on cards a player cast
   from its hand, which are in the cut; total lookups there would still be cheap insurance.
4. **Regression inputs:** `/mpac/sdicks02/jobs/clasher/live-panic-fix/failing-root-perc-emp-v1-idx2-seat0-tick1410.json`
   (real) and `crafted-fc-root.json` (minimal, deterministic).

## Files

- **Repo (uncommitted):**
  - `bot/live/translate.py` (`board_card_ok`, `sanitize`, docstring policy line);
  - `bot/live/player.py` (BaseException guards, `panics`, docstring);
  - new `bot/live/test_panic_guard.py`;
  - this file.
- The worktree also holds other agents' uncommitted edits (`bot/live/empirical.py`, `bot/live/perc.py`,
  `bot/live/test_integration.py`, `live/perception/*`, `reports/live/PROGRESS.md`). They aren't part of this fix.
- **Job dir (05):** `run-repro.sh`/`repro_driver.py`, `repro/`, `dumps/`; `run-verify.sh`/`verify_driver.py`, `verify/`;
  `scratch/craft.py`, `scratch/capture.py`.
