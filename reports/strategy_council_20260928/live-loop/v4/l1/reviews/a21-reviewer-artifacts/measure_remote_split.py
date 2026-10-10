"""Reviewer (A21): split a real 03 record op into lock-retained vs unlocked parts.

Runs on 05 (nice 19). Streams real 03 records over a reviewer-private ControlMaster
(same wrapper flags as the pinned A19 ssh wrapper) into memory only; nothing is
written to disk. Measures (a) mux session fixed cost, (b) whole-transfer wall,
(c) the A18 consumer CPU (gunzip + per-line json.loads + identity checks + sha)
on the in-memory snapshot, and (d) remote `python3 -` hash-batch fixed cost.
Usage: measure_remote_split.py HOST PATH [PATH...]  -> JSON on stdout
"""
import gzip,hashlib,io,json,shlex,statistics,subprocess,sys,time
SOCK='/tmp/sdicks02/a21-review/sock/%r@%h-%p-rev'
def ssh(host,cmd,inp=None):
    argv=['/usr/bin/ssh','-o','ControlMaster=auto','-o','ControlPath='+SOCK,'-o','ControlPersist=120',
          '-o','BatchMode=yes','-o','ConnectTimeout=10',host,cmd]
    t=time.perf_counter();r=subprocess.run(argv,input=inp,capture_output=True,timeout=120,check=True)
    return time.perf_counter()-t,r.stdout
def consume(blob):
    t=time.perf_counter();h=hashlib.sha256();n=0
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as s:
        for n,line in enumerate(s,1):
            row=json.loads(line);row.get('schema');row.get('episode_id');row.get('source_seq');h.update(line)
    return time.perf_counter()-t,n
host=sys.argv[1];out=dict(host=host,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),files=[])
first,_=ssh(host,'true');out['first_session_with_master_setup_s']=first
out['mux_true_s']=[ssh(host,'true')[0] for _ in range(5)]
for p in sys.argv[2:]:
    q=shlex.quote(p);xs=[];blob=None
    for _ in range(3):
        dt,blob=ssh(host,'test ! -L '+q+' && exec nice -n 19 ionice -c 3 cat -- '+q);xs.append(dt)
    sha=hashlib.sha256(blob).hexdigest()
    cpu=[consume(blob)[0] for _ in range(2)];lines=consume(blob)[1]
    out['files'].append(dict(path=p,bytes=len(blob),sha256=sha,lines=lines,transfer_s=xs,consumer_cpu_s=cpu,
        retained_hold_fraction=statistics.median(xs)/(statistics.median(xs)+statistics.median(cpu))))
script=("import pathlib,hashlib,json\npins=%r\nfor name,d in pins.items():\n p=pathlib.Path(name)\n if p.is_symlink():raise ValueError('a')\n hashlib.sha256(p.read_bytes()).hexdigest()\nprint(json.dumps({'verified':len(pins)}))\n"%({sys.argv[2]:'0'*64})).encode()
out['remote_hash_batch_one_record_s']=[ssh(host,'nice -n 19 python3 -',script)[0] for _ in range(3)]
script0=b"import json\nprint(json.dumps({'verified':0}))\n"
out['remote_python_fixed_s']=[ssh(host,'nice -n 19 python3 -',script0)[0] for _ in range(3)]
print(json.dumps(out,indent=1))
