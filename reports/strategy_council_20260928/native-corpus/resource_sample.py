import json,subprocess,time
from pathlib import Path
p=Path(__file__).resolve().parent/'resources.jsonl'
ps=subprocess.check_output(['ps','-axo','pid,ppid,%cpu,rss,comm'],text=True)
rows=[]
for l in ps.splitlines()[1:]:
 a=l.split(None,4)
 if len(a)==5 and any(x in a[4].lower() for x in ['qemu','python']):rows.append(dict(pid=int(a[0]),ppid=int(a[1]),cpu=float(a[2]),rss_kib=int(a[3]),exe=a[4]))
r={'time':time.time(),'processes':rows,'swap':subprocess.check_output(['sysctl','vm.swapusage'],text=True).strip(),'hardware':subprocess.check_output(['sysctl','hw.memsize','hw.ncpu','machdep.cpu.brand_string'],text=True),'disk':subprocess.check_output(['df','-k','.'],text=True),'vm_stat':subprocess.check_output(['vm_stat'],text=True)}
with p.open('a') as f:f.write(json.dumps(r)+'\n')
print(r['swap']);print([x for x in rows if 'qemu' in x['exe']])
