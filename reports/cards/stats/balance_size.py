#!/usr/bin/env python3
"""Balance size: our runtime card stats against RoyaleSim 16.402, for all 122 ladder-pool cards.

Run from anywhere with -I (RoyaleSim's data is third-party, so nothing in its directory is imported):

    python3 -I reports/cards/stats/balance_size.py

Writes reports/cards/stats/BALANCE-SIZE.md. Ours defaults to engine-cards/py/gamedata.json (the runtime r1
copy); BALANCE_OURS=<path> compares another copy (the root gamedata.json, which statsdiff.py reads, differs
from it). Field mapping and unit conversions are statsdiff.py's; the crown-tower and second-unit checks are
new here. RoyaleSim's data is read at run time and never copied; the report holds only differing values.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HERE))  # statsdiff.py: the field mapping this comparer reuses
sys.path.insert(0, str(REPO / 'reports/cards/tools'))
import statsdiff as sd  # noqa: E402
from pool import ladder_pool  # noqa: E402

OURS = Path(os.environ.get('BALANCE_OURS', REPO / 'engine-cards/py/gamedata.json'))
RS_DIR = Path('/mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived')
RS_PATH = Path(os.environ.get('ROYALESIM_CARDS', RS_DIR / 'cards-160402017-20261006.json'))
RS_OLD = RS_DIR / 'cards-160402017.json'      # 16.402.2, the 2026-10-02 install
RS_15535 = RS_DIR / 'cards-15.535.json'       # 15.535.29, the earlier live build
RS_CAL = RS_PATH.parents[1] / 'calibration.json'  # RoyaleSim's data/calibration.json
C56_SRC = REPO / 'bot/players/rext_imitate_replays.py'
OUT_MD = HERE / 'BALANCE-SIZE.md'

# Fields whose difference is material: the brief's list (hp, damage, speed, range, hit speed, cost, spawn
# counts), with death and tower damage under damage and minimum range under range.
MATERIAL = {'elixir', 'count', 'second unit count', 'hitpoints', 'damage', 'death damage',
            'crown tower damage percent', 'hit speed (ms)', 'speed', 'range', 'minimum range',
            'death spawn count', 'spawner number'}

# A crownTowerDamagePercent counts as the card's own when it sits on one of these paths. For a spell the
# damage object is the spell itself (its area or projectile); for a troop or building it is its unit.
# Anywhere else (buffs, spawn chains, a unit's own area effect) is reported as UNCERTAIN.
OWN_CROWN = {
    'spell': {'/crownTowerDamagePercent', '/projectileData/crownTowerDamagePercent',
              '/areaEffectObjectData/crownTowerDamagePercent'},
    'unit': {'/crownTowerDamagePercent', '/summonCharacterData/crownTowerDamagePercent',
             '/summonCharacterData/projectileData/crownTowerDamagePercent'},
}

# Extra caveats for rows statsdiff does not know about (merged into its table so add_rows() applies them).
UNSURE_EXTRA = {
    ('Lightning', 'hit speed (ms)'):
        'RoyaleSim hit_speed_ms (500) is the strike interval the 16.402 strike test calls AreaHitSpeed; '
        'gamedata hitSpeed on the area object may be a different concept',
}
sd.UNSURE.update(UNSURE_EXTRA)


def c56_names():
    src = C56_SRC.read_text()
    return set(re.findall(r"'(\w+)'", re.search(r'C56 = frozenset\(\((.*?)\)\)', src, re.S).group(1)))


def load_rs(path=RS_PATH):
    d = json.loads(path.read_text())
    return {c['name']: c for c in d['cards']}, d['units'], d


def find_crown(node, path=''):
    """First crownTowerDamagePercent in document order under a base card (evolutions and hero forms excluded).
    Returns (path, raw) or None."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ('evolvedSpellsData', 'heroData'):
                continue
            p = f'{path}/{k}'
            if k == 'crownTowerDamagePercent' and isinstance(v, (int, float)):
                return p, v
            hit = find_crown(v, p)
            if hit:
                return hit
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hit = find_crown(v, f'{path}[{i}]')
            if hit:
                return hit
    return None


