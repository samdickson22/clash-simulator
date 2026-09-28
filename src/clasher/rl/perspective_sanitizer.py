"""Allowlist-only pixel boundary for bottom-player live inference.

Dual-HUD spectator footage contains the top player's private hand and elixir.
The production boundary therefore never returns a masked full frame.  It copies
only three explicitly public/owned surfaces out of the source image: arena,
public clock, and bottom-player HUD.  The raw image and the top HUD cannot enter
an actor input or cache through this API.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

PERSPECTIVE_SURFACE_SCHEMA = "clasher.live.bottom_perspective_surfaces.v1"
BOTTOM_PLAYER_PERSPECTIVE = "bottom_player"


class PerspectiveContractError(ValueError):
    """Raised when pixels do not satisfy the perspective privacy contract."""


@dataclass(frozen=True)
class NormalizedRegion:
    x: float
    y: float
    width: float
    height: float

    def validate(self, name: str) -> None:
        values = (self.x, self.y, self.width, self.height)
        if not all(np.isfinite(value) for value in values):
            raise PerspectiveContractError(f"{name} has non-finite coordinates")
        if (
            self.x < 0.0
            or self.y < 0.0
            or self.width <= 0.0
            or self.height <= 0.0
            or self.x + self.width > 1.0
            or self.y + self.height > 1.0
        ):
            raise PerspectiveContractError(f"{name} must be ordered within [0, 1]")

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        self.validate("region")
        x1 = round(self.x * width)
        y1 = round(self.y * height)
        x2 = round((self.x + self.width) * width)
        y2 = round((self.y + self.height) * height)
        if x2 <= x1 or y2 <= y1:
            raise PerspectiveContractError("normalized region became empty")
        return x1, y1, x2, y2


@dataclass(frozen=True)
class DualHudPerspectiveSpec:
    """Source-relative geometry established by a separately audited adapter."""

    arena: NormalizedRegion
    clock: NormalizedRegion
    own_hud: NormalizedRegion
    opponent_private: NormalizedRegion
    perspective: str = BOTTOM_PLAYER_PERSPECTIVE

    def validate(self) -> None:
        if self.perspective != BOTTOM_PLAYER_PERSPECTIVE:
            raise PerspectiveContractError(
                "only the bottom-player actor perspective is supported"
            )
        for name in ("arena", "clock", "own_hud", "opponent_private"):
            getattr(self, name).validate(name)
        if _overlaps(self.opponent_private, self.arena):
            raise PerspectiveContractError("opponent-private region overlaps arena")
        if _overlaps(self.opponent_private, self.own_hud):
            raise PerspectiveContractError("opponent-private region overlaps own HUD")
        # The clock is intentionally an isolated public cutout from the same
        # top band.  Requiring overlap prevents a spec from claiming privacy
        # while silently obtaining the clock from an unrelated safe region.
        if not _overlaps(self.opponent_private, self.clock):
            raise PerspectiveContractError(
                "public clock must be isolated from the opponent top-HUD band"
            )


def _overlaps(left: NormalizedRegion, right: NormalizedRegion) -> bool:
    return (
        left.x < right.x + right.width
        and right.x < left.x + left.width
        and left.y < right.y + right.height
        and right.y < left.y + left.height
    )


def _readonly_copy(
    frame: NDArray[np.uint8], box: tuple[int, int, int, int]
) -> NDArray[np.uint8]:
    x1, y1, x2, y2 = box
    result = cast(
        NDArray[np.uint8], np.ascontiguousarray(frame[y1:y2, x1:x2]).copy()
    )
    result.flags.writeable = False
    return result


def _surface_bytes(
    arena: NDArray[np.uint8],
    clock: NDArray[np.uint8],
    own_hud: NDArray[np.uint8],
) -> bytes:
    blocks: list[bytes] = [PERSPECTIVE_SURFACE_SCHEMA.encode("ascii") + b"\0"]
    for name, surface in (
        ("arena", arena),
        ("clock", clock),
        ("own_hud", own_hud),
    ):
        blocks.append(name.encode("ascii") + b"\0")
        blocks.append(struct.pack(">III", *surface.shape))
        blocks.append(surface.tobytes(order="C"))
    return b"".join(blocks)


@dataclass(frozen=True)
class SanitizedPolicySurfaces:
    """The complete set of pixels allowed to reach the bottom actor."""

    schema: str
    perspective: str
    source_shape: tuple[int, int, int]
    arena: NDArray[np.uint8]
    clock: NDArray[np.uint8]
    own_hud: NDArray[np.uint8]
    pixel_sha256: str

    def validate(self) -> None:
        if self.schema != PERSPECTIVE_SURFACE_SCHEMA:
            raise PerspectiveContractError("unsupported perspective surface schema")
        if self.perspective != BOTTOM_PLAYER_PERSPECTIVE:
            raise PerspectiveContractError("surface perspective is not bottom player")
        if len(self.source_shape) != 3 or self.source_shape[2] != 3:
            raise PerspectiveContractError("source shape must be HWC RGB/BGR")
        for name in ("arena", "clock", "own_hud"):
            surface = getattr(self, name)
            if (
                not isinstance(surface, np.ndarray)
                or surface.dtype != np.uint8
                or surface.ndim != 3
                or surface.shape[2] != 3
                or surface.size == 0
                or surface.flags.writeable
                or not surface.flags.c_contiguous
            ):
                raise PerspectiveContractError(
                    f"{name} must be nonempty read-only contiguous uint8 HWC"
                )
        digest = hashlib.sha256(
            _surface_bytes(self.arena, self.clock, self.own_hud)
        ).hexdigest()
        if digest != self.pixel_sha256:
            raise PerspectiveContractError("sanitized surface digest changed")


def sanitize_dual_hud_frame(
    frame: NDArray[np.uint8], spec: DualHudPerspectiveSpec
) -> SanitizedPolicySurfaces:
    """Copy only actor-allowed surfaces; never return or retain the raw frame."""

    spec.validate()
    if (
        not isinstance(frame, np.ndarray)
        or frame.dtype != np.uint8
        or frame.ndim != 3
        or frame.shape[2] != 3
        or min(frame.shape[:2]) <= 0
    ):
        raise PerspectiveContractError("frame must be nonempty uint8 HWC with 3 channels")
    height, width = frame.shape[:2]
    arena = _readonly_copy(frame, spec.arena.pixels(width, height))
    clock = _readonly_copy(frame, spec.clock.pixels(width, height))
    own_hud = _readonly_copy(frame, spec.own_hud.pixels(width, height))
    digest = hashlib.sha256(_surface_bytes(arena, clock, own_hud)).hexdigest()
    result = SanitizedPolicySurfaces(
        schema=PERSPECTIVE_SURFACE_SCHEMA,
        perspective=spec.perspective,
        source_shape=(int(frame.shape[0]), int(frame.shape[1]), int(frame.shape[2])),
        arena=arena,
        clock=clock,
        own_hud=own_hud,
        pixel_sha256=digest,
    )
    result.validate()
    return result


@dataclass(frozen=True)
class PolicyPixelInput:
    """Normalized actor tensors built exclusively from sanitized surfaces."""

    arena: NDArray[np.float32]
    clock: NDArray[np.float32]
    own_hud: NDArray[np.float32]
    source_pixel_sha256: str


def _normalized_chw(surface: NDArray[np.uint8]) -> NDArray[np.float32]:
    result = np.ascontiguousarray(surface.transpose(2, 0, 1), dtype=np.float32)
    result /= 255.0
    result.flags.writeable = False
    return result


def build_policy_pixel_input(surfaces: SanitizedPolicySurfaces) -> PolicyPixelInput:
    """Build actor tensors; raw ndarrays fail before any tensor/cache creation."""

    if not isinstance(surfaces, SanitizedPolicySurfaces):
        raise PerspectiveContractError(
            "policy input requires SanitizedPolicySurfaces, never a raw frame"
        )
    surfaces.validate()
    return PolicyPixelInput(
        arena=_normalized_chw(surfaces.arena),
        clock=_normalized_chw(surfaces.clock),
        own_hud=_normalized_chw(surfaces.own_hud),
        source_pixel_sha256=surfaces.pixel_sha256,
    )


class PolicySurfaceCache:
    """Minimal type-gated cache demonstrating sanitize-before-cache ordering."""

    def __init__(self) -> None:
        self._values: dict[str, PolicyPixelInput] = {}

    def store(self, surfaces: SanitizedPolicySurfaces) -> str:
        policy_input = build_policy_pixel_input(surfaces)
        self._values[policy_input.source_pixel_sha256] = policy_input
        return policy_input.source_pixel_sha256

    def get(self, key: str) -> PolicyPixelInput:
        return self._values[key]
