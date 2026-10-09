"""Public geometry reconciliation and explicit hypothetical crown-tower priors.

Never changes sensor outputs. A missed body is unknown, not evidence of death.
Only a correctly identified public HP observation can replace a slot's HP prior.
"""
from dataclasses import replace
from clasher.arena import TileGrid
from clasher.rl.live_inference_contract import VisionEntity

ALIASES = {'Tower': 'Tower', 'TowerPrincess': 'Tower',
           'KingTower': 'KingTower', 'TowerKing': 'KingTower'}
# Fixed arena geometry, declared independently of any live battle or deck.
SLOTS = tuple((owner, card, anchor.x, anchor.y)
              for owner, anchors in enumerate((
                  (TileGrid.BLUE_KING_TOWER, TileGrid.BLUE_LEFT_TOWER, TileGrid.BLUE_RIGHT_TOWER),
                  (TileGrid.RED_KING_TOWER, TileGrid.RED_LEFT_TOWER, TileGrid.RED_RIGHT_TOWER)))
              for card, anchor in zip(('KingTower', 'Tower', 'Tower'), anchors))


class PublicTowerModel:
    def __init__(self):
        from clasher.tower_scaling import tower_stat
        self.episode = None
        self.hp = {}
        self.destroyed = set()
        self.death_confidence = {}
        # PacketBuilder already declares tournament level 11. This is a public
        # static model prior, not a recovered native max-HP measurement.
        self.max_hp = tuple(tower_stat('KingTower' if i%3 == 0 else 'PrincessTower', 'hitpoints', 11)
                            for i in range(6))

    def reconcile(self, public):
        if public.episode_id != self.episode:
            self.episode, self.hp = public.episode_id, {}
            self.destroyed = set()
            self.death_confidence = {}
        from .tower_channel import SLOT_NAMES, parse_observations
        from dataclasses import asdict
        observations = parse_observations([asdict(r) for r in public.tower_observations], public.timestamp_ms)
        channel = {SLOT_NAMES.index(r.slot): r for r in observations}
        for i, observation in channel.items():
            if observation.state == 'destroyed':
                self.destroyed.add(i)
                self.death_confidence[i] = observation.confidence
                self.hp[i] = 0.
            elif i not in self.destroyed and observation.state == 'alive':
                if observation.hp_known and 0 < observation.hp <= self.max_hp[i]:
                    self.hp[i] = observation.hp/self.max_hp[i]
                elif observation.hp_fraction is not None:
                    self.hp[i] = observation.hp_fraction
        selected, others = {}, []
        rejected = duplicates = 0
        for entity in public.entities:
            if entity.card not in ALIASES:
                others.append(entity)
                continue
            slots = [(i, s) for i, s in enumerate(SLOTS) if s[0] == entity.player_id]
            i, slot = min(slots, key=lambda item: (entity.x_tiles-item[1][2])**2+
                                                (entity.y_tiles-item[1][3])**2)
            distance = (entity.x_tiles-slot[2])**2+(entity.y_tiles-slot[3])**2
            # Reject identity/geometry contradictions rather than transplant HP
            # from a false princess detection onto a King.
            if distance > 9 or ALIASES[entity.card] != slot[1]:
                rejected += 1
                continue
            if i in selected:
                duplicates += 1
                if entity.confidence <= selected[i].confidence:
                    continue
            selected[i] = entity
        modeled = []
        priors = 0
        for i, (owner, card, x, y) in enumerate(SLOTS):
            if i in self.destroyed:
                # Preserve a zero-HP slot for PacketBuilder's existing tower ABI.
                modeled.append(VisionEntity(f'public-tower-destroyed-{i}', card, 'building', owner,
                                            x, y, self.death_confidence[i], 0., self.death_confidence[i]))
                continue
            entity = selected.get(i)
            if not channel and entity is not None and entity.hp_fraction is not None:
                self.hp[i] = entity.hp_fraction
            hp = self.hp.get(i, 1.)
            observation = channel.get(i)
            if observation is not None:
                # Slot identity and HP come exclusively from the dedicated
                # channel when present, even if detector labels disagree.
                entity = None
                if observation.state == 'alive':
                    entity = VisionEntity(f'public-tower-observed-{i}', card, 'building', owner,
                        x, y, observation.confidence, hp,
                        observation.confidence if observation.hp_fraction is not None or
                        (observation.hp_known and observation.hp <= self.max_hp[i]) else .01)
            if entity is None:
                priors += 1
                entity = VisionEntity(f'public-tower-prior-{i}', card, 'building', owner,
                                      x, y, .01, hp, .01)
            else:
                entity = replace(entity, card=card, kind='building', hp_fraction=hp,
                                 hp_confidence=entity.hp_confidence if entity.hp_fraction is not None else .01)
            modeled.append(entity)
        return replace(public, entities=tuple(modeled+others)), dict(
            tower_model='public-geometry-prior-v1', tower_priors=priors,
            tower_identity_rejected=rejected, tower_duplicates=duplicates,
            tower_channel_slots=len(channel), tower_destroyed=len(self.destroyed))


def tower_packet_builder(base, *, only_channel=False):
    class TowerPacketBuilder(base):
        def __init__(self, builder):
            super().__init__(builder)
            self.towers = PublicTowerModel()

        def build(self, frame, tick, seat=1, terminal=False):
            if only_channel and not frame.tower_observations and self.towers.episode != frame.episode_id:
                return super().build(frame, tick, seat, terminal)
            if self.towers.episode != frame.episode_id:
                self.hp.clear()
                self.positions.clear()
                self.last_time = None
            modeled, diagnostic = self.towers.reconcile(frame)
            packet, original = super().build(modeled, tick, seat, terminal)
            return packet, dict(original, **diagnostic, raw_visible_entities=len(frame.entities))
    return TowerPacketBuilder
