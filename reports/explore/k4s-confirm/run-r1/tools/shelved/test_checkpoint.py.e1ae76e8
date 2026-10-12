"""Offline regression tests for checkpoint.py (Sol checkpoint review r1: R1 k >= 8/6, R2 fail-closed ledger, R3 union).
No ssh, no host, no outcome file: the ssh runner, job directories, copier identity and clock are injected.
Checks use ok() (explicit raise), so the suite is meaningful under python -O as well."""
import copy,json,subprocess,sys
from pathlib import Path
import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import checkpoint as C   # noqa: E402

FIX=HERE/'fixtures'/'blind-ledger-r2.json'   # committed blind-ledger-r2.json, sha256 4a56abf3...

def ok(cond,msg='check failed'):
 if not cond:raise AssertionError(msg)

def ledger():return json.loads(FIX.read_text())

def write(tmp,doc,name='blind-ledger.json'):
 p=tmp/name;p.write_text(doc if isinstance(doc,str) else json.dumps(doc));return p

NONE={'primary':set(),'guard':set()}

def event(pop,lid,rid,cell,k):
 return dict(utc='2026-10-12T00:00:00Z',lost=dict(id=lid,population=pop,cell=cell,replacement_k=None),
             replacement=dict(id=rid,population=pop,cell=cell,replacement_k=k),reason='owned_STOP',evidence_sha256='0'*64)

def synth(pop,n,kmax=0,cell=0):
 """n events in one population; the last event in `cell` carries k = kmax."""
 base=0 if pop=='primary' else 0;rep=3000 if pop=='primary' else 900
 ev=[event(pop,f'{pop}-{i:04d}',f'{pop}-{rep+i:04d}',i%C.CELLS[pop],0) for i in range(n)]
 if n:ev[-1]['lost']['cell']=ev[-1]['replacement']['cell']=cell;ev[-1]['replacement']['replacement_k']=kmax
 return ev

# ---- valid ledger: totals and per-cell maxima reproduce the audited r2 values -------------------------------
def test_committed_r2_ledger_totals_and_k(tmp_path):
 rec,anom,part=C.ledger_gate(FIX,NONE)
 ok(anom==[],anom);ok(rec['status']=='OK')
 ok((rec['primary'],rec['guard'],rec['ledger_events'])==(41,14,55),rec)
 ok(rec['ledger_max_k']=={'primary':2,'guard':1},rec)
 # independent per-cell maxima agree with the population reduction
 per={}
 for e in ledger()['events']:
  r=e['replacement'];key=(r['population'],r['cell']);per[key]=max(per.get(key,-1),r['replacement_k'])
 ok(max(v for (p,c),v in per.items() if p=='primary')==2 and max(v for (p,c),v in per.items() if p=='guard')==1)

# ---- R1: k alert boundaries -----------------------------------------------------------------------------------
@pytest.mark.parametrize('pop,k,alert',[('primary',7,False),('primary',8,True),('guard',5,False),('guard',6,True)])
def test_k_alert_boundary(tmp_path,pop,k,alert):
 p=write(tmp_path,dict(events=synth(pop,3,kmax=k)))
 rec,anom,_=C.ledger_gate(p,NONE)
 ok(rec['status']=='OK');ok(any('replacement k at limit-2' in a for a in anom)==alert,(pop,k,anom))

# ---- cumulative thresholds unchanged (150/45) -------------------------------------------------------------------
@pytest.mark.parametrize('pop,n,alert',[('primary',149,False),('primary',150,True),('guard',44,False),('guard',45,True)])
def test_cumulative_thresholds(tmp_path,pop,n,alert):
 p=write(tmp_path,dict(events=synth(pop,n)))
 rec,anom,_=C.ledger_gate(p,NONE)
 ok(rec[pop]==n);ok(any('50% of a replacement cap' in a for a in anom)==alert,(pop,n,anom))

