"""Card-level perception -> bodies, tracks and derived plays; HUD clock -> tick (LIVE track, exploration).

Perception (live/perception/common.py:frame_record, schema clasher.live.perception-frame.v1) reports each unit as the
CARD that spawned it (C56 names; towers separately) and emits NO play events. This module supplies what the bot needs
from that:

CardBodies   card -> our body tokens, from the frozen engine config (the card's units, its production children and
             its death children; token/kind exactly as the v5 builder writes them, Resources.meta['bodies']); the
             number of bodies one deployment puts down (`count`), death-spawn wave (`death_n`), building lifetime
             (`lifetime`, ticks), champions; and sprite FAMILIES: cards that share a body token (Skeletons/
             SkeletonArmy, Minions/MinionHorde, Goblins/GoblinGang/GoblinHut, FireSpirits/FirespiritHut). One body of
             a family cannot tell its card, so a per-frame label is only a hint within the family.
UnitTracker  frame-to-frame tracks per (FAMILY, owner); a label flip within the family continues the same track, never
             a birth, never a play. Births cluster into deployments: ONE play per deployment, whatever its body count,
             the card inferred ONCE when the cluster closes, from the burst: the family by the summed label votes,
             then within the family the cards that can put down as many bodies as were seen together (`peak`), the
             label votes choosing among those (a perception 'spawn_card' hint, unit field 6, is deployment provenance:
             `hint_weight` votes, and no rule below may swallow it). So 8 skeletons seen together are a SkeletonArmy
             whatever their labels, 2 are whatever the burst's labels say. The play is emitted at the centroid of the
             deployment's first sightings and its first-sighting tick, if the opponent can deploy there (its side,
             y >= 15, unless the card deploys anywhere or the facing own princess tower is down: y >= 9).
             Spawns walking off a spawner, death children, re-detections of a deployment (duplicates, leftovers, late
             bodies, revivals, relabels, champion relocations) are never plays; every such rule needs positive
             evidence, is bounded in space and time, lets a card that could have cycled back be a new play, and
             yields to deployment provenance (UnitTracker docstring; audit table: MULTIBODY.md).
             Public API (stable for code outside this module): update, resolve, identity, last_tracks,
             snapshot/restore, forget_card, deployable; CardBodies.bodies_of, family_of, is_card.
ClockTracker HUD clock (s) + elixir phase (1/2/3) + timestamp -> match tick (20/s), monotonic. Regulation shows
             180..0 (tick = (180-clock)*20 + 1..20), overtime 120..0 (tick = (300-clock)*20 + 1..20)
             (collector.py:379); phase 2 with clock > 60 or phase 3 means overtime. Within the 20-tick second the
             timestamp interpolates.
Known gaps (documented in RESULTS): spells are never seen, so the opponent's spell plays (and their elixir/cycle
effect) are missing; a play whose units are never detected is missed; units re-detected after `memory` ticks look
like a new play. The translator's stream guard (D1/OwnCycle mirrors) drops plays the trackers would reject.
Multi-body counting: reports/live/integration/MULTIBODY.md.
"""
from __future__ import annotations

from collections import Counter, namedtuple
import math

KINDS = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
DEPLOY_ANYWHERE = {'Miner', 'GoblinBarrel', 'MightyMiner'}
TUNNEL = {'Miner'}


class CardBodies:
    def __init__(self, rt):
        R = rt.R
        cfg = R.config
        self.costs, self.R = R.costs, R
        self.oov, self._links = set(), []

        def token(template):
            stat = template['stats']['name']
            kind = template['class'] if template['class'] in ('Troop', 'Building') else None
            if kind is None:
                return None
            meta = R.meta['bodies'].get(stat)
            tok = meta['token'] if meta else 0
            if not tok or (tok, kind) not in R.templates:
                tok = next((t for (t, k), v in R.templates.items() if k == kind and v['stats']['name'] == stat), 0)
            return (int(tok), KINDS.index(kind)) if tok else None

        self.main, self.children, self.death, self.count, self.death_n, self.lifetime = {}, {}, {}, {}, {}, {}
        self.champions = set()          # one on the board at a time; abilities relocate (MightyMiner) or hide (Queen)
        for card, c in cfg['cards'].items():
            if ':' in card:              # a level variant ('level12:Knight', full card scope) of its base card,
                continue                 # not a separate deployable card
            comp = Counter()
            stats = []
            groups = list(c.get('units', ()))
            for grp in groups:
                for t in (grp if isinstance(grp, list) else [grp]):
                    b = token(t)
                    if b:
                        comp[b] += 1
                        stats.append(t['stats']['name'])
            self.main[card] = list(comp.items())
            # config 'units' holds one group per seat orientation: one deployment = one group's bodies
            first = groups[0] if groups else []
            self.count[card] = sum(1 for t in (first if isinstance(first, list) else [first]) if token(t))
            kids = []
            for s in dict.fromkeys(stats):
                p = cfg['production_children'].get(s)
                for t in (p if isinstance(p, list) else [p] if p else []):
                    b = token(t)
                    if b and b not in kids:
                        kids.append(b)
            self.children[card] = kids
            dead = []
            for s in dict.fromkeys(stats):
                for t in cfg['death_children'].get(s) or ():
                    b = token(t)
                    if b and b not in dead:
                        dead.append(b)
            self.death[card] = dead
            self.death_n[card] = max([len(cfg['death_children'].get(st) or ()) for st in dict.fromkeys(stats)] or [0])
            if any(t.get('champion') for t in (first if isinstance(first, list) else [first])):
                self.champions.add(card)
            life = [float(t['stats'].get('lifetime') or 0) for t in (first if isinstance(first, list) else [first])
                    if t.get('class') == 'Building']
            if life and max(life) > 0:
                self.lifetime[card] = int(max(life)/50)       # ms -> ticks: a Cannon stands 600 ticks
        self._families()

    def body_token(self, name):
        """Body token name (the builder's vocabulary: 'Skeleton', 'GoblinHut_Rework', 'SpearGoblin', as the proxy
        table and body-catalog.json write them) -> (token, kind) of a Troop/Building template, or None."""
        if not hasattr(self, '_by_name'):
            names = self.R.builder.token_names
            self._by_name = {}
            for (t, k) in sorted(self.R.templates, key=lambda tk: (str(tk[1]) != 'Troop', int(tk[0]))):
                if k in ('Troop', 'Building') and 0 < int(t) < len(names):
                    self._by_name.setdefault(names[int(t)], (int(t), KINDS.index(k)))
        return self._by_name.get(name) if name else None

    def add_named(self, named, shared=None):
        """Off-vocabulary cards as pseudo-cards (bot/live/oov.py): {card: dict(main=proxy body name, bodies=n,
        extra=[proxy body names of its other bodies (spawns, death children)], building=bool)}. Families join by the
        proxy table's SHARED_BODY (Tombstone with the skeleton cards, SpearGoblins with the goblin cards), not by
        proxy bodies (stand-ins, not sprites). Births then track, count and spawn-filter them like C56 cards and emit
        plays under their TRUE id; a pseudo-card is inferred only when perception names it (UnitTracker.infer_card)."""
        for card, e in named.items():
            if card in self.main:
                continue
            main = self.body_token(e.get('main'))
            if main is None:
                continue
            n = max(1, int(e.get('bodies') or 1))
            self.main[card], self.count[card] = [(main, n)], n
            extra = [b for b in dict.fromkeys(self.body_token(x) for x in e.get('extra') or ()) if b and b != main]
            self.children[card], self.death[card] = list(extra), list(extra)
            self.death_n[card] = 4 if extra else 0
            self.oov.add(card)
            self._links += [(card, c) for c in (shared or {}).get(card, ()) if c in self.main]
        self._families()

    def _families(self):
        """Cards sharing a body token (main, production or death child) form one family (union-find); off-vocabulary
        pseudo-cards join by the proxy table's SHARED_BODY instead."""
        parent = {c: c for c in self.main}

        def find(c):
            while parent[c] != c:
                parent[c] = parent[parent[c]]
                c = parent[c]
            return c
        first = {}
        for card in sorted(c for c in self.main if c not in self.oov):
            for b in [b for b, _ in self.main[card]] + self.children[card] + self.death[card]:
                if b in first:
                    parent[find(card)] = find(first[b])
                else:
                    first[b] = card
        for a, b in self._links:         # an off-vocab card joins a C56 family; it never bridges two of them
            ra, rb = find(a), find(b)
            if ra != rb and not (any(find(c) == ra for c in self.main if c not in self.oov) and
                                 any(find(c) == rb for c in self.main if c not in self.oov)):
                parent[ra] = rb
        groups = {}
        for c in self.main:
            groups.setdefault(find(c), set()).add(c)
        self.families = {}
        self._family = {}
        for members in groups.values():
            fid = min(members - self.oov or members)
            self.families[fid] = frozenset(members)
            for c in members:
                self._family[c] = fid

    def is_card(self, name):
        return name in self.main

    def fam(self, card):
        return self._family.get(card, card)

    def family_of(self, label):
        """Public: the family id (its first card name, e.g. 'SkeletonArmy') of a per-frame label."""
        return self._family.get(label, label)

    def bodies_of(self, card):
        """Public: frozenset of (token, kind) bodies a card can put on the board (its units, production and death
        children)."""
        return frozenset([b for b, _ in self.main.get(card) or ()] + self.children.get(card, []) +
                         self.death.get(card, []))

    def spawner(self, card):
        return bool(self.main.get(card)) and bool(self.children.get(card))


