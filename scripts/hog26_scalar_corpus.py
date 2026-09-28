"""Complete learner-view games; publication occurs only after independent validation."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np

ACTOR_FIELDS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "opponent_history_ids",
    "opponent_history_ages",
    "opponent_seen_card_ids",
)
CONFIDENCE_FIELDS = (
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_id_confidence",
    "global_feature_confidence",
)
ROW_FIELDS = (
    ACTOR_FIELDS
    + CONFIDENCE_FIELDS
    + (
        "policy_entity_id_confidence",
        "action_mask",
        "tick",
        "action",
        "success",
        "previous_action",
        "episode_start",
    )
)
FINAL_FIELDS = (
    "metadata_json",
    "terminal_tick",
    "winner",
    "learner_seat",
    "terminal_tower_hp",
    "initial_tower_hp",
    "outcome_wdl",
    "terminal_tower_margin",
    "decision_interval_ticks",
    "actual_terminal",
    "identity_confidence_definition",
    "schema_version",
    "margin_definition",
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    result = np.array(value, copy=True)
    if result.dtype.kind not in "bifu":
        raise ValueError("only numeric public arrays are allowed")
    return result


def validate_scalar_corpus(path, *, expected_metadata=None):
    """Read without pickle and verify schema, full decision sequence, and labels.

    expected_metadata pins the caller's independently frozen source and scenario;
    a self-consistent file alone cannot establish its simulation provenance.
    """
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(ROW_FIELDS + FINAL_FIELDS):
            raise ValueError("unexpected or missing corpus arrays")
        data = {key: archive[key] for key in archive.files}
    metadata = json.loads(str(data["metadata_json"].item()))
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("nonempty immutable metadata required")
    if expected_metadata is not None and _json(metadata) != _json(expected_metadata):
        raise ValueError("metadata differs from external authority")
    for key, value in data.items():
        if key in (
            "metadata_json",
            "margin_definition",
            "identity_confidence_definition",
        ):
            continue
        if value.dtype.kind not in "bifu" or not np.isfinite(value).all():
            raise ValueError(f"invalid numeric array: {key}")
    for key in (
        "schema_version",
        "terminal_tick",
        "winner",
        "learner_seat",
        "decision_interval_ticks",
        "actual_terminal",
        "terminal_tower_margin",
    ):
        if data[key].shape != ():
            raise ValueError(f"expected scalar: {key}")
    if data["schema_version"].item() != 1 or data["actual_terminal"].item() is not True:
        raise ValueError("requires completed version-1 game")
    for key in (
        "schema_version",
        "terminal_tick",
        "winner",
        "learner_seat",
        "decision_interval_ticks",
    ):
        if data[key].dtype.kind not in "iu":
            raise ValueError(f"integer required: {key}")
    seat, winner = int(data["learner_seat"]), int(data["winner"])
    if seat not in (0, 1) or winner not in (-1, 0, 1):
        raise ValueError("invalid seat or winner")
    ticks = data["tick"]
    interval = int(data["decision_interval_ticks"])
    n = len(ticks)
    if (
        interval < 1
        or n < 1
        or ticks.dtype.kind not in "iu"
        or not np.array_equal(ticks, np.arange(n) * interval)
    ):
        raise ValueError(
            "decision ticks must be complete contiguous boundaries from zero"
        )
    if not ticks[-1] < data["terminal_tick"].item() <= ticks[-1] + interval:
        raise ValueError("terminal tick does not follow final decision")
    for key in ROW_FIELDS:
        if data[key].ndim < 1 or data[key].shape[0] != n:
            raise ValueError(f"row count mismatch: {key}")
    ids, features, mask = (data[key] for key in ACTOR_FIELDS[:3])
    if ids.ndim != 2 or features.shape != (*ids.shape, 32) or mask.shape != ids.shape:
        raise ValueError("entity shapes mismatch")
    if ids.dtype.kind not in "iu" or (ids < 0).any() or mask.dtype != np.bool_:
        raise ValueError("invalid identity or mask dtype")
    if (ids[~mask] != 0).any() or (features[~mask] != 0).any():
        raise ValueError("padding must be zero")
    if data["hand_ids"].shape != (n, 5) or data["global_features"].shape != (n, 18):
        raise ValueError("expected five hand slots and eighteen public globals")
    for key in ACTOR_FIELDS[3:]:
        if data[key].ndim != 2:
            raise ValueError(f"invalid public field shape: {key}")
    for key in (
        "hand_ids",
        "opponent_history_ids",
        "opponent_seen_card_ids",
        "previous_action",
    ):
        if data[key].dtype.kind not in "iu" or (data[key] < 0).any():
            raise ValueError(f"invalid public integer field: {key}")
    if "policy_token_names" in metadata:
        policy_tokens = metadata["policy_token_names"]
        for token in np.unique(data["hand_ids"]):
            if token != 0 and (token <= 1 or token >= len(policy_tokens)
                              or not policy_tokens[int(token)].startswith("card_action:")):
                raise ValueError("hand contains unresolved or non-card public identity")
    if data["opponent_history_ids"].shape != data["opponent_history_ages"].shape:
        raise ValueError("history shapes differ")
    for key, field in zip(
        CONFIDENCE_FIELDS, ACTOR_FIELDS[:2] + ACTOR_FIELDS[3:5], strict=True
    ):
        conf = data[key]
        if conf.shape != data[field].shape or ((conf < 0) | (conf > 1)).any():
            raise ValueError(f"invalid confidence: {key}")
    if (
        data["identity_confidence_definition"].item()
        != "outcome_bound_visible_identity_with_separate_policy_confidence"
    ):
        raise ValueError("incorrect identity confidence definition")
    if not np.array_equal(data["entity_id_confidence"], mask.astype(float)):
        raise ValueError(
            "outcome identity confidence must match bound visible identities"
        )
    policy_conf = data["policy_entity_id_confidence"]
    if (
        policy_conf.shape != ids.shape
        or ((policy_conf < 0) | (policy_conf > 1)).any()
        or (policy_conf[~mask] != 0).any()
    ):
        raise ValueError("invalid policy identity confidence")
    has_outcome_vocab = "outcome_token_names" in metadata
    has_policy_vocab = "policy_token_names" in metadata
    pilot_metadata = metadata.get("schema") == "clasher.scalar-pilot-game-metadata.v1"
    if pilot_metadata or has_outcome_vocab or has_policy_vocab:
        if not (has_outcome_vocab and has_policy_vocab):
            raise ValueError(
                "pilot metadata requires both outcome and policy vocabularies"
            )
        outcome_vocab = metadata["outcome_token_names"]
        policy_vocab = metadata["policy_token_names"]
        for vocabulary in (outcome_vocab, policy_vocab):
            if (
                not isinstance(vocabulary, list)
                or len(vocabulary) < 2
                or any(not isinstance(token, str) or not token for token in vocabulary)
                or len(set(vocabulary)) != len(vocabulary)
            ):
                raise ValueError(
                    "vocabulary must contain distinct nonempty token names"
                )
        if outcome_vocab[: len(policy_vocab)] != policy_vocab:
            raise ValueError(
                "policy vocabulary must be an exact outcome vocabulary prefix"
            )
        if (ids >= len(outcome_vocab)).any() or (ids[mask] <= 1).any():
            raise ValueError(
                "visible identities must be bound in the outcome vocabulary"
            )
        extra = ids >= len(policy_vocab)
        expected_policy_conf = (mask & ~extra).astype(float)
        if not np.array_equal(policy_conf, expected_policy_conf):
            raise ValueError(
                "policy identity confidence contradicts declared vocabularies"
            )
        noncombat_effect = (
            ((features[..., 6] == 1) | (features[..., 7] == 1))
            & (features[..., 4] == 0)
            & (features[..., 5] == 0)
        )
        if (extra & ~noncombat_effect).any():
            raise ValueError(
                "extra identities require noncombat effect appearance rows"
            )
    actions, legal = data["action"], data["action_mask"]
    if (
        actions.shape != (n,)
        or actions.dtype.kind not in "iu"
        or legal.shape != (n, 2306)
        or legal.dtype != np.bool_
    ):
        raise ValueError("invalid action shapes or types")
    if (
        (actions < 0).any()
        or (actions >= legal.shape[1]).any()
        or not legal[np.arange(n), actions].all()
    ):
        raise ValueError("chosen action absent from public mask")
    if data["success"].shape != (n,) or data["success"].dtype != np.bool_:
        raise ValueError("success must preserve a boolean result for every row")
    starts = data["episode_start"]
    if (
        starts.dtype != np.bool_
        or starts.shape != (n,)
        or not starts[0]
        or starts[1:].any()
    ):
        raise ValueError("invalid episode start markers")
    if data["previous_action"].shape != (n,) or not np.array_equal(
        data["previous_action"][1:], actions[:-1]
    ):
        raise ValueError("previous action sequence mismatch")
    initial, terminal = data["initial_tower_hp"], data["terminal_tower_hp"]
    if (
        initial.shape != (2, 3)
        or terminal.shape != (2, 3)
        or (initial <= 0).any()
        or (terminal < 0).any()
        or (terminal > initial).any()
    ):
        raise ValueError("invalid tower health totals")
    outcome = [int(winner == seat), int(winner == -1), int(winner == 1 - seat)]
    if not np.array_equal(data["outcome_wdl"], outcome):
        raise ValueError("outcome label mismatch")
    margin = np.mean(terminal[seat] / initial[seat]) - np.mean(
        terminal[1 - seat] / initial[1 - seat]
    )
    if (
        data["margin_definition"].item()
        != "mean_three_tower_hp_fractions_own_minus_enemy"
    ):
        raise ValueError("incorrect margin definition")
    if not np.isclose(data["terminal_tower_margin"].item(), margin, rtol=0, atol=1e-12):
        raise ValueError("margin label mismatch")
    return {
        "rows": n,
        "rejected_card_actions": int(((actions < 2304) & ~data["success"]).sum()),
        "noop_false_results": int(((actions == 2304) & ~data["success"]).sum()),
        "failed_ability_actions": int(((actions == 2305) & ~data["success"]).sum()),
        "metadata": metadata,
        "outcome_wdl": outcome,
        "terminal_tower_margin": float(margin),
    }


class ScalarGameCorpusWriter:
    """Accumulate copied public rows, then atomically publish without overwrite."""

    def __init__(self, path, metadata, decision_interval_ticks=8):
        self.path = Path(path)
        self.metadata_json = _json(metadata)
        if not isinstance(metadata, dict) or not metadata:
            raise ValueError("nonempty immutable metadata required")
        self.interval = decision_interval_ticks
        self.rows = []
        self.finished = False
        self.seat = None

    def append(self, actor, inputs, *, learner_seat, tick, action, success):
        if self.finished:
            raise ValueError("writer is finished")
        if learner_seat not in (0, 1) or (
            self.seat is not None and self.seat != learner_seat
        ):
            raise ValueError("learner seat changed")
        if tick != len(self.rows) * self.interval:
            raise ValueError("noncontiguous decision")
        if any(
            getattr(inputs, name, None) is not None
            for name in (
                "critic_entity_ids",
                "critic_entity_features",
                "critic_entity_mask",
                "critic_card_ids",
                "critic_global_features",
            )
        ):
            raise ValueError("critic data prohibited at corpus boundary")
        row = {key: _array(getattr(actor, key)) for key in ACTOR_FIELDS}
        for key in CONFIDENCE_FIELDS + ("action_mask",):
            row[key] = _array(getattr(inputs, key)[learner_seat, 0])
        row["policy_entity_id_confidence"] = row["entity_id_confidence"]
        row["entity_id_confidence"] = row["entity_mask"].astype(np.float32)
        row.update(
            tick=_array(tick),
            action=_array(action),
            success=_array(success),
            previous_action=_array(inputs.previous_actions[learner_seat, 0]),
            episode_start=_array(inputs.episode_starts[learner_seat, 0]),
        )
        self.rows.append(row)
        self.seat = learner_seat

    def finish(
        self,
        *,
        terminal_tick,
        winner,
        learner_seat,
        terminal_tower_hp,
        initial_tower_hp,
        actual_terminal,
    ):
        if (
            self.finished
            or not self.rows
            or learner_seat != self.seat
            or actual_terminal is not True
        ):
            raise ValueError("cannot finish incomplete or mismatched game")
        winner = -1 if winner is None else winner
        initial, terminal = _array(initial_tower_hp), _array(terminal_tower_hp)
        if initial.shape != (2, 3) or terminal.shape != (2, 3) or (initial <= 0).any():
            raise ValueError("require positive initial HP for each of six towers")
        payload = {key: np.stack([row[key] for row in self.rows]) for key in ROW_FIELDS}
        payload.update(
            metadata_json=np.array(self.metadata_json),
            schema_version=np.array(1),
            identity_confidence_definition=np.array(
                "outcome_bound_visible_identity_with_separate_policy_confidence"
            ),
            terminal_tick=_array(terminal_tick),
            winner=_array(winner),
            learner_seat=_array(learner_seat),
            terminal_tower_hp=terminal,
            initial_tower_hp=initial,
            actual_terminal=np.array(True),
            decision_interval_ticks=_array(self.interval),
            outcome_wdl=np.array(
                [winner == learner_seat, winner == -1, winner == 1 - learner_seat],
                dtype=np.int8,
            ),
            margin_definition=np.array("mean_three_tower_hp_fractions_own_minus_enemy"),
            terminal_tower_margin=np.array(
                np.mean(terminal[learner_seat] / initial[learner_seat])
                - np.mean(terminal[1 - learner_seat] / initial[1 - learner_seat])
            ),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=".scalar-game-", suffix=".npz", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                np.savez_compressed(stream, **payload)
                stream.flush()
                os.fsync(stream.fileno())
            result = validate_scalar_corpus(
                temporary, expected_metadata=json.loads(self.metadata_json)
            )
            os.link(temporary, self.path)
            self.finished = True
            return result
        finally:
            os.unlink(temporary)
