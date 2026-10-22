"""Exercise the serving path used by CPU and accelerator latency measurements."""
import math

import pytest
import torch

from bot.pretrain_v1 import featurize as F
from bot.pretrain_v1.model import PolicyV1
from bot.pretrain_v1.policy import Session
from bot.pretrain_v1.tests.test_featurize import rec


@pytest.mark.parametrize('device', ['cpu', 'mps'])
def test_session_device_play_history_and_stale(device):
    if device == 'mps' and not torch.backends.mps.is_available():
        pytest.skip('MPS unavailable on this host')
    torch.set_num_threads(1)
    torch.manual_seed(1)
    model = PolicyV1(d=24, layers=1, heads=3, ffn=48).eval().to(device)
    model.gate_bias.fill_(-100)  # Exercise conditional tile sampling on the selected device.
    sess = Session(model, 1)
    play = sess.step(rec(100))
    assert play.status == 'play' and 0 <= play.action < F.NOOP
    assert math.isfinite(play.value) and math.isfinite(play.p_wait)
    sess.accepted(play)
    busy = sess.step(rec(105))
    assert busy.status == 'forced' and busy.action == F.NOOP
    # The unchanged hand releases the command as rejected after the observation timeout.
    stale = sess.step(rec(200))
    assert stale.status == 'stale' and stale.action == F.NOOP
    assert sess.last_feat['slot_ok'].any()


def test_benchmark_loader_counts_monotonic_polls(tmp_path):
    import json
    from bot.pretrain_v1.bench_device import games
    a, b = tmp_path/'a', tmp_path/'b'
    a.mkdir()
    b.mkdir()
    (a/'records.jsonl').write_text(''.join(json.dumps(rec(t))+'\n' for t in [100, 100, 105]))
    (b/'records.jsonl').write_text(''.join(json.dumps(rec(t))+'\n' for t in [200, 205]))
    assert [[r['tick'] for r in g] for g in games(tmp_path, 4)] == [[100, 105], [200, 205]]


def test_benchmark_containment_resolves_traversal_and_symlinks(tmp_path):
    from bot.pretrain_v1.bench_selected import contained
    root = tmp_path/'bench'
    root.mkdir()
    outside = tmp_path/'outside'
    outside.mkdir()
    (root/'link').symlink_to(outside, target_is_directory=True)
    assert contained(root/'results', root) == root/'results'
    for path in [root/'..'/'outside', root/'link'/'results']:
        with pytest.raises(ValueError, match='outside benchmark'):
            contained(path, root)


def test_selected_runner_refuses_existing_attempt(tmp_path, monkeypatch):
    from pathlib import Path
    from bot.pretrain_v1 import bench_selected
    root = tmp_path/'clasher-pretrain-bench'
    root.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.chdir(root)
    ck, out, records = root/'anchor.pt', root/'result', root/'records'
    ck.write_bytes(b'checkpoint')
    out.mkdir()
    records.mkdir()
    stale = out/'cpu-t1.json'
    stale.write_text('{"polls":3000}')
    mf = _records_manifest(records)
    with pytest.raises(FileExistsError):
        bench_selected.main([str(ck), str(out), str(records), '--records-manifest', str(mf)])
    assert stale.read_text() == '{"polls":3000}'


def test_selected_runner_rejects_mismatched_result(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from bot.pretrain_v1 import bench_selected
    root = tmp_path/'clasher-pretrain-bench'
    root.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.chdir(root)
    ck, out, records = root/'anchor.pt', root/'result', root/'records'
    ck.write_bytes(b'checkpoint')
    records.mkdir()
    def run(cmd, **kwargs):
        Path(cmd[cmd.index('--out')+1]).write_text('{"polls":3000,"checkpoint_sha256":"old"}')
    monkeypatch.setattr(bench_selected.subprocess, 'run', run)
    mf = _records_manifest(records)
    with pytest.raises(RuntimeError, match='invalid benchmark result'):
        bench_selected.main([str(ck), str(out), str(records), '--records-manifest', str(mf)])
    assert not json.loads((out/'attempt.json').read_text())['complete']


def _records_manifest(records):
    import hashlib, json
    p = records/'game'
    p.mkdir()
    raw = json.dumps(rec(100)).encode()+b'\n'
    (p/'records.jsonl').write_bytes(raw)
    mf = records.parent/'records-manifest.json'
    mf.write_text(json.dumps({'game/records.jsonl': hashlib.sha256(raw).hexdigest()}))
    return mf


def test_record_manifest_binds_exact_set_and_bytes(tmp_path):
    from bot.pretrain_v1.bench_contract import record_payloads
    root = tmp_path/'records'
    root.mkdir()
    mf = _records_manifest(root)
    assert len(record_payloads(root, mf)) == 1
    extra = root/'extra'
    extra.mkdir()
    (extra/'records.jsonl').write_text('{}')
    with pytest.raises(ValueError, match='file set'):
        record_payloads(root, mf)
    (extra/'records.jsonl').unlink()
    (root/'game'/'records.jsonl').write_text('{}')
    with pytest.raises(ValueError, match='bytes changed'):
        record_payloads(root, mf)
    mf.write_text('{}')
    with pytest.raises(ValueError, match='nonempty'):
        record_payloads(root, mf)


def test_go_gate_requires_matching_review_revision(tmp_path):
    import hashlib, importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[3]/'reports/bot/pretrain-v1/sweep/bench_wait_05.py'
    spec = importlib.util.spec_from_file_location('waiter_test', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    revision = '1'*40
    with pytest.raises(ValueError, match='at least one'):
        m.verify_go({'verdict':'GO','revision':revision,'reviews':[]}, revision)
    report = tmp_path/'review.txt'
    for reviewed, verdict in [('0'*40,'GO'), (revision,'NO-GO'), (revision,'GO')]:
        report.write_text(f'Reviewed-Revision: {reviewed}\nVerdict: {verdict}\n')
        receipt = dict(verdict='GO', revision=revision, reviews=[dict(path=str(report),
                       sha256=hashlib.sha256(report.read_bytes()).hexdigest())])
        if reviewed == revision and verdict == 'GO':
            m.verify_go(receipt, revision)
        else:
            with pytest.raises(ValueError, match='GO review'):
                m.verify_go(receipt, revision)


def test_selected_runner_does_not_follow_lock_symlink(tmp_path, monkeypatch):
    from pathlib import Path
    from bot.pretrain_v1 import bench_selected
    root = tmp_path/'clasher-pretrain-bench'
    root.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.chdir(root)
    ck, records = root/'anchor.pt', root/'records'
    ck.write_bytes(b'checkpoint')
    records.mkdir()
    outside = tmp_path/'outside-lock'
    (root/'selected-benchmark.lock').symlink_to(outside)
    with pytest.raises(OSError):
        bench_selected.main([str(ck), str(root/'result'), str(records),
                             '--records-manifest', str(root/'missing.json')])
    assert not outside.exists()
    assert not (root/'result').exists()


def test_selected_runner_refuses_nonregular_lock(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    from bot.pretrain_v1 import bench_selected
    root = tmp_path/'clasher-pretrain-bench'
    root.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.chdir(root)
    ck, records = root/'anchor.pt', root/'records'
    ck.write_bytes(b'checkpoint')
    records.mkdir()
    os.mkfifo(root/'selected-benchmark.lock')
    with pytest.raises(ValueError, match='regular file'):
        bench_selected.main([str(ck), str(root/'result'), str(records),
                             '--records-manifest', str(root/'missing.json')])
    assert not (root/'result').exists()
