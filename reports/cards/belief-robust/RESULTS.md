# Belief robustness: explicit C56 flag, unknown cards / late reveals, deadline-bounded rebuild

**Current: r3 = 74978f6dd** (belief.py `127ad256…`, player.py `3cb546b4…`). r3 bounds the C56 LiveBelief (rollback path) rebuild, the remaining finding of the Sol review of
r2. The full-pool path that live runs is unchanged in behaviour from r2 (26b0ca8d7, belief.py `d1db6aeb…`), and r2 stays
deployable. See "r2: review fixes" and "r3" at the end. The r1 gate tables below are kept; r2 and r3 reran the gates.

Branch `cards/belief-robust` (from origin/main 8c408d735). Exploration tier. Owner: CARD LEAD implementer (Opus).
Live input: bot-live-diag, s74 (2,466 searches). Belief rebuilds are 1.6% of searches but ~75 ms each on the Mac,
25 of the 30 searches over 100 ms. One cost a live decision: **s74-m11 n394** (poll tick 530, rebuild, 192 ms, hit,
completed 0 → `default-it5s2`), the only default-* fallback in s73+s74.

## Fixes

| # | Change | File |
|---|---|---|
| 1 | `banks.select(rt, …, 'c56')` keeps the literal `'c56'` (it was None, so an inherited `BOT_BELIEF_PRIOR=fullpool:…` overrode the explicit flag). `levels.scope.install` now uses `belief_spec(rt)`, so the explicit flag wins there too. | `bot/fullpool/banks.py`, `bot/levels/scope.py` |
| 3 | **Unknown names / late reveals.** `open_world_class` (shared by FullPoolBelief and the C56 LiveBelief; `base` stays `__mro__[1]`, as the fp_mac_bench rebuild hook expects) canonicalises the event stream before the frozen belief sees it. See "Unknown names" below. | `bot/fullpool/belief.py`, `bot/live/player.py` |
| 4 | **Deadline-bounded rebuild.** See "Bounded rebuild" below. | same |

Neither the frozen belief sources nor any translator, policy or engine file changed.

