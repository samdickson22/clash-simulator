"""Public observation / model contract v5 for the C56 scope expansion.

Contract v5 keeps the v4 actor tensors (32 entity features, 18 globals, levels,
confidence, 4 history and 8 seen-card slots, the 2,306-way action space) and
changes five things, all behind explicit v5 classes so v4 stays byte-identical:

1. Vocabulary. A pinned, versioned token list built once from the 122 corpus
   cards (S122) with every serialized payload name: ``contract_v5_tokens.json``
   (360 tokens). Engine-fix payloads may be appended; the list is never
   reordered, so the observation vocabulary stays fixed while the actor scope
   grows (P16 -> C56 -> S122).
2. Card semantics v5. The 36 v4 card columns followed by ``V5_DESCRIPTOR_NAMES``
   mechanic descriptors. The model feeds them into the semantic projection
   through zero-initialized input weights (``EntityEncoder.v5_descriptor_input``).
3. Champion ability. The owner's ability button state (global 14 cooldown,
   global 15 active duration) is public only while the button is shown: the
   own Champion is on the board and has finished deploying. The ability action
   is unmasked only when the button is shown, cooldown and duration are zero
   and own elixir covers the ability cost of the visible own Champion.
4. Visible status. Enemy units whose stealth is active (Royal Ghost
   invisibility, Archer Queen cloak) or that are travelling underground
   (Miner) are removed from the enemy actor's entity table. Own units stay
   visible. Status timers (stun, slow, haste, shields, wind-ups, stealth and
   hidden-building flags) stay outside the actor contract, as in v4: the
   strategy forbids exposing hidden timers because an effect is visually
   recognizable. The engine itself treats these units as visible to both
   human players (``Entity.is_visible_to``); v5 deliberately fails closed
   until the camera stack's detection of translucent / tunnelling units is
   measured.
5. Placement mask. Crown and building footprints use a float-robust tile
   count. The v4 builder read the Princess Tower radius back from float32
   card features as 1.0000000298, which gave a 4-tile footprint and blocked a
   5x5 ring where the game blocks 3x3.

Research contract for the C56 human prior; not yet admitted (Tier A admits
contract v4 only).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from clasher.arena import Position
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import logic_time_milliseconds
from clasher.placement import building_anchor

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import (
    ENTITY_FEATURE_NAMES,
    GLOBAL_FEATURE_NAMES,
    REAL_PLAY_ENTITY_FEATURE_INDICES,
    REAL_PLAY_GLOBAL_FEATURE_INDICES,
    ConfidenceAwareActorObservation,
    exact_public_observation,
)
from .structured_obs import VISIBLE_CARD_SLOTS, ActorObservation, StructuredObservationBuilder

CONTRACT_VERSION = 5
CARD_SEMANTICS_VERSION = 5
TOKEN_FILE = Path(__file__).with_name("contract_v5_tokens.json")
TOKEN_SCHEMA = "clasher.contract-v5-tokens.v1"
PINNED_TOKEN_SHA256 = "35db1a7647c71a39b12b580cc31a39539c9ad973a8de635df0a95962b4ac8ee2"
PINNED_TOKEN_COUNT = 360

CHAMPION_COOLDOWN_GLOBAL = GLOBAL_FEATURE_NAMES.index("champion_cooldown")
CHAMPION_DURATION_GLOBAL = GLOBAL_FEATURE_NAMES.index("champion_duration")
CHAMPION_GLOBAL_INDICES = (CHAMPION_COOLDOWN_GLOBAL, CHAMPION_DURATION_GLOBAL)
V5_ENTITY_FEATURE_INDICES = frozenset(REAL_PLAY_ENTITY_FEATURE_INDICES)
V5_GLOBAL_FEATURE_INDICES = frozenset(REAL_PLAY_GLOBAL_FEATURE_INDICES) | frozenset(CHAMPION_GLOBAL_INDICES)

# Per-channel public decisions (documentation and test anchor).
VISIBLE_STATUS_DECISIONS: Mapping[str, str] = {
    "shield_fraction": "private (v4 rule; no causal shield-bar estimator yet)",
    "airborne": "private as a feature (static per card; carried by card semantics)",
    "deployment_pending": "private (deployment cue needs a causal definition; strategy)",
    "deployment_remaining_fraction": "private (hidden timer)",
    "stun_remaining": "private (hidden timer; strategy forbids timers because an effect is visible)",
    "slow_remaining": "private (hidden timer)",
    "haste_remaining": "private (hidden timer)",
    "special_move_active": "private",
    "stealth_active": "private; enemy stealthed units are removed from the enemy actor instead",
    "hidden_building": "private; a retracted enemy Tesla stays visible as its trapdoor (engine rule)",
    "forced_movement": "private",
    "attack_windup": "private",
    "charging": "private",
    "effect_progress": "private (hidden timer)",
    "tower_active": "private (v4 rule)",
    "champion_cooldown": "public while the own ability button is shown (own HUD dial)",
    "champion_duration": "public while the own ability button is shown (own HUD active state)",
    "enemy_stealth_unit": "hidden from the enemy actor (Royal Ghost invisibility, Archer Queen cloak)",
    "enemy_underground_unit": "hidden from the enemy actor while travelling underground (Miner)",
}

V5_DESCRIPTOR_NAMES = (
    "deploy_anywhere",
    "spawn_interval",
    "spawned_elixir_per_minute",
    "building_lifetime",
    "elixir_generation_per_minute",
    "is_champion",
    "ability_cost",
    "ability_cooldown",
    "invisibility",
    "underground_travel",
    "ramp_damage",
    "chain_target_count",
    "kamikaze",
    "friendly_buff",
    "pull",
    "clone",
    "mirror",
    "knockback_strength",
    "death_damage",
    "deploy_damage",
    "multi_hit_count",
)
# Engine-implemented mechanics that the compact gamedata export does not name.
# Keep this table tiny and card-specific only where the payload has no field.
_ENGINE_ONLY_MECHANICS: Mapping[str, Mapping[str, float]] = {
    # The engine's ArcherQueenCloak grants stealth; the export only names the
    # rapid-fire buff of the ability.
    "ArcherQueen": {"invisibility": 1.0},
}


# ---------------------------------------------------------------------------
# Pinned vocabulary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PinnedTokens:
    token_list_version: int
    cards: tuple[str, ...]
    tokens: tuple[str, ...]
    base_sha256: str
    appended_versions: tuple[int, ...]

    @property
    def sha256(self) -> str:
        return token_list_sha256(self.tokens)


def token_list_sha256(tokens: Sequence[str]) -> str:
    return hashlib.sha256(json.dumps(list(tokens), separators=(",", ":")).encode()).hexdigest()


def load_pinned_tokens(path: Path = TOKEN_FILE) -> PinnedTokens:
    """Load the pinned v5 vocabulary; appended payloads follow the base list."""
    payload = json.loads(Path(path).read_text())
    if payload.get("schema") != TOKEN_SCHEMA or int(payload.get("contract_version", 0)) != CONTRACT_VERSION:
        raise ValueError("not a contract-v5 token list")
    base = list(payload["tokens"])
    if token_list_sha256(base) != payload["tokens_sha256"]:
        raise ValueError("pinned token list does not match its digest")
    if payload["tokens_sha256"] != PINNED_TOKEN_SHA256 or len(base) != PINNED_TOKEN_COUNT:
        raise ValueError("pinned token list was reordered or replaced; only appends are allowed")
    tokens = list(base)
    versions = []
    for entry in payload.get("appended") or []:
        version = int(entry["token_list_version"])
        if versions and version <= versions[-1] or version <= int(payload["token_list_version"]):
            raise ValueError("appended token lists must have increasing versions")
        versions.append(version)
        tokens.extend(str(name) for name in entry["tokens"])
    if tokens[:2] != ["<pad>", "<unknown>"] or len(set(tokens)) != len(tokens):
        raise ValueError("pinned tokens must start with <pad>, <unknown> and be unique")
    return PinnedTokens(int(payload["token_list_version"]), tuple(payload["cards"]), tuple(tokens),
                        str(payload["tokens_sha256"]), tuple(versions))


def remap_token_ids(ids: np.ndarray, source_tokens: Sequence[str], target_tokens: Sequence[str]) -> np.ndarray:
    """Re-express token ids of one vocabulary in another (by token name)."""
    index = {name: position for position, name in enumerate(target_tokens)}
    missing = [name for name in source_tokens if name not in index]
    if missing:
        raise ValueError(f"target vocabulary lacks {missing[:5]}")
    table = np.asarray([index[name] for name in source_tokens], dtype=np.int64)
    return table[np.asarray(ids, dtype=np.int64)]


# ---------------------------------------------------------------------------
# Card semantics v5 descriptors
# ---------------------------------------------------------------------------

def _number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _unit(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str, Any]]:
    """Yield (parent path, key, scalar value), skipping evo/hero alternates."""
    if isinstance(value, list):
        for child in value:
            yield from _walk(child, path)
        return
    if not isinstance(value, Mapping):
        return
    for key, child in value.items():
        if key in {"evolvedSpellsData", "heroData"}:
            continue
        if isinstance(child, (Mapping, list)):
            yield from _walk(child, path + (str(key),))
        else:
            yield path, str(key), child


def _values(raw: Mapping[str, Any], *keys: str, under: str | None = None) -> list[float]:
    wanted = set(keys)
    return [abs(_number(value)) for path, key, value in _walk(raw)
            if key in wanted and (under is None or any(under in part for part in path))]


@lru_cache(maxsize=4)
def _character_elixir_table(loader_id: int) -> dict[str, float]:
    """Elixir value per unit of each summoned character name, from playable cards."""
    loader = _LOADERS[loader_id]
    table: dict[str, float] = {}
    for name in sorted(loader.load_card_definitions()):
        stats = loader.get_card(name)
        if stats is None:
            continue
        raw = getattr(stats, "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData") or {}
        summoned = character.get("name") if isinstance(character, Mapping) else None
        cost = _number(raw.get("manaCost"))
        count = max(1.0, _number(raw.get("summonNumber")))
        if summoned and cost > 0 and summoned not in table:
            table[str(summoned)] = cost / count
    return table


_LOADERS: dict[int, CardDataLoader] = {}


def v5_card_descriptors(name: str, *, loader: CardDataLoader) -> np.ndarray:
    """Return the v5 mechanic descriptor vector of a card or payload name."""
    from clasher.spells import SPELL_REGISTRY, MirrorSpell

    vector = np.zeros(len(V5_DESCRIPTOR_NAMES), dtype=np.float32)
    stats = loader.get_card(name)
    if stats is None:
        return vector
    _LOADERS.setdefault(id(loader), loader)
    raw = getattr(stats, "_raw_entry", {}) or {}
    kind = str(getattr(stats, "card_type", "") or "").lower()
    definitions = loader.load_card_definitions()
    spell = SPELL_REGISTRY.get(resolve_card_name(name, definitions))
    out = dict.fromkeys(V5_DESCRIPTOR_NAMES, 0.0)

    if spell is not None:
        out["deploy_anywhere"] = float(not bool(getattr(spell, "requires_territory", False)))
    else:
        out["deploy_anywhere"] = float(bool(getattr(stats, "can_deploy_on_enemy_side", False)))

    # Periodic spawns: serialized spawner timings, action-loop intervals or a
    # spell's spawn cadence (Graveyard).
    intervals = [value for value in _values(raw, "spawnPauseTime", "spawnInterval") if value > 1.0]
    intervals += [value for value in _values(raw, "interval", under="onStartingAction") if value > 1.0]
    if spell is not None and _number(getattr(spell, "spawn_interval", 0)) > 0:
        intervals.append(_number(getattr(spell, "spawn_interval", 0)) * 1000.0)
    if intervals:
        interval_ms = max(intervals)
        out["spawn_interval"] = _unit(interval_ms / 20000.0)
        per_wave = max([1.0] + _values(raw, "spawnNumber", "spawnCharacterCount"))
        elixir_table = _character_elixir_table(id(loader))
        spawned_names = [str(value) for path, key, value in _walk(raw)
                         if key == "name" and path and any(part.startswith(("spawnCharacter", "spawnData",
                                                                             "actionToExecute"))
                                                           for part in path[-1:])]
        unit_value = max([elixir_table.get(spawned, 0.0) for spawned in spawned_names] + [0.0])
        if unit_value <= 0.0:
            unit_value = 0.5
        out["spawned_elixir_per_minute"] = _unit(per_wave * unit_value * 60000.0 / interval_ms / 10.0)
    lifetime = max([0.0] + _values(raw, "lifeTime"))
    out["building_lifetime"] = _unit(lifetime / 100000.0)
    generate_ms = max([0.0] + _values(raw, "manaGenerateTimeMs"))
    if generate_ms > 0:
        amount = max([1.0] + _values(raw, "manaCollectAmount"))
        out["elixir_generation_per_minute"] = _unit(amount * 60000.0 / generate_ms / 10.0)

    ability = _ability_data(raw)
    out["is_champion"] = float(kind == "champion" or str(raw.get("rarity", "")).lower() == "champion")
    if isinstance(ability, Mapping):
        out["ability_cost"] = _unit(_number(ability.get("manaCost")) / 5.0)
        out["ability_cooldown"] = _unit(_number(ability.get("cooldown")) / 30000.0)
    texts = [str(value).lower() for _, _, value in _walk(raw) if isinstance(value, str)]
    out["invisibility"] = float(any("invisib" in text for text in texts))
    out["underground_travel"] = float(bool(_values(raw, "spawnPathfindSpeed"))
                                      or any("morph" in key.lower() for _, key, _ in _walk(raw))
                                      or any("Morph" in part for path, _, _ in _walk(raw) for part in path))
    base_damage = max([1.0] + _values(raw, "damage"))
    ramp = max([0.0] + _values(raw, "variableDamage3", "variableDamage2"))
    out["ramp_damage"] = _unit(ramp / base_damage / 20.0) if ramp > 0 else 0.0
    out["chain_target_count"] = _unit(max([0.0] + _values(raw, "chainedHitCount")) / 10.0)
    out["kamikaze"] = float(any(key == "kamikaze" and bool(value) for _, key, value in _walk(raw)))
    positive_buff = any(
        key in {"hitSpeedMultiplier", "speedMultiplier", "damageMultiplier", "spawnSpeedMultiplier"}
        and _number(value) > 0 and not any("target" in part.lower() for part in path)
        for path, key, value in _walk(raw))
    heals = bool(_values(raw, "healPerSecond", "heal_amount")) or getattr(spell, "heal_amount", 0)
    out["friendly_buff"] = float(bool(positive_buff or heals))
    out["pull"] = float(_number(getattr(spell, "attract_percentage", 0)) > 0
                        or bool(_values(raw, "attractPercentage")))
    out["clone"] = float(type(spell).__name__ == "CloneSpell")
    out["mirror"] = float(isinstance(spell, MirrorSpell))
    pushback = max([0.0] + _values(raw, "attackPushback", "deathPushback", "pushback", "pushbackAll"))
    if spell is not None:
        pushback = max(pushback, _number(getattr(spell, "knockback_distance", 0)) * 1000.0)
    out["knockback_strength"] = _unit(pushback / 2000.0)
    death = max([0.0] + _values(raw, "deathDamage"))
    out["death_damage"] = _unit(math.log1p(death) / 8.0)
    deploy = max([0.0] + _values(raw, "damage", under="spawnAreaObject")
                 + _values(raw, "damage", under="spawnAreaEffect"))
    out["deploy_damage"] = _unit(math.log1p(deploy) / 8.0)
    hits = max([0.0] + _values(raw, "multipleProjectiles", "spawnCount"))
    if spell is not None:
        hits = max(hits, _number(getattr(spell, "multiple_projectiles", 0)) if
                   _number(getattr(spell, "multiple_projectiles", 0)) > 1 else 0.0,
                   _number(getattr(spell, "max_targets", 0)))
    out["multi_hit_count"] = _unit(hits / 12.0)
    for key, value in _ENGINE_ONLY_MECHANICS.get(resolve_card_name(name, definitions), {}).items():
        out[key] = float(value)
    vector[:] = [out[key] for key in V5_DESCRIPTOR_NAMES]
    return vector


def _ability_data(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The Champion ability record of a card or body entry.

    Most Champions carry it on the summoned character; Goblinstein carries it
    on its second character (the doctor).
    """
    for key in ("summonCharacterData", "summonCharacterSecondData"):
        character = raw.get(key)
        if isinstance(character, Mapping) and isinstance(character.get("abilityData"), Mapping):
            return character["abilityData"]
    ability = raw.get("abilityData")
    return ability if isinstance(ability, Mapping) else None


