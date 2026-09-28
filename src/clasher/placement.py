"""World-space building anchors shared by deployment and legality checks."""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache

from .arena import Position, TileGrid
from .native_tilemap import native_spawn_tile_blocked


def ground_spawn_tile_clear(position: Position) -> bool:
    """Check the terrain under an ordinary ground troop's anchor tile."""
    # LogicSummoner f3878c..f38804 checks all four half-tile cells, not just
    # the center. A legal command at a bridge edge can resolve elsewhere.
    tile_x, tile_y = math.floor(position.x), math.floor(position.y)
    return not any(
        native_spawn_tile_blocked(2 * tile_x + dx, 2 * tile_y + dy)
        for dx in (0, 1)
        for dy in (0, 1)
    )


def native_deployment_search(
    requested: Position,
    initial: Position,
    is_valid: Callable[[Position], bool],
) -> Position | None:
    """Search native square rings, retaining the nearest candidate in a ring."""
    # LogicSummoner f38554-f38998 visits four rotations for each perimeter
    # offset. It stops after the first ring with a legal candidate, and only
    # strictly better squared distance replaces a previously selected tie.
    for radius in range(31):
        best = None
        best_distance = None
        offsets = [(0, 0)] if radius == 0 else [
            point
            for along in range(-radius, radius)
            for point in (
                (along, -radius), (-radius, -along),
                (-along, radius), (radius, along),
            )
        ]
        for dx, dy in offsets:
            candidate = Position(initial.x + dx, initial.y + dy)
            if not is_valid(candidate):
                continue
            distance = (
                (round(candidate.x * 1000) - round(requested.x * 1000)) ** 2
                + (round(candidate.y * 1000) - round(requested.y * 1000)) ** 2
            )
            if best_distance is None or distance < best_distance:
                best, best_distance = candidate, distance
        if best is not None:
            return best
    return None


@lru_cache(maxsize=16)
def _buildable_anchors(footprint_size: int) -> tuple[tuple[float, float], ...]:
    """Static footprint candidates on the standard arena's placement grid."""
    offset = 0.5 if footprint_size % 2 else 0.0
    half = footprint_size / 2.0
    blocked = set(TileGrid.BLOCKED_TILES)
    candidates = []
    for y in range(32):
        for x in range(18):
            cx, cy = x + offset, y + offset
            left, bottom = int(cx - half), int(cy - half)
            right, top = left + footprint_size, bottom + footprint_size
            if left < 0 or bottom < 0 or right > 18 or top > 32:
                continue
            if any(
                15 <= ty < 17 or (tx, ty) in blocked
                for tx in range(left, right)
                for ty in range(bottom, top)
            ):
                continue
            candidates.append((cx, cy))
    return tuple(candidates)


def building_anchor(position: Position, footprint_size: int) -> Position:
    """Resolve a command tile to the native odd/even footprint anchor.

    Native Tesla/Cannon/Xbow captures show world flooring for both players:
    even footprints sit on integer coordinates, odd footprints on tile centers.
    """
    offset = 0.5 if footprint_size % 2 else 0.0
    anchor = (math.floor(position.x) + offset, math.floor(position.y) + offset)
    candidates = _buildable_anchors(footprint_size)
    if anchor in candidates:
        return Position(*anchor)
    # Keep ordinary world-flooring when legal. A blocked footprint searches
    # around the requested point; observed equal-distance ties favor larger
    # world coordinates, including Tesla's upper river-bank half-tile tie.
    if not candidates:
        raise ValueError("building footprint does not fit the standard arena")
    resolved = min(
        candidates,
        key=lambda p: ((p[0] - position.x) ** 2 + (p[1] - position.y) ** 2, -p[0], -p[1]),
    )
    return Position(*resolved)
