"""live16402 balance overlay: runtime gamedata + RoyaleSim 16.402.19 stats -> patched gamedata + receipt.

    python3 -I bot/cards/balance_overlay.py --gamedata RUNTIME/gamedata.json \
        --rs16 RS/data/derived/cards-160402017-20261006.json --rs15 RS/data/derived/cards-15.535.json \
        --calibration <repo>/gamedata.json --out DIR/gamedata.json --receipt R.json [--detail D.json]

The slots (card, body, field) and their unit conversions are the comparer's (reports/cards/stats/statsdiff.py and
balance_size.py: same units on both sides except crown-tower damage, which gamedata stores as a delta from 100).
This module adds where each slot lives in gamedata, so the RoyaleSim value can be written back. Rules (BOT LEAD):

1. A slot where ours and RoyaleSim 16.402 differ (the comparer's MISMATCH) takes the 16.402 value, C56 included.
2. Calibration: where the calibration gamedata (main's root gamedata.json, measured on the 15.535 client) differs
   from the runtime at a slot, it is used only when RoyaleSim's 15.535 and 16.402 tables agree on that slot (the
   field did not change between versions); otherwise the 16.402 value wins. Every such slot is in the receipt.
3. UNCERTAIN cells (the comparer's caveats, blank 16.402 crown cells, crown values off the card's own damage object)
   and RoyaleSim defaults (`defaults_applied`, not a cell) are never applied; ours stays, and they are listed.
Name and boolean fields (projectile/summon names, attacks-air flags that gamedata encodes in tidTarget) are
structural and not applied; slots whose value gamedata lacks (ABSENT) are not created. Detection-action tier buffs
(Void's laser tiers) are matched to RoyaleSim's strike_area tiers by action kind and buff name (tier_slots). HOLD lists slots kept on
purpose, with the reason. After the slot pass, each unit/projectile change is propagated to the other base copies of
the same named block in pool cards that still hold the old value (BarbLog's Barbarian, Furnace's FireSpirits), so
one unit has one stat set. Output is deterministic (sorted traversal, input JSON format kept); the receipt holds
sha256s and counts and names only; per-slot values go to --detail (keep that next to the output, not in git).
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / 'reports/cards/stats', REPO / 'reports/cards/tools'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import statsdiff as sd  # noqa: E402  (field mapping)
import balance_size as bs  # noqa: E402  (crown + second-unit rules; adds its UNSURE rows to sd.UNSURE)
from pool import KIND  # noqa: E402

GENERATOR = 'bot/cards/balance_overlay.py'
VERSION = 2  # 2: pass 3 (detection-action tier buffs)

# Slots kept on purpose although RoyaleSim differs: (card, subject, field) -> reason.
HOLD = {
    ('DarkMagic', 'card', 'elixir'):
        'Void: gamedata manaCost 3 vs RoyaleSim 5 in BOTH the 15.535 and 16.402 tables, so not a 16.402 balance '
        'change but a source disagreement; elixir drives the elixir model and the action costs. Verify on the live '
        'card before changing',
}
# Boolean/name fields: gamedata encodes them structurally (tidTarget, attacksGround, block names).
STRUCTURAL = ('bool', 'name')
# RoyaleSim record keys behind the unit view keys, for `defaults_applied` (a default is no cell).
RS_DEFAULT_KEYS = {'crown_tower_damage_percent', 'area_damage_radius_milli', 'flying_height', 'shield_hitpoints'}


@dataclass
class Loc:
    """Where one slot's value lives: container[key] (path is for the receipt)."""
    container: dict
    key: str
    path: str


@dataclass
class Slot:
    card: str
    subject: str
    field: str
    kind: str                       # comparer kind: num / opt / bool / name
    ours: object
    rs16: object
    loc: Loc | None
    unsure: str | None = None
    rs_default: bool = False        # RoyaleSim value is a default it applied, not a cell
    crown_raw: object = None        # crown slots: our raw delta
    rs15: object = None
    cal: object = None
    action: str = ''
    value: object = None
    reason: str = ''
    extra: dict = field(default_factory=dict)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


# ----------------------------------------------------------------------------- locations (mirror statsdiff views)

def _put(locs, name, cont, key, path):
    if isinstance(cont, dict) and cont.get(key) is not None:
        locs[name] = Loc(cont, key, f'{path}/{key}')


