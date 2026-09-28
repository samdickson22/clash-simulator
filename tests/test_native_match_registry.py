import copy

import pytest

from clasher.rl.native_match_registry import native_match_id, register_native_root


def config(seed=3):
    return {"rndSeed": seed, "battle": {"deck0": [1, 2], "deck1": [3, 4], "lvlcap": 11}}


def test_reopened_registry_retains_role_despite_key_order(tmp_path):
    path = tmp_path / "roots.sqlite"
    first = register_native_root(path, config(), role="development")
    reordered = {"battle": config()["battle"], "rndSeed": 3}
    assert register_native_root(path, reordered, role="development") == first
    for role in ("training", "selection", "acceptance"):
        with pytest.raises(ValueError, match="already assigned"):
            register_native_root(path, config(), role=role)


def test_distinct_seed_can_have_an_independent_role(tmp_path):
    path = tmp_path / "roots.sqlite"
    a = register_native_root(path, config(), role="development")
    b = register_native_root(path, config(4), role="acceptance")
    assert a.duplicate_group_id != b.duplicate_group_id


def test_match_identity_keeps_related_branches_in_same_root(tmp_path):
    root = register_native_root(tmp_path / "roots.sqlite", config(), role="development")
    commands = [
        {
            "owner": 1,
            "card_id": 28000011,
            "x": 4500,
            "y": 21500,
            "submitted_tick": 4020,
            "execution_tick": 4021,
        }
    ]
    first = native_match_id(root, commands)
    assert native_match_id(root, copy.deepcopy(commands)) == first
    commands[0]["x"] += 1000
    assert native_match_id(root, commands) != first


@pytest.mark.parametrize("bad", [float("nan"), True, "3", None])
def test_noninteger_seeds_cannot_alias_valid_roots(tmp_path, bad):
    with pytest.raises(ValueError):
        register_native_root(tmp_path / "roots.sqlite", config(bad), role="development")


def test_process_metadata_cannot_enter_match_identity(tmp_path):
    root = register_native_root(tmp_path / "roots.sqlite", config(), role="development")
    with pytest.raises(ValueError):
        native_match_id(root, [{"sequence": 8}])
