"""Family-grouped decision metrics for calibration planning, not gate admission."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class DecisionCriteria(StrictRecord):
    minimum_families: int = Field(ge=1)
    confidence: float = Field(gt=0, lt=1)
    maximum_bad_family_rate: float = Field(gt=0, lt=1)
    hp_regret_tolerance: float = Field(ge=0)
    minimum_clear_improvement_families: int = Field(ge=1)

    @property
    def planned_zero_failure_upper_bound(self) -> float:
        # Solve (1-p)^n = 1-confidence. This is a sample-size calculation;
        # opened, repair-selected development results cannot estimate p.
        return 1 - (1 - self.confidence) ** (1 / self.minimum_families)

    @model_validator(mode="after")
    def sample_size_supports_claim(self):
        if self.planned_zero_failure_upper_bound > self.maximum_bad_family_rate:
            raise ValueError(
                "family count cannot support the proposed zero-failure bound"
            )
        if self.minimum_clear_improvement_families > self.minimum_families:
            raise ValueError("improvement coverage exceeds family count")
        return self


class CandidatePair(StrictRecord):
    name: str = Field(min_length=1)
    native_outcome: int = Field(ge=-1, le=1)
    native_hp_margin: float
    scalar_outcome: int = Field(ge=-1, le=1)
    scalar_hp_margin: float

    @property
    def native(self):
        return self.native_outcome, self.native_hp_margin

    @property
    def scalar(self):
        return self.scalar_outcome, self.scalar_hp_margin


class DecisionRoot(StrictRecord):
    root_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    baseline: str = Field(min_length=1)
    expected_candidates: tuple[str, ...] = Field(min_length=2)
    candidates: tuple[CandidatePair, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def complete_candidate_set(self):
        names = [c.name for c in self.candidates]
        if len(set(names)) != len(names) or len(set(self.expected_candidates)) != len(
            self.expected_candidates
        ):
            raise ValueError("duplicate candidate")
        if set(names) != set(self.expected_candidates) or self.baseline not in names:
            raise ValueError("missing declared candidate or baseline")
        return self


def root_metrics(root: DecisionRoot, criteria: DecisionCriteria) -> dict:
    native_best = max(c.native for c in root.candidates)
    scalar_best = max(c.scalar for c in root.candidates)
    chosen = [c for c in root.candidates if c.scalar == scalar_best]
    worst = min(c.native for c in chosen)
    baseline = next(c.native for c in root.candidates if c.name == root.baseline)
    outcome_regret = native_best[0] - worst[0]
    hp_regret = native_best[1] - worst[1] if outcome_regret == 0 else None
    outcome_mismatch = any(c.native_outcome != c.scalar_outcome for c in chosen)
    hp_delta = worst[1] - baseline[1] if worst[0] == baseline[0] else None
    improvement = worst[0] > baseline[0] or (
        hp_delta is not None and hp_delta > criteria.hp_regret_tolerance
    )
    regression = worst[0] < baseline[0] or (
        hp_delta is not None and hp_delta < -criteria.hp_regret_tolerance
    )
    return {
        "root_id": root.root_id,
        "family_id": root.family_id,
        "native_best": [c.name for c in root.candidates if c.native == native_best],
        "scalar_best": [c.name for c in chosen],
        "worst_chosen_outcome_regret": outcome_regret,
        "worst_chosen_hp_regret": hp_regret,
        "selected_outcome_mismatch": outcome_mismatch,
        "bad_decision": outcome_mismatch
        or outcome_regret > 0
        or (hp_regret is not None and hp_regret > criteria.hp_regret_tolerance),
        "clear_improvement_over_baseline": improvement,
        "clear_regression_from_baseline": regression,
    }


def development_summary(roots: list[DecisionRoot], criteria: DecisionCriteria) -> dict:
    """Describe opened evidence without granting acceptance or training permission."""
    ids = [r.root_id for r in roots]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate root cannot inflate sample count")
    rows = [root_metrics(root, criteria) for root in roots]
    families = []
    for family in sorted({r.family_id for r in roots}):
        members = [r for r in rows if r["family_id"] == family]
        regression = any(r["clear_regression_from_baseline"] for r in members)
        families.append(
            {
                "family_id": family,
                "roots": len(members),
                "bad_decision": any(r["bad_decision"] for r in members),
                "clear_regression_from_baseline": regression,
                "clear_improvement_over_baseline": not regression
                and any(r["clear_improvement_over_baseline"] for r in members),
            }
        )
    return {
        "role": "opened development",
        "acceptance_passed": False,
        "training_authorized": False,
        "confidence_bound_from_observed_data": None,
        "confidence_exclusion": "These data were opened and used for repairs.",
        "root_count": len(rows),
        "family_count": len(families),
        "bad_families": sum(f["bad_decision"] for f in families),
        "clear_improvement_families": sum(
            f["clear_improvement_over_baseline"] for f in families
        ),
        "clear_regression_families": sum(
            f["clear_regression_from_baseline"] for f in families
        ),
        "planned_independent_criteria": criteria.model_dump(),
        "planned_zero_failure_upper_bound": criteria.planned_zero_failure_upper_bound,
        "families": families,
        "roots": rows,
    }
