"""Level-aware planner roots for arm B of the pilot (exploration; reports/bot/levels/DESIGN.md).

ExactLevelRoot.root(info, opponent, rng) shares Resources' public template and
attachment defaults, with three level changes:
1. every root body gets the EXACT stats of its level: the fields in which the level-L export of its producing card
   differs from the level-11 export (configs.LevelConfigs) replace the level-11 template's (no rescaling of
   truncated level-11 values); hp = observed fraction x the level's max HP; a projectile in flight keeps max_hp 1
   and takes the level's damage; a spell carrier in flight names its level's qualified spell;
2. crown towers get the TOWER curve of their level (tower_stat below: 7%/8% then 10% per level, integer-truncated,
   = src/clasher/tower_scaling.py extended below 10; level 6 = 3312/2030 HP as RoyaleSim 16.402 and the live client);
3. the payload's config is the per-seat level config (configs.mixed), cut as fc (configs.CutConfig).
Levels: ours from the planner view (the account's card levels, our tower level); the opponent's tower level as the
client shows it; the opponent's card levels from a fixed fair estimate (profile.OpponentEstimate). A body's level is
its producing card's: among the cards of the owner that produce that body (units, spawns, side-table children), the
ones in that owner's known deck (ours; for the opponent, the root's belief sample hand+cycle), else any producer.
With every level 11 and force=False this is R.root itself.
The shared ThreeMusketeers template uses a coarse 700ms load for all three
unobserved ranks. "Exact" refers to exported level fields, not rank/phase/target
recovery or exact GoblinGiant attachment pairing in ambiguous public graphs.
"""
from __future__ import annotations

import copy
import json
import random

import numpy as np

from bot.levels.configs import SIDE, CutConfig, LevelConfigs, base_cards, qkey

TOWER_BASE = {('KingTower', 'max_hp'): (2400, 7), ('KingTower', 'damage'): (50, 8),
              ('Tower', 'max_hp'): (1400, 8), ('Tower', 'damage'): (50, 8)}
TOWERS = ('KingTower', 'Tower')
SKIP_TOP = {'hp', 'x', 'y', 'id', 'owner', 'target', 'alive', 'facing', 'birth', 'age', 'clock', 'lane',
            'deploy', 'stagger', 'cooldown', 'aim', 'shot_target', 'active', 'tunnel_origin', 'tunnel_destination',
            'death_travel', 'mount', 'rider_rank'}
PUBLIC_LEVEL_CLONE_CARDS = frozenset({'GoblinGiant', 'ThreeMusketeers', 'BattleHealer'})
BATTLE_HEALER_PULSES = frozenset({'BattleHealerSpawnHeal', 'BattleHealerHeal'})


def public_carrier_identity(obj):
    """Existing spell key, or B1 pulse's explicit static public identity.

    HealPulse exports have no spell_name. Both healer pulses also share the
    empty stats name, so their declared area identities must distinguish the
    level payloads. Keep every other carrier's existing selection policy.
    """
    spell = obj.get('spell_name', '')
    if spell or obj.get('class') != 'HealPulse':
        return spell
    for namespace, names in obj.get('public_identity', ()):
        if namespace == 'area_effect' and names and names[0] in BATTLE_HEALER_PULSES:
            return names[0]
    return ''


def tower_stat(name, field, level):
    """Crown tower HP/damage at any level (tower_scaling.tower_stat's curve without its 10-12 restriction)."""
    base, growth = TOWER_BASE[name, field]
    pct = 100
    for lv in range(2, int(level) + 1):
        pct = pct * (100 + (growth if lv <= 9 else 10)) // 100
    return base * pct // 100


def _templates(obj, out, card):
    """(stats name, class, public carrier identity) -> template and card.

    Heal pulses share an empty mechanical stats name/class but have different
    declared public area identities and payloads. Keep both, without adding a
    mechanical spell_name field that the exporter does not supply.
    """
    if isinstance(obj, dict):
        if 'class' in obj and 'stats' in obj:
            out.setdefault((obj['stats']['name'], obj['class'], public_carrier_identity(obj)), (card, obj))
        for k, v in obj.items():
            if k != 'stats':
                _templates(v, out, card)
    elif isinstance(obj, list):
        for v in obj:
            _templates(v, out, card)


