"""Fixed development opponents with a public-observation-only decision interface.

These heuristics are diagnostic response models, not trained or expert policies.
Own cards and Crown towers use the declared level-11 base-form ruleset. Visible
body levels are required; no opponent hand, elixir, target, or clock is accepted.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import numpy as np

from clasher.balance import tournament_tower_stat
from clasher.card_aliases import resolve_card_name
from clasher.dynamic_spells import create_spell_from_json

from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import ConfidenceAwareActorObservation
from .structured_obs import StructuredObservationBuilder

SUPPORTED_CARDS = frozenset(
    {
        "Archers",
        "Cannon",
        "DarkPrince",
        "Fireball",
        "Giant",
        "Goblins",
        "HogRider",
        "IceGolem",
        "IceSpirit",
        "Knight",
        "Log",
        "Musketeer",
        "Prince",
        "Skeletons",
        "Tesla",
        "Zap",
    }
)


@dataclass(frozen=True)
class PublicScriptedDecision:
    action_id: int
    reason: str
    score: float


@dataclass(frozen=True)
class _Body:
    x: float
    y: float
    enemy: bool
    hp: float
    max_hp: float
    radius: float
    cost: float
    targets_buildings: bool
    crown: bool
    spell_credit: bool


class PublicScriptedOpponent:
    """Deterministic scoring over legal actions; no simulation or rollout search."""

    def __init__(
        self, builder: StructuredObservationBuilder, *, style: str = "balanced"
    ):
        if style not in {"balanced", "pressure", "defense"}:
            raise ValueError("unsupported public opponent style")
        if not builder.canonical_perspective or not builder.canonical_lane_globals:
            raise ValueError("public opponent requires canonical coordinates and lanes")
        if not builder.public_entity_levels or builder.card_semantics_version != 4:
            raise ValueError(
                "public opponent requires visible levels and metadata version4"
            )
        canonical_actions = {resolve_card_name(n): n for n in SUPPORTED_CARDS}
        if (
            not {resolve_card_name(n) for n in builder.card_vocab}
            <= canonical_actions.keys()
        ):
            raise ValueError(
                "public opponent supports only the declared base-card roster"
            )
        self.builder = builder
        self.style = style
        self.mask_builder = PublicActionMaskBuilder(builder)
        self.cards = {}
        self.bodies = {}
        self.spells = {}
        for declared_name in builder.card_vocab:
            name = canonical_actions[resolve_card_name(declared_name)]
            stats = copy.copy(builder.loader.get_card(name))
            if stats is None or stats.level != 11:
                raise ValueError("own card metadata must declare level11")
            for alias in {declared_name, name}:
                self.cards[builder.token_id(alias, namespace="card_action")] = (
                    name,
                    stats,
                )
            if str(stats.card_type).lower() == "spell":
                self.spells[name] = create_spell_from_json(stats._raw_entry, level=11)
            else:
                namespace = (
                    "building_body"
                    if str(stats.card_type).lower() == "building"
                    else "troop_body"
                )
                character = stats._raw_entry.get("summonCharacterData", {})
                for alias in {
                    declared_name,
                    name,
                    stats.name,
                    character.get("name", name),
                }:
                    token = builder.token_id(alias, namespace=namespace)
                    if token > 1:
                        self.bodies[token] = stats
        self.crowns = {
            builder.token_id(name, namespace="tower"): name
            for name in ("Tower", "KingTower")
        }
        tiles = np.arange(576)
        self.x = tiles % 18 + 0.5
        self.y = tiles // 18 + 0.5

    def _bodies(self, packet):
        obs = packet.observation
        result = []
        for i in np.flatnonzero(obs.entity_mask):
            row = obs.entity_features[i]
            confidence = packet.entity_feature_confidence[i]
            if np.any(confidence[:9] < 1):
                raise ValueError("uncertain public body geometry or kind")
            if row[4] + row[5] < 0.5:
                continue
            if packet.entity_id_confidence[i] < 1 or confidence[9] < 1:
                raise ValueError("uncertain public body identity or health")
            token = int(obs.entity_ids[i])
            crown = token in self.crowns
            if crown:
                maximum = float(
                    tournament_tower_stat(
                        "PrincessTower"
                        if self.crowns[token] == "Tower"
                        else "KingTower",
                        "hitpoints",
                    )
                )
                radius, cost, buildings, spell_credit = 1.0, 0.0, False, True
            else:
                stats = self.bodies.get(token)
                if stats is None:
                    raise ValueError("unsupported visible body identity")
                if obs.entity_levels is None or obs.entity_level_confidence[i] < 1:
                    raise ValueError("unknown visible body level")
                level = int(obs.entity_levels[i])
                if level <= 0:
                    raise ValueError("unknown visible body level")
                maximum = float(
                    stats.scaled_hitpoints
                    if level == 11
                    else stats.get_scaled_stat(stats.hitpoints, level)
                )
                radius = float(stats.collision_radius or 0)
                cost = float(stats.mana_cost) / max(1, int(stats.summon_count or 1))
                buildings = bool(stats.targets_only_buildings)
                # Unknown shield state is not assumed to be depleted.
                shield = float(
                    stats._raw_entry.get("summonCharacterData", {}).get(
                        "shieldHitpoints", 0
                    )
                    or 0
                )
                spell_credit = shield == 0 or (confidence[10] == 1 and row[10] == 0)
            result.append(
                _Body(
                    float(row[0]) * 18,
                    float(row[1]) * 32,
                    bool(row[3] > 0.5),
                    float(row[9]) * maximum,
                    maximum,
                    radius,
                    cost,
                    buildings,
                    crown,
                    spell_credit,
                )
            )
        return result

    def decide(self, packet: ConfidenceAwareActorObservation) -> PublicScriptedDecision:
        if not isinstance(packet, ConfidenceAwareActorObservation):
            raise TypeError("public confidence-aware observation required")
        packet.validate()
        obs = packet.observation
        if obs.terminal is True:
            return PublicScriptedDecision(2304, "terminal", 0.0)
        if obs.terminal is None or obs.board_rotated is None:
            raise ValueError("unknown public lifecycle or board orientation")
        if (
            np.any(packet.hand_id_confidence[:4] < 1)
            or packet.global_feature_confidence[5] < 1
        ):
            raise ValueError("uncertain own hand or elixir")
        if np.any(packet.global_feature_confidence[8:14] < 1):
            raise ValueError("uncertain public Crown health")
        bodies = self._bodies(packet)
        mask = self.mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(packet)
        )
        if mask[self.mask_builder.ability_action]:
            raise ValueError("champion abilities outside declared scope")
        enemies = [b for b in bodies if b.enemy and not b.crown]
        incoming = [b for b in enemies if b.y < 17.0]
        threat = min(incoming, key=lambda b: b.y, default=None)
        elixir = float(obs.global_features[5]) * 10
        reserve = (
            4 if self.style == "pressure" else 7 if self.style == "balanced" else 9
        )
        best = PublicScriptedDecision(
            2304, "reserve elixir", 2.8 if threat is None and elixir < reserve else -0.5
        )
        for slot in range(4):
            token = int(obs.hand_ids[slot])
            if token == 0:
                continue
            if token not in self.cards:
                raise ValueError("unsupported own hand identity")
            name, stats = self.cards[token]
            legal = np.flatnonzero(mask[slot * 576 : (slot + 1) * 576])
            if not len(legal):
                continue
            x, y = self.x[legal], self.y[legal]
            cost = float(stats.mana_cost)
            if name in self.spells:
                spell = self.spells[name]
                value = np.zeros(len(legal))
                lethal = np.zeros(len(legal), dtype=bool)
                for body in bodies:
                    if not body.enemy:
                        continue
                    if name == "Log":
                        # Public fixed corridor approximation, not predicted future contact.
                        overlap = (
                            (abs(x - body.x) < spell.radius + body.radius)
                            & (body.y >= y - 3)
                            & (body.y < y - 3 + spell.projectile_range)
                        )
                    else:
                        overlap = (x - body.x) ** 2 + (y - body.y) ** 2 < (
                            spell.radius + body.radius
                        ) ** 2
                    if body.crown:
                        lethal |= (
                            overlap
                            & (body.hp > 0)
                            & (body.hp <= spell.crown_tower_damage + 1e-3)
                        )
                    elif body.spell_credit:
                        value += (
                            overlap
                            * body.cost
                            * min(float(spell.damage), body.hp)
                            / max(1.0, body.max_hp)
                        )
                scores = np.where(value >= 0.8 * cost, 4.0 + value - cost, -1e6)
                scores = np.where(lethal, 100.0 + value, scores)
                reason = "spell value or Crown finish"
            else:
                building = str(stats.card_type).lower() == "building"
                if threat is not None:
                    tx = (7.5 if threat.x < 9 else 10.5) if building else threat.x
                    ty = (
                        10.5
                        if building
                        else max(
                            3.5, min(13.5, threat.y - max(1.0, float(stats.range or 0)))
                        )
                    )
                    fit = np.exp(-((x - tx) ** 2 + (y - ty) ** 2) / 8.0)
                    efficiency = (
                        math.sqrt(float(stats.scaled_hitpoints or 0) / 700)
                        + float(stats.scaled_damage or 0) / 300
                    ) / max(1.0, cost)
                    scores = 6 * fit + efficiency - 0.28 * cost
                    if building and threat.targets_buildings:
                        scores += 2 * fit
                    if stats.targets_only_buildings:
                        scores -= 3
                    reason = "defend visible pressure"
                else:
                    lane_distance = np.minimum(abs(x - 3.5), abs(x - 14.5))
                    desired_y = (
                        13.5
                        if stats.targets_only_buildings or self.style == "pressure"
                        else 6.5
                    )
                    scores = (
                        4.2 * np.exp(-abs(y - desired_y) / 3.0)
                        - lane_distance
                        - 0.32 * cost
                    )
                    if stats.targets_only_buildings:
                        scores += 1.5
                    if building:
                        scores -= 3
                    reason = "lane pressure"
            at = int(np.argmax(scores))
            score = float(scores[at])
            action = slot * 576 + int(legal[at])
            if score > best.score or (score == best.score and action < best.action_id):
                best = PublicScriptedDecision(action, reason, score)
        assert mask[best.action_id], "public opponent selected an illegal action"
        return best

    def select_action(self, packet: ConfidenceAwareActorObservation) -> int:
        return self.decide(packet).action_id
