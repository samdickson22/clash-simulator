from __future__ import annotations

import json
import lzma
from pathlib import Path

import numpy as np

from clasher.rl.imitation import load_corpus
from clasher.rl.katacr_replay import (
    KataCRReplayConverter,
    import_katacr_replays,
    load_katacr_card_names,
    load_katacr_unit_names,
)


def _classifier_metadata(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "idx2card": {
                    "0": "cannon",
                    "1": "empty",
                    "2": "fireball",
                    "3": "hog-rider",
                    "4": "ice-golem",
                    "5": "ice-spirit",
                    "6": "ice-spirit-evolution",
                    "7": "musketeer",
                    "8": "skeletons",
                    "9": "skeletons-evolution",
                    "10": "the-log",
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _source_root(path: Path) -> Path:
    label_path = path / "katacr/constants/label_list.py"
    label_path.parent.mkdir(parents=True)
    label_path.write_text(
        "unit_list = ['king-tower', 'queen-tower', 'hog-rider', 'bar']\n",
        encoding="utf-8",
    )
    return path


def _episode() -> dict[str, object]:
    states = [
        {
            "time": 4,
            "unit_infos": [
                {"xy": np.asarray([9.0, 28.0]), "cls": 0, "bel": 0},
                {"xy": np.asarray([9.0, 4.0]), "cls": 0, "bel": 1},
                {"xy": np.asarray([16.0, 18.0]), "cls": 2, "bel": 0},
                {"xy": np.asarray([1.0, 1.0]), "cls": 3, "bel": 0},
            ],
            "cards": [7, 3, 4, 10, 5],
            "elixir": 4,
        },
        {
            "time": 5,
            "unit_infos": [],
            "cards": [7, 3, 4, 10, 5],
            "elixir": 4,
        },
    ]
    actions = [
        {"xy": np.asarray([16.6, 17.3]), "card_id": 1},
        {"xy": None, "card_id": 0},
    ]
    return {"state": states, "action": actions, "reward": np.zeros(2)}


def test_loads_external_schema_without_importing_katacr(tmp_path: Path) -> None:
    source = _source_root(tmp_path / "source")
    metadata = _classifier_metadata(tmp_path / "metadata")
    assert load_katacr_unit_names(
        source / "katacr/constants/label_list.py"
    ) == ("king-tower", "queen-tower", "hog-rider", "bar")
    cards = load_katacr_card_names(metadata)
    assert cards[1] is None
    assert cards[3] == "hog-rider"


def test_converter_rotates_bottom_player_and_forces_noop_context(tmp_path: Path) -> None:
    source = _source_root(tmp_path / "source")
    metadata = _classifier_metadata(tmp_path / "metadata")
    converter = KataCRReplayConverter(
        decks_path=Path("decks.json").resolve(),
        unit_names=load_katacr_unit_names(
            source / "katacr/constants/label_list.py"
        ),
        card_names=load_katacr_card_names(metadata),
    )
    arrays = converter.convert_episode(_episode(), episode_id=3)
    action = int(arrays["expert_actions"][0])
    assert action // (18 * 32) == 0
    assert action % (18 * 32) == 14 * 18 + 1
    assert bool(arrays["action_masks"][0][action])
    assert int(np.count_nonzero(arrays["action_masks"][1])) == 1
    assert bool(arrays["action_masks"][1][converter.noop_action])
    features = arrays["entity_features"][0]
    mask = arrays["entity_mask"][0]
    visible = features[mask]
    assert len(visible) == 3
    assert any(np.allclose(row[:4], [0.5, 0.125, 1.0, 0.0]) for row in visible)
    assert converter.skipped_visual_rows == 1


def test_converter_drops_unrecoverable_empty_slot_placement_as_context(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path / "source")
    metadata = _classifier_metadata(tmp_path / "metadata")
    converter = KataCRReplayConverter(
        decks_path=Path("decks.json").resolve(),
        unit_names=load_katacr_unit_names(
            source / "katacr/constants/label_list.py"
        ),
        card_names=load_katacr_card_names(metadata),
    )
    episode = _episode()
    states = episode["state"]
    actions = episode["action"]
    assert isinstance(states, list) and isinstance(actions, list)
    states[0]["cards"] = [7, 3, 1, 10, 5]
    actions[0] = {"xy": np.asarray([16.6, 17.3]), "card_id": 2}

    arrays = converter.convert_episode(episode, episode_id=4)

    assert int(arrays["expert_actions"][0]) == converter.noop_action
    assert int(np.count_nonzero(arrays["action_masks"][0])) == 1
    assert bool(arrays["action_masks"][0][converter.noop_action])
    assert converter.dropped_unrecoverable_placement_rows == 1


def test_imported_corpus_is_directly_loadable_by_imitation_fitter(
    tmp_path: Path,
) -> None:
    source = _source_root(tmp_path / "source")
    classifier = _classifier_metadata(tmp_path / "metadata")
    dataset = tmp_path / "replays/fast_hog_2.6"
    dataset.mkdir(parents=True)
    replay = dataset / "episode.npy.xz"
    with lzma.open(replay, "wb") as target:
        np.save(target, _episode(), allow_pickle=True)
    output = tmp_path / "human.npz"
    manifest = tmp_path / "human.json"
    metadata, stats = import_katacr_replays(
        dataset_root=dataset.parent,
        katacr_source_root=source,
        classifier_metadata=classifier,
        decks_path=Path("decks.json").resolve(),
        output_path=output,
        manifest_path=manifest,
    )
    loaded_metadata, arrays = load_corpus(output)
    assert loaded_metadata == metadata
    assert loaded_metadata.label_source == "human-replay"
    assert stats.samples == 2
    assert stats.placement_samples == 1
    assert arrays["episode_starts"].tolist() == [True, False]
    assert json.loads(manifest.read_text())["stats"]["episodes"] == 1
