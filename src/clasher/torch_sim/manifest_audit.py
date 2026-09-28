"""Aggregate exhaustive manifest results without weakening parity claims.

The differential harness owns fixture construction and oracle comparison. This
module only classifies and hashes those results so fallback-only rows remain
visible and can never be reported as tensor parity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .differential import (
    BattleExternalSurfaces,
    CoverageRequirement,
    build_interaction_fixture,
    enabled_cards,
    interaction_manifest_count,
    iter_interaction_manifests,
    verify_battle_fixture,
)


@dataclass(frozen=True)
class ManifestAuditRow:
    ordinal: int
    player0_card: str
    player1_card: str
    execution: str
    parity_passed: bool
    advanced_ticks: int
    tensor_ticks: int
    python_ticks: int
    unsupported_fallbacks: int
    divergence: str | None

    @property
    def tensor_parity_passed(self) -> bool:
        return self.execution == "tensor" and self.parity_passed


@dataclass(frozen=True)
class EnabledOneVsOneAudit:
    decks_path: str
    decks_sha256: str
    deck_count: int
    card_slots: int
    enabled_cards: tuple[str, ...]
    ticks: int
    rows: tuple[ManifestAuditRow, ...]

    def matrix_sha256(self) -> str:
        encoded = json.dumps(
            [asdict(row) for row in self.rows],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def summary(self) -> dict[str, Any]:
        tensor_rows = [row for row in self.rows if row.tensor_parity_passed]
        fallback_rows = [row for row in self.rows if row.execution == "fallback"]
        split_rows = [row for row in self.rows if row.execution == "split"]
        error_rows = [row for row in self.rows if row.execution == "error"]
        mismatches = [row for row in self.rows if not row.parity_passed]
        diagonal_tensor_cards = sorted(
            row.player0_card
            for row in tensor_rows
            if row.player0_card == row.player1_card
        )
        return {
            "decks_path": self.decks_path,
            "decks_sha256": self.decks_sha256,
            "deck_count": self.deck_count,
            "card_slots": self.card_slots,
            "enabled_card_count": len(self.enabled_cards),
            "ordered_pair_count": len(self.rows),
            "ticks_per_pair": self.ticks,
            "scope": "post-deployment tick window",
            "tensor_executed_exact_pairs": len(tensor_rows),
            "counted_fallback_pairs": len(fallback_rows),
            "split_execution_pairs": len(split_rows),
            "execution_error_pairs": len(error_rows),
            "oracle_mismatches": len(mismatches),
            "tensor_diagonal_card_count": len(diagonal_tensor_cards),
            "tensor_diagonal_cards": diagonal_tensor_cards,
            "matrix_sha256": self.matrix_sha256(),
            "fallback_is_tensor_parity": False,
        }


def _classify_execution(
    *,
    advanced_ticks: int,
    tensor_ticks: int,
    python_ticks: int,
    unsupported_fallbacks: int,
) -> str:
    if (
        tensor_ticks == advanced_ticks
        and python_ticks == 0
        and unsupported_fallbacks == 0
    ):
        return "tensor"
    if (
        tensor_ticks == 0
        and python_ticks == advanced_ticks
        and unsupported_fallbacks == 1
    ):
        return "fallback"
    if tensor_ticks > 0 and python_ticks > 0 and unsupported_fallbacks > 0:
        return "split"
    return "error"


def audit_enabled_one_vs_one(
    *,
    decks_path: str | Path = "decks.json",
    ticks: int = 1,
    device: str = "cpu",
    compare_structured_observations: bool = True,
) -> EnabledOneVsOneAudit:
    """Run every ordered enabled 1v1 fixture for an explicit tick window.

    This is deployment-window coverage, not complete interaction or episode
    parity. The returned summary always publishes the requested tick count.
    """

    requested = int(ticks)
    if requested <= 0:
        raise ValueError("ticks must be positive")
    path = Path(decks_path)
    raw = path.read_bytes()
    payload = json.loads(raw)
    decks = payload.get("decks")
    if not isinstance(decks, list):
        raise TypeError("deck manifest must contain a decks list")
    card_slots = sum(
        len(deck.get("cards", ())) for deck in decks if isinstance(deck, dict)
    )
    cards = enabled_cards(path)
    expected_rows = interaction_manifest_count(len(cards), 1)
    surfaces = BattleExternalSurfaces(
        decks_path=path,
        compare_structured_observations=compare_structured_observations,
    )
    rows: list[ManifestAuditRow] = []
    for manifest in iter_interaction_manifests(cards, cards_per_owner=1):
        seed = 10_000 + manifest.ordinal
        report = verify_battle_fixture(
            build_interaction_fixture(manifest, seed=seed),
            seed=seed,
            name=manifest.name,
            ticks=requested,
            backend="pytorch",
            device=device,
            decks_path=path,
            compare_structured_observations=compare_structured_observations,
            coverage_requirement=CoverageRequirement(),
            external_surfaces=surfaces,
        )
        coverage = report.coverage
        execution = _classify_execution(
            advanced_ticks=report.advanced_ticks,
            tensor_ticks=coverage.tensor_ticks,
            python_ticks=coverage.python_ticks,
            unsupported_fallbacks=coverage.unsupported_fallbacks,
        )
        rows.append(
            ManifestAuditRow(
                ordinal=manifest.ordinal,
                player0_card=manifest.player0_cards[0],
                player1_card=manifest.player1_cards[0],
                execution=execution,
                parity_passed=report.parity_passed,
                advanced_ticks=report.advanced_ticks,
                tensor_ticks=coverage.tensor_ticks,
                python_ticks=coverage.python_ticks,
                unsupported_fallbacks=coverage.unsupported_fallbacks,
                divergence=None
                if report.divergence is None
                else str(report.divergence),
            )
        )
    if len(rows) != expected_rows:
        raise AssertionError(
            f"manifest yielded {len(rows)} rows, expected {expected_rows}"
        )
    return EnabledOneVsOneAudit(
        decks_path=str(path),
        decks_sha256=hashlib.sha256(raw).hexdigest(),
        deck_count=len(decks),
        card_slots=card_slots,
        enabled_cards=cards,
        ticks=requested,
        rows=tuple(rows),
    )
