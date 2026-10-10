"""Immediate completed-block transport to01; no outcome reduction or04 access."""
import argparse,os,socket,subprocess,time,re
from pathlib import Path
from common import read,write,sha,utc,plan

def copy_block(j,host,phase,identity):
 assert socket.gethostname()=='127x01' and host in plan()['compute']['hosts'] and host!='127x01'
 assert identity.replace('-','').isalnum() and re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',phase)
 source=f'{host}:{j}/{phase}/{identity}/';dest=j/'hub-blocks'/identity
 dest.mkdir(parents=True,exist_ok=True);os.chmod(dest,0o700)
 # complete.json is committed on hub only after the raw files and hashes arrive.
 subprocess.run(['rsync','-a','--exclude','complete.json','--exclude','hub-ack.json',source,str(dest)+'/'],check=True,timeout=900)
 pending=dest/'complete.pending.json'
 subprocess.run(['rsync','-a',source+'complete.json',str(pending)],check=True,timeout=30)
 proof=read(pending);assert proof['descriptor']['id']==identity and len(proof['games'])==8
 for name,h in proof['games'].items():assert sha(dest/'games'/name)==h,name
 pending.replace(dest/'complete.json')
 ack=dict(utc=utc(),hub='127x01',source_host=host,block=identity,complete_sha256=sha(dest/'complete.json'),games=8,sealed=True)
 write(dest/'hub-ack.json',ack)
 subprocess.run(['rsync','-a',str(dest/'hub-ack.json'),source+'hub-ack.json'],check=True,timeout=30)
 return ack

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--hosts',nargs='+',required=True);p.add_argument('--phase',required=True);p.add_argument('--once',action='store_true');a=p.parse_args();j=a.job
 assert socket.gethostname()=='127x01' and os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)=={62}
 while not (j/'STOP-COPY').exists():
  for h in a.hosts:
   if h=='127x01':continue
   assert h in plan()['compute']['hosts']
   try:
    listing=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',h,'find',str(j/a.phase),'-mindepth','2','-maxdepth','2','-name','complete.json','-print'],text=True,timeout=30)
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
