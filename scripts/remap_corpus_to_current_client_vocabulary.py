from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import numpy as np

from clasher.rl.imitation import load_corpus
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256

ENTITY_NAMESPACES = (
    "troop_body",
    "building_body",
    "projectile",
    "area_effect",
    "card_action",
)
RUNTIME_NAMESPACES = frozenset((*ENTITY_NAMESPACES[:-1], "tower"))


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if payload.get("schema") != "clasher.current_client.youtube_stable_vocabulary.v1":
        raise ValueError("unsupported current-client vocabulary manifest")
    return payload


class TypedVocabularyRemapper:
    def __init__(self, manifest: dict[str, Any], old_tokens: tuple[str, ...]) -> None:
        eligible = [
            row for row in manifest["entries"] if row["policy_token_eligible"]
        ]
        eligible.sort(key=lambda row: int(row["actor_token_id"]))
        expected = list(range(2, 2 + len(eligible)))
        actual = [int(row["actor_token_id"]) for row in eligible]
        if actual != expected:
            raise ValueError("actor token IDs are not contiguous after reserved IDs")
        self.token_names = (
            "<pad>",
            "<unknown>",
            *(str(row["stable_key"]) for row in eligible),
        )
        self.old_tokens = old_tokens
        self.by_key = {str(row["stable_key"]): row for row in eligible}
        self.by_exact = {
            (str(row["namespace"]), str(row["canonical_name"])): row
            for row in eligible
        }
        self.aliases = {
            (str(row["context"]), str(row["normalized_label"])): str(
                row["target_stable_key"]
            )
            for row in manifest["aliases"]
        }
        self.new_id = {
            name: index for index, name in enumerate(self.token_names)
        }
        self.reason_counts: Counter[str] = Counter()
        self.entity_reason: dict[tuple[int, int], str] = {}

    def _card_key(self, name: str) -> str | None:
        alias = self.aliases.get(("card_action", _normalize(name)))
        if alias in self.by_key:
            return alias
        direct = f"card_action:{name}"
        return direct if direct in self.by_key else None

    def _entity_key(self, name: str, namespace: str) -> tuple[str | None, str]:
        if name in {"Tower", "KingTower"}:
            return f"tower:{name}", "tower_source_identity"
        direct = self.by_exact.get((namespace, name))
        if direct is not None:
            return str(direct["stable_key"]), "exact_role_identity"
        card_key = self._card_key(name)
        owned: list[dict[str, Any]] = []
        if card_key is not None:
            root = str(self.by_key[card_key]["canonical_name"])
            owned = [
                row
                for row in self.by_key.values()
                if row["namespace"] == namespace
                and root in row.get("owner_root_cards", ())
                and "base" in row.get("variant_kinds", ())
            ]
            if len(owned) == 1:
                return str(owned[0]["stable_key"]), "unique_base_form_from_owner"
        exact_runtime = [
            row
            for (candidate_namespace, candidate_name), row in self.by_exact.items()
            if candidate_name == name and candidate_namespace in RUNTIME_NAMESPACES
        ]
        if len(exact_runtime) == 1:
            return str(exact_runtime[0]["stable_key"]), "exact_cross_kind_identity"
        if card_key is None:
            return None, "unresolved_identity"
        # The old corpus recorded only the source card for many spawned
        # projectiles/effects. Preserve that known identity instead of guessing
        # among multiple visible forms. Entity-kind features still encode role.
        return card_key, f"source_card_fallback_{len(owned)}_forms"

    def card_table(self) -> np.ndarray:
        result = np.ones((len(self.old_tokens),), dtype=np.int64)
        result[0] = 0
        for old_id, name in enumerate(self.old_tokens[2:], start=2):
            key = self._card_key(name)
            if key is None:
                self.reason_counts["card_unresolved"] += 1
                continue
            result[old_id] = self.new_id[key]
            self.reason_counts["card_resolved"] += 1
        return result

    def entity_tables(self) -> np.ndarray:
        tables = np.ones(
            (len(ENTITY_NAMESPACES), len(self.old_tokens)), dtype=np.int64
        )
        tables[:, 0] = 0
        for kind, namespace in enumerate(ENTITY_NAMESPACES):
            for old_id, name in enumerate(self.old_tokens[2:], start=2):
                key, reason = self._entity_key(name, namespace)
                self.entity_reason[(kind, old_id)] = reason
                self.reason_counts[reason] += 1
                if key is not None:
                    tables[kind, old_id] = self.new_id[key]
        return tables


