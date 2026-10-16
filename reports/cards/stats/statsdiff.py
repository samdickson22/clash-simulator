#!/usr/bin/env python3
"""Cross-check base (level-1) card stats: our gamedata.json against RoyaleSim 16.402.

Run from the repo root with -I (the RoyaleSim file is third-party data, so nothing in its
directory is imported):

    python3 -I reports/cards/stats/statsdiff.py

Writes reports/cards/stats/STATSDIFF.md and prints the counts plus the priority-card rows.
RoyaleSim's data is read at run time from ROYALESIM_CARDS and never copied into the repo;
the report holds only the differing values.
"""
import json
import os
import re
import sys
from collections import Counter, namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'reports/cards/tools'))
from pool import ladder_pool  # noqa: E402

RS_PATH = Path(os.environ.get(
    'ROYALESIM_CARDS',
    '/mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/cards-160402017-20261006.json'))
C56_SRC = REPO / 'bot/players/rext_imitate_replays.py'
OUT_MD = HERE / 'STATSDIFF.md'

PRIORITY = ['GoblinCage', 'SpearGoblins', 'Bomber', 'Tombstone', 'Barbarians', 'BattleRam',
            'MegaMinion', 'BarbarianHut', 'Mortar', 'DartBarrell', 'Witch', 'Pekka',
            'SkeletonWarriors', 'SkeletonDragons']

# Spells whose own damage/duration/flags are not on a top-level areaEffectObjectData block.
# None means no AOE block: the spell's numbers come from its summoned unit (Heal) or it has none (Mirror).
SPELL_AOE_PATH = {
    'Rage': ('summonCharacterData', 'deathAreaEffectData', 'spawnAreaEffectObjectData'),
    'Snowball': ('projectileData',),
    'Heal': None,
    'Mirror': None,
    'MergeMaiden': None,
}
# Spells whose main unit has a non-standard home (ours): see unit_block().
VARIANTS = {'MergeMaiden': ['MergeMaiden_Normal', 'MergeMaiden_Mounted']}

Row = namedtuple('Row', 'card subject field ours rs kind note')

# Field-level caveats: a difference in these is reported as UNCERTAIN, not as a plain mismatch.
UNSURE = {
    ('*', 'death spawn deploy (ms)'):
        'RoyaleSim death_spawn.deploy_time_ms may be a spawn delay, not the spawned unit\'s deploy time',
    ('SkeletonWarriors', 'summon radius'):
        'RoyaleSim gives spawn_radius_milli, not summon_radius_milli; assumed to be the same concept',
    ('DarkMagic', 'hits air'):
        'gamedata AOE flags are false; the laser-ball sub-actions may do the hitting',
    ('DarkMagic', 'hits ground'):
        'gamedata AOE flags are false; the laser-ball sub-actions may do the hitting',
    ('Vines', 'hits air'):
        'gamedata AOE flags are false; the trap sub-actions may do the hitting',
    ('Vines', 'hits ground'):
        'gamedata AOE flags are false; the trap sub-actions may do the hitting',
    ('DarkMagic', 'damage'):
        'RoyaleSim has no damage field for this spell (it sits in the strike action graph)',
    ('MegaKnight', 'spawner number'):
        'gamedata spawnNumber 1 on the MegaKnight block; RoyaleSim models no spawner, so likely not a spawn field',
    ('MegaKnight', 'spawner interval (ms)'):
        'gamedata spawnInterval 1 on the MegaKnight block; RoyaleSim models no spawner, so likely not a spawn field',
    ('GoblinMachine', 'minimum range'):
        'gamedata minimumRange sits in onStartingActionData (the rocket attack); RoyaleSim may not model it as range',
    ('GoblinCurse', 'damage'):
        'RoyaleSim has no damage field for this spell (it sits in the curse action graph)',
}
FIELD_NOTE = {
    'flying height': 'gamedata has no flying field on unit blocks, so this cannot be checked',
    'area damage radius': 'ours uses areaDamageRadius, else the projectile radius (splash)',
    'death spawn deploy (ms)': 'RoyaleSim death_spawn.deploy_time_ms vs our death-spawn unit deployTime',
    'load first hit': 'not in gamedata',
}
NOT_COMPARED = [
    'load_first_hit (RoyaleSim bool; gamedata has no equivalent key on unit blocks)',
    'crown tower damage percent (gamedata and RoyaleSim encode it differently; not in the requested list)',
    'mass, stop/wait timers, pushback, charge and jump fields (not in the requested list)',
    'spell action graphs (spawn lists inside Graveyard, Vines, Clone, etc.)',
]


