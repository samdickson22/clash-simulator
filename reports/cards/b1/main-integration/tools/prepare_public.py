"""Proposed local stdlib-only committed archive preparation; review before use.

No imports from the engine/model, network, host job or shared source mutation.
Writes only a fresh fixed /tmp staging directory; failures preserve artifacts.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path('/mpac/sdicks02/repos/clasher-cards-b1')
OUT = Path('/tmp/b1-public-stage-20261016-04')
REPORT = Path('reports/cards/b1/main-integration')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def require(ok, message):
    if not ok:
        raise SystemExit(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


require(Path.cwd().resolve() == ROOT and git('branch', '--show-current').decode().strip() == 'cards/b1',
        'B1 worktree/branch required')
revision = git('rev-parse', 'HEAD').decode().strip()
require(len(sys.argv) == 2 and sys.argv[1] == revision, 'exact current commit argument required')
tracked = git('ls-files').decode().splitlines()
files = [p for p in tracked if p.startswith('engine-cards/') or
         (p.startswith('bot/') and (p.endswith('.py') or p == 'bot/fidelity/c56_native_ids.json')) or
         (p.startswith(('reports/explore/x4s/', 'reports/cards/b1/tools/',
                        'reports/cards/b1/main-integration/tools/', 'reports/cards/runtime/tools/'))
          and p.endswith(('.py', '.sh'))) or
         p == 'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py']
require(str(REPORT/'tools/stage_public.sh') in files and str(REPORT/'tools/prepare_public.py') in files,
        'staging tools must be committed before preparation')
subprocess.run(['git', 'diff', '--exit-code', revision, '--', *files], cwd=ROOT, check=True)
subprocess.run(['git', 'diff', '--exit-code', '5c8afc2d78cb9160c42cd2536f1588cc0dc98c6e', revision, '--',
                'engine-cards/src', 'engine-cards/Cargo.toml', 'engine-cards/Cargo.lock', 'engine-cards/build.rs'],
               cwd=ROOT, check=True)
packet_path = ROOT/'reports/cards/runtime/receipts/b1-public-root-implementation-packet-r5.json'
packet = json.loads(packet_path.read_text())
require(packet['approved_source'] == 'ff23043fc3857bd26b42440637da4d017b12731d' and
        packet['review']['round'] == 5 and packet['review']['verdict'] == 'APPROVE',
        'corrected reviewed root-source packet required')
for path, digest in packet['sha256'].items():
    require(sha(ROOT/path) == digest, 'approved public implementation changed: '+path)
OUT.mkdir()
with (OUT/'source.tar').open('xb') as output:
    subprocess.run(['git', 'archive', '--format=tar', revision, '--', *files], cwd=ROOT, stdout=output, check=True)
with (OUT/'source.sha256').open('x') as output:
    with tarfile.open(OUT/'source.tar') as archive:
        for p in files:
            member = archive.getmember(p)
            require(member.isfile(), 'only regular tracked source files admitted: '+p)
            destination = 'tree/'+p[len('engine-cards/'):] if p.startswith('engine-cards/') else 'repo/'+p
            digest = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
            output.write(digest+'  '+destination+'\n')
(OUT/'source-commit.txt').write_text(revision+'\n')
for source, name in ((ROOT/REPORT/'native-build-inputs.sha256', 'native-build-inputs.sha256'),
                     (ROOT/REPORT/'gate-inputs-expected.sha256', 'gate-inputs-expected.sha256'),
                     (ROOT/REPORT/'tools/stage_public.sh', 'stage_public.sh'),
                     (packet_path, 'root-implementation-packet.json'),
                     (ROOT/'reports/cards/runtime/receipts/b1-public-root-review-r5.md', 'root-source-review.md')):
    shutil.copyfile(source, OUT/name)
inputs = sorted(p for p in OUT.iterdir() if p.is_file())
with (OUT/'inputs.sha256').open('x') as output:
    for p in inputs:
        output.write(sha(p)+'  '+p.name+'\n')
require(git('rev-parse', 'HEAD').decode().strip() == revision, 'source moved during preparation')
print(json.dumps(dict(commit=revision, source_files=len(files), source_archive_sha256=sha(OUT/'source.tar'),
                      source_manifest_sha256=sha(OUT/'source.sha256'), input_manifest_sha256=sha(OUT/'inputs.sha256'),
                      output=str(OUT), note='Preparation only; host staging/execution require independent approval.')))
