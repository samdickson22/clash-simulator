# Native vs scalar mechanics checks (2026-09-28)

These are opened development checks only. There is no fitting, no ledger or readiness claim, and no training. All runs are level 11 on native 15.535.86 with the captured ruleset `daa58b28…`. Instances: read-only `emulator-5580` (26789) and `emulator-5582` (26790), one job per instance. Rendering was off during each run and back on afterwards; both instances ended ready and paused with `renderSuppressed=false` and zero snapshot handles.

## Method

`nm_lib.py` reuses the pattern of `scripts/trace_native_public_prefix.py` and `collect-giant-log-river-controls.py`:

1. Configure the snapshot template with custom decks.
2. Take the first seed in the fixed range 1609280001+ whose initial hands contain the needed cards. There is no outcome selection.
3. Seed scalar `BattleState` from the native initial deck, hand, cycle and elixir.
4. Issue identical commands on both engines: native `replay-schedule-card` at tick+1, scalar `deploy_card` at the tick.
5. Step both engines one tick at a time. Native frames are ordinary plus rich (target key, shield, attack timeline and projectile source), read over a `session-v1` connection.

Scenario 5 and 1c trigger their test deployment relative to each engine's own tower-destruction tick.

Verdict scale:

- **match**
- **small**: within a few ticks, or under 5% HP
- **consequential**: changes the winner or a target, or more than 0.5 s of tower fire

## Results (`summary.json`, produced by `make_summary.py`)

| # | Scenario | Native | Scalar | Verdict |
|---|---|---|---|---|
| 1 | King wake-up + Zap (`s1_*`, `s1b_*`) | First shot 80 ticks after the activating hit. A Zap cast in the first 3.3 s adds **0**. A Zap in the last 0.7 s adds 3–10 ticks. | **Before repair: +10–11 ticks (0.5–0.55 s)** for every early Zap. After repair: exact (±1 baseline) early, at most +4 ticks late. | Before: consequential and systematic. **Repaired**; now small. |
| 1c | Ice Spirit freeze on the waking King (`s1c_*`) | 770 (control 748) | 770 before and after the repair (the triage T1 variant gives 768) | match |
| 2 | Dark Prince shield (`s2_shield.json`) | The shield (240) absorbs the whole breaking hit: Knight 202 on 38 remaining shield leaves HP at 1200, and Fireball on a full shield leaves HP at 1200. The Knight dies at tick 319 with the Dark Prince on 190 HP. | Identical per tick (xy/HP difference 0) | match. Fireball contact is 1 tick earlier in scalar. |
| 3 | Hog + 3 Skeletons (`s3_hog_skeletons.json`) | Unblocked: 7 hits (2219), first hit at 204. Blocked (4 placements): 2 hits (634), first hit 4–9 ticks later. The Hog only ever targets the Princess Tower. | Tick-exact Hog path, HP, hits and skeleton deaths | match |
| 4 | Log pushback (`s4_log_pushback.json`) | Giant pushed a maximum of 0.906 tiles, net 0.750. Ice Golem: 0.920 / 0.868. Hog: 1.453 / −0.107. 268 damage each. | Tick-exact | match |
| 5 | Lane after a Princess falls (`s5_lane_after_tower.json`) | Fall at 668 or 456. Knight, Giant and Hog in the lane, the pocket, and the centre go to the King; a Hog at x=8.5 goes to the surviving Princess. | Identical fall ticks, target sequences and 10-tick paths, and the same King first shot | match |

Side finding (not consequential): native accepts an out-of-zone pocket placement at y=10.5 by snapping it to y=11.5 (`icespirit_pocket_early*` variants). Scalar rejects it. Masked actions only emit legal tiles, so the policy never sends such a placement.

## Repair (scenario 1)

Native evidence (`s1b_zap_sweep_pre_repair.json`, 32 Zap timings; rich King timeline) shows two things:

- The King's wake-up delay keeps running under stun.
- The last part behaves like an ordinary loaded attack. It is retained, not advanced, while paused. The native King reacquires at thaw, then loads for 0.45 s.

Candidate fixes, by maximum error in ticks over the sweep:

| Model | Max error (ticks) | Ice Spirit case |
|---|---|---|
| Main source before repair | 11 | exact |
| Triage proposal T1 (both clocks run under stun) | 8 | −2 |
| Applied T2 (only the 3.3 s delay runs under stun) | 4 | exact |
| A 3.55/0.45 split | ≤1 | — |

The 3.55/0.45 split was not applied because it changes data constants and torch parity.

- `src/clasher/entities.py:4673-4690` (`Building._update_active_combat`): during the Zap/Freeze pause, advance `activation_delay_remaining` and nothing else.
- New `tests/test_native_king_wakeup_stun.py`, with fixture `tests/fixtures/native_king_wakeup_stun_15_535_86.json` (built by `build_king_fixture.py`): 10 tests. Six fail under an in-memory revert.
- `tests/test_match_rules.py`: the Freeze test is renamed and re-pinned to the retained first-hit phase (launch 0.7 s after thaw). A native Zap covering the end of the wake-up implies about 0.5 s after thaw, so this is a small, extrapolated difference.
- Suites run: `test_match_rules.py`, `test_enabled_troop_interactions.py`, `test_native_*.py`, `test_building_footprint.py` and `test_enabled_spell_interactions.py`, **2320 passed** (`pytest-suites.log`). Torch tower-combat/spawn and idle-fast-forward: 38 passed, 24 skipped.

## Remaining concerns

- A King residual of up to 4 ticks when a Zap lands in the last 0.7 s of the wake-up.
- The torch simulator still runs both activation clocks under stun (T1-like). It was not changed; it is not the pilot backend.
- Only one seed per scenario and level 11. Ice Spirit freeze could only be placed at the end of the wake-up.

Files: `s*.py` (scenario drivers), `*_pre_repair.json` (scalar before the repair, same native data), `s1b_zap_sweep_models_only.json` (scalar models after the repair), `explore_probe.py` (the initial format probe).