class Track:
    __slots__ = ('card', 'owner', 'body', 'x', 'y', 'first', 'last', 'facing', 'main', 'id', 'fam', 'labels', 'fx', 'fy',
                 'px', 'py',
                 'spawn', 'hint', 'resolved', 'state', 'body_constraint')

    def __init__(self, tid, card, owner, body, x, y, tick, main, fam):
        self.id, self.card, self.owner, self.body = tid, card, owner, body
        self.x, self.y, self.first, self.last, self.facing, self.main = x, y, tick, tick, (0., 0.), main
        self.fam, self.labels = fam, Counter({card: 1})
        self.fx, self.fy = x, y
        self.px, self.py = x, y      # position before this frame's match (a split moves the parent's track)
        self.spawn = None        # dict(kind='spawn'|'death', wave, parent) for a birth beside a spawner / dying parent
        self.hint = None         # perception spawn_card (deployment provenance)
        self.resolved = None     # card of the deployment this body belongs to, once its cluster closed
        self.state = 'none'      # pending | played | spawn | child | leftover | none
        self.body_constraint = None       # canonical observed body, never deployment provenance

    def label(self):
        """Majority per-frame label (ties: the birth label)."""
        return max(self.labels.items(), key=lambda kv: (kv[1], kv[0] == self.card))[0]

    @property
    def deploy(self):
        """The deployment card stored when its cluster closed (kept through revivals); None while it votes."""
        return self.resolved

    def copy(self):
        t = Track.__new__(Track)
        for k in Track.__slots__:
            setattr(t, k, getattr(self, k))
        t.labels = Counter(self.labels)
        return t


Identity = namedtuple('Identity', 'id owner fam label card body state')


