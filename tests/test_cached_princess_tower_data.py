import json
import os

import pytest

from clasher import battle as battle_module
from clasher import data as data_module
from clasher.battle import BattleState
from clasher.rl.determinism_check import compute_rollout_digest


def _support_payload(*, attack_range: int) -> dict:
    return {
        "items": {
            "spells": [
                {
                    "name": "King_PrincessTowers",
                    "statCharacterData": {
                        "range": attack_range,
                        "projectileData": {"speed": 600},
                    },
                }
            ]
        }
    }


def test_cached_support_data_is_revision_keyed_and_copy_isolated(tmp_path):
    path = tmp_path / "gamedata.json"
    path.write_text(json.dumps(_support_payload(attack_range=7500)))
    data_module._load_princess_tower_character_snapshot.cache_clear()

    first = data_module.load_princess_tower_character_data(path)
    first["range"] = 1
    second = data_module.load_princess_tower_character_data(path)

    assert second["range"] == 7500
    assert second is not first
    assert second["projectileData"] is not first["projectileData"]

    path.write_text(json.dumps(_support_payload(attack_range=8000)))
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))

    assert data_module.load_princess_tower_character_data(path)["range"] == 8000


def test_two_battles_parse_support_data_once(monkeypatch):
    data_module._load_princess_tower_character_snapshot.cache_clear()
    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_PRINCESS_TOWER_DATA",
        True,
    )

    BattleState(fast_path=True)
    BattleState(fast_path=True)

    cache_info = data_module._load_princess_tower_character_snapshot.cache_info()
    assert cache_info.misses == 1
    assert cache_info.hits == 1


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_princess_data_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8867,
        "decisions": 64,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_PRINCESS_TOWER_DATA",
        False,
    )
    parsed = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_USE_CACHED_PRINCESS_TOWER_DATA",
        True,
    )
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == parsed.sha256
    assert cached.mask_shadow_checks == parsed.mask_shadow_checks
    assert cached.mask_shadow_mismatches == parsed.mask_shadow_mismatches == 0
