"""Deterministic enabled-card audit for the standalone projectile bridge.

This module is verification support, not a resident-engine capability claim.
Catalog support means only that :class:`TensorResidentProjectileSpellBridge`
can serialize and execute the payload in isolation.  Full resident-engine
parity still requires action ingress and every surrounding tick phase to stay
resident and match the Python oracle.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

import torch

from clasher.battle import BattleState
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks

from .catalog import TensorCardCatalog
from .projectile_bridge import (
    BridgePayloadKind,
    TensorResidentProjectileSpellBridge,
)
from .resident_engine import _resident_deployment_catalog_closure
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime

FeatureScalar: TypeAlias = bool | int | float | str | None
FeatureValue: TypeAlias = FeatureScalar | tuple[object, ...]


@dataclass(frozen=True)
class ProjectileBridgeCoverageEntry:
    card_name: str
    payload_kind: str
    bridge_supported: bool
    unsupported_reason: str | None
    serialized_features: tuple[tuple[str, FeatureValue], ...]

    @property
    def feature_map(self) -> Mapping[str, FeatureValue]:
        return dict(self.serialized_features)

    @property
    def resident_engine_parity_evidence(self) -> bool:
        """Standalone bridge support is never full resident-engine evidence."""

        return False


@dataclass(frozen=True)
class ProjectileBridgeCoverageMatrix:
    entries: tuple[ProjectileBridgeCoverageEntry, ...]
    digest: str
    resident_engine_parity_claimed: bool = False

    @property
    def supported_cards(self) -> tuple[str, ...]:
        return tuple(
            entry.card_name for entry in self.entries if entry.bridge_supported
        )

    @property
    def unsupported_cards(self) -> tuple[str, ...]:
        return tuple(
            entry.card_name for entry in self.entries if not entry.bridge_supported
        )

    @property
    def reason_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(
            entry.unsupported_reason or "supported" for entry in self.entries
        )
        return tuple(sorted(counts.items()))

    def require_standalone_support(
        self, card_name: str
    ) -> ProjectileBridgeCoverageEntry:
        entry = next(
            (item for item in self.entries if item.card_name == card_name), None
        )
        if entry is None:
            raise KeyError(card_name)
        if not entry.bridge_supported:
            raise ValueError(
                f"{card_name} is unsupported by the standalone projectile bridge: "
                f"{entry.unsupported_reason}"
            )
        return entry


def _value(tensor: torch.Tensor, index: int) -> FeatureScalar:
    value = tensor[index].item()
    if tensor.dtype == torch.bool:
        return bool(value)
    if tensor.dtype.is_floating_point:
        return float(value)
    return int(value)


def _features(
    bridge: TensorResidentProjectileSpellBridge,
    card_id: int,
    card_names: Sequence[str],
) -> tuple[tuple[str, FeatureValue], ...]:
    catalog = bridge.catalog
    child_id = int(catalog.spawn_card_id[card_id].item())
    spawn_count = int(catalog.spawn_count[card_id].item())
    offsets = tuple(
        tuple(
            tuple(
                tuple(int(axis) for axis in offset)
                for offset in catalog.spawn_offsets_units[
                    card_id, owner, lane, :spawn_count
                ].tolist()
            )
            for lane in range(2)
        )
        for owner in range(2)
    )
    planes = (
        "projectile_speed_units",
        "radius_units",
        "damage",
        "hits_air",
        "hits_ground",
        "ignore_buildings",
        "crown_multiplier",
        "crown_damage",
        "crown_damage_valid",
        "stun_ms",
        "slow_ms",
        "slow_multiplier",
        "slow_attack_multiplier",
        "slow_spawn_multiplier",
        "knockback_units",
        "knockback_ignores_mass",
        "duration_ms",
        "interval_ms",
        "initial_delay_ms",
        "max_ticks",
        "damage_on_spawn",
        "projectile_start_radius_units",
        "projectile_y_offset_units",
        "tracks_target",
        "card_knockback_immune",
        "multiple_projectiles",
        "damage_waves",
        "damage_wave_interval_ms",
        "spread_radius_units",
        "projectile_pattern",
        "spawn_count",
        "spawn_deploy_delay_ms",
        "spawn_const_priority",
        "spawn_hp_integer_kind",
        "spawn_hitpoints",
        "spawn_collision_radius_units",
        "spawn_is_air_unit",
        "spawn_lifetime_ms",
    )
    features: list[tuple[str, FeatureValue]] = [
        (name, _value(getattr(catalog, name), card_id)) for name in planes
    ]
    features.extend(
        (
            (
                "spawn_card_name",
                card_names[child_id] if 0 < child_id < len(card_names) else None,
            ),
            ("spawn_offsets_units", offsets),
        )
    )
    return tuple(features)


def _digest(entries: Sequence[ProjectileBridgeCoverageEntry]) -> str:
    payload = [
        {
            "card": entry.card_name,
            "kind": entry.payload_kind,
            "supported": entry.bridge_supported,
            "reason": entry.unsupported_reason,
            "features": dict(entry.serialized_features),
        }
        for entry in entries
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def enumerate_enabled_projectile_bridge_coverage(
    *,
    device: str | torch.device = "cpu",
    decks_path: str = "decks.json",
    card_names: Sequence[str] | None = None,
) -> ProjectileBridgeCoverageMatrix:
    """Compile the stable standalone-bridge feature matrix for enabled cards."""

    names = tuple(
        sorted(
            set(
                card_names
                if card_names is not None
                else unique_cards_from_decks(load_deck_pool(decks_path))
            )
        )
    )
    if not names:
        raise ValueError("projectile bridge coverage manifest is empty")
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    for player in battle.players:
        player.deck = list(names)
        player.hand = [*names[:4], *([None] * max(0, 4 - len(names)))]
        player.cycle_queue.clear()
    loader, closure = _resident_deployment_catalog_closure(
        battle.card_loader, set(names)
    )
    cards = TensorCardCatalog.compile(loader, closure, device=device)
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=8,
        max_cards=max(16, len(names)),
        event_capacity=256,
        catalog=cards,
    )
    objects = TensorRuntimeObjectPhase.from_battles(runtime, [battle], max_objects=64)
    bridge = TensorResidentProjectileSpellBridge.from_battles(
        runtime, objects, [battle]
    )
    kind_names = {int(kind): kind.name.lower() for kind in BridgePayloadKind}
    entries = tuple(
        ProjectileBridgeCoverageEntry(
            card_name=name,
            payload_kind=kind_names[int(bridge.catalog.kind[card_id].item())],
            bridge_supported=bool(bridge.catalog.supported[card_id].item()),
            unsupported_reason=bridge.catalog.unsupported_reason[card_id],
            serialized_features=_features(bridge, card_id, runtime.battle.card_names),
        )
        for name in names
        for card_id in (runtime.battle.card_to_id[name],)
    )
    return ProjectileBridgeCoverageMatrix(entries=entries, digest=_digest(entries))


__all__ = [
    "ProjectileBridgeCoverageEntry",
    "ProjectileBridgeCoverageMatrix",
    "enumerate_enabled_projectile_bridge_coverage",
]
