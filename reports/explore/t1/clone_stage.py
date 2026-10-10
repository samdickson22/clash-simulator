"""Clone own T1 runtime from01 to a named host; no historical job mutation."""
import argparse,socket,subprocess
from pathlib import Path
from common import read,write,sha,utc,plan

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);a=p.parse_args();j=a.job;host=socket.gethostname();assert host in ('127x03','127x08')
 j.mkdir(parents=True,exist_ok=True);assert not (j/'repo').exists(),'never overwrite runtime'
 for name in ('repo','native','native-source','inputs','corpus','inherited-runtime-pin.json'):
  subprocess.run(['rsync','-a','--exclude','__pycache__',f'127x01:{j}/{name}',str(j)+'/'],check=True)
 inherited=read(j/'inherited-runtime-pin.json')
 for name,h in inherited['files'].items():assert sha(j/'repo'/name)==h,name
 for name,h in inherited['native_source'].items():assert sha(j/'native-source'/name)==h,name
 cfg=read(j/'repo/reports/explore/t1/plan.json')
 for n,h in [('native/clasher_core.abi3.so',cfg['source_reference']['native_sha256']),('inputs/R3a.pt',cfg['student']['checkpoint_sha256']),('inputs/main02.pt',cfg['policy']['checkpoint_sha256']),('inputs/R3a-calibration.json',cfg['student']['calibration_sha256'])]:assert sha(j/n)==h,n
 write(j/'staging.json',dict(utc=utc(),host=host,cloned_from='127x01',inherited_files_verified=len(inherited['files']),native_sha256=cfg['source_reference']['native_sha256']))
 # A B-window stop is declarative and can be written at any time, before or during work.
 if host=='127x08':write(j/'B-WINDOW-STOP-CONTRACT.json',dict(utc=utc(),stop_file=str(j/'STOP-127x08'),honored='one-second supervisor poll plus per-game tick check',coordinator_may_write=True))
if __name__=='__main__':main()
