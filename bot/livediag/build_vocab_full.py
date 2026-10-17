"""Full-scope RoyaleSim translator vocabulary for Battle Log pool v3 (live-diag; exploration).

    python -m bot.livediag.build_vocab_full --base vocab-combined.json --out vocab-full.json --report report.json

The L16 driver translates RoyaleSim rows with a vocabulary built empirically per card (bot/players/royalesim_vocab.build:
paired demos in our engine and in RoyaleSim). vocab-combined.json covers C56 plus the 7 deck-search extras
(fullpool_eval.empirical_vocab). This builds every other full-scope card (C56 + bot/cards/scope.EXTRA_CARDS) the same way,
ONE CARD PER BUILD so a failure stays with its card. A card is supported only if its own build has no
unresolved units / projectiles / spells and no missing template, exactly fullpool_eval's acceptance rule for the 7
extras. Accepted rows are merged in only where the base lacks the key, so base values stay as measured. The result
goes through royalesim_translate.complete_vocab, and meta.v3_extra_cards lists the accepted cards. The report lists
every rejected card with its reasons (the list for the CARD LEAD).
Needs the full-scope runtime env (CLASHER_BOT_RUNTIME_PINS=live16402b-r3, as run-l16-cadence.sh).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--report', required=True, type=Path)
    ap.add_argument('--client', default='16.402')
    ap.add_argument('--cards', default='', help='comma-separated subset (default: every full-scope card the base lacks)')
    a = ap.parse_args(argv)
    from bot.players.runtime import Runtime
    from bot.players import royalesim_vocab as rv
    from bot.players.royalesim_translate import complete_vocab
    from bot.cards.scope import EXTRA_CARDS
    rt = Runtime()                           # bootstraps the runtime sys.path (c56_controller lives there)
    import c56_controller
    assert rt.pins.get('card_scope') == 'full', 'needs a full-scope pin set (live16402b-r3)'
    base = json.loads(a.base.read_text())
    have = set(base['meta']['cards']) | set(base['meta'].get('deckopt_extra_cards', ()))
    todo = [c for c in (a.cards.split(',') if a.cards else EXTRA_CARDS) if c and c not in have]
    measured = json.loads(json.dumps(base))
    report, accepted = {}, []
    saved = c56_controller.CARDS
    for card in todo:
        try:
            c56_controller.CARDS = (card,)
            extra = rv.build(rt, a.client)
        except BaseException as ex:          # a card the engine / RoyaleSim demo cannot run (pyo3 panics included)
            if isinstance(ex, (KeyboardInterrupt, SystemExit)):
                raise
            report[card] = dict(ok=False, error=f'{type(ex).__name__}: {ex}'[:300])
            print(card, 'ERROR', report[card]['error'], flush=True)
            continue
        finally:
            c56_controller.CARDS = saved
        unresolved_proj = sorted(set(extra['unresolved_projectiles']) - set(measured['projectiles'])
                                 - set(measured.get('no_counterpart_firers', ())))
        why = {k: v for k, v in dict(unresolved_units=extra['unresolved_units'], unresolved_projectiles=unresolved_proj,
                                     unresolved_spells=extra['unresolved_spells'], no_template=extra['no_template']).items() if v}
        report[card] = dict(ok=not why, **why)
        print(card, 'OK' if not why else why, flush=True)
        if why:
            continue
        accepted.append(card)
        for field in ('units', 'spells', 'projectiles', 'statics'):
            for key, value in extra[field].items():
                if key not in measured[field]:
                    measured[field][key] = value
    measured['meta']['v3_extra_cards'] = accepted
    measured['meta']['v3_base_sha256'] = hashlib.sha256(a.base.read_bytes()).hexdigest()
    measured = complete_vocab(rt, measured)
    a.out.write_text(json.dumps(measured, indent=1, sort_keys=True) + '\n')
    a.report.write_text(json.dumps(dict(base=str(a.base), client=a.client, accepted=accepted,
                                        rejected={c: r for c, r in report.items() if not r['ok']}), indent=1) + '\n')
    print(json.dumps(dict(accepted=len(accepted), rejected=sorted(c for c, r in report.items() if not r['ok']))))


if __name__ == '__main__':
    main()