class UnitTracker:
    """Tracks + plays from births. Every rule that can suppress, absorb, revive or defer a birth needs positive
    evidence, is bounded in space and time, lets a card that could have cycled back (4 other plays of its owner
    since) be a new play, and yields to perception's deployment provenance (`spawn_card`, unit field 6); the audit
    table is in reports/live/integration/MULTIBODY.md.

    Matching (`_plan`, shared by update and resolve): same-family, same-owner tracks, globally nearest first (a
    different label within the family costs `label_penalty`; a building only takes building labels and never moves;
    a unit with deployment provenance only continues a track of the same provenance) plus augmenting paths; then expired tracks within `memory` (`building_memory` for buildings and spawners) are
    revived if `_revivable`; then a unit within `relabel_tiles` of a body of another family that is missing from this
    frame and was seen within `relabel_gap` ticks continues it (`_relabel_ok`).
    Clusters: a main-body birth of owner o joins an open cluster of o of its family within `spread_tiles` of the
    cluster's first body or `link_tiles` of a member, or of any family when it coincides with a member seen in this
    frame (a double detection, `_coincident`); else a closed cluster absorbs it (`_absorbed`) or it opens a cluster if
    the opponent can deploy there. For `vote_ticks` the members vote with their per-frame labels (score >=
    `min_score`) and count towards the family's `peak` (most new bodies in one frame); a cluster with >=
    `confirm_hits` frames with a member closes and emits ONE play, its card inferred from the burst, at the centroid
    of its members' first sightings and the first-sighting tick; one short of hits after `confirm_ticks` is dropped.
    No play (the cluster stays, closed, to absorb the rest of its bodies) when `_suppressed` says spawn, death child,
    duplicate or leftover. A tunnelling Miner closes only when it surfaces, and takes no members meanwhile.
    Public, stable API for code outside births.py (bot/live/revealed.py etc.): update, resolve, identity,
    last_tracks, snapshot/restore, forget_card, deployable; the rest is private."""
    hint_weight = 10.
    label_penalty = .75
    relabel_tiles, relabel_gap = 1., 10
    link_tiles, coincide_tiles, death_tiles, split_tiles = 2., .8, 1.6, .3
    still_tiles, spawn_wait = .3, 40
    champion_radius, champion_gap = 40., 80
    site_wave, site_death_wave, site_tiles, site_window = 2, 4, 2.5, 400
    continuity_tiles, continuity_speed = 1.5, .08
    cycle_plays = 4
    tunnel_speed, tunnel_ticks, tunnel_speed_max, tunnel_radius = .15, 80, 1., 9.
    building_radius, building_memory = 1.2, 1200     # a building does not move; it stands up to a minute

    def __init__(self, bodies: CardBodies, *, radius=1.2, speed=.06, max_radius=3.5, ttl=40, building_ttl=400,
                 memory=200, cluster_tiles=4.0, cluster_ticks=40, confirm_hits=2, vote_ticks=10, vote_tiles=2.5,
                 relabel_ticks=40, min_score=.6, confirm_ticks=30, spread_tiles=4.0, spawn_tiles=3.0, death_ticks=40,
                 repeat_ticks=160):
        # Defaults from a sweep on the perception owner's 2 validation matches (sample-records, 49 opponent plays):
        # real output P/R .75/.80 (vs .33-.42/.93-1.0 with per-track confirmation); truth units .91/.86.
        self.cb = bodies
        self.radius, self.speed, self.max_radius = radius, speed, max_radius
        self.ttl, self.building_ttl, self.memory = ttl, building_ttl, memory
        self.cluster_tiles, self.cluster_ticks = cluster_tiles, cluster_ticks
        self.confirm_hits, self.vote_ticks, self.vote_tiles = confirm_hits, vote_ticks, vote_tiles
        self.relabel_ticks, self.min_score, self.confirm_ticks = relabel_ticks, min_score, confirm_ticks
        self.spread_tiles, self.spawn_tiles, self.death_ticks = spread_tiles, spawn_tiles, death_ticks
        self.repeat_ticks = repeat_ticks
        self.live, self.dead, self.clusters = [], [], []
        self.played = []            # {owner, fam, card, t0, peak, ids, cluster} of emitted plays within repeat_ticks
        self.history = []           # (owner, t0, card) of every emitted play (cycle eligibility)
        self.n = 0
        self.stats = Counter()
        self.last_tracks = []       # track id per unit of the last update (None: no body)
        self.sites = []             # spawner sites without a card: class-only buildings, inferred spawners (R15)
        self.last_tick = None       # frames must not go back in time (rejected, state untouched)
        self.oov_allowed = lambda owner, card: True     # the translator's revealed-set rule for off-vocab cards

    # -- public, read-only -------------------------------------------------------------------------------------------
    def identity(self, tid):
        """Identity(id, owner, fam, label, card, body, state) of a live or remembered track, or None. card = the
        resolved card of its deployment (None while its cluster still votes)."""
        t = next((t for t in self.live + self.dead if t.id == tid), None)
        return None if t is None else self._identity(t)

    @staticmethod
    def _identity(t):
        return Identity(t.id, t.owner, t.fam, t.label(), t.resolved, t.body, t.state)

    def resolve(self, units, tick):
        """The track each unit WOULD continue under update's matching rules (Identity) or None (a birth). Read-only."""
        got, _, _ = self._plan(self._parse(units), tick)
        return [None if t is None else self._identity(t) for t in got]

    def snapshot(self):
        """All mutable state (tracks, clusters, plays, counters, stats); CardBodies is shared. restore() + the same
        update gives the same result."""
        return self._copy_state((self.live, self.dead, self.clusters, self.played, self.history, self.n, self.stats,
                                 self.last_tracks, self.sites, self.last_tick))

    def restore(self, snap):
        (self.live, self.dead, self.clusters, self.played, self.history, self.n, self.stats,
         self.last_tracks, self.sites, self.last_tick) = self._copy_state(snap)

    def _copy_state(self, st):
        live, dead, clusters, played, history, n, stats, last, sites, last_tick = st
        cl = {id(c): self._copy_cluster(c) for c in clusters}
        pl = [dict(p, ids=set(p['ids']), cluster=cl.get(id(p['cluster']), p['cluster'])) for p in played]
        return ([t.copy() for t in live], [t.copy() for t in dead], [cl[id(c)] for c in clusters], pl, list(history),
                n, Counter(stats), list(last), [dict(x) for x in sites], last_tick)

    @staticmethod
    def _copy_cluster(c):
        d = dict(c)
        for k in ('votes', 'peak'):
            d[k] = Counter(c[k])
        d['by'] = {k: Counter(v) for k, v in c.get('by', {}).items()}
        d['members'], d['pts'] = set(c['members']), list(c['pts'])
        if 'trail' in c:
            d['trail'] = list(c['trail'])
        return d

    def forget_card(self, owner, card):
        """Drop owner's tracks of `card` (resolved card, or the label while unresolved) from live and dead, and from
        open clusters (an open cluster left without members goes). The play history stays. Returns the count."""
        gone = {t.id for t in self.live + self.dead
                if t.owner == owner and (t.resolved == card or (t.resolved is None and t.label() == card))}
        self.live = [t for t in self.live if t.id not in gone]
        self.dead = [t for t in self.dead if t.id not in gone]
        keep = []
        for c in self.clusters:
            if c['owner'] == owner and c['card'] == card:
                continue                 # its closed deployment can no longer absorb or vouch for anything
            if c['card'] is None and c['owner'] == owner:
                for tid in gone & c['members']:
                    c['votes'] -= c['by'].pop(tid, Counter())   # their votes go with them
                c['members'] -= gone
                if not c['members']:
                    continue
                left = Counter(t.fam for t in self.live if t.id in c['members'])
                c['peak'] = Counter({f: min(n, left[f]) for f, n in c['peak'].items() if left[f]})
            keep.append(c)
        self.clusters = keep
        self.played = [p for p in self.played if not (p['owner'] == owner and p['card'] == card)]
        self.stats['forgotten'] += len(gone)
        return len(gone)

    # -- matching ------------------------------------------------------------------------------------------------------
    def _parse(self, units):
        parsed = []
        for u in units:
            card, owner, x, y = u[:4]
            score = u[4] if len(u) > 4 and u[4] is not None else 1.
            hint = u[5] if len(u) > 5 and u[5] and self.cb.is_card(u[5]) else None
            body = tuple(u[6]) if len(u) > 6 and u[6] is not None else None
            if body is not None and body not in self.cb.bodies_of(card):
                raise ValueError(f'observed body outside configured card: {card}/{body}')
            parsed.append((card, owner, float(x), float(y), float(score), hint, self.cb.fam(card), body))
        return parsed

    def _static(self, t):
        """Buildings stand still (a FirespiritHut is a troop in the config and gets pushed: it moves)."""
        return t.body[1] == 1

    def _radius(self, t, tick):
        if self._static(t):              # buildings do not move
            return self.building_radius
        if t.spawn is None and t.label() in self.cb.champions and tick - t.last <= self.champion_gap and \
                not self._cycle_ok(t.owner, t.label(), t.first):
            return self.champion_radius  # one champion on the board: an ability moved or hid it, it is the same
            # (a short gap: Explosive Escape is instant, the Queen hides 3.5 s; not once its card could cycle back)
        if t.card in TUNNEL and t.main and tick - t.first <= self.tunnel_ticks:    # underground: ~0.6 tiles/tick
            return min(self.tunnel_radius, self.radius + self.tunnel_speed_max*(tick - t.last))
        return min(self.max_radius, self.radius + self.speed*(tick - t.last))

    def _ttl(self, t):
        return self.building_ttl if self._static(t) or self._spawner(t) else self.ttl

    def _memory(self, t):
        return self.building_memory if self._static(t) or self._spawner(t) else self.memory

    def _pools(self, tick):
        """(live, remembered) as of `tick`: ages are checked before matching (a long gap expires tracks)."""
        live = [t for t in self.live if tick - t.last <= self._ttl(t)]
        dead = [t for t in self.dead + [t for t in self.live if tick - t.last > self._ttl(t)]
                if tick - t.last <= self._memory(t)]
        return live, dead

    def _expire(self, tick):
        self.live, self.dead = self._pools(tick)

    def _plan(self, parsed, tick):
        """-> (track or None per unit, how per unit: 'live' | 'revive' | 'relabel' | None, augmented). Pure."""
        got, taken = [None]*len(parsed), set()
        live, dead = self._pools(tick)
        # a building not seen for a while is as good as remembered: the same rules as a revival
        aug = self._assign(live, parsed, got, tick, taken,
                           lambda t, u: (u[5] is None or u[5] == t.hint) and
                           (not self._static(t) or tick - t.last <= self.ttl or self._revivable(t, u, tick)))
        how = ['live' if t is not None else None for t in got]
        aug += self._assign(dead, parsed, got, tick, taken, lambda t, u: self._revivable(t, u, tick))
        how = [h or ('revive' if got[i] is not None else None) for i, h in enumerate(how)]
        for i, u in enumerate(parsed):
            if got[i] is not None:
                continue
            best = min(((math.hypot(u[2] - t.x, u[3] - t.y), t.id, t) for t in live
                        if t.id not in taken and self._relabel_ok(t, u, tick)), default=None)
            if best is not None:
                got[i], how[i] = best[2], 'relabel'
                taken.add(best[1])
        return got, how, aug

    def _assign(self, pool, units, got, tick, taken, ok):
        """Globally nearest-first matching of still unmatched units to tracks of the same family and owner, then
        augmenting paths (Kuhn): greedy alone strands a body in a dense swarm whose only reachable track went to a
        neighbour (a phantom birth). Returns the number of augmented matches."""
        pairs = []
        for i, u in enumerate(units):
            if got[i] is not None:
                continue
            card, owner, x, y, fam = u[0], u[1], u[2], u[3], u[6]
            for t in pool:
                if t.fam != fam or t.owner != owner or t.id in taken:
                    continue
                if not self._body_matches(t, u):
                    continue                 # observed body cannot continue a different body of its family
                if t.body[1] == 1 and not self._building(card) or self._spawner(t) and card != t.label():
                    continue                 # a building or spawner is only ever its own label (a goblin is not its hut)
                d = math.hypot(x - t.x, y - t.y)
                if d <= self._radius(t, tick) and ok(t, u):
                    # within a family the same label is preferred (a goblin walking past its hut stays a goblin)
                    pairs.append((d + (0. if t.label() == card else self.label_penalty), i, t.id, t))
        pairs.sort(key=lambda p: p[:3])
        free = [i for i in range(len(units)) if got[i] is None]
        for _, i, tid, t in pairs:
            if got[i] is None and tid not in taken:
                got[i] = t
                taken.add(tid)
        near = {}
        for d, i, tid, t in pairs:
            near.setdefault(i, []).append(t)
        holder = {got[i].id: i for i in free if got[i] is not None}

        def augment(i, seen):
            for t in near.get(i, ()):
                if t.id in seen or (t.id in taken and t.id not in holder):
                    continue
                seen.add(t.id)
                j = holder.get(t.id)
                if j is None or augment(j, seen):
                    got[i], holder[t.id] = t, i
                    taken.add(t.id)
                    return True
            return False
        return sum(1 for i in free if got[i] is None and near.get(i) and augment(i, set()))

    def _revivable(self, t, u, tick):
        """Revival of a remembered (or long unseen building) track: never for a unit with deployment provenance;
        never past the card's lifetime (a Cannon stands 30 s); never once the card could have cycled back (4 other
        plays of its owner since it was last seen: a new Cannon on the old tile is a play)."""
        if u[5] is not None:
            return False
        card = t.resolved or t.label()
        life = self.cb.lifetime.get(card)
        if life and tick - t.first > life:
            return False
        return not self._cycle_ok(t.owner, card, t.last)

    def _body_matches(self, t, u):
        """Exact observations constrain identity; legacy inputs retain original tracking.

        An unconstrained proxy may relabel another unconstrained backend track,
        but cannot repurpose an exact track as a card that cannot own its body.
        """
        if u[7] is not None:
            return u[7] == t.body
        return t.body_constraint is None or t.body in self.cb.bodies_of(u[0])

    def _relabel_ok(self, t, u, tick):
        """A label switch ACROSS families (Knight read as Valkyrie): the unit sits within `relabel_tiles` of a body of
        another family that is missing from this frame and was seen within `relabel_gap` ticks (never a building,
        never a unit with deployment provenance)."""
        return (self._body_matches(t, u) and
                u[5] is None and t.owner == u[1] and t.fam != u[6] and t.body[1] != 1 and t.last < tick and
                tick - t.last <= self.relabel_gap and math.hypot(u[2] - t.x, u[3] - t.y) <= self.relabel_tiles)

    def _cycle_ok(self, owner, card, since):
        """`card` may have been played again: its owner made >= `cycle_plays` other plays after tick `since`."""
        return sum(1 for o, t, c in self.history if o == owner and t > since and c != card) >= self.cycle_plays

    # -- bodies --------------------------------------------------------------------------------------------------------
    def _spawner(self, t):
        lab = t.label()
        return t.spawn is None and self.cb.spawner(lab) and any(t.body == b for b, _ in self.cb.main[lab])

    def _new_body(self, card, owner, x, y, tick, fam, hint=None):
        """-> (body or None, spawn or None). A birth with deployment provenance is that card's body. A death child
        needs a death TRANSITION of a parent with death children within `death_tiles`: the parent vanished (seen
        within `death_ticks`, missing from this frame), or its track split in this frame (one golemite continued it:
        the track jumped >= `split_tiles` and the birth is next to where the parent was). Else one within
        `spawn_tiles` of a spawner (tracked, or remembered for `building_memory`) is a spawn. All still cluster:
        `_suppressed` decides with the burst size (a deployment beside a living parent is a play)."""
        cb = self.cb
        if hint is not None:
            main = cb.main.get(hint) or cb.main.get(card) or []
            return (self._fill(main, card, owner) if main else None), None
        parents = [t for t in self.live + self.dead if t.owner == owner and t.fam == fam and t.spawn is None and
                   cb.death.get(t.label()) and tick - t.last <= self.death_ticks and t.first < tick and
                   math.hypot(x - t.x, y - t.y) <= self.death_tiles]
        for t in parents:                # its parent vanished: a death child
            if t.last < tick:
                return self._death(t)
        for t in self.live + self.dead:
            life = self.cb.lifetime.get(t.label())
            if t.owner == owner and t.fam == fam and self._spawner(t) and t.first < tick and \
                    not (life and tick - t.first > life) and math.hypot(x - t.x, y - t.y) <= self.spawn_tiles:
                lab = t.label()
                return cb.children[lab][0], dict(kind='spawn', wave=1, parent=t.id, card=t.resolved or lab,
                                                 since=t.first)
        for t in parents:                # a parent still seen whose track just split (one golemite continued it)
            if t.last == tick and math.hypot(t.x - t.px, t.y - t.py) >= self.split_tiles and \
                    math.hypot(x - t.px, y - t.py) <= self.death_tiles:
                return self._death(t)
        site = self._site_spawn(owner, fam, x, y, tick)
        if site is not None:
            main = cb.main.get(card) or []
            return (self._fill(main, card, owner) if main else None), site
        main = cb.main.get(card) or []
        return (self._fill(main, card, owner) if main else None), None

    def _site_spawn(self, owner, fam, x, y, tick):
        """A birth within `spawn_tiles` of a site (a building perception sees only as a class: Tombstone, Goblin
        Cage; or a spawner inferred from its spawns, R15): a death spawn of up to `site_death_wave` if the site
        vanished within `death_ticks` (the Cage's Brawler, Tombstone's last skeletons); else, for swarm sprites only
        (a family with a card of >= 3 bodies: a Knight beside a building is a play), a periodic spawn of up to
        `site_wave`."""
        swarm = any(self.cb.count.get(c, 1) >= 3 for c in self.cb.families.get(fam, ()))
        best = None
        for s in self.sites:
            if s['owner'] != owner or s['first'] >= tick or math.hypot(x - s['x'], y - s['y']) > self.spawn_tiles:
                continue
            if not s.get('inferred') and s['last'] < tick - 2 and tick - s['last'] <= self.death_ticks:
                return dict(kind='death', wave=self.site_death_wave, parent=None, card=s.get('card'), site=True)
            if swarm and (s.get('fam') in (None, fam)):
                best = dict(kind='spawn', wave=self.site_wave, parent=None, card=s.get('card'), since=s['first'],
                            site=True)
        return best

    def _sites(self, tick, unknown):
        for kind, owner, x, y in unknown:
            if kind != 'building':
                continue
            s = min((s for s in self.sites if s['owner'] == owner and not s.get('inferred') and
                     math.hypot(x - s['x'], y - s['y']) <= self.building_radius),
                    key=lambda s: math.hypot(x - s['x'], y - s['y']), default=None)
            if s is None:
                self.sites.append(dict(owner=owner, x=x, y=y, first=tick, last=tick))
                self.stats['unknown_site'] += 1
            else:
                s['last'] = tick
        self.sites = [s for s in self.sites if tick - s['last'] <= self.building_memory]

    def _inferred_site(self, c, card):
        """R15: a swarm of the same family again from (nearly) the same point (`site_tiles`) within a spawner's
        life (`site_window`) before its card could have cycled back, both bursts no bigger than a spawner wave,
        where the proxy table knows an off-vocab spawner building of this family the opponent may have (Tombstone:
        skeletons in pairs; labels flip between the family's cards): an unseen spawner. The play that started it
        stays; this burst and later ones there are its spawns."""
        spawners = [x for x in self.cb.families.get(c['fam'], ()) if x in self.cb.oov and self._building(x) and
                    self.cb.children.get(x) and self.oov_allowed(c['owner'], x)]
        if not spawners or c['peak'][c['fam']] > self.site_wave:
            return None
        cx = sum(p[0] for p in c['pts'])/len(c['pts'])
        cy = sum(p[1] for p in c['pts'])/len(c['pts'])
        for p in self.played:
            if p['owner'] == c['owner'] and p['fam'] == c['fam'] and p['peak'] <= self.site_wave and \
                    0 < c['t0'] - p['t0'] <= self.site_window and math.hypot(cx - p['x'], cy - p['y']) <= self.site_tiles \
                    and not self._cycle_ok(c['owner'], card, p['t0']):
                self.sites.append(dict(owner=c['owner'], x=p['x'], y=p['y'], first=p['t0'], last=c['t0'],
                                       inferred=True, fam=c['fam'], card=spawners[0] if len(spawners) == 1 else None))
                self.stats['inferred_site'] += 1
                return 'spawn', None
        return None

    def _death(self, t):
        lab = t.label()
        return self.cb.death[lab][0], dict(kind='death', wave=self.cb.death_n.get(lab, 1), parent=t.id,
                                           card=t.resolved or lab)

    def _fill(self, main, card, owner):
        if len(main) == 1:
            return main[0][0]
        return self._fill_one(main, Counter(t.body for t in self.live if t.card == card and t.owner == owner))

    @staticmethod
    def _fill_one(main, have):
        total = sum(n for _, n in main)
        k = sum(have.values()) + 1
        return max(main, key=lambda bn: (bn[1]*k/total - have[bn[0]], bn[1]))[0]

    def _body(self, card, owner, x, y, tick, fam=None):
        """Backward-compatible (body, main) for a new unit of `card` (main False for a spawn or death child)."""
        body, spawn = self._new_body(card, owner, x, y, tick, self.cb.fam(card) if fam is None else fam)
        return body, body is not None and spawn is None

    def _building(self, card):
        main = self.cb.main.get(card)
        return bool(main) and all(k == 1 for (_, k), _ in main)

    # -- clusters ------------------------------------------------------------------------------------------------------
    def _coincident(self, c, t, tick):
        """t sits on a member of c seen in this frame: one body detected under two labels."""
        return any(m.id in c['members'] and m.id != t.id and m.last == tick and
                   math.hypot(t.x - m.x, t.y - m.y) <= self.coincide_tiles for m in self.live)

    def _linked(self, c, t):
        """A body of the same family within `link_tiles` of a live member: the same formation (a SkeletonArmy first
        seen at its edge spreads further than `spread_tiles` from that first body)."""
        return any(m.id in c['members'] and m.fam == t.fam and m.id != t.id and
                   math.hypot(t.x - m.x, t.y - m.y) <= self.link_tiles for m in self.live)

    def _absorbed(self, c, t, tick):
        """A closed cluster takes a birth: a late body of the same family while its deployment has bodies left
        (`_room`) within `cluster_ticks` and `cluster_tiles` (or `link_tiles` of a member), or a double detection of
        a member within `relabel_ticks`; never a birth with deployment provenance."""
        if t.hint is not None or c['owner'] != t.owner:
            return False
        if c['fam'] == t.fam and tick - c['t0'] <= self.cluster_ticks and self._room(c) and \
                (math.hypot(t.x - c['x'], t.y - c['y']) <= self.cluster_tiles or self._linked(c, t)):
            return True
        return tick - c['t0'] <= self.relabel_ticks and self._coincident(c, t, tick)

    def _room(self, c):
        """The deployment of closed cluster c has bodies it has not shown yet (fewer members than its card's)."""
        return len([m for m in self.live + self.dead if m.id in c['members'] and m.fam == c['fam']]) < \
            self.cb.count.get(c['card'], 1)

    @staticmethod
    def _source(t):
        """What a birth may cluster with: None for a deployment, else the spawn's parent (or 'site')."""
        if not t.spawn:
            return None
        return t.spawn.get('parent') if t.spawn.get('parent') is not None else 'site'

    def _late_body(self, t, tick):
        """A body of a recent deployment that was never tracked on its own (a 15-skeleton army seen 14 at a time):
        within `repeat_ticks` of a played deployment of its family that still has untracked bodies (fewer tracks
        than its card puts down), next to (`link_tiles`) one of its bodies seen in this frame; never with
        deployment provenance."""
        if t.hint is not None:
            return None
        for p in self.played:
            if p['owner'] != t.owner or p['fam'] != t.fam or not 0 <= tick - p['t0'] <= self.repeat_ticks or \
                    len(p['ids']) >= self.cb.count.get(p['card'], 1) or self._cycle_ok(p['owner'], p['card'], p['t0']):
                continue                 # full, or its card could have cycled back: a new deployment
            if any(m.id in p['ids'] and m.last == tick and m.id != t.id and
                   math.hypot(t.x - m.x, t.y - m.y) <= self.link_tiles for m in self.live):
                return p
        return None

    def _birth(self, t, tick, tower_alive):
        for c in self.clusters:
            if c['owner'] != t.owner or c.get('deferred') or c.get('waiting'):
                continue                     # a deferred or waiting cluster is frozen: no members, no votes
            if c['card'] is None:
                if t.spawn and t.spawn['parent'] in c['members']:
                    continue                 # its spawner's own deployment: the spawn is the spawner's output
                if t.hint is not None and c.get('hint') != t.hint:
                    continue                 # deployment provenance: another deployment's cluster
                if c.get('source') != self._source(t):
                    continue                 # spawns of one parent never mix with a deployment (or other spawns)
                d = math.hypot(t.x - c['x'], t.y - c['y'])
                if (c['fam'] == t.fam and (d <= self.spread_tiles or self._linked(c, t))) or \
                        self._coincident(c, t, tick):
                    c['members'].add(t.id)
                    c['pts'].append((t.x, t.y))
                    t.state = 'pending'
                    return
        for c in self.clusters:
            if c['card'] is not None and not c.get('deferred') and self._absorbed(c, t, tick):
                c['members'].add(t.id)
                for p in self.played:            # the deployment's bodies so far (late-body room)
                    if p['cluster'] is c:
                        p['ids'].add(t.id)
                # a late body of the deployment shares its state; a double detection (another family) is no play
                t.resolved, t.state = c['card'], (c['state'] if t.fam == c['fam'] else 'leftover')
                self.stats['absorbed'] += 1
                return
        p = self._late_body(t, tick)
        if p is not None:
            p['ids'].add(t.id)
            t.resolved, t.state = p['card'], 'played'
            self.stats['late_body_absorbed'] += 1
            return
        if t.owner == 1 and not self.deployable(t.card, t.x, t.y, tower_alive):
            self.stats['birth_outside_zone'] += 1
            return
        t.state = 'pending'
        self.clusters.append(dict(owner=t.owner, x=t.x, y=t.y, t0=tick, votes=Counter(), hits=0, card=None,
                                  fam=t.fam, members={t.id}, peak=Counter(), pts=[(t.x, t.y)], hinted=False,
                                  state='pending', hint=t.hint, by={}, source=self._source(t)))

    def infer_card(self, fam, votes, peak, moved=False, standing=()):
        """Card of one deployment of family `fam`: the cards that can put down `peak` bodies at once (else the
        largest), the burst's label votes choosing among them (none voted: the smallest that fits). A building card
        (GoblinHut) is out when the burst moves or that building already stands and cannot have cycled back (its
        spawns walk off from it)."""
        cands = sorted(c for c in self.cb.families.get(fam, {fam}) if self.cb.main.get(c)
                       and (c not in self.cb.oov or votes.get(c, 0) > 0))     # off-vocab only when perception named it
        if len(cands) > 1:
            mobile = [c for c in cands if not ((moved or c in standing) and self._building(c))]
            cands = mobile or cands
        if len(cands) <= 1:
            return cands[0] if cands else max(votes, key=votes.get)
        count = self.cb.count
        fit = [c for c in cands if count[c] >= peak] or [max(cands, key=lambda c: (count[c], c))]
        voted = [c for c in fit if votes.get(c, 0) > 0]
        if voted:
            return max(voted, key=lambda c: (votes[c], -count[c], c))
        return min(fit, key=lambda c: (count[c], c))

    def _members(self, c, fam=None):
        return [t for t in self.live if t.id in c['members'] and (fam is None or t.fam == fam)]

    def _close(self, c):
        fam_votes = Counter()
        for card, v in c['votes'].items():
            fam_votes[self.cb.fam(card)] += v
        fam = max(fam_votes.items(), key=lambda kv: (kv[1], kv[0]))[0]
        votes = Counter({k: v for k, v in c['votes'].items() if self.cb.fam(k) == fam})
        members = self._members(c, fam)
        moved = any(math.hypot(t.x - t.fx, t.y - t.fy) > self.still_tiles for t in members)
        standing = {t.label() for t in self.live if t.owner == c['owner'] and t.body[1] == 1 and t.spawn is None
                    and t.id not in c['members'] and t.first < c['t0'] and c['t0'] - t.last <= self.ttl
                    and not self._cycle_ok(c['owner'], t.resolved or t.label(), t.first)}
        card = self.infer_card(fam, votes, c['peak'][fam], moved, standing)
        top = max(c['votes'].items(), key=lambda kv: (kv[1], kv[0]))[0]
        if card != top:
            self.stats['card_from_burst'] += 1
        if len(c['votes']) > 1:
            self.stats['vote_contested'] += 1
        c['fam'], c['moved'] = fam, moved
        return card

    def _suppressed(self, c, card):
        """-> None (a play) or (reason, card of the deployment the bodies belong to)."""
        if c['hinted']:
            return None                  # deployment provenance: a play
        fam = c['fam']
        members = self._members(c, fam)
        r = self._spawned(c, members)
        if r:
            return r
        o = self._duplicate(c, card, members)
        if o is not None:
            o['members'] |= c['members']         # its bodies are that deployment's (for later leftovers)
            for p in self.played:
                if p['cluster'] is o:
                    p['ids'] |= c['members']
            return 'duplicate', o['card']
        p = self._leftover(c, card)
        if p is not None:
            p['ids'] |= c['members']
            return 'leftover', p['card']
        return self._inferred_site(c, card)

    def _spawned(self, c, members):
        """Every member was born beside a spawner or a dying parent and the burst is no bigger than one wave: death
        children; spawns when they walk off (`moved`) or when a second copy of their spawner could not have been
        played yet (no cycle since it appeared); else a still body may be a new building: 'wait' up to `spawn_wait`
        ticks for it to move (a spawn stands through its deploy time). A bigger burst is a deployment."""
        if not members or not all(t.spawn for t in members) or c['peak'][c['fam']] > max(t.spawn['wave'] for t in members):
            return None
        kinds = {t.spawn['kind'] for t in members}
        if 'death' in kinds:
            return 'child', members[0].spawn['card']
        sp = members[0].spawn
        if sp.get('site'):                # a site's card is unknown: its spawns walk off
            if c['moved']:
                return 'spawn', sp['card']
            return 'wait' if self._tick - c['t0'] < self.spawn_wait else None
        if c['moved'] or not self._cycle_ok(c['owner'], sp['card'], sp['since']):
            return 'spawn', sp['card']   # it walks off, or a second copy of its spawner could not have been played
        # the spawner card could have cycled back: a still body may be a new building; it gets `spawn_wait`
        return 'wait' if self._tick - c['t0'] < self.spawn_wait else None

    def _duplicate(self, c, card, members):
        """A second cluster of a just-played deployment of the same family (bodies lost for a moment and re-born, a
        misread inside a swarm): within `cluster_ticks` of it, a member born within `link_tiles` of one of its
        bodies, no bigger a burst and only bodies its card has."""
        bodies = {b for b, _ in self.cb.main.get(card) or ()}
        for o in self.clusters:
            if o is c or o['card'] is None or o['owner'] != c['owner'] or o['fam'] != c['fam'] or \
                    not 0 <= c['t0'] - o['t0'] <= self.cluster_ticks or c['peak'][c['fam']] > o['peak'][o['fam']] or \
                    not bodies <= {b for b, _ in self.cb.main.get(o['card']) or ()}:
                continue
            olds = [m for m in self.live + self.dead if m.id in o['members']]
            if any(math.hypot(t.fx - m.x, t.fy - m.y) <= self.link_tiles for t in members for m in olds):
                return o
        return None

    def _leftover(self, c, card):
        """Bodies of a deployment P re-detected after their tracks were lost (a swarm walking through a detection
        gap) look like a new deployment seconds later. Within `repeat_ticks` of P (same owner and family), a smaller
        burst whose card's bodies are all P's, starting where one of P's LOST bodies could have walked
        (`continuity_tiles` + `continuity_speed` per tick since it was last seen), is P again; unless it is P's card
        after `cycle_plays` other plays (a real cycle)."""
        if not self.repeat_ticks:
            return None
        bodies = {b for b, _ in self.cb.main.get(card) or ()}
        cx = sum(p[0] for p in c['pts'])/len(c['pts'])
        cy = sum(p[1] for p in c['pts'])/len(c['pts'])
        for p in self.played:
            o, f, pcard, t0, n, ids = p['owner'], p['fam'], p['card'], p['t0'], p['peak'], p['ids']
            if o != c['owner'] or f != c['fam'] or not 0 <= c['t0'] - t0 <= self.repeat_ticks or \
                    c['peak'][f] >= max(2, n) or not bodies <= {b for b, _ in self.cb.main.get(pcard) or ()}:
                continue
            if card == pcard and self._cycle_ok(o, card, t0):
                continue
            for m in self.live + self.dead:
                if m.id in ids and m.last < c['t0'] and \
                        math.hypot(cx - m.x, cy - m.y) <= self.continuity_tiles + self.continuity_speed*(c['t0'] - m.last):
                    return p
        return None

    def _surfaced(self, c, tick):
        """A tunnelling card (Miner: seen travelling underground from its king) deploys where it stops: wait until
        its body moves < `tunnel_speed` tiles/tick over >= 4 ticks, at most `tunnel_ticks`."""
        m = min(self._members(c), key=lambda t: t.id, default=None)
        if m is None:
            return True
        trail = c.setdefault('trail', [])
        if m.last == tick and (not trail or trail[-1][0] != tick):     # actual sightings only (gaps look still)
            trail.append((tick, m.x, m.y))
            old = [p for p in trail if tick - p[0] >= 4]
            if old and math.hypot(m.x - old[-1][1], m.y - old[-1][2]) < self.tunnel_speed*(tick - old[-1][0]):
                return True
        return tick - c['t0'] >= self.tunnel_ticks

    def _emit(self, c, card, tick, plays):
        why = self._suppressed(c, card)
        if why == 'wait':
            return False
        members = self._members(c)
        if why is None:
            state, resolved = 'played', card
            px, py = sum(p[0] for p in c['pts'])/len(c['pts']), sum(p[1] for p in c['pts'])/len(c['pts'])
            self.played.append(dict(owner=c['owner'], fam=c['fam'], card=card, t0=c['t0'], peak=c['peak'][c['fam']],
                                    ids=set(c['members']), cluster=c, x=px, y=py))
            self.played = [p for p in self.played if tick - p['t0'] <= self.repeat_ticks + self.vote_ticks]
            self.history.append((c['owner'], c['t0'], card))
            if card in TUNNEL and c.get('trail'):
                px, py = c['trail'][-1][1:]       # where it surfaced (or was last seen)
            else:                                 # centroid of first sightings (a swarm's first body is its edge)
                px, py = sum(p[0] for p in c['pts'])/len(c['pts']), sum(p[1] for p in c['pts'])/len(c['pts'])
            plays.append((c['owner'], card, px, py, c['t0']))
            for t in members:                     # a deployment after all: no longer a speculative spawn
                t.spawn = None
            # the deployment's bodies follow its card's composition (GoblinGang: goblins + spear goblins)
            main = self.cb.main.get(card) or []
            fam = sorted((t for t in members if t.fam == c['fam']), key=lambda t: t.id)
            if main and len(fam) <= self.cb.count.get(card, 0):
                have = Counter()
                for t in fam:
                    if t.body_constraint is None:
                        t.body = self._fill_one(main, have) if len(main) > 1 else main[0][0]
                    have[t.body] += 1
        else:
            state, resolved = why
            self.stats[f'{state}_play_suppressed'] += 1
            state = {'duplicate': 'leftover'}.get(state, state)
        c['card'], c['state'] = resolved or card, state
        for t in members:
            t.resolved, t.state = c['card'], state
        return True

    # -- frame ---------------------------------------------------------------------------------------------------------
    def update(self, tick, units, tower_alive, unknown=()):
        """units: [(card, owner, x, y[, score[, spawn_card[, body_constraint]]])], unknown: class-only detections [(kind, owner, x, y)]
        (never tracked as cards; unknown buildings are spawner sites) -> (assigned [(body or None, facing)],
        plays [(owner, card, x, y, tick)]). last_tracks: the track id per unit (None: no body)."""
        if self.last_tick is not None and tick < self.last_tick:
            self.stats['backward_frame_rejected'] += 1            # never rewrite the past: state untouched
            self.last_tracks = [None]*len(units)
            return [(None, (0., 0.))]*len(units), []
        self.last_tick = self._tick = tick
        self._expire(tick)                   # ages before matching: a long gap expires tracks
        self._sites(tick, unknown)
        parsed = self._parse(units)
        got, how, aug = self._plan(parsed, tick)
        self.stats['matched_by_augment'] += aug
        out, plays, seen, ids = [None]*len(parsed), [], [], [None]*len(parsed)
        for i, t in enumerate(got):
            if t is None:
                continue
            if how[i] == 'revive':
                self.dead.remove(t)
                self.live.append(t)
                self.stats['revived'] += 1
            elif how[i] == 'relabel':
                self.stats['cross_family_relabel'] += 1
            card, _, x, y, score, hint, _, constraint = parsed[i]
            if constraint is not None:
                t.body_constraint = constraint
            t.px, t.py = t.x, t.y
            dx, dy = x - t.x, y - t.y
            if self._static(t):              # buildings and spawners do not move: a spawn read with their label
                dx = dy = 0.                 # cannot drag their track away
                x, y = t.x, t.y
            if math.hypot(dx, dy) > .05:
                t.facing = (dx, dy)
            t.x, t.y, t.last = x, y, tick
            t.labels[card] += 1
            if card != t.card:
                self.stats['label_flip'] += 1
            t.fam = self.cb.fam(t.label())
            out[i], ids[i] = (t.body, t.facing), t.id
            seen.append((t, score, card, hint))
        for i, (card, owner, x, y, score, hint, fam, constraint) in enumerate(parsed):
            if got[i] is not None:
                continue
            body, spawn = self._new_body(card, owner, x, y, tick, fam, hint)
            if constraint is not None:
                if constraint != body and constraint in {b for b, _ in self.cb.main.get(card, ())}:
                    spawn = None        # a verified main body cannot be a different inferred child body
                body = constraint
            if body is None:
                self.stats[f'no_body:{card}'] += 1
                out[i] = (None, (0., 0.))
                continue
            self.n += 1
            t = Track(self.n, card, owner, body, x, y, tick, True, fam)
            t.spawn, t.hint = spawn, hint
            t.body_constraint = constraint
            self.live.append(t)
            out[i], ids[i] = (t.body, t.facing), t.id
            self.stats['births'] += 1
            if spawn:
                self.stats[f'{spawn["kind"]}_birth'] += 1
            if constraint is not None and constraint not in {b for b, _ in self.cb.main.get(card, ())}:
                # A configured descendant body is visible, but its parent's play
                # was not observed. Keep the body without inventing that play or
                # a spawn_card/parent link. This also covers orphan death children.
                t.main, t.state = False, 'child'
                self.stats['observed_descendant_no_play'] += 1
            else:
                self._birth(t, tick, tower_alive)
            seen.append((t, score, card, hint))
        # votes/hits for open clusters (members only), then close the ones whose window has passed
        for c in self.clusters:
            if c['card'] is not None or c.get('deferred') or c.get('waiting'):
                continue
            hit, peak = False, Counter()
            for t, score, card, hint in seen:
                if t.id in c['members'] and score >= self.min_score:
                    by = c['by'].setdefault(t.id, Counter())
                    c['votes'][card] += score
                    by[card] += score
                    if hint is not None:
                        c['votes'][hint] += self.hint_weight
                        by[hint] += self.hint_weight
                        c['hinted'] = True
                    peak[t.fam] += 1
                    hit = True
            for f, k in peak.items():
                c['peak'][f] = max(c['peak'][f], k)
            c['hits'] += hit
        keep = []
        for c in self.clusters:
            if c.get('deferred'):
                if self._surfaced(c, tick):
                    card = c.pop('deferred')
                    self._emit(c, card, tick, plays)
                keep.append(c)
                continue
            if c.get('waiting'):                  # a spawn still standing in its deploy time
                if self._emit(c, self._close(c), tick, plays):
                    c.pop('waiting')
                keep.append(c)
                continue
            if c['card'] is None and tick - c['t0'] >= self.vote_ticks and \
                    (c['hits'] >= self.confirm_hits or tick - c['t0'] > self.confirm_ticks):
                if c['hits'] >= self.confirm_hits and c['votes']:
                    card = self._close(c)
                    if card in TUNNEL and not self._surfaced(c, tick):
                        c['deferred'] = card      # still underground: no members, no votes until it surfaces
                        keep.append(c)
                        continue
                    if not self._emit(c, card, tick, plays):
                        c['waiting'] = True
                        keep.append(c)
                        continue
                else:
                    self.stats['unconfirmed_birth'] += 1
                    for t in self._members(c):
                        t.state = 'none'
                    continue
            if c['card'] is None or tick - c['t0'] <= max(self.relabel_ticks, self.cluster_ticks):
                keep.append(c)
        self.clusters = keep
        self._expire(tick)
        self.last_tracks = ids
        return out, plays

    @staticmethod
    def deployable(card, x, y, tower_alive):
        """Opponent deploy zone in our frame. tower_alive: {('left'|'right'): bool} for OUR princess towers."""
        if card in DEPLOY_ANYWHERE or y >= 15.:
            return True
        side = 'left' if x < 9 else 'right'
        return not tower_alive.get(side, True) and y >= 9.


