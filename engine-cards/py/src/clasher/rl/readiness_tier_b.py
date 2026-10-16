"""Tier B learned-policy transfer records, candidates and decisions.

Tier B re-applies the Tier A regret, measurement-floor and automatic-bias
arithmetic (``training_readiness_v2.score_families``) to roots reached by a
frozen learned policy. Two blocks have separate reporting roles:

* ``representative``: 30 roots stratified by supported deck, phase and seat.
  At least 15 must give consequential non-wait coverage; otherwise the block
  is inconclusive. Only this block supports a population-rate reading, and its
  bound is computed for its own size, never quoted from Tier A's 32 families.
* ``targeted_probe``: roots selected for suspected exploits or frequent
  problematic patterns. It can block, but it never "passes" and never carries
  a population bound.

Every declared root stays in failure accounting. A root that could not be
captured or had no eligible policy candidates is a missing case, not a
replacement opportunity. This module never collects outcomes.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
from pydantic import Field, model_validator

from .public_observation import ConfidenceAwareActorObservation
from .public_scripted_opponent import SUPPORTED_CARDS
from .training_readiness_v2 import (
    APPROVED_STRATEGY_SHA,
    CONDITIONS,
    ROLES,
    SHA,
    Branch,
    Candidate,
    Family,
    FamilyResult,
    MeasurementFloors,
    MechanismReview,
    Record,
    Role,
    generate_candidates,
    review_findings,
    score_families,
)

Phase = Literal["early", "middle", "double_elixir", "overtime"]
BlockKind = Literal["representative", "targeted_probe"]
ProbeKind = Literal[
    "lane_choice",
    "building_pull",
    "body_block",
    "charge_blocking",
    "log_pushback",
    "shields",
]
OpponentKind = Literal["policy", "script:balanced", "script:pressure", "script:defense"]

# Native tick windows (20 ticks/s; first playable tick 90; regulation ends at
# 3600 and overtime at 6000). Windows are half-open [start, end).
PHASE_WINDOWS: Final[dict[str, tuple[int, int]]] = {
    "early": (90, 1200),
    "middle": (1200, 2400),
    "double_elixir": (2400, 3600),
    "overtime": (3600, 6000),
}
PROBE_KINDS: Final[tuple[str, ...]] = (
    "lane_choice",
    "building_pull",
    "body_block",
    "charge_blocking",
    "log_pushback",
    "shields",
)
REPRESENTATIVE_ROOTS: Final = 30
REPRESENTATIVE_MIN_INFORMATIVE: Final = 15
# Same practical repeated-harm constant as Tier A (not recalibrated for size).
REPEATED_HARM_FAMILIES: Final = 4
MAX_PROBE_ROOTS: Final = 48
DEFAULT_PHASE_ALLOCATION: Final[tuple[tuple[Phase, int], ...]] = (
    ("early", 10),
    ("middle", 10),
    ("double_elixir", 10),
)
RANKING_RULE: Final = "masked_joint_log_prob_desc_then_action_id"
WAIT_ACTION: Final = 2304
ACTION_COUNT: Final = 2306


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class Stratum(Record):
    """Pre-capture design cell of one root; fixed before any outcome."""

    family_id: str = Field(min_length=1)
    deck_id: str = Field(min_length=1)
    phase: Phase
    root_owner: Literal[0, 1]
    opponent: OpponentKind
    probe_kind: ProbeKind | None = None


def representative_allocation(
    deck_ids: tuple[str, ...],
    phase_allocation: tuple[tuple[Phase, int], ...] = DEFAULT_PHASE_ALLOCATION,
) -> tuple[tuple[str, Phase, Literal[0, 1]], ...]:
    """Deterministic (deck, phase, seat) cells for the 30-root block.

    Seats balance overall and within each phase. Decks cycle through the slot
    order, so deck counts differ by at most one and every (phase, seat) cell of
    at least ``len(deck_ids)`` slots contains every deck.
    """
    if len(deck_ids) < 2 or len(set(deck_ids)) != len(deck_ids):
        raise ValueError("at least two distinct supported deck identities required")
    phases = [phase for phase, _ in phase_allocation]
    if len(set(phases)) != len(phases) or not set(phases) <= set(PHASE_WINDOWS):
        raise ValueError("phase allocation must name distinct declared phases")
    if sum(n for _, n in phase_allocation) != REPRESENTATIVE_ROOTS or any(
        n <= 0 or n % 2 for _, n in phase_allocation
    ):
        raise ValueError("representative allocation needs 30 roots, even per phase")
    cells: list[tuple[str, Phase, Literal[0, 1]]] = []
    counter = 0
    for phase, count in phase_allocation:
        for seat in (0, 1):
            for _ in range(count // 2):
                cells.append((deck_ids[counter % len(deck_ids)], phase, seat))
                counter += 1
    return tuple(cells)


class PolicyRootRecord(Record):
    """The frozen policy's ranking at a captured root, frozen before outcomes."""

    family_id: str = Field(min_length=1)
    checkpoint_sha256: SHA
    policy_contract_sha256: SHA
    public_packet_sha256: SHA
    policy_packet_sha256: SHA
    root_tick: int = Field(ge=90, lt=6001)
    original_recommendation: int = Field(ge=0, le=WAIT_ACTION)
    original_log_prob: float = Field(le=0)
    wait_log_prob: float = Field(le=0)
    candidate_actions: dict[Role, int]
    candidate_log_probs: dict[Role, float]
    legal_play_count: int = Field(ge=3)
    ranking_rule: Literal["masked_joint_log_prob_desc_then_action_id"] = RANKING_RULE
    probe_kind: ProbeKind | None = None

    @model_validator(mode="after")
    def roles(self) -> PolicyRootRecord:
        if set(self.candidate_actions) != set(ROLES) or set(
            self.candidate_log_probs
        ) != set(ROLES):
            raise ValueError("policy record must cover all four candidate roles")
        if self.candidate_actions["wait"] != WAIT_ACTION:
            raise ValueError("wait candidate must be the wait action")
        if self.candidate_log_probs["wait"] != self.wait_log_prob:
            raise ValueError("wait candidate log-probability differs from record")
        if any(v > 0 for v in self.candidate_log_probs.values()):
            raise ValueError("log-probabilities cannot exceed zero")
        return self


