"""OP-6 exact caps, source isolation and outcome-blind sensitivity ledger."""
import copy,json
import pytest
import numpy as np
import ssh_budget as B
import ssh_sensitivity as S
from common import write,read,sha
from test_op4 import parent,child
from reduce import population_stats

def measured(tmp_path,ticks):
 p=parent();c=child(p,cpu_ticks=0);f=B.Families()
 before=f.apply([p,c],tmp_path);m=B.begin(before,hz=100)
 after=f.apply([parent(),dict(c,cpu_ticks=ticks)],tmp_path);B.update(m,after)
 return before,after,m

@pytest.mark.parametrize('ticks,flag,stop',[(3,False,False),(30,False,False),(31,True,False),(600,True,False),(601,True,True)])
def test_exact_sixty_second_average_thresholds(tmp_path,ticks,flag,stop):
 _,_,m=measured(tmp_path,ticks);r=B.finish(m,60)
 assert r['ssh_flagged'] is flag and r['stop'] is stop
 assert S.flagged({'ssh_family':r}) is flag

@pytest.mark.parametrize('ticks,stop',[(25,False),(26,False),(150,False),(151,True)])
def test_exact_immediate_proven_ssh_sample_threshold(tmp_path,ticks,stop):
 before,after,_=measured(tmp_path,ticks)
 assert B.sample(before,after,1,hz=100)['stop'] is stop

def test_average_floor_does_not_delay_sample_stop(tmp_path):
 before,after,m=measured(tmp_path,601)
 assert not B.finish(m,59.999)['stop'] and B.finish(m,60)['stop']
 assert B.sample(before,after,1,hz=100)['stop']

def test_all_descendants_share_sample_budget(tmp_path):
 p=parent();a=child(p,cpu_ticks=0);b=dict(a,pid=22,ppid=a['pid'])
 f=B.Families();before=f.apply([p,a,b],tmp_path)
 after=f.apply([parent(),dict(a,cpu_ticks=80),dict(b,cpu_ticks=71)],tmp_path)
 r=B.sample(before,after,1,hz=100)
 assert r['source_proven_cpu_ticks']==151 and r['stop']

def test_idle_only_services_keep_old_caps_and_do_not_trigger_ssh_exclusion(tmp_path):
 before,after,m=measured(tmp_path,31)
 # Pure idle evidence has no LAN-source exception, even if its PID is allowlisted.
 idle=dict(parent(),pid=80,cmd='python /idle-cache.py',ssh_budget={'source':None,'approved_idle_service':True},cpu_ticks=0)
 im=B.begin([idle],hz=100);B.update(im,[dict(idle,cpu_ticks=121)])
 r=B.finish(im,60)
 assert r['stop'] and r['interfered'] and not r['ssh_flagged']
 assert not S.flagged({'ssh_family':r})
 assert B.sample([idle],[dict(idle,cpu_ticks=26)],1,hz=100)['stop']
 assert not B.sample([idle],[dict(idle,cpu_ticks=25)],1,hz=100)['stop']

def test_reaped_child_cpu_still_counts_at_new_caps(tmp_path):
 p=parent();c=child(p,cpu_ticks=0,child_cpu_ticks=10);f=B.Families()
 before=f.apply([p,c],tmp_path);m=B.begin(before,hz=100)
 after=f.apply([parent(),dict(c,child_cpu_ticks=161)],tmp_path);B.update(m,after)
 assert B.sample(before,after,1,hz=100)['stop']
 assert B.finish(m,60)['source_proven_cpu_ticks']==151

def test_legacy_completed_blocks_replay_source_bound_flag():
 meter=dict(cpu_ticks=50,block_seconds=60,processes=[dict(cpu_ticks=31,source={'source':'129.65.221.14 55838 129.65.221.18 22'}),dict(cpu_ticks=19,source={'source':None,'approved_idle_service':True})])
 assert S.flagged({'ssh_family':meter})
 meter['processes'][0]['cpu_ticks']=30
 assert not S.flagged({'ssh_family':meter})

