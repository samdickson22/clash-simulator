"""Local bounded model-free checks. Reviewed orchestration: fixed phase/argv,
explicit child environment, no shell, no remote/deployment/pin mutations."""
from pathlib import Path
import argparse, datetime, hashlib, json, subprocess
C=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('focused','full'));a=ap.parse_args()
 env=json.loads((C.parent/'consumer-mapping-compat-r2-20261016/frozen-tests.json').read_text())['env']
 env.update(PYTHONPATH=str(C/'patched'),TMPDIR=str(C/'tmp'))
 Path(env['TMPDIR']).mkdir(exist_ok=True)
 paths=list((C/'patched/bot/live').glob('*.py'))+[C/'patched/bot/players/royalesim_translate.py',C/'patched/bot/players/runtime.py',C/'verify_host_package.py',C/'model_free_checks.py',C/'selection.json',C/'host-base-guards.json']
 sources={str(p.relative_to(C)):sha(p) for p in paths}
 argv=['nice','-n','19','taskset','-c','2-3','/mpac/sdicks02/repos/clasher-bot/.venv/bin/python',str(C/'model_free_checks.py'),a.phase]
 r=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=argv,cwd=str(C/'patched'),env=env,entire_child_environment_explicit=True,source_sha256=sources,affinity=[2,3],nice=19,model_free='exact frozen Runtime3policy-loading statements omitted in memory only; callguard rejects policy/game/torchload; no product/runtime files changed')
 receipt=C/(a.phase+'-tests.json');receipt.write_text(json.dumps(r,indent=2)+'\n')
 with (C/(a.phase+'-tests.log')).open('w') as stream:p=subprocess.run(argv,cwd=C/'patched',env=env,stdout=stream,stderr=subprocess.STDOUT)
 r.update(end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),returncode=p.returncode,log_sha256=sha(C/(a.phase+'-tests.log')),source_unchanged=all(sha(C/n)==v for n,v in sources.items()))
 receipt.write_text(json.dumps(r,indent=2)+'\n');print((C/(a.phase+'-tests.log')).read_text()[-6500:]);raise SystemExit(p.returncode)
if __name__=='__main__':main()
