"""OA-1 tests: mirror_k4s remote commands are accepted by the FROZEN ssh_transport.copier_activity guard, and the
hub-side proof checks reject wrong inventories. Run: K4S_FROZEN=<frozen k4s-confirm dir> pytest test_mirror_k4s.py"""
import json,os,shlex,sys
from pathlib import Path
import pytest
FROZEN=Path(os.environ['K4S_FROZEN']);sys.path[:0]=[str(FROZEN),str(Path(__file__).parent)]
import ssh_transport
import mirror_k4s as M

J=Path('/mpac/sdicks02/jobs/clasher/k4s-confirm-r1')
ROOT=dict(pid=4242,pgid=4242,start_ticks=1,cmdline_sha256='0'*64,uid=3822945,exe='/usr/bin/python3')

def receipt(tmp,**kw):
 j=tmp/'k4s-confirm-r1';j.mkdir(exist_ok=True)
 r=dict(utc='x',host=M.HUB,source_ip=M.HUB_IP,identity=ROOT,job=str(j),phase='reporting',source_host='127x03',active=True);r.update(kw)
 (j/'owned-copier-admission.json').write_text(json.dumps(r));return j

def remote_row(cmd,conn=M.HUB_IP+' 50000 129.65.221.13 22'):
 return dict(pid=99,ppid=98,cmd=cmd,ssh_connection_snapshot=conn,copier_identity_snapshot={})

def env_of(pid=ROOT['pid'],pgid=ROOT['pgid']):return lambda row:{'T1_COPIER_PID':str(pid),'T1_COPIER_PGID':str(pgid)}

def find_cmd(j,phase='reporting'):
 # The process the remote shell execs: argv after `env VAR=..` is consumed by env(1).
 return shlex.join(['find',str(j/phase),'-mindepth','2','-maxdepth','2','-name','complete.json','-print'])

def test_find_accepted(tmp_path,monkeypatch):
 j=receipt(tmp_path);monkeypatch.setattr(ssh_transport.socket,'gethostname',lambda:'127x03')
 assert ssh_transport.copier_activity(remote_row(find_cmd(j)),[],j,env_reader=env_of())

def test_find_via_shell_with_env_prefix_accepted(tmp_path,monkeypatch):
 j=receipt(tmp_path);monkeypatch.setattr(ssh_transport.socket,'gethostname',lambda:'127x03')
 inner=shlex.join(['env','T1_COPIER_PID=4242','T1_COPIER_PGID=4242','find',str(j/'reporting'),'-mindepth','2','-maxdepth','2','-name','complete.json','-print'])
 assert ssh_transport.copier_activity(remote_row(shlex.join(['bash','-c',inner])),[],j,env_reader=lambda r:{})

def test_rsync_server_sender_and_receiver_accepted(tmp_path,monkeypatch):
 j=receipt(tmp_path);monkeypatch.setattr(ssh_transport.socket,'gethostname',lambda:'127x03')
 for cmd in (f'rsync --server --sender -logDtpre.iLsfxCIvu . {j}/reporting/primary-0001/',
             f'rsync --server -logDtpre.iLsfxCIvu . {j}/reporting/primary-0001/hub-ack.json'):
  assert ssh_transport.copier_activity(remote_row(cmd),[],j,env_reader=env_of())

def test_wrong_source_ip_or_identity_rejected(tmp_path,monkeypatch):
 j=receipt(tmp_path);monkeypatch.setattr(ssh_transport.socket,'gethostname',lambda:'127x03')
 assert not ssh_transport.copier_activity(remote_row(find_cmd(j),conn='127.0.1.1 5 129.65.221.13 22'),[],j,env_reader=env_of())
 assert not ssh_transport.copier_activity(remote_row(find_cmd(j)),[],j,env_reader=env_of(pid=1))
 assert not ssh_transport.copier_activity(remote_row(f'rsync --server . /etc/passwd'),[],j,env_reader=env_of())

