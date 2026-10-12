"""Analyze the 04 system-bus baseline samples (local; reads only samples.txt). Core % = 100 * delta(utime+stime ticks)
/ (CLK_TCK * delta(wall seconds)) of the pinned dbus-daemon. Reports the whole window and rolling windows."""
import json,sys,hashlib
B=sys.argv[1];raw=open(B+'/samples.txt','rb').read();lines=raw.decode().splitlines()
begin=[l for l in lines if l.startswith('BEGIN')];end=[l for l in lines if l.startswith('END')];gone=[l for l in lines if l.startswith('GONE')]
clk=int(begin[0].split('clk_tck=')[1].split()[0]) if begin else 100
S=[]
for l in lines:
 if not l.startswith('S '):continue
 _,t,rest=l.split(' ',2);f=rest.rsplit(')',1)[1].split()
 S.append((float(t),int(f[11])+int(f[12]),int(f[19])))
starts={s for _,_,s in S}
def pct(a,b):return 100*(S[b][1]-S[a][1])/(clk*(S[b][0]-S[a][0]))
out=dict(samples=len(S),begin=begin,end=end,gone=gone,clk_tck=clk,start_ticks=sorted(starts),
 wall_seconds=round(S[-1][0]-S[0][0],1),whole_window_core_pct=round(pct(0,len(S)-1),4),samples_sha256=hashlib.sha256(raw).hexdigest())
for w in (30,60,120,300,600):
 vals=[];j=0
 for i in range(len(S)):
  while j<len(S) and S[j][0]-S[i][0]<w:j+=1
  if j>=len(S):break
  vals.append(pct(i,j))
 vals.sort()
 if vals:out[f'window_{w}s']=dict(n=len(vals),min=round(vals[0],4),p50=round(vals[len(vals)//2],4),p95=round(vals[int(.95*(len(vals)-1))],4),max=round(vals[-1],4),over_1pct=sum(v>1 for v in vals),over_0_7pct=sum(v>0.7 for v in vals))
print(json.dumps(out,indent=1))
