"""Reviewer model input: real 04 decoder records, A20 in-lock vs out-of-lock cost.

Run on 127x05 (not 04) on copies of real 04 compressed records. For each file:
  in_lock  = A20's locked work: open + fstat + read(MAX-buffered+1) + sha256
  outside  = what A20 moves out of the lock: GzipFile over BytesIO, line iteration,
             json.loads per line, trailing read(1)
The frozen scope held the lock for in_lock + outside + any consumer scoring inside
the with-block, so outside is a LOWER bound on the moved work and the ratio below
is an UPPER bound on A20's residual in-lock share.
Also records resource.getrusage peak RSS to bound the read(512MiB+1) allocation.
"""
import gzip,hashlib,io,json,os,resource,statistics,sys,time
MAX=512*1024*1024

def locked(path):
    t=time.perf_counter()
    with open(path,'rb') as f:
        if os.fstat(f.fileno()).st_size>MAX:raise ValueError('oversize')
        blob=f.read(MAX+1)
    pin=hashlib.sha256(blob).hexdigest()
    return blob,pin,time.perf_counter()-t

def outside(blob):
    t=time.perf_counter();n=0
    with io.BytesIO(blob) as b,gzip.GzipFile(fileobj=b) as g:
        for line in g:json.loads(line);n+=1
        assert not g.read(1)
    return n,time.perf_counter()-t

out={}
for path in sys.argv[1:]:
    rows=[]
    for _ in range(5):
        blob,pin,a=locked(path);n,b=outside(blob);rows.append((a,b))
    a=statistics.median(r[0] for r in rows);b=statistics.median(r[1] for r in rows)
    out[os.path.basename(path)]=dict(compressed_bytes=len(blob),sha256=pin,lines=n,locked_s=round(a,5),outside_s=round(b,5),
        locked_share_of_frozen_block_upper_bound=round(a/(a+b),5))
out['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
out['python']=sys.version.split()[0]
print(json.dumps(out,indent=1,sort_keys=True))