def effective_crown(raw):
    """Gamedata stores a delta from 100 for negative values (RoyaleSim's stated convention: -77 -> 23)."""
    return 100 + raw if raw < 0 else raw


def rs_crown_blank(rec):
    """True when RoyaleSim's 100 is a blank 16.402 cell (raw None, which loads as 100), not a measured value."""
    objs = [rec.get('projectile'), (rec.get('spell') or {}).get('area_effect_object')]
    cells = [o for o in objs if o and 'crown_tower_damage_percent' in o]
    return bool(cells) and all(o['crown_tower_damage_percent'] == 100 and o.get('crown_tower_damage_percent_raw') is None
                               for o in cells)


def crown_rows(name, kind, card, rec):
    """Card-level crown-tower damage percent: ours (effective; 100 when gamedata has none) against
    RoyaleSim's effective card value."""
    found = find_crown(card)
    ours = effective_crown(found[1]) if found else 100
    rs = rec.get('crown_tower_damage_percent')
    if rs == 100 and rs_crown_blank(rec) and ours != 100:
        note = ('RoyaleSim\'s 16.402.19 crown cell is blank (loads as 100), so it is no measured value; '
                f'gamedata raw {found[1]} at {found[0]}')
        return [sd.Row(name, 'card', 'crown tower damage percent', sd.fmt(ours), '100 (blank cell)', 'UNCERTAIN', note)]
    if rs is not None:
        kind_out = sd.compare(ours, rs, 'num')
    else:
        kind_out = 'RS-ABSENT' if found and ours else None  # the runtime default says nothing about RoyaleSim
    if kind_out is None:
        return []
    note = f'gamedata raw {found[1]} at {found[0]}' if found else 'gamedata has no crown value (runtime default 100)'
    if kind_out == 'MISMATCH' and found and found[0] not in OWN_CROWN['spell' if kind == 'spell' else 'unit']:
        kind_out = 'UNCERTAIN'
        note += '; not on the card\'s own damage object, so the sources may not mean the same thing'
    return [sd.Row(name, 'card', 'crown tower damage percent', sd.fmt(ours), sd.fmt(rs), kind_out, note)]


def second_rows(name, card, rec, rs_units):
    """The second unit type and its count (GoblinGang's SpearGoblins, Rascals' RascalGirls, Goblinstein's doctor)."""
    rows = []
    node = card.get('summonCharacterSecondData') or None
    rs2 = rec.get('second_summon') or {}
    rs_name = rs2.get('character')
    sd.add_rows(rows, name, 'card', [('second unit', 'name', 'name')],
                {'name': (node or {}).get('name')}, {'name': rs_name})
    sd.add_rows(rows, name, 'card', [('second unit count', 'count', 'num')],
                {'count': card.get('summonCharacterSecondCount')}, {'count': rs2.get('count')})
    if node and rs_name:
        key = next((k for k in rs_units if k.casefold() == rs_name.casefold()), None)
        if key:
            sd.add_rows(rows, name, f'second unit {key}', sd.SPEC_UNIT,
                        sd.ours_unit(node), sd.rs_unit(rs_units[key]))
    return rows


def card_rows(name, kind, card, rec, rs_units, ours_spells, unparsed):
    """Every comparison row for one card against one RoyaleSim file."""
    rows = sd.card_check(name, kind, card, rec, rs_units, ours_spells, unparsed)
    if rec is not None:
        rows += second_rows(name, card, rec, rs_units)
        rows += crown_rows(name, kind, card, rec)
    return rows


def all_rows(order, kinds, ours_spells, rs_cards, rs_units):
    unparsed = []
    return {n: card_rows(n, kinds[n], ours_spells[n], rs_cards.get(n), rs_units, ours_spells, unparsed)
            for n in order}