def test_current_phase_failures_add_to_ledger(tmp_path):
 p=write(tmp_path,dict(events=synth('guard',44)))
 rec,anom,_=C.ledger_gate(p,{'primary':set(),'guard':{'guard-0500'}})
 ok(rec['guard']==45 and any('50% of a replacement cap' in a for a in anom),rec)

# ---- R3: no double counting --------------------------------------------------------------------------------------
def test_overlap_counted_once(tmp_path):
 p=write(tmp_path,dict(events=[event('primary','primary-0001','primary-3001',1,0)]))
 rec,anom,part=C.ledger_gate(p,{'primary':{'primary-0001'},'guard':set()})
 ok(rec['primary']==1,rec);ok(rec['overlap']=={'primary':1,'guard':0},rec);ok(anom==[],anom)
 rec2,_,_=C.ledger_gate(p,{'primary':{'primary-0001','primary-0002'},'guard':set()})
 ok(rec2['primary']==2,rec2)

def test_recheck_of_inventoried_phase_does_not_inflate(tmp_path):
 """The r2 ledger already holds replacement-r1's 22 failed blocks; re-checking that phase must still give 41/14."""
 ev=ledger()['events'][33:]
 cur={'primary':{e['lost']['id'] for e in ev if e['lost']['population']=='primary'},'guard':{e['lost']['id'] for e in ev if e['lost']['population']=='guard'}}
 ok((len(cur['primary']),len(cur['guard']))==(16,6))
 rec,anom,_=C.ledger_gate(FIX,cur)
 ok((rec['primary'],rec['guard'])==(41,14),rec);ok(anom==[],anom)

# ---- R2: missing / unreadable / malformed ledgers fail closed ----------------------------------------------------
def mutate(fn):
 d=ledger();fn(d);return d

BAD={
 'invalid_json':'{"events": [',
 'not_object':[],
 'missing_events':{'utc':'x'},
 'events_dict':{'events':{}},
 'event_not_object':{'events':[1]},
 'unknown_lost_population':mutate(lambda d:d['events'][0]['lost'].update(population='smoke')),
 'unknown_replacement_population':mutate(lambda d:d['events'][0]['replacement'].update(population='smoke')),
 'null_replacement':mutate(lambda d:d['events'][0].update(replacement=None)),
 'missing_replacement':mutate(lambda d:d['events'][0].pop('replacement')),
 'null_k':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k=None)),
 'missing_k':mutate(lambda d:d['events'][0]['replacement'].pop('replacement_k')),
 'negative_k':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k=-1)),
 'bool_k':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k=True)),
 'float_k':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k=1.0)),
 'string_k':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k='1')),
 'k_beyond_bank':mutate(lambda d:d['events'][0]['replacement'].update(replacement_k=10)),   # guard bank max 9
 'cell_out_of_range':mutate(lambda d:(d['events'][0]['lost'].update(cell=18),d['events'][0]['replacement'].update(cell=18))),
 'cell_mismatch':mutate(lambda d:d['events'][0]['replacement'].update(cell=(d['events'][0]['lost']['cell']+1)%18)),
 'missing_cell':mutate(lambda d:d['events'][0]['lost'].pop('cell')),
 'duplicate_lost_id':mutate(lambda d:d['events'].append(copy.deepcopy(d['events'][0]))),
 'malformed_lost_id':mutate(lambda d:d['events'][0]['lost'].update(id='guard-61')),
 'id_population_mismatch':mutate(lambda d:d['events'][0]['lost'].update(id='primary-0061')),
}

@pytest.mark.parametrize('name',sorted(BAD))
def test_malformed_ledger_is_unknown(tmp_path,name):
 p=write(tmp_path,BAD[name] if isinstance(BAD[name],str) else json.dumps(BAD[name]))
 rec,anom,part=C.ledger_gate(p,NONE)
 ok(rec['status']=='UNKNOWN' and rec['primary'] is None and rec['ledger_max_k'] is None,(name,rec))
 ok(len(anom)==1 and anom[0].startswith('ledger UNKNOWN'),(name,anom));ok('UNKNOWN' in part)

