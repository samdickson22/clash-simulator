"""Tier B targeted probes of suspected exploits and problematic patterns.

Probes cover the human-found bug classes in the external review's merge plan
(item 10): lane choice, building pull, body block, charge blocking, Log
pushback and shields. A probe is a *selected* root: a public pattern predicate
must hold and the frozen policy's candidates are drawn under a probe-specific
rule. Probes reuse the Tier B regret/floor/bias arithmetic but are reported
separately; they can block promotion and never support a population rate.

Predicates read only public packet fields (visible token identity, canonical
position and side). They never consult hidden state or outcomes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

import numpy as np
from pydantic import Field

from .public_observation import ConfidenceAwareActorObservation
from .training_readiness_v2 import ROLES, Candidate, Record

WAIT = 2304


class RankedPlay(Protocol):
    @property
    def action_id(self) -> int: ...

    @property
    def score(self) -> float: ...

MELEE_GROUND = frozenset(
    {"Knight", "Prince", "DarkPrince", "Giant", "HogRider", "Goblin", "Goblins",
     "Skeleton", "Skeletons", "IceGolem", "IceGolemite"}
)
GROUND_TROOPS = MELEE_GROUND | {"Archer", "Archers", "Musketeer"}
BUILDING_TARGETERS = frozenset({"Giant", "HogRider"})
CHARGERS = frozenset({"Prince", "DarkPrince"})
SHIELDED = frozenset({"DarkPrince"})


@dataclass(frozen=True)
class ProbeRule:
    """Public predicate plus candidate rule for one probe kind."""

    focal_cards: frozenset[str]
    threat_tokens: frozenset[str]
    # Maximum canonical y (tiles, own side is low y) of a qualifying threat.
    threat_max_y: float
    displaced: Literal["opposite_lane", "two_tiles"]
    # Lane choice requires no enemy troop already on the owner's half.
    quiet_own_half: bool = False
    description: str = ""


PROBE_RULES: Final[dict[str, ProbeRule]] = {
    "lane_choice": ProbeRule(
        focal_cards=frozenset({"Giant", "HogRider", "Prince", "DarkPrince", "Knight",
                               "Musketeer", "Archers", "IceGolem", "Goblins"}),
        threat_tokens=frozenset(),
        threat_max_y=32.0,
        displaced="opposite_lane",
        quiet_own_half=True,
        description="same troop in the opposite lane while the owner's half is quiet",
    ),
    "building_pull": ProbeRule(
        focal_cards=frozenset({"Cannon", "Tesla"}),
        threat_tokens=BUILDING_TARGETERS,
        threat_max_y=19.0,
        displaced="two_tiles",
        description="defensive building against a visible building-targeting troop",
    ),
    "body_block": ProbeRule(
        focal_cards=frozenset({"Knight", "IceGolem"}),
        threat_tokens=MELEE_GROUND,
        threat_max_y=17.0,
        displaced="two_tiles",
        description="tank placement in the path of a visible melee ground troop",
    ),
    "charge_blocking": ProbeRule(
        focal_cards=frozenset({"Skeletons", "IceSpirit", "Goblins", "Knight",
                               "IceGolem"}),
        threat_tokens=CHARGERS,
        threat_max_y=20.0,
        displaced="two_tiles",
        description="cheap interrupter against a visible Prince or Dark Prince",
    ),
    "log_pushback": ProbeRule(
        focal_cards=frozenset({"Log"}),
        threat_tokens=GROUND_TROOPS,
        threat_max_y=20.0,
        displaced="two_tiles",
        description="Log placement against visible enemy ground troops",
    ),
    "shields": ProbeRule(
        focal_cards=frozenset({"Zap", "Log", "Archers", "Musketeer", "Knight",
                               "Skeletons", "Goblins", "Fireball"}),
        threat_tokens=SHIELDED,
        threat_max_y=24.0,
        displaced="two_tiles",
        description="response to a visible shielded Dark Prince",
    ),
}


def _names(token_names: Sequence[str], ids: np.ndarray) -> list[str]:
    return [token_names[int(i)] if 0 <= int(i) < len(token_names) else "" for i in ids]


def _enemy_bodies(
    packet: ConfidenceAwareActorObservation, token_names: Sequence[str]
) -> list[tuple[str, float, float]]:
    obs = packet.observation
    rows = obs.entity_mask & (obs.entity_features[:, 3] > 0.5)
    names = _names(token_names, obs.entity_ids[rows])
    features = obs.entity_features[rows]
    confidence = packet.entity_id_confidence[rows]
    return [
        (name, float(f[0] * 18), float(f[1] * 32))
        for name, f, c in zip(names, features, confidence)
        if c > 0
    ]


def probe_matches(
    kind: str,
    packet: ConfidenceAwareActorObservation,
    token_names: Sequence[str],
) -> bool:
    rule = PROBE_RULES[kind]
    obs = packet.observation
    hand = set(_names(token_names, obs.hand_ids))
    if not hand & rule.focal_cards:
        return False
    enemies = _enemy_bodies(packet, token_names)
    if rule.quiet_own_half and any(
        name in GROUND_TROOPS and y < 16 for name, _, y in enemies
    ):
        return False
    if not rule.threat_tokens:
        return True
    return any(
        name in rule.threat_tokens and y <= rule.threat_max_y for name, _, y in enemies
    )


def _tile(action: int) -> tuple[int, int]:
    tile = action % 576
    return tile % 18, tile // 18


def probe_candidates(
    kind: str,
    plays: Sequence[RankedPlay],
    packet: ConfidenceAwareActorObservation,
    token_names: Sequence[str],
) -> tuple[Candidate, ...]:
    """Probe-specific four roles; raises ``ineligible root:`` before outcomes.

    ``plays`` are legal immediate plays already in the frozen policy order.
    immediate_play is the policy's best focal-card play; alternate_card its best
    play of another card; displaced_placement its best same-slot play in the
    opposite lane (lane choice) or at least two tiles away (other probes).
    """
    if kind not in PROBE_RULES:
        raise ValueError("undeclared probe kind")
    if not probe_matches(kind, packet, token_names):
        raise ValueError("ineligible root: probe pattern absent")
    rule = PROBE_RULES[kind]
    ids = packet.observation.hand_ids
    names = _names(token_names, ids)
    ranked = [p for p in plays if p.action_id < WAIT]
    first = next(
        (p for p in ranked if names[p.action_id // 576] in rule.focal_cards), None
    )
    if first is None:
        raise ValueError("ineligible root: no legal focal play")
    slot = first.action_id // 576
    token = int(ids[slot])
    fx, fy = _tile(first.action_id)
    alternate = next(
        (p for p in ranked if int(ids[p.action_id // 576]) != token), None
    )

    def displaced_ok(action: int) -> bool:
        x, y = _tile(action)
        far = (x - fx) ** 2 + (y - fy) ** 2 >= 4
        if rule.displaced == "opposite_lane":
            return far and (x < 9) != (fx < 9)
        return far

    displaced = next(
        (
            p
            for p in ranked
            if p.action_id // 576 == slot and displaced_ok(p.action_id)
        ),
        None,
    )
    if alternate is None or displaced is None:
        raise ValueError("ineligible root: missing distinct card or displaced placement")
    result = []
    choices: tuple[RankedPlay | None, ...] = (first, None, alternate, displaced)
    for role, play in zip(ROLES, choices):
        result.append(
            Candidate(
                role=role,
                action_id=WAIT if play is None else play.action_id,
                card_token=0 if play is None else int(ids[play.action_id // 576]),
                public_score=0.0 if play is None else float(play.score),
            )
        )
    return tuple(result)


class ProbeFinding(Record):
    probe_kind: str
    declared: int = Field(ge=0)
    complete: int = Field(ge=0)
    missing: int = Field(ge=0)
    nonwait_informative: int = Field(ge=0)
    material_failures: int = Field(ge=0)
    repeatable_events: int = Field(ge=0)
    above_floor_events: int = Field(ge=0)
    blocking: bool


class ProbeReport(Record):
    """Separate targeted-probe report; never a population rate."""

    schema_version: Literal["training-readiness-v2-tier-b-probes-v1"] = (
        "training-readiness-v2-tier-b-probes-v1"
    )
    status: Literal["blocked", "inconclusive", "no_block_found"]
    protocol_sha256: str
    interpretation: Literal[
        "targeted probes can block; they do not estimate a population rate"
    ] = "targeted probes can block; they do not estimate a population rate"
    findings: tuple[ProbeFinding, ...]
    reasons: tuple[str, ...]


def probe_report(protocol: object, report: object) -> ProbeReport:
    """Summarize a targeted-probe ``TierBReport`` by probe kind."""
    from .readiness_tier_b import TierBProtocol, TierBReport

    assert isinstance(protocol, TierBProtocol) and isinstance(report, TierBReport)
    if protocol.block_kind != "targeted_probe" or report.block_kind != "targeted_probe":
        raise ValueError("probe reports summarize targeted-probe blocks only")
    if report.protocol_sha256 != protocol.sha256:
        raise ValueError("probe report differs from its frozen protocol")
    results = {r.family_id: r for r in report.families}
    findings = []
    for kind in sorted({s.probe_kind for s in protocol.strata if s.probe_kind}):
        ids = [s.family_id for s in protocol.strata if s.probe_kind == kind]
        rows = [results[i] for i in ids if i in results and results[i].complete]
        material = sum(r.material_failure for r in rows)
        findings.append(
            ProbeFinding(
                probe_kind=kind,
                declared=len(ids),
                complete=len(rows),
                missing=len(ids) - len(rows),
                nonwait_informative=sum(r.nonwait_informative for r in rows),
                material_failures=material,
                repeatable_events=sum(len(r.repeatable_classes) for r in rows),
                above_floor_events=sum(len(r.above_floor_classes) for r in rows),
                blocking=material > 0,
            )
        )
    return ProbeReport(
        status=report.status,  # type: ignore[arg-type]  # probes never pass
        protocol_sha256=report.protocol_sha256,
        findings=tuple(findings),
        reasons=report.reasons,
    )
