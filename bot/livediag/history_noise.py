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
  none     no corruption (for a delay-only arm).
  own<P>   OUR OWN plays: P% of them (seeded) are dropped from what the candidate is told about its own plays (D1 rows
           of its seat and the packet's own_last_play via plays[seat]); a later own play that the strict own cycle
           (own_cycle.OwnCycle from the opening order) rejects given the observed sequence is dropped too, as the
           live translator's _consistent(seat 0) does (live s63-m01: 15/25 own plays dropped). The tracked hand,
           elixir and the opponent stream stay true (bot lead Q1: they come from OwnTracker / HUD / opponent events).
  ownbad<P> per-battle wrong opening order (translator owner's measured cause, s63-s65: 26% of own rows missing,
           clustered): with probability P% (seeded per match) the opening order is misread by one swap of positions
           SWAP (a hand card <-> a queue card); that wrong order initialises both the guard's OwnCycle AND the
           player's MatchContext.own_order (as live: the first HUD read sets both), and the strict guard then drops
           every own row it rejects for the rest of the battle. Good battles: no own drops.
  v2       the translator owner's measured stream (missed-play audit v2: 12 live battles, 263 real enemy deployments +
           34 extras; REAL-v2.jsonl / EXTRAS-v2.jsonl): spells never reported; troops dropped otherwise at 13.3%
           (unseen / no-play / wrong-class / board / zone); the deployed translator's stream guard (a DerivedD1 mirror:
           cycle queue with refill timing, 9th card) applied to the REPORTED stream in report order, so its drops cluster with the others (measured 13.7% of troops);
           reported troops wrong-card 3.5% (another opponent card), late 9.15% of the rest (buildings 1/11); report delays
           drawn from the measured on-time / late / wrong distributions; extras: our own play reported as an enemy play
           (Bats 30.6% of our Bats plays, other cards 0.9%; delay 30-217 ticks), a re-detection read as another card per
           reported play (3.9%; Skeletons 4 of 7), spawner children (Tombstone 1.0, Witch .4, GoblinCage .33 (reads as
           MiniPekka), others .4; BattleRam 0). Component knock-outs: +xspell (spells reported), +xdrop (no other drops), +xdropt (translator-side other drops fixed: no-play / suppressed / board / zone;
           the detector-side 11/233 kept),
           +xcyc (no cycle-rule drops), +xwrong, +xlate (on-time delays only), +xextra (no extras), +xown (no own-as-enemy).
