"""Apply the authorized council integration to existing v6 and re-pin it."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/sam/Desktop/code/clasher')
KIT = Path(__file__).resolve().parent
RC = KIT.parents[1]
RT = RC / 'm0/runtime-snapshots/pilot-runtime-v6'
V5 = RT.with_name('pilot-runtime-v5')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, content):
    path.chmod(0o644)
    path.write_text(content)
    path.chmod(0o444)

manifest = json.loads((RT / 'pilot-runtime.json').read_text())
relative = 'src/clasher/rl/council_pilot.py'
assert manifest['files'][relative]['class'] == 'TRAINING_ONLY'
write(RT / relative, (ROOT / relative).read_text())
manifest['files'][relative]['sha256'] = sha(RT / relative)
manifest['overlay'][relative] = {'workspace_sha256': sha(ROOT / relative), 'v5_sha256': sha(V5 / relative), 'v6_sha256': sha(RT / relative)}
admission = json.loads(Path(manifest['admission_path']).read_text())
bound = {}
for name, entry in manifest['files'].items():
    assert sha(RT / name) == entry['sha256'], name
    if entry['class'] == 'ADMISSION_BOUND':
        digest = sha(RT / name)
        assert digest == sha(V5 / name) == entry['admission_sha256'] == admission['source_pins'][str(Path(manifest['base_snapshot']) / name)], name
        bound[name] = digest
assert len(bound) == 342
pins = {str(RT / r): e['sha256'] for r, e in sorted(manifest['files'].items())}
write(RT / 'pilot-source-pins.json', json.dumps(pins, indent=2) + '\n')
manifest['pilot_source_pins_sha256'] = sha(RT / 'pilot-source-pins.json')
manifest['v5_admission_module_equality'] = bound
manifest['status'] = 'coordinator-authorized council TBPTT integration; validation pending'
manifest['integration_utc'] = datetime.now(timezone.utc).isoformat()
manifest['integration_authorization'] = '2026-10-04 coordinator: council_pilot training-only integration, preserving all 342 admission-bound modules'
write(RT / 'pilot-runtime.json', json.dumps(manifest, indent=2) + '\n')
sidepath = KIT / 'orchestration-pins-pilot-runtime-v6.json'
side = json.loads(sidepath.read_text())
side['runtime_manifest_sha256'] = sha(RT / 'pilot-runtime.json')
side['source_pins_sha256'] = sha(RT / 'pilot-source-pins.json')
side['training_only_changed_vs_admission'][relative]['pilot_runtime_sha256'] = sha(RT / relative)
side['reason'] = 'Coordinator-authorized TBPTT training extension: 352 pinned modules, 342 admission-bound modules unchanged, 10 training-only modules. Admission receipt and decision unchanged.'
write(sidepath, json.dumps(side, indent=2) + '\n')
for name in ('verify_v7r5_launch.py', 'make_sidecar.py'):
    path = KIT / name
    s = re.sub(r'RUNTIME_MANIFEST_SHA = "[a-f0-9]+"', f'RUNTIME_MANIFEST_SHA = "{sha(RT / "pilot-runtime.json")}"', path.read_text())
    if name.startswith('verify'):
        s = s.replace('len(report["training_only"]) == 9', 'len(report["training_only"]) == 10').replace('342 bound, 9 training-only, 4 changed', '342 bound, 10 training-only, 6 changed')
    path.write_text(s)
receipt = {'utc': manifest['integration_utc'], 'manifest_sha256': sha(RT / 'pilot-runtime.json'), 'pins_sha256': sha(RT / 'pilot-source-pins.json'), 'council_sha256': sha(RT / relative), 'admission_bound_equal': len(bound), 'admission_sha256': sha(Path(manifest['admission_path'])), 'v5_manifest_sha256': sha(V5 / 'pilot-runtime.json')}
(KIT / 'logs/council-integration-build.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