def field_diff(xa, xb):
    """Field-level differences between two name-keyed record sets: [(name, path, a value, b value)]."""
    out = []

    def walk(x, y, name, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k in ('evolvedSpellsData', 'heroData', 'meta', 'defaults_applied'):
                    continue
                if k not in x or k not in y:
                    out.append((name, f'{path}/{k}', x.get(k), y.get(k)))
                else:
                    walk(x[k], y[k], name, f'{path}/{k}')
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, name, f'{path}[{i}]')
        elif x != y:
            out.append((name, path, x, y))

    for n in xa:
        if n in xb:
            walk(xa[n], xb[n], n, '')
    return out


def copy_diff(a, b):
    """Our two gamedata copies, compared on their spell records."""
    sa = {s['name']: s for s in json.loads(a.read_text())['items']['spells']}
    sb = {s['name']: s for s in json.loads(b.read_text())['items']['spells']}
    return field_diff(sa, sb)


def rs_card_diff(a, b):
    """RoyaleSim's two 16.402 card files, compared on card records."""
    ca = {c['name']: c for c in json.loads(a.read_text())['cards']}
    cb = {c['name']: c for c in json.loads(b.read_text())['cards']}
    return field_diff(ca, cb)


def shown(p):
    """A path for the report: repo-relative when it is inside the repo, else as given."""
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)


def overlay_check(rs_cards, rs_units, overlay):
    """Each RoyaleSim CLIENT16402_VALUES entry against the 16.402 table: (card, column, want, got, equal|None)."""
    out = []
    for name, cols in overlay.items():
        rec = rs_cards.get(name) or {}
        unit = rs_units.get(name) or {}
        for col, val in cols.items():
            if col == 'Hitpoints':
                got, want = unit.get('hitpoints', rec.get('hitpoints')), val
            elif col == 'ProjectileDamage':
                got = ((unit.get('projectile') or rec.get('projectile')) or {}).get('damage')
                want = val
            elif col == 'CrownTowerDamagePercent':
                got, want = rec.get('crown_tower_damage_percent'), effective_crown(val)
            elif col == 'AreaBuffTime':
                got = ((rec.get('spell') or {}).get('area_effect_object') or {}).get('buff_time_ms')
                want = val
            else:
                got, want = None, val
            out.append((name, col, want, got, got == want if got is not None else None))
    return out


def alt_match(material, alt_rows):
    """For each material row: 'same' when the older file has no differing row for it (so it equals ours),
    'other' when the older file differs from ours, 'unknown' when it has a non-comparable row."""
    alt = {(r.card, r.subject, r.field): r for rows in alt_rows.values() for r in rows}
    out = []
    for r in material:
        a = alt.get((r.card, r.subject, r.field))
        out.append('same' if a is None else 'other' if a.kind == 'MISMATCH' else 'unknown')
    return Counter(out)