def test_inactive_receipt_rejected(tmp_path,monkeypatch):
 j=receipt(tmp_path,active=False);monkeypatch.setattr(ssh_transport.socket,'gethostname',lambda:'127x03')
 assert not ssh_transport.copier_activity(remote_row(find_cmd(j)),[],j,env_reader=env_of())

def proof(identity,order,host='127x03'):
 return dict(host=host,descriptor=dict(id=identity,order=order),games={f'{identity}-d27-{a}.json':'0'*64 for a in order})

TEN=['K4-200','K4S-200','K4-180','K4-140','K4S-180','K4-160','K4S-160','K4-120','K4S-140','K4S-120']

def test_expected_games_8_and_10():
 assert M.expected_games(proof('primary-0700',TEN[:3]+TEN[4:7]+TEN[8:]),'primary-0700')==8
 assert M.expected_games(proof('smoke-0003',TEN),'smoke-0003')==10

def test_expected_games_rejects_bad_inventories():
 p=proof('guard-0001',TEN);p['games'].pop(next(iter(p['games'])))
 with pytest.raises(AssertionError):M.expected_games(p,'guard-0001')
 p=proof('guard-0001',TEN);p['games']['guard-0001-d27-extra.json']='0'*64
 with pytest.raises(AssertionError):M.expected_games(p,'guard-0001')
 with pytest.raises(AssertionError):M.expected_games(proof('guard-0002',TEN),'guard-0001')
 with pytest.raises(AssertionError):M.expected_games(proof('guard-0001',TEN[:7]),'guard-0001')

def test_ack_in_other_phase_detected(tmp_path):
 j=tmp_path/'k4s-confirm-r1';(j/'hub-blocks/reporting/primary-0001').mkdir(parents=True)
 (j/'hub-blocks/reporting/primary-0001/hub-ack.json').write_text('{}')
 assert M.acked_elsewhere(j,'replacement-r1','primary-0001')==['reporting']
 assert M.acked_elsewhere(j,'reporting','primary-0001')==[]


# ---- Sol review r1/r2 regressions (findings 1-3, 6, 7) and hardening ---------------------------------------------
import signal,subprocess,threading,time

def fake_world(tmp,monkeypatch,fail=lambda cmd:False,transfers=lambda:[]):
 """Hub job under a fake approved root; 'remote' source files live under tmp/remote/<abs path>; transports faked at M.run."""
 root=tmp/'root';root.mkdir();monkeypatch.setattr(M,'ROOTS',{'127x03':root,'127x04':tmp/'other'})
 remote=tmp/'remote';calls=[]
 def loc(x):return remote/x.split(':',1)[1].lstrip('/') if x.startswith('127x0') else Path(x)
 def run(cmd,timeout,capture=False):
  calls.append(cmd)
  if fail(cmd):raise subprocess.CalledProcessError(23,cmd)
  src,dst=loc(cmd[-2]),loc(cmd[-1]);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes());return ''
 monkeypatch.setattr(M,'run',run);monkeypatch.setattr(M,'remote_transfers',lambda j,h:transfers())
 monkeypatch.setattr(M,'utc',lambda:'2026-10-11T00:00:00Z');monkeypatch.setattr(M.time,'sleep',lambda s:None)
 M.STOP_REQUEST.clear()
 return root/'k4s-confirm-t1',remote,calls

def rpath(remote,p):return remote/str(p).lstrip('/')

ORDER8=TEN[:3]+TEN[4:7]+TEN[8:]
def hub_block(j,host='127x03',phase='smoke',identity='smoke-0001',order=ORDER8):
 """A genuinely verified hub block (synthetic bytes)."""
 d=j/'hub-blocks'/phase/identity;(d/'games').mkdir(parents=True);games={}
 for arm in order:
  f=d/'games'/f'{identity}-d27-{arm}.json';f.write_bytes(arm.encode());games[f.name]=M.hashlib.sha256(arm.encode()).hexdigest()
 M.write(d/'complete.json',dict(host=host,descriptor=dict(id=identity,order=order),games=games))
 M.write(d/'hub-ack.json',dict(hub=M.HUB,source_host=host,job=str(j),phase=phase,block=identity,complete_sha256=M.sha(d/'complete.json'),games=len(order),sealed=True))
 return d

