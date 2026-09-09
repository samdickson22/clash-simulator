"""Read the audited public-global outcome view without loading entity tensors."""

import json
from pathlib import Path

import numpy as np

from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus
from scripts.train_hog26_procedural_outcome_candidate import require_current_audit


def protocol_audit_path(path, protocol, root):
    target = Path(path).resolve()
    stages = [*protocol["training"], protocol["development_selection"],
              protocol["probability_calibration"], *protocol["final_holdout"].values()]
    pairs = [(row["output_corpus"], row["audit_report"]) for row in stages]
    pairs.extend(protocol["primary_candidate_data"]["legacy_audit_reports"].items())
    matches = {str((root / audit).resolve()) for corpus, audit in pairs
               if (root / corpus).resolve() == target}
    if len(matches) != 1:
        raise ValueError("public projection requires one declared corpus audit")
    return Path(matches.pop())


def load_public_outcome_projection(path, *, audit_path):
    """A full-corpus audit is mandatory; projection is not a replacement audit."""
    require_current_audit(Path(path), Path(audit_path))
    row_names = (
        "global_features", "next_global_features", "final_outcomes",
        "terminal_tower_margins", "terminal_winners", "episode_starts", "dones",
    )
    episode_names = (
        "episode_opponent_indices", "episode_learner_players",
        "episode_final_outcomes", "episode_terminal_tower_margins",
        "episode_opponent_deck_indices", "episode_battle_indices",
    )
    with np.load(path, allow_pickle=False) as archive:
        if any(name.startswith("critic_") for name in archive.files):
            raise ValueError("public outcome archive contains privileged critic fields")
        metadata = json.loads(str(archive["metadata_json"].item()))
        corpus = DirectSimpleBehaviorCorpus(
            arrays={name: archive[name] for name in row_names},
            episode_offsets=archive["episode_offsets"],
            episode_stream_rows=archive["episode_stream_rows"],
            episode_ordinals=archive["episode_ordinals"],
            initial_hidden=archive["initial_hidden"], initial_cell=archive["initial_cell"],
            episode_arrays={name: archive[name] for name in episode_names if name in archive.files},
        )
    offsets = corpus.episode_offsets
    if offsets.ndim != 1 or len(offsets) < 2 or offsets[0] != 0 or (np.diff(offsets) <= 0).any():
        raise ValueError("invalid projected episode offsets")
    if (
        metadata.get("complete_episodes_only") is not True
        or metadata.get("row_count") != corpus.row_count
        or metadata.get("episode_count") != corpus.episode_count
        or len(offsets) != corpus.episode_count + 1
        or any(len(a) != corpus.row_count for a in corpus.arrays.values())
        or any(len(a) != corpus.episode_count for a in corpus.episode_arrays.values())
    ):
        raise ValueError("public projection metadata or row counts disagree")
    for name in ("global_features", "next_global_features"):
        if corpus.arrays[name].shape != (corpus.row_count, 18):
            raise ValueError("public projection requires exactly 18 globals")
    starts = np.zeros(corpus.row_count, dtype=bool)
    dones = np.zeros(corpus.row_count, dtype=bool)
    starts[offsets[:-1]] = True
    dones[offsets[1:] - 1] = True
    if not np.array_equal(starts, corpus.arrays["episode_starts"]) or not np.array_equal(dones, corpus.arrays["dones"]):
        raise ValueError("projected episode boundaries are not complete")
    return metadata, corpus