def champion_ability_cost(name: str, *, loader: CardDataLoader) -> float | None:
    """Static ability elixir cost of a Champion card or body, if it has an ability."""
    stats = loader.get_card(name)
    if stats is None:
        return None
    raw = getattr(stats, "_raw_entry", {}) or {}
    ability = _ability_data(raw)
    if not isinstance(ability, Mapping) or "manaCost" not in ability:
        return None
    return _number(ability.get("manaCost"))


# ---------------------------------------------------------------------------
# Observation builder and public projection
# ---------------------------------------------------------------------------

def hidden_from_enemy(entity: Any) -> bool:
    """Whether contract v5 hides this unit from the opposing actor."""
    if bool(getattr(entity, "_underground_deployment", False)):
        return True
    stealth_until = int(getattr(entity, "_stealth_until", 0) or 0)
    if stealth_until <= 0:
        return False
    battle = getattr(entity, "battle_state", None)
    now = logic_time_milliseconds(float(getattr(battle, "time", 0.0) or 0.0))
    return stealth_until > now


def champion_button_visible(battle: Any, player_id: int) -> bool:
    """Whether the player's Champion ability button is shown (owner deployed)."""
    if bool(getattr(battle, "game_over", False)):
        return False
    found = battle._champion_ability_mechanic(player_id)
    if found is None:
        return False
    entity, _ = found
    return bool(entity.is_alive and not getattr(entity, "placement_pending", False)
                and float(getattr(entity, "deploy_delay_remaining", 0.0) or 0.0) <= 1e-9)