def unit_locs(node, path):
    """Locations of sd.ours_unit's numeric fields in one unit block (same precedence as ours_unit)."""
    locs = {}
    if not node:
        return locs
    proj = node.get('projectileData')
    ppath = f'{path}/projectileData'
    ds = node.get('deathSpawnCharacterData')
    onstart = node.get('onStartingActionData')
    for name, key in (('hitpoints', 'hitpoints'), ('hit_speed_ms', 'hitSpeed'), ('load_time_ms', 'loadTime'),
                      ('speed', 'speed'), ('range_milli', 'range'), ('sight_range_milli', 'sightRange'),
                      ('collision_radius_milli', 'collisionRadius'), ('deploy_time_ms', 'deployTime'),
                      ('lifetime_ms', 'lifeTime'), ('shield_hitpoints', 'shieldHitpoints'),
                      ('death_damage', 'deathDamage'), ('death_spawn_count', 'deathSpawnCount'),
                      ('spawner_number', 'spawnNumber'), ('spawner_interval_ms', 'spawnInterval'),
                      ('spawner_pause_ms', 'spawnPauseTime'), ('mana_generate_ms', 'manaGenerateTimeMs'),
                      ('mana_collect', 'manaCollectAmount'), ('mana_on_death', 'manaOnDeath')):
        _put(locs, name, node, key, path)
    if node.get('damage') is not None:
        _put(locs, 'damage', node, 'damage', path)
    else:
        _put(locs, 'damage', proj, 'damage', ppath)
    if node.get('areaDamageRadius') is not None:
        _put(locs, 'area_damage_radius_milli', node, 'areaDamageRadius', path)
    else:
        _put(locs, 'area_damage_radius_milli', proj, 'radius', ppath)
    _put(locs, 'minimum_range_milli', onstart, 'minimumRange', f'{path}/onStartingActionData')
    _put(locs, 'projectile_speed', proj, 'speed', ppath)
    _put(locs, 'projectile_radius_milli', proj, 'radius', ppath)
    _put(locs, 'death_spawn_deploy_ms', ds, 'deployTime', f'{path}/deathSpawnCharacterData')
    return locs


def resolve(root, path):
    """'/a/b[2]/c' -> (container, key) inside root (keys may hold dots, e.g. 'nextAction.spawnDataData')."""
    parts = [p for p in path.split('/') if p]
    node = root
    for part in parts[:-1]:
        m = re.fullmatch(r'(.*?)((?:\[\d+\])*)', part)
        node = node[m.group(1)]
        for idx in re.findall(r'\[(\d+)\]', m.group(2)):
            node = node[int(idx)]
    return node, parts[-1]


# ----------------------------------------------------------------------------- slots (mirror balance_size.card_rows)

def _spec_slots(out, card, subject, spec, ours, rs, locs, rs_rec=None):
    for label, key, kind in spec:
        o = ours.get(key) if ours else None
        r = rs.get(key) if rs else None
        out.append(Slot(card, subject, label, kind, o, r, locs.get(key),
                        rs_default=bool(rs_rec) and key in RS_DEFAULT_KEYS
                        and key in (rs_rec.get('defaults_applied') or [])))


def _rs_unit_key(rs_units, name):
    return next((k for k in rs_units if k.casefold() == name.casefold()), None)


