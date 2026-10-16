"""One explicitly reviewed stage-only recovery from the preserved Python3.8 staging failure.

Usage: stage_r2v2.py APPROVED_REVIEW_RECEIPT.json
Does not stop/requeue the frozen arm. Requires its successful supersede receipt,
no old process/lease/claim, the first failed directory still empty, and a different
fresh job directory. Queues at most one cpu_job4/nice15 corrected validation.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]
NEW = '/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z'
OLD_FAILED = '/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0925Z'


if __name__ == '__main__':
    review = json.loads(Path(sys.argv[1]).read_text())
    assert review['verdict'] == 'APPROVED FOR BOUNDED TEST EXECUTION'
    for name, expected in review['reviewed_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, ('reviewed tool changed', name)
    assert 'stage_r2v2.py' in review['reviewed_sha256'] and 'supersede_r2.py' in review['reviewed_sha256']
    spec = importlib.util.spec_from_file_location('frozen_scheduler', HERE/'supersede_r2.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)  # Its scheduling actions exist only under __main__; import has no host actions.
    script = prior.PREPARE_AND_LAUNCH
    old_check = "assert member.isfile() and (new/member.name).resolve().is_relative_to(new.resolve()), member.name"
    assert script.count(old_check) == 1
    script = script.replace(old_check, "assert member.isfile(), member.name\n        (new/member.name).resolve().relative_to(new.resolve())")
    assert script.count(prior.NEW) == 1
    script = script.replace(prior.NEW, NEW)
    marker = "assert not new.exists(), 'fresh job directory already exists; inspect before any retry'"
    assert script.count(marker) == 1
    check = f"""assert not Path('/proc/561530').exists(), 'old PID exists; inspect before any new launch'
assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-561530').exists(), 'old lease exists'
assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/claim-561552').exists(), 'old claim exists'
failed=Path({OLD_FAILED!r})
assert failed.is_dir() and not list(failed.iterdir()), 'failed stage directory changed; inspect'
{marker}"""
    script = script.replace(marker, check)
    files = {}
    names = subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    for name in names:
        if name:
            files[str(Path('tree')/Path(name).relative_to('engine-cards'))] = WORKTREE/name
    for name in ['probe_dash_full.py','probe_clone_recovery.py','probe_clone_bounds.py','run_r2.sh',
                 'validate_r2.py','test_r2_harness.py','native_entity_sites.py','run_scen.sh','probe_native_scen.py','scenarios.py']:
        files[f'fid/{name}'] = HERE/name
    files['fid/probe_first_update_paths.py'] = WORKTREE/'reports/cards/batchA/tools/probe_first_update_paths.py'
    source_commit = subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip()
    patch = subprocess.check_output(['git','-C',str(WORKTREE),'diff','--','engine-cards'])
    manifest = dict(source_commit=source_commit,engine_wip_diff_sha256=hashlib.sha256(patch).hexdigest(),
                    files={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()},
                    reviewed_sha256=review['reviewed_sha256'],
                    supersedes_failed_staging=OLD_FAILED)
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for name,path in files.items():
            assert path.is_file() and not path.is_symlink(), path
            archive.add(path,arcname=name,recursive=False)
        data=json.dumps(manifest,indent=1).encode()
        member=tarfile.TarInfo('source-and-tools.json'); member.size=len(data)
        archive.addfile(member,io.BytesIO(data))
    launched = prior.remote(script,payload.getvalue())
    (HERE.parent/'evidence/r2v2-launch-20261016.json').write_text(json.dumps(launched,indent=1)+'\n')
