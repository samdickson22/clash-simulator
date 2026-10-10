"""Reviewer (A21 r1) adversarial differential tests: A20 (frozen remote whole-context) vs A21.

Synthetic only: SSH is replaced by exact local children (bash -c <the frozen remote command>,
or a scripted Python child). Run with the package dir and its composed-runtime on sys.path:
  PYTHONPATH=<pkg>/composed-runtime:<pkg> python3.12 -B -m unittest test_rev_a21 -v
The frozen I/O module is the A18-pinned queue_audit_io_v4.py (1df4d0c1...).
"""
import contextlib,fcntl,gzip,hashlib,importlib.util,json,os,random,subprocess,sys,tempfile,threading,time,unittest,zlib
from pathlib import Path
from unittest.mock import patch
import a21_io as A
import a20_io as OLD
PKG=Path(A.__file__).resolve().parents[1];L=PKG.parents[1]
FROZEN=L/'prepared/amendment18-review-r2/queue_audit_io_v4.py'
def sha(b):return hashlib.sha256(b).hexdigest()
def frozen():
    s=importlib.util.spec_from_file_location('rev_fixture_io',FROZEN);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
CHILD={
 # stream the file in random tiny chunks with flushes (exercises coalescing)
 'dribble':"import sys,random,time\nb=open(sys.argv[1],'rb').read();i=0;r=random.Random(7)\nwhile i<len(b):\n n=r.randint(1,700);sys.stdout.buffer.write(b[i:i+n]);sys.stdout.flush();i+=n\n",
 # full correct bytes, then nonzero exit (SSH failure after the stream completed)
 'exit255':"import sys;sys.stdout.buffer.write(open(sys.argv[1],'rb').read());sys.stdout.flush();sys.exit(255)",
 # half the bytes then nonzero exit (connection drop mid-transfer)
 'half':"import sys;b=open(sys.argv[1],'rb').read();sys.stdout.buffer.write(b[:len(b)//2]);sys.stdout.flush();sys.exit(255)",
 # never-ending stream of valid-looking bytes
 'endless':"import sys\nb=open(sys.argv[1],'rb').read()\nwhile True:sys.stdout.buffer.write(b);sys.stdout.flush()\n",
 # exits 0 but a detached grandchild keeps stderr open (a ControlPersist master that did NOT detach stdio)
 'heldstderr':"import os,sys,time\nif os.fork()==0:\n os.setsid();time.sleep(5);os._exit(0)\nsys.stdout.buffer.write(open(sys.argv[1],'rb').read());sys.stdout.flush();os._exit(0)",
 # slow but steady progress: 2 KiB every 50 ms (idle-timeout would pass, whole-transfer must not)
 'slow':"import sys,time\nb=open(sys.argv[1],'rb').read()\nfor i in range(0,len(b),2048):sys.stdout.buffer.write(b[i:i+2048]);sys.stdout.flush();time.sleep(.05)\n",
}
class Rev(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=frozen();self.children=[];self.mode='normal';self.p=self.root/'rows.gz'
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        for t in (A,OLD):self.stack.enter_context(patch.object(t,'LOCK_ROOT',self.root))
        self.stack.enter_context(patch.object(self.m,'ROOTS',(str(self.root)+'/',)))
        self.stack.enter_context(patch.object(self.m,'local',side_effect=lambda h:h=='127x04'))
        popen=subprocess.Popen
        def spawn(argv,*a,**k):
            if argv[0]=='ssh':
                argv=['bash','-c',argv[-1]] if self.mode=='normal' else [sys.executable,'-B','-c',CHILD[self.mode],str(self.p)]
            c=popen(argv,*a,**k);self.children.append(c);return c
        self.stack.enter_context(patch.object(subprocess,'Popen',side_effect=spawn))
    def locked_by_other(self,h):
        with (self.root/(h+'.io.lock')).open('a') as f:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN);return False
            except BlockingIOError:return True
    def outcome(self,adapter,host,blob,pin=None,consumer=list):
        """(kind, value, ledger): rows or exception class+message, plus admission ledger."""
        self.p.write_bytes(blob);pin=sha(blob) if pin is None else pin
        with self.m.capture_evidence() as e:
            try:
                with adapter.io_locks(self.m,lambda:None):
                    with self.m.records(host,str(self.p),pin) as rows:v=consumer(rows)
                return ('ok',v,dict(e))
            except BaseException as x:return ('err',type(x).__name__,dict(e))
    def corrupt_classes(self):
        raw=b''.join(json.dumps(dict(source_seq=i,v='x'*i)).encode()+b'\n' for i in range(300))
        g=gzip.compress(raw,mtime=0);out={}
        out['good']=g;out['empty']=b'';out['not_gzip']=b'plain text\n';out['truncated']=g[:len(g)//2];out['truncated_trailer']=g[:-3]
        b=bytearray(g);b[-8]^=1;out['crc_flip']=bytes(b)
        b=bytearray(g);b[-1]^=1;out['isize_flip']=bytes(b)
        b=bytearray(g);b[len(g)//2]^=0x40;out['body_flip']=bytes(b)
        out['trailing_garbage']=g+b'GARBAGE';out['two_members']=g+gzip.compress(b'{"tail":1}\n',mtime=0);out['zero_pad']=g+b'\0'*64
        return out
    # 1. Scientific identity across every input class, remote hosts, pin of those bytes
    def test_identity_all_classes_remote_with_own_pin(self):
        for host in ('127x03','127x08'):
            for name,blob in self.corrupt_classes().items():
                with self.subTest(host=host,cls=name):
                    o,n=self.outcome(OLD,host,blob),self.outcome(A,host,blob)
                    self.assertEqual(o[0],n[0]);self.assertEqual(o[2],n[2])
                    if o[0]=='ok':self.assertEqual(o[1],n[1])
                    else:self.assertEqual(n[2],{})
    # 2. Same corruptions with the GOOD pin: neither ever passes or notes evidence
    def test_corrupt_bytes_with_good_pin_never_admitted(self):
        c=self.corrupt_classes();good=sha(c['good'])
        for name,blob in c.items():
            if name=='good':continue
            for ad in (OLD,A):
                with self.subTest(cls=name,adapter=ad.__name__):
                    r=self.outcome(ad,'127x03',blob,good);self.assertEqual(r[0],'err');self.assertEqual(r[2],{})
            self.assertEqual(self.outcome(A,'127x03',blob,good)[1],'ValueError')   # A21: SHA before any gzip
    # 3. Partial consumers / consumer exceptions: identical, no ledger, budget released
    def test_consumer_failures_identical_and_budget_released(self):
        blob=self.corrupt_classes()['good']
        def one(rows):return next(rows)
        def boom(rows):next(rows);raise KeyError('consumer')
        for c in (one,boom):
            o,n=self.outcome(OLD,'127x03',blob,consumer=c),self.outcome(A,'127x03',blob,consumer=c)
            self.assertEqual(o,n);self.assertEqual(n[0],'err');self.assertEqual(n[2],{})
    # 4. Tiny/random pipe reads: snapshot bytes == source bytes == hashed bytes
    def test_dribbled_stream_snapshot_equals_hashed_bytes(self):
        raw=b''.join(b'%d,'%i for i in range(60000));blob=gzip.compress(raw,mtime=0);self.p.write_bytes(blob)
        self.mode='dribble';seen={}
        real=A.Snapshot.close
        def spy(s):seen['joined']=b''.join(s.chunks)+bytes(s.pending);seen['sha']=s.sha.hexdigest();seen['n']=len(s.chunks);return real(s)
        with patch.object(A.Snapshot,'close',spy),self.m.capture_evidence() as e,A.io_locks(self.m,lambda:None):
            with self.m.records('127x03',str(self.p),sha(blob)) as rows:self.assertEqual(rows.read(),raw)
        self.assertEqual(seen['joined'],blob);self.assertEqual(seen['sha'],sha(blob));self.assertEqual(e,{('127x03',str(self.p)):sha(blob)})
        self.assertLessEqual(seen['n'],len(blob)//A.CHUNK_BYTES+1)   # coalesced, not one object per pipe read
    # 5. SSH nonzero exit after a complete correct stream / mid-transfer
    def test_ssh_failure_after_full_stream_and_midtransfer(self):
        blob=self.corrupt_classes()['good']
        for mode in ('exit255','half'):
            self.mode=mode
            with self.subTest(mode=mode):
                o,n=self.outcome(OLD,'127x03',blob),self.outcome(A,'127x03',blob)
                self.assertEqual((o[0],o[2]),('err',{}));self.assertEqual((n[0],n[2]),('err',{}))
                self.assertEqual(n[1],'CalledProcessError')
                self.assertTrue(all(c.poll() is not None for c in self.children));self.assertFalse(self.locked_by_other('127x03'))
    # 6. Never-ending stream: A21 fails closed at the bound, never yields, releases lock and budget
    def test_endless_stream_fails_closed_before_yield(self):
        blob=self.corrupt_classes()['good'];self.mode='endless';yielded=[]
        with patch.object(A,'MAX_SNAPSHOT_BYTES',4*1024*1024):
            r=self.outcome(A,'127x03',blob,consumer=lambda rows:yielded.append(1))
        self.assertEqual((r[0],r[1],r[2]),('err','ValueError',{}));self.assertEqual(yielded,[])
        self.assertTrue(all(c.poll() is not None for c in self.children));self.assertFalse(self.locked_by_other('127x03'))
        with patch.object(A,'TRANSFER_SECONDS',.3):
            r=self.outcome(A,'127x03',blob,consumer=lambda rows:yielded.append(1))
        self.assertEqual(r[0],'err');self.assertEqual(yielded,[])
    # 7. A grandchild holding stderr open: fail-closed timeout (documents the ControlPersist dependency)
    def test_stderr_held_by_detached_grandchild_times_out_closed(self):
        blob=self.corrupt_classes()['good'];self.mode='heldstderr'
        with patch.object(A,'TRANSFER_SECONDS',1):
            t=time.monotonic();r=self.outcome(A,'127x03',blob)
        self.assertEqual((r[0],r[1],r[2]),('err','TimeoutError',{}));self.assertLess(time.monotonic()-t,4)
        self.assertFalse(self.locked_by_other('127x03'))
    # 8. Whole-transfer (not idle) bound: steady progress past the bound still fails
    def test_bound_is_whole_transfer_not_idle(self):
        blob=os.urandom(64*1024);self.mode='slow'           # ~32 writes x 50 ms = ~1.6 s
        with patch.object(A,'TRANSFER_SECONDS',.5):r=self.outcome(A,'127x03',blob,pin=sha(blob))
        self.assertEqual((r[0],r[1]),('err','TimeoutError'))
        with patch.object(A,'TRANSFER_SECONDS',30):r=self.outcome(A,'127x03',blob,pin=sha(blob))
        self.assertEqual(r[1],'BadGzipFile')                # passes the bound, then the same gzip failure as A20
        self.assertEqual(self.outcome(OLD,'127x03',blob,pin=sha(blob))[1],'BadGzipFile')
    # 9. Production nesting (audit left/right on one host): identical rows/ledger; lock free inside; aggregate budget
    def test_left_right_pair_identical_unlocked_and_aggregate(self):
        a=gzip.compress(b'{"a":1}\n'*5000,mtime=0);b=gzip.compress(b'{"a":1}\n'*5000,mtime=1)
        pa,pb=self.root/'left.gz',self.root/'right.gz';pa.write_bytes(a);pb.write_bytes(b)
        def run(ad,probe):
            with self.m.capture_evidence() as e,ad.io_locks(self.m,lambda:None):
                with self.m.records('127x03',str(pa),sha(a)) as left,self.m.records('127x03',str(pb),sha(b)) as right:
                    free=not self.locked_by_other('127x03') if probe else None
                    rows=[(x,next(right)) for x in left];self.assertEqual(next(right,b''),b'')
            return rows,dict(e),free
        o,n=run(OLD,True),run(A,True)
        self.assertEqual(o[:2],n[:2]);self.assertFalse(o[2]);self.assertTrue(n[2])
        with patch.object(A,'MAX_SNAPSHOT_BYTES',len(a)+len(b)-1):
            with self.assertRaisesRegex(ValueError,'aggregate'):run(A,False)
    # 10. Remote hashes: identical success ledger; nonzero exit / wrong count identical failure, no ledger
    def test_hashes_identity_and_failures(self):
        f=self.root/'src.py';f.write_bytes(b'print(1)\n');pins={str(f):sha(f.read_bytes())}
        def go(ad,p):
            with self.m.capture_evidence() as e:
                try:
                    with ad.io_locks(self.m,lambda:None):self.m.hashes('127x03',p)
                    return 'ok',dict(e)
                except BaseException as x:return type(x).__name__,dict(e)
        ok_old=go(OLD,pins);ok_new=go(A,pins);self.assertEqual(ok_old,ok_new);self.assertEqual(ok_new[0],'ok')
        bad={str(f):'0'*64};self.assertEqual(go(OLD,bad),('CalledProcessError',{}));self.assertEqual(go(A,bad),('CalledProcessError',{}))
    # 11. Local 04 path reimplemented by A21 is result-identical to A20 (A20 io_locks no longer runs)
    def test_local04_records_and_read_identical_to_a20(self):
        for name,blob in self.corrupt_classes().items():
            with self.subTest(cls=name):
                o,n=self.outcome(OLD,'127x04',blob),self.outcome(A,'127x04',blob)
                self.assertEqual((o[0],o[2]),(n[0],n[2]))
                if o[0]=='ok':self.assertEqual(o[1],n[1])
        meta=self.root/'m.json';meta.write_bytes(b'{"k":[1,2]}')
        for ad in (OLD,A):
            with self.m.capture_evidence() as e,ad.io_locks(self.m,lambda:None):v=self.m.read('127x04',str(meta))
            self.assertEqual((v,dict(e)),(({'k':[1,2]},sha(b'{"k":[1,2]}')),{('127x04',str(meta)):sha(b'{"k":[1,2]}')}))
    # 12. Remote metadata read: frozen raw() already had a 30 s whole-transfer bound; A21 keeps 30 s
    def test_frozen_remote_read_bound_matches(self):
        src=FROZEN.read_text();self.assertIn('capture_output=True,check=True,timeout=30',src)
        self.assertIn("capture_output=True,check=True,timeout=60",src)
        self.assertIn('proc.wait(timeout=30)',src)                     # frozen records: post-consumption wait only
        self.assertEqual((A.TRANSFER_SECONDS,A.HASH_SECONDS),(30,60))
if __name__=='__main__':unittest.main()
