"""Exact sim lineage from entity insertion call context, never geometric matching.

The engine's entities have IDs but do not persist parent IDs. An instance-local
dict observes EVERY insertion, including projectiles and spell payload carriers.
At insertion the spawning entity is still on the synchronous Python call stack.
Only named source arguments / the entity method receiver are used, never targets.
Unknown call paths fail closed; build validation rejects unresolved sim bodies.
"""
import inspect
from collections import Counter


def is_body(entity):
    return (getattr(entity, 'entity_kind', 4) in (0, 1)
            and getattr(entity.card_stats, 'name', '') not in ('Tower', 'KingTower')
            and entity.max_hitpoints > 0)


class EntityLedger(dict):
    def __init__(self, initial, observer):
        super().__init__(initial)
        self.observer = observer

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.observer.insert(value)


class SimOrigins:
    def __init__(self, battle):
        self.b = battle
        self.deployments, self.origins, self.entities = [], {}, {}
        self.active = None
        self.cast_deployment = {}
        self.ability_commands, self.ability_events, self.ability_hidden = [], [], {}
        self.pending_ability = set()
        self.b.entities = EntityLedger(self.b.entities, self)
        queue = battle._queue_spell_cast

        def deploy_card(owner, card, position):
            index = len(self.deployments)
            row = dict(index=index, owner=int(owner), card=card, tick=int(battle.tick),
                       x=float(position.x), y=float(position.y), is_spell=False)
            self.deployments.append(row)
            previous, self.active = self.active, index
            try:
                # play_match installs PublicRecorder's class-level wrapper
                # AFTER constructing the battle. Resolve it at call time so
                # its accepted-play position context remains intact.
                accepted = type(battle).deploy_card(battle, owner, card, position)
            finally:
                self.active = previous
            if not accepted:
                if any(o['deployment_index'] == index for o in self.origins.values()):
                    raise RuntimeError('engine spawned entities for a rejected deployment')
                self.deployments.pop()
            return accepted

        def queue_spell(name, owner, position, **kw):
            if self.active is None:
                raise RuntimeError('spell queued outside an accepted card command')
            self.deployments[self.active]['is_spell'] = True
            self.cast_deployment[battle._next_spell_cast_sequence] = self.active
            return queue(name, owner, position, **kw)

        battle.deploy_card = deploy_card
        battle._queue_spell_cast = queue_spell

    @staticmethod
    def hidden(entity, tick):
        return bool(getattr(entity, '_underground_deployment', False)
                    or getattr(entity, '_stealth_until', 0) > tick * 50)

    def activate_abilities(self):
        """Deterministic augmentation of play_match's ordinary card-only loop."""
        for owner in (0, 1):
            if not self.b.can_activate_champion_ability(owner):
                continue
            entity, mechanic = self.b._champion_ability_mechanic(owner)
            if self.b.activate_champion_ability(owner):
                self.pending_ability.add(entity.id)
                self.ability_commands.append(dict(uid=self.origins[entity.id]['uid'], owner=owner,
                                                  tick=int(self.b.tick), mechanism=type(mechanic).__name__))

    def observe_abilities(self):
        """Engine stealth/tunnel state transitions, without motion thresholds."""
        for eid in sorted(self.pending_ability):
            entity = self.entities[eid]
            if not entity.is_alive:
                continue
            hidden = self.hidden(entity, self.b.tick)
            was_hidden = self.ability_hidden.get(eid, False)
            if was_hidden and not hidden:
                root = self.origins[eid]
                self.ability_events.append(dict(uid=root['uid'], kind='ability', origin='ability', exact=True,
                                                deployment_index=root['deployment_index'], parent_uid=None,
                                                tick=int(self.b.tick), source_card=root['source_card'],
                                                x=float(entity.position.x), y=float(entity.position.y),
                                                method='engine_hidden_to_visible_after_accepted_ability'))
            self.ability_hidden[eid] = hidden

    def insert(self, entity):
        from clasher.entities import Entity
        parent, cause, dep = None, 'spawn', None
        frame = inspect.currentframe().f_back
        try:
            while frame is not None:
                name, local = frame.f_code.co_name, frame.f_locals
                # At this boundary the engine has resolved the accepted anchor.
                if name == 'deploy_card' and local.get('self') is self.b:
                    pos = local.get('position')
                    if self.active is not None and pos is not None:
                        self.deployments[self.active].update(x=float(pos.x), y=float(pos.y))
                if 'death' in name.lower():
                    cause = 'death'
                receiver = local.get('self')
                candidates = ([receiver] if isinstance(receiver, Entity) else [])
                # These are source parameters at the engine's spawn boundaries.
                from clasher.mechanics.mechanic_base import BaseMechanic
                if (isinstance(receiver, BaseMechanic)
                        or name in ('_spawn_units', '_spawn_death_units', '_native_child_position_without_radius')):
                    candidates += [local.get('entity'), local.get('troop'), local.get('parent')]
                for candidate in candidates:
                    if (isinstance(candidate, Entity) and candidate is not entity
                            and candidate.id in self.origins):
                        parent = self.origins[candidate.id]
                        break
                if parent is not None:
                    break
                cast = local.get('cast')
                if name == '_resolve_pending_spell_casts' and local.get('self') is self.b and cast is not None:
                    dep = self.cast_deployment.get(cast.sequence)
                    break
                frame = frame.f_back
        finally:
            del frame
        if parent is not None:
            dep = parent['deployment_index']
            # A spell projectile/area is a deployment carrier, not a unit parent.
            if parent['_payload']:
                kind, parent_uid = 'main', None
            else:
                kind = 'death' if cause == 'death' or parent['kind'] == 'death' else 'spawn'
                parent_uid = parent['uid'] if parent['_body'] else parent['parent_uid']
        elif dep is not None or self.active is not None:
            dep = self.active if dep is None else dep
            kind, parent_uid = 'main', None
        else:
            kind, parent_uid = 'unresolved', None
        body = is_body(entity)
        row = dict(uid=f'sim:{entity.id}', deployment_index=dep, kind=kind, origin=kind,
                   parent_uid=parent_uid, owner=int(entity.player_id),
                   source_card=self.deployments[dep]['card'] if dep is not None else None,
                   first_tick=int(self.b.tick), exact=kind != 'unresolved',
                   is_building=body and entity.entity_kind == 1, is_deployment=kind == 'main',
                   _body=body, _payload=not body and kind == 'main')
        self.origins[entity.id] = row
        self.entities[entity.id] = entity

    def body_origins(self):
        return [{k: v for k, v in o.items() if not k.startswith('_')}
                for o in self.origins.values() if o['_body']]


def origin_counts(origins):
    return dict(Counter(('exact:' if o['exact'] else 'unresolved:') + o['origin'] for o in origins))
