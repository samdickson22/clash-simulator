from copy import deepcopy

import pytest

from scripts.hog26_inference_authority import (
    SOURCES,
    capture_inference_authority,
    validate_inference_authority,
)


def test_authority_detects_source_and_runtime_drift(tmp_path):
    for name in SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixed source")
    authority = capture_inference_authority(tmp_path)
    validate_inference_authority(authority, tmp_path)
    wrong = deepcopy(authority)
    wrong["runtime"]["torch"] = "different"
    with pytest.raises(ValueError, match="authority changed"):
        validate_inference_authority(wrong, tmp_path)
    (tmp_path / SOURCES[0]).write_text("changed source")
    with pytest.raises(ValueError, match="authority changed"):
        validate_inference_authority(authority, tmp_path)
