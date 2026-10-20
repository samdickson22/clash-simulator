"""simfid-20261020 live-fidelity fixes in the full-pool engine (engine-cards/py), run in a subprocess.

The full-pool engine is a separate `clasher` package, so each check runs in its own interpreter with
PYTHONPATH=engine-cards/py/src and CLASHER_ROOT at a root holding engine-cards' gamedata.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def run_engine_cards(tmp_path, code):
    root = tmp_path / 'root'
    root.mkdir()
    for name, src in (('gamedata.json', REPO / 'engine-cards/py/gamedata.json'),
                      ('hitboxes.json', REPO / 'hitboxes.json'), ('pyproject.toml', REPO / 'pyproject.toml'),
                      ('decks.json', REPO / 'decks.json')):
        (root / name).symlink_to(src)
    env = dict(os.environ, PYTHONPATH=str(REPO / 'engine-cards/py/src'), CLASHER_ROOT=str(root),
               PYTHONDONTWRITEBYTECODE='1')
    out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, cwd=tmp_path,
                         check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


LAYOUT = r'''
import json, random
from collections import deque
from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop
card, radius = {card!r}, {radius!r}
b = BattleState(rng=random.Random(0))
deck = [card, 'Knight', 'Archers', 'Zap', 'Fireball', 'Cannon', 'Musketeer', 'Valkyrie']
p = b.players[0]
p.deck, p.hand, p.cycle_queue, p.elixir = list(deck), list(deck[:4]), deque(deck[4:]), 10
stats = b.card_loader.get_card(card)
if radius is not None:
    stats.summon_radius = radius        # the 16.402 table's value (bot/cards/balance_overlay.py)
before = set(b.entities)
assert b.deploy_card(0, card, Position(9.5, 10.5))
units = [e for k, e in b.entities.items() if k not in before and isinstance(e, Troop)]
print(json.dumps(sorted((round(e.position.x - 9.5, 2), round(e.position.y - 10.5, 2)) for e in units)))
'''


def test_skeletons_ring_not_tighter_than_collision_radius_under_16402_table(tmp_path):
    # 16.402: SummonRadius 400 < Skeleton collision radius 500 -> the live client's 500 ring.
    got = run_engine_cards(tmp_path, LAYOUT.format(card='Skeletons', radius=0.4))
    assert got == [[-0.5, -0.29], [0.0, 0.58], [0.5, -0.29]]


def test_skeletons_ring_unchanged_on_15535_table(tmp_path):
    # 15.535 (T1): SummonRadius 700 > collision radius: the serialized radius stands.
    got = run_engine_cards(tmp_path, LAYOUT.format(card='Skeletons', radius=None))
    assert got == [[-0.7, -0.4], [0.0, 0.81], [0.7, -0.4]]


def test_royal_hogs_line_keeps_its_one_unit_radius(tmp_path):
    # A SummonWidth line: the 1-unit radius (no depth stagger) is not raised to the 0.6 collision radius.
    got = run_engine_cards(tmp_path, LAYOUT.format(card='RoyalHogs', radius=None))
    assert len(got) == 4 and len({y for _, y in got}) == 1