class ContractV5ObservationBuilder(StructuredObservationBuilder):
    """Council public builder with the pinned v5 vocabulary and semantics v5."""

    public_contract_version = CONTRACT_VERSION

    def __init__(self, *, card_loader: CardDataLoader | None = None, max_entities: int = 128,
                 tokens: PinnedTokens | None = None) -> None:
        tokens = tokens or load_pinned_tokens()
        super().__init__(
            card_loader=card_loader, card_vocab=tokens.cards, token_names=tokens.tokens,
            max_entities=max_entities, canonical_perspective=True, canonical_lane_globals=True,
            public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
            public_entity_levels=True, public_hand_levels=True)
        self.pinned_tokens = tokens
        self.card_semantics_version = CARD_SEMANTICS_VERSION
        self.v4_card_stat_features = self.card_stat_features
        descriptors = np.zeros((len(self.token_names), len(V5_DESCRIPTOR_NAMES)), dtype=np.float32)
        for token_id, token in enumerate(self.token_names):
            if not token.startswith("<"):
                descriptors[token_id] = v5_card_descriptors(token, loader=self.loader)
        self.v5_card_descriptors = descriptors
        self.card_stat_features = np.concatenate([self.v4_card_stat_features, descriptors], axis=1)
        self._ability_costs = np.full(len(self.token_names), np.nan, dtype=np.float64)
        for token_id, token in enumerate(self.token_names):
            if not token.startswith("<"):
                cost = champion_ability_cost(token, loader=self.loader)
                if cost is not None:
                    self._ability_costs[token_id] = cost

    def _actor_visible(self, entity: Any, player_id: int) -> bool:
        if not entity.is_visible_to(player_id):
            return False
        if int(entity.player_id) == int(player_id):
            return True
        return not hidden_from_enemy(entity)

    def ability_cost_for_token(self, token_id: int) -> float | None:
        if not 0 < token_id < len(self._ability_costs):
            return None
        value = float(self._ability_costs[token_id])
        return None if math.isnan(value) else value

    def build_public(self, battle: Any, player_id: int) -> ConfidenceAwareActorObservation:
        """Actor observation projected onto the v5 public contract."""
        return project_public_v5(self.build_actor(battle, player_id),
                                 champion_button=champion_button_visible(battle, player_id))


