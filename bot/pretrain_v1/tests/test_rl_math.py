import pytest
import torch

from bot.pretrain_v1 import featurize as F
from bot.pretrain_v1.rl_math import gae, joint_kl, joint_terms, normalize_advantages, ppo_sums


def full_joint(gate, tiles):
    g, t = gate.softmax(-1), tiles.softmax(-1)
    return torch.cat([g[:, :1], (g[:, 1:, None]*t).flatten(1)], -1)


def test_kl_entropy_and_logp_equal_full_enumeration():
    torch.manual_seed(12)
    g, t = torch.randn(4, 5), torch.randn(4, 4, F.NTILE)
    ag, at = torch.randn_like(g), torch.randn_like(t)
    p, q = full_joint(g, t), full_joint(ag, at)
    actions = torch.tensor([F.NOOP, 0, F.NTILE+2, 4*F.NTILE-1])
    lp, entropy = joint_terms(g, t, actions, torch.full((4,), 5))
    indices = torch.where(actions == F.NOOP, 0, actions+1)
    assert torch.allclose(lp, p.log().gather(1, indices[:, None])[:, 0], atol=2e-6)
    assert torch.allclose(entropy, -(p*p.log()).sum(-1), atol=2e-6)
    assert torch.allclose(joint_kl(g, t, ag, at), (p*(p.log()-q.log())).sum(-1), atol=2e-6)
    with pytest.raises(ValueError, match='five ticks'):
        joint_terms(g, t, actions, torch.full((4,), 10))


def test_forced_mask_is_certain_wait_and_zero_kl():
    g = torch.tensor([[0., -1e9, -1e9, -1e9, -1e9]], requires_grad=True)
    t = torch.full((1, 4, F.NTILE), -1e9, requires_grad=True)
    lp, entropy = joint_terms(g, t, torch.tensor([F.NOOP]), torch.tensor([5]))
    kl = joint_kl(g, t, g.detach(), t.detach())
    assert torch.equal(lp, torch.zeros(1)) and torch.equal(entropy, torch.zeros(1))
    assert torch.equal(kl, torch.zeros(1))
    (lp+entropy+kl).sum().backward()
    assert torch.isfinite(g.grad).all() and torch.isfinite(t.grad).all()


def test_real_terminal_resets_but_unfinished_tail_bootstraps():
    rewards = torch.tensor([0., 1., 0.])
    values = torch.tensor([.2, .3, .4])
    adv, ret = gae(rewards, values, torch.tensor([False, True, False]), .8, lam=1.)
    assert torch.allclose(ret, torch.tensor([1., 1., .8]))
    assert torch.allclose(adv, ret-values)


def test_microbatch_accumulation_preserves_effective_objective_gradient():
    torch.manual_seed(1)
    x = torch.randn(9, requires_grad=True)
    actor = torch.tensor([True, True, False, True, False, True, True, True, True])
    adv = normalize_advantages(torch.randn(9), actor)
    old, returns = torch.zeros(9), torch.randn(9)
    def loss(v, a, ad, o, r):
        s = ppo_sums(v, o, ad, v.tanh(), r, v.square(), v.square(), a)
        return (s['policy']-.001*s['entropy']+.05*s['kl'])/actor.sum() + .5*s['value']/len(x)
    whole = loss(x, actor, adv, old, returns)
    whole.backward(); expected = x.grad.clone(); x.grad.zero_()
    for start in range(0, len(x), 2):
        end = start+2
        loss(x[start:end], actor[start:end], adv[start:end], old[start:end], returns[start:end]).backward()
    assert torch.allclose(x.grad, expected, atol=1e-7)
