"""Local stdlib admission controls only; no host access, engine import or jobs."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('diagnostic_job',HERE/'diagnostic_job.py')
J=importlib.util.module_from_spec(spec); spec.loader.exec_module(J)


def reject(call):
    try: call()
    except (AssertionError,RuntimeError,FileNotFoundError): return
    raise AssertionError('bad diagnostic input accepted')


def main():
    for name in ('diagnostic_job.py','diagnostic_worker.py'):
        ast.parse((HERE/name).read_text(),filename=name)
    ast.parse(J.BOOTSTRAP)
    for path in J.EXTRAS:
        assert (J.REPO/path).is_file(),path
    env=J.clean_environment()
    assert env['USER']==pwd.getpwuid(os.getuid()).pw_name and env['LOGNAME']==env['USER']
    assert env['CARGO_BUILD_JOBS']=='4' and env['PYTHONHASHSEED']=='0'
    assert all(env[key]=='1' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','RAYON_NUM_THREADS'))
    assert not set(env)&{'CLASHER_BOT_RUNTIME_PINS','CLASHER_ROOT','PYTHONPATH','PYTHONHOME','BASH_ENV','ENV','RUSTFLAGS'}
    with tempfile.TemporaryDirectory(prefix='c1-diagnostic-control-') as temp:
        job=Path(temp); (job/'src/engine-cards').mkdir(parents=True)
        source=job/'src/engine-cards/source.py'; source.write_text('sentinel\n')
        files={'engine-cards/source.py':J.sha(source)}
        review=dict(verdict='APPROVED_FOR_DIAGNOSTIC_EXECUTION',commit='a'*40,base=J.BASE,reviewed_sha256=files)
        J.save(job/'review.json',review)
        manifest=dict(commit='a'*40,base=J.BASE,files=files,review_sha256=J.sha(job/'review.json'))
        J.save(job/'manifest.json',manifest)
        assert J.validate(job)==manifest
        source.write_text('changed\n'); reject(lambda:J.validate(job)); source.write_text('sentinel\n')
        extra=job/'src/extra.py'; extra.write_text('extra\n'); reject(lambda:J.validate(job)); extra.unlink()
        original=source.read_bytes(); source.unlink(); target=job/'external.py'; target.write_bytes(original)
        source.symlink_to(target); reject(lambda:J.validate(job)); source.unlink(); source.write_bytes(original)
        for key,value in (('verdict','APPROVE'),('commit','b'*40),('base','b'*40),('reviewed_sha256',{})):
            broken=copy.deepcopy(review); broken[key]=value
            (job/'review.json').write_text(json.dumps(broken))
            altered=dict(manifest,review_sha256=J.sha(job/'review.json'))
            (job/'manifest.json').write_text(json.dumps(altered))
            reject(lambda:J.validate(job))
        (job/'review.json').write_text(json.dumps(review))
        manifest['review_sha256']=J.sha(job/'review.json')
        manifest['external']={str(target):J.sha(target)}
        (job/'manifest.json').write_text(json.dumps(manifest))
        J.validate(job)
        target.write_text('external changed\n'); reject(lambda:J.validate(job))
    for name in ('diagnostic_job.py','diagnostic_worker.py'):
        optimized=subprocess.run([sys.executable,'-O','-B',str(HERE/name)],capture_output=True,text=True)
        assert optimized.returncode!=0 and 'unoptimized execution required' in optimized.stderr
        assert 'No module named' not in optimized.stderr
    print('PASS: stdlib inventory/review/source/extra/symlink/external drift, clean CPU-accounting environment, embedded bootstrap AST and optimized guards; no hosts/engine/native/jobs')


if __name__=='__main__': main()