class TierBProtocol(Record):
    schema_version: Literal["training-readiness-v2-tier-b"] = (
        "training-readiness-v2-tier-b"
    )
    strategy_sha256: Literal[
        "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
    ] = APPROVED_STRATEGY_SHA
    attempt_id: str = Field(min_length=1)
    block_kind: BlockKind
    status: Literal["draft", "frozen"] = "draft"
    conditions: tuple[str, ...] = CONDITIONS
    decision_interval_ticks: Literal[5] = 5
    family_count: int = Field(ge=1, le=MAX_PROBE_ROOTS)
    minimum_nonwait_informative: int | None = None
    repeated_harm_families: Literal[4] = REPEATED_HARM_FAMILIES
    checkpoint_sha256: SHA
    policy_contract_sha256: SHA
    tier_a_protocol_sha256: SHA | None = None
    source_pins: dict[str, SHA] = Field(default_factory=dict)
    config_sha256: SHA | None = None
    generator_sha256: SHA | None = None
    floors: MeasurementFloors | None = None
    strata: tuple[Stratum, ...]
    families: tuple[Family, ...] = ()
    policy_roots: tuple[PolicyRootRecord, ...] = ()
    generation_failures: tuple[str, ...] = ()
    comparator_tie_rule: Literal["role_order"] = "role_order"
    root_rule: Literal["first_policy_eligible_root_in_declared_window"] = (
        "first_policy_eligible_root_in_declared_window"
    )
    replacement_rule: Literal["retain_failure_no_replacement"] = (
        "retain_failure_no_replacement"
    )

    @model_validator(mode="after")
    def design(self) -> TierBProtocol:
        if self.conditions != CONDITIONS:
            raise ValueError("four frozen ordered style conditions required")
        ids = [s.family_id for s in self.strata]
        if len(set(ids)) != len(ids) or len(ids) != self.family_count:
            raise ValueError("one distinct declared stratum per root required")
        if self.block_kind == "representative":
            _validate_representative(self)
        else:
            if self.minimum_nonwait_informative is not None:
                raise ValueError("targeted probes carry no coverage threshold")
            if any(s.probe_kind is None for s in self.strata):
                raise ValueError("every targeted probe root declares its probe kind")
        by_id = {s.family_id: s for s in self.strata}
        for key in ("family_id", "independence_id", "root_sha256"):
            if len({getattr(f, key) for f in self.families}) != len(self.families):
                raise ValueError(
                    f"duplicate {key}; correlated roots are not independent roots"
                )
        for family in self.families:
            stratum = by_id.get(family.family_id)
            if stratum is None or stratum.root_owner != family.root_owner:
                raise ValueError("family differs from its declared stratum")
            if family.role != "fresh_acceptance":
                raise ValueError("opened evidence cannot enter a Tier B block")
        families = {f.family_id: f for f in self.families}
        if {p.family_id for p in self.policy_roots} != set(families) or len(
            self.policy_roots
        ) != len(families):
            raise ValueError("exactly one policy ranking record per captured root")
        for record in self.policy_roots:
            family = families[record.family_id]
            if (
                record.checkpoint_sha256 != self.checkpoint_sha256
                or record.policy_contract_sha256 != self.policy_contract_sha256
                or record.public_packet_sha256 != family.public_packet_sha256
                or record.original_recommendation != family.original_recommendation
                or record.candidate_actions
                != {c.role: c.action_id for c in family.candidates}
                or record.probe_kind != by_id[record.family_id].probe_kind
            ):
                raise ValueError("policy ranking differs from frozen family candidates")
        failed = []
        for failure in self.generation_failures:
            family_id, _, reason = failure.partition(": ")
            if family_id not in by_id or family_id in families or not reason:
                raise ValueError("generation failure must name an uncaptured root")
            failed.append(family_id)
        if len(set(failed)) != len(failed):
            raise ValueError("duplicate generation failure")
        if self.status == "frozen":
            if (
                not self.source_pins
                or self.config_sha256 is None
                or self.generator_sha256 is None
                or self.floors is None
                or self.tier_a_protocol_sha256 is None
            ):
                raise ValueError(
                    "source/config/generator pins, Tier A reference and floors required"
                )
            if set(families) | set(failed) != set(by_id):
                raise ValueError(
                    "every declared root must be captured or retained as a failure"
                )
            if {r.root_sha256 for r in self.floors.repetitions} & {
                f.root_sha256 for f in self.families
            }:
                raise ValueError("development repetition roots cannot enter Tier B")
        return self

    @property
    def sha256(self) -> str:
        return _sha(self.model_dump(mode="json"))


