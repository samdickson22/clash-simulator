"""Hold the released04 lease while03 drains, then resume only missing cases."""
import json,os,shlex,subprocess,time
from pathlib import Path
from bot.deckopt2.run import dump,sha,utc
from clean import read_rows
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');R=J/'new-cards';S=R/'screen'
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
REPO='/mpac/sdicks02/repos/clasher-bot-deckopt2'
LABEL='h04-budget-r2'

def command(argv):return subprocess.check_output(list(map(str,argv)),text=True,stderr=subprocess.STDOUT)
def remote(host,argv):return command(['ssh',host,shlex.join(list(map(str,argv)))])

def main():
    assert os.uname().nodename=='127x04'
    route=S/'routes-budget-handoff-r2.json';assert not route.exists()
    old=(('127x01',S/'finished-h01.json'),('127x03',S/'finished-h03a.json'),
         ('127x04',S/'finished-h04.json'),('127x03',S/'pool-h03b-2857209.json'))
    while True:
        receipts=[]
        for host,path in old:
            receipt=json.loads(path.read_text()) if host=='127x04' else json.loads(remote(host,['cat',path]))
            assert not receipt.get('errors'),receipt
            assert receipt['bank_sha256']==sha(S/'bank.json')
            receipts.append(receipt)
        done=all(r.get('finished_utc') for r in receipts)
        dump(S/'handoff-r2-status.json',dict(utc=utc(),done=done,receipts=receipts,pid=os.getpid(),pgid=os.getpgrp()))
        if done:break
        time.sleep(15)
    for host in ('127x01','127x03'):
        command(['rsync','-a',f'{host}:{S}/rows/',str(S/'rows')+'/'])
    data,rows=read_rows(R,'screen');assert len(rows)>=910
    print('ALL PRIOR PARTITIONS DRAINED CLEAN',utc(),len(rows),'completed',flush=True)
    print(command([PY,J/'routes.py','--root',R,'--stage','screen','--out',route,'--weights',f'{LABEL}:40']),flush=True)
    dump(S/'handoff-r2-ready.json',dict(utc=utc(),completed=len(rows),bank_sha256=sha(S/'bank.json'),route_sha256=sha(route),receipts=receipts))
    argv=[PY,str(J/'pool.py'),'--root',str(R),'--stage','screen','--route',str(route),'--label',LABEL,'--workers','40']
    os.execv(PY,argv)

if __name__=='__main__':
    try:main()
    except BaseException as error:
        dump(S/'handoff-r2-error.json',dict(utc=utc(),error=repr(error)));raise
