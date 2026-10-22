"""Calibrated-engine public arena and own HUD -> the unchanged live FrameBuilder and Session.

Runtime must be bootstrapped before importing any engine modules. This producer never reads the other player's
hand, cycle, elixir or RNG. Root-card tags track public bodies, including descendants; tags are never features.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import sys
import zlib

from . import featurize as F
from .sim_rsim import NATIVE_ID, CARRIERS, new_builder, record_from_line


def install_root_tracking(battle):
    """Annotate inserted entities with creating card identity, preserving dict behavior and engine rules."""
    if getattr(battle, '_pv1_tracking', False):
        return
    from clasher.entities import Entity
    from clasher.spells import Spell

    def creating_card(new):
        frame = sys._getframe(2)
        try:
            while frame is not None:
                local = frame.f_locals
                if frame.f_code.co_name == 'deploy_card' and 'card_name' in local:
                    return local['card_name']
                own = local.get('self')
                if isinstance(own, Spell):
                    return own.name
                for key in ('self', 'source_entity', 'parent', 'spawner', 'source'):
                    parent = local.get(key)
                    if isinstance(parent, Entity) and parent is not new:
                        root = getattr(parent, '_pv1_root_card', None)
                        if root is not None:
                            return root
                frame = frame.f_back
        finally:
            del frame  # Stack frames must not keep an entire battle alive after insertion.
        return None

    class RootDict(dict):
        def __setitem__(self, key, entity):
            if key not in self:
                entity._pv1_root_card = creating_card(entity)
            super().__setitem__(key, entity)

    battle.entities = RootDict(battle.entities)
    battle._pv1_tracking = True


def body_name(raw, root):
    if raw == 'Tower':
        return 'PrincessTower'
    if raw == 'KingTower' or raw in F.catalog().body_idx:
        return raw
    # Formation card names sometimes identify a single body type in the engine. Only unambiguous mappings
    # from the same pinned live catalog are allowed; do not guess one body of a multi-body formation.
    card = F.catalog().by_name.get(raw)
    if raw == root and card and len(card['bodies']) == 1:
        return card['bodies'][0]
    raise F.FeatureError(f'engine body has no live identity: {raw!r}, root={root!r}')


class OursFrames:
    """One acting perspective. All six towers and arena bodies are public; only own HUD is accessed."""

    def __init__(self, battle, seat, order, seed):
        self.battle, self.seat, self.order = battle, int(seat), list(order)
        self.builder = new_builder(self.order)
        self.token = zlib.crc32(f'ours-{seed}-{seat}'.encode())+1
        self.towers = {}
        self.stats = {}
        install_root_tracking(battle)

    def xy(self, position):
        x, y = position.x, position.y
        if self.seat == 1:
            x, y = 18-x, 32-y
        return round(x*1000), round(y*1000)

    def frame(self):
        b = self.battle
        own = b.players[self.seat]
        hand, cycle = list(own.hand), list(own.cycle_queue)
        if len(hand) != 4 or any(c not in self.order for c in hand) or not cycle:
            raise F.FeatureError('engine own HUD has an incomplete hand or next card')
        units, aims, present = [], [], set()
        for entity in b.entities.values():
            uid = int(entity.id)+1
            raw = getattr(entity.card_stats, 'name', '')
            owner = 0 if entity.player_id == self.seat else 1
            x, y = self.xy(entity.position)
            if int(entity.entity_kind) == 1 and raw in ['Tower', 'KingTower']:
                row = [uid, owner, x, y, -1, max(0, round(entity.hitpoints)), round(entity.max_hitpoints), body_name(raw, None)]
                self.towers[uid] = row
                present.add(uid)
                units.append(row)
                continue
            if not entity.is_alive or entity.hitpoints <= 0 or not entity.is_visible_to(self.seat):
                continue
            spell = getattr(entity, 'spell_name', None)
            if spell in CARRIERS:
                if getattr(entity, 'launch_delay', 0.) > 0:
                    continue
                aim = getattr(entity, 'target_position', None)
                if aim is None or spell not in NATIVE_ID:
                    raise F.FeatureError('engine visible spell carrier has no public aim or live card identity')
                ax, ay = self.xy(aim)
                units.append([uid, owner, x, y, NATIVE_ID[spell], -1, -1, spell+'Spell'])
                aims.append([uid, ax, ay])
                continue
            # Ordinary attack projectiles and temporary area effects are not live record units.
            if int(entity.entity_kind) not in (0, 1):
                continue
            root = getattr(entity, '_pv1_root_card', None)
            if root not in NATIVE_ID:
                raise F.FeatureError(f'engine visible body lacks its creating card: {raw!r}, {root!r}')
            units.append([uid, owner, x, y, NATIVE_ID[root], round(entity.hitpoints), round(entity.max_hitpoints),
                          body_name(raw, root)])
        # The live reader marks destroyed public towers dead. A removed tower is not a stale positive HP row.
        for uid, previous in self.towers.items():
            if uid not in present:
                row = list(previous); row[5] = 0; units.append(row)
        return dict(t=int(b.tick), b=self.token, s=0, e=round(float(own.elixir)*10000),
                    h=[self.order.index(c) for c in hand], n=self.order.index(cycle[0]), u=units, p=aims, m=0)

    def record(self):
        line = json.dumps(self.frame())
        got, why = record_from_line(line, self.builder)
        if got is None:
            raise F.FeatureError(f'engine live record refused: {why}')
        return got, line


@contextmanager
def bind_matches(players):
    """Bind to the unchanged level-aware match constructor inside a private, single-thread actor process.

    The frozen match loop, CommandQueue, five-tick polling and action mapping execute unchanged. Only this
    process's constructor reference is wrapped and restored. Planner/HP1 source and runtime files are untouched.
    """
    import bot.levels.match as levels
    original = levels.level_battle
    captured = []

    def construct(*args, **kwargs):
        battle = original(*args, **kwargs)
        if captured:
            raise RuntimeError('more than one true battle constructed in a policy match')
        captured.append(battle)
        install_root_tracking(battle)
        for player in players.values():
            if hasattr(player, 'bind_ours'):
                player.bind_ours(battle)
        return battle

    levels.level_battle = construct
    try:
        yield
    finally:
        levels.level_battle = original


class PolicyOursPlayer:
    deadline_seconds = None

    def __init__(self, model, name='pretrain-v1-ours'):
        from .policy_trace import PolicyTrace
        if model.training:
            raise ValueError('actors must use the evaluation-mode sampled policy')
        self.model, self.name = PolicyTrace(model), name
        self.battle = None
        self.counts = {}
        self.rows = []

    def bind_ours(self, battle):
        self.battle = battle

    def start(self, ctx):
        from .policy import Session
        if self.battle is None:
            raise RuntimeError('calibrated-engine policy was not bound to the true match')
        self.frames = OursFrames(self.battle, ctx.seat, ctx.own_order, ctx.seed)
        seed = (int(ctx.seed) ^ (0x9E3779B97F4A7C15*(ctx.seat+1))) % (1 << 63)
        self.session = Session(self.model, seed)
        self.shadow_builder, self.shadow_hist = new_builder(ctx.own_order), F.History()

    def act(self, view):
        from bot.players.base import Decision, WAIT
        (record, extras), line = self.frames.record()
        if self.frames.builder.decided(record['tick']):
            return Decision(WAIT, 0, None)
        gap = record['tick']-self.session.last_tick if self.session.last_tick is not None else F.POLL
        self.model.clear()
        decision = self.session.step(record, extras)
        logp = self.model.log_probability(decision, gap=gap)
        shadow, why = record_from_line(line, self.shadow_builder)
        if shadow is None:
            raise F.FeatureError(f'engine shadow refused record: {why}')
        features = F.observe(shadow[0], shadow[1], self.shadow_hist)
        if F.feature_bytes(features) != F.feature_bytes(self.session.last_feat):
            raise F.FeatureError('engine logged-record replay differs from acting features')
        if decision.status == 'play':
            if not view.can_act:
                raise F.FeatureError('engine channel and public-record channel disagree')
            self.session.accepted(decision)
            self.shadow_hist.submit(decision.tick, decision.slot, decision.card, decision.tile)
        self.counts[decision.status] = self.counts.get(decision.status, 0)+1
        # Readiness log is bounded: full training actors publish chunks instead of retaining a whole run.
        if len(self.rows) >= 2000:
            raise RuntimeError('readiness player exceeded one-game log bound')
        self.rows.append((record, extras, decision, F.feature_bytes(features), logp))
        return Decision(int(decision.action), 0, dict(status=decision.status, value=decision.value))

    def close(self):
        pass