def card_slots(name, kind, card, rec, rs_units, spells):
    """Every comparer slot of one card against one RoyaleSim table (rec None -> no slots)."""
    out = []
    if rec is None:
        return out
    block = sd.unit_block(card)
    single = kind == 'spell' or block is not None
    ours_card = dict(elixir=card.get('manaCost'), count=sd.first(card.get('summonNumber'), 1 if single else None),
                     summon_radius=card.get('summonRadius'), summon_deploy_delay=card.get('summonDeployDelay'))
    spawn_only = rec.get('summon_radius_milli') is None and not rec.get('spawner')
    rs_card = dict(elixir=rec.get('elixir'), count=rec.get('count'),
                   summon_radius=sd.first(rec.get('summon_radius_milli'),
                                          rec.get('spawn_radius_milli') if spawn_only else None),
                   summon_deploy_delay=rec.get('summon_deploy_delay_ms'))
    locs = {}
    for k, key in (('elixir', 'manaCost'), ('count', 'summonNumber'), ('summon_radius', 'summonRadius'),
                   ('summon_deploy_delay', 'summonDeployDelay')):
        _put(locs, k, card, key, '')
    _spec_slots(out, name, 'card', sd.SPEC_CARD, ours_card, rs_card, locs)

    if kind == 'spell':
        aoe_path = sd.SPELL_AOE_PATH.get(name, ('areaEffectObjectData',))
        aoe = {}
        if aoe_path:
            node = card
            for key in aoe_path:
                node = (node or {}).get(key)
            aoe = node or {}
        apath = '/' + '/'.join(aoe_path) if aoe_path else ''
        summon = unit_locs(card.get('summonCharacterData'), '/summonCharacterData')
        slocs = {}
        _put(slocs, 'damage', aoe, 'damage', apath)
        if 'damage' not in slocs and 'damage' in summon:
            slocs['damage'] = summon['damage']
        _put(slocs, 'area', aoe, 'radius', apath)
        if 'area' not in slocs and 'area_damage_radius_milli' in summon:
            slocs['area'] = summon['area_damage_radius_milli']
        if name != 'Rage':
            _put(slocs, 'duration', aoe, 'lifeDuration', apath)
        _put(slocs, 'hit_speed', aoe, 'hitSpeed', apath)
        _put(slocs, 'buff_time', aoe, 'buffTime', apath)
        _spec_slots(out, name, 'card', sd.SPEC_SPELL, sd.ours_spell(name, card), sd.rs_spell(rec), slocs)
        summon_rs = ((rec.get('spell') or {}).get('summon') or {}).get('character')
        _spec_slots(out, name, 'card', [('summon character', 'name', 'name')],
                    {'name': (card.get('summonCharacterData') or {}).get('name')}, {'name': summon_rs}, {})
        if summon_rs and summon_rs in rs_units:
            _spec_slots(out, name, f'summon {summon_rs}', sd.SPEC_UNIT, sd.ours_unit(card.get('summonCharacterData')),
                        sd.rs_unit(rs_units[summon_rs]), summon, rs_units[summon_rs])
    elif block is not None:
        bpath = '/summonCharacterData' if card.get('summonCharacterData') else \
            '/areaEffectObjectData/onStartingActionData/spawnDataData'
        main = sd.ours_unit(block)
        _spec_slots(out, name, 'card', [('summon character', 'name', 'name')], {'name': main['name']},
                    {'name': rec.get('summon_character')}, {})
        _spec_slots(out, name, 'card', sd.SPEC_UNIT + sd.SPEC_MAIN_EXTRA, main, sd.rs_unit(rec),
                    unit_locs(block, bpath), rec)
        ds_rs = (rec.get('death_spawn') or {}).get('character')
        if main['death_spawn_character'] and ds_rs and ds_rs in rs_units and block.get('deathSpawnCharacterData'):
            sub = block['deathSpawnCharacterData']
            _spec_slots(out, name, f'death spawn {ds_rs}', sd.SPEC_UNIT, sd.ours_unit(sub), sd.rs_unit(rs_units[ds_rs]),
                        unit_locs(sub, f'{bpath}/deathSpawnCharacterData'), rs_units[ds_rs])
        sp_rs = (rec.get('spawner') or {}).get('character')
        if main['spawner_character'] and sp_rs and sp_rs in rs_units:
            sub = block.get('spawnCharacterData')
            _spec_slots(out, name, f'spawner {sp_rs}', sd.SPEC_UNIT, sd.ours_unit(sub), sd.rs_unit(rs_units[sp_rs]),
                        unit_locs(sub, f'{bpath}/spawnCharacterData'), rs_units[sp_rs])
        morph = block.get('spawnPathfindMorphData')
        morph_rs = (rec.get('spawn_pathfind') or {}).get('morph')
        if morph and morph_rs and morph_rs in rs_units:
            _spec_slots(out, name, f'morph {morph_rs}', sd.SPEC_UNIT, sd.ours_unit(morph), sd.rs_unit(rs_units[morph_rs]),
                        unit_locs(morph, f'{bpath}/spawnPathfindMorphData'), rs_units[morph_rs])
    for variant in sd.VARIANTS.get(name, []):
        v_card = spells.get(variant, {})
        if variant in rs_units and v_card.get('summonCharacterData'):
            _spec_slots(out, name, f'variant {variant}', sd.SPEC_UNIT, sd.ours_unit(v_card['summonCharacterData']),
                        sd.rs_unit(rs_units[variant]),
                        unit_locs(v_card['summonCharacterData'], f'<{variant}>/summonCharacterData'), rs_units[variant])

    # second unit (balance_size.second_rows)
    node = card.get('summonCharacterSecondData') or None
    rs2 = rec.get('second_summon') or {}
    _spec_slots(out, name, 'card', [('second unit', 'name', 'name')], {'name': (node or {}).get('name')},
                {'name': rs2.get('character')}, {})
    locs2 = {}
    _put(locs2, 'count', card, 'summonCharacterSecondCount', '')
    _spec_slots(out, name, 'card', [('second unit count', 'count', 'num')],
                {'count': card.get('summonCharacterSecondCount')}, {'count': rs2.get('count')}, locs2)
    if node and rs2.get('character'):
        key = _rs_unit_key(rs_units, rs2['character'])
        if key:
            _spec_slots(out, name, f'second unit {key}', sd.SPEC_UNIT, sd.ours_unit(node), sd.rs_unit(rs_units[key]),
                        unit_locs(node, '/summonCharacterSecondData'), rs_units[key])

    # crown-tower damage percent (balance_size.crown_rows)
    found = bs.find_crown(card)
    ours = bs.effective_crown(found[1]) if found else 100
    rs = rec.get('crown_tower_damage_percent')
    crown = Slot(name, 'card', 'crown tower damage percent', 'num', ours, rs, None, crown_raw=found[1] if found else None)
    if found:
        cont, key = resolve(card, found[0])
        crown.loc = Loc(cont, key, found[0])
    if rs == 100 and bs.rs_crown_blank(rec) and ours != 100:
        crown.unsure = 'RoyaleSim 16.402.19 crown cell is blank (loads as 100), no measured value'
    elif found and found[0] not in bs.OWN_CROWN['spell' if kind == 'spell' else 'unit'] \
            and sd.compare(ours, rs, 'num') == 'MISMATCH':
        crown.unsure = 'crown value is not on the card\'s own damage object'
    out.append(crown)
    for s in out:
        if s.loc is not None and s.field != 'crown tower damage percent':
            assert s.loc.container[s.loc.key] == s.ours, (s.card, s.subject, s.field, s.loc.path)
        if s.unsure is None and s.field != 'crown tower damage percent':
            s.unsure = sd.UNSURE.get((name, s.field)) or sd.UNSURE.get(('*', s.field))
    return out


def verdict(s):
    """The comparer's row kind for a slot (None = agree)."""
    return sd.compare(s.ours, s.rs16, s.kind)