def first(*vals):
    """First value that is not None (False and 0 count as values)."""
    for v in vals:
        if v is not None:
            return v
    return None


# ----------------------------------------------------------------------------- loading

def load_ours():
    g = json.loads((REPO / 'gamedata.json').read_text())
    spells = {s['name']: s for s in g['items']['spells']}
    assert len(spells) == len(g['items']['spells']), 'duplicate spell names in gamedata.json'
    return spells


def load_rs():
    d = json.loads(RS_PATH.read_text())
    cards = {c['name']: c for c in d['cards']}
    return cards, d['units']


def targets():
    src = C56_SRC.read_text()
    c56 = set(re.findall(r"'(\w+)'", re.search(r'C56 = frozenset\(\((.*?)\)\)', src, re.S).group(1)))
    pool = ladder_pool(REPO / 'gamedata.json')
    kinds = {p['name']: p['kind'] for p in pool}
    names = [p['name'] for p in pool if p['name'] not in c56]
    return names, kinds, {p['name'] for p in pool}


# ----------------------------------------------------------------------------- normalised views

def ours_targets(tt, attacks_ground):
    """(attacks air, attacks ground, buildings only) from our tidTarget and attacksGround keys."""
    if tt is None:
        return None, attacks_ground, None
    return (tt == 'TID_TARGETS_AIR_AND_GROUND', True if attacks_ground is None else attacks_ground,
            tt == 'TID_TARGETS_BUILDINGS')


def ours_unit(node):
    """Normalised stats of one of our unit blocks (summonCharacterData-shaped), or None."""
    if not node:
        return None
    proj = node.get('projectileData') or {}
    ds = node.get('deathSpawnCharacterData') or {}
    sp = node.get('spawnCharacterData') or {}
    onstart = node.get('onStartingActionData') or {}
    air, ground, bldg = ours_targets(node.get('tidTarget'), node.get('attacksGround'))
    return dict(
        name=node.get('name'),
        hitpoints=node.get('hitpoints'),
        damage=first(node.get('damage'), proj.get('damage')),
        hit_speed_ms=node.get('hitSpeed'),
        load_time_ms=node.get('loadTime'),
        speed=node.get('speed'),
        range_milli=node.get('range'),
        minimum_range_milli=onstart.get('minimumRange'),
        sight_range_milli=node.get('sightRange'),
        collision_radius_milli=node.get('collisionRadius'),
        deploy_time_ms=node.get('deployTime'),
        lifetime_ms=node.get('lifeTime'),
        shield_hitpoints=node.get('shieldHitpoints'),
        area_damage_radius_milli=first(node.get('areaDamageRadius'), proj.get('radius')),
        attacks_air=air,
        attacks_ground=ground,
        target_only_buildings=bldg,
        flying_height=None,
        projectile_name=proj.get('name'),
        projectile_speed=proj.get('speed'),
        projectile_radius_milli=proj.get('radius'),
        death_spawn_character=ds.get('name') or node.get('deathSpawnCharacter'),
        death_spawn_count=node.get('deathSpawnCount'),
        death_spawn_deploy_ms=ds.get('deployTime'),
        death_spawn_radius_milli=None,
        death_damage=node.get('deathDamage'),
        spawner_character=sp.get('name'),
        spawner_number=node.get('spawnNumber'),
        spawner_interval_ms=node.get('spawnInterval'),
        spawner_pause_ms=node.get('spawnPauseTime'),
        spawner_start_ms=None,
        spawner_radius_milli=None,
        mana_generate_ms=node.get('manaGenerateTimeMs'),
        mana_collect=node.get('manaCollectAmount'),
        mana_on_death=node.get('manaOnDeath'),
    )


