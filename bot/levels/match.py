"""Per-seat card and tower levels for bot.players.ours.play_match (exploration; reports/cards/levels/RESULTS.md).

    levels = {'cards': {seat: int | {card: level}}, 'towers': {seat: level}, 'planner': 'exact' | 'l11'}
    levels = max_levels()     # Sam's eval rule: every card on both sides and both King towers at level 16

A missing seat (or card of a {card: level} map) is level 11. levels=None is not handled here: play_match keeps
its exact level-11 code path.

1. TRUE GAME (the Python match engine, the runtime's src/clasher): PlayerState(card_levels=..., tower_level=...)
   per seat. The engine already scales every deployment by the deploying player's card level (resolve_card_play),
   death spawns / spawner children / spells inherit it, and Mirror plays the copy at Mirror's level + 1. Crown
   towers: the engine's tower_scaling.tower_stat only covers 10-12; while the battle is built, levels outside
   10-12 take bot/levels/root.tower_stat (the same 7%/8%, then 10% after level 9 curve, integer-truncated; level
   16 checked against RoyaleSim 16.402), HP and damage. 10-12 keep the engine's own values.
2. PLANNERS (search players with a `root_fn` hook: K4S-*/K4C-*/K4L-* MultiSearchPlayer subclasses): planner='exact'
   installs MatchLevelRoot, the BOT LEAD's ExactLevelRoot (exact level-L root bodies, tower curve, per-seat
   native rollout config via LevelConfigs.mixed, fc cut via CutConfig) plus a Mirror generalisation: the native
   Mirror resolver reads cards['level12:<card>'], so for a Mirror at level M those entries become the level-(M+1)
   exports (same leaf_elixir_share as the level-12 entries). The leaf/scripted crown maxima take the tower level
   (root.leaf_native). The planner is told the declared levels of BOTH seats: fair when the level rule is public
   (max_levels: everyone at 16); with private per-card opponent levels use planner='l11' or the pilot's estimate.
   Policy players (v1, R3a, students, the R3a proposer and the learned rollout opponent) are unchanged: they read
   the same contract-v5 packet (hp fractions, level-11 static columns) as at level 11.
   LIVE-* players: their search tier (WallCandidatePlayer). Not level-aware (planning stays level 11, recorded per
   seat in the result): players without root_fn (PolicyPlayer, K4S-b*/KU SearchPlayer, aliased: wrappers),
   pooled K4L players (p<N>: worker processes keep level-11 leaf metadata), the extra roots of K4S-m<M>, K4L D
   (determinize) roots.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
from collections import deque
from pathlib import Path

MAX_LEVEL = 16      # live16402c gamedata: every rarity's levelCount + relativeLevel = 16; towerLevel max 16
CACHE = Path(os.environ.get('CLASHER_LEVELS_CACHE', '/mpac/sdicks02/jobs/clasher/cards/levels/level-configs'))


def max_levels(level=MAX_LEVEL):
    return dict(cards={0: level, 1: level}, towers={0: level, 1: level}, planner='exact')


def from_lists(levels=None, tower_levels=None, planner='exact'):
    """RoyaleSim play_match arguments ([{card: level} per seat], [tower0, tower1]) -> a play_match levels spec."""
    out = dict(cards={}, towers={}, planner=planner)
    if levels is not None:
        out['cards'] = {s: dict(levels[s]) for s in (0, 1)}
    if tower_levels is not None:
        out['towers'] = {s: int(tower_levels[s]) for s in (0, 1)}
    return out


def _seat(d, seat, default=11):
    d = d or {}
    return d.get(seat, d.get(str(seat), default))


def _level(v):
    if isinstance(v, bool) or int(v) != v or not 1 <= int(v) <= MAX_LEVEL:
        raise ValueError(f'level {v!r} not an integer in 1..{MAX_LEVEL}')
    return int(v)


def resolve(levels, decks):
    """-> dict(cards=[{card: level} for each seat's deck], towers=[t0, t1], planner, tag)."""
    unknown = set(levels) - {'cards', 'towers', 'planner'}
    if unknown:
        raise ValueError(f'unknown levels keys {sorted(unknown)}')
    planner = levels.get('planner', 'exact')
    if planner not in ('exact', 'l11'):
        raise ValueError(f'planner {planner!r} not in exact/l11')
    cards = []
    for seat in (0, 1):
        v = _seat(levels.get('cards'), seat)
        if isinstance(v, dict):
            extra = set(v) - set(decks[seat])
            if extra:
                raise ValueError(f'seat {seat} levels for cards not in its deck: {sorted(extra)}')
            cards.append({c: _level(v.get(c, 11)) for c in decks[seat]})
        else:
            cards.append({c: _level(v) for c in decks[seat]})
    towers = [_level(_seat(levels.get('towers'), s)) for s in (0, 1)]
    trivial = towers == [11, 11] and all(v == 11 for d in cards for v in d.values())
    return dict(cards=cards, towers=towers, planner=planner, tag=tag(cards, towers), trivial=trivial)


def tag(cards, towers):
    """Short row label: 'card16-tower16' when uniform, else per seat."""
    per = []
    for seat in (0, 1):
        vals = set(cards[seat].values())
        per.append(f'card{vals.pop()}' if len(vals) == 1 else 'cardmixed')
    if per[0] == per[1] and towers[0] == towers[1]:
        return f'{per[0]}-tower{towers[0]}'
    return f'{per[0]}-tower{towers[0]}/{per[1]}-tower{towers[1]}'


# -- true game -----------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def tower_curve():
    """Crown tower stats outside the engine's 10-12 range from the full curve (bot/levels/root.tower_stat)."""
    import clasher.tower_scaling as ts
    from bot.levels.root import tower_stat
    original = ts.tower_stat
    names = {'PrincessTower': 'Tower', 'KingTower': 'KingTower'}
    fields = {'hitpoints': 'max_hp', 'damage': 'damage'}

    def extended(name, field, level=11):
        if isinstance(level, int) and not isinstance(level, bool) and not 10 <= level <= 12:
            return tower_stat(names[name], fields[field], level)
        return original(name, field, level)
    ts.tower_stat = extended
    try:
        yield
    finally:
        ts.tower_stat = original


def install_engine_levels():
    """Spell construction at levels != 11 (process-wide, idempotent; level-11 construction is unchanged).

    The runtime refuses a non-11 level for spells whose level-11 values are measured clasher.balance pins that
    its raw data does not reproduce ('<spell> level L needs a reconciled <field> override': Earthquake damage/
    building/crown, Tornado crown, ...). At level L != 11 such a pin scales with the game's level table, truncated:
    pin * multiplier(L) / multiplier(11) (RoyaleSim 16.402 at level 16: Earthquake crown 49 -> 78, Tornado hit
    84 -> 134). Unpinned fields keep the engine's own level formula. Clone ('inheritance is not implemented')
    has no level-scaled stat (copies keep their own level, 1 HP) and plays its level-11 spell object."""
    import copy
    import clasher.dynamic_spells as ds
    if getattr(ds, '_match_levels', False):
        return
    from clasher.balance import TOURNAMENT_SPELL_OVERRIDES
    from clasher.stat_scaling import level_multiplier
    pins = copy.deepcopy(TOURNAMENT_SPELL_OVERRIDES)   # after Runtime's pin-set adjustments
    crown_reconciled = set()

    def scaled(name, field, level):
        v = pins.get(name, {}).get(field)
        return None if v is None else float(int(v * level_multiplier(level) / level_multiplier(11) + 1e-9))

    o_check, o_aux, o_crown, o_create = (ds._checked_level_override, ds._spell_aux_damage, ds._crown_damage,
                                         ds.create_spell_from_json)

    def checked(name, field, raw_value, level, tournament_raw_value):
        current = ds.tournament_spell_stat(name, field)
        if level != 11 and current is not None and current != tournament_raw_value:
            return scaled(name, field, level)
        return o_check(name, field, raw_value, level, tournament_raw_value)

    def aux(name, field, fallback=None, *, level=11):
        if level != 11 and ds.tournament_spell_stat(name, field) is not None:
            return scaled(name, field, level)
        return o_aux(name, field, fallback, level=level)

    def crown(name, damage, percent, *, level=11):
        if level != 11 and name in crown_reconciled:
            return scaled(name, 'crown_tower_damage', level)
        return o_crown(name, damage, percent, level=level)

    def create(spell_data, object_registry=None, *, level=11):
        try:
            return o_create(spell_data, object_registry, level=level)
        except ValueError as ex:
            msg = str(ex)
            name = msg.split(' level ', 1)[0]
            if level == 11:
                raise
            if msg.endswith('needs a reconciled crown damage override') and name in TOURNAMENT_SPELL_OVERRIDES:
                # The guard compares the level-11 pin with the formula; the pin itself scales (crown above).
                crown_reconciled.add(name)
                pin = TOURNAMENT_SPELL_OVERRIDES[name].pop('crown_tower_damage')
                try:
                    return o_create(spell_data, object_registry, level=level)
                finally:
                    TOURNAMENT_SPELL_OVERRIDES[name]['crown_tower_damage'] = pin
            if msg == f'Clone level {level} inheritance is not implemented':
                return o_create(spell_data, object_registry)
            raise
    ds._checked_level_override, ds._spell_aux_damage, ds._crown_damage = checked, aux, crown
    ds.create_spell_from_json = create
    ds._match_levels = True


class L11Packets:
    """The policy-facing packet of a non-11 game, as a level-11 game shows the same board: entity column 30
    (base_damage = log1p(entity.damage)/8, the only level-dependent packet column; hp is a fraction) takes the
    level-11 value of the row's (token, kind) template (R.templates, the bodies of level-11 demos). Validated on
    level-11 games: the mapping reproduces their packets (reports/cards/levels/RESULTS.md)."""

    def __init__(self, R):
        import math
        import numpy as np
        self.np = np
        self.f30 = {}
        for key, e in R.templates.items():
            d = e.get('stats', {}).get('damage')
            if isinstance(d, (int, float)) and not isinstance(d, bool):
                self.f30[key] = np.float32(min(1., max(0., math.log1p(max(0., float(d))) / 8.)))
        self.counts = dict(rows=0, changed=0, unmapped=0)

    def info(self, info):
        import copy
        from dataclasses import replace
        np = self.np
        obs = info.packet.observation
        feats = np.array(obs.entity_features, copy=True)
        kinds = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
        for i in np.flatnonzero(np.asarray(obs.entity_mask)):
            row = feats[i]
            v = self.f30.get((int(obs.entity_ids[i]), kinds[int(np.argmax(row[4:9]))]))
            self.counts['rows'] += 1
            if v is None:
                self.counts['unmapped'] += 1
            elif row[30] != v:
                row[30] = v
                self.counts['changed'] += 1
        o = copy.copy(obs)
        object.__setattr__(o, 'entity_features', feats)
        packet = copy.copy(info.packet)
        object.__setattr__(packet, 'observation', o)
        return replace(info, packet=packet)


def level_battle(seed, decks, loader, spec):
    """stage2_matches.battle with per-seat card and tower levels (spec = resolve(...))."""
    import random
    install_engine_levels()
    from clasher.player import PlayerState
    from differential import BattleState
    players = [PlayerState(owner, deck=list(deck), hand=list(deck[:4]), cycle_queue=deque(deck[4:]),
                           card_levels=dict(spec['cards'][owner]), tower_level=spec['towers'][owner])
               for owner, deck in enumerate(decks)]
    with tower_curve():
        return BattleState(players=players, rng=random.Random(seed), card_loader=loader)


# -- planners ------------------------------------------------------------------------------------------------------
class _LockedConfigs:
    """LevelConfigs whose per-level cache build is serialised across processes (headline forks many workers)."""

    def __new__(cls, rt, cache=None):
        from bot.levels.configs import LevelConfigs

        class Locked(LevelConfigs):
            def load(self, level):
                level = int(level)
                if level not in self.levels:
                    self.dir.mkdir(parents=True, exist_ok=True)
                    with open(self.dir / '.build.lock', 'w') as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        LevelConfigs.load(self, level)
                return self.levels[level]

            def supported(self):
                if not hasattr(self, '_supported'):
                    self.dir.mkdir(parents=True, exist_ok=True)
                    with open(self.dir / '.build.lock', 'w') as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        LevelConfigs.supported(self)
                return self._supported
        return Locked(rt, cache=cache or CACHE)


def level_configs(rt):
    lc = getattr(rt, '_match_level_configs', None)
    if lc is None:
        lc = rt._match_level_configs = _LockedConfigs(rt)
    return lc


def mirror_config(lc, cfg, copy_level):
    """cards['level12:<c>'] (the native Mirror resolver's fixed key) -> the level-`copy_level` copy of <c>.
    Returns (config, unsupported cards). copy_level 12 = cfg unchanged."""
    from bot.levels.configs import SIDE, qkey
    if copy_level == 12:
        return cfg, []
    cards, tables, bad = dict(cfg['cards']), {t: dict(cfg[t]) for t in SIDE if isinstance(cfg.get(t), dict)}, []
    for key in [k for k in cfg['cards'] if k.startswith('level12:')]:
        card = key[len('level12:'):]
        e = lc.entry(card, copy_level)
        if e is None:
            bad.append(card)
            continue
        new = _with_shares(e['card'], cfg['cards'][key])
        cards[key] = new
        cards.setdefault(qkey(card, copy_level), e['card'])
        for t, rows in e['tables'].items():
            tables.setdefault(t, {}).update(rows)
    out = dict(cfg)
    out['cards'] = cards
    out.update(tables)
    return out, bad


def _with_shares(entry, mirrored):
    """The level-12 Mirror entries carry Mirror's cost share per formation body (mirror_snapshot.extend)."""
    import copy
    entry = copy.deepcopy(entry)
    for seat in (0, 1):
        units, ref = (entry.get('units') or [[], []])[seat], (mirrored.get('units') or [[], []])[seat]
        if len(units) != len(ref):
            continue
        for unit, source in zip(units, ref):
            unit['stats']['leaf_elixir_share'] = source['stats'].get('leaf_elixir_share')
            if unit.get('clone_template') is not None and source.get('clone_template') is not None:
                unit['clone_template']['stats']['leaf_elixir_share'] = \
                    source['clone_template']['stats'].get('leaf_elixir_share')
    return entry


def match_root(rt, seat, spec):
    """MatchLevelRoot for the player in `seat` (spec = resolve(...)): own = its deck's levels, the opponent's
    declared levels, both tower levels."""
    from bot.levels.configs import CutConfig
    from bot.levels.root import ExactLevelRoot
    own, opp = spec['cards'][seat], spec['cards'][1 - seat]
    opp_default = next(iter(set(opp.values()))) if len(set(opp.values())) == 1 else 11

    class MatchLevelRoot(ExactLevelRoot):
        def config(self, root_seat):
            if root_seat not in self._cfg:
                cfg, _, report = ExactLevelRoot.config(self, root_seat)
                holder = 'Mirror' in self.own_levels
                copy_level = self.level(root_seat, root_seat if holder else 1 - root_seat, 'Mirror') + 1
                if 'Mirror' in self.R.config['cards'] and copy_level != 12:
                    cfg, bad = mirror_config(self.lc, cfg, copy_level)
                    report = dict(report, mirror_level=copy_level, mirror_unsupported=bad)
                    self._cfg[root_seat] = (cfg, CutConfig(cfg), report)
            return self._cfg[root_seat]

    return MatchLevelRoot(rt, own, lambda card: opp.get(card, opp_default), spec['towers'][seat],
                          spec['towers'][1 - seat], lc=level_configs(rt))


def install_planner(rt, player, seat, spec):
    """Level-aware planning for `player` (a root_fn search player, or a LIVE-* LivePlayer's search tier) when
    spec['planner'] == 'exact'. Returns the status recorded in the match result."""
    if spec['planner'] != 'exact':
        return 'l11'
    search = player if hasattr(type(player), 'root_fn') else getattr(player, 'search', None)
    if search is None or not hasattr(type(search), 'root_fn'):
        return 'l11 (no root_fn)'
    if spec['trivial']:
        return 'exact (all 11 = R.root)'
    if getattr(search, 'pool_size', 0):
        return f'l11 (pooled p{search.pool_size}: workers keep level-11 metadata)'
    from bot.levels.root import leaf_native
    root = match_root(rt, seat, spec)
    search.root_fn, search.level_root = root.root, root
    native = leaf_native(rt, spec['towers'][seat], spec['towers'][1 - seat])
    start = search.start

    def start_with_leaf(ctx):
        start(ctx)
        if native is not None:
            search.p.core.native = native
    search.start = start_with_leaf
    return 'exact'
