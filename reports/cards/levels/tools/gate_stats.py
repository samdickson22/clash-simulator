"""Gate 2: level-16 stats of our engine vs RoyaleSim 16.402 (and our own level table), plus spawn levels.

    (source env-fp.sh) python reports/cards/levels/tools/gate_stats.py OUT.json

HP: RoyaleSim Battle.unit_hitpoints(card, 16) (every unit a card puts down, down the whole chain) vs the bodies our
Python engine (the true game of play_match) puts down for the same card at level 16: formation, spawner children
(300 ticks), then death spawns (every own body killed). Same at level 11 as a baseline.
Damage: first hit on the enemy's left princess tower (level-16 towers both sides), card played at level L (troops
from our bridge side, spells on the tower), RoyaleSim vs ours, L = 11 and 16.
Spawn levels: native rollouts (per-seat config, LevelConfigs.mixed) vs the Python engine on Tombstone/Witch/
Graveyard/Golem-like cards: every body seen in 700 ticks (owner, name, max HP, damage).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

TOWER_CENTER = (3.5, 25.5)          # the red (seat 1) left princess tower, tiles
NEAR = {'Miner', 'GoblinDrill'}     # troops that may go down on the enemy side: in front of the tower
FILL = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Valkyrie']


def rsim():
    import royalesim
    b = royalesim.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]], calibration_overrides={}, level=11,
                         tower_level=11)
    cat = json.loads(b.catalogue_json())
    return b, {r[0]: i for i, r in enumerate(cat)}, cat


def deck_for(card):
    return [card] + [c for c in FILL if c != card][:7]


def our_bodies(R, card, level, spec_fn):
    """name(lower) -> sorted set of max HP our Python engine shows for `card` at `level` (formation, children, death)."""
    from clasher.arena import Position
    from bot.levels.match import level_battle
    deck = deck_for(card)
    b = level_battle(1, [deck, deck], R.builder.loader, spec_fn(deck, level))
    p = b.players[0]
    p.elixir = 10.
    tower_names = ('Tower', 'KingTower', 'PrincessTower')
    pos = Position(*(TOWER_CENTER if spell(R, card) else (3.5, 22.5) if card in NEAR else (9.5, 9.5)))
    seen = defaultdict(set)
    ok = b.deploy_card(0, card, pos)

    def look():
        for e in list(b.entities.values()):
            cs = getattr(e, 'card_stats', None)
            if e.player_id == 0 and cs is not None and cs.name not in tower_names and getattr(e, 'max_hitpoints', 0):
                seen[cs.name.lower()].add(int(e.max_hitpoints))
    for _ in range(300):
        b.step()
        look()
    for _ in range(4):      # kill every own body; death spawns appear
        for e in list(b.entities.values()):
            cs = getattr(e, 'card_stats', None)
            if e.player_id == 0 and cs is not None and cs.name not in tower_names and getattr(e, 'hitpoints', 0) > 0:
                e.hitpoints = 0
        for _ in range(40):
            b.step()
            look()
    return bool(ok), {k: sorted(v) for k, v in seen.items()}


def spell(R, card):
    return str(getattr(R.builder.loader.get_card(card), 'card_type', '') or '').lower() == 'spell'


def first_hit_ours(R, card, level):
    from clasher.arena import Position
    from bot.levels.match import level_battle, resolve
    deck = deck_for(card)
    spec = resolve(dict(cards={0: {card: level}}, towers={0: 16, 1: 16}), [deck, deck])
    b = level_battle(1, [deck, deck], R.builder.loader, spec)
    b.players[0].elixir = 10.
    start = b.players[1].left_tower_hp
    pos = TOWER_CENTER if spell(R, card) else (3.5, 22.5) if card in NEAR else (3.5, 13.5)
    if not b.deploy_card(0, card, Position(*pos)):
        return None
    for t in range(900):
        b.step()
        hp = b.players[1].left_tower_hp
        if hp != start:
            return [t, round(float(start - hp), 1)]
    return 'none'


def first_hit_rsim(b, ids, card, level):
    from bot.players.royalesim_adapter import royalesim_card, TILE_SUBTILES
    deck = [ids[royalesim_card(c)] for c in deck_for(card)]
    b.set_command_delay_ticks(0, 0)
    b.reset(seed=1, decks=[deck, deck], shuffle=0, start_tick=0, elixir_milli=[10000, 10000], tower_hp=None,
            spawns=[], levels=[[level] + [11] * 7, [11] * 8], tower_levels=[16, 16])
    s = json.loads(b.state_json())
    start = s['players'][1]['tower_hp']
    kind = json.loads(b.catalogue_json())[ids[royalesim_card(card)]][1]
    x, y = (TOWER_CENTER if kind_is_spell(kind) else (3.5, 22.5) if card in NEAR else (3.5, 13.5))
    rows = b.step([(0, 0, round(x * TILE_SUBTILES), round(y * TILE_SUBTILES))], 0)
    if rows[0][1] != 0:
        return None
    for t in range(900):
        b.step([], 1)
        hp = json.loads(b.state_json())['players'][1]['tower_hp']
        if hp != start:
            # engine k order: king, engine-Left, engine-Right; report the largest drop
            return [t, max(a - c for a, c in zip(start, hp))]
    return 'none'


def kind_is_spell(code):
    import royalesim
    return royalesim.CARD_KINDS[code] == 'SPELL'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--cards', default='')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)
    R = rt.R
    from bot.levels.configs import base_cards
    from bot.levels.match import resolve
    from bot.levels.root import tower_stat
    from bot.players.royalesim_adapter import royalesim_card
        import royalesim
    out = {}
    from bot.players.royalesim_vocab import VOCAB_PATH
    out['translator_cards'] = sorted(json.loads(VOCAB_PATH.read_text())['rsim_rows'])
    b, ids, cat = rsim()
    cards = [c for c in base_cards(R.config) if royalesim_card(c) in ids and c != 'Mirror']
    if a.cards:
        cards = a.cards.split(',')
    out['compared_cards'] = cards
    out['ours_only'] = [c for c in base_cards(R.config) if royalesim_card(c) not in ids]
    # towers
    b.reset(seed=1, decks=[[ids['Knight']] * 8] * 2, shuffle=0, start_tick=0, elixir_milli=[6000, 6000],
            tower_hp=None, spawns=[], tower_levels=[16, 16])
    out['towers16'] = dict(rsim_max_hp=json.loads(b.state_json())['players'][0]['tower_max_hp'],
                           ours=[tower_stat('KingTower', 'max_hp', 16), tower_stat('Tower', 'max_hp', 16)],
                           ours_damage=[tower_stat('KingTower', 'damage', 16), tower_stat('Tower', 'damage', 16)])

    def spec_fn(deck, level):
        return resolve(dict(cards={0: level}, towers={0: 16, 1: 16}), [deck, deck])
    hp, dmg = {}, {}
    for card in cards:
        row = {}
        for level in (11, 16):
            try:
                want = b.unit_hitpoints(ids[royalesim_card(card)], level)
            except Exception as ex:
                row[level] = dict(error=f'rsim {ex!r}'[:200])
                continue
            try:
                ok, ours = our_bodies(R, card, level, spec_fn)
            except Exception as ex:
                row[level] = dict(error=f'ours {ex!r}'[:200])
                continue
            units = []
            for role, unit, h in want:
                got = ours.get(str(unit).lower())
                units.append([role, unit, h, got, 'equal' if got and h in got else 'differs' if got else 'unmatched'])
            row[level] = dict(deployed=ok, units=units)
        hp[card] = row
        d = {}
        for level in (11, 16):
            try:
                d[level] = dict(rsim=first_hit_rsim(b, ids, card, level), ours=first_hit_ours(R, card, level))
            except Exception as ex:
                d[level] = dict(error=repr(ex)[:200])
        dmg[card] = d
        print(card, json.dumps(row)[:200], json.dumps(d), flush=True)
    out['hp'], out['damage'] = hp, dmg
    # summaries
    s = defaultdict(lambda: defaultdict(int))
    for card, row in hp.items():
        for level, r in row.items():
            for u in r.get('units', []):
                s[f'hp{level}'][u[4]] += 1
            if 'error' in r:
                s[f'hp{level}']['error'] += 1
    for card, d in dmg.items():
        for level, r in d.items():
            if 'error' in r:
                s[f'dmg{level}']['error'] += 1
            elif isinstance(r['rsim'], list) and isinstance(r['ours'], list):
                s[f'dmg{level}']['equal' if r['rsim'][1] == r['ours'][1] else 'differs'] += 1
            else:
                s[f'dmg{level}']['no hit'] += 1
    out['summary'] = {k: dict(v) for k, v in s.items()}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out['summary']), out['towers16'])


if __name__ == '__main__':
    main()