def admitted(j,me):M.write(j/'owned-copier-admission.json',dict(identity=me,active=True))

def test_failed_ack_return_is_retried_on_next_pass_and_after_restart(tmp_path,monkeypatch):
 state={'fail':True}
 j,remote,calls=fake_world(tmp_path,monkeypatch,fail=lambda cmd:state['fail'] and str(cmd[-1]).startswith('127x03:') and str(cmd[-1]).endswith('hub-ack.json'))
 admitted(j,M.self_identity());d=hub_block(j);monkeypatch.setattr(M,'listing',lambda j,h,p:['smoke-0001'])
 h=M.one_pass(j,'127x03','smoke',set())
 assert h['ack_returned']==0 and h['pending_return']==['smoke-0001'] and 'smoke-0001' in h['block_errors']
 state['fail']=False
 h=M.one_pass(j,'127x03','smoke',set())          # a fresh verified set = a restarted copier
 assert h['durable_on_hub']==1 and h['ack_returned']==1 and h['pending_return']==[] and h['block_errors']=={}
 assert rpath(remote,j/'smoke/smoke-0001/hub-ack.json').read_bytes()==(d/'hub-ack.json').read_bytes()
 n=len(calls);M.one_pass(j,'127x03','smoke',{'smoke-0001'});assert len(calls)==n

@pytest.mark.parametrize('damage',['no-proof','missing-game','changed-game','ack-binding','ack-proof-sha'])
def test_restart_never_returns_or_counts_an_unverified_hub_block(tmp_path,monkeypatch,damage):
 j,remote,calls=fake_world(tmp_path,monkeypatch);admitted(j,M.self_identity());d=hub_block(j)
 monkeypatch.setattr(M,'listing',lambda j,h,p:['smoke-0001'])
 g=sorted((d/'games').iterdir())[0]
 if damage=='no-proof':(d/'complete.json').unlink()
 elif damage=='missing-game':g.unlink()
 elif damage=='changed-game':g.write_bytes(b'tampered')
 elif damage=='ack-binding':a=M.read(d/'hub-ack.json');a['source_host']='127x04';M.write(d/'hub-ack.json',a)
 else:a=M.read(d/'hub-ack.json');a['complete_sha256']='0'*64;M.write(d/'hub-ack.json',a)
 # the source has no block bytes in this test, so the re-copy also fails: nothing may be acknowledged
 h=M.one_pass(j,'127x03','smoke',set())
 assert h['durable_on_hub']==0 and h['ack_returned']==0 and 'smoke-0001' in h['block_errors']
 assert not rpath(remote,j/'smoke/smoke-0001/hub-ack.json').exists()
 assert not (d/'hub-ack.json').exists() and list(d.glob('quarantine-*.json'))

def test_startup_verification_quarantines_bad_and_keeps_good(tmp_path,monkeypatch):
 j,_,_=fake_world(tmp_path,monkeypatch);good=hub_block(j,identity='smoke-0001');bad=hub_block(j,identity='smoke-0002')
 sorted((bad/'games').iterdir())[0].write_bytes(b'x')
 out=M.startup_verify(j,'127x03','smoke')
 assert list(out)==['smoke-0002'] and (good/'hub-ack.json').exists() and not (bad/'hub-ack.json').exists()