def test_ledger_carries_only_health_and_deduplicates_lost_phase(tmp_path):
 root=tmp_path/'hub';events=[dict(lost={'id':'primary-0000'},replacement={'id':'replacement-primary-0000','replaces':'primary-0000'})]
 _,_,m=measured(tmp_path,31);health={'ssh_family':B.finish(m,60)}
 for identity,replaces in [('primary-0000',None),('replacement-primary-0000','primary-0000')]:
  folder=root/identity;write(folder/'interference.json',health)
  descriptor=dict(id=identity,population='primary',cell=0,replaces=replaces)
  write(folder/'complete.json',dict(host='127x08',descriptor=descriptor,interference=health,interference_sha256=sha(folder/'interference.json'),games={'unreadable-game.json':'sealed'}))
  write(folder/'hub-ack.json',{'copied':True})
 ledger=S.health_ledger(root,events,'blind-sha');assert len(ledger['blocks'])==1
 entry=ledger['blocks'][0]
 assert entry['id']=='primary-0000' and entry['source_id']=='replacement-primary-0000' and entry['ssh_flagged']
 assert 'games' not in json.dumps(ledger) and 'loss' not in json.dumps(ledger)
 # A second completed attempt for the same logical seed is never silently counted.
 write(root/'duplicate'/'complete.json',read(root/'replacement-primary-0000'/'complete.json'))
 write(root/'duplicate'/'interference.json',health)
 write(root/'duplicate'/'hub-ack.json',{'copied':True})
 with pytest.raises(AssertionError,match='duplicate logical'):S.health_ledger(root,events,'blind-sha')

def test_sensitivity_keeps_primary_rows_and_rng_and_handles_empty_strata(tmp_path):
 from schedule import ARMS
 _,_,m=measured(tmp_path,31)
 rows={'primary':[dict(id='primary-0000',cell=0,complete_sha256='a',interference={'ssh_family':B.finish(m,60)},loss={a:1 for a in ARMS},draw={a:False for a in ARMS},win={a:False for a in ARMS}),dict(id='primary-0001',cell=1,complete_sha256='b',interference={},loss={a:0 for a in ARMS},draw={a:False for a in ARMS},win={a:True for a in ARMS})]}
 ledger={'blocks':[dict(id=r['id'],complete_sha256=r['complete_sha256'],ssh_flagged=S.flagged(r['interference'])) for r in rows['primary']]}
 original=copy.deepcopy(rows);rng=np.random.default_rng(2026101040)
 primary=population_stats(rows['primary'],rng,100);state=copy.deepcopy(rng.bit_generator.state)
 sensitivity=S.analyze(rows,ledger,100,2026101040,population_stats,np.random.default_rng)
 assert rows==original and rng.bit_generator.state==state and primary['n']==2
 result=sensitivity['populations']['primary']
 assert result['retained']==1 and result['excluded']==1 and result['statistics']['n']==1
 assert result['statistics']['stratum_counts']=={1:1} and not sensitivity['selection_eligible']
 only={'primary':rows['primary'][:1]};one={'blocks':ledger['blocks'][:1]}
 result=S.analyze(only,one,100,2026101040,population_stats,np.random.default_rng)['populations']['primary']
 assert result['status']=='NO_UNFLAGGED_BLOCKS' and result['statistics'] is None
 ledger['blocks'][0]['ssh_flagged']=False
 with pytest.raises(AssertionError):S.analyze(rows,ledger,100,2026101040,population_stats,np.random.default_rng)

# The historical OP-4 suites exercise unchanged foreign/console/unknown-source paths.
from test_op4 import test_non_lan_and_unknown_fall_back_to_identity_guard,test_non_ssh_foreign_stops_even_with_lan_ssh_family,test_console_stop_has_no_low_load_exception