def project_public_v5(observation: ActorObservation, *, champion_button: bool) -> ConfidenceAwareActorObservation:
    """Project exact public state onto contract v5 (adds no noise, infers nothing)."""
    source = exact_public_observation(observation)
    entity_allowed = np.zeros(observation.entity_features.shape, dtype=bool)
    entity_allowed[..., sorted(V5_ENTITY_FEATURE_INDICES)] = True
    global_allowed = np.zeros(observation.global_features.shape, dtype=bool)
    global_allowed[..., sorted(REAL_PLAY_GLOBAL_FEATURE_INDICES)] = True
    if champion_button:
        global_allowed[..., list(CHAMPION_GLOBAL_INDICES)] = True
    result = replace(
        source,
        observation=replace(
            observation,
            entity_features=np.where(entity_allowed, observation.entity_features, 0).astype(np.float32),
            global_features=np.where(global_allowed, observation.global_features, 0).astype(np.float32),
        ),
        entity_feature_confidence=np.where(entity_allowed, source.entity_feature_confidence, 0).astype(np.float32),
        global_feature_confidence=np.where(global_allowed, source.global_feature_confidence, 0).astype(np.float32),
    )
    validate_public_v5(result)
    return result


def validate_public_v5(observation: ConfidenceAwareActorObservation) -> None:
    """Reject actor values outside contract v5."""
    observation.validate()
    entity_confidence = observation.entity_feature_confidence
    global_confidence = observation.global_feature_confidence
    leaked_entities = [ENTITY_FEATURE_NAMES[index] for index in range(entity_confidence.shape[-1])
                       if index not in V5_ENTITY_FEATURE_INDICES and np.any(entity_confidence[..., index] > 0.0)]
    leaked_globals = [GLOBAL_FEATURE_NAMES[index] for index in range(global_confidence.shape[-1])
                      if index not in V5_GLOBAL_FEATURE_INDICES and np.any(global_confidence[..., index] > 0.0)]
    if leaked_entities or leaked_globals:
        raise ValueError(f"observation exceeds public contract v5: entity={leaked_entities}, global={leaked_globals}")
    champion = global_confidence[..., list(CHAMPION_GLOBAL_INDICES)]
    if np.any((champion > 0.0) != (champion[..., :1] > 0.0)):
        raise ValueError("champion cooldown and duration share one button visibility")
    hand = observation.observation.hand_ids
    if hand.shape[-1] > VISIBLE_CARD_SLOTS and np.any(hand[..., VISIBLE_CARD_SLOTS:] != 0):
        raise ValueError("observation exposes cards beyond hand plus public next card")