def test_missing_and_unreadable_ledger_is_unknown(tmp_path):
 for p in (tmp_path/'absent.json',tmp_path):   # missing file; a directory is unreadable as a file
  rec,anom,_=C.ledger_gate(p,NONE)
  ok(rec['status']=='UNKNOWN' and anom and anom[0].startswith('ledger UNKNOWN'),(p,rec,anom))

def test_unknown_host_failures_make_cumulative_unknown():
 rec,anom,part=C.ledger_gate(FIX,None)
 ok(rec['status']=='UNKNOWN' and rec['primary'] is None and any('cumulative UNKNOWN' in a for a in anom),(rec,anom))

# ---- failed-ID read: cross-checked against LOSTPOP ---------------------------------------------------------------
def test_failed_ids_consistency():
 ok(C.failed_ids({'FAILEDIDS':'primary-0001 guard-0002','LOSTPOP':'1 1'})=={'primary':{'primary-0001'},'guard':{'guard-0002'}})
 ok(C.failed_ids({'FAILEDIDS':'','LOSTPOP':'0 0'})==NONE)
 for y in ({'FAILEDIDS':'primary-0001','LOSTPOP':'0 0'},{'FAILEDIDS':'primary-1','LOSTPOP':'1 0'},
           {'FAILEDIDS':'primary-0001 primary-0001','LOSTPOP':'2 0'},{'LOSTPOP':'0 0'},{'FAILEDIDS':'','LOSTPOP':'x'}):
  with pytest.raises(ValueError):C.failed_ids(y)

# ---- end to end: main() with injected ssh / jobs / identity (no host contact) ------------------------------------
UTC='2026-10-12T09:30:00Z'
IDENT=dict(pid=4242,pgid=4242,start_ticks=1,cmdline_sha256='c'*64,uid=1)

def host_dirs(tmp,phase):
 jobs={}
 for h in ('127x03','127x04'):
  J=tmp/'jobs'/h;(J/'hub-blocks'/phase).mkdir(parents=True)
  (J/'owned-copier-admission.json').write_text(json.dumps(dict(active=True,identity=IDENT)))
  (J/f'copy-health-{h}.json').write_text(json.dumps(dict(utc=UTC,listed=0)))
  jobs[h]=str(J)
 return jobs

def fake_run(failed='',lostpop='0 0',exits='11 0'):
 def run(cmd,**kw):
  out='\n'.join([
   'WHO 0','STOPFILES 0 0',
   'PROGRESS '+json.dumps(dict(utc=UTC,phase='replacement-r2',complete_local_blocks=0,failed_blocks=0,queued=1,inflight=11,reason=None)),
   'COMPLETE 0','HUBACK 0',f'EXITS {exits}',f'LOSTPOP {lostpop}',f'FAILEDIDS {failed}',
   'SRCRECEIPT "pid": 4242 "active": true','SUPPROC 99 SNs'])+'\n'
  return subprocess.CompletedProcess(cmd,0,out,'')
 return run

def runmain(tmp,ledger_doc,run,capsys,ack=None):
 root=tmp/'run';(root/'ledger').mkdir(parents=True);(root/'health').mkdir()
 if ack is not None:(root/'health'/'acknowledged-events.json').write_text(json.dumps(ack))
 if ledger_doc is not None:(root/'ledger'/'blind-ledger.json').write_text(ledger_doc if isinstance(ledger_doc,str) else json.dumps(ledger_doc))
 rc=C.main(['checkpoint.py','replacement-r2','test'],run=run,root=root,jobs=host_dirs(tmp,'replacement-r2'),identity=lambda pid:dict(state='S',**{k:IDENT[k] for k in ('pgid','start_ticks','cmdline_sha256','uid')}),utc=UTC)
 line=json.loads(capsys.readouterr().out.strip().splitlines()[-1])
 rec=json.loads(Path(line['out']).read_text())
 return rc,line,rec

def test_main_healthy_exit0(tmp_path,capsys):
 rc,line,rec=runmain(tmp_path,FIX.read_text(),fake_run(),capsys)
 ok(rc==0 and line['anomalies']==[],line);ok(rec['cumulative_lost']['primary']==41 and rec['cumulative_lost']['guard']==14,rec['cumulative_lost'])

