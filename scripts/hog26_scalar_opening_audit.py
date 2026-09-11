"""Independent verifier for externally pinned scalar opening metadata.

No producer module is imported. Each retained deal is reconstructed with an
explicit Fisher-Yates loop, including deterministic duplicate-deal rejection.
Algorithm validity does not authorize any data role or budget.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass

_VERSION = "clasher.scalar-canonical-opening.v1"
_STREAMS = ("opening", "battle", "action-order", "opponent")
_AUTHORITY_FIELDS = frozenset({"version", "campaign_seed", "role", "deck_name",
                              "opponent_style", "relative_templates", "episodes", "canonical_names"})
_METADATA_FIELDS = frozenset({"authority", "authority_sha256", "scenarios", "pairing", "repeats", "rng_algorithm"})
_SCENARIO_FIELDS = frozenset({"scenario_id", "cluster_id", "ordinal", "relative_decks", "stream_seeds", "attempts"})
_PAIRING = "same-relative-deal-and-streams-across-seats"
_REPEATS = "same-scenario-and-cluster; determinism-only"
_RNG_ALGORITHM = "CPython random.Random MT19937; shuffle/randbelow version pinned externally"


class ScalarOpeningAuditError(ValueError):
    """Published opening metadata differs from its pinned authority or replay."""


def _require(condition, message):
    if not condition:
        raise ScalarOpeningAuditError(message)


def _keys(value, expected, where):
    _require(type(value) is dict and set(value) == expected, f"{where}: unexpected schema fields")


def _sha(value):
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value):
    return type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value) is not None


def _hex_digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _decks(value, inventory, where):
    _require(type(value) is list and len(value) == 2, f"{where}: expected two relative decks")
    for deck in value:
        _require(type(deck) is list and len(deck) == 8, f"{where}: expected eight cards per deck")
        _require(all(type(name) is str and name in inventory for name in deck),
                 f"{where}: card outside pinned canonical inventory")
        _require(len(set(deck)) == 8, f"{where}: repeated card in deck")


def _authority(value, where):
    _keys(value, _AUTHORITY_FIELDS, where)
    _require(value["version"] == _VERSION, f"{where}: unsupported opening version")
    _require(_decimal(value["campaign_seed"]), f"{where}: campaign seed must be canonical decimal text")
    for field in ("role", "deck_name", "opponent_style"):
        _require(type(value[field]) is str and value[field] != "", f"{where}: {field} must be explicit")
    _require(type(value["episodes"]) is int and 1 <= value["episodes"] <= 100000,
             f"{where}: invalid fixed episode budget")
    names = value["canonical_names"]
    _require(type(names) is list and bool(names)
             and all(type(name) is str and name != "" for name in names),
             f"{where}: canonical inventory must be a nonempty string list")
    _require(names == sorted(set(names)), f"{where}: canonical inventory must be sorted and unique")
    _decks(value["relative_templates"], set(names), where + "/relative_templates")


@dataclass(frozen=True)
class AuditedScalarOpening:
    scenario_id: str
    cluster_id: str
    ordinal: int
    relative_decks: tuple[tuple[str, ...], tuple[str, ...]]
    stream_seeds: tuple[tuple[str, int], ...]
    attempts: int

    def world_decks(self, learner_seat):
        _require(type(learner_seat) is int and learner_seat in (0, 1), "invalid learner seat")
        return self.relative_decks if learner_seat == 0 else self.relative_decks[::-1]


def audit_scalar_opening_metadata(metadata, *, expected_authority):
    """Validate against an external pin, then return independently rebuilt rows.

    Obtain expected_authority from the frozen protocol or other trusted setup,
    never by copying metadata['authority']. Python RNG runtime version remains
    an externally pinned execution prerequisite, as its metadata declares.
    """
    _authority(expected_authority, "expected_authority")
    _keys(metadata, _METADATA_FIELDS, "metadata")
    _authority(metadata["authority"], "authority")
    _require(metadata["authority"] == expected_authority, "authority differs from caller's external pin")
    pinned_digest = _sha(expected_authority)
    _require(_hex_digest(metadata["authority_sha256"])
             and metadata["authority_sha256"] == pinned_digest, "authority digest differs from external pin")
    _require(metadata["pairing"] == _PAIRING, "unsupported seat pairing contract")
    _require(metadata["repeats"] == _REPEATS, "unsupported repeat contract")
    _require(metadata["rng_algorithm"] == _RNG_ALGORITHM, "unsupported RNG contract")
    published = metadata["scenarios"]
    _require(type(published) is list and len(published) == expected_authority["episodes"],
             "scenario inventory differs from fixed episode budget")
    inventory = set(expected_authority["canonical_names"])
    retained_clusters = set()
    verified = []
    for ordinal, row in enumerate(published):
        label = f"scenario[{ordinal}]"
        _keys(row, _SCENARIO_FIELDS, label)
        _require(type(row["ordinal"]) is int and row["ordinal"] == ordinal, label + ": wrong ordinal")
        _require(type(row["attempts"]) is int and 1 <= row["attempts"] <= 1000,
                 label + ": invalid attempt count")
        _require(_hex_digest(row["scenario_id"]) and _hex_digest(row["cluster_id"]),
                 label + ": malformed identity digest")
        _decks(row["relative_decks"], inventory, label)
        _keys(row["stream_seeds"], set(_STREAMS), label + "/stream_seeds")
        _require(all(_decimal(seed) and len(seed) <= 78 and int(seed) < 2**256
                     for seed in row["stream_seeds"].values()), label + ": malformed stream seed")
        context = {key: value for key, value in expected_authority.items() if key != "episodes"}
        context["ordinal"] = ordinal
        streams = {name: str(int(_sha({"domain": "stream-seed", "stream": name,
                                      "scenario": context}), 16)) for name in _STREAMS}
        _require(row["stream_seeds"] == streams, label + ": stream derivation differs")
        for attempt in range(1000):
            seed_material = {"domain": "opening-attempt", "version": _VERSION,
                             "opening_seed": streams["opening"], "attempt": attempt}
            rng = random.Random(int(_sha(seed_material), 16))
            rebuilt = []
            for template in expected_authority["relative_templates"]:
                deck = list(template)
                for last in range(7, 0, -1):
                    other = rng.randrange(last + 1)
                    deck[last], deck[other] = deck[other], deck[last]
                rebuilt.append(deck)
            cluster = _sha({"domain": "relative-deal-cluster", "version": _VERSION,
                            "deck_name": expected_authority["deck_name"],
                            "opponent_style": expected_authority["opponent_style"],
                            "relative_decks": rebuilt})
            if cluster not in retained_clusters:
                retained_clusters.add(cluster)
                break
        else:
            raise ScalarOpeningAuditError(label + ": duplicate-deal retry budget exhausted")
        identity = _sha({"domain": "scenario-identity", "scenario": context,
                         "relative_decks": rebuilt,
                         "stream_seeds": [(name, streams[name]) for name in _STREAMS],
                         "attempt": attempt})
        _require(row["relative_decks"] == rebuilt, label + ": ordered deals differ")
        _require(row["attempts"] == attempt + 1, label + ": retained attempt differs")
        _require(row["cluster_id"] == cluster, label + ": cluster identity differs")
        _require(row["scenario_id"] == identity, label + ": scenario identity differs")
        verified.append(AuditedScalarOpening(identity, cluster, ordinal,
            tuple(tuple(deck) for deck in rebuilt), tuple((name, int(streams[name])) for name in _STREAMS),
            attempt + 1))
    return tuple(verified)
