"""PREREG-K4S SD1 artifact manifest (r3 §2.1): build it, and check it before any game.

SD1 = clasher-sd1-k4s-default-20261011: the exact R3a bytes re-frozen under a new artifact identity.
SD1-MANIFEST.json binds the EMA checkpoint, calibration, threshold, every inference source file,
the Torch version and the inference mode. Its own sha256 is the SD1 hash (computed at the freeze).
The runner calls check() and refuses to start on any mismatch.

  runtime.sh reports/explore/k4s-confirm/sd1_manifest.py build   # on a staged host; writes SD1-MANIFEST.json
  runtime.sh reports/explore/k4s-confirm/sd1_manifest.py check   # verifies the staged job
"""
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE/'SD1-MANIFEST.json'
# Repo-relative files executed on the SD1 inference path (seat poll, ranking, packet, network).
SOURCES = (
    'reports/explore/k4s-confirm/cached_policy.py',
    'reports/explore/k4s-confirm/sd1_policy.py',
    'reports/explore/k4s-confirm/proposals.py',
    'reports/explore/e1/policy.py',
    'imitation/evaluation/d1.py',
    'imitation/evaluation/standalone.py',
    'imitation/model/inference.py',
    'student-source/exit_r3/network.py',
)
MODE = dict(device='cpu', dtype='float32', torch_threads=1, cuda_visible_devices='', grad='torch.inference_mode',
            temperatures=[1., 1., 1.], forwards_per_poll=1)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(job):
    import torch
    plan = json.loads((HERE/'plan.json').read_text())
    s = plan['student']
    m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    m.update(
        schema='clasher.k4s.sd1-manifest.v1',
        artifact='SD1', artifact_id='clasher-sd1-k4s-default-20261011',
        same_bytes_as='R3a (exit-r3 Stage 1 arm R3a; final EMA)',
        checkpoint=dict(job_path=s['checkpoint'], sha256=sha(job/s['checkpoint'])),
        calibration=dict(job_path=s['calibration'], sha256=sha(job/s['calibration'])),
        threshold=s['threshold'],
        inference_sources={p: sha(ROOT/p) for p in SOURCES},
        torch_version=torch.__version__, inference_mode=MODE)
    assert m['checkpoint']['sha256'] == s['checkpoint_sha256'] == '37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85'
    assert m['calibration']['sha256'] == s['calibration_sha256'] == 'e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414'
    assert m['threshold'] == 0.5005528330802917
    MANIFEST.write_text(json.dumps(m, indent=2)+'\n')
    return sha(MANIFEST)


def check(job, plan):
    import os, torch
    m = json.loads(MANIFEST.read_text())
    s = plan['student']
    assert m['artifact_id'] == 'clasher-sd1-k4s-default-20261011'
    assert m['checkpoint']['job_path'] == s['checkpoint'] and m['calibration']['job_path'] == s['calibration']
    assert sha(job/s['checkpoint']) == m['checkpoint']['sha256'] == s['checkpoint_sha256'], 'SD1 checkpoint'
    assert sha(job/s['calibration']) == m['calibration']['sha256'] == s['calibration_sha256'], 'SD1 calibration'
    assert m['threshold'] == s['threshold'], 'SD1 threshold'
    assert set(m['inference_sources']) == set(SOURCES)
    for p, h in m['inference_sources'].items():
        assert sha(ROOT/p) == h, 'SD1 inference source '+p
    assert torch.__version__ == m['torch_version'], 'Torch version'
    assert torch.get_num_threads() == 1 and torch.get_default_dtype() == torch.float32
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and m['inference_mode'] == MODE
    return sha(MANIFEST)


if __name__ == '__main__':
    sys.path[:0] = [str(HERE)]
    from common import job
    if sys.argv[1] == 'build':
        print(build(job()))
    else:
        import torch; torch.set_num_threads(1)
        print(check(job(), json.loads((HERE/'plan.json').read_text())))
