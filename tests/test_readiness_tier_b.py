"""Tier B stratification, policy ranking, probes and decision thresholds.

Synthetic accounting only: no native execution, reference outcome or
promotion evidence. Branch values are fabricated to exercise the rules.
"""

from collections import Counter

import numpy as np
import pytest
from pydantic import ValidationError
from test_public_scripted_opponent import fixture, packet, spawn
from test_training_readiness_v2 import branches, floors, sha

from clasher.rl.readiness_execution import CaptureBinding, ExecutionPlan
from clasher.rl.readiness_tier_b import (
    CONDITIONS,
    ROLES,
    PolicyRanker,
    PolicyRootRecord,
    Stratum,
    TierBProtocol,
    TierBReport,
    evaluate_tier_b,
    policy_candidates,
    rank_policy_plays,
    representative_allocation,
    tier_b_branch_plan,
    tier_b_upper_bound,
)
from clasher.rl.readiness_tier_b_probes import (
    probe_candidates,
    probe_matches,
    probe_report,
)
from clasher.rl.training_readiness_v2 import (
    Candidate,
    Family,
    MechanismReview,
    Protocol,
)

DECK_IDS = ("giant_beatdown", "giant_control", "hog_control", "hog_cycle")


def candidates():
    return tuple(
        Candidate(role=role, action_id=action, card_token=token, public_score=-1.0)
        for role, action, token in zip(ROLES, (0, 2304, 576, 2), (2, 0, 3, 2))
    )


def tb_family(i, owner):
    return Family(
        family_id=f"tb-{i}",
        independence_id=f"tb-game-{i}",
        root_sha256=sha(("tb-root", i)),
        public_packet_sha256=sha(("tb-public", i)),
        root_owner=owner,
        role="fresh_acceptance",
        candidates=candidates(),
        original_recommendation=2304,
    )


def record(family, probe=None):
    return PolicyRootRecord(
        family_id=family.family_id,
        checkpoint_sha256=sha("checkpoint"),
        policy_contract_sha256=sha("contract"),
        public_packet_sha256=family.public_packet_sha256,
        policy_packet_sha256=sha(("policy", family.family_id)),
        root_tick=400,
        original_recommendation=2304,
        original_log_prob=-0.5,
        wait_log_prob=-0.5,
        candidate_actions={c.role: c.action_id for c in family.candidates},
        candidate_log_probs={
            "immediate_play": -1.0,
            "wait": -0.5,
            "alternate_card": -2.0,
            "displaced_placement": -3.0,
        },
        legal_play_count=100,
        probe_kind=probe,
    )


def strata(block="representative"):
    if block == "representative":
        return tuple(
            Stratum(
                family_id=f"tb-{i}",
                deck_id=deck,
                phase=phase,
                root_owner=seat,
                opponent="policy",
            )
            for i, (deck, phase, seat) in enumerate(representative_allocation(DECK_IDS))
        )
    kinds = ("lane_choice", "building_pull", "log_pushback")
    return tuple(
        Stratum(
            family_id=f"tb-{i}",
            deck_id=DECK_IDS[i % 4],
            phase="middle",
            root_owner=i % 2,
            opponent="script:balanced",
            probe_kind=kinds[i % 3],
        )
        for i in range(6)
    )


def tb_protocol(block="representative", *, drop=(), status="frozen", **kw):
    cells = strata(block)
    families = tuple(
        tb_family(i, s.root_owner) for i, s in enumerate(cells) if i not in drop
    )
    probe = {s.family_id: s.probe_kind for s in cells}
    values = {
        "attempt_id": "synthetic-tier-b",
        "block_kind": block,
        "status": status,
        "family_count": len(cells),
        "minimum_nonwait_informative": 15 if block == "representative" else None,
        "checkpoint_sha256": sha("checkpoint"),
        "policy_contract_sha256": sha("contract"),
        "tier_a_protocol_sha256": sha("tier-a"),
        "source_pins": {"source": sha("source")},
        "config_sha256": sha("config"),
        "generator_sha256": sha("generator"),
        "floors": floors(),
        "strata": cells,
        "families": families,
        "policy_roots": tuple(record(f, probe[f.family_id]) for f in families),
        "generation_failures": tuple(f"tb-{i}: no_eligible_root" for i in drop),
    }
    values.update(kw)
    return TierBProtocol(**values)


