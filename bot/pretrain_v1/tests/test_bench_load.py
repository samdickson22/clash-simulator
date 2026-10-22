import subprocess

import pytest

from bot.pretrain_v1 import bench_load as B

PS = '''0 0 0.0 0 kernel_task
10 1 0.1 74000 /opt/homebrew/bin/limactl hostagent --pidfile /Users/sam/.colima/_lima/colima-canvasdoc/ha.pid
11 1 170.5 1400000 /System/Library/Virtualization/com.apple.Virtualization.VirtualMachine
12 11 2.0 1000 guest-helper
13 1 250.0 9999999 /other/com.apple.Virtualization.VirtualMachine
'''


def fake_run(cmd, **kwargs):
    if cmd[0] == 'ps':
        return subprocess.CompletedProcess(cmd, 0, PS, '')
    output = ('n/Users/sam/.colima/_lima/colima-canvasdoc/disk\n' if cmd[2] == '11' else 'n/other/disk\n')
    return subprocess.CompletedProcess(cmd, 0, output, '')


def test_canvasdoc_vm_is_attributed_by_open_disk_and_children(monkeypatch):
    monkeypatch.setattr(B.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(B.subprocess, 'run', fake_run)
    load = B.CanvasdocLoad()
    load.sample(force=True)
    load.sample(force=True)
    d = load.report()
    assert d['complete'] and d['classification'] == 'shared-load' and not d['clean_result']
    assert d['vm_observed'] and d['cpu_percent_peak'] == 172.6 and d['rss_kib_peak'] == 1475000
    assert {r['pid'] for r in d['samples'][0]['processes']} == {10, 11, 12}
    assert all('args' not in r for r in d['samples'][0]['processes'])
    assert B.budget_result({'p95': 20, 'p99': 40}, d)['qualification'] == 'pass-under-shared-load'
    assert B.budget_result({'p95': 31, 'p99': 40}, d)['qualification'] == 'fail-under-shared-load'


def test_canvasdoc_unknown_telemetry_never_qualifies(monkeypatch):
    monkeypatch.setattr(B.platform, 'system', lambda: 'Darwin')
    def fail(cmd, **kwargs):
        if cmd[0] == 'ps':
            return subprocess.CompletedProcess(cmd, 0, PS, '')
        return subprocess.CompletedProcess(cmd, 1, '', 'unavailable')
    monkeypatch.setattr(B.subprocess, 'run', fail)
    load = B.CanvasdocLoad()
    load.sample(force=True)
    load.sample(force=True)
    assert not load.report()['complete']
    assert B.budget_result({'p95': 1, 'p99': 2}, load.report())['qualification'] == 'telemetry-incomplete'


def test_canvasdoc_start_midrun_is_shared_load(monkeypatch):
    monkeypatch.setattr(B.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(B.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, '1 0 0 100 init', ''))
    load = B.CanvasdocLoad()
    load.sample(force=True)
    monkeypatch.setattr(B.subprocess, 'run', fake_run)
    load.sample(force=True)
    d = load.report()
    assert d['complete'] and d['vm_observed'] and not d['clean_result']
    assert [s['state'] for s in d['samples']] == ['absent', 'present']


@pytest.mark.parametrize('raw', ['', '1 0 nan 10 init', '1 0 0 -1 init', '1 0 0 1 init\n1 0 0 1 duplicate'])
def test_bad_process_telemetry_fails_closed(raw):
    with pytest.raises(ValueError):
        B.parse_ps(raw)