def _validate_representative(protocol: TierBProtocol) -> None:
    if (
        protocol.family_count != REPRESENTATIVE_ROOTS
        or protocol.minimum_nonwait_informative != REPRESENTATIVE_MIN_INFORMATIVE
    ):
        raise ValueError("representative block is 30 roots with 15 required coverage")
    strata = protocol.strata
    if any(s.probe_kind is not None for s in strata):
        raise ValueError("representative roots cannot be probe selections")
    if Counter(s.root_owner for s in strata) != {0: 15, 1: 15}:
        raise ValueError("representative roots must balance seats")
    phases = Counter(s.phase for s in strata)
    for phase in phases:
        seats = Counter(s.root_owner for s in strata if s.phase == phase)
        if seats[0] != seats[1]:
            raise ValueError("seats must balance within each phase")
    decks = Counter(s.deck_id for s in strata)
    if len(decks) < 2 or max(decks.values()) - min(decks.values()) > 1:
        raise ValueError("supported decks must be balanced within one root")
    for phase in phases:
        if {s.deck_id for s in strata if s.phase == phase} != set(decks):
            raise ValueError("every declared deck must appear in every phase")


# ---------------------------------------------------------------------------
# Root requests from scalar policy games.


class ScalarPreview(Record):
    """Scalar evidence that the policy reaches an eligible state; not a root."""

    scalar_seed: int = Field(ge=0, lt=2**32)
    scalar_root_tick: int = Field(ge=0, le=6001)
    scalar_packet_sha256: SHA
    scalar_candidate_actions: tuple[int, int, int, int]
    scalar_original_recommendation: int = Field(ge=0, le=WAIT_ACTION)


