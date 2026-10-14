# Divergence: Goblinstein (native 26000099) spawn and formation

Read-only diagnosis; no engine code changed. Scratch on 127x03: `/mpac/sdicks02/jobs/clasher/bot-div/goblinstein/`.

## 1. What differs

115 fixtures, 70,074 truth unit-ticks. Ours w250 = 6,874 (9.8%). 10,389 truth unit-ticks have no paired unit on our side.

- **Monster is placed 3.5 tiles forward of the tap; native places it on the tap.** (932 hp card, 2385 hp at lvl 11)
  - ep 1975100707, side 1, tap (0.5, 22.5), exec 1008: truth (499, 22499); ours (499, 18999).
  - ep 1975100707, side 1, tap (14.5, 18.5), exec 2558: truth (14500, 18499); ours (14500, 14999).
- **Doctor is off by 1 tile laterally.** (282 hp card, 721 hp at lvl 11)
  - ep 1975100707, side 0, tap (3.5, 13.5), exec 369: truth (4499, 10000); ours (3499, 10000).
- **Timing and HP are right.** First-frame ticks match (369, 1009, 2558); hp 2385 / 721 match.
- **One tap dropped entirely.** ep 1975100715, side 1, tap (4.5, 28.5), exec 5898: native spawns monster (4499, 28499)
  and doctor (5499, 31750); ours has `deploy.dropped = 1` and zero units. Cause not traced: unknown.
- **Native rule from truth** (all 328 spawn rows in t1-trainval, `gob_truth_survey.py`):
  - Monster on the tap tile (|Δ| ≤ 0.001) in 146 rows.
  - Doctor at (+1 if tap x < 9 else −1, +3.5 for side 1 / −3.5 for side 0): 144 rows, no exceptions.
  - Doctor clipped at the top edge: y 32.0 → 31.75 (same as our clamp, battle.py:1959-1961).

## 2. Root cause (most likely)

Goblinstein (summonNumber 1, summonCharacterSecondCount 1, summonRadius 3500) goes through the mixed-swarm path:

- `src/clasher/battle.py:1603` `has_front_back` → `_spawn_front_back_formation` (battle.py:1687).
- battle.py:1704 places the primary with `mixed_ring_offset(0, 1, 1, 3.5, ...)`.
- `src/clasher/formations.py:10` `formation_offset`, count=1 and secondary=1: slot_count = 2, primary `angle = 90`
  (branch at formations.py:122; primary_arc_offset set at :98; `base_angle = 0` at :105). That yields (0, ∓3.5).
- The doctor gets angle 270, giving (0, ±3.5) with x = cos·r = 0. No ±1 lateral term exists.

Native: primary on the anchor; secondary at (±1 toward centre, 3.5 behind). |(1, 3.5)| = 3.64, so this is not a
3.5-radius ring. The mechanism behind the ±1 is **unknown**. RoyaleSim 15.535 matches truth on this card
(its source is a compiled .so, not readable here).

## 3. Fix sketch and verification

Fix: in `formation_offset` special-case count=1 with secondary_count=1: primary = (0, 0); secondary =
(sign(9 − tap_x) × 1.0 tile, 3.5 tiles behind). Keep it data-driven and cite this measurement in a comment.
Check whether the sign follows x or lane: `lane_flip_x` (formations.py:53, applied at :148) is the candidate.
Lane vs x is **unknown** from this data.

Verify (127x03, nice):

```
cd /mpac/sdicks02/repos/clasher-bot && PYTHONPATH=src:. nice -n 15 .venv/bin/python -m bot.fidelity.run \
  --engine clasher --data /mpac/sdicks02/repos/clasher-bot-data/t1-trainval \
  --split /mpac/sdicks02/repos/clasher-bot-data/t1-split.json --ids bot/fidelity/c56_native_ids.json \
  --out /mpac/sdicks02/jobs/clasher/bot-div/goblinstein/after.json \
  --episodes v4-phase-a-1975100707,v4-phase-a-1975100715,v4-phase-a-1975100712,v4-phase-a-1975100740
```

Pass: Goblinstein w250 rises toward RoyaleSim's 89% on these episodes; `debug_traj.py <ep> Goblinstein 6` shows
monster Δ ≤ 0.25 tile at first frame. The run's flags are from run.py:143-151; the `--split` path is my assumption
(debug_traj uses the same file).

## Open items

- Why our engine drops ep 1975100715's tap at exec 5898: unknown; trace `deploy_card` (battle.py:1218-1260).
- Whether the ±1 lateral follows lane or tap x: unknown.
- Whether other champion mixed swarms share the monster-on-tap rule: not checked.
