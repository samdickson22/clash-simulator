"""R64 package verification. Verification reads only; only R64_INTENT creates the dispatch intent."""
import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import os,json,hashlib,base64,zlib,time
from pathlib import Path
R64_ROOT=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r87-fix-20261023')
R64_AUTH='32269e4e1519451f2300ac5e53cb2bf03c6b0faf246066f39c75ad53b57d5cf1'
def R64_SHA(b):return hashlib.sha256(b).hexdigest()
def R64_CHECK(ctx,payload):
 fraw=base64.b64decode(ctx['freeze']);mraw=base64.b64decode(ctx['manifest']);receipt=ctx['review']
 if receipt.get('status')!='GO' or receipt.get('review')!='R88' or receipt.get('freeze_sha256')!=R64_SHA(fraw) or receipt.get('host')!='127x14' or type(receipt.get('maximum_new_M_measurements')) is not int or receipt.get('maximum_new_M_measurements')!=1 or receipt.get('authorization_sha256')!=R64_AUTH:raise RuntimeError('exact R88 review receipt required')
 freeze=json.loads(fraw)
 if receipt.get('manifest_sha256')!=R64_SHA(mraw) or receipt.get('source_freeze_sha256')!=freeze['source_freeze_sha256'] or receipt.get('r37_sha256')!='cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872':raise RuntimeError('R88 source-bound receipt required')
 if freeze['manifest_sha256']!=R64_SHA(mraw) or freeze['authorization_sha256']!=R64_AUTH:raise RuntimeError('freeze/config mismatch')
 manifest=json.loads(mraw);pins=json.loads(base64.b64decode(ctx['pins']))
 if R64_SHA(base64.b64decode(ctx['pins']))!=manifest['operational/package-pins.json'] or R64_SHA(payload.encode())!=pins['payload_sha256'] or len(payload)>126000:raise RuntimeError('transport pin/cap mismatch')
 files={k:base64.b64decode(v) for k,v in json.loads(zlib.decompress(base64.b64decode(payload)))['files'].items()}
 for n,b in files.items():
  if Path(n).is_absolute() or '..' in Path(n).parts or R64_SHA(b)!=manifest['operational/'+n]:raise RuntimeError('unreviewed transport '+n)
 if set(files)!=set(pins['bundle_files']):raise RuntimeError('bundle inventory mismatch')
 for n,h in pins['bundle_files'].items():
  if R64_SHA(files[n])!=h:raise RuntimeError('bundle bytes '+n)
 return manifest,files

def R64_BOOT(entry,ctx,payload):
 if entry not in ('controller.py','stage.py','admission.py','ready_stage.py','ready_admission.py','exposure.py','source_boot.py','ready_source.py'):raise RuntimeError('invalid bootstrap entry')
 code="import sys\nif sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')\nsys.dont_write_bytecode=True\nCTX="+repr(ctx)+"\nPAYLOAD="+repr(payload)+"\nR64_GATE_BYTES="+repr(R64_GATE_BYTES)+"\nexec(compile(R64_GATE_BYTES,'gate.py','exec'))\n_,FILES=R64_CHECK(CTX,PAYLOAD)\nif FILES['gate.py']!=R64_GATE_BYTES:raise RuntimeError('gate mismatch')\nexec(compile(FILES["+repr(entry)+"],"+repr(entry)+",'exec'))\n"

 if len(code.encode())>126000:raise RuntimeError('whole helper argument cap')
 return code

