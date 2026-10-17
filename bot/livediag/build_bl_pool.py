"""Battle Log opponent-deck pool v2 for the L16 driver (bot lead live-diag): v1 (the LIVE LEAD's 2026-10-16 Battle Log,
91 rows / 49 distinct decks) + the s73 Royal Arena Battle Log rows that are fully identified and fully supported.

    python3 -m bot.livediag.build_bl_pool --v1 V1.jsonl --add S73.jsonl --vocab vocab-combined.json --out POOL.jsonl

Rules (BOT LEAD 2026-10-17):
- a row with any null card identity is dropped (recorded);
- hero / evo forms: the sim plays base cards only (vocab-combined has no form variants), so a form is mapped to its base
  card and recorded per row (`form_mapped`);
- a deck with a card outside the supported set (vocab meta.cards + meta.deckopt_extra_cards: C56 + 7 deck-search extras,
  exactly what v1's 49 decks use) is excluded (recorded with the unsupported cards), since the strong opponent's runtime
  and the translator vocab cannot play it;
- dedupe vs v1: a new deck whose sorted engine-name card set equals one of v1's distinct decks is dropped (recorded);
  duplicates WITHIN the new rows are kept as rows (row frequency = weight, as in v1).
v1 rows come first, unchanged, so v1 indices are stable. Levels in the rows are kept for the secondary account-level
prior only; play evals stay L16 both sides. Writes POOL.jsonl and POOL.manifest.json (sha256s, counts, every decision).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--v1', required=True, type=Path)
    ap.add_argument('--add', required=True, type=Path, action='append', help='Battle Log jsonl(s), in order (v3: s73 then s74)')
    ap.add_argument('--vocab', required=True, type=Path, help='supported set = meta.cards + deckopt_extra_cards + v3_extra_cards')
    ap.add_argument('--hold', default='', help='comma-separated engine cards excluded with a flag (v3: ElectroWizard until live16402d)')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--name', default='battlelog-v2', help='pool name in the manifest (v2.1: the s73-m18 correction)')
    ap.add_argument('--correction', action='append', default=[], type=Path,
                    help='correction receipt json(s) applied in --add (recorded with sha256 in the manifest)')
    a = ap.parse_args(argv)
    from bot.fullpool.cards import engine_name
    vocab = json.loads(a.vocab.read_text())
    supported = set(vocab['meta']['cards']) | set(vocab['meta']['deckopt_extra_cards']) | set(vocab['meta'].get('v3_extra_cards', ()))
    hold = set(filter(None, a.hold.split(',')))
    v1 = [json.loads(l) for l in a.v1.read_text().splitlines() if l.strip()]
    distinct = []
    for r in v1:
        d = sorted(engine_name(c) for c in r['opp_deck'])
        if d not in distinct:
            distinct.append(d)
    assert not {c for d in distinct for c in d} - supported, 'v1 outside the supported set'
    added, decisions = [], []
    for r in (json.loads(l) for f in a.add for l in f.read_text().splitlines() if l.strip()):
        deck, forms = r.get('opp_deck') or [], r.get('opp_forms') or [None] * 8
        row = dict(run=r.get('run'), deck=deck)
        if len(deck) != 8 or not all(deck):
            decisions.append(dict(row, decision='dropped: null card identity'))
            continue
        mapped = {c: f for c, f in zip(deck, forms) if f not in (None, 'normal')}
        en = sorted(engine_name(c) for c in deck)
        out = sorted(c for c in en if c not in supported)
        if out:
            decisions.append(dict(row, decision='excluded: unsupported cards', unsupported=out, forms=mapped))
            continue
        held = sorted(c for c in en if c in hold)
        if held:
            decisions.append(dict(row, decision='held: card awaiting a later runtime', held=held, forms=mapped))
            continue
        if en in distinct:
            decisions.append(dict(row, decision='dropped: duplicate of a v1 deck', forms=mapped))
            continue
        rr = dict(r, pool=f'{a.name}-add', pekka='Pekka' in en, form_mapped={c: f'{f}->base' for c, f in mapped.items()})
        added.append(rr)
        decisions.append(dict(row, decision='added', forms=mapped,
                              duplicate_within_new=any(sorted(engine_name(c) for c in x['opp_deck']) == en for x in added[:-1])))
    rows = v1 + added
    a.out.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    d2 = list(distinct)
    for r in added:
        d = sorted(engine_name(c) for c in r['opp_deck'])
        if d not in d2:
            d2.append(d)
    corrections = [dict(path=str(c), sha256=sha(c), receipt=json.loads(c.read_text())) for c in a.correction]
    man = dict(pool=a.name, corrections=corrections, rows=len(rows), distinct=len(d2), v1_rows=len(v1), v1_distinct=len(distinct),
               added_rows=len(added), added_distinct=len(d2) - len(distinct), out_sha256=sha(a.out),
               inputs=dict(v1=str(a.v1), v1_sha256=sha(a.v1), add=[str(f) for f in a.add], add_sha256=[sha(f) for f in a.add],
                           vocab=str(a.vocab), vocab_sha256=sha(a.vocab)),
               supported_cards=sorted(supported), held_cards=sorted(hold), decisions=decisions,
               note='v1 rows first and unchanged; forms mapped to base cards (the sim has no form variants); levels kept '
                    'for the secondary account-level prior only (play evals L16 both sides)')
    Path(str(a.out).replace('.jsonl', '.manifest.json')).write_text(json.dumps(man, indent=1) + '\n')
    print(json.dumps({k: man[k] for k in ('pool', 'rows', 'distinct', 'v1_rows', 'v1_distinct', 'added_rows',
                                           'added_distinct', 'out_sha256')}))
    for x in decisions:
        print(x['run'], x['decision'], x.get('unsupported', ''), x.get('forms', ''))


if __name__ == '__main__':
    main()
