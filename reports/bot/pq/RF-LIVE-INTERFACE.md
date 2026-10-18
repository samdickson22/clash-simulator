# RF (root fidelity) on the LIVE path: what the memory-route translator must supply

RF1 (RF1-RESULTS.md): vs LIVE-K4CW-r16-fp +0.085 [+0.030, +0.140] pooled over L16 + account (account row +0.135
[+0.060, +0.205]); Goblin Barrel answer share 0.055 → 0.137. Owner decision 2026-10-18: ship (see RF1 decision below).

## Player side (already on main)
Live name: add the token `RF` to the live K4L body, e.g. `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-wint`
(bot/search/lopp_fast.py live_options). It installs `search.root_fn = FidelityRoot(rt.R).root` (bot/search/rootfid.py).
**Without extras it is exactly R.root** (no change, no cost), so the token is safe to deploy before the translator
supplies extras, but it only helps once it does.

## Translator side (LIVE owner; bot/live is not changed by this owner)
`info` passed to the player must carry `extras`: use `bot.players.royalesim_translate.public_information_class()(tick,
seat, packet, own, events, extras=...)` instead of `fair_player.Information(...)` in bot/live/translate.py (line ~1034).
`extras` is a dict keyed by `bot.players.royalesim_translate.extra_key(row)` for each packet entity row
(= (argmax(row[4:9]), row[2] > .5, float32 x, float32 y) as stored in the packet), value a dict with any of:

| key | for | meaning (live source) |
|---|---|---|
| `aim` | spells in flight (Goblin Barrel, Fireball, Arrows, Rocket, Royal Delivery …) and shots | absolute destination (x, y) in tiles, OUR engine frame (team 0 at the bottom; un-rotated) — memory: the projectile's target |
| `flown` | spells in flight | ticks since cast (20/s) — memory, or ticks since first seen |
| `deploy` | troops/buildings deploying | remaining deploy ticks — memory deploy timer, or the deploy-clock detector |
| `stun` | troops/buildings | remaining stun/freeze ticks — memory |
| `live` | deployed troops/buildings | ticks since its deploy clock reached 0 (track per object address: first tick seen with deploy 0, or first-seen tick + remaining deploy) |

Fields missing for a body keep the old default (aim one tile ahead / at (0,0), deploy 0, stun 0, age 1000 ms, fresh
spawner). All of these are public (visible on screen, or the client's public unit data); nothing about the opponent's
hand, elixir or deck is read. Hasty-CR cap: positions/identities/levels are within it; flight targets, deploy and stun
timers need the parity table's sign-off (memory-reader rule) — fill only the fields the cap allows.
Sim reference implementation: bot/players/royalesim_translate.py `_rows` (per-seat uid tracking).

## Install
One change per restart, at a forced break between battles. Rollback: drop `-RF` from the live name.
