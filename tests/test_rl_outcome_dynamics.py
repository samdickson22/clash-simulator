from types import SimpleNamespace

import numpy as np
import torch

from clasher.rl.outcome_model import ActorOutcomeHead, actor_outcome_loss
from scripts.train_hog26_actor_outcome import extract_actor_features


def test_dynamics_change_only_overtime_margins_and_preserve_wdl():
    plain = ActorOutcomeHead(18, hidden_size=4, margin_residual_scale=0.5)
    dynamic = ActorOutcomeHead(19, hidden_size=4, margin_residual_scale=0.5,
                               margin_dynamics="overtime-damage-race-v1")
    dynamic.load_state_dict(plain.state_dict())
    public = torch.rand(3, 18)
    public[:, 4] = torch.tensor([0.0, 1.0, 1.0])
    features = torch.cat([torch.tensor([[0.1], [0.2], [-0.3]]), public], dim=1)
    before = plain(public)
    raw = dynamic(features, apply_margin_dynamics=False)
    after = dynamic(features)
    assert torch.equal(before.outcome_logits, after.outcome_logits)
    assert torch.equal(before.terminal_tower_margin, raw.terminal_tower_margin)
    assert torch.equal(after.terminal_tower_margin[:1], before.terminal_tower_margin[:1])
    current = (public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3
    torch.testing.assert_close(after.terminal_tower_margin[1:], (current + features[:, 0]).clamp(-1, 1)[1:])


def test_integrated_dynamics_features_ignore_labels_and_future_rows():
    public = np.zeros((40, 18), dtype=np.float32)
    public[:, 0] = np.linspace(0.6, 0.9, 40)
    public[:, 1] = 1 - public[:, 0]
    public[:, 4] = 1
    public[:, 8:14] = 1
    public[:, 11] = np.linspace(1, 0.2, 40)
    corpus = SimpleNamespace(arrays={"global_features": public, "final_outcomes": np.ones(40)},
                             episode_offsets=np.array([0, 40]))
    def extract():
        return extract_actor_features(torch.nn.Identity(), corpus, device=torch.device("cpu"),
                                      sequence_steps=8, feature_set="public-global-dynamics")
    first = extract()
    assert first.shape == (40, 19)
    assert torch.equal(first[:, -18:], torch.from_numpy(public))
    corpus.arrays["final_outcomes"] *= -1
    public[25:, 8:14] = 0.1
    assert torch.equal(first[:25], extract()[:25])


def test_absolute_margin_loss_uses_the_declared_target_metric():
    head = ActorOutcomeHead(18, hidden_size=2)
    prediction = head(torch.zeros(1, 18))
    absolute = actor_outcome_loss(prediction, torch.zeros(1), torch.ones(1), margin_loss="absolute")
    huber = actor_outcome_loss(prediction, torch.zeros(1), torch.ones(1))
    assert absolute.tower_margin_loss.item() == 1.0
    assert huber.tower_margin_loss.item() == 0.5
