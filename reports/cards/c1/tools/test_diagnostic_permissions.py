"""Local setgid and prebuild-failure recovery controls; no hosts or engine."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from unittest.mock import patch

HERE=Path(__file__).resolve().parent


def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


J=load('diagnostic_job'); R=load('diagnostic_recover')


def reject(call):
    try: call()
    except (AssertionError,ValueError,FileNotFoundError): return
    raise AssertionError('unsafe input accepted')


def main():
    ast.parse(R.BOOTSTRAP)
    with tempfile.TemporaryDirectory(prefix='c1-private-dir-') as root:
        parent=Path(root); parent.chmod(0o2700)
        original=parent/'original'; original.mkdir(mode=0o700)
        assert stat.S_IMODE(original.stat().st_mode)==0o2700
        reject(lambda:J.private_directory(original))
        fixed=parent/'fixed'; J.private_directory(fixed,create=True)
        assert stat.S_IMODE(fixed.stat().st_mode)==0o700
        output=fixed/'output'; J.private_directory(output,create=True)
        class Controller:
            @staticmethod
            def check_cancelled(): pass
        class Children:
            live={}; rows=[]
            def stop(self): raise ValueError('cleanup receipt failed')
        failures=[dict(phase='driver',error='original prebuild error')]
        assert J.finish(Children(),failures,Controller,output,'a'*40)==1
        terminal=json.loads((output/'terminal.json').read_text())
        assert terminal['status']=='DIAGNOSTIC_FAIL' and terminal['cleanup_complete'] is False
        assert [row['phase'] for row in terminal['failures']]==['driver','cleanup']
        assert terminal['failures'][0]['error']=='original prebuild error'
        assert 'cleanup receipt failed' in terminal['failures'][1]['error']
        assert terminal['engine_acceptance'] is False and terminal['final_C56']=='WITHHELD'
        link=parent/'link'; link.symlink_to(fixed,target_is_directory=True)
        reject(lambda:J.private_directory(link))
    with tempfile.TemporaryDirectory(prefix='c1-prebuild-recovery-') as root:
        job=Path(root); job.chmod(0o2700)
        for name in ('output','root','native','src/engine-cards/py'):
            (job/name).mkdir(mode=0o700,parents=True)
        (job/'src/engine-cards/py/gamedata.json').write_text('{}')
        (job/'root/gamedata.json').write_text('{}')
        J.save(job/'manifest.json',dict(commit='a'*40,
            files={'engine-cards/py/gamedata.json':R.sha(job/'root/gamedata.json')}))
        J.save(job/'launch.json',dict(pid=123,pgid=123))
        J.save(job/'output/before.json',dict(pid=124,pgid=123))
        (job/'run.log').write_text('ValueError: run/output must be mode 0700')
        spec=dict(commit='a'*40,pid=123,pgid=123,driver_pid=124,
            files={name:R.sha(job/name) for name in ('manifest.json','launch.json','output/before.json','run.log')})
        evidence=R.inspect_failed(job,spec)
        assert evidence['directory_modes']['output']==0o2700
        for name in ('output/build.log','output/terminal.json','native/borrowed.so','src/extra.py'):
            path=job/name; path.write_text('unexpected')
            reject(lambda:R.inspect_failed(job,spec)); path.unlink()
        (job/'target').mkdir(); reject(lambda:R.inspect_failed(job,spec)); (job/'target').rmdir()
        original=(job/'run.log').read_text(); (job/'run.log').write_text('changed')
        reject(lambda:R.inspect_failed(job,spec)); (job/'run.log').write_text(original)
        assert R.inspect_failed(job,spec)==evidence
        claims=job/'claims'; claims.mkdir()
        with patch.object(R.subprocess,'check_output',return_value='555 1 555 555 S\n'):
            R.absent_owned_job(spec,claims)
            for name,text in (('lease-123','4 123'),('claim-124','4'),('lease-999','4 123')):
                (claims/name).write_text(text)
                reject(lambda:R.absent_owned_job(spec,claims)); (claims/name).unlink()
        for row in ('123 1 555 555 S','124 1 555 555 S','555 1 123 555 S','555 1 555 123 Z'):
            with patch.object(R.subprocess,'check_output',return_value=row+'\n'):
                reject(lambda:R.absent_owned_job(spec,claims))
    print('PASS: inherited2700 reproduction/exact0700 creation, cleanup-error terminal failure retention, symlink rejection, exact prebuild inventory and process/group/session/lease negative controls; no host/engine/native execution')


if __name__=='__main__': main()
