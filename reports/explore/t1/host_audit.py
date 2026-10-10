"""Exclusive T1 host admission and one-second process census."""
import argparse,json,os,socket,subprocess,time,shlex,hashlib
from pathlib import Path
from common import utc,write,job,plan,sha
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
def processes():
    rows=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split()
            raw_cmd=(d/'cmdline').read_bytes()
            cmd=raw_cmd.replace(b'\0',b' ').decode(errors='replace').strip()
            rows.append(dict(cmdline_sha256=hashlib.sha256(raw_cmd).hexdigest(),pid=int(d.name),ppid=int(stat[1]),pgid=int(stat[2]),start_ticks=int(stat[19]),cpu_ticks=int(stat[11])+int(stat[12]),tty=int(stat[4]),uid=d.stat().st_uid,cmd=cmd,affinity=sorted(os.sched_getaffinity(int(d.name)))))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return rows

def foreign_compute(job,rows):
    from idle_services import member
    forbidden=[]
    for r in rows:
        if not r['cmd']:continue
        # Recognize the host's idle boot services by exact root-owned command.
        if r['uid']==0 and r['cmd'] in (
            '/usr/bin/python3 /usr/bin/networkd-dispatcher --run-startup-triggers',
            '/opt/anaconda3/bin/python /opt/anaconda3/bin/jupyterhub -f /etc/jupyterhub/jupyterhub_config.py',
            '/usr/bin/python3 /usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal',
            'python /etc/jupyterhub/cull_idle_servers.py --timeout=3600',
            '/bin/node_exporter --collector.systemd',
            'node /opt/anaconda3/bin/configurable-http-proxy --ip  --port 8000 --api-ip 127.0.0.1 --api-port 8001 --error-target http://127.0.0.1:8081/hub/error --ssl-key /etc/ssl/private/key.key --ssl-cert /etc/ssl/private/cert.cer'):
            continue
        first=Path(r['cmd'].split()[0]).name.lower()
        if own_process(job,r) or perception_reader(r,rows) or member(r,rows,job):continue
        if first.startswith('python') or first in ('raylet','cargo','rustc','gcc','clang','node','java','ffmpeg'):
            forbidden.append(r)
    return forbidden

def own_process(j,r):
 try:cwd=(Path('/proc')/str(r['pid'])/'cwd').resolve()
 except OSError:return False
 return str(j) in r['cmd'] or (cwd==j/'repo' and ('reports/explore/t1/' in r['cmd'] or 'pytest' in r['cmd']))

def physical_cpus():
 rows=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET,ONLINE'],text=True)
 seen=set();cpus=[]
 for line in rows.splitlines():
  if line.startswith('#'):continue
  cpu,core,socket_,online=line.split(',')
  key=(core,socket_)
  if online=='Y' and key not in seen:seen.add(key);cpus.append(int(cpu))
 return cpus

def console():
 who=subprocess.check_output(['who'],text=True)
 helper=Path.home()/'.local/bin/fleet-console-users'
 assert helper.exists(),'required console helper absent'
 p=subprocess.run([str(helper)],capture_output=True,text=True)
 assert p.returncode in (0,1),(p.returncode,p.stderr)
 # The installed helper prints a numeric count; nonempty who is also positive.
 raw=p.stdout.strip();assert raw.isdigit(),raw
 return dict(who=who,console_count=int(raw),positive=bool(who.strip()) or int(raw)>0)

def perception_reader(r,rows):
 exception=plan()['compute'].get('perception_io_exception',{})
 if socket.gethostname()!=exception.get('host'):return False
 try:argv=shlex.split(r['cmd'])
 except ValueError:return False
 if not argv or Path(argv[0]).name not in ('cat','sha256sum'):return False
 operands=argv[1:];operands=operands[1:] if operands[:1]==['--'] else operands
 if not operands or any(not x.startswith(exception['path_prefix']) or '..' in Path(x).parts for x in operands):return False
 try:
  env=(Path('/proc')/str(r['pid'])/'environ').read_bytes().split(b'\0')
  conn=next(x[len(b'SSH_CONNECTION='):].decode() for x in env if x.startswith(b'SSH_CONNECTION='))
 except (OSError,StopIteration):return False
 parts=conn.split()
 if len(parts)!=4 or parts[0]!=exception['source_ip'] or parts[3]!='22':return False
 bypid={x['pid']:x for x in rows};parent=r
 for _ in range(4):
  parent=bypid.get(parent['ppid'])
  if parent is None:return False
  if parent['cmd']==f'sshd: {os.environ.get("USER","sdicks02")}@notty' and parent['uid']==r['uid']:
   r['perception_io_allowlist']=dict(source_ip=parts[0],ssh_ancestor_pid=parent['pid'],reader_pid=r['pid'],start_ticks=r['start_ticks'],command=argv)
   return True
  if Path(parent['cmd'].split()[0]).name not in ('bash','sh'):return False
 return False

def census(j,before=None):
 after=processes();allowed=[]
 for r in after:
  if perception_reader(r,after):allowed.append(r['perception_io_allowlist'])
 if allowed:
  j.mkdir(parents=True,exist_ok=True)
  with (j/'perception-io-occurrences.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),occurrences=allowed))+'\n')
 forbidden=foreign_compute(j,after);active=[];console_cpu=0.
 if before is not None:
  old={r['pid']:r for r in before};hz=os.sysconf('SC_CLK_TCK')
  for r in after:
   if not r['cmd'] or r['pid'] not in old or old[r['pid']]['start_ticks']!=r['start_ticks']:continue
   used=(r['cpu_ticks']-old[r['pid']]['cpu_ticks'])/hz
   if r['uid']!=0 and not own_process(j,r) and not r.get('perception_io_allowlist') and not __import__('idle_services').member(r,after,j) and used>.1 and Path(r['cmd'].split()[0]).name not in ('sshd','tailscaled'):
    active.append(dict(r,cpu_seconds=used));console_cpu+=used
 return after,forbidden,active,console_cpu

def admission(j):
 host=socket.gethostname();cfg=plan();assert host in cfg['compute']['hosts'],host
 expected=cfg['compute']['hosts'][host]
 physical=physical_cpus();assert set(expected['physical_cpus'])|{expected['supervisor_cpu'],expected['copy_cpu'],expected['census_cpu']}<=set(physical)
 c=console();before=processes();time.sleep(1);after,foreign,active,load=census(j,before)
 r=dict(utc=utc(),host=host,console=c,physical_cpus=physical,foreign_compute=foreign,foreign_active=active,memavailable_GiB=memory()/2**30,processes=after,admitted=not foreign and not active and memory()>=24*2**30)
 assert not (j/'STOP').exists() and not (j/f'STOP-{host}').exists(),'owned stop present'
 return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=admission(a.job);write(a.out,r)
 print(json.dumps({k:r[k] for k in ('utc','host','admitted','console','memavailable_GiB')}))
 assert r['admitted'],'foreign compute/activity or memory floor; host not admitted'
if __name__=='__main__':main()
