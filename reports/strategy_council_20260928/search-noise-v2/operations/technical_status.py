"""Outcome-blind identity validation and technical counts; stdlib only."""
from pathlib import Path
import collections,hashlib,json,sys,time
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from cells import CELLS,H2H

def main():
    path=HERE/'evaluation-manifest.json'
    if not path.exists():
        print(json.dumps(dict(protocol='r2',sealed=False,confirmation_launched=False)))
        return
    manifest=json.loads(path.read_text());sha=hashlib.sha256(path.read_bytes()).hexdigest()
    execution=json.loads((HERE/'execution.json').read_text())['workers']
    schedule=json.loads((HERE/'schedule.json').read_text())
    expected=[(ep,cell,seat) for ep in schedule['pairs'] for cell in (CELLS if ep['mode']=='scripts' else H2H) for seat in (0,1)]
    assert len(expected)==4992 and len(execution)==248
    counts=collections.Counter();cpu=0.;valid=0
    for p in sorted((HERE/'confirmation').glob('*.json')):
        index=int(p.stem);assert 0<=index<len(expected),('unexpected receipt',p.name)
        row=json.loads(p.read_text());ep,cell,seat=expected[index]
        assert row['terminal'] and row['manifest']==sha and row['job']==index,('receipt identity',p.name)
        for key,want in [('seed',ep['seed']),('noise_seed',ep['noise_seed']),('pair',ep['pair']),('seat',seat),('variant',cell),('mode',ep['mode'])]:
            assert row[key]==want,('receipt field',p.name,key)
        host=execution[index%248]['host']
        assert row['host']['hostname'].split('.')[0]==host,('receipt host',p.name)
        assert row['started']>=manifest['sealed_unix'] and row['host']['nice']>=10 and row['host']['native_threads']==1,('receipt execution',p.name)
        valid+=1;counts[host]+=1;cpu+=row['cpu_seconds']
    done=0
    for w in execution:
        p=HERE/'collected-status'/f'worker-{w["index"]}-done.json'
        e=HERE/'collected-status'/f'worker-{w["index"]}.exit'
        if not p.exists() or not e.exists():continue
        row=json.loads(p.read_text())
        assert row['manifest']==sha and row['complete'] and e.read_text().strip()=='0',('partition status',w['index'])
        done+=1
    out=dict(utc=time.time(),protocol='r2',sealed=True,manifest=sha,
             valid_terminal_receipts=valid,expected_receipts=4992,
             successful_collected_partitions=done,expected_partitions=248,
             per_host_receipts=dict(counts),completed_game_cpu_hours=cpu/3600,
             complete_only_ready=valid==4992 and done==248,outcomes_inspected=False)
    print(json.dumps(out))
if __name__=='__main__':main()