def champion_button_flags(global_feature_confidence: np.ndarray) -> np.ndarray:
    """Per-row button visibility recovered from stored global confidence."""
    return np.asarray(global_feature_confidence)[..., CHAMPION_COOLDOWN_GLOBAL] > 0.0


def global_confidence_v5(rows: int, champion_button: np.ndarray) -> np.ndarray:
    """Exact-source v5 global confidence for stored rows."""
    confidence = np.zeros((rows, len(GLOBAL_FEATURE_NAMES)), dtype=np.float32)
    confidence[:, sorted(REAL_PLAY_GLOBAL_FEATURE_INDICES)] = 1.0
    flags = np.asarray(champion_button, dtype=bool)
    for index in CHAMPION_GLOBAL_INDICES:
        confidence[flags, index] = 1.0
    return confidence


# ---------------------------------------------------------------------------
# Action mask
# ---------------------------------------------------------------------------

class ContractV5ActionMaskBuilder(PublicActionMaskBuilder):
    """v4 public mask with the float-robust footprint and the Champion ability."""

    def __init__(self, builder: ContractV5ObservationBuilder, *, mask_version: int = 1) -> None:
        if not isinstance(builder, ContractV5ObservationBuilder):
            raise TypeError("the v5 mask needs the v5 observation builder")
        super().__init__(builder, mask_version=mask_version)

    @staticmethod
    def _footprint_size(radius: float) -> int:
        # Radii come back from float32 card features (1.0 -> 1.0000000298);
        # round before taking the ceiling so a 3-tile Princess Tower stays 3.
        return max(1, math.ceil(round(max(0.0, radius) * 2.0, 4)) + 1)

    def _building_blockers(self, observation: Any, *, crowns_only: bool = False):
        # Body centres come back from float32 normalized features (a Princess
        # Tower at x=3.5 reads 3.5000002), which made the strict footprint
        # test block a fourth column on one side. Round centres to the
        # millitile so the footprint is symmetric: the game's 3x3 rule.
        return [(round(x, 3), round(y, 3), radius, half)
                for x, y, radius, half in super()._building_blockers(observation, crowns_only=crowns_only)]

    def _placement_occupied(self, x, y, radius, blockers, *, building_footprint_half,
                            observation, can_deploy_enemy_side):
        if building_footprint_half is None or not can_deploy_enemy_side:
            return super()._placement_occupied(
                x, y, radius, blockers, building_footprint_half=building_footprint_half,
                observation=observation, can_deploy_enemy_side=can_deploy_enemy_side)
        # Goblin Drill uses an even building footprint. Resolve its world-space
        # anchor before checking visible footprints, including for the red seat.
        # The requested tile must still clear the public crown-tower tiles.
        for bx, by, _, half in self._building_blockers(observation, crowns_only=True):
            if abs(x - bx) <= half - 0.5 + 1e-9 and abs(y - by) <= half - 0.5 + 1e-9:
                return True
        rotated = observation.board_rotated
        if rotated is None:
            return True
        position = Position(BOARD_WIDTH - x, BOARD_HEIGHT - y) if rotated else Position(x, y)
        anchor = building_anchor(position, int(round(building_footprint_half * 2)))
        ax, ay = ((BOARD_WIDTH - anchor.x, BOARD_HEIGHT - anchor.y) if rotated
                  else (anchor.x, anchor.y))
        return any(abs(ax - bx) < building_footprint_half + half - 0.5
                   and abs(ay - by) < building_footprint_half + half - 0.5
                   for bx, by, _, half in blockers)

    def ability_legal(self, observation: Any) -> bool:
        if observation.terminal is not False:
            return False
        confidence = observation.global_feature_confidence
        if confidence is None or confidence[5] <= 0.0:
            return False
        if confidence[CHAMPION_COOLDOWN_GLOBAL] <= 0.0 or confidence[CHAMPION_DURATION_GLOBAL] <= 0.0:
            return False
        features = observation.global_features
        if features[CHAMPION_COOLDOWN_GLOBAL] > 1e-6 or features[CHAMPION_DURATION_GLOBAL] > 1e-6:
            return False
        cost = self.visible_own_ability_cost(observation)
        if cost is None:
            return False
        return cost <= float(features[5]) * 10.0 + 1e-6

    def visible_own_ability_cost(self, observation: Any) -> float | None:
        identity = observation.entity_id_confidence
        costs = []
        for index in np.flatnonzero(observation.entity_mask).tolist():
            if observation.entity_features[index, 2] <= 0.5 or observation.entity_features[index, 4] <= 0.5:
                continue
            if identity is not None and identity[index] <= 0.0:
                continue
            cost = self.builder.ability_cost_for_token(int(observation.entity_ids[index]))
            if cost is not None:
                costs.append(cost)
        return max(costs) if costs else None

    def build(self, observation: Any) -> np.ndarray:
        mask = super().build(observation)
        mask[self.ability_action] = self.ability_legal(observation)
        return mask


