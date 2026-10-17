"""Card table for bot/livediag/behaviour_diag.py (SC1 add-on, cycle-model owner; analysis only), from the runtime config:
card_cost, card_unit_value (cost / units deployed), body_card (body -> the card with the lowest unit value among cards
deploying it), body_hp / card_hp (max HP at level 11, single-body cards), spell (radius: spread radius for multi-
projectile spells; damage x waves). Usage (runtime env as for the L16 driver): python cardtable.py OUT.json
"""
import json, os, sys
from bot.players.runtime import Runtime
from bot.live.births import CardBodies
rt = Runtime(); R = rt.R; cb = CardBodies(rt); names = R.builder.token_names
out = dict(card_cost={}, card_unit_value={}, body_card={}, spells={}, body_hp={}, spell={}, card_hp={}, wincon=[], body_cards=[])
for card, c in R.config['cards'].items():
    if ':' in card: continue
    cost = float(c.get('cost', 0)); out['card_cost'][card] = cost
    main = cb.main.get(card) or []
    n = sum(cnt for _, cnt in main) if main and isinstance(main[0], tuple) and len(main[0]) == 2 else 0
    if main:
        try:
            n = sum(int(cnt) for (_b, cnt) in main)
        except Exception:
            n = len(main)
        n = n // 2      # the config lists every unit template twice (Knight: 2 entries for 1 knight; see SC1 RESULTS)
        if n:
            out['card_unit_value'][card] = round(cost / n, 4)
            for (b, cnt) in main:
                tok = int(b[0]) if isinstance(b, tuple) else int(b)
                nm = names[tok] if 0 <= tok < len(names) else str(tok)
                hps = {float(t.get('stats', {}).get('max_hp', 0)) for g in c.get('units', ())
                       for t in (g if isinstance(g, list) else [g]) if t.get('class') in ('Troop', 'Building')}
                if len(main) == 1 and hps:                # single-body cards only (templates carry no token); max = conservative
                    out['body_hp'][nm] = max(out['body_hp'].get(nm, 0.0), max(hps))
                    out['card_hp'][card] = max(hps)
                prev = out['body_card'].get(nm)
                if prev is None or out['card_unit_value'][card] < out['card_unit_value'].get(prev, 1e9):
                    out['body_card'][nm] = card
    sp = c.get('spell') or {}
    if sp.get('damage'):
        multi = int(sp.get('multiple_projectiles', 1) or 1) > 1
        out['spell'][card] = dict(radius=float(sp.get('spread_radius') if multi and sp.get('spread_radius') else sp.get('radius', 0)),
                                  damage=float(sp['damage']) * int(sp.get('damage_waves', 1) or 1), level=sp.get('level'))
    groups = [t for g in c.get('units', ()) for t in (g if isinstance(g, list) else [g])]
    if any(t.get('class') in ('Troop', 'Building') for t in groups):
        out['body_cards'].append(card)
    if any(t.get('class') in ('Troop', 'Building') and (t.get('stats') or {}).get('only_buildings') for t in groups):
        out['wincon'].append(card)        # win condition (data rule): a unit that targets only buildings
    if not any(t.get('class') in ('Troop', 'Building') for t in groups):
        info = {}
        for k in ('radius', 'area_radius', 'crown_tower_damage', 'tower_damage', 'damage'):
            if k in c: info[k] = c[k]
        for t in groups:
            st = t.get('stats', {})
            for k in ('radius', 'area_damage_radius', 'crown_tower_damage', 'damage', 'tower_damage'):
                if k in st and k not in info: info[k] = st[k]
        out['spells'][card] = info
json.dump(out, open(sys.argv[1], 'w'), indent=1, sort_keys=True)
print(len(out['card_cost']), len(out['card_unit_value']), len(out['body_card']), {k: out['spells'][k] for k in ('Zap', 'Fireball', 'Arrows', 'TheLog') if k in out['spells']})