def pct(ours, rs):
    if isinstance(ours, (int, float)) and isinstance(rs, (int, float)) and ours not in (0, None):
        return f'{(rs - ours) / ours * 100:+.1f}%'
    return '—'


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    c56 = c56_names()
    pool = ladder_pool(OURS)
    kinds = {p['name']: p['kind'] for p in pool}
    ours_spells = {s['name']: s for s in json.loads(OURS.read_text())['items']['spells']}
    rs_cards, rs_units, rs_doc = load_rs()
    overlay = json.loads(RS_CAL.read_text())['cards']['CLIENT16402_VALUES']['value']['values']

    names = [p['name'] for p in pool]
    assert len(names) == 122 and c56 <= set(names), 'pool is not the 122 ladder cards or C56 is outside it'
    order = sorted(n for n in names if n in c56) + sorted(n for n in names if n not in c56)

    per_card = all_rows(order, kinds, ours_spells, rs_cards, rs_units)
    diffs = {n: [r for r in per_card[n] if r.kind == 'MISMATCH'] for n in order}
    unsures = {n: [r for r in per_card[n] if r.kind == 'UNCERTAIN'] for n in order}
    cannots = {n: [r for r in per_card[n] if r.kind in ('ABSENT', 'RS-ABSENT')] for n in order}

    def group(flag):
        cards = [n for n in order if (n in c56) == flag]
        any_d = [n for n in cards if diffs[n]]
        mat_d = [n for n in cards if any(r.field in MATERIAL for r in diffs[n])]
        return cards, any_d, mat_d

    c56_cards, c56_any, c56_mat = group(True)
    oth_cards, oth_any, oth_mat = group(False)
    mat_rows = [r for n in order for r in diffs[n] if r.field in MATERIAL]
    nonmat_rows = [r for n in order for r in diffs[n] if r.field not in MATERIAL]
    kinds_count = Counter(r.kind for n in order for r in per_card[n])

    # the older RoyaleSim files, to see which build the runtime copy matches
    old_cards, old_units, _ = load_rs(RS_OLD)
    old_rows = all_rows(order, kinds, ours_spells, old_cards, old_units)
    c_cards, c_units, _ = load_rs(RS_15535)
    c_rows = all_rows(order, kinds, ours_spells, c_cards, c_units)
    m_old = alt_match(mat_rows, old_rows)
    m_15535 = alt_match(mat_rows, c_rows)

    cannot_by_field = defaultdict(list)
    for n in order:
        for r in cannots[n]:
            cannot_by_field[(r.field, r.kind, 'card' if r.subject == 'card' else 'sub-unit')].append(n)
    unsure_rows = [r for n in order for r in unsures[n]]
    blank_cards = sorted({r.card for r in unsure_rows if r.rs == '100 (blank cell)'})

    copy_root = copy_diff(REPO / 'gamedata.json', OURS)
    rs_versions = rs_card_diff(RS_OLD, RS_PATH)
    overlay_rows = overlay_check(rs_cards, rs_units, overlay)
    overlay_ok = sum(1 for r in overlay_rows if r[4])
    overlay_unmapped = sum(1 for r in overlay_rows if r[4] is None)

    lines = [
        '# Balance size: our runtime card stats vs RoyaleSim 16.402',
        '',
        f'Generated by `reports/cards/stats/balance_size.py` (run with `python3 -I`). Ours: `{shown(OURS)}`. '
        f'RoyaleSim: `{RS_PATH.name}`, version `{rs_doc.get("version")}` (the 16.402.19 update). '
        'Level-1 base values. Only differing values are listed; RoyaleSim\'s data file is not copied into the repo.',
        '',
        '## (a) Headline',
        '',
        f'- Pool: {len(names)} ladder cards: C56 {len(c56_cards)}, others {len(oth_cards)}.',
        f'- **C56 ({len(c56_cards)} cards)**: any stat difference: **{len(c56_any)}**; material difference '
        f'(hp, damage, speed, range, hit speed, cost, spawn counts): **{len(c56_mat)}**.',
        f'- **Others ({len(oth_cards)} cards)**: any stat difference: **{len(oth_any)}**; material difference: **{len(oth_mat)}**.',
        f'- Rows: MISMATCH {kinds_count["MISMATCH"]} (counted); UNCERTAIN {kinds_count["UNCERTAIN"]} (in d, not counted); '
        f'ABSENT {kinds_count["ABSENT"]} and RS-ABSENT {kinds_count["RS-ABSENT"]} (in c, not counted).',
        '- "Any difference" = a row where both sides have a value and they differ (MISMATCH), counting non-material fields too.',
        '',
        '## (b) Material differences (C56 first)',
        '',
        'Body is the card itself or the sub-unit it spawns or carries. % change is (16.402 − ours) / ours.',
        '',
        '| Card | Body | Field | Ours (runtime) | 16.402 | % change |',
        '|---|---|---|---|---|---|',
    ]
    for r in mat_rows:
        card = f'{r.card} (C56)' if r.card in c56 else r.card
        lines.append(f'| {card} | {r.subject} | {r.field} | {r.ours} | {r.rs} | {pct(_num(r.ours), _num(r.rs))} |')
    if not mat_rows:
        lines.append('| none | | | | | |')

    lines += ['', f'Non-material differences ({len(nonmat_rows)} rows, not in the table): '
              + '; '.join(f'{r.card} {r.subject} {r.field} ({r.ours} → {r.rs})' for r in nonmat_rows) + '.']
    lines += ['', '## (c) Fields we could not compare (not counted as differences)', '',
              'ABSENT: gamedata has no such field and RoyaleSim has a value. RS-ABSENT: RoyaleSim has no value and gamedata has one.',
              '', '| Field | Kind | Body | Cards | Example cards |', '|---|---|---|---|---|']
    for (field, kind, body), cards in sorted(cannot_by_field.items(), key=lambda kv: (-len(set(kv[1])), kv[0])):
        uniq = sorted(set(cards))
        ex = ', '.join(uniq[:6]) + (' …' if len(uniq) > 6 else '')
        lines.append(f'| {field} | {kind} | {body} | {len(uniq)} | {ex} |')
    lines += ['', '## (d) Notes and unsure fields', '']
    lines += [
        f'- Which copy is ours: the runtime copy `{shown(OURS)}`, as the brief names it. The root `gamedata.json` '
        f'(what statsdiff.py reads, the calibrated copy) differs from it on {len(copy_root)} fields in '
        f'{len({c for c, *_ in copy_root})} spells ({", ".join(sorted({c for c, *_ in copy_root}))}). '
        'The STATSDIFF comparison used the root copy and so did not see those differences.',
        f'- Which build the runtime copy matches. Of the {len(mat_rows)} material rows, ours equals the 16.402.2 value '
        f'(`cards-160402017.json`) on {m_old["same"]}, differs from it on {m_old["other"]}, and is not comparable on '
        f'{m_old["unknown"]}; ours equals the 15.535.29 value on {m_15535["same"]}, differs on {m_15535["other"]}, '
        f'not comparable on {m_15535["unknown"]}. A row counted as "equals" means the older file has no differing row for it.',
        f'- RoyaleSim versions: `{RS_PATH.name}` (16.402.19) is used. The older `cards-160402017.json` (16.402.2) differs '
        f'from it on {len(rs_versions)} card-level fields ({", ".join(sorted({c for c, *_ in rs_versions}))}), so it is not the same truth.',
        f'- CLIENT16402_VALUES: {overlay_ok} of {len(overlay_rows)} overlay values equal the 16.402.19 table as it stands; '
        f'{overlay_unmapped} not mapped. The overlay is already in the table, so applying it again changes nothing.',
        '- Crown-tower damage: gamedata stores a negative delta (e.g. -75) and RoyaleSim an effective percent (25 or 23). '
        'We convert ours with 100 + raw for negative raw, per RoyaleSim\'s stated convention. Ours is the first '
        'crownTowerDamagePercent in the base card; a spell\'s own area or projectile, or a unit, counts as its own. '
        'Values in a buff, a spawn chain or a unit\'s own area effect are UNCERTAIN.',
        f'- Blank 16.402 crown cells: RoyaleSim loads a blank cell as 100 (raw None). Where ours is not 100 and '
        f'RoyaleSim\'s only value is that blank, the row is UNCERTAIN, not a difference ({", ".join(blank_cards) or "none"}). '
        'The 15.535.29 table has a measured value on those cards.',
        '- Sub-units (death spawns, spawners, morphs, second units) are compared on base stats only, with the same rules as the card.',
        '- The material list is the brief\'s (hp, damage, speed, range, hit speed, cost, spawn counts). Load time, sight range, '
        'deploy time, spawn interval and spell radius/duration are compared but not material.',
        '- Nothing compares first-spawn timing or spawner radius (not in gamedata). Those are in (c).',
        '',
    ]
    if unsure_rows:
        lines += ['UNCERTAIN rows:', '', '| Body | Field | Ours | 16.402 | Note |', '|---|---|---|---|---|']
        for r in unsure_rows:
            lines.append(f'| {r.card}: {r.subject} | {r.field} | {r.ours} | {r.rs} | {r.note} |')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines) + '\n')

    print(f'C56: {len(c56_cards)} cards, any {len(c56_any)}, material {len(c56_mat)}')
    print(f'others: {len(oth_cards)} cards, any {len(oth_any)}, material {len(oth_mat)}')
    print('row kinds:', dict(kinds_count), '| material rows', len(mat_rows),
          '| vs 16.402.2:', dict(m_old), '| vs 15.535.29:', dict(m_15535))
    print('wrote', OUT_MD)


if __name__ == '__main__':
    main()
