"""Metadata-only final01 release after the coordinator moves survivor timing03.

This closes the descriptive host, not the entire experiment. Never launches
games, signals processes, or imports scientific code.
"""
import hashlib, inspect, json
from pathlib import Path
from audit_vacancy import J, ROOT, OBSERVE, classify_gpu_pids, remote


def main():
    result = remote('127x01', inspect.getsource(classify_gpu_pids)+'\n'+
                    OBSERVE.replace('JOB', repr(J)).replace('HOST', repr('127x01')))
    assert result['all_recorded_groups_absent'], '01 still occupied'
    code = '''import fcntl,hashlib,json,os,subprocess
from pathlib import Path
j=Path(JOB);v=RESULT
assert not Path('/proc/'+str(v['pid'])).exists(),'First observer present'
for name,want in v['source_sha256'].items():
 assert hashlib.sha256((j/name).read_bytes()).hexdigest()==want,'Inventory changed: '+name
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  assert int(p.name) not in v['recorded_pids'] and os.getpgid(int(p.name)) not in v['recorded_pgids']+[v['pgid']],'Recorded group present'
  cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  assert cmd.startswith(('ssh ','sshd:','rsync ')) or str(j)+'/' not in cmd,'Owned runtime present'
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
for item in v['locks']:
 with (j/item['path']).open('r') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
d=json.loads((j/'descriptive-results.json').read_text())
assert d['paired_seeds']==600 and d['never_adoptable'] and not d['live_adoption']
assert not (j/'stage2-results.json').exists(),'Unexpected01 Stage2'
v.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
 released=True,reporting_complete=True,host='127x01',physical_cores=list(range(40)),
 observer_independently_absent=True,all_recorded_groups_absent=True,
 scope='Final R3 descriptive01 release; any survivor timing moved03 by coordinator08:45Z',
 no_further_R3_timing_on01=True,whole_experiment_complete=False,
 pgids=v['recorded_pgids'],descriptive_results_sha256=hashlib.sha256((j/'descriptive-results.json').read_bytes()).hexdigest())
for name in ('EVAL-VACATED.json','R3-CPU-RELEASE.json'):
 p=j/name
 if p.exists():assert json.loads(p.read_text()).get('released'), 'Do not overwrite unrelated vacancy'
 tmp=j/(name+'.tmp')
 with tmp.open('w') as f:f.write(json.dumps(v,indent=2)+'\\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
fd=os.open(j,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(v))
'''.replace('JOB', repr(J)).replace('RESULT', repr(result))
    final = remote('127x01', code)
    target = ROOT/'receipts/vacancy-audits/127x01'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('EVAL-VACATED.json', 'R3-CPU-RELEASE.json'):
        (target/name).write_text(json.dumps(final, indent=2)+'\n')
    # Hash is over the exact remote formatting written above.
    raw = (json.dumps(final, indent=2)+'\n').encode()
    print(json.dumps(dict(host='127x01',utc=final['utc'],released=True,
                         recorded_pgids=len(final['pgids']),
                         path=J+'/R3-CPU-RELEASE.json',sha256=hashlib.sha256(raw).hexdigest())))


if __name__ == '__main__':
    main()
