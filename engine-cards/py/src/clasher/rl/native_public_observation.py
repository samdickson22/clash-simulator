"""Strict public-schema projection of the pinned offline native reference.

This supplies exact reference measurements, not a camera detector. Ordinary
snapshots cannot establish every effect identity or card form. Unsupported
objects fail explicitly. Retraction does not remove Tesla trapdoors or health
bars from the rendered arena; combat targetability stays outside this schema.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from dataclasses import dataclass

import numpy as np

from .own_card_history import AcceptedOwnPlay
from .public_observation import (
    ConfidenceAwareActorObservation,
    validate_real_play_feature_contract,
)
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    VISIBLE_CARD_SLOTS,
    ActorObservation,
    StructuredObservationBuilder,
)

# Base ground bodies whose ordinary snapshot identity is unambiguous. This is
# observation coverage, not a certificate of their simulated combat mechanics.
SUPPORTED_BODY_CARDS = frozenset({
    'Knight', 'Archers', 'Skeletons', 'Goblins', 'Giant', 'HogRider',
    'Prince', 'DarkPrince', 'Musketeer', 'Cannon', 'IceGolem', 'IceSpirit', 'Tesla',
})
PUBLIC_REFERENCE_CARDS = tuple(sorted(SUPPORTED_BODY_CARDS | {'Fireball', 'Log', 'Zap'}))
TOWER_ANCHORS = {
    (0, 3500, 6500): ('Tower', 3052),
    (0, 14500, 6500): ('Tower', 3052),
    (0, 9000, 3000): ('KingTower', 4824),
    (1, 3500, 25500): ('Tower', 3052),
    (1, 14500, 25500): ('Tower', 3052),
    (1, 9000, 29000): ('KingTower', 4824),
}


class NativePublicProjectionError(ValueError):
    """The source cannot establish all fields needed by this projection."""


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise NativePublicProjectionError(f'invalid {name}')
    return value


# Native arena extent in logic units (thousandths of a tile).
NATIVE_ARENA_WIDTH = 18000
NATIVE_ARENA_HEIGHT = 32000
# Native objects may legitimately sit outside the arena rectangle. For the
# supported pilot roster the worst case is the thrown Log: LogProjectile starts
# MinDistance=3000 behind its placement along the owner's y axis (balance.py
# PROJECTILE_FIELD_OVERRIDES; tests/fixtures/native_public_log_phases shows
# 11500 placement, 9220 at +2 ticks at speed 360, so start=8500) and x is
# unchanged. Rolling spells are restricted to the deploy zone, whose outermost
# tile centres are y=500 (owner 0) and y=31500 (owner 1), so the thrown log
# reaches y=-2500 or y=34500: 2500 outside. Everything else stays inside:
# LogicBattle::spawnObject clamps character centres (Goblins/Skeletons
# formation spread, Tesla/Cannon anchors) to [250, extent-250]; Fireball is
# launched from its owner's King Tower; Zap resolves at its tile centre; the
# rolling Log travels 10100 forward from a deploy-zone tile (at most 30600 or
# at least 1400). The margin is that 2500 plus one 500 half-tile of safety.
# Anything farther is a corrupt frame and still fails the projection.
NATIVE_OUT_OF_ARENA_MARGIN = 3000


def clip_native_position(x: int, y: int) -> tuple[int, int]:
    """Clip native logic coordinates onto the arena for observation features."""
    return (
        min(max(x, 0), NATIVE_ARENA_WIDTH),
        min(max(y, 0), NATIVE_ARENA_HEIGHT),
    )


def native_public_position(x, y) -> tuple[int, int]:
    """Validate raw native coordinates and return their clipped feature position.

    Positions within ``NATIVE_OUT_OF_ARENA_MARGIN`` outside any of the four
    arena edges are accepted and clipped; raw values remain in the stored
    native frame and in :func:`native_out_of_arena_positions`.
    """
    for value, name in ((x, 'x'), (y, 'y')):
        if type(value) is not int:
            raise NativePublicProjectionError(f'invalid {name}')
    margin = NATIVE_OUT_OF_ARENA_MARGIN
    if not (-margin <= x <= NATIVE_ARENA_WIDTH + margin and -margin <= y <= NATIVE_ARENA_HEIGHT + margin):
        raise NativePublicProjectionError('out-of-arena body')
    return clip_native_position(x, y)


def native_out_of_arena_positions(snapshot: dict) -> list[dict]:
    """Diagnostics for objects whose raw position was clipped by the projection."""
    result = []
    for obj in snapshot.get('objects', ()):
        x, y = obj.get('x'), obj.get('y')
        if type(x) is not int or type(y) is not int:
            continue
        clipped = clip_native_position(x, y)
        if clipped != (x, y):
            result.append({
                'nativeObjectId': obj.get('nativeObjectId'),
                'owner': obj.get('owner'),
                'cardId': obj.get('cardId'),
                'raw': [x, y],
                'clipped': list(clipped),
            })
    return result


@dataclass(frozen=True)
class NativePublicScope:
    """Caller-bound provenance for standard level11 base-form offline matches."""
    content_version: str
    ruleset_sha256: str
    level: int = 11
    base_forms_only: bool = True

    def validate(self, builder):
        if self.content_version != '15.535.86' or self.level != 11 or self.base_forms_only is not True:
            raise NativePublicProjectionError('unsupported native ruleset or forms')
        actual = hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest()
        if self.ruleset_sha256 != actual:
            raise NativePublicProjectionError('public ruleset digest mismatch')


@dataclass(frozen=True)
class NativeProjectileCatalog:
    names: tuple[str, ...]
    sha256: str

    @classmethod
    def from_csv(cls, path, *, expected_sha256: str):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha256:
            raise NativePublicProjectionError('projectile catalog digest mismatch')
        rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        if len(rows) < 3 or rows[0][0] != 'Name' or rows[1][0].lower() != 'string':
            raise NativePublicProjectionError('invalid projectile catalog')
        names = tuple(row[0] for row in rows[2:] if row and row[0])
        if len(set(names)) != len(names):
            raise NativePublicProjectionError('duplicate projectile catalog identity')
        return cls(names, digest)

    def name(self, identity):
        index = integer(identity, 'projectile data ID') - 10000000
        if not 0 <= index < len(self.names):
            raise NativePublicProjectionError('projectile data ID outside catalog')
        return self.names[index]


def public_reference_builder(loader, catalog, *, card_semantics_version=4, public_contract_version=3):
    """Use the declared public roster, never either player's hidden deck.

    Version 4 serializes own-card level missingness; it does not establish a
    native HUD level reader. The legacy v3 builder remains the default.
    """
    if public_contract_version not in (3, 4):
        raise ValueError("public reference builder supports contract v3 or v4")
    base = StructuredObservationBuilder(card_loader=loader, card_vocab=PUBLIC_REFERENCE_CARDS)
    tokens = ['<pad>', '<unknown>', *sorted(set(base.token_names[2:]) | set(catalog.names))]
    return StructuredObservationBuilder(
        card_loader=loader,
        card_vocab=PUBLIC_REFERENCE_CARDS,
        token_names=tokens,
        canonical_lane_globals=True,
        public_entity_levels=True,
        public_hand_levels=public_contract_version >= 4,
        card_semantics_version=card_semantics_version,
    )


def join_rich_snapshot(snapshot, rich):
    if rich is None:
        return {}
    if rich.get('ok') is not True or rich.get('schema') != 'native-rich-telemetry.v3' or rich.get('truncated') is not False:
        raise NativePublicProjectionError('invalid rich snapshot')
    for key in ('tick', 'generation', 'stateEpoch', 'count', 'returned'):
        if snapshot.get(key) != rich.get(key):
            raise NativePublicProjectionError('rich snapshot epoch or coverage mismatch')
    objects = rich.get('objects')
    if not isinstance(objects, list) or len(objects) != snapshot['count']:
        raise NativePublicProjectionError('incomplete rich snapshot')
    by_id = {obj.get('nativeObjectId'): obj for obj in objects}
    if len(by_id) != len(objects):
        raise NativePublicProjectionError('duplicate rich object')
    for obj in snapshot['objects']:
        counterpart = by_id.get(obj['nativeObjectId'])
        if counterpart is None or any(counterpart.get(k) != obj.get(k) for k in ('owner', 'cardId', 'x', 'y', 'hp', 'maxHp')):
            raise NativePublicProjectionError('rich and ordinary objects disagree')
    return by_id


@dataclass(frozen=True)
class NativePublicLevelEvidence:
    """Frame-local level readings from public labels, never inferred from HP.

    Native IDs bind reviewed labels to source bodies; they never reach actor
    tensors. The evidence digest belongs in the surrounding capture manifest.
    """
    tick: int
    generation: int
    state_epoch: int
    source_sha256: str
    levels: dict[int, int]
    confidence: dict[int, float]

    def validate(self, snapshot):
        for value in (self.tick, self.generation, self.state_epoch):
            integer(value, 'level evidence frame')
        if (self.tick, self.generation, self.state_epoch) != (snapshot['tick'], snapshot['generation'], snapshot['stateEpoch']):
            raise NativePublicProjectionError('public level evidence belongs to another frame')
        if not isinstance(self.source_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', self.source_sha256):
            raise NativePublicProjectionError('public level evidence lacks source digest')
        if self.levels.keys() != self.confidence.keys():
            raise NativePublicProjectionError('public level readings lack confidence')
        for identity, level in self.levels.items():
            integer(identity, 'level body ID')
            if type(level) is not int or not 1 <= level <= 127:
                raise NativePublicProjectionError('invalid public level reading')
            confidence = self.confidence[identity]
            if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 < confidence <= 1:
                raise NativePublicProjectionError('invalid public level confidence')
        bodies = {o['nativeObjectId'] for o in snapshot['objects'] if o.get('hp') is not None}
        if not self.levels.keys() <= bodies:
            raise NativePublicProjectionError('public level reading does not identify a body')


class NativePublicObservationAdapter:
    def __init__(self, builder: StructuredObservationBuilder, scope: NativePublicScope, *, card_names: tuple[str, ...], projectile_catalog: NativeProjectileCatalog | None = None):
        scope.validate(builder)
        if not builder.canonical_perspective or not builder.canonical_lane_globals:
            raise NativePublicProjectionError('native projection requires canonical positions and lane globals')
        self.projectile_catalog = projectile_catalog
        self.builder = builder
        self.scope = scope
        self.supported_body_ids = {builder.loader.get_card(name)._raw_entry["id"] for name in SUPPORTED_BODY_CARDS}
        self.cards = {}
        for name in card_names:
            card = builder.loader.get_card(name)
            if card is None or builder.token_id(name, namespace='card_action') <= 1:
                raise NativePublicProjectionError(f'undeclared card {name}')
            identity = card._raw_entry['id']
            if identity in self.cards:
                raise NativePublicProjectionError('duplicate card identity')
            self.cards[identity] = (name, card)

    def project(self, snapshot: dict, perspective: int, *, own_last_play: AcceptedOwnPlay | None = None, rich_snapshot: dict | None = None, level_evidence: NativePublicLevelEvidence | None = None) -> ConfidenceAwareActorObservation:
        if type(perspective) is not int or perspective not in (0, 1):
            raise NativePublicProjectionError('invalid perspective')
        if snapshot.get('ok') is not True or snapshot.get('truncated') is not False:
            raise NativePublicProjectionError('failed or truncated snapshot')
        objects = snapshot.get('objects')
        if not isinstance(objects, list) or snapshot.get('returned') != len(objects) or snapshot.get('count') != len(objects):
            raise NativePublicProjectionError('incomplete object coverage')
        if level_evidence is not None:
            if not self.builder.public_entity_levels:
                raise NativePublicProjectionError('public level evidence requires a level-aware builder')
            level_evidence.validate(snapshot)
        rich_objects = join_rich_snapshot(snapshot, rich_snapshot)
        tick = integer(snapshot.get('tick'), 'tick')
        if type(snapshot.get('ended')) is not bool:
            raise NativePublicProjectionError('unknown native lifecycle')
        # After native gameplay stops, presentation can drain tower HP. A result
        # screen needs its own adapter and must not masquerade as a battle frame.
        if tick > 6001 or snapshot.get('finalized') is not False:
            raise NativePublicProjectionError('result presentation is outside battle-frame scope')
        players = [p for p in snapshot.get('players', []) if p.get('owner') == perspective]
        if len(players) != 1:
            raise NativePublicProjectionError('missing or duplicate own HUD')
        own = players[0]
        elixir = integer(own.get('elixirRaw'), 'own elixir')
        if elixir > 100000:
            raise NativePublicProjectionError('own elixir exceeds capacity')
        hand = own.get('hand')
        if not isinstance(hand, list) or len(hand) > 4 or any(not isinstance(card, dict) for card in hand):
            raise NativePublicProjectionError('malformed own hand')
        slots = [card.get('handIndex') for card in hand]
        if any(type(slot) is not int or not 0 <= slot < 4 for slot in slots) or len(set(slots)) != len(slots):
            raise NativePublicProjectionError('invalid or duplicate own hand slot')
        # Native HUD snapshots omit a slot while its next card refills. Its
        # absence is not a shorter hand whose remaining cards shift left.
        hand = sorted(hand, key=lambda c: c['handIndex'])
        next_card = own.get('nextCard')
        if not isinstance(next_card, dict):
            raise NativePublicProjectionError('missing visible next card')
        hand_ids = np.zeros(VISIBLE_CARD_SLOTS, dtype=np.int64)
        visible_cards = [(card['handIndex'], card) for card in hand] + [(4, next_card)]
        for index, card in visible_cards:
            identity = card.get('cardId')
            if type(identity) is not int or identity not in self.cards:
                raise NativePublicProjectionError(f'unsupported visible card {identity}')
            name, _ = self.cards[identity]
            command_identity = card.get('commandCardId', identity)
            # Mirror keeps its own hand identity while native dispatch names
            # the copied card. Do not infer accepted-play history from this.
            if type(command_identity) is not int or (command_identity != identity and (identity != 28000006 or command_identity not in self.cards)):
                raise NativePublicProjectionError('alternate card form is unsupported')
            hand_ids[index] = self.builder.token_id(name, namespace='card_action')
        rows, tower_hp, seen_ids = [], {}, set()
        level_rows = []
        for obj in objects:
            identity = integer(obj.get('nativeObjectId'), 'object ID')
            if identity in seen_ids:
                raise NativePublicProjectionError('duplicate object')
            seen_ids.add(identity)
            owner = integer(obj.get('owner'), 'body owner')
            if owner not in (0, 1):
                raise NativePublicProjectionError('unsupported neutral object')
            # Bounded out-of-arena positions (thrown Log) are clipped; crown
            # anchors below are inside the arena, so clipping cannot alias them.
            x, y = native_public_position(obj.get('x'), obj.get('y'))
            observed_level = 0 if level_evidence is None else level_evidence.levels.get(identity, 0)
            observed_confidence = 0.0 if level_evidence is None else level_evidence.confidence.get(identity, 0.0)
            if obj.get('hp') is None:
                rich_obj = rich_objects.get(identity, {})
                projectile = rich_obj.get('projectile')
                if rich_obj.get('dataGlobalId') == 22000007 and obj.get('cardId') == 26000038 and projectile is None:
                    # Pinned rendered Ice Golem death controls establish this
                    # association. Area IDs cannot be inferred from CSV order.
                    name, kind, namespace = 'FreezeIceGolemite', 3, 'area_effect'
                else:
                    if self.projectile_catalog is None or not isinstance(projectile, dict):
                        raise NativePublicProjectionError('effect requires verified projectile identity')
                    data_id = rich_obj.get('dataGlobalId')
                    if projectile.get('projectileDataGlobalId') != data_id:
                        raise NativePublicProjectionError('projectile catalog identity disagrees')
                    name = self.projectile_catalog.name(data_id)
                    # Other projectile visibility/launch phases still need controls.
                    if name not in {'FireballSpell', 'ArcherArrow', 'TowerPrincessProjectile', 'KingProjectile', 'TowerCannonball', 'LogProjectile', 'LogProjectileRolling', 'MusketeerProjectile', 'IceSpiritsProjectile'} or projectile.get('nativePhase') != 'in_flight' or projectile.get('terminal') is not False:
                        raise NativePublicProjectionError(f'projectile visibility unsupported: {name}')
                    kind, namespace = 2, 'projectile'
                hp, maximum = 1, 1
            else:
                hp = integer(obj.get('hp'), 'body HP')
                maximum = integer(obj.get('maxHp'), 'body maximum HP', 1)
                if hp > maximum:
                    raise NativePublicProjectionError('body HP exceeds maximum')
                card_id = obj.get('cardId')
                if card_id == -1:
                    anchor = (owner, x, y)
                    if anchor not in TOWER_ANCHORS or anchor in tower_hp:
                        raise NativePublicProjectionError('unknown or duplicate crown tower')
                    name, expected_max = TOWER_ANCHORS[anchor]
                    if observed_level not in (0, self.scope.level):
                        raise NativePublicProjectionError('unsupported observed crown level')
                    tower_hp[anchor] = hp / maximum
                    kind, namespace = 1, 'tower'
                else:
                    if card_id not in self.cards:
                        raise NativePublicProjectionError(f'undeclared body {card_id}')
                    action_name, card = self.cards[card_id]
                    if card_id not in self.supported_body_ids:
                        raise NativePublicProjectionError(f'body visibility or identity unsupported: {action_name}')
                    name, expected_max = card.name, card.scaled_hitpoints
                    if observed_level not in (0, self.scope.level):
                        if observed_level != self.scope.level + 1 or 28000006 not in self.cards:
                            raise NativePublicProjectionError('observed level outside declared Mirror scope')
                        expected_max = card.get_scaled_stat(card.hitpoints, observed_level)
                    kind = int(card.card_type.lower() == 'building')
                    namespace = 'building_body' if kind else 'troop_body'
                if maximum != expected_max:
                    raise NativePublicProjectionError(f'level/form/HP mismatch: {name}')
            token = self.builder.token_id(name, namespace=namespace)
            if token <= 1:
                raise NativePublicProjectionError(f'undeclared body token {name}')
            if hp == 0:
                continue
            if perspective == 1:
                x, y = 18000 - x, 32000 - y
            row = np.zeros(ENTITY_FEATURE_SIZE, dtype=np.float32)
            row[:4] = [x / 18000, y / 32000, owner == perspective, owner != perspective]
            row[4 + kind] = 1
            row[9] = hp / maximum if kind < 2 else 0
            key = (kind, int(owner != perspective), token, y, x)
            rows.append((key, token, row))
            level_rows.append((key, observed_level, observed_confidence))
        # Missing towers mean destruction only because coverage was complete and
        # this scope fixes the six initial crown anchors.
        crowns = [sum(tower_hp.get(key, 0) == 0 for key in TOWER_ANCHORS if key[0] == 1 - owner) for owner in (0, 1)]
        kings_dead = any(tower_hp.get(key, 0) == 0 for key, (name, _) in TOWER_ANCHORS.items() if name == 'KingTower')
        terminal = snapshot['ended'] or tick > 6000 or kings_dead or (tick > 3600 and crowns[0] != crowns[1])
        ids, features, mask = self.builder._pack_entity_rows(rows)
        feature_confidence = np.zeros_like(features)
        feature_confidence[mask, :9] = 1
        feature_confidence[mask & ((features[:, 4] + features[:, 5]) > 0), 9] = 1
        globals_ = np.zeros(ACTOR_GLOBAL_SIZE, dtype=np.float32)
        global_confidence = np.zeros_like(globals_)
        globals_[5] = elixir / 100000
        global_confidence[5] = 1
        for owner in (perspective, 1 - perspective):
            offset = 8 if owner == perspective else 11
            keys = [k for k in TOWER_ANCHORS if k[0] == owner]
            for key in keys:
                name, _ = TOWER_ANCHORS[key]
                column = 2 if name == 'KingTower' else int((18000-key[1] if perspective else key[1]) > 9000)
                globals_[offset + column] = tower_hp.get(key, 0)
                global_confidence[offset + column] = 1
        level_fields = {}
        if self.builder.public_entity_levels:
            levels = np.zeros(self.builder.max_entities, dtype=np.int64)
            confidence = np.zeros(self.builder.max_entities, dtype=np.float32)
            for index, (_, level, certainty) in enumerate(sorted(level_rows, key=lambda r: r[0])):
                levels[index], confidence[index] = level, certainty
            level_fields = {'entity_levels': levels, 'entity_level_confidence': confidence}
        if self.builder.public_hand_levels:
            # The pinned reader supplies body-label levels only. Neither the
            # nominal scope, scaled HP nor undeclared raw HUD keys establish an
            # owned-card reading. Preserve five explicit unknown slots until a
            # separately bound own-HUD/next-card source has been calibrated.
            level_fields.update(
                hand_levels=np.zeros(VISIBLE_CARD_SLOTS, dtype=np.int64),
                hand_level_confidence=np.zeros(VISIBLE_CARD_SLOTS, dtype=np.float32),
            )
        actor = ActorObservation(
            **level_fields,
            entity_ids=ids, entity_features=features, entity_mask=mask,
            hand_ids=hand_ids, global_features=globals_,
            opponent_history_ids=np.zeros(self.builder.public_history_slots, dtype=np.int64),
            opponent_history_ages=np.zeros(self.builder.public_history_slots, dtype=np.float32),
            opponent_seen_card_ids=np.zeros(self.builder.public_seen_card_slots, dtype=np.int64),
            own_last_play=own_last_play, terminal=terminal,
            board_rotated=bool(perspective == 1),
        )
        result = ConfidenceAwareActorObservation(
            observation=actor, entity_id_confidence=mask.astype(np.float32),
            entity_feature_confidence=feature_confidence,
            hand_id_confidence=(hand_ids > 0).astype(np.float32),
            global_feature_confidence=global_confidence,
            opponent_history_confidence=np.zeros_like(actor.opponent_history_ages),
            opponent_seen_card_confidence=np.zeros_like(actor.opponent_seen_card_ids, dtype=np.float32),
        )
        validate_real_play_feature_contract(result)
        return result


def native_public_level_coverage(
    builder: StructuredObservationBuilder, public: ConfidenceAwareActorObservation,
) -> dict[str, dict[str, int]]:
    """Report measured channel coverage separately from structural validity.

    A valid v4 packet may have no measured own-card levels. These counts make
    that limitation explicit; they do not certify source calibration or infer
    level values from the nominal ruleset or unit health.
    """
    public.validate()
    actor = public.observation
    body = actor.entity_mask & ((actor.entity_features[:, 4] + actor.entity_features[:, 5]) > 0)
    towers = body & np.isin(actor.entity_ids, [
        builder.token_id("Tower", namespace="tower"),
        builder.token_id("KingTower", namespace="tower"),
    ])
    entity_known = (np.zeros_like(actor.entity_mask) if actor.entity_level_confidence is None
                    else actor.entity_level_confidence > 0)
    hand_visible = actor.hand_ids > 1
    hand_known = (np.zeros_like(hand_visible) if actor.hand_level_confidence is None
                  else actor.hand_level_confidence > 0)
    def counts(visible, known):
        return {"observed": int(np.count_nonzero(visible & known)), "visible": int(np.count_nonzero(visible))}
    return {
        "body_levels": counts(body & ~towers, entity_known),
        "tower_levels": counts(towers, entity_known),
        "own_hand_levels": counts(hand_visible[:4], hand_known[:4]),
        "own_next_card_level": counts(hand_visible[4:], hand_known[4:]),
    }
