import subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit
for name, path in [('diagnostic-initial',kit.INITIAL), ('diagnostic-it1',kit.FINAL)]:
    subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('evaluate.py')),'--checkpoint',str(path),'--name',name,'--games','4','--trace-games','4','--parallel','1'],check=True)
