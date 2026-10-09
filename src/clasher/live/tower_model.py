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
        self.episode = None
        self.hp = {}

    def reconcile(self, public):
        if public.episode_id != self.episode:
            self.episode, self.hp = public.episode_id, {}
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
        for i, (owner, card, x, y) in enumerate(SLOTS):
            entity = selected.get(i)
            if entity is not None and entity.hp_fraction is not None:
                self.hp[i] = entity.hp_fraction
            hp = self.hp.get(i, 1.)
            if entity is None:
                entity = VisionEntity(f'public-tower-prior-{i}', card, 'building', owner,
                                      x, y, .01, hp, .01)
            else:
                entity = replace(entity, card=card, kind='building', hp_fraction=hp,
                                 hp_confidence=entity.hp_confidence if entity.hp_fraction is not None else .01)
            modeled.append(entity)
        return replace(public, entities=tuple(modeled+others)), dict(
            tower_model='public-geometry-prior-v1', tower_priors=6-len(selected),
            tower_identity_rejected=rejected, tower_duplicates=duplicates)


def tower_packet_builder(base):
    class TowerPacketBuilder(base):
        def __init__(self, builder):
            super().__init__(builder)
            self.towers = PublicTowerModel()

        def build(self, frame, tick, seat=1, terminal=False):
            if self.towers.episode != frame.episode_id:
                self.hp.clear()
                self.positions.clear()
                self.last_time = None
            modeled, diagnostic = self.towers.reconcile(frame)
            packet, original = super().build(modeled, tick, seat, terminal)
            return packet, dict(original, **diagnostic, raw_visible_entities=len(frame.entities))
    return TowerPacketBuilder
