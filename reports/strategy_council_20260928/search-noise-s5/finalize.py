"""Post-collector independent audit and final frozen-file verification."""
from pathlib import Path
import json,socket,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
def call(args,**kw):return subprocess.run(args,check=True,text=True,timeout=180,**kw)
assert (JOBS/'s5-collect-127x01-r1.exit').read_text().strip()=='0'
call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'completion_audit.py')])
for host in ('127x01','127x04','127x08'):
 args=[str(ROOT/'.venv/bin/python'),'-B',str(HERE/'integrity.py')]
 if host!='127x01':args=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'env','RAYON_NUM_THREADS=1',*args]
 call(args)
 if host!='127x01':
  call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',f'{host}:{HERE}/integrity-{host}-*.json',str(HERE)+'/'])
call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'compute_audit.py')])
result=json.loads((HERE/'result.json').read_text());cpu=json.loads((HERE/'compute-audit.json').read_text());audit=json.loads((HERE/'completion-audit.json').read_text())
# Preserve the frozen analyzer's output as a separate generated artifact.
generated=HERE/'RESULTS-generated.md';assert not generated.exists();generated.write_bytes((HERE/'RESULTS.md').read_bytes())
notes=['','## Integrity and operations','',f"Independent recomputation matched all 1,536 receipts, six scores, all score CIs, and all four paired contrasts/CIs. Receipt aggregate {audit['receipt_aggregate']}.", '','All S1–S5 frozen manifests and the separately frozen S4 tracker dependencies pass final audits on 01/04/08. No confirmation reruns, exclusions, tracker changes or engine/gamedata edits. Both seed audits passed; 726 unavailable historical paths limit absolute historical-disjointness claims. The only preflight failure was a new test comparing rounded decimal radii with exact float equality; test-only correction passed and original failed log is retained.', '',f"Game CPU: {result['game_cpu_hours']:.3f} core-hours. Confirmation supervisor/worker CPU: {cpu['confirmation_supervisors_and_workers_cpu_hours']:.3f}. Total metered CPU: {'at least ' if cpu['total_is_lower_bound'] else ''}{cpu['total_metered_cpu_hours']:.3f}. These overlap; do not add them. Small finalization/copy operations are unmetered. Confirmation wall span: {audit['wall_span_minutes']:.2f} minutes.", '', 'Games used 04/08 only, nice 10, one native/BLAS thread; console-user capacity reserved headroom. Hub 01 performed collection/analysis; 05 received only code/docs/small receipts/results. Raw terminal receipts stay on the fleet. No commits or data deletion.']
(HERE/'RESULTS.md').write_text(generated.read_text()+'\n'.join(notes)+'\n')
(HERE/'PROGRESS.md').write_text(f"# S5 progress\n\nCOMPLETE: 1,536 games, 152 successful partitions, two successful supervisors. Complete-only analysis, independent aggregation and final frozen-file audits all pass. Manifest {result['manifest']}. See RESULTS.md and result.json.\n")
(HERE/'RESUME.md').write_text('# S5 resume\n\nComplete. Do not relaunch. Raw receipts remain on 01/04/08. Final code/docs/small audit/results mirror to 05. No commits.\n')
files=[str(p.relative_to(HERE)) for p in HERE.iterdir() if p.is_file() and (p.suffix in ('.py','.md','.json','.sha256') or p.name.startswith('transfer-')) and not p.name.startswith(('worker-','launch-'))]
files += [str(p.relative_to(HERE)) for p in (HERE/'preflight-status').glob('*')]
(HERE/'transfer-results.txt').write_text('\n'.join(sorted(files))+'\n')
call(['rsync','-ac','--files-from=-','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',str(HERE)+'/',f'127x05:{HERE}/'],input='\n'.join(files)+'\n')
print(json.dumps(dict(complete=True,manifest=result['manifest'],game_cpu_hours=result['game_cpu_hours'])),flush=True)
