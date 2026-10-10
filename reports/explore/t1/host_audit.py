"""Exclusive T1 host admission and one-second process census."""
import argparse,json,os,socket,subprocess,time,shlex,hashlib
from pathlib import Path
from common import utc,write,job,plan,sha
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
def source_parent(ppid,uid):
    """Bind collected connection evidence to a still-identical SSH ancestor."""
    for _ in range(4):
        d=Path('/proc')/str(ppid)
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split();owner=d.stat().st_uid
            raw=(d/'cmdline').read_bytes();cmd=raw.replace(b'\0',b' ').decode(errors='replace').strip()
            check=(d/'stat').read_text().rsplit(')',1)[1].split()
            if stat[19]!=check[19] or owner!=d.stat().st_uid or owner!=uid:return None
            if cmd==f'sshd: {os.environ.get("USER","sdicks02")}@notty':
                return [ppid,int(stat[19]),owner,hashlib.sha256(raw).hexdigest()]
            if not cmd or Path(cmd.split()[0]).name not in ('sh','bash'):return None
            ppid=int(stat[1])
        except (OSError,ProcessLookupError):return None
    return None
def ssh_family_source_parent(ppid,uid):
    # OP-4 provenance traverses arbitrary descendants, independently of OP-2.
    for _ in range(64):
        d=Path('/proc')/str(ppid)
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split();owner=d.stat().st_uid
            raw=(d/'cmdline').read_bytes();cmd=raw.replace(b'\0',b' ').decode(errors='replace').strip()
            check=(d/'stat').read_text().rsplit(')',1)[1].split()
            if stat[19]!=check[19] or owner!=d.stat().st_uid:return None
            if cmd==f'sshd: {os.environ.get("USER","sdicks02")}@notty' and owner==3822945:
                return [ppid,int(stat[19]),owner,hashlib.sha256(raw).hexdigest()]
            ppid=int(stat[1])
            if ppid<=1:return None
        except OSError:return None
    return None
def processes():
    from apt_budget import capture_cgroup,capture_uids,apt_uid,helper_exe
    helper_uid=apt_uid()
    rows=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            uid=d.stat().st_uid
            stat=(d/'stat').read_text().rsplit(')',1)[1].split()
            raw_cmd=(d/'cmdline').read_bytes()
            apt_cgroup=capture_cgroup(d)
            apt_uids=capture_uids(d)
            cmd=raw_cmd.replace(b'\0',b' ').decode(errors='replace').strip()
            # OP-2: retain connection evidence while this child still exists.
            # Only SSH_CONNECTION is retained, never the remaining environment.
            try:
                env=(d/'environ').read_bytes().split(b'\0')
                connection=next((v[len(b'SSH_CONNECTION='):].decode() for v in env if v.startswith(b'SSH_CONNECTION=')),None)
            except OSError:env=[];connection=None
            parent_identity=source_parent(int(stat[1]),uid) if connection and uid==3822945 else None
            family_parent=ssh_family_source_parent(int(stat[1]),uid) if connection else None
            copier={k:next((v[len(k)+1:].decode() for v in env if v.startswith((k+"=").encode())),None) for k in ("T1_COPIER_PID","T1_COPIER_PGID")}
            captured=time.monotonic()
            exe_errno=None
            try:exe=(d/'exe').resolve(strict=True).as_posix()
            except OSError as error:exe=None;exe_errno=error.errno
            exe_evidence='proc/exe' if exe else 'unavailable'
            if uid==103 and cmd.split()[:1]==['/usr/bin/dbus-daemon'] and exe is None:
                exe=Path(cmd.split()[0]).resolve().as_posix();exe_evidence='argv0 (proc/exe unreadable, unprivileged)'
            argv0=raw_cmd.split(b'\0',1)[0].decode(errors='replace')
            apt_helper_exe=helper_exe(exe,exe_errno,argv0) if helper_uid is not None and apt_uids==(helper_uid,helper_uid) else None
            try:
                check=(d/'stat').read_text().rsplit(')',1)[1].split()
                if check[19]!=stat[19] or check[1]!=stat[1] or d.stat().st_uid!=uid or capture_uids(d)!=apt_uids:continue
            except FileNotFoundError:pass # retain the captured identity of an exited child
            try:affinity=sorted(os.sched_getaffinity(int(d.name)))
            except (ProcessLookupError,PermissionError):affinity=[]
            rows.append(dict(ssh_family_parent_snapshot=family_parent,copier_identity_snapshot=copier,ssh_parent_snapshot=parent_identity,snapshot_monotonic=captured,ssh_connection_snapshot=connection,exe=exe,exe_evidence=exe_evidence,cmdline_sha256=hashlib.sha256(raw_cmd).hexdigest(),pid=int(d.name),ppid=int(stat[1]),pgid=int(stat[2]),start_ticks=int(stat[19]),cpu_ticks=int(stat[11])+int(stat[12]),child_cpu_ticks=int(stat[13])+int(stat[14]),tty=int(stat[4]),uid=uid,cmd=cmd,affinity=affinity))
            rows[-1]['apt_cgroup_snapshot']=apt_cgroup
            rows[-1]['apt_uid_snapshot']=apt_uids
            rows[-1]['apt_helper_uid_snapshot']=helper_uid
            rows[-1]['apt_helper_exe_snapshot']=apt_helper_exe
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
        if r.get('op2_denied'):forbidden.append(r);continue
        if r.get('allowlist_kind'):continue
        from apt_budget import apt_command
        if apt_command(r):forbidden.append(r);continue
        if first=='dbus-daemon' and (r['uid']==103 or '--system' in r['cmd'].split()):forbidden.append(r);continue
        from ssh_transport import sshd_title,authenticated
        if sshd_title(r) and '@' in r['cmd'] and any(c['ppid']==r['pid'] for c in rows):forbidden.append(r);continue
        if own_process(job,r) or perception_reader(r,rows) or member(r,rows,job):continue
        if first.startswith('python') or first in ('raylet','cargo','rustc','gcc','clang','node','java','ffmpeg'):
            forbidden.append(r)
    return forbidden