def rs_unit(rec):
    """Normalised stats of a RoyaleSim card or unit record, or None."""
    if not rec:
        return None
    proj = rec.get('projectile') or {}
    ds = rec.get('death_spawn') or {}
    sp = rec.get('spawner') or {}
    mana = rec.get('mana') or {}
    return dict(
        name=rec.get('name'),
        hitpoints=rec.get('hitpoints'),
        damage=rec.get('damage'),
        hit_speed_ms=rec.get('hit_speed_ms'),
        load_time_ms=rec.get('load_time_ms'),
        speed=rec.get('speed'),
        range_milli=rec.get('range_milli'),
        minimum_range_milli=rec.get('minimum_range_milli'),
        sight_range_milli=rec.get('sight_range_milli'),
        collision_radius_milli=rec.get('collision_radius_milli'),
        deploy_time_ms=rec.get('deploy_time_ms'),
        lifetime_ms=rec.get('lifetime_ms'),
        shield_hitpoints=rec.get('shield_hitpoints'),
        area_damage_radius_milli=rec.get('area_damage_radius_milli'),
        attacks_air=rec.get('attacks_air'),
        attacks_ground=rec.get('attacks_ground'),
        target_only_buildings=rec.get('target_only_buildings'),
        flying_height=rec.get('flying_height'),
        projectile_name=proj.get('name'),
        projectile_speed=proj.get('speed'),
        projectile_radius_milli=proj.get('radius_milli'),
        death_spawn_character=ds.get('character'),
        death_spawn_count=ds.get('count'),
        death_spawn_deploy_ms=ds.get('deploy_time_ms'),
        death_spawn_radius_milli=ds.get('radius_milli'),
        death_damage=rec.get('death_damage'),
        spawner_character=sp.get('character'),
        spawner_number=sp.get('number'),
        spawner_interval_ms=sp.get('interval_ms'),
        spawner_pause_ms=sp.get('pause_time_ms'),
        spawner_start_ms=sp.get('start_time_ms'),
        spawner_radius_milli=sp.get('radius_milli'),
        mana_generate_ms=mana.get('generate_time_ms'),
        mana_collect=mana.get('collect_amount'),
        mana_on_death=mana.get('on_death'),
    )


def ours_spell(name, card):
    """Our view of a spell: its AOE block (or projectile), falling back to its summoned unit."""
    path = SPELL_AOE_PATH.get(name, ('areaEffectObjectData',))
    aoe = {}
    if path:
        node = card
        for key in path:
            node = (node or {}).get(key)
        aoe = node or {}
    summon = ours_unit(card.get('summonCharacterData')) or {}
    return dict(
        damage=first(aoe.get('damage'), summon.get('damage')),
        area=first(aoe.get('radius'), summon.get('area_damage_radius_milli')),
        duration=None if name == 'Rage' else aoe.get('lifeDuration'),
        hit_speed=aoe.get('hitSpeed'),
        hits_air=first(aoe.get('hitsAir'), summon.get('attacks_air')),
        hits_ground=first(aoe.get('hitsGround'), summon.get('attacks_ground')),
        buff_time=aoe.get('buffTime'),
    )


def rs_spell(rec):
    """RoyaleSim's view of a spell: its AOE block, falling back to the top-level card fields."""
    sp = rec.get('spell') or {}
    aoe = sp.get('area_effect_object') or {}
    proj = rec.get('projectile') or {}
    return dict(
        damage=first(rec.get('damage'), aoe.get('damage'), proj.get('damage')),
        area=first(rec.get('area_damage_radius_milli'), sp.get('radius_milli'),
                   aoe.get('radius_milli'), proj.get('radius_milli')),
        duration=aoe.get('life_duration_ms'),
        hit_speed=aoe.get('hit_speed_ms'),
        hits_air=first(aoe.get('hits_air'), rec.get('attacks_air')),
        hits_ground=first(aoe.get('hits_ground'), rec.get('attacks_ground')),
        buff_time=first(aoe.get('buff_time_ms'), proj.get('buff_time_ms')),
    )


def unit_block(card):
    """Our main unit block for a troop or building: summonCharacterData, else the IceWizard-style
    spawnDataData of its area effect. None when gamedata carries no unit block (ThreeMusketeers)."""
    node = card.get('summonCharacterData')
    if node:
        return node
    aoe = card.get('areaEffectObjectData') or {}
    return ((aoe.get('onStartingActionData') or {}).get('spawnDataData')) or None


# ----------------------------------------------------------------------------- comparison

