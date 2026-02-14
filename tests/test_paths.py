from clasher.paths import checkpoints_dir, decks_path, gamedata_path, latest_checkpoint, resolve_path


def test_default_data_paths_exist():
    assert gamedata_path().exists()
    assert decks_path().exists()


def test_latest_checkpoint_missing_dir_returns_none(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    assert latest_checkpoint(missing_dir) is None


def test_checkpoints_dir_create_and_resolve(tmp_path):
    target = tmp_path / "nested" / "ckpts"
    resolved = checkpoints_dir(target, create=True)
    assert resolved.exists()
    assert resolved.is_dir()
    assert resolve_path(resolved, must_exist=True) == resolved
