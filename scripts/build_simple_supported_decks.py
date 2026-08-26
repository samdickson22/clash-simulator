#!/usr/bin/env python3
"""Build the fail-closed public deck pool for the practical tensor Gym.

The source manifest is treated as read-only.  Every candidate must be an
exactly eight-card public deck, and a candidate is copied to the output only
when the standard simple-Gym setup marks all eight roots training-supported.
The output locks both the exact source bytes and the canonical public-card
support profile so ``--check`` rejects source, compiler, or mechanic drift.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, NoReturn

from clasher.data import CardDataLoader
from clasher.rl.deck_pool import unique_cards_from_decks
from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

SCHEMA_VERSION = 1
SUPPORT_PROFILE_VERSION = 1
CONTRACT_NAME = "clasher.simple_gym_supported_decks"
DECK_SIZE = 8
MAX_CANDIDATE_DECKS = 256
MAX_SOURCE_BYTES = 1_048_576
DEFAULT_DECKS_PATH = Path("decks.json")
DEFAULT_OUTPUT_PATH = Path("training_decks/simple_gym_supported_v1.json")


class DeckManifestError(ValueError):
    """Raised when an input or generated deck manifest violates its contract."""


class ArtifactDriftError(RuntimeError):
    """Raised when a checked artifact differs from the current compiler result."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeckManifestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json_object(path: Path, *, max_bytes: int) -> tuple[dict[str, Any], bytes]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DeckManifestError(f"cannot stat manifest {path}: {exc}") from exc
    if size > max_bytes:
        raise DeckManifestError(
            f"manifest exceeds {max_bytes} byte input bound: {size}"
        )
    try:
        raw = path.read_bytes()
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except DeckManifestError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeckManifestError(f"cannot read JSON manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeckManifestError("manifest root must be a JSON object")
    return payload, raw


def _validated_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_decks = payload.get("decks")
    if not isinstance(raw_decks, list) or not raw_decks:
        raise DeckManifestError("manifest.decks must be a non-empty list")
    if len(raw_decks) > MAX_CANDIDATE_DECKS:
        raise DeckManifestError(
            f"manifest contains more than {MAX_CANDIDATE_DECKS} candidate decks"
        )

    candidates: list[dict[str, Any]] = []
    for index, raw_deck in enumerate(raw_decks):
        if not isinstance(raw_deck, dict):
            raise DeckManifestError(f"decks[{index}] must be a JSON object")
        cards = raw_deck.get("cards")
        if not isinstance(cards, list) or len(cards) != DECK_SIZE:
            raise DeckManifestError(
                f"decks[{index}].cards must contain exactly {DECK_SIZE} cards"
            )
        if any(not isinstance(card, str) or not card for card in cards):
            raise DeckManifestError(
                f"decks[{index}].cards must contain non-empty strings"
            )
        if len(set(cards)) != DECK_SIZE:
            raise DeckManifestError(f"decks[{index}].cards must be unique")
        candidates.append(raw_deck)
    return candidates


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_artifact(
    decks_path: str | Path = DEFAULT_DECKS_PATH,
    *,
    device: str = "cpu",
    source_label: str | None = None,
) -> dict[str, Any]:
    """Compile and return the deterministic supported-deck artifact."""

    source_path = Path(decks_path)
    payload, source_bytes = _read_json_object(
        source_path,
        max_bytes=MAX_SOURCE_BYTES,
    )
    candidates = _validated_candidates(payload)
    candidate_cards = [list(deck["cards"]) for deck in candidates]
    public_names = unique_cards_from_decks(candidate_cards)
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        public_names,
        device=device,
        canonical_lane_globals=True,
    )

    public_support: list[dict[str, Any]] = []
    for name in setup.public_root_names:
        card_id = setup.cards.name_to_id[name]
        public_support.append(
            {
                "name": name,
                "training_supported": bool(setup.supported_public_root_mask[card_id]),
            }
        )
    profile_payload = {
        "version": SUPPORT_PROFILE_VERSION,
        "compiler": ("compile_standard_simple_setup/FastSpawnBlueprintCatalog"),
        "canonical_lane_globals": True,
        "public_cards": public_support,
    }
    profile_hash = _sha256(_canonical_bytes(profile_payload))
    supported_names = {
        row["name"] for row in public_support if row["training_supported"]
    }

    supported_decks: list[dict[str, Any]] = []
    for deck in candidates:
        cards = deck["cards"]
        if all(card in supported_names for card in cards):
            # Preserve every source metadata field and the exact source order.
            supported_decks.append(copy.deepcopy(deck))

    supported_cards = [
        row["name"] for row in public_support if row["training_supported"]
    ]
    unsupported_cards = [
        row["name"] for row in public_support if not row["training_supported"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": {
            "name": CONTRACT_NAME,
            "version": SCHEMA_VERSION,
            "deck_size": DECK_SIZE,
            "canonical_lane_globals": True,
            "public_action_mask_contract_version": (PUBLIC_ACTION_MASK_CONTRACT_V2),
        },
        "source": {
            "path": source_label if source_label is not None else str(source_path),
            "sha256": _sha256(source_bytes),
        },
        "counts": {
            "candidate_decks": len(candidates),
            "supported_decks": len(supported_decks),
            "rejected_decks": len(candidates) - len(supported_decks),
            "public_cards": len(public_support),
            "supported_public_cards": len(supported_cards),
            "unsupported_public_cards": len(unsupported_cards),
        },
        "support_profile": {
            "version": SUPPORT_PROFILE_VERSION,
            "sha256": profile_hash,
            "supported_public_cards": supported_cards,
            "unsupported_public_cards": unsupported_cards,
        },
        "decks": supported_decks,
    }


