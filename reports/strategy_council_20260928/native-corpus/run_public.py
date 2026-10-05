import json,subprocess,time,sys
from pathlib import Path
p=Path(__file__).resolve().parent
t=time.time();r=subprocess.run([sys.executable,'-u',str(p/'public_benchmark.py')]);(p/'public-exit.json').write_text(json.dumps({'exit_code':r.returncode,'started':t,'ended':time.time()})+'\n')
