"""K4S runner r1: one SEALED health checkpoint (run on 05). Health metrics only: never opens a game file, never
parses a winner/loss field. One light LAN ssh per host (coreutils on progress/exits/stop files/process table; no
scan of complete.json on the timing host). Interference flags are counted from the verified hub copies on 05.
Prints one JSON line; exit 2 on any anomaly (including unknown/unparseable data).
Usage: checkpoint.py PHASE [TAG]    (PHASE in smoke|reporting|replacement-rN)
Sol ops review r1 fixes: phase allowlist + quoting (1); STOP files, required fields, structured supervisor exit (2);
copier checked by current receipt identity, non-zombie, source receipt, health freshness (3).
Sol checkpoint review r1 fixes (SOL-REVIEW-CHECKPOINT-r1): k alert at zero-based k >= 8/6 (R1); the ledger is read
unconditionally, validated and aggregated inside the anomaly boundary, failing closed to an UNKNOWN anomaly + receipt +
exit 2 (R2); cumulative losses count the per-population union of ledger lost IDs and current-phase failed IDs (R3).
Sol checkpoint review r2 fix: the k alert is evaluated as soon as the ledger validates, so it survives unknown host data.
Round r3 audit F1 fix: the per-host expected completions come from the phase's own dispatch, resolved through
rounds/history.json and bound by sha256 to both the history entry and the host's launch.json; on a supervisor exit the
exit receipt's completed/failed/unstarted counts must account for every dispatched block. Sol checkpoint review r4:
both remote readers parse JSON strictly (launch dispatch_sha256 must be a full 64-hex string, compared whole; the three
exit collections must be lists) and print INVALID otherwise, which main() treats as an anomaly. Sol r5: each reader's
output and exit status are captured before its line is emitted, and parse() rejects unknown, empty or duplicate keys. Any missing, unreadable or
mismatched input is an anomaly (exit 2), never a silent pass.
Every check is explicit (no assert), so it also holds under python -O."""
import datetime,hashlib,json,re,shlex,subprocess,sys
from pathlib import Path
import os
NS=os.environ.get('K4S_NS','k4s-confirm-replacement-r2')
JOBS={'127x03':f'/mpac/sdicks02/jobs/clasher/{NS}','127x04':f'/mpac/sdicks02/jobs-k4s/{NS}'}
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
L=Path('/mpac/sdicks02/k4s-runner/run-r1')
# Frozen bank geometry (plan.json replacement / schedule.CELLS): cells per population and the bank's max zero-based k.
CELLS={'primary':50,'guard':18}
BANK_MAX_K={'primary':11,'guard':9}
# coordinator Option A (afe83faa): escalate at 50% of a replacement cap (150 primary / 45 guard). Stricter k ruling
# (38ed75a2 / 9acbe743): escalate at 9 / 7 replacements in any cell, i.e. zero-based replacement_k >= 8 / 6.
# Bank limits stay 11 / 9 and the cumulative thresholds stay 150 / 45.
CUM_ALERT={'primary':150,'guard':45}
BLOCK_ID=re.compile(r'(primary|guard)-[0-9]{4}')

