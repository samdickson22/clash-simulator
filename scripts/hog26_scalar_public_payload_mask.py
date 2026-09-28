"""Proposed scalar-reference public mask refinement for visible timed bodies.

Only public actor tensors and frozen serialized setup tables enter build().
Timed bodies remain noncombat effects; their timers and future payloads are
neither inputs nor outputs. This proposal does not replace global mask-v2.
"""

import hashlib
import json
from dataclasses import dataclass, fields, replace

import numpy as np
import torch

from clasher.arena import Position
from clasher.placement import building_anchor
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Result
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ScalarPublicPayloadMaskRules:
    policy_token_names: tuple[str, ...]
    outcome_token_names: tuple[str, ...]
    radius_logic_units: tuple[int, ...]
    payload_sha256: tuple[tuple[str, str], ...]
    digest: str

    @classmethod
    def compile(cls, loader, *, policy_token_names, outcome_token_names):
        policy = tuple(policy_token_names)
        outcome = tuple(outcome_token_names)
        if (not policy or outcome[:len(policy)] != policy
                or len(set(outcome)) != len(outcome)):
            raise ValueError("outcome vocabulary must uniquely extend the frozen policy prefix")
        radii = [0] * len(outcome)
        authorities = []
        for card, body_name in (("Balloon", "BalloonBomb"), ("BombTower", "BombTowerBomb"),
                                ("SkeletonBarrel", "SkeletonContainerNew")):
            body = loader.get_card(card)._raw_entry.get("summonCharacterData") or {}
            payload = body.get("deathSpawnCharacterData") or {}
            token_name = "building_body:" + body_name
            if (payload.get("name") != body_name or payload.get("deathDamage") is None
                    or payload.get("hitpoints") or body.get("deathSpawnCount", 1) != 1
                    or token_name not in outcome):
                raise ValueError("serialized timed-body route or public appearance changed")
            radius = payload.get("collisionRadius", 500) or 500
            if type(radius) is not int or not 0 < radius <= 3000:
                raise ValueError("timed-body collision radius is outside audited logic geometry")
            radii[outcome.index(token_name)] = radius
            authorities.append((card + "/summonCharacterData/deathSpawnCharacterData", _digest(payload)))
        values = {"policy_token_names": policy, "outcome_token_names": outcome,
                  "radius_logic_units": radii, "payload_sha256": authorities,
                  "positions": "current public effect centers decoded to 1000 logic units per tile",
                  "geometry": "inclusive circle-circle / circle-placement-square; non-spells only"}
        return cls(policy, outcome, tuple(radii), tuple(authorities), _digest(values))


def policy_public_view(actor, rules):
    """Map outcome-only identities to unknown without changing visible rows."""
    ids = actor.entity_ids
    if bool(((ids < 0) | (ids >= len(rules.outcome_token_names))).any()):
        raise ValueError("public identity outside declared outcome vocabulary")
    extended = ids >= len(rules.policy_token_names)
    effects = ((actor.entity_features[..., 6] == 1) | (actor.entity_features[..., 7] == 1))
    combat = ((actor.entity_features[..., 4] == 1) | (actor.entity_features[..., 5] == 1))
    if bool((extended & (~effects | combat)).any()):
        raise ValueError("outcome-only identity must remain a noncombat public effect")
    values = {field.name: getattr(actor, field.name) for field in fields(actor)}
    values["entity_ids"] = torch.where(extended, 1, ids)
    return TensorPublicStructuredObservation(**values)


