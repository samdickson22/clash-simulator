import torch
from torch.nn import functional as F

from clasher.rl.imitation_objective import (
    ABILITY_ACTION,
    BUILDING_KIND,
    NO_OP_ACTION,
    SPELL_KIND,
    TROOP_KIND,
    SpatialImitationConfig,
    TokenSpatialSemantics,
    factorized_spatial_imitation_loss,
    imitation_metric_sums,
)


def _semantics(
    radii: list[float],
    masses: list[float],
    kinds: list[int],
) -> TokenSpatialSemantics:
    return TokenSpatialSemantics(
        radius_tiles=torch.tensor(radii, dtype=torch.float32),
        neighbor_mass=torch.tensor(masses, dtype=torch.float32),
        kind=torch.tensor(kinds, dtype=torch.long),
    )


def test_zero_smoothing_factorization_equals_exact_joint_cross_entropy():
    generator = torch.Generator().manual_seed(17)
    logits = torch.randn((3, 2306), generator=generator)
    factorized_logits = logits.clone().requires_grad_(True)
    exact_logits = logits.clone().requires_grad_(True)
    masks = torch.zeros_like(logits, dtype=torch.bool)
    masks[0, 576 + 20 : 576 + 25] = True
    masks[0, NO_OP_ACTION] = True
    masks[1, NO_OP_ACTION] = True
    masks[2, NO_OP_ACTION] = True
    masks[2, ABILITY_ACTION] = True
    targets = torch.tensor([576 + 22, NO_OP_ACTION, ABILITY_ACTION])
    hand_ids = torch.tensor(
        [[1, 2, 3, 4, 0], [1, 2, 3, 4, 0], [1, 2, 3, 4, 0]]
    )
    semantics = _semantics(
        [0.0] * 5,
        [0.0] * 5,
        [0] * 5,
    )

    factorized = factorized_spatial_imitation_loss(
        factorized_logits,
        targets,
        masks,
        hand_ids,
        semantics,
        config=SpatialImitationConfig(
            troop_neighbor_mass=0.0,
            spell_neighbor_mass=0.0,
        ),
    )
    exact = F.cross_entropy(exact_logits.masked_fill(~masks, -torch.inf), targets)

    torch.testing.assert_close(factorized.total, exact)
    torch.testing.assert_close(factorized.exact_joint, exact)
    factorized.total.backward()
    exact.backward()
    torch.testing.assert_close(factorized_logits.grad, exact_logits.grad)


def test_spatial_smoothing_never_assigns_mass_to_illegal_tiles():
    logits = torch.full((1, 2306), -4.0)
    masks = torch.zeros_like(logits, dtype=torch.bool)
    masks[0, 0] = True
    masks[0, 1] = True
    masks[0, 18] = True
    masks[0, NO_OP_ACTION] = True
    targets = torch.tensor([0])
    hand_ids = torch.tensor([[1, 0, 0, 0, 0]])
    semantics = _semantics(
        [0.0, 1.5],
        [0.0, 0.4],
        [0, TROOP_KIND],
    )
    baseline = factorized_spatial_imitation_loss(
        logits,
        targets,
        masks,
        hand_ids,
        semantics,
    )
    changed_illegal = logits.clone()
    changed_illegal[0, 19] = 1_000.0
    candidate = factorized_spatial_imitation_loss(
        changed_illegal,
        targets,
        masks,
        hand_ids,
        semantics,
    )

    torch.testing.assert_close(candidate.total, baseline.total)
    torch.testing.assert_close(candidate.location, baseline.location)


def test_metrics_separate_exact_type_distance_and_mechanic_tolerance():
    targets = torch.tensor(
        [5 + 5 * 18, 576 + 5 + 5 * 18, 1152 + 5 + 5 * 18, NO_OP_ACTION]
    )
    predictions = torch.tensor(
        [6 + 5 * 18, 576 + 6 + 5 * 18, 1152 + 7 + 5 * 18, NO_OP_ACTION]
    )
    logits = torch.full((4, 2306), -10.0)
    masks = torch.zeros_like(logits, dtype=torch.bool)
    for row, (target, prediction) in enumerate(
        zip(targets.tolist(), predictions.tolist(), strict=True)
    ):
        masks[row, target] = True
        masks[row, prediction] = True
        masks[row, NO_OP_ACTION] = True
        logits[row, prediction] = 10.0
    hand_ids = torch.tensor(
        [[1, 0, 0, 0, 0], [0, 2, 0, 0, 0], [0, 0, 3, 0, 0], [0, 0, 0, 0, 0]]
    )
    semantics = _semantics(
        [0.0, 1.0, 0.0, 2.0],
        [0.0, 0.15, 0.0, 0.25],
        [0, TROOP_KIND, BUILDING_KIND, SPELL_KIND],
    )

    sums = imitation_metric_sums(logits, targets, masks, hand_ids, semantics)

    assert int(sums["samples"]) == 4
    assert int(sums["exact_correct"]) == 1
    assert int(sums["type_correct"]) == 4
    assert int(sums["correct_slot"]) == 3
    assert int(sums["within_1_tile"]) == 2
    assert int(sums["within_2_tiles"]) == 3
    assert int(sums["mechanic_tolerant_correct"]) == 3
    assert float(sums["correct_slot_distance_sum"]) == 4.0
    assert int(sums["troop_tolerant_correct"]) == 1
    assert int(sums["building_tolerant_correct"]) == 0
    assert int(sums["spell_tolerant_correct"]) == 1


def test_special_actions_have_no_location_loss():
    logits = torch.zeros((2, 2306))
    masks = torch.zeros_like(logits, dtype=torch.bool)
    masks[:, NO_OP_ACTION] = True
    masks[1, ABILITY_ACTION] = True
    targets = torch.tensor([NO_OP_ACTION, ABILITY_ACTION])
    hand_ids = torch.zeros((2, 5), dtype=torch.long)
    semantics = _semantics([0.0], [0.0], [0])

    loss = factorized_spatial_imitation_loss(
        logits,
        targets,
        masks,
        hand_ids,
        semantics,
    )

    assert float(loss.location) == 0.0