REMOTE='''J={J};P={P}
echo "WHO $(who | wc -l)"
echo "STOPFILES $(test -e "$J/STOP" && echo 1 || echo 0) $(test -e "$J/STOP-$(hostname)" && echo 1 || echo 0)"
echo "PROGRESS $(tr -d '\\n' < "$J/progress.json" 2>/dev/null)"
echo "COMPLETE $(find "$J/$P" -mindepth 2 -maxdepth 2 -name complete.json 2>/dev/null | wc -l)"
echo "HUBACK $(find "$J/$P" -mindepth 2 -maxdepth 2 -name hub-ack.json 2>/dev/null | wc -l)"
echo "EXITS $(ls "$J/$P/exits" 2>/dev/null | wc -l) $(grep -l '"complete": false' "$J/$P"/exits/*.json 2>/dev/null | wc -l)"
echo "LOSTPOP $(grep -l '"complete": false' "$J/$P"/exits/primary-*.json 2>/dev/null | wc -l) $(grep -l '"complete": false' "$J/$P"/exits/guard-*.json 2>/dev/null | wc -l)"
echo "FAILEDIDS $(grep -l '"complete": false' "$J/$P"/exits/*.json 2>/dev/null | sed 's#.*/##; s#[.]json$##' | tr '\\n' ' ')"
test -e "$J/$P/stop-reason.json" && echo "STOPREASON $(tr -d '\\n' < "$J/$P/stop-reason.json" | grep -o '"utc": *"[^"]*"' | head -1) $(tr -d '\\n' < "$J/$P/stop-reason.json" | grep -o '"reason": *"[^"]*"' | head -1)"
test -e "$J/$P/supervisor-exit.json" && echo "SUPEXIT $(tr -d '\\n' < "$J/$P/supervisor-exit.json" | grep -o '"reason": *[^,]*' | head -1)"
test -e "$J/$P/supervisor-exit.json" && {{ if out=$(python3 -c '
import json,sys
try:
 e=json.load(open(sys.argv[1]))
 k=("completed","failed","unstarted")
 print(" ".join(str(len(e[x])) for x in k) if isinstance(e,dict) and all(isinstance(e.get(x),list) for x in k) else "INVALID")
except Exception:
 print("INVALID")' "$J/$P/supervisor-exit.json" 2>/dev/null); then echo "SUPEXITN $out"; else echo "SUPEXITN INVALID"; fi; }}
if out=$(python3 -c '
import json,re,sys
try:
 d=json.load(open(sys.argv[1]))
 v=d.get("dispatch_sha256") if isinstance(d,dict) else None
 print(v if isinstance(v,str) and re.fullmatch("[0-9a-f]{{64}}",v) else "INVALID")
except Exception:
 print("INVALID")' "$J/$P/launch.json" 2>/dev/null); then echo "LAUNCHDISPATCH $out"; else echo "LAUNCHDISPATCH INVALID"; fi
echo "SRCRECEIPT $(tr -d '\\n' < "$J/owned-copier-admission.json" 2>/dev/null | grep -o '"pid": *[0-9]*' | head -1) $(tr -d '\\n' < "$J/owned-copier-admission.json" 2>/dev/null | grep -o '"active": *[a-z]*')"
S=$(grep -o '"supervisor_pid": *[0-9]*' "$J/$P/launch.json" 2>/dev/null | grep -o '[0-9]*$')
test -n "$S" && echo "SUPPROC $S $(ps -o stat= -p $S 2>/dev/null | tr -d ' ')"
'''

class HealthDataError(ValueError):
 """Unknown or malformed health input; never treated as healthy."""

def need(cond,msg):
 if not cond:raise HealthDataError(msg)

KEYS=frozenset({'WHO','STOPFILES','PROGRESS','COMPLETE','HUBACK','EXITS','LOSTPOP','FAILEDIDS','STOPREASON','SUPEXIT','SUPEXITN',
                 'LAUNCHDISPATCH','SRCRECEIPT','SUPPROC'})

def parse(text):
 """Remote output -> {KEY: value}. Every line must start with a known key, and each key may appear once (Sol r5:
 a reader that prints a payload and then fails must not leave a stray line or a second value behind)."""
 out={}
 for line in text.splitlines():
  k,_,v=line.partition(' ')
  need(k in KEYS,f'remote line with unknown or empty key {line[:40]!r}')
  need(k not in out,f'duplicate remote key {k}')
  out[k]=v.strip()
 return out

def ints(s,n):
 v=[int(x) for x in s.split()];need(len(v)==n,f'expected {n} integers, got {s!r}');return v

SHA64=re.compile(r'[0-9a-f]{64}')

def exit_counts(v):
 """SUPEXITN payload -> (completed, failed, unstarted). The remote reader prints three list lengths or INVALID;
 anything other than exactly three nonnegative decimal integers is rejected."""
 parts=(v or '').split()
 need(len(parts)==3 and all(re.fullmatch(r'[0-9]+',x) for x in parts),f'supervisor-exit counts invalid ({v!r})')
 return tuple(int(x) for x in parts)

def strict_int(v):
 return isinstance(v,int) and not isinstance(v,bool)

def failed_ids(y):
 """Current-phase failed block IDs from the exit files' operational complete flag (no outcome field). Cross-checked
 against the per-population LOSTPOP counts read in the same ssh session."""
 need('FAILEDIDS' in y and 'LOSTPOP' in y,'FAILEDIDS/LOSTPOP missing')
 ids=y['FAILEDIDS'].split()
 need(all(BLOCK_ID.fullmatch(i) for i in ids),f'malformed failed block id in {ids[:5]}')
 need(len(set(ids))==len(ids),'duplicate failed block id')
 lp,lg=ints(y['LOSTPOP'],2)
 by={'primary':{i for i in ids if i.startswith('primary-')},'guard':{i for i in ids if i.startswith('guard-')}}
 need(len(by['primary'])==lp and len(by['guard'])==lg,f'FAILEDIDS {len(by["primary"])}/{len(by["guard"])} != LOSTPOP {lp}/{lg}')
 return by