class ScalarPublicPayloadMaskProvider:
    """Refine base legality from full public appearances before policy ID mapping.

    Integration: scalar_policy_inputs must call build(unmapped_public_actor)
    before mapping outcome-only IDs to unknown. Its existing ID-confidence rule
    remains valid. tables deliberately remains the frozen POLICY table so hand
    decoding and model vocabulary validation retain their current contract.
    """

    def __init__(self, base_provider, rules):
        if tuple(base_provider.tables.token_keys) != rules.policy_token_names:
            raise ValueError("base mask and payload rules use different policy vocabularies")
        self.base_provider = base_provider
        self.tables = base_provider.tables
        self.rules = rules
        if self.tables.device.type != "cpu":
            raise ValueError("scalar timed-body mask proposal requires CPU public tables")
        radius = torch.round(self.tables.deploy_radius_tiles * 1000).long()
        footprint = ((2 * radius + 999) // 1000 + 1).clamp_min(1)
        sizes = sorted(set(footprint[self.tables.is_building].tolist()) | {1})
        size_index = {size: index for index, size in enumerate(sizes)}
        self.building_size_indices = torch.tensor(
            [size_index.get(size, size_index[1]) for size in footprint.tolist()],
            dtype=torch.int64,
        )
        anchors = []
        for size in sizes:
            seats = []
            for seat in (0, 1):
                positions = []
                for tile in range(576):
                    x, y = tile % 18 + 0.5, tile // 18 + 0.5
                    world = Position(x, y) if seat == 0 else Position(18 - x, 32 - y)
                    resolved = building_anchor(world, size)
                    ax, ay = (resolved.x, resolved.y) if seat == 0 else (18 - resolved.x, 32 - resolved.y)
                    positions.append([round(ax * 1000), round(ay * 1000)])
                seats.append(positions)
            anchors.append(seats)
        self.building_anchor_units = torch.tensor(anchors, dtype=torch.int64)
        anchor_digest = hashlib.sha256(
            self.building_anchor_units.numpy().tobytes()
            + self.building_size_indices.numpy().tobytes()
        ).hexdigest()
        semantics = dict(self.tables.semantics)
        semantics.update(
            semantics_id="public-action-mask-v2/scalar-public-timed-bodies-v2",
            base_semantics_digest=self.tables.semantics_digest,
            scalar_public_payload_digest=rules.digest,
            scalar_public_payload_geometry="inclusive logic-grid circle/circle and circle/resolved-building-square",
            scalar_public_building_anchor_sha256=anchor_digest,
            scalar_public_payload_inputs="unmapped public token, current center, seat-visible mask; no owner restriction",
        )
        self.semantics = semantics
        self.semantics_digest = _digest(semantics)

    def build(self, outcome_actor):
        # The scalar reference is CPU. Do not add a silent device fallback or
        # weaken the global mask provider's float64-authoritative contract.
        if outcome_actor.entity_ids.device.type != "cpu" or self.tables.device.type != "cpu":
            raise ValueError("scalar timed-body mask proposal requires CPU public tensors")
        mapped = policy_public_view(outcome_actor, self.rules)
        base = self.base_provider.build(mapped)
        return self.refine(outcome_actor, base)

    def refine(self, outcome_actor, base):
        """Refine an already-built base result using ORIGINAL outcome IDs."""
        if outcome_actor.entity_ids.device.type != "cpu" or base.masks.device.type != "cpu":
            raise ValueError("scalar timed-body mask proposal requires CPU public tensors")
        if base.semantics_digest != self.tables.semantics_digest:
            raise ValueError("base mask has a different semantics authority")
        policy_public_view(outcome_actor, self.rules)  # Validate full public identity contract.
        actor = outcome_actor
        radii = torch.tensor(self.rules.radius_logic_units, dtype=torch.int64)[actor.entity_ids]
        effect_body = ((actor.entity_features[..., 7] == 1)
                       & (actor.entity_features[..., 4] == 0)
                       & (actor.entity_features[..., 5] == 0))
        blockers = actor.entity_mask & effect_body & (radii > 0)
        if not bool(blockers.any()):
            return replace(base, semantics_id=self.semantics["semantics_id"],
                           semantics=self.semantics, semantics_digest=self.semantics_digest)
        # Effect projection emits logic-unit centers as normalized float32.
        # Inverting that representation by nearest-unit rounding removes its
        # sub-unit float32 error without consulting underlying simulator state.
        x = torch.round(actor.entity_features[..., 0].double() * 18000).to(torch.int64)
        y = torch.round(actor.entity_features[..., 1].double() * 32000).to(torch.int64)
        tile = torch.arange(576, dtype=torch.int64)
        tile_x, tile_y = (tile % 18) * 1000 + 500, (tile // 18) * 1000 + 500
        dx = (tile_x[None, None, None, :, None] - x[:, :, None, None, :]).abs()
        dy = (tile_y[None, None, None, :, None] - y[:, :, None, None, :]).abs()
        hand = actor.hand_ids[..., :4].clamp(0, len(self.rules.policy_token_names) - 1)
        troop_radius = torch.round(self.tables.deploy_radius_tiles[hand] * 1000).long()
        payload_radius = radii[:, :, None, None, :]
        circle = dx.square() + dy.square() <= (
            troop_radius[..., None, None] + payload_radius).square()
        # Scalar building placement uses ceil(2*collision_radius)+1 tile square.
        footprint_tiles = ((2 * troop_radius + 999) // 1000 + 1).clamp_min(1)
        half = footprint_tiles * 500
        seat = torch.arange(2, dtype=torch.int64)[None, :, None]
        anchors = self.building_anchor_units[self.building_size_indices[hand], seat]
        building_dx = (anchors[..., 0, None] - x[:, :, None, None, :]).abs()
        building_dy = (anchors[..., 1, None] - y[:, :, None, None, :]).abs()
        square_dx = (building_dx - half[..., None, None]).clamp_min(0)
        square_dy = (building_dy - half[..., None, None]).clamp_min(0)
        square = square_dx.square() + square_dy.square() <= payload_radius.square()
        overlap = torch.where(self.tables.is_building[hand][..., None, None], square, circle)
        blocked = (overlap & blockers[:, :, None, None, :]).any(dim=-1)
        blocked &= ~self.tables.is_spell[hand][..., None]
        masks = base.masks.clone()
        masks[..., :2304] &= ~blocked.flatten(-2)
        return SimplePublicMaskV2Result(
            masks=masks, semantics_id=self.semantics["semantics_id"],
            semantics=self.semantics, semantics_digest=self.semantics_digest,
            contract_version=base.contract_version,
        )


def scalar_policy_inputs_with_payload_mask(actors, mask_provider, *, previous_actions, episode_starts):
    """Narrow integration seam; original actor arrays survive policy mapping.

    Reuses the frozen policy input/confidence builder and its base mask once,
    then refines that mask using the separate, original outcome-public view.
    """
    inputs, base = scalar_policy_inputs(
        actors, mask_provider.base_provider, previous_actions=previous_actions,
        episode_starts=episode_starts,
        extra_public_effect_tokens=mask_provider.rules.outcome_token_names[
            len(mask_provider.rules.policy_token_names):],
    )
    outcome = TensorPublicStructuredObservation(**{
        field.name: torch.from_numpy(np.stack([getattr(actor, field.name) for actor in actors]))[None]
        for field in fields(TensorPublicStructuredObservation)
    })
    result = mask_provider.refine(outcome, base)
    return replace(inputs, action_mask=result.masks.reshape(2, 1, -1)), result
