"""Regression checks for memory evidence and confined launcher writes."""
import copy
import json
import runpy
import time
from pathlib import Path

import pytest

from bot.pretrain_v1 import supplemental_job as job


def evidence(tmp_path):
    path=tmp_path/'config.json'
    path.write_text('{}\n')
    config=dict(host='127x17',seed=2026102006,config_path=str(path),pss_gib=30.5)
    receipt=dict(status='cpu-memory-qualified',completed=True,host=config['host'],seed=config['seed'],
                 identity=dict(pid=123,start=456,boot='boot'),config_sha256=job.sha(path),
                 written_at=time.time(),qualified_peak_gib=17.,peak_pss_gib=16.,child_peak_rss_gib=16.5)
    return config,receipt


def test_memory_receipt_is_bound_and_conservative(tmp_path):
    config,receipt=evidence(tmp_path)
    job.validate_memory(receipt,config,'boot')
    for field,value in [('host','127x13'),('seed',1),('config_sha256','wrong'),('written_at',0),
                        ('qualified_peak_gib',0),('qualified_peak_gib',float('nan')),
                        ('child_peak_rss_gib',40),('qualified_peak_gib',29)]:
        bad=copy.deepcopy(receipt);bad[field]=value
        with pytest.raises(AssertionError):job.validate_memory(bad,config,'boot')
    with pytest.raises(AssertionError):job.validate_memory(receipt,config,'new-boot')


def test_zero_pss_sample_does_not_hide_high_water(tmp_path):
    config,receipt=evidence(tmp_path)
    receipt.update(peak_pss_gib=0.,child_peak_rss_gib=31.,qualified_peak_gib=31.02)
    with pytest.raises(AssertionError,match='memory margin'):
        job.validate_memory(receipt,config,'boot')


def test_runtime_cache_roots_are_confined():
    env=job.environment(dict(allocator_gib=37.5,gpu_total_gib=47.98828125))
    for key in ['TMPDIR','XDG_CACHE_HOME','TORCH_HOME','CUDA_CACHE_PATH','TRITON_CACHE_DIR','TORCHINDUCTOR_CACHE_DIR']:
        assert Path(env[key]).is_relative_to(job.BASE)


def test_launcher_log_symlink_never_truncates_target(tmp_path):
    source=Path(__file__).parents[3]/'reports/bot/pretrain-v1/supplemental/launch.py'
    module=runpy.run_path(str(source))
    function=module['safe_result'];function.__globals__['BASE']=tmp_path
    outside=tmp_path/'outside';outside.write_bytes(b'preserve')
    (tmp_path/'stdout').symlink_to(outside)
    with pytest.raises(OSError):function('stdout')
    assert outside.read_bytes()==b'preserve'


def test_launcher_hardlink_never_truncates_target(tmp_path):
    import os
    source=Path(__file__).parents[3]/'reports/bot/pretrain-v1/supplemental/launch.py'
    module=runpy.run_path(str(source));function=module['safe_result'];function.__globals__['BASE']=tmp_path
    outside=tmp_path/'outside';outside.write_bytes(b'preserve');os.link(outside,tmp_path/'stdout')
    with pytest.raises(ValueError):function('stdout')
    assert outside.read_bytes()==b'preserve'


def test_slow_resource_sampler_is_bounded_and_reaped(tmp_path,monkeypatch):
    import subprocess
    import sys
    fake=tmp_path/'supervisor.py';fake.write_text('')
    original=subprocess.Popen
    children=[]
    def start(*args,**kwargs):
        child=original([sys.executable,'-c','import time;time.sleep(30)'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        children.append(child)
        return child
    monkeypatch.setattr(job.subprocess,'Popen',start)
    module=type('Fixture',(),{'__file__':str(fake)})
    started=time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):job.sample_resources(module,'127x17',started+.15)
    assert time.monotonic()-started<2 and children[0].poll() is not None


def test_installer_rejects_changed_map_before_writes(tmp_path):
    source=Path(__file__).parents[3]/'reports/bot/pretrain-v1/supplemental/launch.py'
    module=runpy.run_path(str(source))
    root=tmp_path/'root';base=tmp_path/'job';(base/'staging').mkdir(parents=True)
    (base/'staging/source-map.json').write_text('{"../outside":{}}')
    fake=tmp_path/'supervisor.py';fake.write_text('def make_directories(path):\n raise RuntimeError("write reached")\n')
    globals_=dict(SUPERVISOR=str(fake),ROOT=str(root),ADAPTER=str(tmp_path/'adapter'),BASE=str(base),
                  CONFIG={'map_hashes':{'source':'wrong'}},OVERRIDES={})
    import os
    from unittest.mock import patch
    with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='',CLASHER_LEASE_JOB='fixture'):
        with pytest.raises(AssertionError):exec(module['INSTALL'],globals_)
    assert not (tmp_path/'adapter').exists()
