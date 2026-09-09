"""Diagnostic tower-shot receipts with a separate outcome-sidecar vocabulary.

Princess shots use a serialized projectile identity. King shots use a public
origin category, not an asserted asset identity. Both observing seats must see
that exact launch source; this adapter does not invent a per-seat fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from clasher.data import load_princess_tower_character_data
from clasher.entities import Building
from clasher.kinematics import tiles_to_logic_units
from scripts.hog26_scalar_projectile_receipts import (
    ScalarProjectileReceiptRecorder,
    _payload_digest,
)


@dataclass(frozen=True)
class ScalarTowerProjectileDescriptor:
    source: Building
    source_id: int
    owner: int
    position_units: tuple[int, int]
    source_card: str
    tower_slot: str
    token: int
    projectile_payload_sha256: str
    source_visible_to: Callable[[object, int], bool]

    def validate_source(self, source):
        if (
            source is not self.source
            or type(source) is not Building
            or source.id != self.source_id
            or source.player_id != self.owner
            or not source.is_alive
            or source.card_stats is None
            or source.card_stats.name != self.source_card
            or getattr(source, "_crown_tower_slot", None) != self.tower_slot
            or (
                tiles_to_logic_units(source.position.x),
                tiles_to_logic_units(source.position.y),
            )
            != self.position_units
            or _payload_digest(source.card_stats.projectile_data)
            != self.projectile_payload_sha256
        ):
            raise ValueError("tower source differs from its exact initial receipt")
        if not all(bool(self.source_visible_to(source, seat)) for seat in (0, 1)):
            raise ValueError("tower launch source is not observable to both seats")


@dataclass(frozen=True)
class ScalarTowerReceiptSetup:
    battle: object
    descriptors: tuple[ScalarTowerProjectileDescriptor, ...]
    token_names: tuple[str, ...]
    extra_public_effect_ids: tuple[int, int]
    base_vocabulary_sha256: str
    princess_serialized_sha256: str

    @property
    def extra_public_effect_tokens(self):
        return self.token_names[494:]

    @classmethod
    def compile(
        cls,
        battle,
        initial_towers: Iterable[Building],
        loader,
        vocabulary,
        *,
        source_visible_to: Callable[[object, int], bool],
    ):
        """Bind the actual initial six objects before any additional spawning."""
        towers = tuple(initial_towers)
        if (
            len(towers) != 6
            or len({id(tower) for tower in towers}) != 6
            or len(battle.entities) != 6
            or any(
                actual is not receipt
                for actual, receipt in zip(
                    battle.entities.values(), towers, strict=True
                )
            )
            or battle.time != 0
            or battle.tick != 0
        ):
            raise ValueError("expected the exact six initial tower receipts")
        if len(vocabulary.token_names) != 494:
            raise ValueError(
                "tower sidecar requires the frozen 494-token policy vocabulary"
            )
        princess = load_princess_tower_character_data(loader.data_file)
        if _payload_digest(princess) != _payload_digest(
            battle._load_princess_tower_character_data()
        ):
            raise ValueError(
                "battle and appearance setup use different princess authority"
            )
        projectile_name = princess.get("projectileData", {}).get("name")
        if not isinstance(projectile_name, str) or not projectile_name:
            raise ValueError("princess has no serialized projectile appearance")
        categories = ("projectile:" + projectile_name, "public_tower_shot:king")
        if any(name in vocabulary.token_names for name in categories):
            raise ValueError(
                "base policy vocabulary unexpectedly contains sidecar categories"
            )
        names = (*vocabulary.token_names, *categories)
        tokens = (494, 495)
        coordinates = (
            battle.arena.BLUE_LEFT_TOWER,
            battle.arena.BLUE_RIGHT_TOWER,
            battle.arena.BLUE_KING_TOWER,
            battle.arena.RED_LEFT_TOWER,
            battle.arena.RED_RIGHT_TOWER,
            battle.arena.RED_KING_TOWER,
        )
        descriptors = []
        for index, (tower, position) in enumerate(
            zip(towers, coordinates, strict=True)
        ):
            slot = ("left", "right", "king")[index % 3]
            descriptor = ScalarTowerProjectileDescriptor(
                source=tower,
                source_id=tower.id,
                owner=index // 3,
                position_units=(
                    tiles_to_logic_units(position.x),
                    tiles_to_logic_units(position.y),
                ),
                source_card="KingTower" if slot == "king" else "Tower",
                tower_slot=slot,
                token=tokens[slot == "king"],
                projectile_payload_sha256=_payload_digest(
                    tower.card_stats.projectile_data
                ),
                source_visible_to=source_visible_to,
            )
            descriptor.validate_source(tower)
            descriptors.append(descriptor)
        return cls(
            battle,
            tuple(descriptors),
            tuple(names),
            tokens,
            vocabulary.sha256,
            _payload_digest(princess),
        )

    def recorder(self):
        return ScalarProjectileReceiptRecorder(
            self.battle,
            ((descriptor.source, descriptor) for descriptor in self.descriptors),
        )
