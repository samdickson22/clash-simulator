from __future__ import annotations

import numpy as np
import pytest

from scripts.extract_tv_royale_eight_card_deck_sheet import PlayerDeckState


def _crop(value: int) -> np.ndarray:
    output = np.full((90, 70, 3), value, dtype=np.uint8)
    output[10:50, 10:50] = value // 2
    return output


def test_next_change_requires_three_stable_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vectors = {
        10: np.asarray([1.0, 0.0], dtype=np.float32),
        20: np.asarray([0.0, 1.0], dtype=np.float32),
    }

    def vector(crop: np.ndarray) -> np.ndarray:
        return vectors[int(crop[0, 0, 0])]

    monkeypatch.setattr(
        "scripts.extract_tv_royale_eight_card_deck_sheet._art_vector", vector
    )
    state = PlayerDeckState(0)
    state.initialize(0, [_crop(10) for _ in range(5)])
    state.observe_next(1, _crop(20))
    state.observe_next(2, _crop(10))
    assert len(state.next_crops) == 1
    for frame in (3, 4, 5):
        state.observe_next(frame, _crop(20))
    assert len(state.next_crops) == 2
    assert state.next_frames == [0, 3]