def validate_ledger(doc):
 """Explicitly validate the blind ledger. Returns {population: set(lost ids)} and {population: max zero-based k}."""
 need(isinstance(doc,dict),'ledger is not an object')
 need(isinstance(doc.get('events'),list),'ledger events is not a list')
 lost={'primary':set(),'guard':set()};repl=set();kmax={'primary':None,'guard':None}
 for n,e in enumerate(doc['events']):
  need(isinstance(e,dict),f'event {n} is not an object')
  lo,re_=e.get('lost'),e.get('replacement')
  need(isinstance(lo,dict),f'event {n} lost is not an object')
  need(isinstance(re_,dict),f'event {n} replacement is not an object')
  pop=lo.get('population')
  need(pop in CELLS,f'event {n} lost population {pop!r}')
  need(re_.get('population')==pop,f'event {n} replacement population {re_.get("population")!r} != {pop}')
  lid=lo.get('id');rid=re_.get('id')
  need(isinstance(lid,str) and BLOCK_ID.fullmatch(lid) is not None and lid.startswith(pop+'-'),f'event {n} lost id {lid!r}')
  need(isinstance(rid,str) and BLOCK_ID.fullmatch(rid) is not None and rid.startswith(pop+'-'),f'event {n} replacement id {rid!r}')
  need(lid not in lost[pop],f'event {n} duplicate lost id {lid}')
  need(rid not in repl,f'event {n} duplicate replacement id {rid}')
  for name,c in (('lost',lo.get('cell')),('replacement',re_.get('cell'))):
   need(strict_int(c) and 0<=c<CELLS[pop],f'event {n} {name} cell {c!r}')
  need(lo['cell']==re_['cell'],f'event {n} replacement cell != lost cell')
  k=re_.get('replacement_k')
  need(strict_int(k) and 0<=k<=BANK_MAX_K[pop],f'event {n} replacement_k {k!r}')
  lost[pop].add(lid);repl.add(rid)
  kmax[pop]=k if kmax[pop] is None else max(kmax[pop],k)
 return lost,{p:(0 if v is None else v) for p,v in kmax.items()}

def ledger_gate(ledger_path,current_failed):
 """current_failed: {population: set(ids)} for the checked phase (None if any host's failed set is unknown).
 Returns (record, anomalies, summary_part). Fails closed: any ledger problem is an UNKNOWN anomaly."""
 anom=[]
 try:
  doc=json.loads(Path(ledger_path).read_text())
  lost,kmax=validate_ledger(doc)
 except (OSError,ValueError,TypeError,KeyError) as e:   # missing, unreadable, invalid JSON or schema-invalid ledger
  anom.append(f'ledger UNKNOWN: {type(e).__name__}: {e}')
  rec=dict(status='UNKNOWN',primary=None,guard=None,ledger_events=None,ledger_max_k=None,overlap=None)
  return rec,anom,'cumulative UNKNOWN (ledger); ledger max k UNKNOWN'
 # The k alert depends only on the validated ledger: evaluate it before any host-dependent early return (Sol r2).
 if kmax['primary']>=8 or kmax['guard']>=6:anom.append(f'replacement k at limit-2: {kmax}')
 if current_failed is None:
  anom.append('cumulative UNKNOWN: current-phase failed IDs unavailable for a host')
  rec=dict(status='UNKNOWN',primary=None,guard=None,ledger_events=len(doc['events']),ledger_max_k=kmax,overlap=None)
  return rec,anom,f'cumulative UNKNOWN (host); ledger max k {kmax}'
 overlap={p:sorted(lost[p]&current_failed[p]) for p in CELLS}
 cum={p:len(lost[p]|current_failed[p]) for p in CELLS}
 cp,cg=cum['primary'],cum['guard']
 if cp>=CUM_ALERT['primary'] or cg>=CUM_ALERT['guard']:anom.append(f'cumulative lost at 50% of a replacement cap: primary {cp}/300, guard {cg}/90')
 rec=dict(status='OK',primary=cp,guard=cg,ledger_events=len(doc['events']),ledger_max_k=kmax,
          overlap={p:len(v) for p,v in overlap.items()},overlap_ids=overlap)
 part=f'cumulative primary {cp}/300 guard {cg}/90 (union; already in ledger {len(overlap["primary"])}/{len(overlap["guard"])}); ledger max k {kmax}'
 return rec,anom,part

