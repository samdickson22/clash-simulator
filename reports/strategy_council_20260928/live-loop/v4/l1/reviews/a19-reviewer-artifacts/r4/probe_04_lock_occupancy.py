"""Read-only: sample /proc/<seal child>/fd every 20 ms; report io.lock hold fraction per host
and new-acquisition counts. Fed to 127x04 over ssh -c; writes nothing there."""
import os,time,json,collections,sys
pid=2499719;secs=float(sys.argv[1]) if len(sys.argv)>1 else 300;base="/proc/%d/fd"%pid
t0=time.time();n=0;held=collections.Counter();opens=collections.Counter();prev=set();anyheld=0;cpu0=None
def cpu():
    s=open("/proc/%d/stat"%pid).read().rsplit(") ",1)[1].split();return (int(s[11])+int(s[12]))/os.sysconf("SC_CLK_TCK")
cpu0=cpu()
while time.time()-t0<secs:
    cur=set()
    for fd in os.listdir(base):
        try:l=os.readlink(base+"/"+fd)
        except OSError:continue
        if l.endswith(".io.lock"):cur.add((fd,l.rsplit("/",1)[1]))
    n+=1;anyheld+=bool(cur)
    for x in cur:held[x[1]]+=1
    for x in cur-prev:opens[x[1]]+=1
    prev=cur;time.sleep(0.02)
el=time.time()-t0
print(json.dumps(dict(utc_end=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),seconds=round(el,1),samples=n,
  hold_fraction={k:round(v/n,3) for k,v in held.items()},any_lock_fraction=round(anyheld/n,3),
  new_acquisitions=dict(opens),cpu_fraction=round((cpu()-cpu0)/el,3))))