def uninformative_after(k):
    """Roots with index >= k make every non-wait candidate equal."""

    def custom(f, engine, role, index, score, margin):
        if int(f.family_id.split("-")[1]) >= k and role != "wait":
            return 1.0, 0.0
        return score, margin

    return custom


# --- Stratification -------------------------------------------------------


def test_representative_allocation_balances_deck_phase_and_seat():
    cells = representative_allocation(DECK_IDS)
    assert len(cells) == 30
    assert Counter(seat for _, _, seat in cells) == {0: 15, 1: 15}
    assert sorted(Counter(deck for deck, _, _ in cells).values()) == [7, 7, 8, 8]
    for phase in ("early", "middle", "double_elixir"):
        rows = [c for c in cells if c[1] == phase]
        assert Counter(seat for _, _, seat in rows) == {0: 5, 1: 5}
        for seat in (0, 1):
            assert {d for d, p, s in rows if s == seat} == set(DECK_IDS)
    assert cells == representative_allocation(DECK_IDS)  # deterministic


@pytest.mark.parametrize(
    "decks,allocation",
    [
        (("only",), (("early", 10), ("middle", 10), ("double_elixir", 10))),
        (DECK_IDS, (("early", 11), ("middle", 10), ("double_elixir", 9))),
        (DECK_IDS, (("early", 12), ("middle", 10), ("double_elixir", 10))),
        (DECK_IDS, (("early", 10), ("early", 10), ("middle", 10))),
    ],
)
def test_invalid_representative_allocations_are_rejected(decks, allocation):
    with pytest.raises(ValueError):
        representative_allocation(decks, allocation)


def test_protocol_rejects_unbalanced_or_resized_representative_blocks():
    cells = list(strata())
    cells[0] = cells[0].model_copy(update={"root_owner": 1 - cells[0].root_owner})
    with pytest.raises(ValidationError, match="balance seats"):
        tb_protocol(strata=tuple(cells), families=(), policy_roots=(), status="draft")
    with pytest.raises(ValidationError, match="30 roots"):
        tb_protocol(minimum_nonwait_informative=16, status="draft", families=(), policy_roots=())
    with pytest.raises(ValidationError, match="one distinct declared stratum"):
        tb_protocol(family_count=32, status="draft", families=(), policy_roots=())
    probe_cells = strata("targeted_probe")
    with pytest.raises(ValidationError, match="probe selections"):
        tb_protocol(
            strata=tuple(
                s.model_copy(update={"family_id": c.family_id})
                for s, c in zip(probe_cells * 5, strata())
            ),
            status="draft",
            families=(),
            policy_roots=(),
        )
    with pytest.raises(ValidationError, match="no coverage threshold"):
        tb_protocol("targeted_probe", minimum_nonwait_informative=3)


def test_frozen_protocol_requires_every_root_captured_or_retained_as_failure():
    tb_protocol(drop=(3,))
    with pytest.raises(ValidationError, match="captured or retained"):
        tb_protocol(drop=(3,), generation_failures=())
    with pytest.raises(ValidationError, match="uncaptured root"):
        tb_protocol(generation_failures=("tb-1: no_eligible_root",))
    with pytest.raises(ValidationError, match="Tier A reference"):
        tb_protocol(tier_a_protocol_sha256=None)
    p = tb_protocol()
    bad = p.policy_roots[0].model_copy(update={"original_recommendation": 0})
    with pytest.raises(ValidationError, match="policy ranking differs"):
        tb_protocol(policy_roots=(bad,) + p.policy_roots[1:])


def test_development_repetition_roots_cannot_enter_tier_b():
    p = tb_protocol()
    dev_root = floors().repetitions[0].root_sha256
    family = p.families[0].model_copy(update={"root_sha256": dev_root})
    with pytest.raises(ValidationError, match="development repetition"):
        tb_protocol(families=(family,) + p.families[1:])


# --- Policy-conditioned candidates ----------------------------------------


def mask_for(legal):
    mask = np.zeros(2306, dtype=bool)
    mask[list(legal)] = True
    mask[2304] = True
    return mask