def test_quarantined_block_is_recopied_from_source_and_verified(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch);admitted(j,M.self_identity());monkeypatch.setattr(M.socket,'gethostname',lambda:'127x05')
 d=hub_block(j);src=rpath(remote,j/'smoke/smoke-0001');src.mkdir(parents=True)
 import shutil;shutil.copytree(d/'games',src/'games');shutil.copy(d/'complete.json',src/'complete.json')
 sorted((d/'games').iterdir())[0].write_bytes(b'tampered')
 def run(cmd,timeout,capture=False):     # emulate rsync of a directory or a file
  a,b=cmd[-2],cmd[-1];sa=rpath(remote,a.split(':',1)[1]) if a.startswith('127x0') else Path(a);db=rpath(remote,b.split(':',1)[1]) if b.startswith('127x0') else Path(b)
  if sa.is_dir():
   for f in sa.rglob('*'):
    if f.is_file() and f.name not in ('complete.json','hub-ack.json'):t=db/f.relative_to(sa);t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(f.read_bytes())
  else:db.parent.mkdir(parents=True,exist_ok=True);db.write_bytes(sa.read_bytes())
  return ''
 monkeypatch.setattr(M,'run',run);monkeypatch.setattr(M,'listing',lambda j,h,p:['smoke-0001'])
 h1=M.one_pass(j,'127x03','smoke',set());assert 'smoke-0001' in h1['block_errors']   # detected + quarantined
 h2=M.one_pass(j,'127x03','smoke',set());assert h2['ack_returned']==1 and h2['block_errors']=={}

def test_second_copier_cannot_take_the_job_lock(tmp_path,monkeypatch):
 j,_,_=fake_world(tmp_path,monkeypatch);fd=M.lock(j)
 with pytest.raises(SystemExit):M.lock(j)
 os.close(fd);os.close(M.lock(j))

def test_concurrent_lock_attempts_admit_exactly_one(tmp_path,monkeypatch):
 j,_,_=fake_world(tmp_path,monkeypatch);go=threading.Barrier(2);got=[]
 def attempt():
  go.wait()
  try:got.append(M.lock(j))
  except SystemExit:got.append(None)
 ts=[threading.Thread(target=attempt) for _ in range(2)];[t.start() for t in ts];[t.join() for t in ts]
 assert sum(x is not None for x in got)==1

def test_teardown_never_revokes_a_successor(tmp_path,monkeypatch):
 j,_,calls=fake_world(tmp_path,monkeypatch);me=M.self_identity()
 admitted(j,dict(me,pid=me['pid']+1,start_ticks=me['start_ticks']+1))
 with pytest.raises(AssertionError):M.revoke(j,'127x03',me)
 assert M.read(j/'owned-copier-admission.json')['active'] is True and calls==[]

def test_revocation_waits_for_source_transfers_to_finish(tmp_path,monkeypatch):
 left=[[4242],[4242],[]];seen=[]
 def transfers():
  v=left.pop(0) if left else [];seen.append(v);return v
 j,remote,calls=fake_world(tmp_path,monkeypatch,transfers=transfers);me=M.self_identity();admitted(j,me)
 M.revoke(j,'127x03',me)
 assert seen[:3]==[[4242],[4242],[]]
 assert M.read(rpath(remote,j/'owned-copier-admission.json'))['active'] is False

def test_late_active_publication_is_detected_and_overwritten(tmp_path,monkeypatch):
 j,remote,calls=fake_world(tmp_path,monkeypatch);me=M.self_identity();admitted(j,me)
 late={'n':1};base=M.run
 def run(cmd,timeout,capture=False):
  out=base(cmd,timeout,capture)
  # a lingering old receiver republishes the ACTIVE receipt once, right after the first verified inactive push
  if late['n'] and str(cmd[-1]).endswith('.source-check'):
   late['n']=0;M.write(rpath(remote,j/'owned-copier-admission.json'),dict(identity=me,active=True))
  return out
 monkeypatch.setattr(M,'run',run)
 M.revoke(j,'127x03',me)
 assert M.read(rpath(remote,j/'owned-copier-admission.json'))['active'] is False

