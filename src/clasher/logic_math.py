"""Deterministic fixed-point helpers from the native ``LogicMath`` class."""

from __future__ import annotations

from .kinematics import trunc_div


# LogicMath's integer sine table is scaled by 1024.
_SIN_TABLE = (
    0, 18, 36, 54, 71, 89, 107, 125, 143, 160, 178, 195, 213, 230, 248,
    265, 282, 299, 316, 333, 350, 367, 384, 400, 416, 433, 449, 465, 481,
    496, 512, 527, 543, 558, 573, 587, 602, 616, 630, 644, 658, 672, 685,
    698, 711, 724, 737, 749, 761, 773, 784, 796, 807, 818, 828, 839, 849,
    859, 868, 878, 887, 896, 904, 912, 920, 928, 935, 943, 949, 956, 962,
    968, 974, 979, 984, 989, 994, 998, 1002, 1005, 1008, 1011, 1014,
    1016, 1018, 1020, 1022, 1023, 1023, 1024, 1024,
)

# LogicMath's 0..45 degree arctangent lookup, indexed by a 0..128
# fixed-point ratio.
_ATAN_TABLE = (
    0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9,
    9, 10, 10, 11, 11, 11, 12, 12, 13, 13, 14, 14, 14, 15, 15, 16, 16,
    17, 17, 17, 18, 18, 19, 19, 19, 20, 20, 21, 21, 21, 22, 22, 22,
    23, 23, 24, 24, 24, 25, 25, 25, 26, 26, 27, 27, 27, 28, 28, 28,
    29, 29, 29, 30, 30, 30, 31, 31, 31, 32, 32, 32, 33, 33, 33, 34,
    34, 34, 35, 35, 35, 35, 36, 36, 36, 37, 37, 37, 37, 38, 38, 38,
    39, 39, 39, 39, 40, 40, 40, 40, 41, 41, 41, 41, 42, 42, 42, 42,
    43, 43, 43, 43, 44, 44, 44, 44, 45, 45, 45,
)

# Current native child-spawn loops advance their constant-priority allowance
# by 80 fixed-point units per child.
SPAWN_PRIORITY_STEP_LOGIC_UNITS = 80


def spawn_target_distance_discount_sq_units(index: int) -> int:
    """Return the native squared target-distance allowance for child ``index``."""
    offset_units = max(0, int(index)) * SPAWN_PRIORITY_STEP_LOGIC_UNITS
    return offset_units * offset_units


def logic_sin(degrees: int, magnitude: int) -> int:
    """Return ``LogicMath::sin(degrees, magnitude)``."""
    angle = int(degrees) % 360
    if angle < 180:
        table_index = angle if angle <= 90 else 180 - angle
        sine = _SIN_TABLE[table_index]
    else:
        reflected = angle - 180
        table_index = reflected if reflected <= 90 else 360 - angle
        sine = -_SIN_TABLE[table_index]
    return trunc_div(sine * int(magnitude), 1024)


def logic_cos(degrees: int, magnitude: int) -> int:
    """Return ``LogicMath::cos(degrees, magnitude)``."""
    return logic_sin(int(degrees) + 90, magnitude)


def rotate_logic_vector(
    x_units: int,
    y_units: int,
    degrees: int,
) -> tuple[int, int]:
    """Return ``LogicMath::getRotatedX/Y`` for a fixed-point vector."""
    sine = logic_sin(degrees, 1024)
    cosine = logic_cos(degrees, 1024)
    return (
        (cosine * int(x_units) - sine * int(y_units)) >> 10,
        (sine * int(x_units) + cosine * int(y_units)) >> 10,
    )


def logic_vector_angle(x_units: int, y_units: int) -> int:
    """Return LogicMath's integer angle for a fixed-point direction vector."""
    x = int(x_units)
    y = int(y_units)
    if x == 0 and y == 0:
        return 0
    abs_x = abs(x)
    abs_y = abs(y)
    if x > 0 and y >= 0:
        if y < x:
            return _ATAN_TABLE[trunc_div(y * 128, x)]
        return 90 - _ATAN_TABLE[trunc_div(x * 128, y)]
    if x <= 0 and y > 0:
        if abs_x < y:
            return 90 + _ATAN_TABLE[trunc_div(abs_x * 128, y)]
        return 180 - _ATAN_TABLE[trunc_div(y * 128, abs_x)]
    if x < 0 and y <= 0:
        if abs_y < abs_x:
            return 180 + _ATAN_TABLE[trunc_div(abs_y * 128, abs_x)]
        return 270 - _ATAN_TABLE[trunc_div(abs_x * 128, abs_y)]
    if abs_x < abs_y:
        return 270 + _ATAN_TABLE[trunc_div(abs_x * 128, abs_y)]
    return (360 - _ATAN_TABLE[trunc_div(abs_y * 128, abs_x)]) % 360
