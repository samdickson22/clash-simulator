import torch

from scripts.hog26_phase_margin_diagnostic import PhaseMarginDiagnostic


def test_phase_loss_cannot_update_other_heads():
    model = PhaseMarginDiagnostic(20, 4, residual_scale=0.5, progress_power=0)
    state = torch.zeros(3, 20)
    state[:, -18] = torch.tensor([0.2, 0.5, 0.9])
    prediction = model(state).terminal_tower_margin
    prediction[2].backward()
    for index in range(2):
        for parameter in model.margin_trunk[index].parameters():
            assert parameter.grad is None or not parameter.grad.any()
    assert model.margin_trunk[2][-1].bias.grad.abs().sum() > 0


def test_routing_depends_only_on_public_progress():
    model = PhaseMarginDiagnostic(20, 4, residual_scale=0.5, progress_power=0)
    state = torch.zeros(4, 20)
    state[:, -18] = torch.tensor([0.0, 1 / 3, 2 / 3, 1.0])
    with torch.no_grad():
        for index, trunk in enumerate(model.margin_trunk):
            trunk[-1].bias.fill_(index - 1)
    expected = torch.tensor([-1.0, 0.0, 1.0, 1.0]).tanh() * 0.5
    torch.testing.assert_close(model(state).terminal_tower_margin, expected)
