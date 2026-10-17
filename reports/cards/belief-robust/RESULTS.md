# Belief robustness: explicit C56 flag, unknown cards / late reveals, deadline-bounded rebuild

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
- With no deadline the rebuild runs synchronously, as today (fixed-timing hashes unchanged).
- With a deadline, the rebuild is a resumable job: sampler draws, a chunked twin of the frozen `__init__` (bit-identical, tested), and s1's chunked replay transaction. Priors are cached per revealed set.
- The job may use `BOT_BELIEF_REBUILD_SHARE` (default 0.5) of the time left to the deadline, at least 20 ms and never past the deadline. On the Mac's 192 ms that's ~96 ms, more than a typical ~75 ms rebuild.
- If unfinished, `update` returns with `stale=True`. The decision searches on the previous posterior instead of falling back to the default, and the job resumes next decision. LivePlayer stats gain `belief_stale`.
- Option (b), off the decision path, was rejected: a thread would contend for the GIL with the search's Python parts, and doing the work on idle polls would delay the next frame of the live loop.

## Tests (`bot/fullpool/test_belief_robust.py`; run on the real frozen + s1 belief sources, no runtime)

| Required test | Test(s) | Result |
|---|---|---|
| Late reveal: a card first seen after N rebuilds is in all later posterior states | `test_late_reveal_after_several_rebuilds` (5 rebuilds, all earlier reveals present after each) | pass |
| Unknown name: no exception, valid 8-card deck structure, search not disabled | `test_unknown_alias_and_valid_engine_sample`, `test_impossible_reveals_are_dropped_not_fatal`, `test_live_belief_layer`; positive smoke below (search not disabled) | pass |
| Tight deadline: decision returns in time, rebuild completes later and is consistent | `test_rebuild_suspends_resumes_and_includes_new_late_event` (stale posterior usable; completes over many decisions and equals the synchronous twin), `test_unknown_under_deadline_equals_synchronous`, `test_expired_deadline_does_no_rebuild_work`, `test_chunked_init_exactly_matches_frozen` | pass |
| Explicit C56 flag beats the env var | `test_explicit_c56_beats_environment` | pass |

Results:
- 05, no runtime: `pytest bot/fullpool/test_belief_robust.py bot/fullpool/test_fullpool.py` → 20 passed.
- 04, runtime live16402b-r3: the same plus `bot/live/test_live.py::test_live_belief_survives_off_prior_decks` (the C56 LiveBelief through the new layer) → 21 passed.

## Gates

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
- **Required:** `bot/fullpool/belief.py` from 6270c382b (`git show 6270c382b:bot/fullpool/belief.py`), sha256 `08b635a7…`.
  This file alone carries fixes #3 and #4 on the full-pool path. bot-live-diag's replays above used exactly this one-file swap.
- **Optional:** `bot/live/player.py` from 6270c382b (sha256 `39f68453…`). It adds the `belief_stale` decision stat and
  moves the C56 LiveBelief (rollback path) onto the same robust layer.
- **Rollback:** restore the previous belief.py, and player.py if staged.
- **Knob:** `BOT_BELIEF_REBUILD_SHARE` (default 0.5, read per rebuild). Leave it unset.
- **Watch on the first live battles:** `belief_rebuilds` steps with `source` = `search` (not `default-*`), `belief_stale` on at most one decision per
  rebuild (with player.py), and rebuild-decision wall ≤ the cutoff.
