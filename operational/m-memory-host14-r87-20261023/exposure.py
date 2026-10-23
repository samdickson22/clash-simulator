import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x05':raise RuntimeError('central exposure host05 required')
import json,base64,types,time
from pathlib import Path
root=Path('/mpac/sdicks02/jobs/clasher')
intent=json.loads((root/'r64-M-new-measurement.intent').read_bytes())
assert intent['host']=='127x14' and intent['review']==CTX['review'],'global dispatch intent belongs to another host or freeze'
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
C.write(root/'r64-M-new-measurement.exposure',dict(host='127x14',review=CTX['review'],epoch=time.time(),automatic_retry=False))