def expected_counts(root,phase):
 """Per-host dispatched block counts for PHASE from its own dispatch file. Returns (counts, dispatch_sha256).
 Raises HealthDataError unless rounds/history.json names exactly one entry for the phase and the dispatch file's
 sha256 equals that entry."""
 hist=json.loads((Path(root)/'rounds'/'history.json').read_text())
 need(isinstance(hist,list),'history is not a list')
 entries=[e for e in hist if isinstance(e,dict) and e.get('phase')==phase]
 need(len(entries)==1,f'history has {len(entries)} entries for phase {phase}')
 e=entries[0];name=e.get('dispatch_file');want=e.get('dispatch_sha256')
 need(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.-]+[.]json',name) is not None,f'history dispatch_file {name!r}')
 need(isinstance(want,str) and re.fullmatch(r'[0-9a-f]{64}',want) is not None,f'history dispatch_sha256 {want!r}')
 raw=(Path(root)/'dispatch'/name).read_bytes()
 need(hashlib.sha256(raw).hexdigest()==want,f'dispatch {name} sha256 != history')
 doc=json.loads(raw)
 need(isinstance(doc,dict) and isinstance(doc.get('blocks'),list),'dispatch blocks is not a list')
 counts={}
 for b in doc['blocks']:
  need(isinstance(b,dict) and isinstance(b.get('host'),str),'dispatch row without host')
  counts[b['host']]=counts.get(b['host'],0)+1
 return counts,want

def local_identity(pid):
 try:
  d=Path(f'/proc/{pid}');stat=(d/'stat').read_text().rsplit(')',1)[1].split()
  return dict(state=stat[0],pgid=int(stat[2]),start_ticks=int(stat[19]),cmdline_sha256=hashlib.sha256((d/'cmdline').read_bytes()).hexdigest(),uid=d.stat().st_uid)
 except OSError:return None

