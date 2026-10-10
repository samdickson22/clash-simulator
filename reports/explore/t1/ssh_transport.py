"""OP-1: authenticated SSH transport only for wholly attributable child trees."""
import os,shlex,socket
from pathlib import Path
from common import read

def sshd_title(row):return bool(row['cmd'].startswith('sshd: ') and row['cmd'].split()[0]=='sshd:')
def authenticated(row):
 return sshd_title(row) and row['uid']==os.getuid() and row['cmd']==f'sshd: {os.environ.get("USER","sdicks02")}@notty'
def environment(row):
 try:return dict(x.decode(errors='replace').split('=',1) for x in (Path('/proc')/str(row['pid'])/'environ').read_bytes().split(b'\0') if b'=' in x)
 except (OSError,ValueError):return {}
def copier_activity(row,rows,j,env_reader=environment):
 target=j/'owned-copier-admission.json'
 if not target.exists():return False
 receipt=read(target);root=receipt['identity']
 if receipt.get('active') is not True or receipt['job']!=str(j):return False
 env=env_reader(row)
 try:argv=shlex.split(row['cmd'])
 except ValueError:return False
 if not argv:return False
 # An intermediate remote shell must name exactly the approved env-prefixed work.
 if Path(argv[0]).name in ('sh','bash'):
  if len(argv)!=3 or argv[1]!='-c':return False
  try:argv=shlex.split(argv[2])
  except ValueError:return False
 if argv and argv[0]=='env':
  argv=argv[1:]
  while argv and argv[0].startswith('T1_COPIER_') and '=' in argv[0]:
   key,value=argv.pop(0).split('=',1);env[key]=value
 if not argv or Path(argv[0]).name not in ('rsync','find'):return False
 if not any(arg==str(j) or arg.startswith(str(j)+'/') for arg in argv):return False
 if any('..' in Path(arg).parts or (arg.startswith('/') and not arg.startswith(str(j)+'/')) for arg in argv[1:] if not arg.startswith('-')):return False
 if Path(argv[0]).name=='rsync' and '--server' not in argv:return False
 if Path(argv[0]).name=='find' and argv[2:]!=['-mindepth','2','-maxdepth','2','-name','complete.json','-print']:return False
 if env.get('T1_COPIER_PID')!=str(root['pid']) or env.get('T1_COPIER_PGID')!=str(root['pgid']):return False
 conn=env.get('SSH_CONNECTION','').split()
 if len(conn)!=4 or conn[0]!=receipt['source_ip'] or conn[3]!='22':return False
 if socket.gethostname()==receipt['host']:
  live=next((r for r in rows if r['pid']==root['pid']),None)
  if live is None or any(live.get(k)!=v for k,v in root.items()):return False
 return True

def approved_parent(row,rows,approved_leaf):
 if not authenticated(row):return False
 children={}
 for r in rows:children.setdefault(r['ppid'],[]).append(r)
 direct=children.get(row['pid'],[])
 if not direct:return False
 visited=set()
 def attributable(r,depth=0):
  if depth>16 or r['pid'] in visited:return False
  visited.add(r['pid']);desc=children.get(r['pid'],[])
  if desc:
   # Arbitrary programs cannot be treated as approved transport wrappers.
   if not approved_leaf(r) and (not r['cmd'] or Path(r['cmd'].split()[0]).name not in ('sh','bash','env')):return False
   return all(attributable(c,depth+1) for c in desc)
  return bool(approved_leaf(r))
 return all(attributable(c) for c in direct)