class TierBRootRequest(Record):
    family_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    root_owner: Literal[0, 1]
    episode_seed: int = Field(ge=0, lt=2**32)
    decks: tuple[tuple[str, ...], tuple[str, ...]]
    deck_id: str = Field(min_length=1)
    phase: Phase
    opponent: OpponentKind
    policy_seeds: tuple[int, int]
    checkpoint_sha256: SHA
    probe_kind: ProbeKind | None = None
    start_tick: int = Field(ge=90)
    stop_tick: int = Field(le=6000)
    cadence_ticks: Literal[5] = 5
    level: Literal[11] = 11
    root_rule: Literal["first_policy_eligible_root_in_declared_window"] = (
        "first_policy_eligible_root_in_declared_window"
    )
    scalar_preview: ScalarPreview

    @model_validator(mode="after")
    def scope(self) -> TierBRootRequest:
        low, high = PHASE_WINDOWS[self.phase]
        if (
            self.start_tick >= self.stop_tick
            or (self.stop_tick - self.start_tick) % 5
            or self.start_tick % 5
            or not low <= self.start_tick < self.stop_tick < high
        ):
            raise ValueError("root window must be whole five-tick steps in its phase")
        for deck in self.decks:
            if len(deck) != 8 or len(set(deck)) != 8 or not set(deck) <= SUPPORTED_CARDS:
                raise ValueError("each deck needs eight distinct supported pilot cards")
        if any(not 0 <= s < 2**32 for s in self.policy_seeds):
            raise ValueError("policy seeds must be 32-bit")
        return self

    @property
    def episode_design_sha256(self) -> str:
        return _sha(
            {
                "seed": self.episode_seed,
                "decks": self.decks,
                "opponent": self.opponent,
                "policy_seeds": self.policy_seeds,
                "checkpoint": self.checkpoint_sha256,
                "level": self.level,
            }
        )

    def stratum(self) -> Stratum:
        return Stratum(
            family_id=self.family_id,
            deck_id=self.deck_id,
            phase=self.phase,
            root_owner=self.root_owner,
            opponent=self.opponent,
            probe_kind=self.probe_kind,
        )


class RejectedDraw(Record):
    slot: int = Field(ge=0)
    scalar_seed: int
    reason: str = Field(min_length=1)


class TierBRootBank(Record):
    schema_version: Literal["readiness-v2-tier-b-root-bank-v1"] = (
        "readiness-v2-tier-b-root-bank-v1"
    )
    status: Literal["draft_requires_captures"] = "draft_requires_captures"
    block_kind: BlockKind
    master_seed: int = Field(ge=0)
    checkpoint_sha256: SHA
    policy_contract_sha256: SHA
    deck_table: dict[str, tuple[str, ...]]
    window_ticks: int = Field(ge=5, le=1200)
    max_draws_per_root: int = Field(ge=1, le=8)
    requests: tuple[TierBRootRequest, ...]
    rejected_draws: tuple[RejectedDraw, ...] = ()
    slot_failures: tuple[str, ...] = ()
    independence_unit: Literal["one_root_per_separate_policy_game"] = (
        "one_root_per_separate_policy_game"
    )
    missing_rule: Literal["retain_failure_no_replacement"] = (
        "retain_failure_no_replacement"
    )
    draw_rule: Literal["scalar_preview_only_bounded_draws_all_recorded"] = (
        "scalar_preview_only_bounded_draws_all_recorded"
    )

    @model_validator(mode="after")
    def design(self) -> TierBRootBank:
        for name in ("family_id", "source_episode_id", "episode_seed", "episode_design_sha256"):
            values = [getattr(r, name) for r in self.requests]
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {name}: one root per separate policy game")
        seeds = {r.scalar_preview.scalar_seed for r in self.requests}
        if len(seeds) != len(self.requests) or seeds & {d.scalar_seed for d in self.rejected_draws}:
            raise ValueError("a scalar game contributes at most one root or rejection")
        for request in self.requests:
            if request.checkpoint_sha256 != self.checkpoint_sha256:
                raise ValueError("every root request binds the frozen checkpoint")
            if self.deck_table.get(request.deck_id) != tuple(
                sorted(request.decks[request.root_owner])
            ):
                raise ValueError("root owner deck differs from its declared deck identity")
        if self.slot_failures:
            raise ValueError("an incomplete root bank cannot be declared")
        self.protocol_draft("bank-validation")
        return self

    def protocol_draft(self, attempt_id: str, **pins: Any) -> TierBProtocol:
        return TierBProtocol(
            attempt_id=attempt_id,
            block_kind=self.block_kind,
            family_count=len(self.requests),
            minimum_nonwait_informative=REPRESENTATIVE_MIN_INFORMATIVE
            if self.block_kind == "representative"
            else None,
            checkpoint_sha256=self.checkpoint_sha256,
            policy_contract_sha256=self.policy_contract_sha256,
            strata=tuple(r.stratum() for r in self.requests),
            **pins,
        )


