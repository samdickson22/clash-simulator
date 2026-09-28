"""Imported checkpoints must be independent copies and may never overwrite files."""

import pytest
from import_completed import copy_exact


def test_import_preserves_source_and_refuses_overwrite(tmp_path):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.write_bytes(b'checkpoint\x00\xff')
    copy_exact(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_ino != source.stat().st_ino
    with pytest.raises(ValueError, match='preserve'):
        copy_exact(source, destination)
    destination.write_bytes(b'changed-copy')
    assert source.read_bytes() == b'checkpoint\x00\xff'