# ----------------------------------------------------------------------------- decision (rules 1-3)

def decide(s):
    """Fill s.action / s.value / s.reason. Actions: apply, calibration, keep-*, skip-*, agree."""
    v = verdict(s)
    cal_slot = s.cal is not None and s.cal != s.ours and s.kind not in STRUCTURAL
    if v is None and not cal_slot:
        s.action = 'agree'
        return s
    if (s.card, s.subject, s.field) in HOLD:
        s.action, s.reason = 'skip-hold', HOLD[(s.card, s.subject, s.field)]
        return s
    if s.unsure and (v is not None or cal_slot):
        s.action, s.reason = 'skip-uncertain', s.unsure
        return s
    if s.kind in STRUCTURAL:
        s.action, s.reason = 'skip-structural', 'name/boolean field: encoded structurally in gamedata'
        return s
    if s.rs_default:
        s.action, s.reason = 'skip-uncertain', 'RoyaleSim value is a default it applied (defaults_applied), no cell'
        return s
    if cal_slot:
        if s.rs15 is not None and s.rs16 is not None and s.rs15 == s.rs16:
            s.action, s.value = 'calibration', s.cal
            s.reason = 'calibration applied: RoyaleSim 15.535 == 16.402 on this field'
        elif s.rs16 not in (None, 0):
            s.action, s.value = 'apply', s.rs16
            s.reason = 'calibration superseded: RoyaleSim 15.535 != 16.402 (or 15.535 missing), 16.402 wins'
        else:
            s.action, s.reason = 'keep-calibration-unconfirmed', 'calibration not applied: RoyaleSim has no 16.402 value'
            return s
        if s.value == s.ours:
            s.action = 'agree'
        elif s.loc is None:
            s.action, s.reason = 'skip-no-location', s.reason + '; gamedata has no such key'
        return s
    if v != 'MISMATCH':
        s.action = 'skip-absent' if v == 'ABSENT' else 'keep-rs-absent'
        return s
    if s.loc is None:
        s.action, s.reason = 'skip-no-location', 'the comparer value is a gamedata default (no key to write)'
        return s
    s.action, s.value = 'apply', s.rs16
    return s


def raw_value(s):
    """The gamedata value to write for an applied slot (crown: delta from 100, as the engine reads it)."""
    if s.field != 'crown tower damage percent':
        return s.value
    return s.value - 100


def crown_writable(s):
    return s.crown_raw is not None and s.crown_raw < 0


# ----------------------------------------------------------------------------- the overlay

def _index(doc):
    return {s['name']: s for s in doc['items']['spells']}


def _rs(doc):
    return {c['name']: c for c in doc['cards']}, doc['units']


def build(gamedata, rs16_doc, rs15_doc, cal_doc, *, c56=frozenset()):
    """Patch `gamedata` (a parsed doc, modified in place). Returns (slots with decisions, propagated changes).
    Pass 1 = the comparer's slots; pass 2 = named objects (named_slots) at locations pass 1 does not own; pass 3 =
    detection-action tier buffs (tier_slots); all are decided on the unmodified doc, then written; a final step
    propagates unit/projectile changes to same-named copies."""
    spells = _index(gamedata)
    cal_spells = _index(cal_doc)
    c16, u16 = _rs(rs16_doc)
    c15, u15 = _rs(rs15_doc)
    pool = sorted(p['name'] for p in _pool(gamedata))
    kinds = {p['name']: p['kind'] for p in _pool(gamedata)}
    slots = []
    for name in pool:
        card = spells[name]
        mine = card_slots(name, kinds[name], card, c16.get(name), u16, spells)
        old = {(s.subject, s.field): s for s in card_slots(name, kinds[name], card, c15.get(name), u15, spells)}
        cal_card = cal_spells.get(name)
        cal = {} if cal_card is None else {
            (s.subject, s.field): s for s in card_slots(name, kinds[name], cal_card, c16.get(name), u16, cal_spells)}
        for s in mine:
            if (s.subject, s.field) in old:
                s.rs15 = old[(s.subject, s.field)].rs16
            if (s.subject, s.field) in cal:
                s.cal = cal[(s.subject, s.field)].ours
            s.extra['c56'] = name in c56
            s.extra['pass'] = 1
            decide(s)
            if s.action in ('apply', 'calibration') and s.field == 'crown tower damage percent' and not crown_writable(s):
                s.action, s.reason = 'skip-uncertain', 'crown raw >= 0: delta convention unclear'
        slots += mine
    # pass 1 owns its locations unless it had no RoyaleSim value there (then a named table may supply one)
    owned = {(id(s.loc.container), s.loc.key) for s in slots
             if s.loc is not None and s.action not in ('keep-rs-absent', 'skip-absent')}
    slots += named_slots(spells, cal_spells, pool, rs16_doc, rs15_doc, owned, c56)
    slots += tier_slots(spells, cal_spells, pool, c16, c15, owned, c56)

    # one write per location; slots that disagree on a shared location keep ours
    by_loc = {}
    for s in slots:
        if s.action in ('apply', 'calibration'):
            by_loc.setdefault((id(s.loc.container), s.loc.key), []).append(s)
    changes = []
    for group in by_loc.values():
        vals = {json.dumps(raw_value(s)) for s in group}
        if len(vals) > 1:
            for s in group:
                s.action, s.reason = 'skip-conflict', 'two slots map to this location with different 16.402 values'
            continue
        s = group[0]
        old_raw = s.loc.container[s.loc.key]
        s.loc.container[s.loc.key] = raw_value(s)
        for t in group[1:]:
            t.action, t.reason = 'shared', f'same location as {s.card} {s.subject} {s.field}'
        changes.append((s, old_raw))
    propagated = _propagate(spells, pool, changes)
    return slots, propagated


