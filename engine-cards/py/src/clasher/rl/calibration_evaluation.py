"""Complete-family metrics; provenance admission is a separate required step."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from .calibration_decisions import (
    DecisionCriteria,
    DecisionRoot,
    StrictRecord,
    root_metrics,
)

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RootAssessment(StrictRecord):
    family_id: str = Field(min_length=1)
    config_sha256: Digest
    decision: DecisionRoot | None = None
    public_errors: tuple[str, ...] = ()
    branch_errors: tuple[str, ...] = ()

    @model_validator(mode="after")
    def matching_family(self):
        if self.decision is not None and self.decision.family_id != self.family_id:
            raise ValueError("decision belongs to another family")
        return self


def evaluate_family_metrics(
    expected: dict[str, tuple[str, ...]],
    assessments: list[RootAssessment],
    criteria: DecisionCriteria,
) -> dict:
    """Count all planned configurations; omissions cannot make results look better."""
    declarations = [(f, r) for f, roots in expected.items() for r in roots]
    if (
        not expected
        or any(not roots for roots in expected.values())
        or len({r for _, r in declarations}) != len(declarations)
    ):
        raise ValueError("empty or overlapping declared families")
    indexed = {}
    decision_ids = set()
    for assessment in assessments:
        key = assessment.family_id, assessment.config_sha256
        if key not in declarations or key in indexed:
            raise ValueError("undeclared or duplicate assessment")
        if assessment.decision is not None:
            identity = assessment.decision.root_id
            if identity in decision_ids:
                raise ValueError(
                    "one decision root cannot count as multiple configurations"
                )
            decision_ids.add(identity)
        indexed[key] = assessment
    families = []
    for family, configs in expected.items():
        members = []
        for config in configs:
            row = indexed.get((family, config))
            if row is None:
                members.append(
                    {
                        "config_sha256": config,
                        "public_failed": True,
                        "ranking_failed": True,
                        "errors": ["missing declared configuration"],
                        "decision": None,
                    }
                )
                continue
            metrics = (
                None if row.decision is None else root_metrics(row.decision, criteria)
            )
            errors = [*row.public_errors, *row.branch_errors]
            if metrics is None:
                errors.append("missing complete decision comparison")
            members.append(
                {
                    "config_sha256": config,
                    "public_failed": bool(row.public_errors),
                    "ranking_failed": bool(errors)
                    or bool(metrics and metrics["bad_decision"]),
                    "errors": errors,
                    "decision": metrics,
                }
            )
        public_failed = any(m["public_failed"] for m in members)
        ranking_failed = any(m["ranking_failed"] for m in members)
        regression = any(
            m["decision"] and m["decision"]["clear_regression_from_baseline"]
            for m in members
        )
        improvement = (
            not ranking_failed
            and not regression
            and any(
                m["decision"] and m["decision"]["clear_improvement_over_baseline"]
                for m in members
            )
        )
        families.append(
            {
                "family_id": family,
                "public_failed": public_failed,
                "ranking_failed": ranking_failed,
                "clear_regression": bool(regression),
                "clear_improvement": bool(improvement),
                "members": members,
            }
        )
    public_failures = sum(f["public_failed"] for f in families)
    ranking_failures = sum(f["ranking_failed"] for f in families)
    regressions = sum(f["clear_regression"] for f in families)
    improvements = sum(f["clear_improvement"] for f in families)
    enough = len(families) >= criteria.minimum_families
    public_passed = enough and public_failures == 0
    ranking_passed = (
        enough
        and ranking_failures == 0
        and regressions == 0
        and improvements >= criteria.minimum_clear_improvement_families
    )
    return {
        "family_count": len(families),
        "configuration_count": len(declarations),
        "assessed_configurations": len(indexed),
        "public_failed_families": public_failures,
        "ranking_failed_families": ranking_failures,
        "clear_improvement_families": improvements,
        "clear_regression_families": regressions,
        "public_metrics_passed": public_passed,
        "ranking_metrics_passed": ranking_passed,
        "metrics_passed": public_passed and ranking_passed,
        "acceptance_passed": False,
        "training_authorized": False,
        "admission_note": "Metrics alone do not verify roles, source provenance, exposure, protocol or observation-domain suitability.",
        "criteria": criteria.model_dump(),
        "families": families,
    }