def own_process(j,r):
 from owned_supervisor import member as supervisor_member
 matches_job=str(j) in r['cmd']
 if matches_job and supervisor_member(j,r):return True
 try:cwd=(Path('/proc')/str(r['pid'])/'cwd').resolve(strict=True)
 except OSError:return False
 return matches_job or (cwd==j/'repo' and ('reports/explore/t1/' in r['cmd'] or 'pytest' in r['cmd']))

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

def perception_reader(r,rows,source=None):
 exception=plan()['compute'].get('perception_io_exception',{})
 if socket.gethostname()!=exception.get('host') or r['uid']!=3822945:return False
 try:argv=shlex.split(r['cmd'])
 except ValueError:return False
 if not argv or Path(argv[0]).name not in ('cat','sha256sum'):return False
 operands=argv[1:];operands=operands[1:] if operands[:1]==['--'] else operands
 if not operands or any(not x.startswith(exception['path_prefix']) or '..' in Path(x).parts for x in operands):return False
 conn=source if source is not None else r.get('ssh_connection_snapshot')
 if conn is None:return False
 parts=conn.split()
 if len(parts)!=4 or parts[0]!=exception['source_ip'] or parts[3]!='22':return False
 bypid={x['pid']:x for x in rows};parent=r
 for _ in range(4):
  parent=bypid.get(parent['ppid'])
  if parent is None:return False
  if parent['cmd']==f'sshd: {os.environ.get("USER","sdicks02")}@notty' and parent['uid']==r['uid']:
   if r.get('ssh_connection_snapshot') is not None and r.get('ssh_parent_snapshot')!=[parent[k] for k in ('pid','start_ticks','uid','cmdline_sha256')]:return False
   r['perception_io_allowlist']=dict(source_ip=parts[0],ssh_ancestor_pid=parent['pid'],reader_pid=r['pid'],start_ticks=r['start_ticks'],command=argv)
   return True
  if not parent['cmd'] or Path(parent['cmd'].split()[0]).name not in ('bash','sh'):return False
 return False