# Pass 2: named objects. Our nested blocks carry `name` and `source`; RoyaleSim has the same objects by name in its
# units / projectiles / area_effect_objects / buffs tables (same units as the card table; crown values on projectiles
# and areas are raw deltas there too, on buffs effective percents).
NAMED_TABLES = {
    'projectiles': ('projectiles', dict(
        damage='damage', speed='speed', radius='radius_milli', buffTime='buff_time_ms',
        projectileRange='projectile_range_milli', pushback='pushback_milli', radiusY='radius_y_milli',
        spawnCharacterCount='spawn_character_count', crownTowerDamagePercent='crown_tower_damage_percent_raw')),
    'area_effect_objects': ('area_effect_objects', dict(
        lifeDuration='life_duration_ms', radius='radius_milli', hitSpeed='hit_speed_ms', buffTime='buff_time_ms',
        damage='damage', spawnInterval='spawn_interval_ms', crownTowerDamagePercent='crown_tower_damage_percent_raw')),
    'character_buffs': ('buffs', dict(
        speedMultiplier='speed_multiplier_raw', hitSpeedMultiplier='hit_speed_multiplier_raw',
        spawnSpeedMultiplier='spawn_speed_multiplier_raw', hitFrequency='hit_frequency_ms',
        damagePerSecond='damage_per_second', healPerSecond='heal_per_second', damageReduction='damage_reduction',
        buildingDamagePercent='building_damage_percent', crownTowerDamagePercent='crown_tower_damage_percent')),
}
UNIT_SOURCES = ('characters', 'buildings')


def _named_views(node, path, rs_doc):
    """[(field label, our value, RoyaleSim value, Loc | None, rs_default, crown_raw)] for one named block."""
    src, name = node.get('source'), node.get('name')
    out = []
    if src in UNIT_SOURCES:
        rec = rs_doc['units'].get(name)
        if rec is None:
            return out
        ours, rs, locs = sd.ours_unit(node), sd.rs_unit(rec), unit_locs(node, path)
        for label, key, kind in sd.SPEC_UNIT:
            if kind == 'num':
                out.append((label, ours.get(key), rs.get(key), locs.get(key),
                            key in RS_DEFAULT_KEYS and key in (rec.get('defaults_applied') or []), None))
    elif src in NAMED_TABLES:
        table, fields = NAMED_TABLES[src]
        rec = rs_doc[table].get(name)
        if rec is None:
            return out
        for ours_key, rs_key in fields.items():
            if ours_key not in node or rs_key not in rec:
                continue
            o, loc = node[ours_key], Loc(node, ours_key, f'{path}/{ours_key}')
            raw = None
            if ours_key == 'crownTowerDamagePercent' and table == 'buffs':
                raw, o = o, bs.effective_crown(o) if isinstance(o, (int, float)) else o
            out.append((ours_key, o, rec[rs_key], loc, rs_key in (rec.get('defaults_applied') or []), raw))
    return out


def named_slots(spells, cal_spells, pool, rs16_doc, rs15_doc, owned, c56):
    """Pass 2 slots: every named unit/projectile/area/buff block in the pool cards' base forms, at locations pass 1
    does not own, decided with the same rules (RoyaleSim 15.535 and the calibration copy from the same name/path)."""
    out = []
    for card in pool:
        blocks = []
        _walk_blocks(spells[card], '', blocks)
        cal_card = cal_spells.get(card)
        for path, node in blocks:
            if not node.get('name') or not node.get('source'):
                continue
            old = {v[0]: v[2] for v in _named_views(node, path, rs15_doc)}
            for label, o, r, loc, rs_default, raw in _named_views(node, path, rs16_doc):
                if loc is None or (id(loc.container), loc.key) in owned:
                    continue
                owned.add((id(loc.container), loc.key))
                s = Slot(card, f'named {node["source"]} {node["name"]}', label, 'num', o, r, loc,
                         rs_default=rs_default, rs15=old.get(label))
                if loc.key == 'crownTowerDamagePercent':
                    s.field = 'crown tower damage percent'
                    s.crown_raw = raw if raw is not None else o
                    if raw is None:   # projectile / area: both sides raw deltas
                        s.ours, s.rs16 = bs.effective_crown(o), None if r is None else bs.effective_crown(r)
                        s.rs15 = None if s.rs15 is None else bs.effective_crown(s.rs15)
                    if s.rs16 is None:
                        s.unsure = 'RoyaleSim crown cell is blank (raw None), no measured value'
                if cal_card is not None:
                    try:
                        cont, key = resolve(cal_card, loc.path)
                        s.cal = cont.get(key)
                        if s.field == 'crown tower damage percent' and isinstance(s.cal, (int, float)):
                            s.cal = bs.effective_crown(s.cal)
                    except (KeyError, IndexError, TypeError, AttributeError):
                        s.cal = None
                s.extra.update(c56=card in c56, path=loc.path)
                s.extra['pass'] = 2
                decide(s)
                if s.action in ('apply', 'calibration') and s.field == 'crown tower damage percent' \
                        and not crown_writable(s):
                    s.action, s.reason = 'skip-uncertain', 'crown raw >= 0: delta convention unclear'
                out.append(s)
    return out


