"""K4S runner r1: SEALED health projection for 127x03/127x04 (run on 127x05).

One bounded LAN ssh per host per check, running only coreutils (cat/find/grep/ls/ps/who): never a game file, never
an outcome field. Reads progress.json, stop files, stop-reason, exits (complete flags), complete.json interference
flags, hub-ack counts, supervisor/copier identities; on 05 the hub copies and copy-health. Writes one JSON receipt.
Usage: k4s_health.py --phase smoke|reporting|replacement-rN --out receipt.json [--tag LABEL]
"""
import argparse,json,re,subprocess,time
from pathlib import Path

JOBS={'127x03':'/mpac/sdicks02/jobs/clasher/k4s-confirm-r1','127x04':'/mpac/sdicks02/jobs-k4s/k4s-confirm-r1'}
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']

REMOTE=r'''J={J};P={P}
echo "UTC $(date -u +%FT%TZ)"
echo "WHO $(who | wc -l)"
echo "LOAD $(cut -d' ' -f1-3 /proc/loadavg)"
echo "MEMAVAIL_KB $(grep MemAvailable /proc/meminfo | tr -s ' ' | cut -d' ' -f2)"
echo "STOPFILES $(test -e $J/STOP && echo 1 || echo 0) $(test -e $J/STOP-$(hostname) && echo 1 || echo 0)"
echo "PROGRESS $(tr -d '\n' < $J/progress.json 2>/dev/null)"
echo "COMPLETE $(find $J/$P -mindepth 2 -maxdepth 2 -name complete.json 2>/dev/null | wc -l)"
echo "HUBACK $(find $J/$P -mindepth 2 -maxdepth 2 -name hub-ack.json 2>/dev/null | wc -l)"
echo "EXITS $(ls $J/$P/exits 2>/dev/null | wc -l) FAILED $(grep -l '"complete": false' $J/$P/exits/*.json 2>/dev/null | wc -l)"
echo "INTERFERED $(grep -l '"interfered": true' $J/$P/*/complete.json 2>/dev/null | wc -l) SSHFLAG $(grep -l '"ssh_flagged": true' $J/$P/*/complete.json 2>/dev/null | wc -l) APTFLAG $(grep -l '"apt_flagged": true' $J/$P/*/complete.json 2>/dev/null | wc -l)"
test -e $J/$P/stop-reason.json && echo "STOPREASON $(tr -d '\n' < $J/$P/stop-reason.json | grep -o '"reason": *"[^"]*"')"
test -e $J/$P/supervisor-exit.json && echo "SUPEXIT $(tr -d '\n' < $J/$P/supervisor-exit.json | grep -o '"reason": *[^,]*' | head -1)"
test -e $J/$P/launch.json && echo "LAUNCH $(tr -d '\n' < $J/$P/launch.json)"
test -e $J/owned-copier-admission.json && echo "COPIERRECEIPT $(tr -d '\n' < $J/owned-copier-admission.json | grep -o '"active": *[a-z]*')"
S=$(grep -o '"supervisor_pid": *[0-9]*' $J/$P/launch.json 2>/dev/null | grep -o '[0-9]*$')
test -n "$S" && echo "SUPPROC $(ps -o pid=,pgid=,ni=,psr=,etimes=,stat= -p $S 2>/dev/null | tr -s ' ')"
echo "OWNEDGROUPS $(ps -eo pgid=,args= | grep -E "$J(/| |$)" | grep -v -e grep -e 'echo ' | awk '{{print $1}}' | sort -u | wc -l)"
'''

def parse(text):
 out={}
 for line in text.splitlines():
  k,_,v=line.partition(' ');out[k]=v.strip()
 return out

def host_check(h,phase):
 t=time.monotonic()
 try:
  r=subprocess.run(SSH+[h,REMOTE.format(J=JOBS[h],P=phase)],capture_output=True,text=True,timeout=60)
  d=parse(r.stdout);d['ssh_rc']=r.returncode
 except subprocess.TimeoutExpired:d={'ssh_rc':'timeout'}
 d['check_seconds']=round(time.monotonic()-t,2)
 prog=d.get('PROGRESS')
 if prog:
  try:
   p=json.loads(prog);d['PROGRESS']={k:p.get(k) for k in ('utc','phase','complete_local_blocks','complete_local_games','failed_blocks','queued','inflight','reason','memavailable_GiB')}
   d['PROGRESS']['console_positive']=p.get('console',{}).get('positive')
  except ValueError:pass
 return d

def hub(h,phase):
 j=Path(JOBS[h]);root=j/'hub-blocks'/phase
 acked=sum(1 for x in root.glob('*/hub-ack.json')) if root.exists() else 0
 back=sum(1 for x in root.glob('*/hub-ack.returned.json')) if root.exists() else 0
 health=j/f'copy-health-{h}.json'
 ch=json.loads(health.read_text()) if health.exists() else None
 if ch:ch={k:ch.get(k) for k in ('utc','listed','durable_on_hub','ack_returned','pending_return','error','block_errors','lifecycle_error')}
 rec=j/'owned-copier-admission.json'
 return dict(hub_durable=acked,hub_returned=back,copy_health=ch,copier_receipt_active=json.loads(rec.read_text()).get('active') if rec.exists() else None)

def main():
 a=argparse.ArgumentParser();a.add_argument('--phase',required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--tag',default='');x=a.parse_args()
 assert re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',x.phase)
 utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
 r=dict(schema='clasher.k4s.run-health.v1',study='PREREG-K4S',sealed=True,outcomes_read=False,utc=utc,phase=x.phase,tag=x.tag,hosts={h:dict(host=host_check(h,x.phase),hub=hub(h,x.phase)) for h in JOBS})
 x.out.parent.mkdir(parents=True,exist_ok=True);x.out.write_text(json.dumps(r,indent=1)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
