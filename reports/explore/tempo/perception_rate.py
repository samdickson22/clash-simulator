"""Completion-count telemetry only; never decode perception/evaluation records."""
import argparse,json,os,time,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--auto',action='store_true');p.add_argument('--baseline-seconds',type=int,default=120);a=p.parse_args()
roots=[Path('/mpac/sdicks02/repos/clasher-v4-cache/epoch-capture-offload-r1')/f'epoch-{i:02d}' for i in (7,9,15,17)]
if a.auto:
 roots=[]
 for pid in subprocess.check_output(['nice','-n','10','chrt','--idle','0','nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).split():
  try:
   argv=Path('/proc/'+pid+'/cmdline').read_bytes().decode().split('\0')
   output=argv[argv.index('--output')+1]
   if output.startswith('/mpac/sdicks02/repos/clasher'):roots.append(Path(output))
  except (OSError,ValueError,IndexError):continue
 if not roots:raise SystemExit('no capture completion journals found')
offsets={};start=time.monotonic();last=start;rates=[];step=0
def count_new(initial=False):
 n=0
 for root in roots:
  for f in root.glob('body-*/*-completion.jsonl'):
   size=f.stat().st_size
   if initial: offsets[str(f)]=size;continue
   at=offsets.get(str(f),0)
   if size>at:
    with f.open('rb') as h:h.seek(at);data=h.read()
    n+=data.count(b'\n');offsets[str(f)]=size
 return n
count_new(True);a.out.parent.mkdir(parents=True,exist_ok=True)
with a.out.open('a',buffering=1) as output:
 while time.monotonic()-start<10800:
  time.sleep(10);now=time.monotonic();n=count_new();rate=n/(now-last);last=now;step+=1
  output.write(json.dumps(dict(step=step,frames_per_second_step=rate,completed_records=n,utc=time.time()))+'\n')
  if now-start<=a.baseline_seconds+1:rates.append((n,now))
  if not a.out.with_suffix('.baseline.json').exists() and now-start>=a.baseline_seconds:
   baseline=sum(r[0] for r in rates)/(rates[-1][1]-start)
   a.out.with_suffix('.baseline.json').write_text(json.dumps(dict(baseline=baseline,seconds=rates[-1][1]-start,completed_records=sum(r[0] for r in rates),source='own GPU job completion journal counts; no payload decoding',roots=list(map(str,roots)),field='frames_per_second_step',log_path=str(a.out)))+'\n')
