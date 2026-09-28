"""Ordered body buckets used by the native avoidance query."""

from collections import defaultdict
from collections.abc import Iterable, Iterator

from .entities import Building, Entity, Troop
from .kinematics import tiles_to_logic_units


class NativeAvoidanceGrid:
    """Keep indexed extents fixed while component phases move live bodies.

    Native 15.535.86 rebuilds in manager order at f34784, inserts at f348d4,
    and scans x before y at f34b3c. Circle filtering uses current positions
    in the caller, after retrieving these ordered candidates.
    """

    def __init__(self, entities: Iterable[Entity]) -> None:
        self.buckets: dict[tuple[int, int], list[Entity]] = defaultdict(list)
        for entity in entities:
            self.add(entity)

    def add(self, entity: Entity) -> None:
        if not isinstance(entity, (Troop, Building)):
            return
        radius = tiles_to_logic_units(entity.get_collision_radius())
        if radius < 1:
            return
        # f34928 selects the unpadded radius when the movement getter is null;
        # a live movement component expands its indexed extent by250 units.
        if (
            isinstance(entity, Troop)
            and entity.is_alive
            and entity.spawn_stagger_remaining <= 1e-9
        ):
            radius += 250
        x = tiles_to_logic_units(entity.position.x)
        y = tiles_to_logic_units(entity.position.y)
        for bx in range(max(0, (x - radius) >> 10), min(17, (x + radius) >> 10) + 1):
            for by in range(max(0, (y - radius) >> 10), min(31, (y + radius) >> 10) + 1):
                self.buckets[bx, by].append(entity)

    def query(self, x: int, y: int, radius: int) -> Iterator[Entity]:
        seen: set[int] = set()
        for bx in range(max(0, (x - radius) >> 10), min(17, (x + radius) >> 10) + 1):
            for by in range(max(0, (y - radius) >> 10), min(31, (y + radius) >> 10) + 1):
                for entity in self.buckets.get((bx, by), ()):
                    if entity.id not in seen:
                        seen.add(entity.id)
                        yield entity
