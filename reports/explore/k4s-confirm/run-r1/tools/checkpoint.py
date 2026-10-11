"""K4S runner r1: one SEALED health checkpoint (run on 05). Health metrics only: never opens a game file, never
parses a winner/loss field. One light LAN ssh per host (coreutils on progress/exits/stop files/process table; no
scan of complete.json on the timing host). Interference flags are counted from the verified hub copies on 05.
Prints one JSON line; exit 2 on any anomaly (including unknown/unparseable data).
Usage: checkpoint.py PHASE [TAG]    (PHASE in smoke|reporting|replacement-rN)
Sol ops review r1 fixes: phase allowlist + quoting (1); STOP files, required fields, structured supervisor exit (2);
copier checked by current receipt identity, non-zombie, source receipt, health freshness (3)."""
import datetime,hashlib,json,re,shlex,subprocess,sys
from pathlib import Path
import os
NS=os.environ.get('K4S_NS','k4s-confirm-replacement-r1')
JOBS={'127x03':f'/mpac/sdicks02/jobs/clasher/{NS}','127x04':f'/mpac/sdicks02/jobs-k4s/{NS}'}
EXPECTED={'reporting':1950,'replacement-r1':1754}
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
L=Path('/mpac/sdicks02/k4s-runner/run-r1')
KF=L/'health'/'acknowledged-events.json'
KNOWN=json.loads(KF.read_text()) if KF.exists() else {}   # events already reported to the coordinator
phase=sys.argv[1] if len(sys.argv)>1 else 'reporting';tag=sys.argv[2] if len(sys.argv)>2 else 'checkpoint'
assert re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',phase),'phase'
assert re.fullmatch(r'[A-Za-z0-9_.-]{1,40}',tag),'tag'

REMOTE='''J={J};P={P}
echo "WHO $(who | wc -l)"
echo "STOPFILES $(test -e "$J/STOP" && echo 1 || echo 0) $(test -e "$J/STOP-$(hostname)" && echo 1 || echo 0)"
echo "PROGRESS $(tr -d '\\n' < "$J/progress.json" 2>/dev/null)"
echo "COMPLETE $(find "$J/$P" -mindepth 2 -maxdepth 2 -name complete.json 2>/dev/null | wc -l)"
echo "HUBACK $(find "$J/$P" -mindepth 2 -maxdepth 2 -name hub-ack.json 2>/dev/null | wc -l)"
echo "EXITS $(ls "$J/$P/exits" 2>/dev/null | wc -l) $(grep -l '"complete": false' "$J/$P"/exits/*.json 2>/dev/null | wc -l)"
echo "LOSTPOP $(grep -l '"complete": false' "$J/$P"/exits/primary-*.json 2>/dev/null | wc -l) $(grep -l '"complete": false' "$J/$P"/exits/guard-*.json 2>/dev/null | wc -l)"
test -e "$J/$P/stop-reason.json" && echo "STOPREASON $(tr -d '\\n' < "$J/$P/stop-reason.json" | grep -o '"utc": *"[^"]*"' | head -1) $(tr -d '\\n' < "$J/$P/stop-reason.json" | grep -o '"reason": *"[^"]*"' | head -1)"
test -e "$J/$P/supervisor-exit.json" && echo "SUPEXIT $(tr -d '\\n' < "$J/$P/supervisor-exit.json" | grep -o '"reason": *[^,]*' | head -1)"
echo "SRCRECEIPT $(tr -d '\\n' < "$J/owned-copier-admission.json" 2>/dev/null | grep -o '"pid": *[0-9]*' | head -1) $(tr -d '\\n' < "$J/owned-copier-admission.json" 2>/dev/null | grep -o '"active": *[a-z]*')"
S=$(grep -o '"supervisor_pid": *[0-9]*' "$J/$P/launch.json" 2>/dev/null | grep -o '[0-9]*$')
test -n "$S" && echo "SUPPROC $S $(ps -o stat= -p $S 2>/dev/null | tr -d ' ')"
'''

def parse(text):
 out={}
 for line in text.splitlines():
  k,_,v=line.partition(' ');out[k]=v.strip()
 return out

def ints(s,n):
 v=[int(x) for x in s.split()];assert len(v)==n;return v

def local_identity(pid):
 try:
  d=Path(f'/proc/{pid}');stat=(d/'stat').read_text().rsplit(')',1)[1].split()
  return dict(state=stat[0],pgid=int(stat[2]),start_ticks=int(stat[19]),cmdline_sha256=hashlib.sha256((d/'cmdline').read_bytes()).hexdigest(),uid=d.stat().st_uid)
 except OSError:return None

utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();now=datetime.datetime.strptime(utc,'%Y-%m-%dT%H:%M:%SZ')
def age(s):return (now-datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ')).total_seconds()
LOST=[0,0]
r=dict(schema='clasher.k4s.run-health.v2',study='PREREG-K4S',sealed=True,outcomes_read=False,utc=utc,phase=phase,tag=tag,hosts={});anom=[];parts=[]
for h,J in JOBS.items():
 x={};r['hosts'][h]=x
 try:
  p=subprocess.run(SSH+[h,REMOTE.format(J=shlex.quote(J),P=shlex.quote(phase))],capture_output=True,text=True,timeout=60)
  y=parse(p.stdout);x['remote']=y;x['ssh_rc']=p.returncode
  if p.returncode!=0:anom.append(f'{h}: health ssh rc {p.returncode}')
  who=int(y['WHO']);stopf=ints(y['STOPFILES'],2);comp=int(y['COMPLETE']);ack=int(y['HUBACK']);nexit,failed=ints(y['EXITS'],2)
  prog=json.loads(y['PROGRESS']);x['progress']={k:prog.get(k) for k in ('utc','phase','complete_local_blocks','failed_blocks','queued','inflight','reason','memavailable_GiB')}
  if who:anom.append(f'{h}: console users {who}')
  if any(stopf):anom.append(f'{h}: STOP file present {stopf}')
  lp,lg=ints(y['LOSTPOP'],2);x['lost']=dict(primary=lp,guard=lg);LOST[0]+=lp;LOST[1]+=lg
  known=KNOWN.get(h,{})
  if failed>known.get('failed',0):anom.append(f'{h}: failed blocks {failed} (acknowledged {known.get("failed",0)})')
  if y.get('STOPREASON') and y['STOPREASON']!=known.get('stopreason'):anom.append(f'{h}: STOP {y["STOPREASON"]}')
  if prog.get('reason'):anom.append(f'{h}: progress reason {prog["reason"]}')
  if (prog.get('console') or {}).get('positive'):anom.append(f'{h}: console positive')
  exp=EXPECTED.get(phase)
  done=y.get('SUPEXIT') is not None
  if done:
   if y['SUPEXIT'].split(':',1)[-1].strip()!='null' or (exp and comp<exp):anom.append(f'{h}: supervisor exited ({y["SUPEXIT"]}, complete {comp}/{exp})')
  else:
   sp=y.get('SUPPROC','').split()
   if len(sp)!=2 or sp[1].startswith('Z') or sp[1].startswith('T'):anom.append(f'{h}: supervisor process not running ({y.get("SUPPROC")})')
   if age(prog['utc'])>180:anom.append(f'{h}: progress stale {int(age(prog["utc"]))}s')
  # copier: current hub receipt identity, live non-zombie, source receipt, fresh health
  rec=json.loads(Path(J,'owned-copier-admission.json').read_text());ident=rec['identity'];live=local_identity(ident['pid'])
  ok_live=live is not None and live['state'] not in ('Z','T','X') and all(live[k]==ident[k] for k in ('pgid','start_ticks','cmdline_sha256','uid'))
  src=y.get('SRCRECEIPT','')
  ch=json.loads(Path(J,f'copy-health-{h}.json').read_text())
  hub=Path(J,'hub-blocks',phase);flags=dict(interfered=0,dbus=0,ssh=0,apt=0,idle=0)
  durable=returned=0
  for d in hub.iterdir() if hub.exists() else []:
   if not (d/'hub-ack.json').exists():continue
   durable+=1;returned+=(d/'hub-ack.returned.json').exists()
   i=json.loads((d/'complete.json').read_text()).get('interference',{})
   flags['interfered']+=bool(i.get('interfered'));flags['dbus']+=bool(i.get('system_dbus',{}).get('interfered'))
   flags['ssh']+=bool(i.get('ssh_flagged'));flags['apt']+=bool(i.get('apt_flagged'))
   flags['idle']+=any(s.get('interfered') for s in i.get('services',[]))
  x['hub']=dict(durable=durable,returned=returned,flags=flags,copier_pid=ident['pid'],copier_live=ok_live,receipt_active=rec.get('active'),
              copy_health={k:ch.get(k) for k in ('utc','listed','durable_on_hub','ack_returned','pending_return','error','block_errors','lifecycle_error','fatal_error')})
  if not done:
   if not ok_live:anom.append(f'{h}: copier {ident["pid"]} not live with its receipt identity')
   m_pid=re.search(r'"pid": *([0-9]+)',src);m_act=re.search(r'"active": *([a-z]+)',src)
   if rec.get('active') is not True or not m_pid or int(m_pid.group(1))!=ident['pid'] or not m_act or m_act.group(1)!='true':anom.append(f'{h}: source copier receipt mismatch ({src})')
   if age(ch['utc'])>300:anom.append(f'{h}: copier health stale {int(age(ch["utc"]))}s')
  if ch.get('lifecycle_error') or ch.get('fatal_error'):anom.append(f'{h}: copier lifecycle/fatal error')
  if ch.get('error'):anom.append(f'{h}: copier error {str(ch["error"])[:120]}')
  if ch.get('block_errors'):anom.append(f'{h}: copier block errors {list(ch["block_errors"])[:5]}')
  if comp-ack>15:anom.append(f'{h}: ACK lag {comp-ack}')
  parts.append(f"{h} complete {comp} acked {ack} hub {durable}/{returned} failed {failed} stopevent {y.get('STOPREASON') or '-'} inflight {prog.get('inflight')} queued {prog.get('queued')} reason {prog.get('reason')} who {who} flags[dbus {flags['dbus']} ssh {flags['ssh']} apt {flags['apt']} idle {flags['idle']}]")
 except Exception as e:   # unknown data is never treated as healthy
  anom.append(f'{h}: health check failed {type(e).__name__}: {e}');parts.append(f'{h} UNKNOWN')
# coordinator 21:39Z (11105b3f): escalate as cumulative lost blocks approach 10% of a replacement cap (30 primary / 9 guard)
if LOST[0]>=24 or LOST[1]>=7:anom.append(f'lost blocks approaching 10% of a replacement cap: primary {LOST[0]}/30, guard {LOST[1]}/9')
parts.append(f'lost primary {LOST[0]} guard {LOST[1]}')
r['lost_total']=dict(primary=LOST[0],guard=LOST[1])
r['anomalies']=anom;r['summary']='; '.join(parts)
out=L/'health'/f'{phase}-{utc.replace(":","").replace("-","")}.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(r,indent=1)+'\n')
print(json.dumps(dict(utc=utc,out=str(out),summary=r['summary'],anomalies=anom)))
sys.exit(2 if anom else 0)
