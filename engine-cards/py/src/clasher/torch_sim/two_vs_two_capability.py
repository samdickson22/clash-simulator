"""Truthful capability inventory for true team 2v2 simulation.

The repository's current Python oracle models two owners, one per opposing
side.  A fixture that deploys two cards for each of those owners is useful
interaction coverage, but it is not a four-controller team 2v2 match.  This
module records that boundary for every enabled serialized card so the absence
of a 2v2 oracle cannot accidentally be reported as PyTorch parity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.rl.action_space import DiscreteTileActionSpace

from .state import TensorBattleState

TRUE_TWO_VS_TWO_BLOCKER = (
    "unsupported: the Python oracle has two opposing owner slots and no "
    "controller-to-team identity, so it cannot represent a four-controller "
    "team 2v2 match"
)


@dataclass(frozen=True)
class EnabledTwoVsTwoManifest:
    """Canonical enabled-card inventory used by the capability matrix."""

    path: Path
    sha256: str
    deck_count: int
    card_slots: int
    card_names: tuple[str, ...]


@dataclass(frozen=True)
class EnabledTwoVsTwoCapabilityRow:
    """One enabled card's eligibility for a true team 2v2 parity claim."""

    card_name: str
    serialized_kind: str
    serialized_mechanic_count: int
    serialized_effect_count: int
    python_oracle_supported: bool
    tensor_backend_supported: bool
    blocker: str


@dataclass(frozen=True)
class EnabledTwoVsTwoCapabilityReport:
    """Structural oracle evidence plus an exhaustive enabled-card matrix."""

    manifest: EnabledTwoVsTwoManifest
    python_owner_ids: tuple[int, ...]
    action_owner_ids: tuple[int, ...]
    python_has_team_identity: bool
    tensor_player_axis: int
    true_two_vs_two_supported: bool
    rows: tuple[EnabledTwoVsTwoCapabilityRow, ...]

    def matrix_sha256(self) -> str:
        encoded = json.dumps(
            [asdict(row) for row in self.rows],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def summary(self) -> dict[str, Any]:
        return {
            "manifest_path": str(self.manifest.path),
            "manifest_sha256": self.manifest.sha256,
            "enabled_card_count": len(self.manifest.card_names),
            "matrix_row_count": len(self.rows),
            "matrix_sha256": self.matrix_sha256(),
            "python_owner_ids": list(self.python_owner_ids),
            "action_owner_ids": list(self.action_owner_ids),
            "python_has_team_identity": self.python_has_team_identity,
            "tensor_player_axis": self.tensor_player_axis,
            "true_two_vs_two_supported": self.true_two_vs_two_supported,
            "python_oracle_supported_rows": sum(
                row.python_oracle_supported for row in self.rows
            ),
            "tensor_backend_supported_rows": sum(
                row.tensor_backend_supported for row in self.rows
            ),
            "blocker": TRUE_TWO_VS_TWO_BLOCKER,
            "two_cards_per_owner_is_true_two_vs_two": False,
        }


def audit_enabled_true_two_vs_two_capability(
    *,
    manifest_path: str | Path = "decks.json",
) -> EnabledTwoVsTwoCapabilityReport:
    """Inventory true 2v2 support without manufacturing a nonexistent oracle.

    Card rows come from the serialized enabled manifest.  Structural facts are
    read from live Python and tensor state rather than inferred from card names.
    Every row remains unsupported until the Python oracle itself has four
    controller identities, explicit controller-to-team ownership, and the
    tensor backend exposes the corresponding player/controller axis.
    """

    loader = CardDataLoader()
    path = Path(manifest_path)
    raw = path.read_bytes()
    payload = json.loads(raw)
    decks = payload.get("decks")
    if not isinstance(decks, list):
        raise TypeError("enabled manifest must contain a decks list")
    definitions = loader.load_card_definitions()
    resolved: list[str] = []
    for deck_index, deck in enumerate(decks):
        cards = deck.get("cards") if isinstance(deck, dict) else None
        if not isinstance(cards, list):
            raise TypeError(f"deck {deck_index} must contain a cards list")
        for raw_name in cards:
            if not isinstance(raw_name, str):
                raise TypeError(f"deck {deck_index} contains a non-string card")
            name = resolve_card_name(raw_name, definitions)
            if name not in definitions:
                raise ValueError(
                    f"enabled card has no serialized definition: {raw_name}"
                )
            resolved.append(name)
    manifest = EnabledTwoVsTwoManifest(
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        deck_count=len(decks),
        card_slots=len(resolved),
        card_names=tuple(sorted(set(resolved))),
    )
    battle = BattleState(card_loader=loader)
    python_owner_ids = tuple(player.player_id for player in battle.players)
    action_owner_ids = tuple(DiscreteTileActionSpace()._positions_by_player)
    player_fields = {name for player in battle.players for name in vars(player)}
    python_has_team_identity = bool({"team", "team_id", "teammate_id"} & player_fields)
    tensor_state = TensorBattleState.from_battles([battle])
    tensor_player_axis = int(tensor_state.elixir.shape[1])

    # These facts characterize the current oracle.  Should a real 2v2 model be
    # added, fail loudly instead of retaining a stale unsupported inventory.
    if (
        python_owner_ids != (0, 1)
        or action_owner_ids != (0, 1)
        or python_has_team_identity
        or tensor_player_axis != 2
    ):
        raise RuntimeError(
            "battle ownership structure changed; re-audit true 2v2 support "
            "before publishing a capability matrix"
        )

    rows = tuple(
        EnabledTwoVsTwoCapabilityRow(
            card_name=name,
            serialized_kind=definitions[name].kind,
            serialized_mechanic_count=len(definitions[name].mechanics),
            serialized_effect_count=len(definitions[name].effects),
            python_oracle_supported=False,
            tensor_backend_supported=False,
            blocker=TRUE_TWO_VS_TWO_BLOCKER,
        )
        for name in manifest.card_names
    )
    return EnabledTwoVsTwoCapabilityReport(
        manifest=manifest,
        python_owner_ids=python_owner_ids,
        action_owner_ids=action_owner_ids,
        python_has_team_identity=python_has_team_identity,
        tensor_player_axis=tensor_player_axis,
        true_two_vs_two_supported=False,
        rows=rows,
    )