**Unknown names (#3)**
- A name the belief can't encode is resolved to a known card when an alias exists: display, vocab and Battle Log spellings, plus evolution and hero names ("Evo Knight" → Knight, "Rune Giant" → GiantBuffer).
- Otherwise it becomes `~<name>`, a revealed unknown that occupies one deck slot and cycles like any card. Its elixir cost is the meta's weighted mean cost.
- `sample()` replaces `~` names, per sampled row, with the most frequent known non-champion card of the nearest cost that the row doesn't hold. The search never sees a `~` name.
- A certain play that can't share one deck with the earlier reveals (a 9th distinct card, a 2nd champion) is dropped from the belief's stream and counted in `dropped`. Today that raises ValueError, three of which disable search.
- The mapping depends only on earlier events, so the stream stays append-only. Known streams pass through as the same object.

**Bounded rebuild (#4)**
- With no deadline the rebuild runs the same frozen operations as before: same arrays, same fixed-timing command
  hashes (gate 1). "Unchanged" means behaviour and hashes, not bytes: the layer adds its own fields (`stale`,
  `dropped`, `rebuild_slices`, the name map) and module caches (priors per revealed set, the order table).
- With a deadline, the rebuild is a resumable job in bounded steps (r2):
  - prior: one sampler draw per step;
  - state construction: one prior deck per step, into preallocated arrays;
  - history replay: a bounded twin of s1's transaction, one 4096-row block per step, with the cumulative weights in
    16k-row steps. Surviving rows are compacted in place in the job's own buffers, so there is no whole-array
    concatenation or cumsum and no ~20 MB allocate/free per play.
  - Priors are cached per revealed set. The finished job is identical to the synchronous rebuild (tested).
- One cutoff per `update()` (r2): now + `BOT_BELIEF_REBUILD_SHARE` (default 0.5) of the time left, at least 20 ms,
  never past the deadline. A job that finishes and a second job that the newer history needs share it.
  - Malformed, non-finite or out-of-range share values (outside (0, 1]) fall back to 0.5 (r2). Before, they raised
    ValueError, and three of those disable search.
  - On the Mac's ~185 ms remainder the rebuild gets ~92 ms, more than a typical ~75 ms rebuild.
- If unfinished, `update` returns with `stale=True`. The decision searches on the previous posterior instead of falling back to the default, and the job resumes next decision. LivePlayer stats gain `belief_stale`.
- Option (b), off the decision path, was rejected: a thread would contend for the GIL with the search's Python parts, and doing the work on idle polls would delay the next frame of the live loop.

## Tests (r1; `bot/fullpool/test_belief_robust.py`; run on the real frozen + s1 belief sources, no runtime)

| Required test | Test(s) | Result |
|---|---|---|
| Late reveal: a card first seen after N rebuilds is in all later posterior states | `test_late_reveal_after_several_rebuilds` (5 rebuilds, all earlier reveals present after each) | pass |
| Unknown name: no exception, valid 8-card deck structure, search not disabled | `test_unknown_alias_and_valid_engine_sample`, `test_impossible_reveals_are_dropped_not_fatal`, `test_live_belief_layer`; positive smoke below (search not disabled) | pass |
| Tight deadline: decision returns in time, rebuild completes later and is consistent | `test_rebuild_suspends_resumes_and_includes_new_late_event` (stale posterior usable; completes over many decisions and equals the synchronous twin), `test_unknown_under_deadline_equals_synchronous`, `test_expired_deadline_does_no_rebuild_work`, `test_chunked_init_exactly_matches_frozen` | pass |
| Explicit C56 flag beats the env var | `test_explicit_c56_beats_environment` | pass |

Results:
- 05, no runtime: `pytest bot/fullpool/test_belief_robust.py bot/fullpool/test_fullpool.py` → 20 passed.
- 04, runtime live16402b-r3: the same plus `bot/live/test_live.py::test_live_belief_survives_off_prior_decks` (the C56 LiveBelief through the new layer) → 21 passed.

## Gates (r1)

### 1. Default-off parity (fixed timing, deterministic; 08, `gate.sh` + `verify.py`)

`before` = origin/main 8c408d735 (git archive). `after` = the change at first launch. `after2` = the committed tree
6270c382b (adds the 20 ms floor, used only under a deadline, and the `belief_stale` stats key). No deadline anywhere, PYTHONHASHSEED=0.

| Row | Prior / belief class | Cases | before = after | before = after2 |
|---|---|---|---|---|
| K4L-R-gs-rw-fc HEADLINE vs R3a, v1 (live16402c) | C56 catalog, frozen Belief | 0–5 × 2 | **12/12** | **12/12** |
| LIVE-K4CW-r16 HEADLINE vs R3a (live16402c) | C56, LiveBelief (new layer) | 0–2 | **3/3** | **3/3** |
| K4L-R-gs-mk1a1 LIVE-AB1 vs R3a (bundle env, live16402b-r3) | full pool, FullPoolBelief (off-vocab decks: synchronous rebuilds) | 0–3 | **4/4** | **4/4** |
| LIVE-K4CW-r16 LIVE-AB1 vs R3a (bundle env) | full pool, FullPoolBelief via LivePlayer | 0–3 | **4/4** | **4/4** |

`verify.py before after after2`: **VERIFY_PASS, 23/23 identical in both arms, 0 error / nonterminal rows**. The K4L hashes equal the
fullscope-belief gate's (`38ca14d8…`, `872e6bfc…`, …). The mk1a1 hashes equal the 10-16 bundle `eq-main` rows
(case 0 `2bf60631…`, case 3 `9d7dc31e…`).

### 2. Live replay, s74 (04; bot-live-diag's tail_profile + parity.py; deployed eq tree vs the same tree with only belief.py swapped)

| Replay | Searches identical | Errors | Cutoffs | Belief updates at the m11 rebuild (poll 530 = live n394) |
|---|---|---|---|---|
| w2000, m11 + m05 + m07 + m09 (first candidate) | **561/561** | 0 / 0 | 0 / 0 | |
| w2000, m11 (final file) | **73/73** | 0 / 0 | 0 / 0 | eq: one 244 ms update; candidate: one 196 ms update (rebuild completes within its share) |
| forced share 0.04 (~80 ms slice of 2 s), m11 | **73/73** | 0 | 0 | 530 stale (82 ms) → 570 stale (79 ms) → 610 installed (39 ms); both stale decisions searched (no default) and picked the eq tree's action |
| forced share 0.002 (~4 ms), m11, pre-floor diagnostic | 38/73 in order (77 searches vs 73) | 0 | 0 | never finished in-game (58 stale decisions): the reason for the 20 ms floor |

At the deployed w200 the Mac gives the rebuild ~92 ms of a ~185 ms remainder, so a typical ~75 ms rebuild finishes in
the same decision with ~100 ms left to search (non-rebuild search p50 is 37 ms). A longer rebuild, like n394's, goes stale for one
decision and the search still runs. The Mac proof (no default-* at a rebuild in a live battle) is the loop owner's.

### 3. Positive gate (04, `smoke.py`, full pool, our engine)

The opponent (R3a) holds ElectroWizard back until tick 2400. Our player's events rename Witch → "Gravedigger Queen" (no
such card), SkeletonDragons → "Skeleton Dragons" and Knight → "Evo Knight".

| Player | Result | Decisions | Errors / fast errors / panics | Search disabled | belief cutoffs | Rebuilds (stale decisions) | Late card / unknown slot in every posterior state |
|---|---|---|---|---|---|---|---|
| LIVE-K4CW-r16 (unbounded) | terminal, 3601 ticks, hash `9555ae9d…` | 111, all `search` | 0 / 0 / 0 | no | 0 | 5 (0) | yes, from tick 2530 / yes, from tick 150 (126 checks, 0 missing) |
| LIVE-K4L-R-gs-rw-fc-w200-t4-mk1a1 (wall clock, loaded 04) | terminal, 5235 ticks | 161: 104 `search`, 57 `default-it5s2` | 0 / 0 / 0 | no | 0 | 4 (5) | yes, from tick 2430 / yes, from tick 200 (177 checks, 0 missing) |

`~gravediggerqueen` is the only placeholder. The 57 w200 defaults are ordinary searches overrunning 200 ms on a fleet
host that is ~3× slower than the Mac (bot-live-diag's caveat). None is a belief cutoff.

## Reproduction

All on 04/08 under `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4` (`1` for the unbounded smoke), with nice and PYTHONHASHSEED=0. Outputs are in `/mpac/sdicks02/jobs/clasher/cards/belief-robust/`.
- `gate.sh SNAPSHOT OUT`: K4L HEADLINE, LIVE-K4CW-r16 HEADLINE and full-pool res_check rows (08).
- `run-profile4.sh` / `run-profile4-log.sh`: twins of bot-live-diag's `tail/run-profile.sh` with a 4-process lease. The `-log` twin runs `belief_log.py`, which logs every belief update (rebuild completion, stale) without touching the code tree. Candidate tree = a copy of `clasher-bot-livediag-macfp-resume-wint-eq` with only `bot/fullpool/belief.py` swapped.
- `run-smoke.sh SNAPSHOT OUT PLAYER` → `smoke.py` (04).

## Staging the delta on the live (full-pool) tree

The live Mac tree (`fullpool-r1-wint`, = bot-live-diag's `clasher-bot-livediag-macfp-resume-wint-eq`) matches main's
base for `bot/live/player.py` (02252a3d…) and `bot/levels/scope.py`. Its `bot/fullpool/banks.py` differs and isn't
used on the live path, so don't stage it.
- **Required:** `bot/fullpool/belief.py` from **74978f6dd** (r3; `git show 74978f6dd:bot/fullpool/belief.py`), sha256 `127ad256…`.
  It supersedes r2's `d1db6aeb…`, though r2 stays deployable: the full-pool path behaves the same in both, and r3 only adds
  a hook the C56 path uses.
  This file alone carries fixes #3 and #4 on the full-pool path. bot-live-diag's replays above used exactly this one-file swap.
- **Optional, needed for the bounded C56 rollback path:** `bot/live/player.py` from 74978f6dd (sha256 `3cb546b4…`). It needs r3's
  belief.py (`open_world_class(..., weights_work)`). It adds the `belief_stale` decision stat and
  moves the C56 LiveBelief (rollback path) onto the same robust layer.
- **Rollback:** restore the previous belief.py, and player.py if staged.
- **Knob:** `BOT_BELIEF_REBUILD_SHARE` (default 0.5, read per rebuild). Leave it unset.
- **Watch on the first live battles:** `belief_rebuilds` steps with `source` = `search` (not `default-*`), `belief_stale` on at most one decision per
  rebuild (with player.py), and rebuild-decision wall ≤ the cutoff.

## r2: review fixes (Sol review of 6270c382b: REJECT → 26b0ca8d7)

| Finding | Fix | Test (mutation-checked) |
|---|---|---|
| 1 BLOCKER: big single steps overshoot the cutoff (1.84 ms past 0.5 ms; an 8 ms sampler block) | Bounded steps: one sampler draw, one prior deck (preallocated arrays), one 4096-row replay block, one 16k-row cumsum chunk (exact: each chunk restarts from the carry). The replay compacts rows in place in the job's own buffers, with no whole-array concatenation or ~20 MB allocate/free per play. Largest step is now one sampler draw (~0.5 ms on 05). | `test_rebuild_overshoot_bounded`: 400-deck prior (672k states), real clock, 0.5 ms left at every call, ends equal to the synchronous rebuild. Overshoot p50 0.05 / max 0.12 ms on 05, and p50 0.06 / max 0.76 ms on loaded 08 (load ~80); asserts < 1 ms. Also `test_cumsum_work_is_bit_identical_on_float_weights`. |
| 2 share reset within one decision | One cutoff per `update()`, computed at the first rebuild work and shared by every job in that call | `test_one_rebuild_cutoff_per_update` (fake clock): job 1 finishes and job 2 starts within one slice. Before the fix it used ~1.0 job length; now ≤ 0.6 job length + 10 calls. |
| 3 bad `BOT_BELIEF_REBUILD_SHARE` raised every rebuild (3 → search_disabled) | `rebuild_share()`: a malformed value, a non-finite value, or one outside (0, 1] gives 0.5 | `test_rebuild_share_validated` for `bad`, `nan`, `inf`, `-1`, `0`, `5` and empty |
| 4 champion rejection untested | — | `test_second_champion_is_dropped_before_eight_cards`: "Evo Archer Queen" accepted; "Hero Golden Knight" and Monk dropped with 3 cards revealed; neither appears in any state |

**Mutation check** (`reports/cards/belief-robust/mutate.py`, scratch copy): **13/13 mutations killed**. Each reverts one guard or fix (champion guard, 8-card guard, share validation, per-job share, coarse replay, coarse cumsum, coarse prior, stale → TimeoutError, unknown → KeyError, compaction corrupting a queue cell, compaction corrupting a weight, a skipped refill shift, a dropped cumsum carry) and its test fails. A first draft corrupted column 0, which the next refill overwrites, as in the frozen belief; it was replaced by real corruptions.

**Wording:** "byte-for-byte unchanged with no deadline" overstated it. With no deadline, the frozen operations, the arrays and the fixed-timing command hashes are unchanged. The layer adds its own fields and module caches (see "Bounded rebuild").

**r2 gates (rerun on 26b0ca8d7)**

| Gate | Result |
|---|---|
| Unit tests | 31 passed without the runtime (05); 32 passed on the runtime (08, live16402b-r3, incl. test_live's C56 LiveBelief) |
| Default-off parity, fixed timing (08, `gate.sh`; `verify.py before r2`) | **VERIFY_PASS, 23/23 identical**: K4L HEADLINE 12/12, LIVE-K4CW-r16 C56 3/3, mk1a1 LIVE-AB1 4/4, LIVE-K4CW-r16 LIVE-AB1 4/4, 0 bad rows |
| s74 w2000, m11 + m05 + m07 + m09 (04; eq tree vs eq + r2 belief.py) | **561/561 identical**, 0 errors, 0 cutoffs |
| s74-m11 forced share 0.04 (~80 ms slice) | n394 rebuild (poll 530): stale at 530 / 570 / 610 (78.4 / 77.8 / 77.5 ms updates, inside the 80 ms slice) → installed at 650 (19 ms). 73/73 actions identical to eq, 0 errors, 0 cutoffs. The eq tree's synchronous rebuild is one 196–244 ms update. |
| Positive smoke, unbounded LIVE-K4CW-r16 (08) | PASS, same command hash as r1 (`9555ae9d…`): 0 errors, 111/111 search, 5 rebuilds, late card / unknown slot in every state |
| Positive smoke, wall-clock LIVE-K4L-R-gs-rw-fc-w200-t4-mk1a1 (08, load ~80) | PASS: 0 errors, 0 belief cutoffs, never disabled, 4 rebuilds over 12 stale decisions (the fleet is ~3× slower than the Mac, so ~3 decisions per rebuild), late card / unknown slot in every state. 48 of 119 decisions defaulted, all ordinary search overruns on the loaded host. |

bot-live-diag's independent replays (their own eq copy, the deployed `-p4` player name):
- r1: w2000 561/561 identical, share 0.04 73/73.
- r2: w2000 561/561 identical, share 0.04 73/73. The searched step walls at the n394 rebuild were 182 / 169 / 215 / 86 ms
  at poll ticks 531 / 569 / 609 / 650 (installed at 650). The eq tree's were 346 / 95 / 218 ms at 531–609 (650 not
  measured).

## r3: C56 rollback path bounded (Sol review of r2: REJECT on one path)

| Finding | Fix | Test (mutation-checked) |
|---|---|---|
| 1 BLOCKER, C56 LiveBelief only: an unknown reveal computed the catalog card weights (2,925 decks) and `completed_prior()` (scan + full sort) in single steps (~2.5 + ~3.3 ms; 3.15 ms overshoot) | `completed_prior_work()`: 100 catalog decks per step. The top `max_decks` come from sorted runs merged lazily (`heapq.merge`); keys `(-weight, deck)` are unique, so the order equals one full sort. The deck dicts are built in steps of 50. `completed_prior()` is now `_run(completed_prior_work(...))`, one implementation for both paths. Catalog weights: `weights_work`, 100 decks per step, cached per catalog, run by the job before an unknown card's cost is needed. | `test_completed_prior_work_equals_one_step_reference`: equals r2's one-step `completed_prior` on a synthetic 2,925-deck catalog with weight ties, for 4 revealed sets, block 7 and 50, and max_decks 400 and 3000. `test_c56_live_belief_overshoot_bounded`: 2,925-deck catalog, unknown reveal, 0.5 ms left per call, ends equal to the synchronous rebuild. |
| 2 `mutate.py` exited 0 on a survivor; collection / import errors counted as kills | It builds its own scratch copy and requires a passing baseline (else exit 2). KILLED only on pytest exit 1; SURVIVED on exit 0; anything else is ERROR. Exit 1 on any SURVIVED or ERROR. | Self-check: a no-op mutation reports SURVIVED, a syntax-error mutation reports ERROR(rc=4), exit 1 |
| 3 NOTE: the whole-posterior allocation is one step | Kept. `np.zeros` / `np.empty` of the posterior (rows = decks × 1680) are single calls: lazily mapped memory, measured ~µs, and the pages are first touched in the per-deck / per-block steps. Fine at the 400-deck rebuild prior (672k rows, ~8 MB). A much larger rebuild prior would make this one step large. | — |

**Overshoot tests now use this thread's CPU time** as the update clock: they measure the work done past the cutoff,
not preemption on a loaded host (05 ran at load 74–122). Cyclic GC is paused after a collect, because its pauses are
process-wide, not rebuild steps. The live loop does no GC control, so a GC pause can hit any decision.
- r3 measurements on 05, 6 runs: full pool p50 ~0.06 ms, max ≤ 0.49 ms; C56 p50 ~0.05 ms, max ≤ 0.42 ms (assert < 1 ms).
- One earlier wall-clock run on 05 showed 16 / 55 ms outliers. They did not reproduce in 9 reruns with GC on or off, so
  they were most likely host contention.

**Mutation check (r3):** `python reports/cards/belief-robust/mutate.py` gives baseline 23 passed and **17/17 killed** (the 13 r2
mutations, plus C56 completion in one step, C56 catalog weights in one step, C56 merge-key order, C56 top-k off by one).

**r3 gates (rerun on 74978f6dd)**

| Gate | Result |
|---|---|
| Unit tests | 33 passed without the runtime (05); 34 passed on the runtime (08, incl. test_live's C56 LiveBelief) |
| Default-off parity, fixed timing (08, `verify.py before r3`) | **VERIFY_PASS, 23/23 identical** (K4L HEADLINE 12/12, LIVE-K4CW-r16 C56 3/3, mk1a1 LIVE-AB1 4/4, LIVE-K4CW-r16 LIVE-AB1 4/4) |
| s74 w2000, m11 + m05 + m07 + m09 (04; eq + r3 belief.py) | **561/561 identical**, 0 errors, 0 cutoffs; 11 rebuilds, all finished within their share (0 stale) |
| s74-m11 forced share 0.04 | stale at 530 / 570 (78.8 / 78.6 ms, inside the 80 ms slice) → installed at 610 (31 ms); 73/73 identical, 0 errors, 0 cutoffs |
| Smoke, full pool, unbounded LIVE-K4CW-r16 | PASS, same command hash as r1/r2 (`9555ae9d…`) |
| Smoke, full pool, wall-clock LIVE-K4L-R-gs-rw-fc-w200-t4-mk1a1 | PASS: 0 errors, 0 belief cutoffs, never disabled, 3 rebuilds / 3 stale decisions |
| Smoke, **C56 LiveBelief**, unbounded LIVE-K4CW-r16 (explicit `c56` beats the env var) | PASS: LiveBelief, 5 rebuilds, 97/97 search, 0 errors; late card / unknown slot in every state |
| Smoke, **C56 LiveBelief**, wall-clock LIVE-K4CW-r16-w200-t4 | PASS: LiveBelief, 5 rebuilds / 4 stale decisions, 0 belief cutoffs, 0 errors, never disabled; late card / unknown slot in every state. 34 of 138 decisions defaulted, all ordinary search overruns on loaded 08. |