def test_ranking_orders_by_log_probability_with_lowest_id_tie_break():
    logp = np.full(2306, -1e9)
    mask = mask_for([5, 3, 700, 9])
    logp[[5, 3, 700, 9, 2304]] = [-1.0, -1.0, -0.5, -4.0, -0.1]
    plays = rank_policy_plays(logp, mask)
    assert [p.action_id for p in plays] == [700, 3, 5, 9]
    assert PolicyRanker(logp, mask).decide().action_id == 2304


@pytest.mark.parametrize("bad", ["nan", "ability", "positive", "shape", "nowait"])
def test_ranking_rejects_invalid_policy_distributions(bad):
    logp = np.full(2306, -1e9)
    mask = mask_for([1, 2])
    logp[[1, 2, 2304]] = -1.0
    if bad == "nan":
        logp[1] = np.nan
    elif bad == "ability":
        mask[2305] = True
        logp[2305] = -1.0
    elif bad == "positive":
        logp[2] = 0.5
    elif bad == "shape":
        logp = logp[:-1]
    else:
        mask[2304] = False
    with pytest.raises(ValueError):
        rank_policy_plays(logp, mask)


def real_root(owner=0):
    battle, builder, _bot = fixture(owner)
    view = packet(battle, builder, owner)
    from clasher.rl.public_action_mask import (
        PublicActionMaskBuilder,
        PublicActionMaskInput,
    )

    mask = PublicActionMaskBuilder(builder).build(
        PublicActionMaskInput.from_confidence_observation(view)
    )
    return battle, builder, view, mask


