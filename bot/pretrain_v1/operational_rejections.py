"""Read-only executed-command accounting. Never feeds policy history or training.

Rates use executed taps only. Pending identity may be absent in frozen eval
rows; that limits per-card submitted/pending counts, never the denominator.
"""
from __future__ import annotations

import json
from pathlib import Path

FIELDS = ('submitted', 'executed', 'accepted', 'rejected', 'pending')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def integer(value):
    return type(value) is int and value >= 0


def known_cards():
    catalog = json.loads((Path(__file__).parent/'catalog/catalog.json').read_text())
    return {c['name'] for c in catalog['cards']}


def empty():
    return dict.fromkeys(FIELDS, 0)


def validate_counts(c):
    require(all(integer(c[k]) for k in FIELDS), 'invalid command counts')
    require(c['submitted'] == c['executed']+c['pending'] and
            c['executed'] == c['accepted']+c['rejected'], 'command accounting mismatch')


def rate(c):
    return c['rejected']/c['executed'] if c['executed'] else None


def comparison(current, baseline=None):
    """Strict >2x using integer cross multiplication, with no pseudocounts."""
    if baseline is None or not baseline['executed'] or not current['executed']:
        return dict(status='unavailable', alert=None)
    return dict(status='available', alert=(current['rejected']*baseline['executed'] >
                                          2*baseline['rejected']*current['executed']))


def seat_value(mapping, seat):
    require(type(seat) is int and seat in (0, 1), 'unknown seat identity')
    require(isinstance(mapping, dict), 'missing seat mapping')
    require(not (seat in mapping and str(seat) in mapping), 'ambiguous seat identity')
    require(set(map(str, mapping)) == {'0', '1'}, 'unknown/missing seat identity')
    return mapping[seat] if seat in mapping else mapping[str(seat)]


def command(row, cards):
    require(isinstance(row, (list, tuple)) and len(row) == 4, 'invalid execution row')
    tick, card, action, accepted = row
    require(integer(tick) and type(action) is int and 0 <= action < 2304 and
            type(accepted) is bool, 'invalid execution tick/action/outcome')
    require(isinstance(card, str) and card in cards, f'unknown command card: {card!r}')
    return tick, card, action, accepted


def game_counts(game, seat, *, cards=None, submissions=None, delay=27):
    """Validate actual queue counters against every executed log entry.

    Optional submissions are immutable sampled commands, including version and
    policy_sha256. Matching uses actual lag, action and card, never finish-time
    policy. Missing per-card pending identity in frozen logs stays unavailable.
    """
    cards = known_cards() if cards is None else cards
    ch = seat_value(game['channels'], seat)
    logs = seat_value(game['play_log'], seat)
    total = dict(submitted=ch['submitted'], executed=ch['executed'],
                 rejected=ch['rejected'], pending=ch['pending_at_end'],
                 accepted=ch['executed']-ch['rejected'])
    validate_counts(total)
    require(isinstance(logs, (list, tuple)) and len(logs) == total['executed'], 'execution log count mismatch')
    parsed = [command(row, cards) for row in logs]
    require(all(a[0] < b[0] for a, b in zip(parsed, parsed[1:])), 'unordered/duplicate executions')
    require(sum(not row[3] for row in parsed) == total['rejected'], 'rejection log mismatch')
    require(seat_value(game['accepted'], seat) == total['accepted'], 'accepted log mismatch')
    if 'plays' in game:
        require(seat_value(game['plays'], seat) == total['executed'], 'plays log mismatch')
    by_card = {card: empty() for card in sorted(cards)}
    for _, card, _, ok in parsed:
        by_card[card]['executed'] += 1
        by_card[card]['accepted' if ok else 'rejected'] += 1
    by_snapshot = {}
    if submissions is not None:
        require(len(submissions) == total['submitted'], 'sampled submission count mismatch')
        lookup = {}
        for sub in submissions:
            tick, card, action, _ = command((sub['tick'], sub['card'], sub['action'], True), cards)
            require(integer(sub['version']) and isinstance(sub['policy_sha256'], str) and
                    len(sub['policy_sha256']) == 64, 'unknown sampled policy identity')
            key = tick+delay, card, action
            require(key not in lookup, 'duplicate sampled command')
            lookup[key] = sub
            identity = str(sub['version'])
            snap = by_snapshot.setdefault(identity, dict(policy_sha256=sub['policy_sha256'],
                counts=empty(), by_card={c: empty() for c in sorted(cards)}))
            require(snap['policy_sha256'] == sub['policy_sha256'], 'version has multiple policy identities')
            for c in (snap['counts'], snap['by_card'][card], by_card[card]):
                c['submitted'] += 1
                c['pending'] += 1
        for tick, card, action, ok in parsed:
            require((tick, card, action) in lookup, 'execution has no sampled command provenance')
            sub = lookup.pop((tick, card, action))
            snap = by_snapshot[str(sub['version'])]
            for c in (snap['counts'], snap['by_card'][card]):
                c['executed'] += 1
                c['accepted' if ok else 'rejected'] += 1
                c['pending'] -= 1
            by_card[card]['pending'] -= 1
        require(len(lookup) == total['pending'], 'pending provenance mismatch')
        for sub in lookup.values():
            require(sub['tick'] <= game['ticks'] <= sub['tick']+delay,
                    'unexecuted command overdue before game stop')
        for c in by_card.values():
            validate_counts(c)
    else:
        # Some frozen terminal rows save only the queue count, not its cards.
        # No card is guessed from the last execution or the final hand.
        for c in by_card.values():
            c['submitted'] = c['executed'] if not total['pending'] else None
            c['pending'] = 0 if not total['pending'] else None
    return dict(counts=total, by_card=by_card, by_snapshot=by_snapshot,
                unattributed_pending=total['pending'] if submissions is None else 0)


def merge(target, source):
    for key in FIELDS:
        target[key] = None if target[key] is None or source[key] is None else target[key]+source[key]


def aggregate(records, baseline=None):
    total, cards = empty(), {}
    for rec in records:
        merge(total, rec['counts'])
        for card, c in rec['by_card'].items():
            merge(cards.setdefault(card, empty()), c)
    def annotated(c, b):
        return dict(c, rejected_executed_rate=rate(c), comparison=comparison(c, b))
    return dict(counts=annotated(total, baseline['counts'] if baseline else None),
                by_card={card: annotated(c, baseline['by_card'].get(card) if baseline else None)
                         for card, c in sorted(cards.items())},
                unattributed_pending=sum(r.get('unattributed_pending', 0) for r in records))
