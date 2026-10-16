"""Live-perception aliasing for sim A/B arms (exploration).

The live loop's perception (e16 classes.json, built from katacr_to_clasher.json) labels an off-vocab opponent unit
with a C56 look-alike: MegaMinion -> Minions, BattleRam -> HogRider, Bomber -> Firecracker, Barbarians -> Knight,
Tombstone -> Cannon, SpearGoblins -> Goblins, GoblinCage -> Cannon. The translator (unknown_card='drop') then drops
whatever is still outside C56. Aliaser reproduces that at the OBSERVATION and BELIEF level for one seat, while the sim
keeps playing the true cards:

- card events (Information.events, the recorder rows that drive D1): a non-C56 opponent card X becomes alias(X), or the
  play is dropped if X has no C56 identity (spells and non-unit cards);
- the packet's entity_ids / opponent_history_ids / opponent_seen_card_ids: tokens of X's card and of every body the
  katacr class map attributes to a non-C56 source card become the alias card's token / the alias card's main body
  token. This follows the class map, so a C56 card's body that shares a sprite with an off-vocab card (e.g. a
  GoblinHut SpearGoblin) is aliased too, as it is live.
C56 cards and bodies the class map does not alias pass through unchanged. Our own deck must be C56 (e16).
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path

import numpy as np

from bot.fullpool.cards import C56, engine_name

REPO = Path(__file__).resolve().parents[2]
KATACR = (REPO / 'reports/bot/fullpool/ab/katacr_to_clasher.json',
          '6548c95eb5b1dae1')   # sha256 prefix of the LIVE LEAD's copy (scratch/live-lead-share, 2026-10-16)


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def alias_tables(path=None):
    """(card alias {true card: C56 alias or None}, body alias {body name: C56 body name}) from katacr_to_clasher."""
    from bot.cards.proxy_table import _C56_CARD_BODIES
    import hashlib
    path = Path(path or KATACR[0])
    data = path.read_bytes()
    if not hashlib.sha256(data).hexdigest().startswith(KATACR[1]):
        raise ValueError(f'{path}: sha256 does not match the pinned katacr_to_clasher.json')
    classes = json.loads(data)['classes']
    cards, bodies, own = {}, {}, {}
    for name, v in sorted(classes.items()):
        src = engine_name(v.get('source_card') or '', strict=False)
        if not src or src in C56:
            continue
        ident = engine_name(v.get('identity') or '', strict=False)
        alias = ident if ident in C56 else None
        if v.get('unit'):
            # a card play is read from its first birth: prefer the class of the card's own deployed body
            # (goblin-cage for GoblinCage, not its death-spawn goblin-brawler)
            mine = _norm(v.get('body') or name) in (_norm(src), _norm(src).rstrip('s'))
            if src not in cards or (mine and not own.get(src)):
                cards[src], own[src] = alias, mine
            if alias is not None and v.get('body'):
                bodies[v['body']] = _C56_CARD_BODIES.get(alias, alias)
        else:
            cards.setdefault(src, None)
    return cards, bodies


class Aliaser:
    """Per-seat view alias: the seat that observes (its OPPONENT's cards are aliased)."""

    def __init__(self, builder, seat, path=None):
        self.seat = seat
        self.cards, body_names = alias_tables(path)
        names = list(builder.token_names)
        by_norm = {}
        for t, n in enumerate(names):
            by_norm.setdefault(_norm(n), t)
        tok = {}
        unknown = int(builder.token_id(None))
        for card, alias in self.cards.items():
            if alias is None:
                continue
            for a, b in ((card, alias),):
                ta, tb = int(builder.token_id(a)), int(builder.token_id(b))
                if ta > 1 and tb > 1:
                    tok[ta] = tb
        for body, alias_body in body_names.items():
            ta = by_norm.get(_norm(body))
            tb = int(builder.token_id(alias_body))
            if ta is not None and ta > 1 and tb > 1 and ta != tb:
                tok.setdefault(ta, tb)
        self.dropped_cards = {int(builder.token_id(c)) for c, a in self.cards.items() if a is None} - {0, unknown}
        self.tok = tok
        self.lut = np.arange(max(len(names), 1 + max([*tok, *tok.values()], default=0)), dtype=np.int64)
        for a, b in tok.items():
            self.lut[a] = b
        self.counts = dict(events_aliased=0, events_dropped=0, packets=0)

    def name(self, card):
        """Alias of an OPPONENT card name: itself (C56), its C56 look-alike, or None (dropped)."""
        if card in C56 or card is None:
            return card
        return self.cards.get(card)

    def events(self, events):
        out = []
        for e in events:
            if getattr(e, 'kind', None) == 'card' and e.name not in C56:
                a = self.name(e.name)
                if a is None:
                    self.counts['events_dropped'] += 1
                    continue
                self.counts['events_aliased'] += 1
                e = replace(e, name=a)
            out.append(e)
        return tuple(out)

    def recorder(self, rows):
        out = []
        for r in rows:
            if r.get('kind') == 'card' and r.get('seat') != self.seat and r.get('name') not in C56:
                a = self.name(r.get('name'))
                if a is None:
                    continue
                r = dict(r, name=a)
            out.append(r)
        return out

    def _ids(self, a, *, drop_cards=False):
        a = np.asarray(a)
        m = self.lut[np.clip(a.astype(np.int64), 0, len(self.lut) - 1)].astype(a.dtype)
        if drop_cards and self.dropped_cards:
            m = np.where(np.isin(m, list(self.dropped_cards)), 0, m).astype(a.dtype)
        return m

    def info(self, info):
        """Information(tick, seat, packet, own, events) with the opponent's off-vocab cards aliased or dropped."""
        packet = copy.deepcopy(info.packet)
        obs = packet.observation
        obs.entity_ids[...] = self._ids(obs.entity_ids)
        obs.opponent_history_ids[...] = self._ids(obs.opponent_history_ids, drop_cards=True)
        obs.opponent_seen_card_ids[...] = self._ids(obs.opponent_seen_card_ids, drop_cards=True)
        self.counts['packets'] += 1
        return replace(info, packet=packet, events=self.events(info.events))


class AliasedPlayer:
    """'aliased:<player name>': the inner player sees the live-perception alias of the opponent's cards
    (bot.players.ours.play_match applies `observe_alias`). A search player's belief is the live one: the C56 human
    catalog completed with revealed cards (bot/live/player.py live_belief_class), as the current live bot runs."""

    def __init__(self, rt, inner, name):
        self.rt, self.inner, self.name = rt, inner, name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)
        self.observe_alias = None

    def start(self, ctx):
        self.observe_alias = Aliaser(self.rt.R.builder, ctx.seat)
        self.inner.start(ctx)
        p = getattr(self.inner, 'p', None)
        if p is not None and getattr(p, 'belief', None) is not None:
            from bot.live.player import live_belief_class
            b = p.belief
            frozen = next(c for c in type(b).__mro__ if c.__name__ == 'DerivedPublicState')
            frozen.__init__(b, self.rt.PRIOR, b.costs)
            b.__class__ = live_belief_class()
            b.human_prior = self.rt.PRIOR

    def act(self, view):
        return self.inner.act(view)

    def close(self):
        self.inner.close()

    def __getattr__(self, k):
        return getattr(self.inner, k)