class CachedContractV5ActionMask:
    """Exact memo of ``ContractV5ActionMaskBuilder.build`` for replay extraction.

    The key holds every observation value the builder reads: lifecycle, board
    rotation, hand tokens and confidences, per-slot affordability, the two
    enemy Princess flags, every confident building blocker and the ability
    inputs (button visibility, both clocks, own Champion costs, elixir).
    Mirror needs own play history and bypasses the memo.
    """

    def __init__(self, builder: ContractV5ObservationBuilder, *, maximum_entries: int = 20_000,
                 mask_version: int = 1) -> None:
        from clasher.spells import SPELL_REGISTRY, MirrorSpell

        self.builder = builder
        self.inner = ContractV5ActionMaskBuilder(builder, mask_version=mask_version)
        self.maximum_entries = maximum_entries
        self._cache: dict[tuple, np.ndarray] = {}
        self.hits = 0
        self.misses = 0
        definitions = builder.loader.load_card_definitions()
        self._cost = np.full(len(builder.token_names), np.inf, dtype=np.float64)
        self._mirror = np.zeros(len(builder.token_names), dtype=np.bool_)
        for token in range(1, len(builder.token_names)):
            name = builder.card_name_for_token_id(token)
            stats = builder.loader.get_card(name) if name is not None else None
            if stats is None:
                continue
            self._cost[token] = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            self._mirror[token] = isinstance(SPELL_REGISTRY.get(resolve_card_name(name, definitions)), MirrorSpell)

    def build(self, source: ConfidenceAwareActorObservation) -> np.ndarray:
        observation = source.observation
        request = PublicActionMaskInput.from_confidence_observation(source)
        # The frozen cache key omits visible timed payloads. Never reuse it for
        # v2; a future cache must key the complete public placement board.
        if self.inner.mask_version == 2:
            return self.inner.build(request)
        hand = observation.hand_ids[:NUM_HAND_SLOTS]
        if observation.terminal is not False or self._mirror[hand].any():
            return self.inner.build(request)
        confidence = source.global_feature_confidence
        elixir = float(observation.global_features[5]) * 10.0
        blockers = observation.entity_mask & (observation.entity_features[:, 5] > 0.5) & (source.entity_id_confidence > 0.0)
        button = bool(confidence[CHAMPION_COOLDOWN_GLOBAL] > 0.0)
        ability_key: tuple = (button,)
        if button:
            ability_key = (button, observation.global_features[list(CHAMPION_GLOBAL_INDICES)].tobytes(),
                           self.inner.visible_own_ability_cost(request), round(elixir, 6))
        key = (
            observation.board_rotated,
            hand.tobytes(),
            (source.hand_id_confidence[:NUM_HAND_SLOTS] > 0.0).tobytes(),
            bool(confidence[5] > 0.0),
            (self._cost[hand] > elixir + 1e-6).tobytes(),
            bool(confidence[11] > 0.0 and observation.global_features[11] <= 1e-4),
            bool(confidence[12] > 0.0 and observation.global_features[12] <= 1e-4),
            observation.entity_ids[blockers].tobytes(),
            observation.entity_features[blockers, :2].tobytes(),
            ability_key,
        )
        cached = self._cache.get(key)
        if cached is None:
            self.misses += 1
            cached = self.inner.build(request)
            cached.setflags(write=False)
            if len(self._cache) >= self.maximum_entries:
                self._cache.clear()
            self._cache[key] = cached
        else:
            self.hits += 1
        return cached


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