def main(argv,run=subprocess.run,root=L,jobs=None,identity=local_identity,utc=None):
 jobs=JOBS if jobs is None else jobs
 phase=argv[1] if len(argv)>1 else 'reporting';tag=argv[2] if len(argv)>2 else 'checkpoint'
 if not re.fullmatch(r'(smoke|reporting|replacement-r[0-9]+)',phase):print('invalid phase',file=sys.stderr);return 2
 if not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}',tag):print('invalid tag',file=sys.stderr);return 2
 kf=root/'health'/'acknowledged-events.json'
 known_all=json.loads(kf.read_text()) if kf.exists() else {}   # events already reported to the coordinator
 utc=utc or subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();now=datetime.datetime.strptime(utc,'%Y-%m-%dT%H:%M:%SZ')
 def age(s):return (now-datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ')).total_seconds()
 r=dict(schema='clasher.k4s.run-health.v2',study='PREREG-K4S',sealed=True,outcomes_read=False,utc=utc,phase=phase,tag=tag,hosts={});anom=[];parts=[]
 LOST=[0,0];FAILED={'primary':set(),'guard':set()};failed_known=True
 try:
  EXP,EXP_SHA=expected_counts(root,phase)
 except Exception as e:   # no dispatch, no expected count: fail closed
  EXP,EXP_SHA=None,None;anom.append(f'expected counts UNKNOWN for {phase}: {type(e).__name__}: {e}')
 for h,J in jobs.items():
  x={};r['hosts'][h]=x
  try:
   p=run(SSH+[h,REMOTE.format(J=shlex.quote(J),P=shlex.quote(phase))],capture_output=True,text=True,timeout=60)
   y=parse(p.stdout);x['remote']=y;x['ssh_rc']=p.returncode
   if p.returncode!=0:anom.append(f'{h}: health ssh rc {p.returncode}')
   who=int(y['WHO']);stopf=ints(y['STOPFILES'],2);comp=int(y['COMPLETE']);ack=int(y['HUBACK']);nexit,failed=ints(y['EXITS'],2)
   prog=json.loads(y['PROGRESS']);x['progress']={k:prog.get(k) for k in ('utc','phase','complete_local_blocks','failed_blocks','queued','inflight','reason','memavailable_GiB')}
   if who:anom.append(f'{h}: console users {who}')
   if any(stopf):anom.append(f'{h}: STOP file present {stopf}')
   fid=failed_ids(y)   # raises on unknown/inconsistent data -> host UNKNOWN and cumulative UNKNOWN
   lp,lg=len(fid['primary']),len(fid['guard']);x['lost']=dict(primary=lp,guard=lg);LOST[0]+=lp;LOST[1]+=lg
   FAILED['primary']|=fid['primary'];FAILED['guard']|=fid['guard']
   known=known_all.get(h,{})
   if failed>known.get('failed',0):anom.append(f'{h}: failed blocks {failed} (acknowledged {known.get("failed",0)})')
   if y.get('STOPREASON') and y['STOPREASON']!=known.get('stopreason'):anom.append(f'{h}: STOP {y["STOPREASON"]}')
   if prog.get('reason'):anom.append(f'{h}: progress reason {prog["reason"]}')
   if (prog.get('console') or {}).get('positive'):anom.append(f'{h}: console positive')
   exp=None
   if EXP is not None:
    if EXP.get(h,0)<=0:anom.append(f'{h}: expected count UNKNOWN (no {phase} dispatch rows for this host)')
    else:exp=EXP[h]
    ld=y.get('LAUNCHDISPATCH','')
    if SHA64.fullmatch(ld) is None:anom.append(f'{h}: launch dispatch_sha256 invalid ({ld[:20]!r})')
    elif ld!=EXP_SHA:anom.append(f'{h}: launch dispatch_sha256 {ld[:16]} != history {EXP_SHA[:16]}')
   x['expected']=exp
   done=y.get('SUPEXIT') is not None
   if done:
    reason=y['SUPEXIT'].split(':',1)[-1].strip()
    if reason!='null':anom.append(f'{h}: supervisor exited ({y["SUPEXIT"]}, complete {comp}/{exp})')
    if exp is None:anom.append(f'{h}: supervisor exited with no expected count (complete {comp})')
    else:
     if comp<exp:anom.append(f'{h}: supervisor exited ({y["SUPEXIT"]}) with complete {comp} < expected {exp}')
     try:
      nc,nf,nu=exit_counts(y.get('SUPEXITN'))
     except ValueError:
      anom.append(f'{h}: supervisor-exit counts unreadable ({y.get("SUPEXITN")!r})')
     else:
      x['exit_counts']=dict(completed=nc,failed=nf,unstarted=nu)
      if nc+nf+nu!=exp:anom.append(f'{h}: supervisor-exit counts {nc}+{nf}+{nu} != dispatched {exp}')
      if nc!=comp:anom.append(f'{h}: supervisor-exit completed {nc} != complete.json count {comp}')
      if reason=='null' and nu:anom.append(f'{h}: null-reason exit left {nu} unstarted')
   else:
    sp=y.get('SUPPROC','').split()
    if len(sp)!=2 or sp[1].startswith('Z') or sp[1].startswith('T'):anom.append(f'{h}: supervisor process not running ({y.get("SUPPROC")})')
    if age(prog['utc'])>180:anom.append(f'{h}: progress stale {int(age(prog["utc"]))}s')
   # copier: current hub receipt identity, live non-zombie, source receipt, fresh health
   rec=json.loads(Path(J,'owned-copier-admission.json').read_text());ident=rec['identity'];live=identity(ident['pid'])
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
   if 'lost' not in x:failed_known=False
   anom.append(f'{h}: health check failed {type(e).__name__}: {e}');parts.append(f'{h} UNKNOWN')
 # Ledger gate: read unconditionally; validation and aggregation fail closed inside ledger_gate.
 try:
  cum,ganom,gpart=ledger_gate(root/'ledger'/'blind-ledger.json',FAILED if failed_known else None)
 except Exception as e:   # defensive: the gate itself must never crash the receipt
  cum,ganom,gpart=dict(status='UNKNOWN'),[f'ledger UNKNOWN: gate error {type(e).__name__}: {e}'],'cumulative UNKNOWN (gate error)'
 anom+=ganom
 parts.append(f'lost this phase primary {LOST[0]} guard {LOST[1]}; {gpart}')
 r['cumulative_lost']=cum
 r['lost_total']=dict(primary=LOST[0],guard=LOST[1])
 r['anomalies']=anom;r['summary']='; '.join(parts)
 out=root/'health'/f'{phase}-{utc.replace(":","").replace("-","")}.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(r,indent=1)+'\n')
 print(json.dumps(dict(utc=utc,out=str(out),summary=r['summary'],anomalies=anom)))
 return 2 if anom else 0

if __name__=='__main__':
 sys.exit(main(sys.argv))