SPEC_UNIT = [  # (label, key, kind): base stats, compared for every unit
    ('hitpoints', 'hitpoints', 'num'),
    ('damage', 'damage', 'num'),
    ('hit speed (ms)', 'hit_speed_ms', 'num'),
    ('load time (ms)', 'load_time_ms', 'num'),
    ('speed', 'speed', 'num'),
    ('range', 'range_milli', 'num'),
    ('minimum range', 'minimum_range_milli', 'num'),
    ('sight range', 'sight_range_milli', 'num'),
    ('collision radius', 'collision_radius_milli', 'num'),
    ('deploy time (ms)', 'deploy_time_ms', 'num'),
    ('attacks air', 'attacks_air', 'bool'),
    ('attacks ground', 'attacks_ground', 'bool'),
    ('target buildings only', 'target_only_buildings', 'bool'),
    ('shield hitpoints', 'shield_hitpoints', 'num'),
    ('death damage', 'death_damage', 'num'),
    ('area damage radius', 'area_damage_radius_milli', 'num'),
    ('projectile name', 'projectile_name', 'name'),
    ('projectile speed', 'projectile_speed', 'num'),
    ('projectile radius', 'projectile_radius_milli', 'num'),
    ('flying height', 'flying_height', 'num'),
]
SPEC_MAIN_EXTRA = [  # only on a card's own unit (lifetime, death spawn, spawner, mana)
    ('lifetime (ms)', 'lifetime_ms', 'num'),
    ('death spawn character', 'death_spawn_character', 'name'),
    ('death spawn count', 'death_spawn_count', 'num'),
    ('death spawn deploy (ms)', 'death_spawn_deploy_ms', 'opt'),
    ('death spawn radius', 'death_spawn_radius_milli', 'num'),
    ('spawner character', 'spawner_character', 'name'),
    ('spawner number', 'spawner_number', 'num'),
    ('spawner interval (ms)', 'spawner_interval_ms', 'num'),
    ('spawner pause (ms)', 'spawner_pause_ms', 'num'),
    ('spawner start (ms)', 'spawner_start_ms', 'num'),
    ('spawner radius', 'spawner_radius_milli', 'num'),
    ('mana generate (ms)', 'mana_generate_ms', 'num'),
    ('mana collect', 'mana_collect', 'num'),
    ('mana on death', 'mana_on_death', 'num'),
]
SPEC_SPELL = [
    ('damage', 'damage', 'num'),
    ('radius', 'area', 'num'),
    ('duration (ms)', 'duration', 'num'),
    ('hit speed (ms)', 'hit_speed', 'num'),
    ('hits air', 'hits_air', 'bool'),
    ('hits ground', 'hits_ground', 'bool'),
    ('buff time (ms)', 'buff_time', 'num'),
]
SPEC_CARD = [  # card-level fields; both dicts use these keys
    ('elixir', 'elixir', 'num'),
    ('count', 'count', 'num'),
    ('summon radius', 'summon_radius', 'num'),
    ('summon deploy delay (ms)', 'summon_deploy_delay', 'num'),
]


def compare(ours, rs, kind):
    """None when the two agree; else MISMATCH, ABSENT (gamedata lacks it), or RS-ABSENT.
    kind 'opt' compares only when RoyaleSim has a value (its absence is no evidence either way)."""
    if kind == 'opt':
        return None if rs is None else compare(ours, rs, 'num')
    if kind == 'name':
        if ours is None and rs is None:
            return None
        if ours is None:
            return 'ABSENT'
        if rs is None:
            return 'RS-ABSENT'
        return None if ours.casefold() == rs.casefold() else 'MISMATCH'
    if kind == 'bool':
        if ours is None:
            return 'ABSENT' if rs else None
        return None if bool(ours) == bool(rs) else 'MISMATCH'
    # numbers: None and 0 both mean "no value"
    if ours in (None, 0) and rs in (None, 0):
        return None
    if ours is None:
        return 'ABSENT'
    if rs in (None, 0):
        return 'RS-ABSENT'
    return None if ours == rs else 'MISMATCH'


def fmt(v):
    if v is None:
        return '—'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    return str(v)


