"""Read-only s27-m02 protocol, command evidence and public-only summaries.

No runtime imports: fixtures can exercise input/driver failures without models.
The recorded driver alone owns reservations. Shadow decisions are observations.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path

WAIT = 2304
BASE = 'K4L-R-gs-rw-fc'
UNVERIFIED = dict(n=234, poll=170, action=233)
SCOPE_SHA256 = dict(original_sha256='98ffccd04c44d55d255f104c0f969559c421e02f0e6e8293f9a9fa0165227ec1',
                    restricted_sha256='8ef16962fd617bfa5662b058637ee876c6b136a8730d9a355ed951e405e897a1')
INPUT_SHA256 = {
    'perception.jsonl': '0238b560389741ad4d84240af6bf4d9d786d57c858a4abafa94567ab17a764c2',
    'session-config.json': 'dc77804fbe52b541341dd974157f4e72b0b6849a315dbf436dbd7bf6a285457e',
    'decisions.jsonl': '404cc82ea4ab0d9cb6eacf8e21189547b732b6eb252a216653d8ecf945233835',
    'events.jsonl': 'd3b38c45ac99d86bf3fc1bdbba916536fbe1eeed83c10d95cec23c25814efb70',
    'frames.jsonl': 'fe8e5878afda53123d7ed55cf6e78ce0cfd022de94a4a09ba2dc5aa3f878fc26',
    'taps.jsonl': 'cad3008c02debbe1cd7b2ac73869b504e101a7c559b69926f6caddd8a9b69a17',
    'session.json': 'e566a2ed5f48cec65fab5046bfda5f2f2aa6229405102f6d4cea9720db96ddd8',
}


def plain(value):
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'tolist'):
        return value.tolist()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, '__dict__'):
        return plain(vars(value))
    raise TypeError(f'cannot serialize public evidence: {type(value)}')


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def jsonl(raw):
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def unique(rows, key):
    out = {}
    for row in rows:
        k = row[key]
        if k in out:
            raise ValueError(f'duplicate {key}: {k}')
        out[k] = row
    return out


def load_inputs(directory):
    """Pin the copied public logs; never consult battle-log enemy decks/levels."""
    directory = Path(directory)
    raw = {name: (directory / name).read_bytes() for name in INPUT_SHA256}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}
    if hashes != INPUT_SHA256:
        raise ValueError(f'input hashes differ: {[k for k in hashes if hashes[k] != INPUT_SHA256[k]]}')
    data = {name.split('.')[0]: (jsonl(value) if name.endswith('.jsonl') else json.loads(value))
            for name, value in raw.items()}
    decisions = unique(data['decisions'], 'n')
    perceptions = unique(data['perception'], 'n')
    unique(data['decisions'], 'poll')
    unique(data['taps'], 'ack')
    starts = [e for e in data['events'] if e['ev'] == 'match_start']
    ends = [e for e in data['events'] if e['ev'] == 'match_end']
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError('expected exactly one recorded battle')
    cfg = data['session-config']
    if (cfg['translator']['cls'] != 'bot.live.translate.LiveTranslator'
            or cfg['session']['cls'] != 'bot.live.translate.LiveSession'
            or cfg['translator']['unknown_card'] != 'drop'
            or cfg['translator']['plays_from'] != 'births'):
        raise ValueError('unsupported recorded facade contract')
    acks = set(unique(data['taps'], 'ack'))
    for n, d in decisions.items():
        if n not in perceptions:
            raise ValueError(f'decision frame missing: {n}')
        command(d, acks)
    ns = list(perceptions)
    if ns != sorted(ns) or any(b['timestamp_ms'] <= a['timestamp_ms']
                             for a, b in zip(data['perception'], data['perception'][1:])):
        raise ValueError('perception order is not strictly increasing')
    return data, hashes, decisions, acks, starts[0]


def command(row, acks):
    """Five acknowledged taps plus ONE explicitly conditional internal reservation.

    Owner-authorized frame234/action233 is a logged session action, NOT a sixth
    tap/ack/verified play. Later unchanged HUD inference is explicitly conditional.
    Every other unconfirmed command remains an error.
    """
    if row is None:
        return WAIT, 0
    if row.get('error') or any((row.get('stats') or {}).get(k)
                               for k in ('error', 'native_failure', 'search_failures')):
        raise ValueError(f'recorded decision failed: {row}')
    action = int(row['action'])
    if command_kind(row) == 'unverified_internal_reservation':
        return action, 0
    if action < WAIT:
        if (not row.get('submitted') or row.get('tap_id') not in acks
                or row.get('tap') or not row.get('card') or action < 0):
            raise ValueError(f'unconfirmed/refused recorded command at frame {row["n"]}')
    elif row.get('submitted') or action != WAIT:
        raise ValueError('inconsistent recorded WAIT/submission')
    selected = (row.get('stats') or {}).get('action')
    # The live writer omitted Decision.wait_ticks. Only explicit timed-wait IDs
    # justify recovering a duration; other WAITs carry no invented reservation.
    return action, {2400: 10, 2401: 20, 2402: 40}.get(selected, 0)


def command_kind(row):
    if row is None or row['action'] == WAIT:
        return 'wait'
    if (all(row.get(k) == v for k, v in UNVERIFIED.items()) and row.get('submitted') is False
            and not any(row.get(k) for k in ('tap', 'tap_id', 'card', 'error'))):
        return 'unverified_internal_reservation'
    return 'acknowledged_tap' if row.get('submitted') else 'unconfirmed'


def in_window(clock_s):
    """Inclusive displayed public seconds 2:56 through 2:14 (floor, not OCR)."""
    return 134 <= math.floor(float(clock_s)) <= 176


def opportunity_roster(perceptions, decisions):
    """Predeclare the fixed denominator from recorded public clocks/search gates."""
    frames = unique(perceptions, 'n')
    rows = list(decisions)
    unique(rows, 'n')
    unique(rows, 'poll')
    roster = []
    for d in rows:
        frame = frames[d['n']]
        if (d.get('stats') or {}).get('source') == 'search' and in_window(frame['clock_s']):
            if int(d['poll']) != d['poll'] or d['poll'] % 10:
                raise ValueError(f'off-cadence recorded search: {d["n"]}/{d["poll"]}')
            roster.append(dict(n=d['n'], tick=int(d['poll']), clock_s=frame['clock_s']))
    return sorted(roster, key=lambda r: (r['tick'], r['n']))


def tower_audit(record):
    """Keep literal public fractions; compare OCR numbers with known public L6 maxima.

    The driver already divided hp_read by its inferred actual maximum, rounded
    to four decimals. The first enemy king reading may precede level inference.
    An inconsistency is evidence, never a reason to rewrite the perception.
    """
    rows = []
    keys = set()
    for t in record['towers']:
        key = (int(t['owner']), t['kind'], None if t['kind'] == 'king' else t['side'])
        if key in keys:
            raise ValueError(f'duplicate public tower: {key}')
        keys.add(key)
        maximum = 3312 if t['kind'] == 'king' else 2030
        fraction = float(t['hp_frac'])
        if not 0 <= fraction <= 1 or (not t['alive'] and fraction != 0):
            raise ValueError(f'invalid public tower fraction: {t}')
        number = t.get('hp_read')
        rows.append(dict(owner=key[0], kind=key[1], side=key[2], alive=t['alive'],
            hp_frac=fraction, hp_read=number, public_l6_max_hp=maximum,
            reconstructed_l6_hp=fraction * maximum,
            number_consistent=number is None or abs(number - fraction * maximum) <= maximum * .000051))
    if keys != {(o, k, s) for o in (0, 1) for k, s in
                (('king', None), ('princess', 'left'), ('princess', 'right'))}:
        raise ValueError('six explicit public tower records are required')
    return rows


def action_details(action, wait_ticks, hand):
    action = int(action)
    if action == WAIT:
        return dict(action=action, wait_ticks=int(wait_ticks), card=None, row=None, col=None)
    if not 0 <= action < WAIT:
        raise ValueError(f'invalid shadow action: {action}')
    slot, tile = divmod(action, 576)
    row, col = divmod(tile, 18)
    return dict(action=action, wait_ticks=int(wait_ticks), card=hand[slot], row=row, col=col)


def root_tower_audit(physics, fractions, arm):
    """Match actual crown HP to this arm's unchanged public fractions, no RNG."""
    rows = []
    for t in physics['towers']:
        king = t['name'] == 'KingTower'
        slot = (2 if king else int(t['x'] >= 9)) + 3*int(t['owner'])
        maximum = t['max_hp']
        wanted_max = (3312 if king else 2030) if arm == 'B' else maximum
        expected_hp = float(fractions[slot]) * maximum
        rows.append(dict(owner=t['owner'], name=t['name'], x=t['x'], public_fraction=float(fractions[slot]),
            actual_hp=t['hp'], actual_max_hp=maximum, expected_max_hp=wanted_max,
            consistent=maximum == wanted_max and abs(t['hp']-expected_hp) <= max(1., maximum)*1e-6))
    return rows


