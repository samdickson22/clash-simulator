import pytest

from clasher import native_tilemap
from clasher.rl.determinism_check import compute_rollout_digest


def test_native_path_cell_cache_matches_full_scan_for_standard_and_edge_cells(
    monkeypatch,
):
    cells = [
        (cell_x, cell_y)
        for cell_x in range(-2, native_tilemap.STANDARD_PATH_WIDTH + 2)
        for cell_y in range(-2, native_tilemap.STANDARD_PATH_HEIGHT + 2)
    ]
    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", False)
    expected = [
        native_tilemap.nearest_native_path_id(cell_x * 500, cell_y * 500)
        for cell_x, cell_y in cells
    ]

    native_tilemap._nearest_native_path_id_for_cell.cache_clear()
    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", True)
    actual = [
        native_tilemap.nearest_native_path_id(cell_x * 500, cell_y * 500)
        for cell_x, cell_y in cells
    ]

    assert actual == expected


def test_native_path_cell_cache_does_not_change_other_object_tie_scan(monkeypatch):
    cases = [
        (8_995, 15_500, 7_500),
        (9_000, 15_500, 10_500),
        (9_005, 16_000, 7_500),
    ]
    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", False)
    expected = [native_tilemap.nearest_native_path_id(*case) for case in cases]
    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", True)
    actual = [native_tilemap.nearest_native_path_id(*case) for case in cases]
    assert actual == expected


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_native_path_cell_cache_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path,
):
    common = {
        "seed": 2301,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", False)
    full_scan = compute_rollout_digest(**common)
    native_tilemap._nearest_native_path_id_for_cell.cache_clear()
    monkeypatch.setattr(native_tilemap, "_USE_NATIVE_PATH_ID_CELL_CACHE", True)
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == full_scan.sha256
    assert cached.mask_shadow_mismatches == full_scan.mask_shadow_mismatches == 0