def _contract_error(message: str) -> NoReturn:
    raise ArtifactDriftError(f"supported-deck contract drift: {message}")


def validate_artifact_contract(payload: Any) -> None:
    """Reject an artifact that claims a different training contract."""

    if not isinstance(payload, dict):
        _contract_error("artifact root is not an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        _contract_error("schema_version changed")
    contract = payload.get("contract")
    if not isinstance(contract, dict):
        _contract_error("contract object missing")
    expected = {
        "name": CONTRACT_NAME,
        "version": SCHEMA_VERSION,
        "deck_size": DECK_SIZE,
        "canonical_lane_globals": True,
        "public_action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_V2,
    }
    if contract != expected:
        _contract_error(f"expected {expected!r}, got {contract!r}")


def check_artifact(path: str | Path, expected: dict[str, Any]) -> None:
    """Require ``path`` to match the freshly compiled artifact exactly."""

    artifact_path = Path(path)
    try:
        current, _ = _read_json_object(
            artifact_path,
            max_bytes=MAX_SOURCE_BYTES,
        )
    except DeckManifestError as exc:
        raise ArtifactDriftError(str(exc)) from exc
    validate_artifact_contract(current)
    if current != expected:
        raise ArtifactDriftError(
            "supported-deck artifact is stale; regenerate it with "
            "scripts/build_simple_supported_decks.py"
        )


def write_artifact(path: str | Path, artifact: dict[str, Any]) -> None:
    """Write a same-contract artifact without mutating the source manifest."""

    output_path = Path(path)
    if output_path.exists():
        try:
            current, _ = _read_json_object(
                output_path,
                max_bytes=MAX_SOURCE_BYTES,
            )
        except DeckManifestError as exc:
            raise ArtifactDriftError(str(exc)) from exc
        validate_artifact_contract(current)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decks-path", type=Path, default=DEFAULT_DECKS_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless the committed artifact exactly matches current support",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    artifact = build_artifact(
        args.decks_path,
        device=args.device,
        source_label=str(args.decks_path),
    )
    if args.check:
        check_artifact(args.out, artifact)
    else:
        write_artifact(args.out, artifact)
    print(json.dumps(artifact["counts"], sort_keys=True))
    print(f"support_profile_sha256={artifact['support_profile']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