def build_contract_v5_model_config(builder: ContractV5ObservationBuilder, **overrides: Any):
    """The council pilot architecture on contract v5 (fresh-weight default)."""
    from .model import PolicyConfig

    values: dict[str, Any] = dict(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.max_entities,
        public_contract_version=CONTRACT_VERSION,
        public_token_names=builder.token_names,
        public_observation_confidence=True,
        actor_observation_domain="simulator-exact",
        canonical_lane_globals=True,
        card_semantics_version=CARD_SEMANTICS_VERSION,
        public_history_slots=4,
        public_seen_card_slots=8,
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        memory_kind="lstm",
        card_input_mode="hybrid",
        deterministic_hierarchy="slot",
    )
    values.update(overrides)
    return PolicyConfig(**values)


def action_mask_tile_count(mask: np.ndarray) -> int:
    return int(np.asarray(mask)[: NUM_HAND_SLOTS * NUM_TILES].sum())


# ---------------------------------------------------------------------------
# Checkpoint upgrade v4 -> v5
# ---------------------------------------------------------------------------

# Tensors whose first dimension is the token vocabulary. Rows are copied by
# token name; rows of new tokens start at zero.
_VOCABULARY_ROW_SUFFIXES = (
    "token_embedding.weight",
    "public_belief_hand_head.weight",
    "public_belief_hand_head.bias",
    "opponent_hand_head.weight",
    "opponent_hand_head.bias",
)
# Card descriptor buffers are rebuilt from the v5 builder; the rows of the
# source tokens must match the source buffers exactly.
_CARD_BUFFER_SUFFIXES = ("card_stat_features", "semantic_card_features")
_V5_NEW_SUFFIXES = ("v5_card_descriptors", "v5_descriptor_input.weight")