# ---------------------------------------------------------------------------
# Policy-conditioned candidate ranking (pure numpy; no model dependency).


@dataclass(frozen=True)
class RankedPolicyPlay:
    action_id: int
    score: float


def _checked_log_probs(log_probs: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = np.asarray(log_probs, dtype=np.float64)
    legal = np.asarray(mask, dtype=np.bool_)
    if values.shape != (ACTION_COUNT,) or legal.shape != (ACTION_COUNT,):
        raise ValueError("policy distribution and mask must cover 2306 actions")
    if not legal[WAIT_ACTION]:
        raise ValueError("public mask must keep wait legal")
    if legal[WAIT_ACTION + 1]:
        raise ValueError("ability actions are outside the declared scope")
    if not np.all(np.isfinite(values[legal])) or np.any(values[legal] < -1e8):
        raise ValueError("legal actions need finite policy log-probabilities")
    if np.any(values[legal] > 1e-6):
        raise ValueError("policy log-probabilities cannot exceed zero")
    return values


def rank_policy_plays(
    log_probs: np.ndarray, mask: np.ndarray
) -> tuple[RankedPolicyPlay, ...]:
    """Legal immediate plays, highest joint log-probability, then lowest id."""
    values = _checked_log_probs(log_probs, mask)
    legal = np.flatnonzero(np.asarray(mask, dtype=np.bool_)[:WAIT_ACTION])
    order = sorted(legal.tolist(), key=lambda a: (-values[a], a))
    return tuple(RankedPolicyPlay(int(a), float(values[a])) for a in order)


def policy_recommendation(
    log_probs: np.ndarray, mask: np.ndarray
) -> RankedPolicyPlay:
    """The policy's own mode over all legal actions, including wait."""
    values = _checked_log_probs(log_probs, mask)
    legal = np.flatnonzero(np.asarray(mask, dtype=np.bool_)).tolist()
    best = min(legal, key=lambda a: (-values[a], a))
    return RankedPolicyPlay(int(best), float(values[best]))


class PolicyRanker:
    """Expose ``ranked_plays``/``decide`` so Tier A candidate rules are reused."""

    def __init__(self, log_probs: np.ndarray, mask: np.ndarray):
        self.log_probs = _checked_log_probs(log_probs, mask)
        self.mask = np.asarray(mask, dtype=np.bool_).copy()

    def ranked_plays(
        self, packet: ConfidenceAwareActorObservation | None = None
    ) -> tuple[RankedPolicyPlay, ...]:
        return rank_policy_plays(self.log_probs, self.mask)

    def decide(
        self, packet: ConfidenceAwareActorObservation | None = None
    ) -> RankedPolicyPlay:
        return policy_recommendation(self.log_probs, self.mask)


def policy_candidates(
    log_probs: np.ndarray,
    mask: np.ndarray,
    packet: ConfidenceAwareActorObservation,
    *,
    probe_kind: ProbeKind | None = None,
    token_names: tuple[str, ...] | None = None,
) -> tuple[tuple[Candidate, ...], RankedPolicyPlay]:
    """Four candidates ranked by the frozen policy; raises ``ineligible root:``.

    Representative roots use exactly the Tier A role rules
    (``generate_candidates``) with the policy's ranking. Probe roots use the
    declared probe rule. Card identities come from ``packet.hand_ids``.
    """
    ranker = PolicyRanker(log_probs, mask)
    if probe_kind is None:
        candidates = generate_candidates(ranker, packet)  # type: ignore[arg-type]
    else:
        from .readiness_tier_b_probes import probe_candidates

        if token_names is None:
            raise ValueError("probe candidates need the packet token vocabulary")
        candidates = probe_candidates(
            probe_kind, ranker.ranked_plays(), packet, token_names
        )
    return candidates, ranker.decide()


def policy_root_record(
    *,
    family_id: str,
    checkpoint_sha256: str,
    policy_contract_sha256: str,
    public_packet_sha256: str,
    policy_packet_sha256: str,
    root_tick: int,
    log_probs: np.ndarray,
    mask: np.ndarray,
    candidates: tuple[Candidate, ...],
    recommendation: RankedPolicyPlay,
    probe_kind: ProbeKind | None = None,
) -> PolicyRootRecord:
    values = _checked_log_probs(log_probs, mask)
    return PolicyRootRecord(
        family_id=family_id,
        checkpoint_sha256=checkpoint_sha256,
        policy_contract_sha256=policy_contract_sha256,
        public_packet_sha256=public_packet_sha256,
        policy_packet_sha256=policy_packet_sha256,
        root_tick=root_tick,
        original_recommendation=recommendation.action_id,
        original_log_prob=min(0.0, recommendation.score),
        wait_log_prob=min(0.0, float(values[WAIT_ACTION])),
        candidate_actions={c.role: c.action_id for c in candidates},
        candidate_log_probs={
            c.role: min(0.0, float(values[c.action_id])) for c in candidates
        },
        legal_play_count=int(np.asarray(mask, dtype=np.bool_)[:WAIT_ACTION].sum()),
        probe_kind=probe_kind,
    )


# ---------------------------------------------------------------------------
# Decisions.


class StratumSummary(Record):
    key: str
    declared: int = Field(ge=0)
    complete: int = Field(ge=0)
    missing: int = Field(ge=0)
    nonwait_informative: int = Field(ge=0)
    material_failures: int = Field(ge=0)
    repeatable_events: int = Field(ge=0)


class TierBReport(Record):
    schema_version: Literal["training-readiness-v2-tier-b-report-v1"] = (
        "training-readiness-v2-tier-b-report-v1"
    )
    block_kind: BlockKind
    status: Literal["passed", "blocked", "inconclusive", "no_block_found"]
    population_interpretation: Literal["representative_sample", "none_targeted_probe"]
    protocol_sha256: SHA
    declared_roots: int
    missing_roots: tuple[str, ...]
    families: tuple[FamilyResult, ...]
    informative_families: int
    minimum_nonwait_informative: int | None
    play_wait_informative_families: int
    material_failures: int
    class_exposures: dict[Role, int]
    class_events: dict[Role, int]
    insufficient_class_coverage: tuple[Role, ...]
    strata: tuple[StratumSummary, ...]
    policy_recommended_wait: int
    scalar_preferred_policy_immediate: int
    reasons: tuple[str, ...]
    representative_failure_upper_bound: float | None = None

    @model_validator(mode="after")
    def roles(self) -> TierBReport:
        if self.block_kind == "representative" and self.status == "no_block_found":
            raise ValueError("representative blocks pass, block or are inconclusive")
        if self.block_kind == "targeted_probe" and (
            self.status == "passed"
            or self.representative_failure_upper_bound is not None
            or self.population_interpretation != "none_targeted_probe"
        ):
            raise ValueError("targeted probes never pass or carry population bounds")
        if (self.representative_failure_upper_bound is not None) != (
            self.status == "passed"
        ):
            raise ValueError("a population bound accompanies only a passed block")
        return self


def tier_b_branch_plan(protocol: TierBProtocol) -> tuple[dict[str, str | int], ...]:
    """Paired conditions x candidates x engines for captured roots only."""
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


def _summaries(
    protocol: TierBProtocol, results: dict[str, FamilyResult]
) -> tuple[StratumSummary, ...]:
    keys: dict[str, list[Stratum]] = {}
    for s in protocol.strata:
        names = (
            [f"probe:{s.probe_kind}", f"seat:{s.root_owner}"]
            if s.probe_kind is not None
            else [
                f"deck:{s.deck_id}",
                f"phase:{s.phase}",
                f"seat:{s.root_owner}",
                f"cell:{s.deck_id}/{s.phase}/{s.root_owner}",
            ]
        )
        names.append(f"opponent:{s.opponent}")
        for name in names:
            keys.setdefault(name, []).append(s)
    rows = []
    for key in sorted(keys):
        found = [results.get(s.family_id) for s in keys[key]]
        complete = [r for r in found if r is not None and r.complete]
        rows.append(
            StratumSummary(
                key=key,
                declared=len(found),
                complete=len(complete),
                missing=len(found) - len(complete),
                nonwait_informative=sum(r.nonwait_informative for r in complete),
                material_failures=sum(r.material_failure for r in complete),
                repeatable_events=sum(len(r.repeatable_classes) for r in complete),
            )
        )
    return tuple(rows)


def evaluate_tier_b(
    protocol: TierBProtocol,
    branches: tuple[Branch, ...],
    reviews: tuple[MechanismReview, ...] = (),
) -> TierBReport:
    """Apply Tier A arithmetic with this block's own size and roles."""
    results, exposures, events = score_families(
        protocol.families,
        protocol.conditions,
        protocol.floors,
        protocol.sha256,
        branches,
    )
    by_id = {r.family_id: r for r in results}
    review_block, reasons = review_findings(
        results, {f.family_id for f in protocol.families}, reviews
    )
    material = sum(r.material_failure for r in results)
    informative = sum(r.nonwait_informative for r in results)
    repeated = any(n >= protocol.repeated_harm_families for n in events.values())
    blocked = review_block or material > 0 or repeated
    if material:
        reasons.append("material decision failure")
    if repeated:
        reasons.append("automatic repeated-class harm block")
    if protocol.status != "frozen":
        reasons.append("protocol is draft")
    missing = tuple(
        sorted(
            [f.partition(": ")[0] for f in protocol.generation_failures]
            + [r.family_id for r in results if not r.complete]
        )
    )
    if missing or len(results) + len(protocol.generation_failures) != len(
        protocol.strata
    ):
        reasons.append("missing declared roots or branches remain in accounting")
    representative = protocol.block_kind == "representative"
    if representative:
        assert protocol.minimum_nonwait_informative is not None
        if informative < protocol.minimum_nonwait_informative:
            reasons.append(
                f"fewer than {protocol.minimum_nonwait_informative} consequential"
                " non-wait roots"
            )
    if blocked:
        status: Literal["passed", "blocked", "inconclusive", "no_block_found"] = (
            "blocked"
        )
    elif reasons:
        status = "inconclusive"
    else:
        status = "passed" if representative else "no_block_found"
    immediate = {
        f.family_id: next(c.action_id for c in f.candidates if c.role == "immediate_play")
        for f in protocol.families
    }
    return TierBReport(
        block_kind=protocol.block_kind,
        status=status,
        population_interpretation=(
            "representative_sample" if representative else "none_targeted_probe"
        ),
        protocol_sha256=protocol.sha256,
        declared_roots=len(protocol.strata),
        missing_roots=missing,
        families=results,
        informative_families=informative,
        minimum_nonwait_informative=protocol.minimum_nonwait_informative,
        play_wait_informative_families=sum(r.play_wait_informative for r in results),
        material_failures=material,
        class_exposures=dict(exposures),
        class_events=dict(events),
        insufficient_class_coverage=tuple(
            role for role in ROLES if exposures[role] < protocol.repeated_harm_families
        ),
        strata=_summaries(protocol, by_id),
        policy_recommended_wait=sum(
            p.original_recommendation == WAIT_ACTION for p in protocol.policy_roots
        ),
        scalar_preferred_policy_immediate=sum(
            "immediate_play" in r.scalar_preferred
            for r in results
            if r.complete and immediate.get(r.family_id) is not None
        ),
        reasons=tuple(reasons),
        # Zero failures among this block's own declared roots only.
        representative_failure_upper_bound=(
            1 - 0.05 ** (1 / len(protocol.strata)) if status == "passed" else None
        ),
    )


def tier_b_upper_bound(roots: int) -> float:
    """One-sided 95% zero-failure bound for ``roots`` independent roots."""
    if roots <= 0:
        raise ValueError("bound requires at least one root")
    return 1 - math.pow(0.05, 1 / roots)