def _delta(a, b, skip=()):
    return {k: v for k, v in b.items() if k not in skip and a.get(k) != v}


class ExactLevelRoot:
    def __init__(self, rt, own_levels, opp_level, own_tower, opp_tower, *, lc=None, force=False):
        """own_levels: {card: level}; opp_level: callable card -> level (estimate); force: never bypass to R.root."""
        self.rt, self.R = rt, rt.R
        self.own_levels, self.opp_level = dict(own_levels), opp_level
        self.towers = (int(own_tower), int(opp_tower))
        self.lc = lc or LevelConfigs(rt)
        self.force = force
        self._producers = None
        self._cfg = {}          # seat -> (config, CutConfig, report)
        self._delta = {}        # (card, level, stats name, class) -> (stats delta, top delta)
        self.stats = dict(roots=0, bodies=0, leveled=0, towers=0, unmapped=0)

    # -- levels -------------------------------------------------------------------------------------------------
    def level(self, seat, owner, card):
        return int(self.own_levels.get(card, 11)) if owner == seat else int(self.opp_level(card))

    def trivial(self):
        return not self.force and self.towers == (11, 11) and all(int(v) == 11 for v in self.own_levels.values()) \
            and all(self.opp_level(c) == 11 for c in base_cards(self.R.config))

    def producers(self):
        """stats name -> sorted cards producing it (formations, spawns, side-table children reachable from the card)."""
        if self._producers is None:
            cfg, out, carriers = self.R.config, {}, {}
            from bot.cards.fc_cut import strings
            side = {(t, k): v for t in SIDE if isinstance(cfg.get(t), dict) for k, v in cfg[t].items()}
            for card in base_cards(cfg):
                found = {}
                _templates(cfg['cards'][card], found, card)
                seen, todo = set(), list(strings(cfg['cards'][card]))
                while todo:
                    s = todo.pop()
                    for t in SIDE:
                        v = side.get((t, s))
                        if v is not None and (t, s) not in seen:
                            seen.add((t, s))
                            _templates(v, found, card)
                            todo.extend(strings(v))
                for name, _, spell in found:
                    out.setdefault(name, set()).add(card)
                    if spell:
                        carriers.setdefault(spell, set()).add(card)
            self._producers = {k: sorted(v) for k, v in out.items()}
            self._carriers = {k: sorted(v) for k, v in carriers.items()}
        return self._producers

    def body_card(self, name, owner, seat, deck, spell=None):
        # Empty-name carriers use their existing spell key or scoped declared
        # public pulse identity, never hidden emission/cast provenance.
        if spell:
            card = spell.split(':', 1)[1] if spell.startswith('level') and ':' in spell else spell
            if card not in self.R.config['cards']:
                self.producers()
                cards = self._carriers.get(card, [])
                mine = [c for c in cards if c in deck]
                if not cards:
                    raise ValueError(f'unknown public spell carrier {spell}')
                return (mine or cards)[0]
            return card
        cards = self.producers().get(name, [])
        mine = [c for c in cards if c in deck]
        return (mine or cards or [None])[0]

    def config(self, seat):
        if seat not in self._cfg:
            cfg, report = self.make_config(seat)
            self._cfg[seat] = (cfg, CutConfig(cfg), report)
        return self._cfg[seat]

    def make_config(self, seat):
        """Apply level/Mirror transforms before preparing the one cached fc cut."""
        own = set(self.own_levels)
        return self.lc.mixed(lambda s, c: self.level(seat, s, c),
                             holders={c: seat if c in own else 1 - seat for c in base_cards(self.R.config)})

    def body_delta(self, card, level, name, cls, spell=''):
        """Exact level-L fields of body (name, cls) from `card`'s exports: (stats delta, top-level delta)."""
        key = (card, level, name, cls, spell)
        if key not in self._delta:
            out = None
            e11, eL = self.lc.entry(card, 11), self.lc.entry(card, level)
            if e11 is not None and eL is not None:
                t11, tL = {}, {}
                _templates([e11['card'], e11['tables']], t11, card)
                _templates([eL['card'], eL['tables']], tL, card)
                # Qualified direct spells change identity at non-11 levels;
                # child pulses retain their distinct public payload name.
                spell11 = spell.split(':', 1)[1] if spell.startswith('level') and ':' in spell else spell
                spellL = qkey(card, level) if spell11 == card else spell11
                k11, kL = (name, cls, spell11), (name, cls, spellL)
                if kL not in tL and cls == 'Projectile':
                    # Ordinary in-flight shots inherit the producing body's
                    # level damage; exclude body-only fields below.
                    kL = next((x for x in tL if x[0] == name and x[1] in ('Troop', 'Building')), None)
                    k11 = next((x for x in t11 if x[0] == name and x[1] in ('Troop', 'Building')), None)
                if kL is not None and kL in tL and k11 in t11:
                    a, b = t11[k11][1], tL[kL][1]
                    # Scoped B1 clone capabilities include GG's closed static
                    # rider graph and must follow its level. Keep the existing
                    # C56 prototype policy/bytes outside this specific repair.
                    skip = SKIP_TOP | {'stats'}
                    if card not in PUBLIC_LEVEL_CLONE_CARDS:
                        skip = skip | {'clone_template'}
                    out = (_delta(a['stats'], b['stats']), _delta(a, b, skip))
            self._delta[key] = out
        return self._delta[key]

    # -- root ---------------------------------------------------------------------------------------------------
    def tower(self, e, level):
        name = e['stats']['name']
        if level == 11 or name not in TOWERS:
            return
        fields = ('damage',) if e['class'] == 'Projectile' else ('max_hp', 'damage')
        for field in fields:
            v = e['stats'].get(field)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                e['stats'][field] = type(v)(tower_stat(name, field, level))
        self.stats['towers'] += 1

    def root(self, info, opponent, rng):
        if self.trivial():
            return self.R.root(info, opponent, rng)
        import clasher_core
        return clasher_core.BattleState(self.payload(info, opponent, rng))

    def payload(self, info, opponent, rng):
        from clasher.rl.contract_v5 import CHAMPION_COOLDOWN_GLOBAL, CHAMPION_DURATION_GLOBAL
        R, seat = self.R, info.seat
        names = R.builder.token_names
        obs = info.packet.observation
        cfg, cut, _ = self.config(seat)
        # Unused full-scope entries may be unsupported at a low level, but any
        # card this root can actually play must have the requested physics.
        for owner, player in ((seat, info.own), (1 - seat, opponent)):
            cards = list(player.get('hand') or []) + list(player.get('cycle') or [])
            for card in cards:
                if not card:
                    continue
                level = self.level(seat, owner, card)
                if level != 11 and self.lc.entry(card, level) is None:
                    raise ValueError(f'no exact level export for playable card {card} L{level}, owner {owner}')
        decks = {seat: set(self.own_levels),
                 1 - seat: {c for c in list(opponent.get('hand') or []) + list(opponent.get('cycle') or []) if c}}
        entities = []
        self.stats['roots'] += 1
        for token, row in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]):
            kind = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')[int(np.argmax(row[4:9]))]
            key = (int(token), kind)
            if key not in R.templates:
                raise ValueError(f'no C56 public model template: {names[int(token)]}/{kind}')
            e = copy.deepcopy(R.templates[key])
            x, y = float(row[0])*18, float(row[1])*32
            fx, fy = float(row[27]), float(row[28])
            if info.seat == 1:
                x, y, fx, fy = 18-x, 32-y, -fx, -fy
            owner = info.seat if row[2] else 1-info.seat
            # -- the level step (the only addition to Resources.root) --
            self.stats['bodies'] += 1
            name = e['stats']['name']
            if name in TOWERS:
                self.tower(e, self.towers[0 if owner == seat else 1])
            else:
                identity = public_carrier_identity(e)
                card = self.body_card(name, owner, seat, decks[owner], spell=identity)
                level = self.level(seat, owner, card) if card else 11
                if card is None:
                    self.stats['unmapped'] += 1
                    raise ValueError(f'no producing card for observed root body {name}/{e["class"]}')
                elif level != 11:
                    if self.lc.entry(card, level) is None:
                        raise ValueError(f'no exact level export for root body {name} from {card} L{level}')
                    d = self.body_delta(card, level, name, e['class'], identity)
                    if d is None:
                        raise ValueError(f'no matching exact body template for {name}/{e["class"]} from {card} L{level}')
                    sd, td = d
                    if e['class'] == 'Projectile':
                        sd = {k: v for k, v in sd.items() if k not in ('max_hp',)}
                        td = {k: v for k, v in td.items() if k not in ('shield', 'spell_name', 'clone_template', 'clone_children')}
                    e['stats'].update(copy.deepcopy(sd))
                    e.update(copy.deepcopy(td))
                    self.stats['leveled'] += 1
                    if e.get('spell_name') == card and qkey(card, level) in cfg['cards']:
                        e['spell_name'] = qkey(card, level)
            # -- end of the level step --
            e.update(id=len(entities)+1, owner=owner, x=x, y=y, hp=float(row[9])*e['stats']['max_hp'],
                     alive=True, target=None, deploy=0., stagger=0., facing=[round(fx*1000), round(fy*1000)],
                     age=1000, birth=info.tick-1, lane=1 if x < 9 else 2, clock=dict(interval=max(1, e['stats']['interval']),
                     load=e['stats']['load'], timeline=0, remaining=0, finish=0), cooldown=0.)
            if row[9] < 1:
                e['shield'] = 0.
            if e['king']:
                base = 8 if owner == info.seat else 11
                e['active'] = bool(row[9] < 1 or obs.global_features[base] == 0 or obs.global_features[base+1] == 0)
            else:
                e['active'] = True
            if e['class'] == 'Projectile':
                distance = max(1., e['stats'].get('projectile_range', 0), e['stats']['range'])
                e.update(aim=[x+fx*distance, y+fy*distance], shot_target=None)
            c = e.get('champion')
            if c and owner == info.seat:
                a = c['ability']; now = info.tick*50
                remaining = round(float(obs.global_features[CHAMPION_DURATION_GLOBAL])*a['duration'])
                cooldown = round(float(obs.global_features[CHAMPION_COOLDOWN_GLOBAL])*a['cooldown'])
                if remaining > 0:
                    a.update(active=True, start=now-a['duration']+remaining, last_use=now-a['duration']+remaining)
                elif cooldown > 0:
                    a.update(active=False, start=now-a['duration']-a['cooldown']+cooldown,
                             last_use=now-a['duration']-a['cooldown']+cooldown)
            entities.append(e)
        # as bot/live/levels.py: new Resources supply the public-only GG graph policy; the frozen live runtime's
        # CachedResources (the LIVE-* search tier) has none and keeps its existing behaviour (LV2, 2026-10-17)
        if hasattr(R, 'repair_public_graph'):
            R.repair_public_graph(entities)
        for e in entities:
            c = e.get('champion')
            if c and c['effect']['kind'] == 'Goblin':
                monsters = [m for m in entities if m['owner'] == e['owner'] and m['stats']['name'] == 'Goblinstein']
                m = min(monsters, key=lambda m: (m['x']-e['x'])**2+(m['y']-e['y'])**2, default=None)
                c['effect'].update(monster=m['id'] if m else None, anchor=[m['x'], m['y']] if m else [e['x'], e['y']])
        players = [None, None]; players[info.seat] = info.own; players[1-info.seat] = opponent
        state = random.Random(int(rng.integers(2**63))).getstate()[1]
        rest = json.dumps(dict(tick=info.tick, next_id=len(entities)+1, players=players, entities=entities,
                               pending_casts=[], sudden_death=bool(obs.global_features[4]),
                               rng=dict(state=state[:-1], index=state[-1]), game_over=False, winner=None))
        return rest[:-1] + ', "config": ' + cut.text(players, entities, ()) + '}'


def leaf_native(rt, own_tower, opp_tower):
    """NativeScripts whose leaf crown-tower maxima (leaf.rs: meta.bodies Tower/KingTower .hp) are the towers' level
    maxima, so full towers read 1.0 as in the level-11 game. One maximum serves both sides: the mean of the two
    levels' values (exact when the levels match, as in the pilot). None when both are 11."""
    if (int(own_tower), int(opp_tower)) == (11, 11):
        return None
    import clasher_core
    meta = copy.deepcopy(rt.R.meta)
    for name in TOWERS:
        meta['bodies'][name]['hp'] = float(np.mean([tower_stat(name, 'max_hp', t) for t in (own_tower, opp_tower)]))
    return clasher_core.NativeScripts(json.dumps(meta))