def test_persistent_late_publisher_fails_revocation(tmp_path,monkeypatch):
 j,remote,calls=fake_world(tmp_path,monkeypatch);me=M.self_identity();admitted(j,me);base=M.run
 def run(cmd,timeout,capture=False):
  out=base(cmd,timeout,capture)
  if str(cmd[-1]).endswith('.source-check'):M.write(rpath(remote,j/'owned-copier-admission.json'),dict(identity=me,active=True))
  return out
 monkeypatch.setattr(M,'run',run)
 with pytest.raises(RuntimeError,match='revocation not confirmed'):M.revoke(j,'127x03',me)

def test_recovery_revoke_refuses_a_live_copier(tmp_path,monkeypatch):
 j,_,_=fake_world(tmp_path,monkeypatch);admitted(j,M.self_identity())
 with pytest.raises(AssertionError):M.revoke(j,'127x03')

def test_recovery_revoke_deactivates_dead_copier_on_both_sides(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch);admitted(j,dict(M.self_identity(),pid=2**22-3,start_ticks=1))
 M.revoke(j,'127x03')
 assert M.read(j/'owned-copier-admission.json')['active'] is False and M.read(rpath(remote,j/'owned-copier-admission.json'))['active'] is False

def run_main(monkeypatch,j,extra=()):
 monkeypatch.setattr(M.socket,'gethostname',lambda:'127x05');monkeypatch.setattr(M.os,'getpriority',lambda *a:19)
 monkeypatch.setattr(M.os,'sched_getaffinity',lambda pid:{63})
 monkeypatch.setattr(M,'self_identity',lambda:dict(pid=os.getpid(),pgid=os.getpid(),start_ticks=1,cmdline_sha256='c',uid=os.getuid(),exe='x'))
 old=signal.getsignal(signal.SIGTERM),signal.getsignal(signal.SIGINT)
 try:return M.main(['--job',str(j),'--host','127x03',*extra])
 finally:signal.signal(signal.SIGTERM,old[0]);signal.signal(signal.SIGINT,old[1])

def test_main_once_registers_and_revokes_verified(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch);monkeypatch.setattr(M,'listing',lambda j,h,p:[])
 assert run_main(monkeypatch,j,['--phase','smoke','--once'])==0
 for f in (j/'owned-copier-admission.json',rpath(remote,j/'owned-copier-admission.json')):assert M.read(f)['active'] is False

def test_failed_revocation_exits_nonzero_with_lifecycle_error(tmp_path,monkeypatch):
 state={'revoking':False}
 j,remote,_=fake_world(tmp_path,monkeypatch,fail=lambda cmd:state['revoking'])
 def listing(j,h,p):state['revoking']=True;return []
 monkeypatch.setattr(M,'listing',listing)
 assert run_main(monkeypatch,j,['--phase','smoke','--once'])==3
 assert 'revocation not confirmed' in M.read(j/'copy-health-127x03.json')['lifecycle_error']
 assert M.read(rpath(remote,j/'owned-copier-admission.json'))['active'] is True   # honest: not claimed revoked

def test_sigterm_is_a_stop_request_and_still_revokes(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch)
 def listing(j,h,p):os.kill(os.getpid(),signal.SIGTERM);return []
 monkeypatch.setattr(M,'listing',listing)
 assert run_main(monkeypatch,j,['--phase','smoke'])==0      # no --once: the stop request ends the loop
 assert M.STOP_REQUEST==['SIGTERM'] and M.read(rpath(remote,j/'owned-copier-admission.json'))['active'] is False

def test_recovery_mode_holds_lock_and_handles_signals(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch);admitted(j,dict(M.self_identity(),pid=2**22-3,start_ticks=1))
 fd=M.lock(j)
 with pytest.raises(SystemExit):run_main(monkeypatch,j,['--revoke'])
 os.close(fd);assert run_main(monkeypatch,j,['--revoke'])==0

# --- real process trees (no network): run() leaves no transport descendant behind ---
def _pid_gone(pid,limit=3):
 end=time.monotonic()+limit
 while time.monotonic()<end:
  try:
   st=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
   if st=='Z':time.sleep(.05);continue
  except OSError:return True
  time.sleep(.05)
 return False

