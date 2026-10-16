"""Side-table fc cut for the full card scope (pin key `fc_side_cut`, installed by bot/cards/scope.py).

lopp_fast's fc cut (`config_need`, ConfigCache, _ConfigJson) keeps only the referenced cards, but every name-keyed
side table whole. Under scope=full those tables grow from 95 KB to 795 KB (death_children 21 KB -> 358 KB, Mirror's
`level12:` copies, bomb_children, soul_skeletons), so every fc root carries them: the cut config passes 1 MiB, and
LearnedPool.begin (`len(parts[1]) < 1 << 20`) stops treating it as an fc root and re-ships the whole config to
every worker on every decision (reports/cards/runtime/SCOPE.md §5b).

This cut also keeps only the side-table entries a root can reach: an entry is kept when its key appears as a
string anywhere in the root's players/entities/pending casts or in a kept card's config entry, or (transitively) in
another kept entry (Golem -> Golemite, LavaHound -> pups, level12 payloads). The native looks side tables up by
those names only (same contract as config_need: "the native only looks cards up by name"); the root-parity tool
checks every rollout value against the uncut root. soul_skeletons/soul_offsets (lists) stay iff a SkeletonKing
string is reachable.

install() patches lopp_fast.ConfigCache (pool workers; forked workers inherit it, spawned macOS workers do not, so
they keep the cards-only cut: same values, slower parse) and _ConfigJson.dumps (the planner's own root payloads).
Process-wide and idempotent; nothing is patched unless the pin set asks for it.
"""
from __future__ import annotations

import json

SIDE = ('death_areas', 'death_objects', 'death_children', 'spirit_areas', 'production_children', 'spawn_areas',
        'ability_bombs', 'bomb_children')
GATED = {'soul_skeletons': 'SkeletonKing', 'soul_offsets': 'SkeletonKing'}


def strings(obj, out=None):
    """Every string value and dict key anywhere in obj."""
    out = set() if out is None else out
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, str):
            out.add(o)
        elif isinstance(o, dict):
            out.update(o.keys())
            stack.extend(v for v in o.values() if isinstance(v, (str, dict, list)))
        elif isinstance(o, list):
            stack.extend(v for v in o if isinstance(v, (str, dict, list)))
    return out


class SideCut:
    def __init__(self, cfg):
        self.card_strings = {n: frozenset(strings(v)) for n, v in cfg['cards'].items()}
        self.entries = [(t, k, frozenset(strings(v)), json.dumps(k) + ':' + json.dumps(v))
                        for t in SIDE if isinstance(cfg.get(t), dict) for k, v in cfg[t].items()]
        self.tables = [t for t in SIDE if isinstance(cfg.get(t), dict)]
        self.gated = {k: json.dumps(cfg[k]) for k in GATED if k in cfg}
        self.base = json.dumps({k: v for k, v in cfg.items() if k != 'cards' and k not in SIDE and k not in GATED})[1:-1]
        self._text = {}

    def keep(self, need, state):
        """Indices of the kept side entries for cards `need` and state strings `state`."""
        S = set(state)
        for n in need:
            S |= self.card_strings[n]
        kept, grew = set(), True
        while grew:
            grew = False
            for i, (_, k, inner, _) in enumerate(self.entries):
                if i not in kept and k in S:
                    kept.add(i)
                    S |= inner
                    grew = True
        gated = tuple(k for k, trigger in GATED.items() if k in self.gated and trigger in S)
        return frozenset(kept), gated

    def other(self, kept, gated):
        """The config text minus "cards", with only the kept side entries (no braces)."""
        key = (kept, gated)
        if key not in self._text:
            parts = [self.base] if self.base else []
            for t in self.tables:
                body = ','.join(text for i, (tt, _, _, text) in enumerate(self.entries) if tt == t and i in kept)
                parts.append(json.dumps(t) + ':{' + body + '}')
            parts += [json.dumps(k) + ':' + self.gated[k] for k in gated]
            self._text[key] = ','.join(parts)
        return self._text[key]


def mirror_need(cards, players, available):
    """config_need keeps literal names only, but Mirror plays `level12:<last_card>` (scripts.rs / lib.rs look up
    config.cards["level12:" + last_card]). For each player holding Mirror in hand or cycle, keep the level-12 payload
    of every card that can become that player's last_card during a rollout: its hand, cycle and current last_card."""
    extra = set()
    for p in players:
        own = [c for c in list(p.get('hand') or []) + list(p.get('cycle') or []) if c]
        if 'Mirror' not in own:
            continue
        for c in own + [p.get('last_card')]:
            if c and c != 'Mirror' and 'level12:' + c in available:
                extra.add('level12:' + c)
    return tuple(sorted(set(cards) | extra)) if extra - set(cards) else cards


def install():
    from bot.search import lopp_fast as lf
    if getattr(lf, '_side_cut_installed', False):
        return
    init, payload, need = lf.ConfigCache.__init__, lf.ConfigCache.payload, lf.config_need

    def cc_init(self, text):
        init(self, text)
        self.side = SideCut(json.loads(text))

    def cc_payload(self, head, tail):
        if 'side' not in self.__dict__:           # built before install(): the cards-only cut
            return payload(self, head, tail)
        dec = json.JSONDecoder()
        try:
            players = dec.raw_decode(head, head.index('"players":') + 10)[0]
            entities = dec.raw_decode(head, head.index('"entities":') + 11)[0]
            pending = dec.raw_decode(tail, tail.index('"pending_casts":') + 16)[0]
        except ValueError:
            return head + self.full + tail
        cards = need(players, entities, pending, self.cards)
        if cards is None:
            return head + self.full + tail
        cards = mirror_need(cards, players, self.cards)
        kept, gated = self.side.keep(cards, strings([players, entities, pending]))
        key = (cards, kept, gated)
        if key not in self.cut:
            self.cut[key] = ('{' + self.side.other(kept, gated) + ',"cards":{' +
                             ','.join(self.cards[n] for n in cards) + '}}')
        return head + self.cut[key] + tail

    dumps = lf._ConfigJson.dumps

    def cj_dumps(self, obj, *args, **kw):
        if (not self.cut or args or kw or type(obj) is not dict or obj.get('config') is not self._config
                or list(obj)[-1] != 'config'):
            return dumps(self, obj, *args, **kw)
        players, entities, pending = obj['players'], obj.get('entities', ()), obj.get('pending_casts', ())
        cards = need(players, entities, pending, self._config['cards'])
        if cards is None:
            return dumps(self, obj, *args, **kw)
        cards = mirror_need(cards, players, self._config['cards'])
        side = self.__dict__.get('_side')
        if side is None:
            side = self._side = SideCut(self._config)
            self._side_cards = {n: self._json.dumps(n) + ':' + self._json.dumps(v)
                                for n, v in self._config['cards'].items()}
        kept, gated = side.keep(cards, strings([players, list(entities), list(pending)]))
        key = ('side', cards, kept, gated)
        if key not in self._cut:
            self._cut[key] = ('{' + side.other(kept, gated) + ',"cards":{' +
                              ','.join(self._side_cards[n] for n in cards) + '}}')
        rest = self._json.dumps({k: v for k, v in obj.items() if k != 'config'})
        self.hits += 1
        return (rest[:-1] + ', ' if len(rest) > 2 else '{') + '"config": ' + self._cut[key] + '}'

    lf.ConfigCache.__init__, lf.ConfigCache.payload, lf._ConfigJson.dumps = cc_init, cc_payload, cj_dumps
    lf._side_cut_installed = True