# Pass 3: action tiers. A detection action (Void's laser ball) spawns one source-less buff per target-count tier
# from its onDetectedUnitActionList, so pass 2 (which needs `source`) never sees it. RoyaleSim keeps the same buffs
# in the card record's strike_area.tiers[i].buff. Match on the action kind (ActionLaserBall <-> laser_ball) and the
# buff name, never on an action or tier index; a name that is missing or repeated on either side matches nothing.
# crownTowerDamagePerHit is an absolute per-hit value on both sides (no delta convention).
TIER_FIELDS = dict(damagePerSecond='damage_per_second', crownTowerDamagePerHit='crown_tower_damage_per_hit',
                   hitFrequency='hit_frequency_ms')


def _action_kind(class_type):
    """'ActionLaserBall' -> 'laser_ball' (RoyaleSim's strike_area.kind)."""
    if not isinstance(class_type, str) or not class_type.startswith('Action'):
        return None
    return re.sub(r'(?<!^)(?=[A-Z])', '_', class_type[len('Action'):]).lower() or None


def _rs_tier_buffs(rec):
    """{(strike-area kind, buff name): RoyaleSim buff} for one RoyaleSim card record (unique names only)."""
    found = {}

    def walk(node):
        if isinstance(node, dict):
            area = node.get('strike_area')
            if isinstance(area, dict):
                for tier in area.get('tiers') or ():
                    buff = (tier or {}).get('buff') or {}
                    if buff.get('name'):
                        found.setdefault((area.get('kind'), buff['name']), []).append(buff)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(rec or {})
    return {key: hits[0] for key, hits in found.items() if len(hits) == 1}


def _our_tier_buffs(card):
    """{(action kind, buff name): [(path, spawnData)]} for every detection action's per-tier buff spawns."""
    found = {}
    blocks = []
    _walk_blocks(card, '', blocks)
    for path, node in blocks:
        tiers = node.get('onDetectedUnitActionList')
        kind = _action_kind(node.get('classType'))
        if kind is None or not isinstance(tiers, list):
            continue
        for i, action in enumerate(tiers):
            if not isinstance(action, dict) or action.get('spawnType') != 'BuffType':
                continue
            data = action.get('spawnData')
            if isinstance(data, dict) and data.get('name') and not data.get('source'):
                found.setdefault((kind, data['name']), []).append(
                    (f'{path}/onDetectedUnitActionList[{i}]/spawnData', data))
    return found


def tier_slots(spells, cal_spells, pool, c16, c15, owned, c56):
    """Pass 3 slots (see TIER_FIELDS), decided with the same rules as passes 1 and 2."""
    out = []
    for card in pool:
        ours = _our_tier_buffs(spells[card])
        if not ours:
            continue
        rs16, rs15 = _rs_tier_buffs(c16.get(card)), _rs_tier_buffs(c15.get(card))
        # Calibration tiers by the same identity (kind, name), never by our path: its tier order may differ.
        cal = _our_tier_buffs(cal_spells[card]) if card in cal_spells else {}
        for key in sorted(ours):
            if len(ours[key]) != 1 or key not in rs16:
                continue
            path, node = ours[key][0]
            for ours_key, rs_key in TIER_FIELDS.items():
                if ours_key not in node:
                    continue
                loc = Loc(node, ours_key, f'{path}/{ours_key}')
                if (id(loc.container), loc.key) in owned:
                    continue
                owned.add((id(loc.container), loc.key))
                s = Slot(card, f'tier {key[0]} {key[1]}', ours_key, 'num', node[ours_key], rs16[key].get(rs_key),
                         loc, rs15=(rs15.get(key) or {}).get(rs_key))
                if s.rs16 is None:
                    s.unsure = 'RoyaleSim tier cell is blank, no measured value'
                if len(cal.get(key, ())) == 1:
                    s.cal = cal[key][0][1].get(ours_key)
                s.extra.update(c56=card in c56, path=loc.path)
                s.extra['pass'] = 3
                decide(s)
                out.append(s)
    return out


def _pool(doc):
    """ladder_pool over a parsed doc (pool.ladder_pool reads a path)."""
    items = doc['items']
    return [dict(name=s['name'], kind=KIND[s['source']]) for s in items['spells']
            if not s.get('notVisible') and s.get('source') in KIND]


