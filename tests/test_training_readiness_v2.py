"""Synthetic accounting checks; these are not repetition or acceptance receipts."""

import hashlib

import pytest
from pydantic import ValidationError
from test_public_scripted_opponent import fixture, packet

from clasher.rl.training_readiness_v2 import (
    CONDITIONS,
    ROLES,
    Branch,
    Candidate,
    Family,
    MeasurementFloors,
    Protocol,
    Repetition,
    branch_plan,
    evaluate,
    generate_candidates,
)


def sha(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def candidates():
    return tuple(
        Candidate(role=role, action_id=action, card_token=token, public_score=1.0)
        for role, action, token in zip(ROLES, (0, 2304, 576, 2), (2, 0, 3, 2))
    )


def family(i=0, **kw):
    return Family(
        family_id=f"family-{i}",
        independence_id=f"independent-{i}",
        root_sha256=sha(i),
        public_packet_sha256=sha(f"public-{i}"),
        root_owner=i % 2,
        role="fresh_acceptance",
        candidates=candidates(),
        original_recommendation=2304,
        **kw,
    )


def floors(**kw):
    return MeasurementFloors(
        score=0.0,
        margin=0.0,
        score_rounding_allowance=0.0,
        margin_rounding_allowance=0.0,
        repetitions=tuple(
            Repetition(
                engine=engine,
                root_sha256=sha("dev"),
                execution_sha256=sha(engine),
                artifact_sha256=sha((engine, i)),
                score=0.5,
                own_remaining_hp=1000.0,
                enemy_remaining_hp=1000.0,
            )
            for engine in ("scalar", "reference")
            for i in range(2)
        ),
        **kw,
    )


def protocol():
    return Protocol(
        attempt_id="synthetic-test-only",
        status="frozen",
        families=tuple(family(i) for i in range(32)),
        floors=floors(),
        source_pins={"test": sha("source")},
        config_sha256=sha("config"),
        generator_sha256=sha("generator"),
        scalar_coverage_study_sha256=sha("coverage"),
    )


def branches(p, custom=None):
    rows = []
    for f in p.families:
        for engine in ("scalar", "reference"):
            for index, condition in enumerate(CONDITIONS):
                for candidate in f.candidates:
                    role = candidate.role
                    score, margin = (
                        (1.0, 0.0) if role == "immediate_play" else (0.5, 0.0)
                    )
                    if custom:
                        score, margin = custom(f, engine, role, index, score, margin)
                    rows.append(
                        Branch(
                            protocol_sha256=p.sha256,
                            family_id=f.family_id,
                            root_sha256=f.root_sha256,
                            public_packet_sha256=f.public_packet_sha256,
                            candidate_role=role,
                            action_id=candidate.action_id,
                            condition=condition,
                            engine=engine,
                            artifact_sha256=sha((f.family_id, engine, role, index)),
                            score=score,
                            own_remaining_hp=6000.0 + margin * 10928,
                            enemy_remaining_hp=6000.0,
                            terminal=True,
                            public_contract_valid=True,
                            legal_transport_valid=True,
                        )
                    )
    return tuple(rows)


def test_complete_design_and_draft_cannot_pass():
    p = protocol()
    assert len(branch_plan(p)) == 1024  # 512 for each engine
    report = evaluate(p, branches(p))
    assert report.status == "passed"
    assert report.informative_families == 32
    assert report.full_design_failure_upper_bound == pytest.approx(0.08937, abs=1e-5)
    assert report.insufficient_class_coverage == (
        "wait",
        "alternate_card",
        "displaced_placement",
    )
    draft = Protocol(attempt_id="unfinished")
    assert evaluate(draft, ()).status == "inconclusive"


def test_missing_duplicate_unknown_and_provenance_fail_closed():
    p = protocol()
    rows = branches(p)
    assert evaluate(p, rows[:-1]).status == "inconclusive"
    for invalid in (
        rows + rows[:1],
        (rows[0].model_copy(update={"condition": "new-condition"}),) + rows[1:],
        (rows[0].model_copy(update={"root_sha256": sha("wrong")}),) + rows[1:],
    ):
        with pytest.raises(ValueError):
            evaluate(p, invalid)


def test_noise_repeats_cannot_be_response_variation_or_wdl_spacing():
    f = floors()
    with pytest.raises(ValidationError, match="maximum repeat"):
        MeasurementFloors.model_validate({**f.model_dump(), "score": 0.5})
    rows = list(f.repetitions)
    rows[0] = rows[0].model_copy(update={"execution_sha256": sha("different-seed")})
    with pytest.raises(ValidationError, match="at least two"):
        MeasurementFloors.model_validate({**f.model_dump(), "repetitions": tuple(rows)})
    rows = list(f.repetitions)
    rows[0] = rows[0].model_copy(update={"score": 1.0})
    with pytest.raises(ValidationError, match="non-reproducibility"):
        MeasurementFloors.model_validate(
            {**f.model_dump(), "score": 0.5, "repetitions": tuple(rows)}
        )


def test_coverage_never_discards_wait_harm_or_material_failure():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        # No non-wait discrimination, but scalar chooses wait and loses.
        return (
            (1.0 if role == "wait" else 0.0, 0.0)
            if engine == "scalar"
            else (0.0 if role == "wait" else 1.0, 0.0)
        )

    r = evaluate(p, branches(p, outcomes))
    assert r.informative_families == 0
    assert r.status == "blocked"
    assert r.material_failures == 32
    assert r.class_events["wait"] == 32


def test_repeatable_submaterial_margin_harm_uses_four_families_and_three_conditions():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        if int(f.family_id.split("-")[-1]) < 4:
            if engine == "scalar":
                return 0.5, 0.02 if role == "wait" else 0.0
            return 0.5, 0.02 if role == "alternate_card" and index < 3 else 0.0
        return score, margin

    r = evaluate(p, branches(p, outcomes))
    assert r.material_failures == 0
    assert r.class_events["wait"] == 4
    assert r.status == "blocked"
    assert r.families[0].reference_comparator == "alternate_card"
    assert r.families[0].margin_signs["wait"] == (1, 1, 1, 0)


def test_two_conditions_cannot_trigger_repeatability():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        if engine == "scalar":
            return 0.5, 0.02 if role == "wait" else 0.0
        return 0.5, 0.04 if role == "alternate_card" and index < 2 else 0.0

    r = evaluate(p, branches(p, outcomes))
    assert r.class_events["wait"] == 0
    assert r.material_failures == 0


def test_pessimistic_scalar_ties_include_all_preferred_classes():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        return (
            (0.5, 0.0)
            if engine == "scalar"
            else (1.0 if role == "immediate_play" else 0.5, 0.0)
        )

    r = evaluate(p, branches(p, outcomes))
    assert r.families[0].scalar_preferred == ROLES
    assert r.material_failures == 32
    assert r.class_events["wait"] == 32


def test_denominator_is_full_starting_owner_hp():
    p = protocol()
    assert all(f.starting_crown_hp == 10928 for f in p.families)
    with pytest.raises(ValidationError):
        family(starting_crown_hp=21856)

    def outcomes(f, engine, role, index, score, margin):
        return 0.5, (
            0.06
            if role == ("immediate_play" if engine == "scalar" else "alternate_card")
            else 0.0
        )

    assert evaluate(p, branches(p, outcomes)).material_failures == 32


def test_freshness_and_independence_validation():
    p = protocol()
    for updated in (
        {"families": (p.families[0],) * 32},
        {"source_pins": {}},
        {
            "families": tuple(
                f.model_copy(update={"role": "opened_development"}) for f in p.families
            )
        },
    ):
        with pytest.raises(ValidationError):
            Protocol.model_validate({**p.model_dump(), **updated})


def test_ranked_candidates_preserve_decision_and_offer_distinct_roles():
    battle, builder, bot = fixture()
    obs = packet(battle, builder)
    ranked = bot.ranked_plays(obs)
    assert len(ranked) > 4
    assert list(ranked) == sorted(ranked, key=lambda r: (-r.score, r.action_id))
    assert bot.decide(obs) == ranked[0]
    cs = generate_candidates(bot, obs)
    assert len({c.action_id for c in cs}) == 4
    assert cs[0].card_token != cs[2].card_token
    assert cs[0].card_token == cs[3].card_token
    battle.players[0].elixir = 0
    with pytest.raises(ValueError, match="ineligible root"):
        generate_candidates(bot, packet(battle, builder))


def test_repeated_score_harm_requires_same_comparator_despite_opposing_fourth_condition():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        if engine == "scalar":
            return (1.0 if role == "wait" else 0.0), 0.0
        if role == "wait":
            return (0.0 if index < 3 else 1.0), 0.0
        if role == "alternate_card":
            return (0.5 if index < 3 else 0.0), 0.0
        return 0.0, 0.0

    r = evaluate(p, branches(p, outcomes))
    assert r.material_failures == 0
    assert r.class_events["wait"] == 32
    assert r.families[0].score_regrets["wait"] == 0.125
    assert r.families[0].score_signs["wait"] == (1, 1, 1, -1)
    assert r.status == "blocked"


def test_review_can_add_but_never_waive_automatic_block():
    from clasher.rl.training_readiness_v2 import MechanismReview

    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        return (
            (1.0 if role == "wait" else 0.0, 0.0)
            if engine == "scalar"
            else (0.0 if role == "wait" else 1.0, 0.0)
        )

    reviews = tuple(
        MechanismReview(
            family_id=f.family_id,
            candidate_role="wait",
            artifact_sha256=sha(f"review-{f.family_id}"),
            verdict="no_additional_block",
            explanation="Synthetic test review only",
        )
        for f in p.families
    )
    assert evaluate(p, branches(p, outcomes), reviews).status == "blocked"
    review = reviews[0].model_copy(update={"verdict": "block"})
    assert evaluate(p, branches(p), (review,)).status == "blocked"


def test_nonwait_coverage_floor_and_full_starting_denominator_boundary():
    p = protocol()

    def outcomes(f, engine, role, index, score, margin):
        return 0.5, (0.01 if role == "immediate_play" else 0.0)

    r = evaluate(p, branches(p, outcomes))
    assert r.informative_families == 0
    assert r.status == "inconclusive"


def test_original_recommendation_may_wait_while_candidates_contain_ranked_play():
    battle, builder, bot = fixture()
    battle.players[0].elixir = 4
    battle.players[0].hand = ["Cannon", "Fireball", "Zap", "Log"]
    obs = packet(battle, builder)
    assert bot.decide(obs).action_id == 2304
    assert generate_candidates(bot, obs)[0].action_id != 2304
