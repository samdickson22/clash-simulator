# bot/players

This directory wraps the frozen Clasher players behind one interface, `Player.act(PublicView) -> Decision`. Design, numbers and sources: `reports/bot/inventory/INVENTORY.md`.

```python
from bot.players.runtime import Runtime          # bootstraps the import path and verifies native/v1/R3a pins (~15 s CPU)
from bot.players.ours import play_match, x4s_setup
from bot.players.policy import PolicyPlayer
from bot.players.search import SearchPlayer

rt = Runtime()                                    # CLASHER_BOT_RUNTIME overrides the runtime root
case = x4s_setup(rt, index=0, base=<fresh seed bank>)
bot = SearchPlayer(rt, mode='unbounded', default='R3a')   # deterministic KU/K4S; or mode='budget', budget=N
result = play_match(rt, {case['seat']: bot, 1-case['seat']: PolicyPlayer(rt, 'v1')},
                    seed=case['seed'], decks=case['decks'])
```

Run through `bot/players/run.sh`. It applies nice 19, pins one core and sets single-threaded BLAS/torch with `PYTHONHASHSEED=0`:

```
bot/players/run.sh -m bot.players.smoke --ticks 1200 --budget 48
```

Players:
- `PolicyPlayer(rt, 'v1')`: the v1 imitation policy.
- `PolicyPlayer(rt, 'R3a')`: the R3a student alone.
- `SearchPlayer(..., mode='unbounded'|'budget'|'wall', default='R3a'|'v1')`: K4S or K4 W-screen8 search.

RoyaleSim: the same Players play inside RoyaleSim 0.1.34 through `royalesim_match.play_match` (same decks, lag, cadence;
the search still plans on our Rust engine). N games: `bot/players/run.sh -m bot.players.royalesim_run --a search:budget:48 --b v1 --range 0 N --out OUT.jsonl`.
Design, field map, gaps and smoke numbers: `reports/bot/rsim-adapter/NOTES.md`.