def _walk_blocks(node, path, out):
    """Every dict under a base card (evolutions and hero forms excluded), in document order."""
    if isinstance(node, dict):
        out.append((path, node))
        for k, v in node.items():
            if k in ('evolvedSpellsData', 'heroData'):
                continue
            _walk_blocks(v, f'{path}/{k}', out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_blocks(v, f'{path}[{i}]', out)


def _propagate(spells, pool, changes):
    """Unit/projectile changes -> the other base copies of the same named block in pool cards that hold the old
    value. Card-level and crown slots are not propagated."""
    rules = {}
    for s, old in changes:
        if s.extra.get('pass') == 3:
            continue  # tier buffs are matched by action kind + name; a same-named block elsewhere is not that tier
        if s.subject == 'card' and s.field in ('elixir', 'count', 'summon radius', 'summon deploy delay (ms)',
                                               'second unit count', 'crown tower damage percent'):
            continue
        bname = s.loc.container.get('name')
        if not bname:
            continue
        rules.setdefault((bname, s.loc.key, json.dumps(old)), set()).add(json.dumps(s.loc.container[s.loc.key]))
    done = {(id(s.loc.container), s.loc.key) for s, _ in changes}
    out = []
    for (bname, key, old), news in sorted(rules.items()):
        if len(news) != 1:
            continue  # two different new values for one named block: leave the copies alone
        new = json.loads(next(iter(news)))
        for name in pool:
            blocks = []
            _walk_blocks(spells[name], '', blocks)
            for path, node in blocks:
                if node.get('name') == bname and key in node and json.dumps(node[key]) == old \
                        and (id(node), key) not in done:
                    node[key] = new
                    done.add((id(node), key))
                    out.append(dict(card=name, block=bname, path=f'{path}/{key}', key=key, old=json.loads(old), new=new))
    return out


def dumps_like(doc, original_bytes):
    """Serialize in the input's own JSON format (asserted on the unmodified input)."""
    for kw in (dict(indent=2, ensure_ascii=False), dict(indent=1, ensure_ascii=False), dict(ensure_ascii=False),
               dict(indent=2), dict()):
        for tail in ('\n', ''):
            if (json.dumps(json.loads(original_bytes), **kw) + tail).encode() == original_bytes:
                return (json.dumps(doc, **kw) + tail).encode()
    raise SystemExit('input gamedata JSON format not recognised; refusing to rewrite it')


def calibration_paths(runtime_bytes, cal_bytes):
    """Field-level runtime-vs-calibration differences in spell records: [(card, path, runtime, calibration)]."""
    a = _index(json.loads(runtime_bytes))
    b = _index(json.loads(cal_bytes))
    return bs.field_diff(a, b)


def body(subject):
    """'death spawn Barbarian' -> 'death spawn' (the body kind, without the unit name)."""
    return subject if subject == 'card' else re.sub(r' \S+$', '', subject)


def summarize(slots, propagated, cal_diff, out_doc):
    acts = Counter(s.action for s in slots)
    applied = [s for s in slots if s.action in ('apply', 'calibration')]
    by_field = Counter(f'{body(s.subject)}:{s.field}' for s in applied)
    by_card = Counter(s.card for s in applied)
    c56_cards = sorted({s.card for s in applied if s.extra.get('c56')})
    other_cards = sorted({s.card for s in applied if not s.extra.get('c56')})
    out_spells = _index(out_doc)

    def final(card, path):
        try:
            cont, key = resolve(out_spells[card], path)
            return cont.get(key)
        except (KeyError, TypeError, AttributeError):
            return None

    cal_cases = [dict(card=s.card, subject=s.subject, field=s.field, path=s.loc.path if s.loc else None,
                      runtime=s.ours, calibration=s.cal, rs15535=s.rs15, rs16402=s.rs16, action=s.action,
                      written=s.value if s.action in ('apply', 'calibration') else s.ours, reason=s.reason)
                 for s in slots if s.cal is not None and s.cal != s.ours and s.kind not in STRUCTURAL]
    cal_coverage = [dict(card=c, path=p, runtime=r, calibration=k, output=final(c, p),
                         covered_by=('slot' if any(x['card'] == c and x['path'] == p for x in cal_cases) else
                                     'propagation' if any(x['card'] == c and x['path'] == p for x in propagated)
                                     else 'none'))
                    for c, p, r, k in cal_diff]
    return dict(
        actions=dict(sorted(acts.items())),
        actions_by_pass={str(k): dict(sorted(Counter(s.action for s in slots if s.extra.get('pass') == k).items()))
                         for k in (1, 2, 3)},
        applied_slots=len(applied), propagated_copies=len(propagated),
        cards_changed=dict(c56=c56_cards, others=other_cards),
        changes_by_card=dict(sorted(by_card.items())),
        changes_by_field=dict(sorted(by_field.items())),
        changed_fields=sorted({(s.card, s.subject, s.field) for s in applied}),
        propagated=[(p['card'], p['block'], p['key']) for p in propagated],
        calibration_cases=cal_cases,
        calibration_paths=cal_coverage,
        uncertain_kept=sorted({(s.card, s.subject, s.field, s.reason) for s in slots if s.action == 'skip-uncertain'}),
        held=sorted({(s.card, s.subject, s.field, s.reason) for s in slots if s.action == 'skip-hold'}),
        structural_skipped=sorted({(s.card, s.subject, s.field) for s in slots if s.action == 'skip-structural'}),
        no_location=sorted({(s.card, s.subject, s.field) for s in slots if s.action == 'skip-no-location'}),
        conflicts=sorted({(s.card, s.subject, s.field) for s in slots if s.action == 'skip-conflict'}),
    )


def comparer_check(slots, ours_spells, kinds, rs16_doc):
    """Our slot verdicts must reproduce the comparer's MISMATCH/UNCERTAIN rows exactly (no mapping drift)."""
    c16, u16 = _rs(rs16_doc)
    want = set()
    for name in sorted({s.card for s in slots}):
        for r in bs.card_rows(name, kinds[name], ours_spells[name], c16.get(name), u16, ours_spells, []):
            if r.kind in ('MISMATCH', 'UNCERTAIN'):
                want.add((r.card, r.subject, r.field))
    got = set()
    for s in slots:
        if s.extra.get('pass') != 1:
            continue
        v = verdict(s)
        if v is None:
            continue
        if s.field == 'crown tower damage percent':
            if v == 'MISMATCH':
                got.add((s.card, s.subject, s.field))
        elif v == 'MISMATCH' or s.unsure:
            got.add((s.card, s.subject, s.field))
    return sorted(want - got), sorted(got - want)


def run(gamedata_path, rs16_path, rs15_path, cal_path, out_path, *, c56=frozenset()):
    raw = Path(gamedata_path).read_bytes()
    cal_raw = Path(cal_path).read_bytes()
    doc = json.loads(raw)
    pristine = json.loads(raw)
    rs16, rs15 = json.loads(Path(rs16_path).read_text()), json.loads(Path(rs15_path).read_text())
    kinds = {p['name']: p['kind'] for p in _pool(pristine)}
    slots, propagated = build(doc, rs16, rs15, json.loads(cal_raw), c56=c56)
    missing, extra = comparer_check(slots, _index(pristine), kinds, rs16)
    doc['meta'] = dict(doc.get('meta') or {}, live16402_overlay=dict(
        generator=GENERATOR, version=VERSION, input_sha256=hashlib.sha256(raw).hexdigest(),
        royalesim=rs16.get('version'), royalesim_sha256=sha256(rs16_path)))
    out_bytes = dumps_like(doc, raw)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_bytes(out_bytes)
    tmp.replace(out)
    summary = summarize(slots, propagated, calibration_paths(raw, cal_raw), doc)
    gamedata_path, rs16_path, rs15_path, cal_path, out_path = (
        Path(p).resolve() for p in (gamedata_path, rs16_path, rs15_path, cal_path, out_path))
    receipt = dict(
        kind='clasher live16402 balance overlay', generator=GENERATOR, version=VERSION,
        source_note='RoyaleSim table is content 16.402.19 (client 160402017, 2026-10-06 update); live client is '
                    'versionCode 160402020. Same 16.402 line; later server-side balance changes are not covered.',
        inputs=dict(gamedata=dict(path=str(gamedata_path), sha256=sha256(gamedata_path)),
                    royalesim_16402=dict(path=str(rs16_path), sha256=sha256(rs16_path), version=rs16.get('version')),
                    royalesim_15535=dict(path=str(rs15_path), sha256=sha256(rs15_path), version=rs15.get('version')),
                    calibration=dict(path=str(cal_path), sha256=sha256(cal_path))),
        output=dict(path=str(out_path), sha256=sha256(out_path)),
        comparer_check=dict(missing=missing, extra=extra),
        **summary)
    detail = [dict(card=s.card, subject=s.subject, field=s.field, path=s.loc.path if s.loc else None, ours=s.ours,
                   rs16402=s.rs16, rs15535=s.rs15, calibration=s.cal, action=s.action, written=raw_value(s)
                   if s.action in ('apply', 'calibration') else None, reason=s.reason)
              for s in slots if s.action != 'agree'] + [dict(propagated=p) for p in propagated]
    return receipt, detail


def c56_names():
    return frozenset(bs.c56_names())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--gamedata', required=True, help='runtime gamedata.json (r1 / engine-cards/py)')
    ap.add_argument('--rs16', required=True, help='RoyaleSim cards-160402017-20261006.json')
    ap.add_argument('--rs15', required=True, help='RoyaleSim cards-15.535.json')
    ap.add_argument('--calibration', required=True, help="main's calibrated root gamedata.json")
    ap.add_argument('--out', required=True)
    ap.add_argument('--receipt', required=True, help='git-safe receipt: sha256s, counts, names')
    ap.add_argument('--detail', help='per-slot values (keep beside the output, never in git)')
    a = ap.parse_args()
    receipt, detail = run(a.gamedata, a.rs16, a.rs15, a.calibration, a.out, c56=c56_names())
    Path(a.receipt).write_text(json.dumps(receipt, indent=1, sort_keys=True, default=list) + '\n')
    if a.detail:
        Path(a.detail).write_text(json.dumps(detail, indent=1, sort_keys=True) + '\n')
    print(json.dumps(dict(output=receipt['output'], actions=receipt['actions'], applied=receipt['applied_slots'],
                          propagated=receipt['propagated_copies'], cards=receipt['cards_changed'],
                          comparer_check=receipt['comparer_check']), indent=1))


if __name__ == '__main__':
    main()