def upgrade_policy_payload_to_v5(payload: Mapping[str, Any], builder: ContractV5ObservationBuilder) -> dict[str, Any]:
    """Re-express a public-contract-v4 policy checkpoint on contract v5.

    Every tensor whose shape does not depend on the vocabulary is copied
    unchanged. Token-indexed rows (identity embeddings, opponent-hand heads)
    are copied by token name and new tokens get zero rows; the new v5
    descriptor input weights start at zero. On observations that only contain
    source tokens (and no v5-only channel) the upgraded policy's logits equal
    the source policy's bit for bit (tests/test_contract_v5.py).
    """
    import torch

    from .model import ClasherPolicy, PolicyConfig

    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    source_config = PolicyConfig.from_dict(dict(payload["model_config"]))
    if source_config.public_contract_version != 4 or source_config.card_semantics_version != 4:
        raise ValueError("the v5 upgrade starts from a public-contract-v4 / semantics-v4 policy")
    source_tokens = tuple(payload["token_names"])
    target_tokens = tuple(builder.token_names)
    index = {name: position for position, name in enumerate(target_tokens)}
    missing = [name for name in source_tokens if name not in index]
    if missing:
        raise ValueError(f"v5 vocabulary lacks source tokens {missing[:5]}")
    rows = torch.as_tensor([index[name] for name in source_tokens], dtype=torch.long)
    target_config = replace(
        source_config, num_tokens=len(target_tokens), public_token_names=target_tokens,
        public_contract_version=CONTRACT_VERSION, card_semantics_version=CARD_SEMANTICS_VERSION)
    target_model = ClasherPolicy(target_config, torch.as_tensor(builder.card_stat_features))
    target_state = target_model.state_dict()
    source_state = payload["model_state_dict"]
    upgraded: dict[str, Any] = {}
    for key, target in target_state.items():
        if key.endswith(_V5_NEW_SUFFIXES):
            if key.endswith("weight"):
                target = torch.zeros_like(target)
            upgraded[key] = target
            continue
        if key not in source_state:
            raise ValueError(f"source checkpoint lacks {key}")
        source = source_state[key]
        if key.endswith(_CARD_BUFFER_SUFFIXES):
            if not torch.equal(target[rows], source.to(target.dtype)):
                raise ValueError(f"v5 card descriptors differ from the source for {key}")
            upgraded[key] = target
        elif key.endswith(_VOCABULARY_ROW_SUFFIXES):
            value = torch.zeros_like(target)
            value[rows] = source.to(target.dtype)
            upgraded[key] = value
        else:
            if source.shape != target.shape:
                raise ValueError(f"unexpected vocabulary-dependent tensor {key} {tuple(source.shape)}")
            upgraded[key] = source.clone()
    unexpected = sorted(set(source_state) - set(upgraded))
    if unexpected:
        raise ValueError(f"source tensors without a v5 home: {unexpected[:5]}")
    target_model.load_state_dict(upgraded, strict=True)
    result = {key: value for key, value in payload.items() if key not in {"optimizer_state_dict"}}
    result["model_config"] = target_config.to_dict()
    result["token_names"] = target_tokens
    result["model_state_dict"] = target_model.state_dict()
    args = dict(result.get("args") or {})
    args["contract_v5_upgrade"] = {
        "source_contract_version": 4, "target_contract_version": CONTRACT_VERSION,
        "source_tokens": len(source_tokens), "target_tokens": len(target_tokens),
        "target_tokens_sha256": token_list_sha256(target_tokens),
        "rule": "token rows copied by name; new token rows and v5 descriptor inputs zero",
    }
    result["args"] = args
    return result
