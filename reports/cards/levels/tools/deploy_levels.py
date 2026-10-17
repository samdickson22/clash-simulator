"""Every card at level 16 through level_battle: accepted, and the level of every body it puts down (formation,
300 ticks of spawner/spell children, then death spawns after forced deaths). Mirror (after a Knight) must give 17.

    (source env-fp.sh) python reports/cards/levels/tools/deploy_levels.py OUT.json [LEVEL]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

OWN_SIDE_SPELLS = {'Log', 'BarbLog', 'RoyalDelivery', 'Heal', 'Rage', 'Clone', 'Mirror'}
FILL = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Valkyrie']


def main():
    out_path = Path(sys.argv[1])
    level = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)
    R = rt.R
    from clasher.arena import Position
    from bot.levels.configs import base_cards
    from bot.levels.match import level_battle, resolve
    towers = ('Tower', 'KingTower', 'PrincessTower')
    out, bad = {}, {}
    for card in base_cards(R.config):
        deck = (['Knight', 'Mirror'] + FILL[1:7]) if card == 'Mirror' else [card] + [c for c in FILL if c != card][:7]
        spec = resolve(dict(cards={0: level}, towers={0: level, 1: level}), [deck, deck])
        spell = str(getattr(R.builder.loader.get_card(card), 'card_type', '') or '').lower() == 'spell'
        x, y = (9.5, 12.5) if card in OWN_SIDE_SPELLS else (3.5, 25.5) if spell else \
            (3.5, 22.5) if card in ('Miner', 'GoblinDrill') else (9.5, 9.5)
        try:
            b = level_battle(1, [deck, deck], R.builder.loader, spec)
            p = b.players[0]
            p.elixir = 10.
            if card == 'Mirror':
                assert b.deploy_card(0, 'Knight', Position(4.5, 10.5))
                p.elixir = 10.
            before = set(b.entities)
            ok = b.deploy_card(0, card, Position(x, y))
            seen = set()

            def look():
                for i, e in b.entities.items():
                    cs = getattr(e, 'card_stats', None)
                    if i not in before and e.player_id == 0 and cs is not None and cs.name not in towers:
                        seen.add((cs.name, getattr(cs, 'level', None)))
            for _ in range(300):
                b.step(); look()
            for _ in range(3):
                for e in list(b.entities.values()):
                    cs = getattr(e, 'card_stats', None)
                    if e.player_id == 0 and cs is not None and cs.name not in towers and getattr(e, 'hitpoints', 0) > 0:
                        e.hitpoints = 0
                for _ in range(40):
                    b.step(); look()
            want = level + 1 if card == 'Mirror' else level
            wrong = sorted(f'{n}@{lv}' for n, lv in seen if lv != want)
            out[card] = dict(ok=bool(ok), bodies=sorted(f'{n}@{lv}' for n, lv in seen), wrong=wrong)
            if not ok or wrong:
                bad[card] = out[card]
        except Exception as ex:
            out[card] = dict(error=repr(ex)[:300])
            bad[card] = out[card]
    summary = dict(cards=len(out), accepted=sum(1 for r in out.values() if r.get('ok')),
                   with_bodies=sum(1 for r in out.values() if r.get('bodies')),
                   bodies=sum(len(r.get('bodies', [])) for r in out.values()), bad=bad)
    out_path.write_text(json.dumps(dict(level=level, summary=summary, cards=out), indent=1))
    print(json.dumps(summary)[:3000])


if __name__ == '__main__':
    main()