def _remap_entity_ids(
    ids: np.ndarray,
    features: np.ndarray,
    mask: np.ndarray,
    tables: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    if ids.shape != mask.shape or features.shape[:2] != ids.shape:
        raise ValueError("entity ID, feature, and mask shapes do not align")
    kinds = features[..., 4:9]
    valid = mask & (ids > 1)
    if bool((kinds[valid].sum(axis=-1) != 1.0).any()):
        raise ValueError("visible non-reserved entities require one exact kind")
    kind_ids = kinds.argmax(axis=-1)
    remapped = tables[kind_ids, ids]
    remapped = np.where(ids == 0, 0, remapped).astype(np.int64, copy=False)
    return remapped, {
        "visible_rows": int(valid.sum()),
        "visible_rows_unknown_after_remap": int((valid & (remapped == 1)).sum()),
        "nonvisible_nonzero_rows": int(((~mask) & (ids > 0)).sum()),
    }


def _used_entity_reason_counts(
    ids: np.ndarray,
    features: np.ndarray,
    mask: np.ndarray,
    mapper: TypedVocabularyRemapper,
) -> dict[str, int]:
    valid = mask & (ids > 1)
    kinds = features[..., 4:9].argmax(axis=-1)
    pairs = np.stack([kinds[valid], ids[valid]], axis=-1)
    unique, counts = np.unique(pairs, axis=0, return_counts=True)
    result: Counter[str] = Counter()
    for (kind, old_id), count in zip(unique.tolist(), counts.tolist(), strict=True):
        result[mapper.entity_reason[(int(kind), int(old_id))]] += int(count)
    return dict(sorted(result.items()))


def _remap_card_array(values: np.ndarray, table: np.ndarray) -> np.ndarray:
    if not np.issubdtype(values.dtype, np.integer):
        raise ValueError("card token arrays must be integral")
    if values.size and (int(values.min()) < 0 or int(values.max()) >= len(table)):
        raise ValueError("card token array contains an out-of-vocabulary ID")
    result: np.ndarray = table[values]
    return result


def remap(
    *,
    corpus_path: Path,
    sidecar_path: Path,
    vocabulary_path: Path,
    output_corpus: Path,
    output_sidecar: Path,
    output_report: Path,
) -> dict[str, Any]:
    metadata, base = load_corpus(corpus_path)
    manifest = _load_manifest(vocabulary_path)
    mapper = TypedVocabularyRemapper(manifest, tuple(metadata.token_names))
    card_table = mapper.card_table()
    entity_tables = mapper.entity_tables()

    base_output = {name: value.copy() for name, value in base.items()}
    base_output["entity_ids"], base_entity_stats = _remap_entity_ids(
        base["entity_ids"],
        base["entity_features"],
        base["entity_mask"],
        entity_tables,
    )
    base_entity_stats["mapping_reason_rows"] = _used_entity_reason_counts(
        base["entity_ids"], base["entity_features"], base["entity_mask"], mapper
    )
    base_output["hand_ids"] = _remap_card_array(base["hand_ids"], card_table)
    typed_metadata = replace(metadata, token_names=mapper.token_names)
    base_output["metadata_json"] = np.asarray(typed_metadata.to_json())

    with np.load(sidecar_path, allow_pickle=False) as stored:
        sidecar = {name: stored[name].copy() for name in stored.files}
    sidecar_output = dict(sidecar)
    sidecar_output["entity_ids"], sidecar_entity_stats = _remap_entity_ids(
        sidecar["entity_ids"],
        sidecar["entity_features"],
        sidecar["entity_mask"],
        entity_tables,
    )
    sidecar_entity_stats["mapping_reason_rows"] = _used_entity_reason_counts(
        sidecar["entity_ids"],
        sidecar["entity_features"],
        sidecar["entity_mask"],
        mapper,
    )
    for name in ("hand_ids", "opponent_history_ids", "opponent_seen_card_ids"):
        if name in sidecar:
            sidecar_output[name] = _remap_card_array(sidecar[name], card_table)

    if base_entity_stats["visible_rows_unknown_after_remap"]:
        raise ValueError("base corpus retains unknown visible entities after remap")
    if sidecar_entity_stats["visible_rows_unknown_after_remap"]:
        raise ValueError("public sidecar retains unknown visible entities after remap")
    for name, values in (
        ("base hand", base_output["hand_ids"]),
        ("sidecar hand", sidecar_output["hand_ids"]),
    ):
        original = base["hand_ids"] if name == "base hand" else sidecar["hand_ids"]
        if bool(((original > 1) & (values == 1)).any()):
            raise ValueError(f"{name} retains unknown non-reserved cards after remap")

    output_corpus.parent.mkdir(parents=True, exist_ok=True)
    output_sidecar.parent.mkdir(parents=True, exist_ok=True)
    atomic_save_npz(output_corpus, base_output)
    atomic_save_npz(output_sidecar, sidecar_output)
    report = {
        "schema": "clasher.current_client.corpus_vocabulary_remap.v1",
        "source_corpus": str(corpus_path.resolve()),
        "source_corpus_sha256": file_sha256(corpus_path),
        "source_sidecar": str(sidecar_path.resolve()),
        "source_sidecar_sha256": file_sha256(sidecar_path),
        "vocabulary_manifest": str(vocabulary_path.resolve()),
        "vocabulary_manifest_sha256": file_sha256(vocabulary_path),
        "old_token_count": len(metadata.token_names),
        "new_token_count": len(mapper.token_names),
        "new_token_names_sha256": hashlib.sha256(
            "\0".join(mapper.token_names).encode("utf-8")
        ).hexdigest(),
        "mapping_reason_counts": dict(sorted(mapper.reason_counts.items())),
        "base_entity_stats": base_entity_stats,
        "sidecar_entity_stats": sidecar_entity_stats,
        "output_corpus": str(output_corpus.resolve()),
        "output_corpus_sha256": file_sha256(output_corpus),
        "output_sidecar": str(output_sidecar.resolve()),
        "output_sidecar_sha256": file_sha256(output_sidecar),
    }
    atomic_write_json(output_report, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remap a causal corpus into the frozen current-client typed vocabulary"
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--output-corpus", type=Path, required=True)
    parser.add_argument("--output-sidecar", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = remap(
        corpus_path=args.corpus.resolve(),
        sidecar_path=args.sidecar.resolve(),
        vocabulary_path=args.vocabulary.resolve(),
        output_corpus=args.output_corpus.resolve(),
        output_sidecar=args.output_sidecar.resolve(),
        output_report=args.output_report.resolve(),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