def census(j,before=None,block_ids=()):
 from idle_services import member as idle_member
 from system_bus import member as bus_member
 from ssh_transport import approved_parent,copier_activity
 from perception_confirmation import CONFIRMATION
 after=processes();allowed=[]
 for r in after:
  if bus_member(r,j):r['allowlist_kind']='system_dbus'
  elif perception_reader(r,after):r['allowlist_kind']='perception_reader'
  elif idle_member(r,after,j):r['allowlist_kind']='idle_cache'
  elif copier_activity(r,after,j):r['allowlist_kind']='owned_copier_child'
 from ssh_budget import FAMILIES,record as record_ssh
 FAMILIES.apply(after,j)
 identity_rows=[r for r in after if not r.get('ssh_budget')]
 def identity_collect():
  fresh=processes();FAMILIES.apply(fresh,j)
  return [r for r in fresh if not r.get('ssh_budget')]
 CONFIRMATION.apply(identity_rows,j,identity_collect,perception_reader,block_ids=block_ids)
 known={(r['pid'],r['start_ticks']) for r in after}
 after.extend(r for r in identity_rows if (r['pid'],r['start_ticks']) not in known)
 FAMILIES.apply(after,j)
 record_ssh(j,after,block_ids)
 from apt_budget import apply as apply_apt,record as record_apt
 apply_apt(after);record_apt(j,after,block_ids)
 for r in after:
  if not r.get('op2_denied') and approved_parent(r,after,lambda child:child.get('allowlist_kind') in ('perception_reader','idle_cache','owned_copier_child')):
   r['allowlist_kind']='approved_sshd_transport'
  if r.get('allowlist_kind'):
   allowed.append(dict(kind=r['allowlist_kind'],pid=r['pid'],pgid=r['pgid'],start_ticks=r['start_ticks'],cmdline_sha256=r['cmdline_sha256'],block_ids=list(block_ids),op2_confirmation=r.get('op2_confirmation')))
 if allowed:
  j.mkdir(parents=True,exist_ok=True)
  with (j/'allowlist-occurrences.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),scope='blocks' if block_ids else 'admission',occurrences=allowed))+'\n')
 forbidden=foreign_compute(j,after);active=[];console_cpu=0.
 if before is not None:
  old={r['pid']:r for r in before};hz=os.sysconf('SC_CLK_TCK')
  for r in after:
   if not r['cmd'] or r['pid'] not in old or old[r['pid']]['start_ticks']!=r['start_ticks']:continue
   used=(r['cpu_ticks']-old[r['pid']]['cpu_ticks'])/hz
   if r['uid']!=0 and not own_process(j,r) and not r.get('allowlist_kind') and used>.1 and Path(r['cmd'].split()[0]).name!='tailscaled':
    active.append(dict(r,cpu_seconds=used));console_cpu+=used
 return after,forbidden,active,console_cpu

def admission(j):
 host=socket.gethostname();cfg=plan();assert host in cfg['compute']['hosts'],host
 expected=cfg['compute']['hosts'][host]
 physical=physical_cpus();assert set(expected['physical_cpus'])|{expected['supervisor_cpu'],expected['copy_cpu'],expected['census_cpu']}<=set(physical)
 c=console();before=processes()
 from parent_source_seed import admit as seed_sources
 from ssh_budget import FAMILIES
 if not c['positive']:seed_sources(j,before,FAMILIES)
 from system_bus import pin as pin_system_bus
 pin_system_bus(j,before)
 time.sleep(1);after,foreign,active,load=census(j,before)
 r=dict(utc=utc(),host=host,console=c,physical_cpus=physical,foreign_compute=foreign,foreign_active=active,memavailable_GiB=memory()/2**30,processes=after,admitted=not c['positive'] and not foreign and not active and memory()>=24*2**30)
 assert not (j/'STOP').exists() and not (j/f'STOP-{host}').exists(),'owned stop present'
 return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=admission(a.job);write(a.out,r)
 print(json.dumps({k:r[k] for k in ('utc','host','admitted','console','memavailable_GiB')}))
 assert r['admitted'],'foreign compute/activity or memory floor; host not admitted'
if __name__=='__main__':main()