def test_policy_candidates_follow_frozen_policy_ranking_on_a_real_packet():
    _battle, _builder, view, mask = real_root()
    rng = np.random.default_rng(3)
    logp = np.where(mask, -rng.uniform(1, 20, 2306), -1e9)
    logp[2304] = -0.01  # the policy's own mode is wait
    found, recommendation = policy_candidates(logp, mask, view)
    plays = rank_policy_plays(logp, mask)
    first, _, other, displaced = found
    assert [c.role for c in found] == list(ROLES)
    assert first.action_id == plays[0].action_id
    assert first.public_score == pytest.approx(plays[0].score)
    ids = view.observation.hand_ids
    assert other.card_token != first.card_token
    assert other.action_id == next(
        p.action_id for p in plays if ids[p.action_id // 576] != ids[first.action_id // 576]
    )
    assert displaced.action_id // 576 == first.action_id // 576
    assert recommendation.action_id == 2304
    # Same inputs give the same frozen candidates.
    assert policy_candidates(logp, mask, view)[0] == found


def test_policy_candidates_retain_ineligibility_instead_of_substituting():
    battle, builder, view, mask = real_root()
    battle.players[0].elixir = 2  # only Skeletons remains affordable
    view = packet(battle, builder)
    from clasher.rl.public_action_mask import (
        PublicActionMaskBuilder,
        PublicActionMaskInput,
    )

    mask = PublicActionMaskBuilder(builder).build(
        PublicActionMaskInput.from_confidence_observation(view)
    )
    logp = np.where(mask, -3.0, -1e9)
    with pytest.raises(ValueError, match="ineligible root"):
        policy_candidates(logp, mask, view)


def test_lane_choice_probe_uses_the_opposite_lane_for_the_displaced_role():
    battle, builder, view, mask = real_root()
    logp = np.where(mask, -10.0, -1e9)
    hog = battle.players[0].hand.index("HogRider")
    left = hog * 576 + 13 * 18 + 3
    logp[left] = -0.2
    logp[hog * 576 + 13 * 18 + 4] = -0.3  # nearby same lane is not a lane change
    right = hog * 576 + 13 * 18 + 14
    logp[right] = -0.4
    assert probe_matches("lane_choice", view, builder.token_names)
    found, _ = policy_candidates(
        logp, mask, view, probe_kind="lane_choice", token_names=builder.token_names
    )
    assert found[0].action_id == left and found[3].action_id == right


def test_building_pull_probe_requires_a_visible_building_targeter():
    battle, builder, view, mask = real_root()
    plays = PolicyRanker(np.where(mask, -1.0, -1e9), mask).ranked_plays()
    with pytest.raises(ValueError, match="pattern absent"):
        probe_candidates("building_pull", plays, view, builder.token_names)
    spawn(battle, "HogRider", 1, (3.5, 11.5))
    view = packet(battle, builder)
    found = probe_candidates("building_pull", plays, view, builder.token_names)
    cannon = battle.players[0].hand.index("Cannon")
    assert found[0].action_id // 576 == cannon


# --- Decisions -------------------------------------------------------------


def test_fifteen_informative_roots_pass_with_the_block_own_bound():
    p = tb_protocol()
    report = evaluate_tier_b(p, branches(p, uninformative_after(15)))
    assert report.status == "passed" and report.informative_families == 15
    assert report.representative_failure_upper_bound == pytest.approx(tier_b_upper_bound(30))
    # Tier A's 32-family bound is never quoted for this block.
    assert report.representative_failure_upper_bound != pytest.approx(1 - 0.05 ** (1 / 32))
    assert report.population_interpretation == "representative_sample"
    assert {s.key for s in report.strata} >= {"phase:early", "seat:0", "deck:hog_cycle"}


def test_fourteen_informative_roots_are_inconclusive():
    p = tb_protocol()
    report = evaluate_tier_b(p, branches(p, uninformative_after(14)))
    assert report.status == "inconclusive"
    assert any("fewer than 15" in r for r in report.reasons)
    assert report.representative_failure_upper_bound is None


def test_missing_roots_and_branches_stay_in_failure_accounting():
    p = tb_protocol(drop=(7,))
    report = evaluate_tier_b(p, branches(p))
    assert report.status == "inconclusive" and report.missing_roots == ("tb-7",)
    assert report.declared_roots == 30 and len(report.families) == 29
    cell = next(s for s in report.strata if s.key == f"seat:{p.strata[7].root_owner}")
    assert cell.missing == 1
    full = tb_protocol()
    rows = branches(full)[1:]
    report = evaluate_tier_b(full, rows)
    assert report.status == "inconclusive" and report.missing_roots == ("tb-0",)


def test_material_failure_and_repeated_class_harm_block():
    p = tb_protocol()

    def material(f, engine, role, index, score, margin):
        if f.family_id == "tb-2" and engine == "reference" and role == "immediate_play":
            return 0.5, 0.0
        if f.family_id == "tb-2" and engine == "reference" and role == "alternate_card":
            return 1.0, 0.0
        return score, margin

    report = evaluate_tier_b(p, branches(p, material))
    assert report.status == "blocked" and report.material_failures == 1

    def repeated(f, engine, role, index, score, margin):
        if int(f.family_id.split("-")[1]) < 4 and engine == "reference":
            # Tied scores; 1.5% mean margin regret, three of four continuations.
            if role == "immediate_play":
                return 1.0, (-0.02 if index < 3 else 0.0)
            if role == "alternate_card":
                return 1.0, 0.0
        return score, margin

    report = evaluate_tier_b(p, branches(p, repeated))
    assert report.material_failures == 0
    assert report.class_events["immediate_play"] == 4
    assert report.status == "blocked"
    assert "automatic repeated-class harm block" in report.reasons


def test_draft_and_unreviewed_events_cannot_pass_and_reviews_only_add_blocks():
    draft = tb_protocol(status="draft")
    assert evaluate_tier_b(draft, branches(draft)).status == "inconclusive"
    p = tb_protocol()

    def small(f, engine, role, index, score, margin):
        if f.family_id == "tb-5" and engine == "reference" and role == "immediate_play" and index == 0:
            return 0.5, 0.0
        if f.family_id == "tb-5" and engine == "reference" and role == "alternate_card":
            return 1.0, 0.0
        return score, margin

    rows = branches(p, small)
    report = evaluate_tier_b(p, rows)
    assert report.status == "inconclusive"
    assert "above-floor events require mechanism review" in report.reasons
    review = MechanismReview(
        family_id="tb-5",
        candidate_role="immediate_play",
        artifact_sha256=sha("review"),
        verdict="block",
        explanation="demonstrated exploit",
    )
    assert evaluate_tier_b(p, rows, (review,)).status == "blocked"
    clear = review.model_copy(update={"verdict": "no_additional_block"})
    assert evaluate_tier_b(p, rows, (clear,)).status == "passed"


def test_targeted_probes_block_or_find_nothing_but_never_pass():
    p = tb_protocol("targeted_probe")
    report = evaluate_tier_b(p, branches(p))
    assert report.status == "no_block_found"
    assert report.representative_failure_upper_bound is None
    assert report.population_interpretation == "none_targeted_probe"
    summary = probe_report(p, report)
    assert {f.probe_kind for f in summary.findings} == {"lane_choice", "building_pull", "log_pushback"}
    assert all(f.declared == 2 and not f.blocking for f in summary.findings)

    def material(f, engine, role, index, score, margin):
        if f.family_id == "tb-1" and engine == "reference" and role == "immediate_play":
            return 0.0, 0.0
        return score, margin

    blocked = evaluate_tier_b(p, branches(p, material))
    assert blocked.status == "blocked"
    finding = next(f for f in probe_report(p, blocked).findings if f.probe_kind == "building_pull")
    assert finding.blocking and finding.material_failures == 1
    with pytest.raises(ValidationError):
        TierBReport.model_validate({**report.model_dump(), "status": "passed"})
    rep = tb_protocol()
    with pytest.raises(ValueError, match="targeted-probe"):
        probe_report(rep, evaluate_tier_b(rep, branches(rep)))


def test_branch_provenance_must_match_the_frozen_tier_b_protocol():
    p = tb_protocol()
    other = tb_protocol(attempt_id="another")
    with pytest.raises(ValueError, match="provenance"):
        evaluate_tier_b(p, branches(other))
    plan = tier_b_branch_plan(p)
    assert len(plan) == 30 * 4 * 4 * 2
    assert {row["condition"] for row in plan} == set(CONDITIONS)


# --- Execution plan compatibility -----------------------------------------


def binding(family):
    from clasher.rl.readiness_execution import CAPTURE_FILES

    return CaptureBinding.model_construct(
        family_id=family.family_id,
        capture_path="/nonexistent",
        root_tick=400,
        input_hashes={name: sha(name) for name in CAPTURE_FILES},
        config_sha256=sha("config"),
        root_frame_sha256=sha(("frame", family.family_id)),
    )


def test_execution_plan_accepts_tier_b_only_under_its_purpose():
    p = tb_protocol()
    families = []
    captures = []
    for f in p.families:
        b = binding(f)
        families.append(f.model_copy(update={"root_sha256": b.root_sha256}))
        captures.append(b)
    p = tb_protocol(
        families=tuple(families),
        policy_roots=tuple(record(f) for f in families),
    )
    common = {
        "protocol": p,
        "captures": tuple(captures),
        "catalog_path": "/nonexistent",
        "catalog_sha256": sha("catalog"),
        "native_attestation_sha256": sha("native"),
        "source_pins": {"source": sha("source")},
    }
    plan = ExecutionPlan(purpose="tier_b_transfer", **common)
    restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
    assert isinstance(restored.protocol, TierBProtocol) and restored == plan
    with pytest.raises(ValidationError, match="Tier B"):
        ExecutionPlan(purpose="fresh_acceptance", **common)


def test_tier_a_plans_round_trip_unchanged_and_cannot_use_tier_b_purpose():
    from test_training_readiness_v2 import protocol as tier_a_protocol

    tier_a = tier_a_protocol()
    captures = []
    families = []
    for f in tier_a.families:
        b = binding(f)
        captures.append(b)
        families.append(f.model_copy(update={"root_sha256": b.root_sha256}))
    tier_a = Protocol.model_validate(
        {**tier_a.model_dump(), "families": [f.model_dump() for f in families]},
        strict=False,
    )
    common = {
        "protocol": tier_a,
        "captures": tuple(captures),
        "catalog_path": "/nonexistent",
        "catalog_sha256": sha("catalog"),
        "native_attestation_sha256": sha("native"),
        "source_pins": {"source": sha("source")},
    }
    plan = ExecutionPlan(purpose="fresh_acceptance", **common)
    text = plan.model_dump_json()
    restored = ExecutionPlan.model_validate_json(text)
    assert isinstance(restored.protocol, Protocol)
    assert restored.model_dump_json() == text
    assert restored.protocol.sha256 == tier_a.sha256
    with pytest.raises(ValidationError, match="Tier B"):
        ExecutionPlan(purpose="tier_b_transfer", **common)
