"""Five fresh projected-bank cases per player, two strong, LD versus fc-c4."""
import json,os,signal,subprocess,time,traceback
from pathlib import Path
from bot.deckopt2 import run as h
from clean import problems
import projected_fast
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');D=J/'projected-parity';R=J/'final-validation'
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
MODE=None;OBSERVED=[]

class Counted:
    def __init__(self,inner):
        self.inner=inner;self.reserve_calls=0;self.reserve_positive=0
        self.deadline_seconds=inner.deadline_seconds
        OBSERVED.append(self)
    def __getattr__(self,name):return getattr(self.inner,name)
    def start(self,ctx):
        self.inner.start(ctx);core=self.inner.search.p.core
        for field in ('reserve','reserve_penalty'):
            previous=getattr(core,field,None)
            if previous is not None:
                def counted(a,e,_previous=previous):
                    value=_previous(a,e);self.reserve_calls+=1;self.reserve_positive+=value>0
                    return value
                setattr(core,field,counted)
    def act(self,view):return self.inner.act(view)
    def close(self):return self.inner.close()

def run():
    D.mkdir(exist_ok=True);(D/'rows').mkdir(exist_ok=True)
    bank=json.loads((R/'validation/bank.json').read_text());meta=json.loads((R/'manifest.json').read_text())
    assert not (D/'receipt.json').exists()
    from bot.players.runtime import Runtime
    from bot.players.royalesim_vocab import load
    from bot.live.player import load_fast
    from bot.livediag.variants import ground_reserve
    import bot.livediag.variants as variants
    rt=Runtime();h.install_compat(rt);vocab=load(rt);rt.STUDENT;load_fast(rt)
    names=[n for n in bank['candidates'] if n!='baseline']
    cheap=min(names,key=lambda n:(ground_reserve(rt.R,meta['candidates'][n]),n))
    different=max(names,key=lambda n:(len(set(meta['candidates'][n])^set(meta['candidates']['baseline'])),n))
    picks=[('R3a',0,'baseline'),('v1',0,names[0]),('LIVE-K4CW-r16',0,cheap),('LIVE-K4CW-r16',1,different),('rext-bc',0,'baseline')]
    chosen=[(next(c for c in bank['cases'] if c['opponent']==op and c['index']==index),name) for op,index,name in picks]
    h.dump(D/'plan.json',dict(utc=h.utc(),bank_sha256=h.sha(R/'validation/bank.json'),cases=[dict(case_id=c['id'],opponent=c['opponent'],candidate=n) for c,n in chosen],players=list(h.PLAYERS),modes=['LD','fc-c4'],factory_sha256=h.sha(J/'projected_fast.py')),exclusive=True)
    original=variants.make_variant
    def make(current,name):return Counted(projected_fast.make(current,name) if MODE=='fc-c4' else original(current,name))
    variants.make_variant=make
    import instrument
    instrument.install()
    jobs=[(i,c,n,p,mode) for i,(c,n) in enumerate(chosen) for p in h.PLAYERS for mode in ('LD','fc-c4')]
    active={}
    def reap():
        pid,status=os.wait();job=active.pop(pid);assert status==0,(job,status)
    for i,c,n,p,mode in jobs:
        while len(active)>=4:reap()
        output=D/'rows'/f'{i}-{p}-{mode}.json';assert not output.exists()
        pid=os.fork()
        if pid==0:
            try:
                globals()['MODE']=mode
                current=dict(meta,own_levels=meta['candidate_plans'][n]['levels'])
                h.game(rt,vocab,R,'validation',current,c,n,p,output)
                row=json.loads(output.read_text());row['parity_mode']=mode
                row['reserve_counts']=[dict(calls=o.reserve_calls,positive=o.reserve_positive) for o in OBSERVED]
                h.dump(output,row)
                assert not problems(row),problems(row)
            except BaseException:
                traceback.print_exc();os._exit(1)
            os._exit(0)
        active[pid]=(i,p,mode)
    while active:reap()
    comparisons=[]
    for i,c,n in [(i,c,n) for i,(c,n) in enumerate(chosen)]:
        for p in h.PLAYERS:
            rows=[json.loads((D/'rows'/f'{i}-{p}-{mode}.json').read_text()) for mode in ('LD','fc-c4')]
            keys=('command_sha256','state_hash','ticks','winner','crowns','towers')
            same=all(rows[0]['result'][key]==rows[1]['result'][key] for key in keys)
            comparisons.append(dict(case_id=c['id'],opponent=c['opponent'],candidate=n,player=p,identical=same,
                command_sha256=[r['result']['command_sha256'] for r in rows],reserve_counts=[r['reserve_counts'] for r in rows]))
    passed=all(c['identical'] for c in comparisons)
    reserve_fired=all(any(x['positive'] for x in counts) for c in comparisons if c['player'].endswith('-res') and c['opponent']=='LIVE-K4CW-r16' for counts in c['reserve_counts'])
    assert reserve_fired,'strong-case reserve did not fire in every required comparison'
    receipt=dict(utc=h.utc(),passed=passed,reserve_fired=reserve_fired,comparisons=comparisons,bank_sha256=h.sha(R/'validation/bank.json'),factory_sha256=h.sha(J/'projected_fast.py'),source_sha256=h.sha(__file__))
    h.dump(D/'receipt.json',receipt,exclusive=True)
    implementation=dict(utc=h.utc(),mode='fc-c4' if passed else 'LD',parity_receipt_sha256=h.sha(D/'receipt.json'),bank_sha256=receipt['bank_sha256'],factory_sha256=receipt['factory_sha256'])
    h.dump(R/'implementation.json',implementation,exclusive=True)
    for path in (D/'receipt.json',R/'implementation.json'):
        subprocess.run(['rsync','-a',str(path),f'127x05:{path}'],check=True)
    subprocess.run(['rsync','-a',str(D)+'/',f'127x05:{D}/'],check=True)
    print('PROJECTED_PARITY_DONE',json.dumps(implementation),flush=True)

if __name__=='__main__':
    try:run()
    except BaseException as error:
        h.dump(D/'error.json',dict(utc=h.utc(),error=repr(error)));raise