def add_rows(rows, card, subject, spec, ours, rs):
    """Compare each spec field of one view pair and append a Row per disagreement."""
    for label, key, kind in spec:
        o = ours.get(key) if ours else None
        r = rs.get(key) if rs else None
        kind_out = compare(o, r, kind)
        if kind_out is None:
            continue
        caveat = UNSURE.get((card, label)) or UNSURE.get(('*', label))
        if caveat:
            kind_out, note = 'UNCERTAIN', caveat
        else:
            note = FIELD_NOTE.get(label, '')
        rows.append(Row(card, subject, label, fmt(o), fmt(r), kind_out, note))


def card_check(name, kind, card, rec, rs_units, ours_spells, unparsed):
    """All rows for one card."""
    rows = []
    elixir_ours = card.get('manaCost')
    # gamedata omits summonNumber on single-unit cards: 1 when the card has a unit or is a spell.
    single = kind == 'spell' or unit_block(card) is not None
    count_ours = first(card.get('summonNumber'), 1 if single else None)
    ours_card = dict(elixir=elixir_ours, count=count_ours,
                     summon_radius=card.get('summonRadius'),
                     summon_deploy_delay=card.get('summonDeployDelay'))
    if rec is None:
        rows.append(Row(name, 'card', 'in RoyaleSim', '—', 'missing', 'ABSENT', 'no RoyaleSim card record'))
        return rows

    spawn_only = rec.get('summon_radius_milli') is None and not rec.get('spawner')
    rs_card = dict(elixir=rec.get('elixir'), count=rec.get('count'),
                   summon_radius=first(rec.get('summon_radius_milli'),
                                       rec.get('spawn_radius_milli') if spawn_only else None),
                   summon_deploy_delay=rec.get('summon_deploy_delay_ms'))
    add_rows(rows, name, 'card', SPEC_CARD, ours_card, rs_card)

    if kind == 'spell':
        ours = ours_spell(name, card)
        rsv = rs_spell(rec)
        add_rows(rows, name, 'card', SPEC_SPELL, ours, rsv)
        summon_rs = ((rec.get('spell') or {}).get('summon') or {}).get('character')
        summon_ours = (card.get('summonCharacterData') or {}).get('name')
        add_rows(rows, name, 'card', [('summon character', 'name', 'name')],
                 {'name': summon_ours}, {'name': summon_rs})
        if summon_rs and summon_rs in rs_units:
            add_rows(rows, name, f'summon {summon_rs}', SPEC_UNIT,
                     ours_unit(card.get('summonCharacterData')), rs_unit(rs_units[summon_rs]))
    else:
        block = unit_block(card)
        if block is None:
            unparsed.append(name)
            return rows
        main = ours_unit(block)
        rs_main = rs_unit(rec)
        add_rows(rows, name, 'card', [('summon character', 'name', 'name')],
                 {'name': main['name']}, {'name': rec.get('summon_character')})
        add_rows(rows, name, 'card', SPEC_UNIT + SPEC_MAIN_EXTRA, main, rs_main)

        ds_rs = (rec.get('death_spawn') or {}).get('character')
        if main['death_spawn_character'] and ds_rs and ds_rs in rs_units:
            sub_block = block.get('deathSpawnCharacterData')
            if sub_block:
                add_rows(rows, name, f'death spawn {ds_rs}', SPEC_UNIT,
                         ours_unit(sub_block), rs_unit(rs_units[ds_rs]))
            else:
                rows.append(Row(name, f'death spawn {ds_rs}', 'unit block', '—', 'present', 'ABSENT',
                                'gamedata names the death spawn but has no unit block for it'))
        sp_rs = (rec.get('spawner') or {}).get('character')
        if main['spawner_character'] and sp_rs and sp_rs in rs_units:
            add_rows(rows, name, f'spawner {sp_rs}', SPEC_UNIT,
                     ours_unit(block.get('spawnCharacterData')), rs_unit(rs_units[sp_rs]))
        morph_block = block.get('spawnPathfindMorphData')
        morph_rs = (rec.get('spawn_pathfind') or {}).get('morph')
        if morph_block and morph_rs and morph_rs in rs_units:
            add_rows(rows, name, f'morph {morph_rs}', SPEC_UNIT,
                     ours_unit(morph_block), rs_unit(rs_units[morph_rs]))
    for variant in VARIANTS.get(name, []):
        v_card = ours_spells.get(variant, {})
        if variant in rs_units and v_card.get('summonCharacterData'):
            add_rows(rows, name, f'variant {variant}', SPEC_UNIT,
                     ours_unit(v_card['summonCharacterData']), rs_unit(rs_units[variant]))
        else:
            rows.append(Row(name, f'variant {variant}', 'unit block', '—', fmt(variant in rs_units),
                            'ABSENT', 'variant not found in gamedata or RoyaleSim'))
    return rows