@pytest.mark.parametrize('doc',[None,'not json',json.dumps({'events':{}})])
def test_main_bad_ledger_receipt_and_exit2(tmp_path,capsys,doc):
 rc,line,rec=runmain(tmp_path,doc,fake_run(),capsys)
 ok(rc==2,rc);ok(any(a.startswith('ledger UNKNOWN') for a in line['anomalies']),line)
 ok(rec['cumulative_lost']['status']=='UNKNOWN' and rec['anomalies']==line['anomalies'],rec)
 ok('cumulative UNKNOWN' in rec['summary'],rec['summary'])

def test_main_union_with_current_phase_failures(tmp_path,capsys):
 d=ledger();lid=d['events'][-1]['lost']['id']   # a failure already inventoried into the ledger
 pop=d['events'][-1]['lost']['population'];lp='1 0' if pop=='primary' else '0 1'
 ack={'127x03':{'failed':1},'127x04':{'failed':1}}
 rc,line,rec=runmain(tmp_path,json.dumps(d),fake_run(failed=lid,lostpop=lp,exits='12 1'),capsys,ack=ack)
 cum=rec['cumulative_lost'];ok((cum['primary'],cum['guard'])==(41,14),cum);ok(rc==0,line)

def test_main_inconsistent_failed_ids_is_unknown(tmp_path,capsys):
 rc,line,rec=runmain(tmp_path,FIX.read_text(),fake_run(failed='primary-0001',lostpop='0 0'),capsys)
 ok(rc==2 and rec['cumulative_lost']['status']=='UNKNOWN',(rc,rec['cumulative_lost']))

def test_invalid_phase_refused_without_assert(capsys):
 ok(C.main(['checkpoint.py','bad;phase'])==2)

# ---- Sol checkpoint review r2: the k alert survives unknown host data --------------------------------------------
def ledger_k(kp,kg):
 return dict(events=synth('primary',3,kmax=kp,cell=10)+synth('guard',3,kmax=kg,cell=3))

def has_k(anoms):return any(a.startswith('replacement k at limit-2') for a in anoms)
def has_cum_unknown(anoms):return any('cumulative UNKNOWN' in a for a in anoms)

@pytest.mark.parametrize('kp,kg,alert',[(8,6,True),(8,0,True),(0,6,True),(9,7,True),(7,5,False)])
def test_gate_k_alert_with_unknown_host_failures(tmp_path,kp,kg,alert):
 p=write(tmp_path,ledger_k(kp,kg))
 rec,anom,part=C.ledger_gate(p,None)
 ok(rec['status']=='UNKNOWN' and rec['ledger_max_k']=={'primary':kp,'guard':kg},rec)
 ok(has_cum_unknown(anom),anom);ok(has_k(anom)==alert,(kp,kg,anom))

def failing_run(cmd,**kw):
 raise subprocess.TimeoutExpired(cmd,60)

def rc255_run(cmd,**kw):
 return subprocess.CompletedProcess(cmd,255,'','ssh: connect to host: Connection refused')

@pytest.mark.parametrize('runner',['mismatch','timeout','ssh_rc_255'])
def test_main_k_alert_and_cumulative_unknown_both_reported(tmp_path,capsys,runner):
 run={'mismatch':fake_run(failed='primary-0001',lostpop='0 0'),'timeout':failing_run,'ssh_rc_255':rc255_run}[runner]
 rc,line,rec=runmain(tmp_path,json.dumps(ledger_k(8,6)),run,capsys)
 ok(rc==2,rc)
 for anoms in (line['anomalies'],rec['anomalies']):
  ok(has_k(anoms) and has_cum_unknown(anoms),(runner,anoms))
 ok(line['anomalies']==rec['anomalies'])
 ok(rec['cumulative_lost']['status']=='UNKNOWN' and rec['cumulative_lost']['ledger_max_k']=={'primary':8,'guard':6},rec['cumulative_lost'])
