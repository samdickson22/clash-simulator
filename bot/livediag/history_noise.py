"""Live-like corruption of the OPPONENT-PLAY HISTORY one seat observes (bot lead's cycle-rule sizing; exploration).

The game is untouched; only what the candidate seat is told about the opponent's card plays changes:
  spells   opponent spells are never observed (births sees only bodies; their effects still happen), with the live
           translator's guards that make that survivable: the strict cycle rule below and the 9th-distinct-card
           rejection (without them the bot's own D1/belief trackers raise on the first too-early repeat, so "spells
           unseen, every other play seen" is not a state the live bot can be in).
  live     spells unobserved; then the deployed translator's strict cycle rule (LiveTranslator._consistent: a card
           cannot be played again until 4 other cards have been) is applied to the OBSERVED sequence, so a real play
           whose previous observed copy is among the last 4 observed plays is dropped (the drop mechanism measured
           live: 435 drops in 80 battles, ~68% real); and phantom plays are inserted at the measured rate (~1.8 per
           battle: p = PHANTOM_P per observed non-spell play, 20 ticks later): a spawner's output when the source is a
           spawner (Tombstone -> Skeletons, GoblinHut -> SpearGoblins, ...), else a re-detection read as another card of
           the opponent's deck that passes the cycle rule. Phantoms enter the observed sequence (they padded the cycle
           count live too).
  raw      the live noise WITHOUT the translator's guards: spells unobserved and phantoms inserted (p, 20 ticks later, a
           spawner output or another deck card), but no cycle-rule or 9th-card drop. For a downstream consumer
           (e.g. a hard rule vs a soft cycle model) to apply its own guard to the same deterministic stream.
Each opponent play is decided once (by its ordinal) and the decision is shared by Information.events (and therefore
the packet's opponent history fields, which observe() builds from those events) and the D1 recorder rows.

Mechanism: bot.players.ours.play_match calls fair_player.observe(b, builder, seat, events) per poll and applies a
player's `observe_alias` (info, recorder). install_observe_patch() wraps fair_player.observe so the candidate seat's
event list is corrupted BEFORE the packet is built; observe_alias.recorder applies the same decisions to the rows.
RoyaleSim (bot/players/royalesim_match.py) does not call fair_player.observe: NoisyPlayer.bind_rsim(m) wraps
m.information for the candidate seat only (Translator.information gets the corrupted opponent events and plays), and
act() applies the same decisions to view.public_events (the recorder stream). The simulator's own play log is untouched.
Name: 'histnoise:<arm>:<player>' (bot.livediag.ours_diag and bot.livediag.sim_diag resolve it).
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

PHANTOM_P = 0.106          # ~1.8 phantoms / ~17 observed non-spell opponent plays per battle (live, s41-s60)
SPAWNS = {'Tombstone': 'Skeletons', 'GoblinHut': 'SpearGoblins', 'GoblinCage': 'Goblins', 'Furnace': 'FireSpirits',
          'BarbarianHut': 'Barbarians', 'Witch': 'Skeletons', 'NightWitch': 'Bats', 'BattleRam': 'Barbarians',
          'GoblinGiant': 'SpearGoblins', 'ElixirGolem': 'Skeletons'}
_ACTIVE = {}               # id(match battle) is not available here; keyed by (seat, seed) of the running match


def _u(*key):
    h = hashlib.sha256(repr(key).encode()).digest()
    return int.from_bytes(h[:8], 'big') / 2 ** 64


class HistoryNoise:
    def __init__(self, rt, seat, seed, arm, opp_deck=(), guard=True):
        """guard=False (or arm 'raw' = 'live' with guard=False): no cycle-rule / 9th-card drop; the consumer applies its
        own guard (hard rule or soft cycle model) to the same deterministic noisy stream."""
        if arm not in ('spells', 'live', 'raw'):
            raise ValueError(arm)
        self.rt, self.seat, self.seed, self.arm = rt, seat, seed, arm
        self.guard = bool(guard) and arm != 'raw'
        self.opp_deck = list(opp_deck)
        self._dec = {}          # ordinal -> (true name, observed name or None, phantom (tick, name) or None)
        self._seen = []         # observed sequence (accepted plays + phantoms), names
        self.now = 0
        self.counts = dict(plays=0, spells_hidden=0, cycle_dropped=0, phantoms=0)
        self._spell = {}

    def is_spell(self, name):
        if name not in self._spell:
            from clasher.card_aliases import resolve_card_name
            from clasher.spells import SPELL_REGISTRY
            b = self.rt.R.builder
            try:
                self._spell[name] = resolve_card_name(name, b.loader.load_card_definitions()) in SPELL_REGISTRY
            except Exception:
                self._spell[name] = False
        return self._spell[name]

    def decide(self, k, name, tick):
        if k in self._dec:
            if self._dec[k][0] != name:
                raise ValueError(f'history streams disagree at opponent play {k}')
            return self._dec[k]
        self.counts['plays'] += 1
        obs, ph = name, None
        if self.is_spell(name):
            obs = None
            self.counts['spells_hidden'] += 1
        elif self.guard and name in self._seen[-4:]:
            obs = None
            self.counts['cycle_dropped'] += 1
        elif self.guard and name not in self._seen and len(set(self._seen)) >= 8:
            obs = None
            self.counts['ninth_dropped'] = self.counts.get('ninth_dropped', 0) + 1
        if obs is not None:
            self._seen.append(obs)
            if self.arm in ('live', 'raw') and _u(self.seed, self.seat, k, 'ph') < PHANTOM_P:
                guard = self.guard
                cand = SPAWNS.get(name)
                if cand is None or (guard and cand in self._seen[-4:]):
                    pool = [c for c in self.opp_deck if (not guard or c not in self._seen[-4:]) and c != name
                            and not self.is_spell(c)]
                    cand = pool[int(_u(self.seed, self.seat, k, 'pc') * len(pool))] if pool else None
                if guard and cand is not None and cand not in self._seen and len(set(self._seen)) >= 8:
                    cand = None
                if cand is not None:
                    ph = (tick + 20, cand)
                    self._seen.append(cand)
                    self.counts['phantoms'] += 1
        self._dec[k] = (name, obs, ph)
        return self._dec[k]

    def _merge(self, items, now, make_ph):
        """items: [(tick, obj, ordinal-or-None)] in stream order -> output with phantoms emitted in TICK order once
        due (tick <= now), so the observed list only ever grows at its end (DerivedPublicState is append-only)."""
        out, pend = [], []
        for tick, obj, k, name in items:
            while pend and pend[0][0] <= tick:          # any later item (either seat, any kind) comes after a due phantom
                out.append(make_ph(*pend.pop(0)))
            if k is None:
                out.append(obj)
                continue
            _, obs, ph = self.decide(k, name, tick)
            if obs is not None:
                out.append(obj)
            if ph is not None:
                pend.append((ph[0], ph[1], obj))
                pend.sort(key=lambda x: x[0])
        out += [make_ph(*x) for x in pend if x[0] <= now]
        return out

    def events(self, events, now):
        """fair_player PublicEvent list (this seat's view of the opponent's card plays) -> corrupted list."""
        self.now = now
        items, n = [], 0
        for e in events:
            if getattr(e, 'kind', None) == 'card':
                items.append((e.tick, e, n, e.name)); n += 1
            else:
                items.append((e.tick, e, None, None))
        rep = (lambda e, **kw: e._replace(**kw)) if hasattr(events[0] if events else None, '_replace') else \
            (lambda e, **kw: replace(e, **kw))
        return self._merge(items, now, lambda t, nm, src: rep(src, tick=t, name=nm))

    def rows(self, rows):
        items, n = [], 0
        for r in rows:
            if r.get('kind') == 'card' and r.get('seat') != self.seat:
                items.append((r['tick'], r, n, r['name'])); n += 1
            else:
                items.append((r.get('tick', 0), r, None, None))
        return self._merge(items, self.now, lambda t, nm, src: dict(src, tick=t, name=nm))


class _Hook:
    """observe_alias protocol of play_match: info passthrough (the packet is already built from corrupted events by the
    observe patch), recorder rows corrupted with the same decisions."""

    def __init__(self, noise):
        self.noise = noise
        self.counts = noise.counts

    def info(self, info):
        return info

    def recorder(self, rows):
        return self.noise.rows(rows)


class NoisyPlayer:
    def __init__(self, rt, inner, arm, name):
        self.rt, self.inner, self.arm, self.name = rt, inner, arm, name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)
        self.observe_alias = None
        self.noise = None

    def start(self, ctx):
        self.noise = HistoryNoise(self.rt, ctx.seat, ctx.seed, self.arm, getattr(self, 'opp_deck', ()))
        self.observe_alias = _Hook(self.noise)
        _ACTIVE[ctx.seat] = self.noise
        self.inner.start(ctx)

    def bind_rsim(self, m):
        """RoyaleSim: corrupt what Translator.information sees for this seat (events + the opponent's plays)."""
        self._rsim = m
        if hasattr(self.inner, 'bind_rsim'):
            self.inner.bind_rsim(m)
        orig = m.information
        me = self

        def information(seat):
            if me.noise is None or seat != me.noise.seat:
                return orig(seat)
            ev = me.noise.events(list(m.events[seat]), int(m.tick))
            plays = dict(m.plays)
            plays[1 - seat] = [(e.tick, e.name) for e in ev if getattr(e, 'kind', None) == 'card']
            return m.tr.information(m.state, seat, m.own_hud(seat), plays, ev)
        m.information = information

    def act(self, view):
        if getattr(self, '_rsim', None) is not None:
            view = replace(view, public_events=self.noise.rows(list(view.public_events)))
        return self.inner.act(view)

    def close(self):
        _ACTIVE.pop(getattr(self.noise, 'seat', None), None)
        self.inner.close()

    def __getattr__(self, k):
        return getattr(self.inner, k)


def install_observe_patch():
    """Wrap fair_player.observe once per process: the seat with an active HistoryNoise sees corrupted events."""
    import fair_player
    if getattr(fair_player.observe, '_histnoise', False):
        return
    orig = fair_player.observe

    def observe(b, builder, actor, events, *a, **kw):
        noise = _ACTIVE.get(actor)
        if noise is not None:
            events = noise.events(list(events), int(b.tick))
        return orig(b, builder, actor, events, *a, **kw)
    observe._histnoise = True
    fair_player.observe = observe
