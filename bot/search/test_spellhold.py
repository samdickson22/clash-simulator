"""Spell-hold term (token sh<N>): penalty, composition with res, idempotency.
    PYTHONHASHSEED=0 .venv/bin/python -m pytest -q bot/search/test_spellhold.py"""
from types import SimpleNamespace

import numpy as np

from bot.search import spellhold


def fake(hand):
    names = ['<pad>', '<unk>'] + hand
    builder = SimpleNamespace(card_name_for_token_id=lambda t: names[t] if 1 < t < len(names) else None)
    config = {'cards': {'Zap': {'units': []}, 'Fireball': {'units': [[{'class': 'Projectile'}]]},
                        'Giant': {'units': [[{'class': 'Troop'}]]}, 'Cannon': {'units': [[{'class': 'Building'}]]}}}
    R = SimpleNamespace(config=config, costs={'Zap': 2.0, 'Fireball': 4.0, 'Giant': 5.0, 'Cannon': 3.0}, builder=builder)
    obs = SimpleNamespace(hand_ids=np.asarray([2, 3, 4, 5, 0]))
    core = SimpleNamespace(info=SimpleNamespace(packet=SimpleNamespace(observation=obs)))
    return SimpleNamespace(R=R), core


def test_penalty_spells_only_and_composition():
    rt, core = fake(['Zap', 'Giant', 'Fireball', 'Cannon'])
    spellhold.install(rt, core, 0.005)
    pen = core.reserve
    assert abs(pen(0 * 576 + 100, 5.) - 0.010) < 1e-12        # Zap: 0.005 * 2
    assert pen(1 * 576 + 100, 5.) == 0.                        # Giant (troop)
    assert abs(pen(2 * 576 + 100, 5.) - 0.020) < 1e-12        # Fireball: 0.005 * 4
    assert pen(3 * 576 + 10, 5.) == 0.                         # Cannon (building)
    assert pen(2304, 5.) == 0. and pen(2402, 5.) == 0.         # waits
    spellhold.install(rt, core, 0.005)                          # idempotent
    assert core.reserve is pen
    core.reserve = lambda a, e: 0.1 if a < 2304 else 0.       # res re-installed (new function): wrap once more
    spellhold.install(rt, core, 0.005)
    assert abs(core.reserve(0, 5.) - 0.110) < 1e-12 and core.reserve(576, 5.) == 0.1
    assert core.reserve(2304, 5.) == 0.


def test_spell_rule_is_data():
    rt, _ = fake(['Zap', 'Giant', 'Fireball', 'Cannon'])
    assert spellhold.spell_cards(rt.R) == {'Zap', 'Fireball'}
