import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1]);roots={}
for arg in sys.argv[2:]:
    label,path=arg.split('=',1);root=Path(path);manifest={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.npz','.so'):
            h=hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda:f.read(1<<20),b''):h.update(block)
            manifest[str(p.relative_to(root))]=h.hexdigest()
    roots[label]=manifest
roots['utc']=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();out.write_text(json.dumps(roots,indent=2)+'\n');print(json.dumps({k:len(v) for k,v in roots.items() if isinstance(v,dict)}))
