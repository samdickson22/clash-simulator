"""OA-1 integration fixture on a source host: synthetic (random-byte) blocks; no game is played or read."""
import hashlib,json,os,sys
from pathlib import Path
TJ=Path(sys.argv[1]);host=sys.argv[2]
TEN=['K4-200','K4S-200','K4-180','K4-140','K4S-180','K4-160','K4S-160','K4-120','K4S-140','K4S-120']
EIGHT=[a for a in TEN if a not in ('K4-140','K4-120')]
def block(i,order,corrupt=False,size=12*2**20):
 ident=f'smoke-{i:04d}';d=TJ/'smoke'/ident;(d/'games').mkdir(parents=True)
 games={}
 for arm in order:
  name=f'{ident}-d27-{arm}.json';raw=os.urandom(size);(d/'games'/name).write_bytes(raw);games[name]=hashlib.sha256(raw).hexdigest()
 if corrupt:games[next(iter(games))]='0'*64
 (d/'complete.json').write_text(json.dumps(dict(host=host,descriptor=dict(id=ident,order=order),games=games,synthetic_fixture=True)))
block(3,TEN,corrupt=True);block(1,TEN,size=int(sys.argv[3])*2**20 if len(sys.argv)>3 else 12*2**20);block(2,EIGHT)
(TJ/'SYNTHETIC').write_text('OA-1 integration fixture; random bytes, not games\n')
