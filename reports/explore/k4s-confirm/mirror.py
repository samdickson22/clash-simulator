"""Immediate completed-block transport to01; no outcome reduction or04 access."""
import argparse,os,socket,subprocess,time,re,shlex
from pathlib import Path
from common import read,write,sha,utc,plan

def transport_prefix(j):
 r=read(j/'owned-copier-admission.json')['identity']
 assert r['pid']==os.getpid() and r['pgid']==os.getpgrp(),'copier root attribution changed'
 return ['env',f'T1_COPIER_PID={r["pid"]}',f'T1_COPIER_PGID={r["pgid"]}']

def register(j,hosts,phase):
 from host_audit import processes
 rows=processes();r=next(r for r in rows if r['pid']==os.getpid())
 target=j/'owned-copier-admission.json'
 if target.exists():
  old=read(target)['identity'];live=next((r for r in rows if r['pid']==old['pid']),None)
  assert live is None or any(live.get(k)!=v for k,v in old.items()),'finish/stop the prior owned copier before registering another phase'
 identity={k:r[k] for k in ('pid','pgid','start_ticks','cmdline_sha256','uid','exe')}
 receipt=j/'owned-copier-admission.json'
 write(receipt,dict(utc=utc(),host=socket.gethostname(),source_ip=socket.gethostbyname(socket.gethostname()),identity=identity,job=str(j),phase=phase,active=True))
 # Register before scientific supervisors launch; these bootstrap copies are not timing work.
 for h in hosts:
  if h!=socket.gethostname():subprocess.run(['rsync','-a',str(receipt),f'{h}:{receipt}'],check=True,timeout=30)
 return receipt


def copy_block(j,host,phase,identity):
 assert socket.gethostname()=='127x01' and host in plan()['compute']['hosts'] and host!='127x01'
 assert identity.replace('-','').isalnum() and re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',phase)
 source=f'{host}:{j}/{phase}/{identity}/';dest=j/'hub-blocks'/identity
 dest.mkdir(parents=True,exist_ok=True);os.chmod(dest,0o700)
 # complete.json is committed on hub only after the raw files and hashes arrive.
 subprocess.run(['rsync','-a','--rsync-path',shlex.join(transport_prefix(j)+['rsync']),'--exclude','complete.json','--exclude','hub-ack.json',source,str(dest)+'/'],check=True,timeout=900)
 pending=dest/'complete.pending.json'
 subprocess.run(['rsync','-a','--rsync-path',shlex.join(transport_prefix(j)+['rsync']),source+'complete.json',str(pending)],check=True,timeout=30)
 proof=read(pending);assert proof['descriptor']['id']==identity and len(proof['games'])==8
 for name,h in proof['games'].items():assert sha(dest/'games'/name)==h,name
 pending.replace(dest/'complete.json')
 ack=dict(utc=utc(),hub='127x01',source_host=host,block=identity,complete_sha256=sha(dest/'complete.json'),games=8,sealed=True)
 write(dest/'hub-ack.json',ack)
 subprocess.run(['rsync','-a','--rsync-path',shlex.join(transport_prefix(j)+['rsync']),str(dest/'hub-ack.json'),source+'hub-ack.json'],check=True,timeout=30)
 return ack

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--hosts',nargs='+',required=True);p.add_argument('--phase',required=True);p.add_argument('--once',action='store_true');a=p.parse_args();j=a.job
 assert socket.gethostname()=='127x01' and os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)=={62}
 assert re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',a.phase)
 register(j,a.hosts,a.phase)
 while not (j/'STOP-COPY').exists():
  for h in a.hosts:
   if h=='127x01':continue
   assert h in plan()['compute']['hosts']
   try:
    listing=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',h,shlex.join(transport_prefix(j)+['find',str(j/a.phase),'-mindepth','2','-maxdepth','2','-name','complete.json','-print'])],text=True,timeout=30)
    for line in listing.splitlines():
     identity=Path(line).parent.name
     if (j/'hub-blocks'/identity/'hub-ack.json').exists():continue
     ack=copy_block(j,h,a.phase,identity)
     print(__import__('json').dumps(ack),flush=True)
   except (subprocess.CalledProcessError,subprocess.TimeoutExpired,AssertionError) as e:
    write(j/f'copy-health-{h}.json',dict(utc=utc(),host=h,error=str(e),sealed=True))
  if a.once:break
  time.sleep(10)
if __name__=='__main__':main()