def test_timeout_drains_the_whole_transport_tree(tmp_path):
 f=tmp_path/'grandchild.pid'
 with pytest.raises(subprocess.TimeoutExpired):M.run(['bash','-c',f'sleep 60 & echo $! > {f}; wait'],timeout=1)
 assert _pid_gone(int(f.read_text()))

def test_finished_leader_with_stray_helper_is_drained(tmp_path):
 f=tmp_path/'helper.pid'
 M.run(['bash','-c',f'(sleep 60 & echo $! > {f}) ; exit 0'],timeout=10)
 assert _pid_gone(int(f.read_text()))

def test_failed_transport_raises_after_drain(tmp_path):
 f=tmp_path/'helper.pid'
 with pytest.raises(subprocess.CalledProcessError):M.run(['bash','-c',f'(sleep 60 & echo $! > {f}); exit 23'],timeout=10)
 assert _pid_gone(int(f.read_text()))

def test_signal_during_real_transfer_lets_it_finish(tmp_path):
 M.STOP_REQUEST.clear();old=signal.signal(signal.SIGTERM,M._signal)
 try:
  threading.Timer(.3,lambda:os.kill(os.getpid(),signal.SIGTERM)).start()
  M.run(['bash','-c',f'sleep 1; echo done > {tmp_path}/out'],timeout=10)
 finally:signal.signal(signal.SIGTERM,old)
 assert (tmp_path/'out').read_text().strip()=='done' and M.STOP_REQUEST==['SIGTERM']

def test_job_path_confinement(tmp_path,monkeypatch):
 j,_,_=fake_world(tmp_path,monkeypatch)
 M.check_job(j,'127x03')
 for bad,host in ((j,'127x04'),(j.parent/'t1-20261010-r1','127x03'),(j.parent/'sub'/'k4s-confirm-x','127x03')):
  with pytest.raises(AssertionError):M.check_job(bad,host)
 alias=j.parent/'k4s-confirm-alias';(j.parent/'k4s-confirm-real').mkdir();alias.symlink_to(j.parent/'k4s-confirm-real')
 with pytest.raises(AssertionError):M.check_job(alias,'127x03')

def test_noncanonical_arm_rejected():
 with pytest.raises(AssertionError):M.expected_games(proof('smoke-0001',TEN[:9]+['../x']),'smoke-0001')

def test_symlinked_game_never_acked(tmp_path,monkeypatch):
 j,remote,_=fake_world(tmp_path,monkeypatch);monkeypatch.setattr(M.socket,'gethostname',lambda:'127x05')
 monkeypatch.setattr(M,'prefix',lambda j:['env','T1_COPIER_PID=1','T1_COPIER_PGID=1'])
 ident='smoke-0001';d=j/'hub-blocks/smoke'/ident/'games';d.mkdir(parents=True)
 target=tmp_path/'outside.json';target.write_bytes(b'x');games={}
 for arm in ORDER8:
  f=d/f'{ident}-d27-{arm}.json'
  if arm=='K4-200':f.symlink_to(target)
  else:f.write_bytes(b'y')
  games[f.name]=M.hashlib.sha256(b'x' if arm=='K4-200' else b'y').hexdigest()
 src=rpath(remote,j/'smoke'/ident/'complete.json');src.parent.mkdir(parents=True);M.write(src,dict(host='127x03',descriptor=dict(id=ident,order=ORDER8),games=games))
 def run(cmd,timeout,capture=False):
  if cmd[-1].endswith('complete.pending.json'):Path(cmd[-1]).write_bytes(src.read_bytes())
  return ''
 monkeypatch.setattr(M,'run',run)
 with pytest.raises(AssertionError):M.copy_block(j,'127x03','smoke',ident)
 assert not (j/'hub-blocks/smoke'/ident/'hub-ack.json').exists()
