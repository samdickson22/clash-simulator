"""RoyaleSim helpers shared by the adapter: card names and our action id -> RoyaleSim command.

The adapter itself (see reports/bot/rsim-adapter/NOTES.md):
- royalesim_vocab.py      RoyaleSim rows -> our tokens/kinds/static columns (royalesim_vocab.json)
- royalesim_translate.py  state_json -> fair public view (v5 packet + own HUD + public events)
- royalesim_match.py      the match loop (X4S harness semantics) and RsimMatch
- royalesim_opponents.py  RoyaleGym built-in opponents and our scripted bot as Players
- royalesim_run.py / royalesim_summary.py / royalesim_crosscheck.py  N games, summary, engine cross-check
"""
from __future__ import annotations

TILE_SUBTILES = 18000          # 1 tile = 1000 millitiles x SUBTILE_PER_MILLITILE 18
BOARD_W, BOARD_H = 18, 32

# C56 name -> RoyaleSim catalogue name (cards-15535.1): 53 identical, 3 renamed.
RENAMED = {'Archers': 'Archer', 'IceGolem': 'IceGolemite', 'IceSpirit': 'IceSpirits'}


def royalesim_card(name):
    return RENAMED.get(name, name)


def our_card(name):
    inverse = {v: k for k, v in RENAMED.items()}
    return inverse.get(name, name)


def action_to_command(action, seat):
    """Our own-frame action id -> (team, hand_slot, x_subtiles, y_subtiles).

    Mirrors DiscreteTileActionSpace.decode_action (src/clasher/rl/action_space.py:88-113):
    seat 1 flips the tile (17-x, 31-y); the tap is the tile centre (+0.5). Both engines
    put team/seat 0 (blue) at the bottom: king (9, 3) tiles; red king (9, 29).
    Hand slots must refer to the same card in both engines: build the view's own hand
    from RoyaleSim `players[seat].hand` in slot order so slot indices coincide.
    """
    slot, tile = divmod(int(action), 576)
    cx, cy = tile % BOARD_W, tile // BOARD_W
    if seat == 1:
        cx, cy = BOARD_W-1-cx, BOARD_H-1-cy
    return seat, slot, round((cx+.5)*TILE_SUBTILES), round((cy+.5)*TILE_SUBTILES)
