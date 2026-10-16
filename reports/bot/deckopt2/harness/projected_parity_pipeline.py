"""Light 05 coordinator for the requested implementation check on 03."""
import json,os,shlex,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');D=J/'projected-parity';R=J/'final-validation'
def cmd(args):return subprocess.check_output(list(map(str,args)),text=True,stderr=subprocess.STDOUT)
def run():
    D.mkdir(exist_ok=True)
    (D/'coordinator.json').write_text(json.dumps(dict(pid=os.getpid(),utc=cmd(['date','-u','+%Y-%m-%dT%H:%M:%SZ']).strip())))
    while not (R/'validation/bank.json').exists():time.sleep(15)
    files=['projected_fast.py','projected_parity.py','projected_entry.py','run-projected-parity.sh']
    cmd(['rsync','-a',*[J/f for f in files],f'127x03:{J}/'])
    receipt=D/'launch.json'
    assert not receipt.exists()
    output=cmd(['ssh','127x03',shlex.join(['/mpac/sdicks02/repos/clasher-bot-deckopt2/bot/detach.sh',str(D/'run.log'),str(receipt),'bash',str(J/'run-projected-parity.sh')])])
    print(output,flush=True)
    cmd(['rsync','-a',f'127x03:{receipt}',receipt])
    while not (D/'receipt.json').exists():
        result=subprocess.run(['rsync','-a','--ignore-missing-args',f'127x03:{D}/error.json',str(D)+'/'])
        if (D/'error.json').exists():raise RuntimeError((D/'error.json').read_text())
        time.sleep(20)
    print((D/'receipt.json').read_text(),flush=True)
if __name__=='__main__':run()
