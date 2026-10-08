"""Run the original trusted C56 filter against the newly fetched source bytes.

Only its source-path IO bindings change. Original source remains untouched.
Reproduce gzip filename/timestamp metadata from the archived output to make the
strong compressed-byte comparison meaningful; independently compare JSONL bytes.
"""
from __future__ import annotations
import ast, gzip, hashlib, io, json, os, socket, struct, sys, time, types
from pathlib import Path
ROOT=Path('/mpac/sdicks02/repos/clasher')
COUNCIL=ROOT/'reports/strategy_council_20260928'
DATA=COUNCIL/'imitation/data'
OLD=COUNCIL/'c56/data/payloads'
RAW=Path('/mpac/sdicks02/repos/clasher-local-data/il_replay')
OUT=DATA/'c56-refilter'
sys.path.insert(0,str(Path(__file__).parent))
from fetch_source import sha,write

def main():
    assert socket.gethostname()=='127x03'
    start=time.time()
    source=COUNCIL/'c56/data/scripts/fetch_payloads_c56.py'
    tree=ast.parse(source.read_text())
    tree.body=[n for n in tree.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MANIFEST' for t in n.targets))]
    env={'__file__':str(source),'__name__':'trusted_c56_filter','MANIFEST':json.loads((RAW/'hf_manifest.json').read_text())}
    exec(compile(tree,str(source),'exec'),env)
    def fetch(e):
        p=RAW/e['path']
        b=p.read_bytes()
        assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256']
        return b
    def original_gzip_metadata(path, mode):
        assert mode=='wt'
        original=OLD/(Path(path).name.removesuffix('.tmp')+'.gz')
        raw=original.read_bytes()
        assert raw[:3]==b'\x1f\x8b\x08' and raw[3] in (0,8),raw[:10]
        filename=raw[10:raw.index(b'\0',10)].decode() if raw[3]&8 else ''
        f=Path(path).open('wb')
        z=gzip.GzipFile(filename=filename,mode='wb',fileobj=f,mtime=struct.unpack('<I',raw[4:8])[0],compresslevel=9)
        # TextIOWrapper closes gzip; underlying file is flushed when released.
        return io.TextIOWrapper(z,encoding='utf-8',newline=None)
    env.update(OUT=OUT,fetch=fetch,gzip=types.SimpleNamespace(open=original_gzip_metadata))
    env['main']()
    comparisons=[]
    for p in sorted(OLD.glob('shard-*.jsonl.gz')):
        fresh=OUT/p.name
        a=gzip.decompress(p.read_bytes()); b=gzip.decompress(fresh.read_bytes())
        assert a==b,f'PAYLOAD MISMATCH {p.name}'
        comparisons.append({'file':p.name,'payload_bytes':len(a),'payload_sha256':hashlib.sha256(a).hexdigest(),'payload_byte_equal':True,'original_gzip_sha256':sha(p),'refilter_gzip_sha256':sha(fresh),'archive_byte_equal':p.read_bytes()==fresh.read_bytes()})
    assert len(comparisons)==52
    result={'filter_sha256':sha(source),'source_manifest_sha256':sha(RAW/'hf_manifest.json'),'files':comparisons,'payload_byte_equal':True,'archive_byte_equal':all(x['archive_byte_equal'] for x in comparisons),'shards':52,'wall_seconds':time.time()-start,'gzip_metadata':'original filename and mtime; freshly compressed refiltered source'}
    write(DATA/'receipts/T9-C56-equality.json',result)
    assert result['archive_byte_equal'],'JSONL payloads equal but archive encoding differs; review receipt before proceeding'
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
if __name__=='__main__':main()
