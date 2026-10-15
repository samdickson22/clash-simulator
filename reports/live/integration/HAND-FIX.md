# Own hand/cycle sanitising + search-failure stats (exploration tier)

Owner: hand-fix sub-agent (parent: LIVE LEAD), 127x05 worktree `live/lead` on main 5cb79878, 2026-10-15. No commits.
Job dir (05): `/mpac/sdicks02/jobs/clasher/live-hand-fix/` (`run-games.sh`, `games_driver.py`, `games/`, `suites-*.log`).

## 1. Hand/cycle invariants (bot-lead finding: two Valkyries in our hand, a 5-card cycle)

**Cause.** `OwnTracker.own()` took the HUD hand as is: it blanked off-deck cards only, so a misread slot that named a
card already held gave a duplicate hand. The cycle was built as `deck − set(hand)`, which then had 5 cards. A `next`
that was a held card was silently dropped. The empirical channel (`empirical.py`) misreads 1.15% of slots and 1.5% of
`next` reads per frame, each as a random other deck card, so about 2% of frames held a duplicate.

**Fix (`bot/live/translate.py`).** Our hand is now tracked, not read:
- **`_Cycle`.** The engine's own dynamics (`src/clasher/player.py`, the same rule as the frozen `own_cycle.OwnCycle`): a
  play empties its slot and appends the card to the queue. When the refill cooldown reaches 0, the first empty slot
  takes the queue head. A slot changes only after our own play of that slot.
- **`OwnTracker`.** It is reset from the opening order (`set_own_order`) and fed our own plays. Every HUD reading
  that disagrees with the tracked state is overridden and counted in `stats['own_fix:<kind>']`:
  - `duplicate`, `off_deck`, `missing`, `slot` (a plausible but wrong card) and `empty` for hand slots;
  - `next_in_hand`, `next`, `next_missing` and `next_off_deck` for the next card;
  - totals `own_fix` and `own_fix_frames`.
- **What the HUD still decides.** It settles what the play history can't: the order of the opening queue past
  `known`. LiveSession knows only hand + next; the other 3 come from the deck order.
  - Each ordering is a hypothesis (at most 3! = 6).
  - Each slot mismatch costs `min(prob, .98)`, using the HUD probabilities when the record carries `probs` and
    `next_prob`.
  - The lowest cumulative cost wins. Ties go to the given order.
- **Recovery when the tracker itself is wrong** (a guessed mid-match start, a missed own play):
  - an own play of a card no hypothesis holds re-anchors the tracker (`own_reanchor_play`);
  - a valid HUD state that differs from the tracked one and reads the same on 4 consecutive polls re-anchors on it
    (`own_reanchor_hud`).
- **Invariants on every `information()`** (`own_invariant_breaks`, which is checked and would count
  `own_invariant_break`):
  - 4 slots of distinct deck cards or `None`;
  - next = cycle[0], and it isn't held;
  - hand + cycle = the 8 deck cards.
  - The cycle has **4 cards when the hand is full**. During a refill the played card waits at the back, giving 3 + 5,
    exactly as the engine's `cycle_queue` and the frozen OwnCycle do. A 5-card cycle beside 4 held cards can no
    longer happen.
- **LiveSession** (the live loop) now confirms our pending play from the raw HUD instead of the hand the bot sees:
  - the reserved slot must read empty, or a card not held elsewhere, on 2 consecutive polls, so one misread can't
    complete a command;
  - the play event then enters **that** poll's record, so the bot never sees a card that already left its slot;
  - the opening hand must have 4 distinct deck cards (`opening_hand_waits`);
  - `_reconcile` also completes a command when the tracked slot changed. That covers a play the tracker took but
    the stream guard dropped.
- **Fair information.** The tracker reads only our deck, our HUD and our own plays.

**Opponent side.** No invariant break was found:
- the opponent dict in a search root is a belief sample, which is a permutation of an 8-card deck by construction
  (`derived_public_state`);
- the test samples the belief along a PERC-emp game's translator event stream, resyncs included, and every sample
  passed `deck_state_breaks`;
- `_WallMulti.act` now counts root breaks of both players per decision (`own_state_break`, `opp_state_break`; expected
  0, never corrected).

## 2. `native_failure` propagation (`bot/live/player.py`)

- `LivePlayer._done` copied only 6 search keys. It now uses `search_stats()`: the fixed keys (incl. `native_failure`),
  plus **any key naming a failure** (fail/error/panic/broken/dead), plus `native`/`learned` as
  `native_rollouts`/`learned_rollouts`. A new failure field reaches the decision stats and `LiveSession.log` without a
  change here.
- `LivePlayer.native_failures` counts failures by kind per match (`native_failures` in the stats).
- **Found while testing:** since 654b18bb, a killed K4L pool worker doesn't produce `native_failure`.
  - Its rollouts simply don't return (a timeout), and the pool is recreated (`lopp.FAILURES['pool_recreated']`).
  - LivePlayer now reports the per-decision change in `lopp.FAILURES` as `search_failures` (e.g.
    `{'pool_recreated': 1}`).