def R64_DISK(entry,file):
 global R64_CONTEXT,R64_GATE_BYTES
 b=Path(file).resolve().parent
 if b not in (R64_ROOT/'operational',R64_ROOT/'r'):raise RuntimeError('relocated raw entry refused')
 if b==R64_ROOT/'operational':
  ctx=dict(freeze=base64.b64encode((R64_ROOT/'FREEZE.json').read_bytes()).decode(),manifest=base64.b64encode((R64_ROOT/'MANIFEST.json').read_bytes()).decode(),review=json.loads((R64_ROOT/'R88-REVIEW.json').read_bytes()),pins=base64.b64encode((b/'package-pins.json').read_bytes()).decode())
 else:ctx=json.loads((b/'context.json').read_bytes())
 
 for p in b.rglob('*'):
  if p.name=='__pycache__' or p.suffix in ('.pyc','.pyo'):raise RuntimeError('helper cache refused')
 payload=(b/'payload.b64').read_text();manifest,files=R64_CHECK(ctx,payload)
 if entry not in files or (b/entry).read_bytes()!=files[entry]:raise RuntimeError('raw entry mismatch')
 if b==R64_ROOT/'operational':
  for n,h in manifest.items():
   if R64_SHA((R64_ROOT/n).read_bytes())!=h:raise RuntimeError('package pin '+n)
  if R64_SHA((R64_ROOT/'authorization.json').read_bytes())!=R64_AUTH:raise RuntimeError('authorization mismatch')
 else:
  if (b/'package-pins.json').read_bytes()!=base64.b64decode(ctx['pins']):raise RuntimeError('staged package pins mismatch')
  for n,data in files.items():
   if (b/n).read_bytes()!=data:raise RuntimeError('staged helper '+n)
  inputs=json.loads(files['inputs.json']);source=Path('/mpac/sdicks02/repos/clasher-M-host14-source-20261023')
  if R64_SHA((b/'archive.tar').read_bytes())!='73527481b5010e9a19a1090eee49710f45ae77d3f97a8dc9d1bcb61d40eaae13':raise RuntimeError('source archive mismatch')
  for n,h in inputs['source_files'].items():
   if R64_SHA((source/n).read_bytes())!=h:raise RuntimeError('source mismatch '+n)
  if {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}!=set(inputs['source_files']):raise RuntimeError('source inventory mismatch')
  if R64_SHA((b/'anchors/M/anchor.pt').read_bytes())!='947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4':raise RuntimeError('anchor mismatch')
 R64_CONTEXT=ctx;R64_GATE_BYTES=files['gate.py']

def R64_INTENT(ctx):
 permit=json.loads((R64_ROOT/'PARENT-DISPATCH.json').read_bytes())
 if permit.get('freeze_sha256')!=R64_SHA(base64.b64decode(ctx['freeze'])) or permit.get('host')!='127x14' or permit.get('allow_once') is not True or permit.get('no_reservation') is not True or not 0<=time.time()-permit['checked_epoch']<=60:raise RuntimeError('fresh parent arbitration required')
 path=R64_ROOT.parent/'r64-M-new-measurement.intent'
 with path.open('x') as f:
  json.dump(dict(host='127x14',review=ctx['review'],parent_dispatch=permit,created_epoch=time.time(),automatic_retry=False),f);f.flush();os.fsync(f.fileno())
 fd=os.open(str(path.parent),os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def R77_READY_PERMIT(ctx):
 permit=ctx['cpu_stage']
 if permit.get('freeze_sha256')!=R64_SHA(base64.b64decode(ctx['freeze'])) or permit.get('host')!='127x14' or permit.get('cpu_only') is not True or permit.get('no_reservation') is not True or not 0<=time.time()-permit['checked_epoch']<=60:raise RuntimeError('fresh parent CPU stage arbitration required')
 return permit

def R77_ARGUMENTS(ctx,payload):
 lengths={}
 for name in ('controller.py','stage.py','admission.py','ready_stage.py','ready_admission.py','exposure.py','source_boot.py','ready_source.py'):
  code=R64_BOOT(name,ctx,payload);lengths[name]=len(code.encode())
  if name in ('stage.py','ready_stage.py'):
   request=json.dumps(dict(name='M-host14-ready-stage-20261023' if name=='ready_stage.py' else 'M-host14-stage-20261023',workers=6,pss_gb=2,gpu_gb=0,grace=120,cwd='/mpac/sdicks02/jobs/clasher/lease-20261022',cmd=['/bin/python3','-B','-c',code]))
   if len(request.encode())>126000:raise RuntimeError('packed stage argument cap')
   lengths['packed-'+name]=len(request.encode())
 _,files=R64_CHECK(ctx,payload);plan=json.loads(files['ready-plan.json'])
 sources=[plan['inventory_source']]+[v['source_path'] for v in plan['archives'].values()]
 for i,source in enumerate(sources):
  for mode in ('stream','confirm'):
   request=dict(mode=mode,index=i,source=source,seconds=600,token='0'*32,phase_started_epoch=time.time())
   argv=R78_SOURCE_SSH(R64_BOOT('ready_source.py',ctx,payload),request)
   lengths['source-SSH-'+mode+'-'+str(i)]=max(len(v.encode()) for v in argv)
 return lengths

def R78_SOURCE_SSH(code,request):
 import shlex
 remote='cd /mpac/sdicks02/jobs/clasher/M-physical-host14-r87-fix-20261023 && exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-31 nice -n 15 /bin/python3 -B -c '+shlex.quote(code)+' '+shlex.quote(json.dumps(request,separators=(',',':')))
 if max(len(code.encode()),len(remote.encode()),len(json.dumps(request).encode()))>126000:raise RuntimeError('source SSH argument cap')
 return ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','ControlMaster=no','-o','ControlPath=none','-o','StrictHostKeyChecking=yes','127x05',remote]