# ----------------------------------------------------------------------------- report

def name_coverage(rs_cards, ours_spells, pool_names):
    rs_not_ours = sorted(n for n in rs_cards if n not in ours_spells)
    pool_not_rs = sorted(n for n in pool_names if n not in rs_cards)
    ours_not_rs = sorted(n for n in ours_spells if n not in rs_cards and n not in pool_names)
    return rs_not_ours, pool_not_rs, ours_not_rs


def md_table(rows):
    out = ['| Subject | Field | Ours (gamedata.json) | RoyaleSim 16.402 | Kind | Note |',
           '|---|---|---|---|---|---|']
    for r in rows:
        out.append(f'| {r.subject} | {r.field} | {r.ours} | {r.rs} | {r.kind} | {r.note} |')
    return out


def main():
    names, kinds, pool_names = targets()
    ours_spells = load_ours()
    rs_cards, rs_units = load_rs()

    order = list(PRIORITY)
    assert all(n in names for n in order), 'a priority card is not among the 66 targets'
    check = order + sorted(n for n in names if n not in order)
    kinds_all = dict(kinds)

    per_card, unparsed, missing = {}, [], []
    for n in check:
        if n not in ours_spells:
            missing.append(n)
            continue
        rows = card_check(n, kinds_all[n], ours_spells[n], rs_cards.get(n), rs_units,
                          ours_spells, unparsed)
        per_card[n] = rows

    clean = [n for n, rows in per_card.items() if not rows]
    flagged = [n for n, rows in per_card.items() if rows]
    kind_counts = Counter(r.kind for rows in per_card.values() for r in rows)
    rs_not_ours, pool_not_rs, ours_not_rs = name_coverage(rs_cards, ours_spells, pool_names)

    ordered = [n for n in order if n in flagged] + sorted(n for n in flagged if n not in order)
    lines = [
        '# Card stats cross-check: gamedata.json vs RoyaleSim 16.402',
        '',
        'Generated by `reports/cards/stats/statsdiff.py` (run with `python3 -I`). Base level-1 values only. '
        'Only differing values are listed; RoyaleSim\'s data file is not copied into the repo.',
        '',
        '## Summary',
        '',
        f'- Cards checked: {len(per_card)}, the ladder pool cards outside C56; all 14 priority cards are among them.',
        f'- Fully matching (every compared field present on both sides and equal): **{len(clean)}** of {len(per_card)}.',
        f'- Cards with at least one row: {len(flagged)}.',
        f'- Rows: MISMATCH {kind_counts["MISMATCH"]}, ABSENT {kind_counts["ABSENT"]}, '
        f'RS-ABSENT {kind_counts["RS-ABSENT"]}, UNCERTAIN {kind_counts["UNCERTAIN"]}.',
        f'- Not parsed (no unit block in gamedata, so unit stats were not compared): '
        f'{", ".join(unparsed) if unparsed else "none"}.',
        f'- Missing from gamedata.json: {", ".join(missing) if missing else "none"}.',
        '',
        '### Name coverage',
        '',
        f'- RoyaleSim cards with no gamedata spell entry: {", ".join(rs_not_ours) if rs_not_ours else "none"}.',
        f'- Ladder pool cards with no RoyaleSim card: {", ".join(pool_not_rs) if pool_not_rs else "none"}.',
        f'- Other gamedata spell entries (not in the pool) with no RoyaleSim card: '
        f'{", ".join(ours_not_rs) if ours_not_rs else "none"}.',
        '',
        '## Kinds',
        '',
        '- **MISMATCH**: both sides have a value and they differ.',
        '- **ABSENT**: gamedata has no such field; RoyaleSim has a non-zero value.',
        '- **RS-ABSENT**: RoyaleSim has no such value; gamedata has a non-zero one.',
        '- **UNCERTAIN**: the two sources may not mean the same thing (note says why); treat as a question, not a fix.',
        '',
        '## Conventions and assumptions',
        '',
        '- Both sides are level-1 base values (RoyaleSim\'s unified level 1, calibration.json STAT_BASE_LEVEL). '
        'Level-1 agreement is visible on the cards that match fully, e.g. Pekka 1469 HP on both sides.',
        '- Distances are millitiles (1000 = 1 tile) on both sides; times are ms; speeds are the raw Supercell '
        'speed column on both sides; hit speed -1 means "no repeat" on both.',
        '- Ranged damage: a unit with a projectile has its damage on the projectile (RoyaleSim uses the same rule '
        'for damage_source). Our `damage` falls back to `projectileData.damage`.',
        '- Area damage radius: our `areaDamageRadius`, else `projectileData.radius` (splash), compared with '
        'RoyaleSim\'s `area_damage_radius_milli`.',
        '- Attacks air/ground/buildings-only come from our `tidTarget` (TID_TARGETS_*) and `attacksGround`. '
        'A block with neither `tidTarget` nor `attacksGround` (for example GoblinCage, Tombstone, BarbarianHut) '
        'shows RoyaleSim\'s `attacks_ground` as ABSENT.',
        '- Counts: our missing `summonNumber` means 1 (RoyaleSim count 1).',
        '- Spawner: our `spawnNumber` / `spawnInterval` / `spawnPauseTime` on the unit block and `spawnCharacterData` '
        'as the spawned unit. Spawner start time and spawn radius are not in gamedata.',
        '- Death spawn: our `deathSpawnCount` and `deathSpawnCharacterData` (the unit\'s own deployTime is compared '
        'as "death spawn deploy", flagged UNCERTAIN).',
        '- Spells: damage, radius, duration and hit flags come from the AOE block (projectileData for Snowball; '
        'Rage uses its spawnAreaEffectObjectData); Heal\'s damage and radius come from its HealSpirit projectile.',
        '- Sub-units (death spawns, spawners, morphs, variants, spell summons) are compared on base stats only, '
        'with the same rules, against RoyaleSim\'s unit records of the same name.',
        '- Not compared: ' + '; '.join(NOT_COMPARED) + '.',
        '- Flying: gamedata has no flying field on unit blocks, so `flying height` is reported as ABSENT where '
        'RoyaleSim has a non-zero value.',
        '- gamedata.json\'s META.canonicalization records deliberate calibration overrides away from the admitted '
        'source (Barbarian HP 270 to 280, IceSpirits/FireSpirits/ElectroSpirit HP 90 to 84, Wallbreakers projectile '
        '137 to 110, Goblinstein doctor 36 to 53, Goblin_Stab 47 to 49, Rascals deploy delay). They are not treated '
        'as errors here; any that still differ from RoyaleSim appear in the table like any other value.',
        '',
        '## Mismatch table',
        '',
        'Priority cards first (in the order requested), then the rest alphabetically. '
        'Cards with no rows are listed at the end.',
        '',
    ]
    for n in ordered:
        rows = per_card[n]
        tag = ' (priority)' if n in PRIORITY else ''
        lines += [f'### {n}{tag}: {len(rows)} row{"s" if len(rows) != 1 else ""}', '']
        lines += md_table(rows)
        lines.append('')
    lines += ['## Fully matching', '', ', '.join(sorted(clean)) if clean else 'none', '']
    if unparsed:
        lines += ['## Not parsed', '', f'{", ".join(unparsed)}: gamedata has no unit block; '
                  'card-level fields only.', '']
    OUT_MD.write_text('\n'.join(lines))

    print(f'checked {len(per_card)} cards; fully matching {len(clean)}; with rows {len(flagged)}')
    print('row kinds:', dict(kind_counts))
    print('unparsed:', unparsed, '| missing:', missing)
    print('RS cards not in gamedata:', rs_not_ours)
    print('pool cards not in RS:', pool_not_rs)
    print('wrote', OUT_MD)
    print()
    for n in PRIORITY:
        if n in per_card and per_card[n]:
            print(f'[{n}]')
            for r in per_card[n]:
                print(f'  {r.subject} | {r.field} | ours={r.ours} | rs={r.rs} | {r.kind}')


if __name__ == '__main__':
    main()
