"""Prospective readiness records and decision checks, independent of v7.

This module neither collects native outcomes nor authorizes training. Drafts
cannot pass. All recorded families remain in accounting, including missing and
uninformative ones. Development repetitions measure within-engine repeatability.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import product
from typing import Annotated, Any, Final, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from .public_observation import ConfidenceAwareActorObservation
from .public_scripted_opponent import PublicScriptedOpponent

SHA = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Role = Literal["immediate_play", "wait", "alternate_card", "displaced_placement"]
Engine = Literal["scalar", "reference"]
ROLES: tuple[Role, ...] = (
    "immediate_play",
    "wait",
    "alternate_card",
    "displaced_placement",
)
CONDITIONS = (
    "balanced/pressure",
    "balanced/balanced",
    "defense/pressure",
    "defense/balanced",
)
APPROVED_STRATEGY_SHA: Final = (
    "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
)


def _match_score(value: float) -> float:
    if value not in (0.0, 0.5, 1.0):
        raise ValueError("match score must be 0, 0.5 or 1")
    return value


MatchScore = Annotated[float, AfterValidator(_match_score)]


class Record(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class Candidate(Record):
    role: Role
    action_id: int = Field(ge=0, le=2304)
    card_token: int = Field(ge=0)
    public_score: float

    @model_validator(mode="after")
    def action_kind(self) -> Candidate:
        if (self.role == "wait") != (self.action_id == 2304):
            raise ValueError("wait role must have wait action; other roles must play")
        if (self.card_token == 0) != (self.role == "wait"):
            raise ValueError("only wait has no card token")
        return self


class Family(Record):
    family_id: str = Field(min_length=1)
    independence_id: str = Field(min_length=1)
    root_sha256: SHA
    public_packet_sha256: SHA
    root_owner: Literal[0, 1]
    # Scope is nominal level 11 until expanded level admission is declared.
    tower_levels: tuple[Literal[11], Literal[11], Literal[11]] = (11, 11, 11)
    starting_crown_hp: Literal[10928] = 10928
    role: Literal["fresh_acceptance", "opened_development"]
    candidates: tuple[Candidate, ...]
    original_recommendation: int = Field(ge=0, le=2304)

    @model_validator(mode="after")
    def candidate_roles(self) -> Family:
        if tuple(c.role for c in self.candidates) != ROLES:
            raise ValueError("exactly four candidates in declared role order required")
        if len({c.action_id for c in self.candidates}) != 4:
            raise ValueError("candidate actions must be distinct")
        first, _, other, displaced = self.candidates
        if first.card_token == other.card_token:
            raise ValueError("alternate card must have a different identity")
        if (
            first.card_token != displaced.card_token
            or first.action_id // 576 != displaced.action_id // 576
        ):
            raise ValueError("displaced placement must use the first card and slot")
        a, b = first.action_id % 576, displaced.action_id % 576
        if (a % 18 - b % 18) ** 2 + (a // 18 - b // 18) ** 2 < 4:
            raise ValueError("displaced placement must be at least two tiles away")
        return self


def generate_candidates(
    controller: PublicScriptedOpponent, packet: ConfidenceAwareActorObservation
) -> tuple[Candidate, ...]:
    """Eligibility: two affordable distinct cards and a >=2-tile alternative.

    Ineligible roots raise before outcomes; callers must retain the generation
    failure in their attempt ledger, never silently draw a replacement root.
    """
    plays = controller.ranked_plays(packet)
    if not plays:
        raise ValueError("ineligible root: no legal play")
    first = plays[0]
    ids = packet.observation.hand_ids
    first_token = int(ids[first.action_id // 576])
    alternate = next(
        (p for p in plays if int(ids[p.action_id // 576]) != first_token), None
    )
    tile = first.action_id % 576
    displaced = next(
        (
            p
            for p in plays
            if p.action_id // 576 == first.action_id // 576
            and (
                (p.action_id % 18 - tile % 18) ** 2
                + ((p.action_id % 576) // 18 - tile // 18) ** 2
                >= 4
            )
        ),
        None,
    )
    if alternate is None or displaced is None:
        raise ValueError(
            "ineligible root: missing distinct card or displaced placement"
        )
    result = []
    for role, play in zip(ROLES, (first, None, alternate, displaced)):
        result.append(
            Candidate(
                role=role,
                action_id=2304 if play is None else play.action_id,
                card_token=0 if play is None else int(ids[play.action_id // 576]),
                public_score=0.0 if play is None else play.score,
            )
        )
    return tuple(result)


class Repetition(Record):
    """Repeated identical execution, not different response seeds or engines."""

    engine: Engine
    root_sha256: SHA
    execution_sha256: SHA  # states, candidate, policies, seeds, schedules and source
    artifact_sha256: SHA
    score: MatchScore
    own_remaining_hp: float = Field(ge=0)
    enemy_remaining_hp: float = Field(ge=0)
    starting_crown_hp: Literal[10928] = 10928

    @property
    def margin(self) -> float:
        return (
            self.own_remaining_hp - self.enemy_remaining_hp
        ) / self.starting_crown_hp


class MeasurementFloors(Record):
    score: float = Field(ge=0)
    margin: float = Field(ge=0)
    score_rounding_allowance: float = Field(ge=0)
    margin_rounding_allowance: float = Field(ge=0)
    repetitions: tuple[Repetition, ...]

    @model_validator(mode="after")
    def verify(self) -> MeasurementFloors:
        groups: dict[tuple[str, str, str], list[Repetition]] = {}
        if {r.engine for r in self.repetitions} != {"scalar", "reference"}:
            raise ValueError(
                "identical execution repetitions required for both engines"
            )
        if len({r.artifact_sha256 for r in self.repetitions}) != len(self.repetitions):
            raise ValueError("duplicate repetition receipt")
        for row in self.repetitions:
            groups.setdefault(
                (row.engine, row.root_sha256, row.execution_sha256), []
            ).append(row)
        if any(len(rows) < 2 for rows in groups.values()):
            raise ValueError("each identical execution needs at least two repetitions")
        score = max(
            self.score_rounding_allowance,
            max(
                max(r.score for r in rows) - min(r.score for r in rows)
                for rows in groups.values()
            ),
        )
        margin = max(
            self.margin_rounding_allowance,
            max(
                max(r.margin for r in rows) - min(r.margin for r in rows)
                for rows in groups.values()
            ),
        )
        if abs(self.score - score) > 1e-12 or abs(self.margin - margin) > 1e-12:
            raise ValueError(
                "floors must equal maximum repeat difference or rounding allowance"
            )
        if score >= 0.125 or margin > 0.01:
            raise ValueError(
                "material non-reproducibility must be resolved before freezing"
            )
        return self


class Protocol(Record):
    schema_version: Literal["training-readiness-v2"] = "training-readiness-v2"
    strategy_sha256: Literal[
        "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
    ] = APPROVED_STRATEGY_SHA
    attempt_id: str = Field(min_length=1)
    status: Literal["draft", "frozen"] = "draft"
    conditions: tuple[str, ...] = CONDITIONS
    decision_interval_ticks: Literal[5] = 5
    family_count: Literal[32] = 32
    minimum_nonwait_informative: Literal[16] = 16
    source_pins: dict[str, SHA] = Field(default_factory=dict)
    config_sha256: SHA | None = None
    generator_sha256: SHA | None = None
    scalar_coverage_study_sha256: SHA | None = None
    floors: MeasurementFloors | None = None
    families: tuple[Family, ...] = ()
    generation_failures: tuple[str, ...] = ()
    comparator_tie_rule: Literal["role_order"] = "role_order"
    teacher_order: Literal[
        "tier_a_then_search_scope_then_64_256_strength_then_fresh_reference_then_labels"
    ] = "tier_a_then_search_scope_then_64_256_strength_then_fresh_reference_then_labels"

    @model_validator(mode="after")
    def design(self) -> Protocol:
        if self.conditions != CONDITIONS:
            raise ValueError("four frozen ordered style conditions required")
        for key in ("family_id", "independence_id", "root_sha256"):
            if len({getattr(f, key) for f in self.families}) != len(self.families):
                raise ValueError(
                    f"duplicate {key}; correlated roots are not independent families"
                )
        if self.status == "frozen":
            if not self.source_pins or any(
                x is None
                for x in (
                    self.config_sha256,
                    self.generator_sha256,
                    self.scalar_coverage_study_sha256,
                    self.floors,
                )
            ):
                raise ValueError(
                    "source/config/generator pins and real development studies required"
                )
            if len(self.families) != 32 or self.generation_failures:
                raise ValueError("all 32 generated families required before freeze")
            if Counter(f.root_owner for f in self.families) != {0: 16, 1: 16}:
                raise ValueError("families must balance seats")
            if any(f.role != "fresh_acceptance" for f in self.families):
                raise ValueError("opened evidence cannot become fresh acceptance")
            assert self.floors is not None
            if {r.root_sha256 for r in self.floors.repetitions} & {
                f.root_sha256 for f in self.families
            }:
                raise ValueError(
                    "development repetition roots cannot enter fresh acceptance"
                )
        return self

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()


class Branch(Record):
    protocol_sha256: SHA
    family_id: str
    root_sha256: SHA
    public_packet_sha256: SHA
    candidate_role: Role
    action_id: int = Field(ge=0, le=2304)
    condition: str
    engine: Engine
    artifact_sha256: SHA
    score: MatchScore
    own_remaining_hp: float = Field(ge=0)
    enemy_remaining_hp: float = Field(ge=0)
    terminal: Literal[True]
    public_contract_valid: Literal[True]
    legal_transport_valid: Literal[True]


class FamilyResult(Record):
    family_id: str
    complete: bool
    missing_branches: int
    nonwait_informative: bool = False
    play_wait_informative: bool = False
    scalar_preferred: tuple[Role, ...] = ()
    reference_comparator: Role | None = None
    score_regret: float = 0.0
    margin_regret: float = 0.0
    material_failure: bool = False
    repeatable_classes: tuple[Role, ...] = ()
    above_floor_classes: tuple[Role, ...] = ()
    score_regrets: dict[Role, float] = Field(default_factory=dict)
    margin_regrets: dict[Role, float] = Field(default_factory=dict)
    # Each preferred class: comparator minus candidate in fixed condition order.
    score_signs: dict[Role, tuple[int, ...]] = Field(default_factory=dict)
    margin_signs: dict[Role, tuple[int, ...]] = Field(default_factory=dict)


class TechnicalRerunSummary(Record):
    """One pre-declared technical rerun of a claim that recorded no outcome.

    Listed in Tier A reports and admission receipts so every rerun, its reason
    and the hash of the preserved original evidence remain auditable.
    """

    family_id: str
    condition: str
    candidate_role: Role
    engine: Engine
    original_nonce: str
    rerun_nonce: str
    original_output_path: str
    rerun_output_path: str
    reason: Literal["infrastructure_failure", "runner_killed_without_outcome"]
    failure_type: str | None
    evidence_sha256: SHA
    completed: bool


class Report(Record):
    status: Literal["passed", "blocked", "inconclusive"]
    protocol_sha256: SHA
    families: tuple[FamilyResult, ...]
    informative_families: int
    material_failures: int
    class_exposures: dict[Role, int]
    class_events: dict[Role, int]
    insufficient_class_coverage: tuple[Role, ...]
    reasons: tuple[str, ...]
    full_design_failure_upper_bound: float | None = None
    technical_reruns: tuple[TechnicalRerunSummary, ...] = ()

    @model_serializer(mode="wrap")
    def _omit_empty_reruns(self, handler: Any) -> Any:
        # Reports without reruns serialize byte-identically to earlier reports.
        data = handler(self)
        if not self.technical_reruns:
            data.pop("technical_reruns", None)
        return data


def branch_plan(protocol: Protocol) -> tuple[dict[str, str | int], ...]:
    """Enumerate paired conditions x candidates x engines without executing jobs."""
    return tuple(
        {
            "family_id": f.family_id,
            "candidate_role": c.role,
            "action_id": c.action_id,
            "condition": condition,
            "engine": engine,
            "seed_label": condition,
        }
        for f in protocol.families
        for condition in protocol.conditions
        for c in f.candidates
        for engine in ("scalar", "reference")
    )


class MechanismReview(Record):
    family_id: str
    candidate_role: Role
    artifact_sha256: SHA
    verdict: Literal["no_additional_block", "block"]
    explanation: str = Field(min_length=1)


def score_families(
    families: tuple[Family, ...],
    conditions: tuple[str, ...],
    floors: MeasurementFloors | None,
    protocol_sha256: str,
    branches: tuple[Branch, ...],
) -> tuple[tuple[FamilyResult, ...], Counter[Role], Counter[Role]]:
    """Per-family regret, coverage and repeated-harm scoring.

    Shared by the Tier A evaluator and later blocks (for example Tier B) so
    that every block uses identical regret, floor and bias arithmetic. Block
    size, coverage thresholds and bounds are applied by the caller.
    """
    expected = {
        (f.family_id, c.role, condition, engine): (f, c)
        for f in families
        for c in f.candidates
        for condition in conditions
        for engine in ("scalar", "reference")
    }
    seen = {}
    receipts = set()
    for row in branches:
        key = (row.family_id, row.candidate_role, row.condition, row.engine)
        if key not in expected or key in seen:
            raise ValueError("unexpected or duplicate branch")
        f, c = expected[key]
        if (
            row.protocol_sha256 != protocol_sha256
            or row.root_sha256 != f.root_sha256
            or row.public_packet_sha256 != f.public_packet_sha256
            or row.action_id != c.action_id
        ):
            raise ValueError("branch provenance does not match frozen declaration")
        if row.artifact_sha256 in receipts:
            raise ValueError("duplicate branch artifact")
        receipts.add(row.artifact_sha256)
        seen[key] = row
    score_floor = floors.score if floors else 0.0
    margin_floor = floors.margin if floors else 0.0
    results = []
    exposures = Counter({role: 0 for role in ROLES})
    events = Counter({role: 0 for role in ROLES})
    for f in families:
        missing = sum(key not in seen for key in expected if key[0] == f.family_id)
        if missing:
            results.append(
                FamilyResult(
                    family_id=f.family_id, complete=False, missing_branches=missing
                )
            )
            continue

        def values(
            engine: Engine, role: Role, family: Family = f
        ) -> tuple[tuple[float, ...], tuple[float, ...]]:
            rows = [
                seen[family.family_id, role, condition, engine]
                for condition in conditions
            ]
            return tuple(r.score for r in rows), tuple(
                (r.own_remaining_hp - r.enemy_remaining_hp) / family.starting_crown_hp
                for r in rows
            )

        def means(engine: Engine, role: Role) -> tuple[float, float]:
            score, margin = values(engine, role)
            return sum(score) / 4, sum(margin) / 4

        scalar = {role: means("scalar", role) for role in ROLES}
        reference = {role: means("reference", role) for role in ROLES}
        scalar_best = max(scalar.values())
        preferred = tuple(role for role in ROLES if scalar[role] == scalar_best)
        comparator = max(
            ROLES, key=lambda role: reference[role]
        )  # stable role-order tie rule
        best_score, best_margin = reference[comparator]
        regret = max(best_score - reference[role][0] for role in preferred)
        margin_regret = max(
            (
                best_margin - reference[role][1]
                if best_score == reference[role][0]
                else 0.0
            )
            for role in preferred
        )

        def informative(
            roles: tuple[Role, ...],
            reference: dict[Role, tuple[float, float]] = reference,
        ) -> bool:
            return any(
                abs(reference[a][0] - reference[b][0]) > score_floor
                or abs(reference[a][1] - reference[b][1]) > max(margin_floor, 0.01)
                for a, b in product(roles, roles)
                if a != b
            )

        repeatable, above_floor, score_signs, margin_signs = [], [], {}, {}
        score_regrets, margin_regrets = {}, {}
        for role in preferred:
            exposures[role] += 1
            ds = best_score - reference[role][0]
            dm = best_margin - reference[role][1]
            score_regrets[role], margin_regrets[role] = ds, dm
            cs, cm = values("reference", comparator)
            rs, rm = values("reference", role)
            signs = lambda a, b: tuple((x > y) - (x < y) for x, y in zip(a, b))
            score_signs[role], margin_signs[role] = signs(cs, rs), signs(cm, rm)
            score_event = ds >= 0.125 and ds > score_floor
            margin_event = ds == 0 and dm > 0.01 and dm > margin_floor
            if ds > score_floor or (ds == 0 and dm > margin_floor):
                above_floor.append(role)
            if (score_event and score_signs[role].count(1) >= 3) or (
                margin_event and margin_signs[role].count(1) >= 3
            ):
                repeatable.append(role)
                events[role] += 1
        results.append(
            FamilyResult(
                family_id=f.family_id,
                complete=True,
                missing_branches=0,
                nonwait_informative=informative(tuple(r for r in ROLES if r != "wait")),
                play_wait_informative=any(
                    abs(reference[r][0] - reference["wait"][0]) > score_floor
                    or abs(reference[r][1] - reference["wait"][1])
                    > max(margin_floor, 0.01)
                    for r in ROLES
                    if r != "wait"
                ),
                scalar_preferred=preferred,
                reference_comparator=comparator,
                score_regret=regret,
                margin_regret=margin_regret,
                material_failure=regret >= 0.25 or margin_regret > 0.05,
                repeatable_classes=tuple(repeatable),
                above_floor_classes=tuple(above_floor),
                score_signs=score_signs,
                margin_signs=margin_signs,
                score_regrets=score_regrets,
                margin_regrets=margin_regrets,
            )
        )
    return tuple(results), exposures, events


def review_findings(
    results: tuple[FamilyResult, ...],
    family_ids: set[str],
    reviews: tuple[MechanismReview, ...],
) -> tuple[bool, list[str]]:
    """Validate mechanism reviews; reviews can add blocks, never remove them."""
    reasons = []
    reviewed: set[tuple[str, Role]] = set()
    declared_events = {
        (r.family_id, role) for r in results for role in r.above_floor_classes
    }
    for review in reviews:
        review_key = (review.family_id, review.candidate_role)
        if review_key in reviewed or review.family_id not in family_ids:
            raise ValueError("duplicate or undeclared mechanism review")
        reviewed.add(review_key)
    review_block = any(r.verdict == "block" for r in reviews)
    if review_block:
        reasons.append("mechanism review blocks admission")
    if declared_events - reviewed:
        reasons.append("above-floor events require mechanism review")
    return review_block, reasons


def evaluate(
    protocol: Protocol,
    branches: tuple[Branch, ...],
    reviews: tuple[MechanismReview, ...] = (),
) -> Report:
    results, exposures, events = score_families(
        protocol.families,
        protocol.conditions,
        protocol.floors,
        protocol.sha256,
        branches,
    )
    material = sum(r.material_failure for r in results)
    informative_count = sum(r.nonwait_informative for r in results)
    review_block, reasons = review_findings(
        results, {f.family_id for f in protocol.families}, reviews
    )
    blocked = review_block or material > 0 or any(n >= 4 for n in events.values())
    if material:
        reasons.append("material decision failure")
    if any(n >= 4 for n in events.values()):
        reasons.append("automatic repeated-class harm block")
    if protocol.status != "frozen":
        reasons.append("protocol is draft")
    if (
        len(results) != 32
        or any(not r.complete for r in results)
        or protocol.generation_failures
    ):
        reasons.append("missing declared families or branches or generation failures")
    if informative_count < 16:
        reasons.append("fewer than 16 consequential non-wait families")
    status: Literal["blocked", "inconclusive", "passed"] = (
        "blocked" if blocked else "inconclusive" if reasons else "passed"
    )
    return Report(
        status=status,
        protocol_sha256=protocol.sha256,
        families=results,
        informative_families=informative_count,
        material_failures=material,
        class_exposures=dict(exposures),
        class_events=dict(events),
        insufficient_class_coverage=tuple(
            role for role in ROLES if exposures[role] < 4
        ),
        reasons=tuple(reasons),
        full_design_failure_upper_bound=(1 - 0.05 ** (1 / 32))
        if status == "passed"
        else None,
    )
