"""Read-only cooperative notification tests; no owner leases or processes."""
import json
from pathlib import Path

import pytest

from bot.pretrain_v1 import lease_adapter as L


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(L.S, 'STATE_ROOT', str(tmp_path))
    clock = [0.]
    path = tmp_path/'job.stop'
    adapter = L.LeaseStopAdapter(stop_file=path, token='a'*32,
        stop_by_utc='2026-10-25T07:00:00Z', boot='fixture-boot', wall_time=lambda: clock[0])
    record = dict(name='job', token='a'*32, boot='fixture-boot', reason='reclaim', utc='2026-10-22T20:00:00Z')
    return adapter, path, record, clock


def test_own_hosts_independent_and_partial_env_refused():
    assert L.LeaseStopAdapter.from_environment({}) is None
    with pytest.raises(L.LeaseAdapterError, match='partial'):
        L.LeaseStopAdapter.from_environment({'CLASHER_LEASE_JOB': 'a'*32})


def test_reopen_replaced_notification_and_latch_without_writing(tmp_path, monkeypatch):
    a, path, r, _ = fixture(tmp_path, monkeypatch)
    assert a.poll() is None
    path.write_text(json.dumps(r))
    original = path.read_bytes()
    assert a.poll() == 'reclaim' and path.read_bytes() == original
    path.unlink()
    assert a.poll() == 'reclaim'
    b, path, r, _ = fixture(tmp_path, monkeypatch)
    wrong = dict(r, token='b'*32)
    path.write_text(json.dumps(wrong))
    with pytest.raises(L.LeaseAdapterError): b.poll()
    replacement = path.with_suffix('.tmp'); replacement.write_text(json.dumps(r)); replacement.replace(path)
    assert b.poll() == 'reclaim'


@pytest.mark.parametrize('bad', ['{', '[]', '{}', '{"reason":NaN}', 'x'*65537])
def test_malformed_own_notification_fails_closed(tmp_path, monkeypatch, bad):
    a, path, _, _ = fixture(tmp_path, monkeypatch)
    path.write_text(bad)
    with pytest.raises(L.LeaseAdapterError): a.poll()


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity', '1e999'])
@pytest.mark.parametrize('shadowed', [False, True])
def test_nonfinite_unused_notification_field_fails_closed(tmp_path, monkeypatch, constant, shadowed):
    a, path, record, _ = fixture(tmp_path, monkeypatch)
    suffix = ', "unused": null' if shadowed else ''
    path.write_text(json.dumps(record)[:-1]+', "unused": {"nested": ['+constant+']}'+suffix+'}')
    before = path.read_bytes()
    with pytest.raises(L.LeaseAdapterError):
        a.poll()
    assert a.reason is None and path.read_bytes() == before


@pytest.mark.parametrize('key,value', [('token','b'*32), ('boot','other'), ('name','other'), ('reason',''), ('utc','bad')])
def test_notification_generation_and_schema(tmp_path, monkeypatch, key, value):
    a, path, record, _ = fixture(tmp_path, monkeypatch)
    record[key] = value; path.write_text(json.dumps(record))
    with pytest.raises(L.LeaseAdapterError): a.poll()


def test_stop_bound_and_symlink_and_allowed_root(tmp_path, monkeypatch):
    a, path, record, clock = fixture(tmp_path, monkeypatch)
    clock[0] = a.stop_by
    assert a.poll() == 'lease scheduled stop bound'
    a, path, record, _ = fixture(tmp_path, monkeypatch)
    target = tmp_path/'other'; target.write_text(json.dumps(record)); path.symlink_to(target)
    with pytest.raises(L.LeaseAdapterError): a.poll()
    with pytest.raises(L.LeaseAdapterError, match='outside'):
        L.LeaseStopAdapter(stop_file='/tmp/job.stop', token='a'*32, stop_by_utc='2026-10-25T07:00:00Z')
