"""Read-only r4 inventory probe, fed over ssh stdin to 127x04 (writes nothing there).
Executes the exact r4 a19_common/a19_resources bytes (SHA-checked locally) and prints
counts, blockers and X5 identity status only: no command lines."""
import sys,types,json,hashlib
srcs=json.loads(sys.stdin.readline())
for name in ('a19_common','a19_resources'):
    m=types.ModuleType(name);m.__file__=name+'.py';sys.modules[name]=m;exec(compile(srcs[name],name+'.py','exec'),m.__dict__)
R=sys.modules['a19_resources']
s=R.snapshot((),True)
rows=s.pop('inventory')
out={k:v for k,v in s.items()}
out['launch_blockers']=R.launch_blockers(s)
out['capacity_if_controller_only']=max(0,min(12,16-(s['admission_processes']+1)-5))
out['x5_present']={str(p):(p in {r['pid'] for r in rows}) for p in R.X5_FIT_IDENTITIES}
out['unknown_denied']=sorted({tuple(r['denied']) for r in rows if r['unknown']})
out['training_rows']=[dict(pid=r['pid'],parent=r['parent'],x5=r['pid'] in R.X5_FIT_IDENTITIES) for r in rows if r['training']]
print(json.dumps(out,sort_keys=True,default=str))