def opportunity_statuses(rows, roster, fatal_error):
    """One success/error/not_reached entry per expected key, without invented states.

    A fatal pre-row error belongs to its planned frame. A post-row error (e.g.
    queue replacement contradiction) invalidates that key's apparent success.
    Original rows remain intact; not-reached entries contain no arm decisions.
    """
    unique(roster, 'n')
    unique(roster, 'tick')
    statuses, successful, unexpected = [], [], []
    planned = {r['n'] for r in roster}
    for r in rows:
        if r['opportunity'] and r['n'] not in planned:
            unexpected.append(dict(n=r['n'], tick=r['tick']))
    for expected in roster:
        found = [r for r in rows if r['n'] == expected['n'] and not r['catch_up']]
        entry = dict(expected)
        if fatal_error and fatal_error.get('n') == expected['n']:
            entry.update(status='error', error=fatal_error)
        elif not found:
            entry.update(status='not_reached', reason='No recorded public decision state was reached.')
        elif (len(found) != 1 or found[0]['tick'] != expected['tick'] or not found[0]['opportunity']):
            entry.update(status='error', error='Duplicate/mismatched recorded opportunity row.')
        elif any(found[0]['arms'].get(a, {}).get('error') or not found[0]['arms'].get(a, {}).get('searched')
                 or not isinstance(found[0]['arms'].get(a, {}).get('chosen'), dict) for a in ('A', 'B')):
            entry.update(status='error', error='Both shadow decisions did not complete successfully.')
        else:
            entry['status'] = 'success'
            successful.append(found[0])
        statuses.append(entry)
    return statuses, successful, unexpected


