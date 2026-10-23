import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import os,time,json,subprocess

class SourceFetch:
 def __init__(self,C,L,m,source_code,phase,resultdir,source_argv):
  self.C=C;self.L=L;self.m=m;self.code=source_code;self.phase=phase;self.resultdir=resultdir
  self.owner=L.OwnedCPU(m);self.active=None;self.receipts=[];self.index=0;self.confirm_attempt=0;self.source_argv=source_argv
 def spawn(self,request,**kw):
  parent=os.getpid()
  return self.owner.capture(subprocess.Popen(self.source_argv(self.code,request),preexec_fn=lambda:self.L.parent_death(parent),**kw))
 def confirmation(self,request):
  r=dict(request,mode='confirm');self.confirm_attempt+=1
  with (self.resultdir/('fetch-%d-confirm-%d.stderr'%(r['index'],self.confirm_attempt))).open('xb') as err:
   p=self.spawn(r,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=err)
   raw,_=p.communicate(timeout=18)
  assert self.owner.exit(p)==0,'source confirmation SSH failed'
  receipt=json.loads(raw);assert receipt['source_reaped'] is True,'source reap not confirmed'
  self.receipts.append(receipt);self.active['confirmed']=True
  return receipt
 def get(self,source,dest,expected,seconds=600):
  self.C.lease_check();self.C.admission(self.m)
  assert self.active is None,'previous source fetch not confirmed'
  request=dict(self.phase,mode='stream',index=self.index,source=source,seconds=seconds)
  self.index+=1;self.active=dict(request=request,process=None,confirmed=False)
  end=time.monotonic()+seconds
  with dest.open('xb') as out,(self.resultdir/('fetch-%d.stderr'%request['index'])).open('xb') as err:
   p=self.spawn(request,stdout=out,stdin=subprocess.PIPE,stderr=err);self.active['process']=p
   os.set_blocking(p.stdin.fileno(),False);next_guard=0
   while p.poll() is None:
    assert time.monotonic()<end,'CPU input transfer timeout'
    if time.monotonic()>=next_guard:
     self.C.lease_check()
     with self.C.bounded(5):self.C.admission(self.m)
     next_guard=time.monotonic()+1
    try:os.write(p.stdin.fileno(),b'H\n')
    except (BlockingIOError,BrokenPipeError):pass
    time.sleep(.2)
   p.stdin.close()
   assert self.owner.exit(p)==0,'CPU input transfer failed'
  with self.C.bounded(20):receipt=self.confirmation(request)
  terminal=receipt['terminal'];assert terminal['status']=='pass','source helper failed'
  assert terminal['result']['sha256']==expected and terminal['result']['bytes']==dest.stat().st_size,'source byte receipt mismatch'
  self.C.write(self.resultdir/('fetch-%d-receipt.json'%request['index']),receipt)
  self.active=None
 def cleanup(self):
  errors=[];drain=None;receipt=None
  if self.active:
   p=self.active['process']
   if p is not None and p.stdin and not p.stdin.closed:
    try:os.write(p.stdin.fileno(),b'STOP\n')
    except (OSError,ValueError):pass
    p.stdin.close()
  # Exact local SSH children, including a stalled confirmation. This is not remote proof.
  try:drain=self.owner.drain(1,1,1)
  except BaseException as ex:
   drain=getattr(ex,'receipt',drain);errors.append('local SSH drain: '+repr(ex))
  if self.active and not self.active['confirmed']:
   try:receipt=self.confirmation(self.active['request'])
   except BaseException as ex:errors.append('source reap confirmation: '+repr(ex))
  # A timed-out confirmation is itself an exact tracked child, and cannot be abandoned.
  try:
   final=self.owner.drain(0,1,1)
   if not final['gone']:errors.append('local SSH survivor '+repr(final))
   drain=final
  except BaseException as ex:
   drain=getattr(ex,'receipt',drain);errors.append('confirmation drain: '+repr(ex))
  return dict(local=drain,source_confirmed=self.active is None or self.active['confirmed'],receipts=self.receipts,errors=errors)
