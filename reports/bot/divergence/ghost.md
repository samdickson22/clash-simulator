# Ghost (native 26000050) divergence: diagnosis

Episode v4-phase-a-1975100700 (train/validation). Truth = native `objects.jsonl` per tick; ours = `clasher` engine. 1000 mt = 1 tile. Scripts: `/mpac/sdicks02/jobs/clasher/bot-div/ghost/` on 127x03.
In this episode, Ghost unit-ticks within 1/4 tile (250 mt): **9.8%** baseline (2303 scored); global 21.3% covers all fixtures.

## (1) What differs

**Movement direction (not speed).** Speed matches: truth covers 533 mt in 6 ticks (~89 mt/tick), ours 90. Direction does not.
- Truth x by tick: 629:5499, 641:5257, 647:5065, 653:5047, 659:5362, 671:5198, 683:4667, 689:4636. Lateral swings of 200-400 mt.
- Ours is a straight line toward the target. tick 683: truth (4667,8231), ours (5123,8683), 642 mt apart.

**Targeting.** Both pick side-1 PrincessTower 5000004 at (3500,25500). Truth `targetEntityKey` at 690 = [1,-2,5000004]; ours `Tower:4` from tick 640. Target choice matches; the path does not.

**Invisibility.** Truth (rich-objects, sampled): invisible at 617 and 690; visible at 905 (`inv=0`); invisible at 925 (`inv=1`) while standing at (5885,23162); visible at 980.
Ours (probe of entity state): `_stealth_until` = invisible until ~832, set to 0 at ~840, and still 0 through 960. Ours never re-hides in the window where truth does.

**HP.** Totals match by 980 (1210 to 552 in both). Timing differs:
- Ours: -109 at 864, 880, 896, 912 (princess shots every 16 ticks while visible); -222 at 944.
- Truth: -109 at 872 and 884; no hits 925-940 (invisible); -218 by 980.
Hits stop in truth during invisibility; they never stop in ours.

## (2) Likely root cause (ranked, with confidence)

A. **Lateral movement (cause unknown).** No unit lies within 1.5 tiles of the truth Ghost in ticks 617-760 (objects.jsonl scan), so body pushback does not explain the zigzag. Our hover rule (`src/clasher/battle.py:2760-2766`) ignores bodies and steers straight, and nothing in our code models the jitter. The native mechanism is unknown.

B. **Re-hide timer (weak evidence it matters here).** `src/clasher/cards/royal_ghost.py:29-49` freezes the fade timer while the target is in attack reach. That mode comes from `src/clasher/balance.py:729-731` (`buffWhenNotAttackingUseAttackRange: True`), which is not in gamedata. Gamedata has only `buffWhenNotAttackingTime: 2000`. Scratch test (monkeypatch, no engine edit) with the flag forced False: this episode drops 9.8% -> 7.8%, but Ghost 5000108 drops 48 -> 0 unit-ticks. The flag is therefore not the cause here, and its effect is mixed. Keep it until native evidence says otherwise.

C. **Reveal timing (unknown).** `royal_ghost.py:51-53` sets visible on attack start (called from `src/clasher/entities.py:3899-3901`). Truth reveal instant is not sampled; our hits land ~8 ticks earlier than truth's, which may be this.

Stale doc: `reports/cards/royal-ghost.md` says 1800 ms and "NOT IMPLEMENTED". Gamedata says 2000 ms, and the mechanic exists in `royal_ghost.py`.

## (3) Fix sketch and verification

1. **Get dense truth visibility.** `rich-objects.jsonl.gz` has ~113 ticks per episode; Ghost visibility is known at 5 of them. Capture `visibilityState` per tick for Ghost to pin the reveal tick (on attack start vs on hit) and the re-hide tick (2000 ms after last attack start vs last hit).
2. **Movement.** Truth `raw.targetX/targetY` is already in `objects.jsonl` every tick. Test candidate movement models (waypoint or flow-field steering, lateral jitter) against truth before editing `battle.py:2760`.
3. **Verify.** `PYTHONPATH=src:. .venv/bin/python bot/fidelity/debug_traj.py v4-phase-a-1975100700 Ghost 6`, and a variant of the 9.8% count (`variant.py`) over all Ghost fixtures in `bot-fid-r2`. Accept a change only if the within-1/4 rate rises on the Ghost fixtures overall, not just here.

**Unknown / not verified:** the native lateral movement cause; reveal/re-hide timing; whether 5000108's sensitivity to the attack-range flag reflects a real rule.
