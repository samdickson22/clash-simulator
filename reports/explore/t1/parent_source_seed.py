"""OP-5: exact committed R4 parent-generation source evidence at admission."""
import hashlib,json,re,socket,subprocess
from pathlib import Path
from common import read,sha,utc,write
from ssh_transport import authenticated

FIELDS=('pid','start_ticks','uid','cmdline_sha256','ppid','pgid')
SOURCE='129.65.221.14'

def matching(row,receipt):
 p=receipt.get('parent',{})
 return (receipt.get('schema')=='clasher.t1.parent-source-seed.v1'
         and receipt.get('host')=='127x03' and receipt.get('source_ip')==SOURCE
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
  name=Path(binding['path'])
  assert not name.is_absolute() and '..' not in name.parts and str(name).startswith('reports/explore/t1/receipts/')
  assert re.fullmatch('[0-9a-f]{40}',binding['commit']) and re.fullmatch('[0-9a-f]{64}',binding['sha256'])
  assert manifest['files'].get(str(name))==binding['sha256'],'source seed not pinned by job manifest'
  path=(repo/name).resolve();assert repo in path.parents and sha(path)==binding['sha256']
  raw=subprocess.check_output(['git','-C',str(commit_repo),'show',binding['commit']+':'+str(name)])
  assert raw==path.read_bytes() and hashlib.sha256(raw).hexdigest()==binding['sha256'],'source seed differs from committed bytes'
  receipt=json.loads(raw)
  if socket.gethostname()!=receipt.get('host'):continue
  for row in rows:
   if not matching(row,receipt):continue
   from ssh_budget import identity
   key=(str(j),identity(row))
   # Never replace contradictory current-generation source evidence.
   if key in families.sources and families.sources[key]!=receipt['ssh_connection']:continue
   families.sources[key]=receipt['ssh_connection']
   accepted.append(dict(binding=binding,parent={k:row[k] for k in FIELDS},source_ip=SOURCE))
 write(j/'parent-source-seed-admission.json',dict(utc=utc(),host=socket.gethostname(),job=str(j),accepted=accepted))
 return accepted
