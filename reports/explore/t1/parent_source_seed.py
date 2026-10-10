"""OP-5: exact committed parent-generation source evidence at admission."""
import hashlib,json,re,socket,subprocess
from pathlib import Path
from common import read,sha,utc,write
from ssh_transport import authenticated

FIELDS=('pid','start_ticks','uid','cmdline_sha256','ppid','pgid')
SOURCE='129.65.221.14'
CONTROL='/mpac/sdicks02/jobs/clasher/v4-a1-parallel-r2/sockets/sdicks02@127x08-22-a1-body-seal-r4'

def joined_08(receipt,server,client):
 """Exact receipt join; the daemonized mux has no asserted live ancestry."""
 try:
  conn=receipt['ssh_connection'].split();endpoint=client['socket_identity']
  p=dict(server['parent'],cmdline_sha256=server['cmdline_sha256'])
  if (server['schema']!='clasher.t1.parent-generation.v1' or server['host']!='127x08'
      or p!=receipt['parent'] or server['cmd']!='sshd: sdicks02@notty'
      or conn!=[SOURCE,'55838','129.65.221.18','22']
      or server['candidate_peer']!=SOURCE+':55838' or server['destination']!='129.65.221.18:22'
      or client['schema']!='clasher.v4.serial-r4.08-transport-identity.v1'
      or client['result']!='ESTABLISHED_SOCKET_OWNER_AND_SERIAL_SLOT_BINDING_CONFIRMED'
      or client['observation']['host']!='127x04' or client['client_uid']!=3822945
      or client['control_path']!=CONTROL or client['exact_cmdline_argv']!=['ssh: '+CONTROL+' [mux]']
      or endpoint['local']!={'ip':SOURCE,'port':55838}
      or endpoint['remote']!={'ip':'129.65.221.18','port':22}
      or endpoint['state_hex']!='01' or endpoint['uid']!=3822945):return False
  # Reverse endpoint and inode must be present in the committed 08 snapshot.
  tcp=next(t['text'] for t in server['parent_socket_receipt']['network_tables'] if t['path']=='/proc/net/tcp')
  if not any(r[1:4]==['12DD4181:0016','0EDD4181:DA1E','01'] and r[9]==str(server['socket_inode']) for r in (line.split() for line in tcp.splitlines()[1:])):return False
  identity=receipt['client_identity']
  owners=client['observation']['owners']
  if len(owners)!=1:return False
  owner=owners[0]
  for observed in (owner['identity'],owner['identity_recheck']):
   if ({k:observed[k] for k in ('pid','starttime','cmdline_sha256','ppid','pgid')}!= {k:identity[k] for k in ('pid','starttime','cmdline_sha256','ppid','pgid')}
       or observed['uid_fields']!=[identity['uid']]*4 or identity['uid']!=3822945
       or observed['cmdline_argv']!=client['exact_cmdline_argv']
       or hashlib.sha256(bytes.fromhex(observed['cmdline_hex'])).hexdigest()!=identity['cmdline_sha256']):return False
  if identity['pid']!=client['client_pid'] or identity['starttime']!=client['client_starttime']:return False
  return any(fd['pid']==identity['pid'] and fd['link']=='socket:['+str(endpoint['inode'])+']' for fd in client['socket_fd_owners'])
 except (KeyError,ValueError,TypeError,StopIteration,IndexError):return False

def committed_binding(repo,commit_repo,manifest,binding,prefix):
 name=Path(binding['path'])
 assert not name.is_absolute() and '..' not in name.parts and str(name).startswith(prefix)
 assert re.fullmatch('[0-9a-f]{40}',binding['commit']) and re.fullmatch('[0-9a-f]{64}',binding['sha256'])
 assert manifest['files'].get(str(name))==binding['sha256'],'source seed dependency not pinned by job manifest'
 path=(repo/name).resolve();assert repo in path.parents and sha(path)==binding['sha256']
 raw=subprocess.check_output(['git','-C',str(commit_repo),'show',binding['commit']+':'+str(name)])
 assert raw==path.read_bytes() and hashlib.sha256(raw).hexdigest()==binding['sha256'],'source seed dependency differs from committed bytes'
 return json.loads(raw)

def matching(row,receipt,server=None,client=None):
 p=receipt.get('parent',{})
 return (receipt.get('schema')=='clasher.t1.parent-source-seed.v1'
         and (receipt.get('host')=='127x03' or receipt.get('host')=='127x08' and joined_08(receipt,server,client)) and receipt.get('source_ip')==SOURCE
         and set(p)==set(FIELDS) and p.get('uid')==3822945
         and authenticated(row) and all(row.get(k)==p[k] for k in FIELDS)
         and receipt.get('ssh_connection','').split()[:1]==[SOURCE]
         and len(receipt['ssh_connection'].split())==4 and receipt['ssh_connection'].split()[3]=='22')

def admit(j,rows,families):
 manifest=read(j/'FROZEN-T1.json');bindings=manifest.get('parent_source_seeds',[])
 if not bindings:return []
 repo=(j/'repo').resolve();commit_repo=repo if (repo/'.git').exists() else Path('/mpac/sdicks02/repos/clasher')
 accepted=[]
 for binding in bindings:
  receipt=committed_binding(repo,commit_repo,manifest,binding,'reports/explore/t1/receipts/')
  if socket.gethostname()!=receipt.get('host'):continue
  server=client=None
  if receipt.get('host')=='127x08':
   join=receipt.get('source_join',{})
   server=committed_binding(repo,commit_repo,manifest,join['server'],'reports/explore/t1/receipts/')
   client=committed_binding(repo,commit_repo,manifest,join['client'],'reports/strategy_council_20260928/live-loop/v4/l1/receipts/')
  for row in rows:
   if not matching(row,receipt,server,client):continue
   from ssh_budget import identity
   key=(str(j),identity(row))
   # Never replace contradictory current-generation source evidence.
   if key in families.sources and families.sources[key]!=receipt['ssh_connection']:continue
   families.sources[key]=receipt['ssh_connection']
   accepted.append(dict(binding=binding,parent={k:row[k] for k in FIELDS},source_ip=SOURCE))
 write(j/'parent-source-seed-admission.json',dict(utc=utc(),host=socket.gethostname(),job=str(j),accepted=accepted))
 return accepted