class ClockTracker:
    """HUD clock -> tick, robust to misread frames. Game time is linear in capture time (20 ticks/s), so
    tick = timestamp_ms/50 + offset; only the offset is estimated:
    1. an anchor, best first: `anchor(tick, timestamp_ms)` from the live loop (e.g. match start), else a CONFIRMED
       elixir-phase transition (1->2 at tick 2400, 2->3 at 4800; the new phase must hold for `confirm` frames; the
       boundary is put midway between the last old-phase and first new-phase frame) - the phase head is far more
       accurate than the clock regression;
    2. otherwise the robust centre of all clock readings: a displayed second c says tick in [lo, lo+19],
       lo = (180-c)*20+1 (regulation) or (300-c)*20+1 (overtime, chosen when nearer the current estimate); offset =
       midpoint of the 80th-percentile lower end and 20th-percentile upper end, else the median centre.
    Without timestamps: the plain per-frame reading. Monotonic. Phase deltas (elixir regen) never depend on the
    offset; only absolute boundaries (2400/4800/3600) do."""

    def __init__(self, window=4000, confirm=3):
        from collections import deque
        self.obs, self.tick = deque(maxlen=window), None
        self.confirm, self.fixed, self.candidate = confirm, None, None
        self.last_phase, self.last_ts = None, None

    def anchor(self, tick, timestamp_ms):
        self.fixed = float(tick) - float(timestamp_ms)/50

    def offset(self):
        if self.fixed is not None:
            return self.fixed
        lows = sorted(self.obs)
        n = len(lows) - 1
        lo, hi = lows[int(.8*n)], lows[int(.2*n)] + 19
        return (lo + hi)/2 if lo <= hi else lows[n//2] + 9.5

    def _phase(self, phase, ts):
        if self.candidate is not None:
            target, mid, seen = self.candidate
            if phase == target:
                seen += 1
                if seen >= self.confirm and self.fixed is None:
                    self.fixed = {2: 2400, 3: 4800}[target] - mid/50
                    self.candidate = None
                else:
                    self.candidate = (target, mid, seen)
            else:
                self.candidate = None
        if self.last_phase is not None and phase == self.last_phase + 1 and phase in (2, 3) and \
                self.last_ts is not None and ts - self.last_ts <= 1000 and self.fixed is None:
            self.candidate = (phase, (self.last_ts + ts)/2, 1)
        if self.candidate is None or phase != self.candidate[0]:
            self.last_phase, self.last_ts = phase, ts
        elif self.last_phase is None:
            self.last_phase, self.last_ts = phase, ts

    def __call__(self, clock_s, phase, timestamp_ms=None):
        c = max(0, int(round(float(clock_s))))
        phase = int(phase or 1)
        reg, ot = (180 - c)*20 + 1, (300 - c)*20 + 1
        if timestamp_ms is None:
            t = ot if (phase == 3 or (phase == 2 and c > 60)) else reg
        else:
            ts = float(timestamp_ms)
            self._phase(phase, ts)
            t0 = ts/50
            if self.obs or self.fixed is not None:
                guess = t0 + self.offset()
                lo = min((reg, ot), key=lambda v: abs(v + 9.5 - guess))
            else:
                lo = ot if (phase == 3 or (phase == 2 and c > 60)) else reg
            self.obs.append(lo - t0)
            t = int(round(t0 + self.offset()))
        t = max(t, 0)
        if self.tick is not None:
            t = max(t, self.tick)
        self.tick = t
        return t