- `test_panic_guard.py::test_k4l_dead_pool_worker_keeps_falling_back` was stale against 654b18bb: it expected
  `fast-error`. It now asserts the new contract:
  - `pool_recreated` appears in `search_failures`;
  - there is no `fast-error` and the search isn't disabled;
  - the search resumes.

## Tests

- **New `bot/live/test_hand_fix.py`, 15 tests:**
  - the four HUD faults (duplicate slot, off-deck slot, next = a held card, missing slot);
  - "a slot changes only after our play" (4+4 / 3+5);
  - exact parity with the frozen OwnCycle under heavy HUD noise;
  - unknown queue order learned from the HUD (0 hand errors; next wrong ≤ 0.2% of frames, only on the reveal frame);
  - both re-anchors;
  - the translator packet's hand ids;
  - fair-information invariance (opponent-private record fields change no own state, count or packet);
  - LiveSession play confirmation (a single misread doesn't complete; 2 polls do);
  - opening-hand wait;
  - `native_failure` + other failure fields + the counter reaching the decision stats;
  - `root_state_breaks`;
  - a PERC-emp game: **the own state the bot saw equalled the engine's true hand and cycle on every poll** while
    `own_fix` > 0, and every opponent belief sample was valid.
- `test_live.py::test_translator_rows_towers_globals`: the record plays our Knight at 500, yet the HUD still shows it
  at 600. The test now expects the tracked state (MiniPekka refilled, Knight at the back of the cycle).
- **Final run on 05** (cores 2–5, nice 10, docstring env + `CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models`;
  `PYTHONPATH=.:bot/live`, because `test_panic_guard` imports `test_live` as a top-level module):
  - `test_hand_fix` + `test_live` + `test_integration` + `test_panic_guard` gave **61 passed, 1 skipped** (230 s).
  - The skipped test is the panic reproduction: the native pin no longer panics (total lookup).
  - The fair-information tests (`test_invariance_*`, `test_sanitizer_is_fair_information_invariant`,
    `test_resync_is_fair_information_invariant`, new `test_hand_sanitising_is_fair_information_invariant`) pass.

## 4 × PERC-emp:LIVE-fast-it5s2 on 05

Command: `run-games.sh`, i.e. `bot.live.headline_wall --group 1 --cores 2-5 --engine ours`, games 0–1 × v1/R3a.
Per-game stats are in `games/perc-stats.jsonl`.

**Result: 4/4 terminal, 0 perc errors, 0 invariant breaks, 0 re-anchors.**

Corrections count per-poll HUD slot/next overrides.

| opp, idx, seat | score | ticks | polls | corrections | frames corrected | duplicate | wrong slot | next = held | wrong next | order pruned by a play | rejected taps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1, 0, 0 | 1 | 3601 | 703 | 32 | 32 | 10 | 14 | 5 | 3 | 2 | 1 |
| v1, 1, 1 | 1 | 3601 | 703 | 46 | 46 | 18 | 15 | 8 | 5 | 2 | 6 |
| R3a, 0, 0 | 1 | 4711 | 925 | 37 | 37 | 11 | 18 | 6 | 2 | 0 | 5 |
| R3a, 1, 1 | 1 | 5998 | 1182 | 65 | 64 | 18 | 40 | 3 | 4 | 2 | 3 |
| **total** | 4/4 | | **3513** | **180** | **179 (5.1%)** | **57** | **87** | **22** | **14** | 6 | 15 |

- The channel misreads only into our own deck, so there were 0 off-deck or missing corrections.
- The 57 duplicate frames (1.6% of polls) are exactly the bot lead's duplicate-Valkyrie / 5-card-cycle roots.
- The 87 "wrong slot" frames (a held card shown as a cycle card) used to pass silently as a wrong hand.
- **Rejected taps** are taps the true state refused (PercPlayer's scratch check). The tracked hand was exact in the
  test game, so these come from elixir noise (sd .1), not the hand.
- 4/4 is not a win-rate estimate (n = 4).

## Not done / residual

- **real_replay / mac_bench numbers in RESULTS.md weren't re-run.** Those arms now see the tracked own state; their
  own plays are the true plays, and a wrongly guessed mid-match opening re-anchors.
- **LiveSession's frozen own mirror (`_own_cycle`, stream guard)** still uses the guessed deck order for the 3 unknown
  queue cards, so it can drop an own play from the public rows (`cycle_conflict_dropped:0`). This predates the fix.
  The tracker takes the play anyway, and `_reconcile` now completes the command.
- **No test stages a guard-dropped own play inside LiveSession.**
- **Files:**
  - `bot/live/translate.py` (`_Cycle`, `own_invariant_breaks`, `deck_state_breaks`, `OwnTracker`, `set_own_order(known)`,
    `hud` probs, LiveSession `_confirm_pending`/`_reconcile`/opening wait, docstrings);
  - `bot/live/player.py` (`search_stats`, `native_failures`, `search_failures`, `root_state_breaks`);
  - `bot/live/test_live.py` (1 assertion);
  - `bot/live/test_panic_guard.py` (K4L test updated to 654b18bb);
  - new `bot/live/test_hand_fix.py`;
  - this file.
