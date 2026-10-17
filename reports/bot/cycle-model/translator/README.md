# Cycle-model translator hand-off (for the LIVE LEAD / translator owner; bot/live is theirs, so this is a diff)

## Files

- `cycle-soft-on-drop-features.diff`: the change on top of the translator owner's drop_features patch
  (guardfix/ship-drop-features/drop_features.patch, 256a69ae…). It touches bot/live/translate.py and bot/live/player.py.
- `cycle-soft-full-vs-main.diff`: drop_features plus this change, against origin/main (translate.py at 8fae4f567).
- `a/` = origin/main, `p/` = main + drop_features, `b/` = p + this change (full files).

## What it does

1. **translate.py.** An opponent play that fails `_consistent` is still dropped from the D1 stream, and
   `cycle_conflict_dropped:1` still counts it. When `bot.cyclemodel.belief.enabled()` (env `BOT_CYCLE_MODEL=soft…`),
   the play is also appended to the belief stream `self.events` as
   `PublicEvent(tick, 'card?', name, amount=p_real(self.drop_features(tick, name, x, y)))`. A 9th distinct card is
   never emitted. New counters: `cycle_conflict_soft:1` and `cycle_conflict_ninth:1`.
   - These stay guarded and unchanged: `public_events`, the mirrors, `plays`, `board_card_ok`, own-seat handling.
   - With the env unset, nothing is emitted and the translator behaves exactly as today.
2. **player.py.** `live_belief_class(rt)` builds LiveBelief (the C56 catalog fallback) on top of the cycle model,
   so the catalog rebuild replays hidden plays. The full-pool tree, which the Mac runs, gets the model from
   bot/fullpool/belief.py `planner_belief` (on main with bot/cyclemodel), so no player.py change is needed there.
   `live_belief_class()` without `rt` (bot/fullpool/alias.py) is unchanged.

## Consumers of `info.events` (audit)

| consumer | belief class with the model on | `card?` handled |
|---|---|---|
| bot/live/player.py `_WallMulti.act` (LIVE K4CW / K4L search tier) | FullPoolBelief(CycleBelief) or LiveBelief(CycleBelief) | yes |
| bot/players/search.py, bot/search/players.py (K4L/K4C) | planner_belief → Cycle… | yes |
| bot/fullpool/packet_check.py belief replay | planner_belief → Cycle… | yes (the name check reads `kind == 'card'` only) |
| bot/fullpool/alias.py `events()` (sim harness) | passes non-card kinds through | n/a |
| D1 pollers (it5s2/f1a2, R3a) | read `view.public_events`, never `info.events` | not reached |

- **The same switch drives both sides.** The translator emits `card?` only if `enabled()`, and `enabled()` is exactly
  the condition under which `planner_belief` / `live_belief_class(rt)` install the model. The live loop must set
  `BOT_CYCLE_MODEL` in the process that runs both the translator and the player (LiveSession).
- **`amount`:** only `ability` (elixir) and `collector` read it in the frozen code; both are matched by kind. Nothing
  sums it across kinds (grep: bot/, the stage5 frozen files).
- **ResyncMixin translators** (sim PERC arms, real_replay): a resync rewrites `self.events` from the accepted rows,
  which drops earlier `card?` events, and restarts the player. That is harmless. The deployed live loop uses plain
  LiveTranslator.

## Gate (translator owner)

The 80-battle replay (guardfix/runs.txt): plays changed vs the deployed translator, a Sol video check of every changed
play, and the packet check. The shadow harness runs the real `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1` player over whole
battles with `BOT_CYCLE_MODEL=soft`; expect 0 search errors.

Belief-side outcomes per drop are in the player's belief `cycle_stats` and the LivePlayer decision stats. "Kept" =
real-branch mass p. A conflict is rejected only if no affordable explanation exists.
