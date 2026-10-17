# Cycle model: Mac package spec (DRAFT; ships only after the sim A/B and the translator owner's live gate pass;
check with the LIVE LEAD before any copy)

The Mac has run a tree from main ≥ 2fa5d496 since the full-pool switch (reports/bot/fullpool/BUNDLE.md). The live
player is LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1[-res] with the full-pool belief (`BOT_BELIEF_PRIOR=fullpool:…`), so the
model enters through bot/fullpool/belief.py `planner_belief`.

## Files

| file | source | note |
|---|---|---|
| bot/cyclemodel/__init__.py, belief.py, preal.py | main 3db832568 or later | runtime |
| bot/fullpool/belief.py | main 3db832568 or later | 2-line hook (`wrap`); with the env unset it is today's class |
| bot/live/translate.py, bot/live/player.py | the LIVE LEAD's tree + reports/bot/cycle-model/translator/*.diff | translator owner's call (drop_features + `_soft_conflict`; `live_belief_class(rt)`) |
| (optional) P(real) v1 json | reports/bot/cycle-model/preal-v1.json (after sample 2) | `BOT_CYCLE_PREAL=<path>`; default v0 is in code |

Not needed on the Mac: ab.py, parity.py, replay80.py, test_cycle.py (fleet tools).

## Environment (the LiveSession process: translator and player)

```
BOT_CYCLE_MODEL=soft          # eps 0.1, slack 2, cap 400000 (defaults); unset = off (rollback)
BOT_CYCLE_PREAL=<json>        # optional; unset = v0
```

## Checks before switching on

1. Session-start manifest guard: sha256 of the files above against the commit (mac-deploy drift rule).
2. Mac copy == main command hashes on the deterministic twins with `BOT_CYCLE_MODEL=soft` (bot/cyclemodel/parity.py,
   a few LIVE-AB1 cases). They must equal `off` (perfect observation).
3. Timing: the first conflict of a battle costs up to ~110 ms on loaded fleet hosts (RESULTS). On the Mac, check that
   the cutoff rate and p95 stay inside the gate (cutoff ≤ 10%, p95 ≤ 60 ms) on the shadow replay.
4. Rollback: unset `BOT_CYCLE_MODEL`. The translator then emits nothing new and the belief class is today's.
