"""Exercise cancellation checkpoints and generation validation with real torch state."""
import json
from pathlib import Path
import signal

import pytest
import torch

from bot.pretrain_v1.lease_stop import LeaseStop, LeaseStopped, atomic_write


def lease(tmp_path):
    value = LeaseStop.__new__(LeaseStop)
    value.out, value.seed = tmp_path, 2026102006
    value.path = tmp_path/'job.stop'
    value.name, value.token, value.boot = 'job', 'own-token', 'own-boot'
    value.signal_requested = False
    return value


def notify(value, **changes):
    notice = dict(name=value.name, token=value.token, boot=value.boot,
                  reason='reclaim', utc='2026-10-22T00:00:00Z')
    notice.update(changes)
    value.path.write_text(json.dumps(notice))


def test_disabled_without_opt_in(monkeypatch):
    monkeypatch.delenv('PV1_LEASE_STOP_ONLY', raising=False)
    assert LeaseStop.from_env('/does/not/matter', 1) is None


@pytest.mark.parametrize('changes', [dict(name='other'), dict(token='stale'), dict(boot='old'),
    dict(reason=''), dict(utc='invalid'), dict(utc='2026-10-22Z'), dict(utc='20261022Z'), dict(utc='2099-01-01T00:00:00Z')])
def test_wrong_or_malformed_generation_never_claims_reclaim(tmp_path, changes):
    value = lease(tmp_path)
    notify(value, **changes)
    with pytest.raises((RuntimeError, ValueError)):
        value.poll()
    assert not (tmp_path/'lease-exit.json').exists()


def test_signal_only_sets_request_and_unknown_signal_fails_closed(tmp_path):
    value = lease(tmp_path)
    value._signal(signal.SIGTERM, None)
    assert value.signal_requested and not (tmp_path/'lease-exit.json').exists()
    with pytest.raises(RuntimeError, match='without own durable'):
        value.poll()


def test_initialization_exit_has_no_checkpoint(tmp_path):
    value = lease(tmp_path)
    notify(value)
    with pytest.raises(LeaseStopped) as result:
        value.poll()
    assert result.value.code == 75
    receipt = json.loads((tmp_path/'lease-exit.json').read_text())
    assert receipt['initialization_without_model'] and receipt['consumed_optimizer_steps'] == 0
    assert receipt['checkpoint'] is None and not list(tmp_path.glob('*.pt'))


def test_completed_update_is_serialized_atomically(tmp_path):
    value = lease(tmp_path)
    model = torch.nn.Linear(2, 1)
    model.cfg = {'fixture': True}
    opt = torch.optim.AdamW(model.parameters(), lr=.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda step: 1/(step+1))
    before = {k: v.clone() for k, v in model.state_dict().items()}
    model(torch.tensor([[1., 2.]])).square().sum().backward()
    opt.step()
    sched.step()
    notify(value)
    with pytest.raises(LeaseStopped):
        value.poll(model, opt, sched, step=1, epoch=0, consumed_batches=1, phase='training')
    receipt = json.loads((tmp_path/'lease-exit.json').read_text())
    checkpoint = torch.load(tmp_path/receipt['checkpoint'], weights_only=False)
    assert receipt['status'] == 'cancelled-by-lease' and not receipt['admitted'] and not receipt['finished']
    assert checkpoint['progress']['consumed_optimizer_steps'] == 1
    assert checkpoint['scheduler']['last_epoch'] == sched.last_epoch
    assert checkpoint['optimizer']['param_groups'][0]['lr'] == opt.param_groups[0]['lr']
    assert all(torch.equal(checkpoint['model'][key], tensor) for key, tensor in model.state_dict().items())
    assert any(not torch.equal(before[key], tensor) for key, tensor in model.state_dict().items())
    assert not list(tmp_path.glob('.*.pt.*'))
    assert not (tmp_path/'best.pt').exists() and not (tmp_path/'summary.json').exists()


def test_failed_atomic_write_leaves_no_published_checkpoint(tmp_path):
    target = tmp_path/'checkpoint.pt'
    def fail(stream):
        stream.write(b'partial')
        raise OSError('disk full')
    with pytest.raises(OSError):
        atomic_write(target, fail)
    assert not target.exists() and not list(tmp_path.iterdir())


def test_calibration_uses_preserved_training_weights(tmp_path):
    value = lease(tmp_path)
    model = torch.nn.Linear(2,1)
    model.cfg = {'fixture': True}
    opt = torch.optim.AdamW(model.parameters(),lr=.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt,lambda _:1.)
    model(torch.tensor([[1.,2.]])).square().sum().backward()
    opt.step();sched.step()
    trained = {key:tensor.detach().cpu().clone() for key,tensor in model.state_dict().items()}
    with torch.no_grad():
        model.weight.zero_()
    notify(value)
    with pytest.raises(LeaseStopped):
        value.poll(model,opt,sched,step=1,epoch=0,consumed_batches=1,phase='calibration',model_state=trained)
    receipt = json.loads((tmp_path/'lease-exit.json').read_text())
    ck = torch.load(tmp_path/receipt['checkpoint'],weights_only=False)
    assert torch.equal(ck['model']['weight'],trained['weight'])
    assert ck['progress'] == receipt
    assert receipt['checkpoint'] in receipt['artifacts']
    assert receipt['model_state_origin'] == 'final-training-boundary'
