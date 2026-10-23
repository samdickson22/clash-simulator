import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('host14 required')
import json,os,types,importlib.machinery
from pathlib import Path
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
C.verify_ready(json.loads(FILES['ready-plan.json']));C.no_cache(C.SOURCE)
assert os.sched_getaffinity(0)<=set(range(32)) and os.getpriority(os.PRIO_PROCESS,0)>=15
plan=json.loads((C.READY/'cpu-stage-inventory.json').read_bytes())
source=json.loads(FILES['inputs.json'])['source_files']
allowed={str(C.READY/n):r['sha256'] for n,r in plan['ready_files'].items()}
allowed.update({str(C.SOURCE/n):h for n,h in source.items()})
def source_code(loader,fullname):
 p=Path(loader.path);raw=p.read_bytes()
 assert p.suffix=='.py' and allowed[str(p)]==hashlib.sha256(raw).hexdigest(),'unverified Python source '+str(p)
 return compile(raw,str(p),'exec',dont_inherit=True,optimize=0)
def no_bytecode(*_):raise RuntimeError('sourceless bytecode refused')
importlib.machinery.SourceFileLoader.get_code=source_code
importlib.machinery.SourcelessFileLoader.get_code=no_bytecode
mode=sys.argv[1]
if mode=='check':
 import torch,numpy
 assert sys.version_info[:3]==(3,12,12) and torch.__version__=='2.7.1+cu118' and numpy.__version__=='2.3.5'
 print(json.dumps(dict(python=sys.version,torch=torch.__version__,numpy=numpy.__version__,cuda_initialized=torch.cuda.is_initialized())))
else:
 assert mode=='probe'
 script=C.SOURCE/'bot/pretrain_v1/checks/qualify_maxshape.py';raw=script.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==C.SCRIPT_SHA
 sys.argv=[str(script)]+sys.argv[2:]
 exec(compile(raw,str(script),'exec'),dict(__name__='__main__',__file__=str(script),__builtins__=__builtins__))