Modifiers (live-diag cadence A/B, from the integration owner's translator rate-replay latency curve):
  +vt<D>   observed-play delay: an opponent play (and its phantom) reaches the candidate D ticks after it happened and
           is reported with tick = true tick + D (live: births report latency ~= vote_ticks + poll quantization + frame
           age; today ~13.5 ticks, poll 2 / vote 6 ~8 ticks). Reporting at the delayed tick keeps every stream
           append-only (the D1 rows interleave both seats).
  +ph<P>   phantom probability P% per observed non-spell play (default 10.6; poll 2 / vote 6 adds ~6% plays: ph17).
  e.g. 'live+vt14', 'live+vt8+ph17', 'none+vt14'.
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

SWAP = (3, 4)             # ownbad: the misread swaps the last hand card with the first queue card
PHANTOM_P = 0.106          # ~1.8 phantoms / ~17 observed non-spell opponent plays per battle (live, s41-s60)
SPAWNS = {'Tombstone': 'Skeletons', 'GoblinHut': 'SpearGoblins', 'GoblinCage': 'Goblins', 'Furnace': 'FireSpirits',
          'BarbarianHut': 'Barbarians', 'Witch': 'Skeletons', 'NightWitch': 'Bats', 'BattleRam': 'Barbarians',
          'GoblinGiant': 'SpearGoblins', 'ElixirGolem': 'Skeletons'}
_ACTIVE = {}               # id(match battle) is not available here; keyed by (seat, seed) of the running match
# histnoise v2 (missaudit export, translator owner 2026-10-17): REAL-v2.jsonl r1 cd086cc1... (263 rows; BASE18-BASE20 runs),
# r2 (262 rows, a duplicate BattleRam row removed: troop other-drops 30/232); EXTRAS-v2.jsonl 69d18025...
V2_P_OTHER = 30 / 232            # troop dropped other than by the cycle guard (export r2 2026-10-17: was 31/233)
V2_P_OTHER_DETECTOR = 11 / 232   # of those, detector / owner side (wrong class 10, read as ours 1); +xdropt keeps only these
V2_P_WRONG = 6 / 170             # reported troop with another card
V2_P_LATE = dict(troop=15 / 164, building=1 / 11)
V2_ONTIME = {4: 1, 5: 9, 6: 16, 7: 10, 8: 23, 9: 24, 10: 18, 11: 22, 12: 13, 13: 9, 14: 1, 15: 4, 16: 1, 17: 1, 18: 2, 19: 1,
             20: 1, 22: 1, 24: 1, 30: 1}
V2_LATE = [31, 34, 34, 35, 36, 36, 38, 38, 40, 41, 43, 43, 51, 58, 59, 73]
V2_WRONG = [5, 22, 43, 54, 57, 77]
V2_P_DUP = 7 / 181
V2_DUP = [17, 31, 46, 72, 81, 120, 350]
V2_P_OWN = dict(Bats=19 / 62)
V2_P_OWN_OTHER = 3 / 262
V2_OWN = [30, 42, 62, 62, 66, 67, 72, 72, 82, 82, 100, 102, 102, 107, 111, 141, 161, 187, 192, 201, 217]
V2_SPAWN = dict(Tombstone=('Skeletons', 1.0), Witch=('Skeletons', .4), GoblinCage=('MiniPekka', 1 / 3),
                GoblinHut=('SpearGoblins', .4), Furnace=('FireSpirits', .4), BarbarianHut=('Barbarians', .4),
                NightWitch=('Bats', .4))
V2_SPAWN_D = [28, 48, 53, 111, 353]
V2_KNOCK = ('spell', 'drop', 'dropt', 'cyc', 'wrong', 'late', 'extra', 'own')


def _u(*key):
    h = hashlib.sha256(repr(key).encode()).digest()
    return int.from_bytes(h[:8], 'big') / 2 ** 64


class HistoryNoise:
    def __init__(self, rt, seat, seed, arm, opp_deck=(), guard=True):
        import re
        mods = arm.split('+')
        arm, self.delay, self.phantom_p = mods[0], 0, PHANTOM_P
        self.v2_off = set()
        for m in mods[1:]:
            if re.fullmatch(r'vt\d+', m):
                self.delay = int(m[2:])
            elif re.fullmatch(r'ph\d+', m):
                self.phantom_p = int(m[2:]) / 100
            elif m[:1] == 'x' and m[1:] in V2_KNOCK and arm == 'v2':
                self.v2_off.add(m[1:])
            else:
                raise ValueError(f'history noise modifier {m!r}')
        """guard=False (or arm 'raw' = 'live' with guard=False): no cycle-rule / 9th-card drop; the consumer applies its
        own guard (hard rule or soft cycle model) to the same deterministic noisy stream."""
        self.own_p, self.own_bad = None, None
        if re.fullmatch(r'own\d+', arm):
            self.own_p, arm = int(arm[3:]) / 100, 'none'
        elif re.fullmatch(r'ownbad\d+(m\d+)?', arm):
            mm = re.fullmatch(r'ownbad(\d+)(?:m(\d+))?', arm)
            self.own_p, self.own_bad, arm = 0., int(mm[1]) / 100, 'none'
            self.own_bad_miss = int(mm[2] or 0) / 100     # bad battles: the confirmed stream also misses M% iid
        if arm not in ('spells', 'live', 'raw', 'none', 'v2'):
            raise ValueError(arm)
        self._own_dec, self._oc, self.own_order = {}, None, None
        self.rt, self.seat, self.seed, self.arm = rt, seat, seed, arm
        self.guard = bool(guard) and arm not in ('raw', 'none')
        if arm == 'v2':
            self.guard = bool(guard) and 'cyc' not in self.v2_off
        self._v2, self._ownx, self.own_seen, self._gated, self._gseen = {}, {}, [], {}, []
        self._mirror = None
        self.opp_deck = list(opp_deck)
        self._dec = {}          # ordinal -> (true name, observed name or None, phantom (tick, name) or None)
        self._seen = []         # observed sequence (accepted plays + phantoms), names
        self.now = 0
        self.counts = dict(plays=0, spells_hidden=0, cycle_dropped=0, phantoms=0, own_plays=0, own_dropped=0,
                           own_cycle_dropped=0)
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
        if self.arm == 'v2':
            return self._decide_v2(k, name, tick)
        obs, ph = name, None
        if self.arm == 'none':
            pass
        elif self.is_spell(name):
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
            if self.arm in ('live', 'raw') and _u(self.seed, self.seat, k, 'ph') < self.phantom_p:
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

    def _pick(self, table, *key):
        """Draw from a list or a {value: count} table, deterministically from key."""
        vals = [v for v, c in table.items() for _ in range(c)] if isinstance(table, dict) else list(table)
        return vals[int(_u(self.seed, self.seat, *key) * len(vals))]

    BUILDINGS = frozenset(('Cannon', 'Tombstone', 'GoblinCage', 'GoblinHut', 'InfernoTower', 'BombTower', 'Tesla',
                           'Furnace', 'BarbarianHut', 'Mortar', 'Xbow', 'ElixirCollector', 'Elixir Collector',
                           'GoblinDrill'))

    def _kind(self, name):
        return 'spell' if self.is_spell(name) else ('building' if name in self.BUILDINGS else 'troop')

    def _decide_v2(self, k, name, tick):
        off, c = self.v2_off, self.counts
        kind = self._kind(name)
        obs, delay, extras = name, None, []
        if kind == 'spell' and 'spell' not in off:
            obs = None
            c['spells_hidden'] = c.get('spells_hidden', 0) + 1
        elif kind == 'troop' and 'drop' not in off and \
                _u(self.seed, self.seat, k, 'v2od') < (V2_P_OTHER_DETECTOR if 'dropt' in off else V2_P_OTHER):
            obs = None
            c['other_dropped'] = c.get('other_dropped', 0) + 1
        if obs is not None:                       # the cycle rule runs later, in REPORT order (_gate), as deployed
            if kind == 'troop' and 'wrong' not in off and _u(self.seed, self.seat, k, 'v2wr') < V2_P_WRONG:
                pool = [x for x in self.opp_deck if x != name and not self.is_spell(x)]
                if pool:
                    obs = pool[int(_u(self.seed, self.seat, k, 'v2wc') * len(pool))]
                    delay = self._pick(V2_WRONG, k, 'v2wd')
                    c['wrong_card'] = c.get('wrong_card', 0) + 1
            if delay is None:
                late = 'late' not in off and _u(self.seed, self.seat, k, 'v2lt') < V2_P_LATE.get(kind, 0)
                delay = self._pick(V2_LATE, k, 'v2ld') if late else self._pick(V2_ONTIME, k, 'v2od2')
                c['late'] = c.get('late', 0) + int(late)
            if 'extra' not in off:
                if _u(self.seed, self.seat, k, 'v2dp') < V2_P_DUP:
                    sk = [x for x in self.opp_deck if x == 'Skeletons']
                    pool = [x for x in self.opp_deck if x != obs and not self.is_spell(x)]
                    card = 'Skeletons' if _u(self.seed, self.seat, k, 'v2dk') < 4 / 7 else \
                        (pool[int(_u(self.seed, self.seat, k, 'v2dc') * len(pool))] if pool else 'Skeletons')
                    extras.append((tick + self._pick(V2_DUP, k, 'v2dd'), card))
                    c['dup'] = c.get('dup', 0) + 1
                sp = V2_SPAWN.get(name)
                if sp and _u(self.seed, self.seat, k, 'v2sp') < sp[1]:
                    extras.append((tick + self._pick(V2_SPAWN_D, k, 'v2sd'), sp[0]))
                    c['spawn'] = c.get('spawn', 0) + 1
        self._dec[k] = (name, obs, None)
        self._v2[k] = (delay or 0, extras)
        return self._dec[k]

    def _gate(self, key, name, tick):
        """v2: the deployed translator's stream guard (LiveTranslator._consistent) applied in REPORT order: a DerivedD1
        mirror of the opponent seat, advanced to the report tick, rejects a report whose card is still in the cycle
        queue, a 5th play before the queue refills (queue >= 8), a 9th distinct card or an unknown card; otherwise it
        accepts it. Memoized per stream item, so every rebuild of the append-only stream decides the same way.
        key = ('r', k) real play, ('x', k, i) extra, ('o', j) own-as-enemy."""
        if key in self._gated:
            return self._gated[key]
        ok, tag = True, None
        if self.guard:
            from derived_d1 import DerivedD1
            from imitation.evaluation.d1 import PublicEvent as D1Event
            m = self._mirror
            if m is None:
                m = self._mirror = DerivedD1(self.rt.R.costs)
            t = max(m.tick, int(tick))
            m.advance(t)
            if name not in m.costs:
                tag = 'unknown'
            elif name in m.queue:
                tag = 'cycle'
            elif len(m.queue) >= 8:
                tag = 'burst'
            elif len(m.revealed | {name}) > 8:
                tag = 'ninth'
            if tag is None:
                m.accept(D1Event(t, 'card', name, 0., 0., 0.))
            else:
                ok = False
                c = f'{tag}_dropped' if key[0] == 'r' else f'extra_{tag}_dropped'
                self.counts[c] = self.counts.get(c, 0) + 1
        if ok:
            self._gseen.append(name)
            if key[0] == 'r':
                self._seen.append(name)
        self._gated[key] = ok
        return ok

    def own_extra(self, j, card, tick):
        """v2: (report tick, card) if our j-th own play is reported as an ENEMY play, else None; decided once."""
        if self.arm != 'v2' or 'extra' in self.v2_off or 'own' in self.v2_off:
            return None
        if j not in self._ownx:
            p = V2_P_OWN.get(card, V2_P_OWN_OTHER)
            hit = _u(self.seed, self.seat, j, 'v2own') < p
            self._ownx[j] = (tick + self._pick(V2_OWN, j, 'v2ownd'), card, j) if hit else None
            if hit:
                self.counts['own_as_enemy'] = self.counts.get('own_as_enemy', 0) + 1
        return self._ownx[j]

    def decide_own(self, k, name, tick):
        """Observed? for our k-th own play (own<P> arm), decided once per ordinal."""
        if self.own_p is None:
            return True
        if k in self._own_dec:
            return self._own_dec[k]
        import copy
        from own_cycle import OwnCycle
        if self._oc is None:
            self._oc = OwnCycle(list(self.own_order))
        self.counts['own_plays'] += 1
        p = self.own_p
        if self.own_bad is not None and self.counts.get('own_bad_battle'):
            p = getattr(self, 'own_bad_miss', 0.)
        ok = _u(self.seed, self.seat, k, 'own') >= p
        if not ok:
            self.counts['own_dropped'] += 1
        else:
            oc = copy.deepcopy(self._oc)
            try:
                oc.play(tick, name)
                self._oc = oc
            except ValueError:
                ok = False
                self.counts['own_cycle_dropped'] += 1
        self._own_dec[k] = ok
        return ok

    def own_plays(self, plays):
        """[(tick, name)] of our own accepted plays -> the observed subset."""
        return [p for k, p in enumerate(plays) if self.decide_own(k, p[1], p[0])]

    def _merge(self, items, now, make_ph):
        """items: [(tick, obj, ordinal-or-None)] in stream order -> output with phantoms emitted in TICK order once
        due (tick <= now), so the observed list only ever grows at its end (DerivedPublicState is append-only)."""
        out, pend = [], []          # pend: (report tick, name, source[, key]) of delayed plays / phantoms, report order
        D = self.delay
        v2 = self.arm == 'v2'

        def emit(x):
            if not v2 or self._gate(x[3], x[1], x[0]):
                out.append(make_ph(x[0], x[1], x[2]))
        for tick, obj, k, name in items:
            while pend and pend[0][0] <= tick:          # any later item (either seat, any kind) comes after a due one
                emit(pend.pop(0))
            if k is None:
                out.append(obj)
                continue
            if k == 'ownx':                              # v2: our own play reported as an enemy play (obj = template)
                pend.append((name[0] + D, name[1], obj, ('o', name[2])))
                pend.sort(key=lambda x: (x[0], x[3]))
                continue
            _, obs, ph = self.decide(k, name, tick)
            if v2:
                dly, extras = self._v2[k]
                if obs is not None:
                    pend.append((tick + dly + D, obs, obj, ('r', k)))
                for i, (t2, nm2) in enumerate(extras):
                    pend.append((t2 + D, nm2, obj, ('x', k, i)))
                pend.sort(key=lambda x: (x[0], x[3]))
                continue
            if obs is not None:
                if D:
                    pend.append((tick + D, obs, obj))
                else:
                    out.append(obj)
            if ph is not None:
                pend.append((ph[0] + D, ph[1], obj))
            pend.sort(key=lambda x: x[0])
        for x in pend:
            if x[0] <= now:
                if v2:
                    emit(x)
                else:
                    out.append(make_ph(*x))
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
        items = self._with_own_extras(items, [it for it in items if it[2] is not None])
        rep = (lambda e, **kw: e._replace(**kw)) if hasattr(events[0] if events else None, '_replace') else \
            (lambda e, **kw: replace(e, **kw))
        return self._merge(items, now, lambda t, nm, src: rep(src, tick=t, name=nm))

    def rows(self, rows):
        items, n, j = [], 0, 0
        for r in rows:
            if r.get('kind') == 'card' and r.get('seat') != self.seat:
                items.append((r['tick'], r, n, r['name'])); n += 1
            elif r.get('kind') == 'card' and r.get('seat') == self.seat and self.own_p is not None:
                if self.decide_own(j, r['name'], r['tick']):
                    items.append((r.get('tick', 0), r, None, None))
                j += 1
            else:
                items.append((r.get('tick', 0), r, None, None))
        if self.arm == 'v2' and not getattr(self, '_own_from_sim', False):
            self.own_seen = [(r['tick'], r['name']) for r in rows if r.get('kind') == 'card' and r.get('seat') == self.seat]
        items = self._with_own_extras(items, [it for it in items if it[2] is not None])
        return self._merge(items, self.now, lambda t, nm, src: dict(src, tick=t, name=nm))

    def _with_own_extras(self, items, opp_cards):
        """v2: insert ('ownx') items for our own plays reported as enemy plays, at our play's tick, using the latest
        opponent card item at or before it as the template (no template yet: not reported, decided once)."""
        if self.arm != 'v2' or not self.own_seen:
            return items
        add = []
        for j, (t, card) in enumerate(self.own_seen):
            x = self.own_extra(j, card, t)
            if x is None:
                continue
            tmpl = [it for it in opp_cards if it[0] <= x[0]] or opp_cards[:1]
            if not tmpl:                    # no opponent card event yet in this stream: reported once one exists
                continue
            add.append((t, tmpl[-1][1], 'ownx', x))
        if not add:
            return items
        out, i = [], 0
        for it in items:
            while i < len(add) and add[i][0] < it[0]:
                out.append(add[i]); i += 1
            out.append(it)
        return out + add[i:]


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
        order = list(ctx.own_order)
        n = self.noise
        if n.own_bad is not None:
            n.counts['own_bad_battle'] = int(_u(ctx.seed, ctx.seat, 'ownbad') < n.own_bad)
            if n.counts['own_bad_battle']:
                i, j = SWAP
                order[i], order[j] = order[j], order[i]
                from dataclasses import replace as _replace
                ctx = _replace(ctx, own_order=tuple(order))     # the player's own D1 cycle gets the misread too
        n.own_order = order
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
            if me.noise.arm == 'v2':                       # one source of our plays for BOTH streams (events, rows)
                me.noise.own_seen, me.noise._own_from_sim = list(m.plays[seat]), True
            ev = me.noise.events(list(m.events[seat]), int(m.tick))
            plays = dict(m.plays)
            plays[1 - seat] = [(e.tick, e.name) for e in ev if getattr(e, 'kind', None) == 'card']
            plays[seat] = me.noise.own_plays(list(m.plays[seat]))      # own<P> arm; identity otherwise
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