def summary(rows, driver, translator_stats, roster, fatal_error=None):
    """Always use the predeclared denominator, including pre-row/future failures."""
    statuses, pairs, unexpected = opportunity_statuses(rows, roster, fatal_error)
    expected = len(roster)
    failed = sum(r['status'] == 'error' for r in statuses)
    unvisited = sum(r['status'] == 'not_reached' for r in statuses)
    opportunities = [r for r in rows if r['opportunity']]
    differences = [r for r in pairs if any(r['arms']['A']['chosen'][k] != r['arms']['B']['chosen'][k]
                                         for k in ('action', 'wait_ticks'))]
    counts = {a: dict(cannon_available=sum(r['arms'][a].get('cannon_available', False) for r in opportunities),
                      cannon_affordable=sum(r['arms'][a].get('cannon_affordable', False) for r in opportunities),
                      cannon_chosen=sum(r['arms'][a].get('chosen', {}).get('card') == 'Cannon' for r in pairs),
                      cannon_home_defense=sum(r['arms'][a].get('cannon_home_defense', False) for r in pairs),
                      cpu_s=sum(r['arms'][a].get('cpu_s', 0.) for r in rows),
                      wall_s=sum(r['arms'][a].get('wall_s', 0.) for r in rows),
                      native_failures=sum(sum(r['arms'][a].get('failures', {}).values()) for r in rows))
              for a in ('A', 'B')}
    errors = [dict(n=r['n'], tick=r['tick'], arm=a, error=v['error']) for r in rows
              for a, v in r['arms'].items() if v.get('error')]
    errors += [dict(n=r['n'], tick=r['tick'], error=r['error'], stage='opportunity')
               for r in statuses if r['status'] == 'error'
               and not any(e['n'] == r['n'] and e['tick'] == r['tick'] for e in errors)]
    roots = sum(r['arms']['B'].get('root_calls', 0) for r in rows)
    checks = dict(recorded_commands_match=not driver['mismatches'],
                  complete_recorded_decisions=not driver['missing_decisions'],
                  zero_shadow_errors=not errors, matched_all_opportunities=bool(expected) and len(pairs) == expected,
                  all_opportunities_reached=unvisited == 0, zero_opportunity_errors=failed == 0,
                  no_unexpected_opportunities=not unexpected, zero_fatal_errors=fatal_error is None,
                  search_observed=bool(pairs), exact_B_roots_observed=roots > 0,
                  zero_native_failures=all(v['native_failures'] == 0 for v in counts.values()),
                  zero_submit_refusals=not translator_stats.get('submit_refused', 0))
    examples = [dict(n=r['n'], tick=r['tick'], clock_s=r['clock_s'],
                     A=r['arms']['A'].get('chosen'), B=r['arms']['B'].get('chosen'),
                     threats=r['arms']['B'].get('threats')) for r in pairs
                if any(r['arms'][a].get('cannon_home_defense') for a in ('A', 'B'))]
    return dict(protocol='s27-recorded-world-v1', diagnostic_only=True,
        conditional_reconstruction='Frame234/action233 is an UNVERIFIED INTERNAL RESERVATION; later HUD-derived play/context is conditional, never an acknowledged tap/verified actual play.',
        claims='Chosen-action changes on a recorded future world; no outcome or causal estimate.',
        checks=checks, pass_checks=all(checks.values()), opportunities=expected,
        expected=expected, attempted=expected-unvisited, successful=len(pairs), failed=failed, unvisited=unvisited,
        opportunity_statuses=statuses, unexpected_opportunities=unexpected, fatal_error=fatal_error,
        matched=len(pairs), action_differences=len(differences), arms=counts, errors=errors,
        first_differences=[dict(n=r['n'], tick=r['tick'], clock_s=r['clock_s'],
                               A=r['arms']['A']['chosen'], B=r['arms']['B']['chosen'])
                           for r in differences[:10]], cannon_home_defense_examples=examples[:20],
        B_root_calls=roots, driver=driver, translator_stats=translator_stats,
        public_clock_range=[rows[0]['clock_s'], rows[-1]['clock_s']] if rows else None)
