from corpus import quotas,stratum

def test_proportional_strata_and_sparse_stratum_minimum():
 q=quotas({(0,0):1,(1,1):1000,(2,2):1000},300)
 assert sum(q.values())==300 and q[(0,0)]==1
 assert abs(q[(1,1)]-q[(2,2)])<=1

def test_exact_bin_boundaries():
 assert stratum(2.99,0)==(0,0)
 assert stratum(3.,1)==(1,1)
 assert stratum(6.,128)==(2,2)

def test_committed_snapshot_clears_private_generator_without_touching_live_state():
 import copy,pickle
 from types import SimpleNamespace
 from corpus import committed_belief
 live=SimpleNamespace(_pending=(x for x in range(2)),states=[1,2],events=['a'])
 sealed=committed_belief(live)
 assert sealed._pending is None and live._pending is not None
 assert pickle.loads(pickle.dumps(sealed)).states==[1,2]
 sealed.states.append(3);assert live.states==[1,2]

def test_resume_and_fresh_committed_history_give_same_complete_belief():
 import numpy as np
 from belief import Belief
 from derived_public_state import PublicEvent
 from corpus import committed_belief
 prior={'decks':[{'cards':list('ABCDEFGH'),'frequency':2},{'cards':list('ABCDEFGI'),'frequency':3}]}
 costs=dict.fromkeys('ABCDEFGHI',3);b=Belief(prior,costs);b.block_rows=17
 events=[PublicEvent(1,'card','A')];now=[0.]
 def clock():now[0]+=.001;return now[0]
 try:b.update(20,events,deadline=.02,clock=clock)
 except TimeoutError:pass
 fresh=committed_belief(b);b.update(40,events,deadline=1e6,clock=lambda:0.);fresh.update(40,events)
 for k in ('states','weights','cumulative'):np.testing.assert_array_equal(getattr(b,k),getattr(fresh,k))
 r1=np.random.default_rng(11);r2=np.random.default_rng(11)
 assert [b.sample(r1) for _ in range(16)]==[fresh.sample(r2) for _ in range(16)]
 assert r1.bit_generator.state==r2.bit_generator.state

class CaptureBelief:
 _pending=None
 def update(self,tick,events,deadline=None):assert deadline is None
 def sample(self,rng,deadline=None):assert deadline is None;return dict(public_sample=int(rng.integers(10)))

class CaptureCore:
 def candidates(self,packet,proposals):
  import numpy as np
  assert proposals in ([],[12]);self.rng.integers(10)
  return [12,13,2304],np.ones(2306,dtype=bool)

class CaptureRoot:
 def snapshot(self):return b'public sampled root'
 def digest(self):return 'public digest'

def test_capture_path_cached_and_uncached_outside_window_validates_rows():
 import copy,numpy as np,pytest
 from types import SimpleNamespace as N
 from corpus import contract
 from corpus_capture import capture_row
 from cached_policy import CachedPolicy
 from gc_window import WINDOW
 def check():assert WINDOW.active
 for tier in ('K0c','S','K2','K4'):
  rng=np.random.default_rng(11);state=copy.deepcopy(rng.bit_generator.state)
  d1=N(public=True);mask=np.ones(2306,dtype=bool);physical=N(tick=90,events=[],own={'elixir':4},packet=N(physical=True));reserved=N(reserved=True)
  before=dict(pending=(),belief_had_suspended_transaction=True,belief_before=CaptureBelief(),belief_rng_state=copy.deepcopy(state),candidate_rng_state=copy.deepcopy(state),policy_rng_state=b'policy rng',d1_before={'tick':85},d1_events=[])
  policy=N(opponent_elixir=5,player=N(last_d1=d1),mask=mask)
  p=N(core=CaptureCore());R=N(costs={},root=lambda info,opponent,rng:CaptureRoot())
  cached=None
  if tier in ('K0c','S'):
   cached=CachedPolicy(N(model=None,costs={}),check=check)
   with WINDOW:cached.cache=(d1,mask.copy(),[{'action':12}])
   with pytest.raises(AssertionError):cached.propose({'action_mask':mask},d1)
  assert not WINDOW.active
  row=capture_row(p,R,physical,reserved,policy,cached,before,tier+'-200',4503603407370500)
  contract().validate_row(row,tier)
  assert row['info'].packet.physical and row['reserved_packet'].reserved
  assert before['candidate_rng_state']==state and before['belief_rng_state']==state
  assert row['belief_had_suspended_transaction'] is True
  if cached is not None:assert cached.forward_calls==cached.proposal_calls==cached.fallback_calls==0

def test_builder_validates_every_selected_row_and_published_capture_receipt(tmp_path,monkeypatch):
 import gzip,pickle,json,sys
 from types import SimpleNamespace as N
 import corpus
 from common import write,sha,plan
 captures=tmp_path/'captures';output=tmp_path/'out';bank=plan()['seed_ranges']['corpus']['base']
 for tier in ('K0c','S','K2','K4'):
  path=captures/f'corpus-{tier}-0004';path.mkdir(parents=True)
  rows=[]
  for i in range(300):
   r=dict(id=f'{tier}/{bank+4}/{90+i*10}',tier=tier,seed=bank+4,info=N(tick=90+i*10),reserved_packet=None,pending=(),opponent_elixir=5.,d1_before={},d1_events=[],d1=None,policy_rng_state=None,candidate_rng_state=None,belief_before=N(_pending=None),belief_had_suspended_transaction=False,belief_rng_state=None,opponent=None,root_rng_state=None,root=b'synthetic public state',root_digest='synthetic',strata=dict(elixir=4.,legal_play_count=2,bins=[1,1]))
   rows.append((corpus.priority(r),r))
  with gzip.open(path/'capture.pkl.gz','wb') as f:pickle.dump(dict(counts={(1,1):300},rows={(1,1):rows},health=dict(eligible_search_opportunities=300,deadline_cut=100,suspended_transaction=0)),f)
  write(path/'descriptor.json',dict(index=4,phase='corpus',game_class='qualification'))
  write(path/'local-complete.json',dict(capture_sha256=sha(path/'capture.pkl.gz')))
 contract=corpus.contract();calls=[];receipts=[];validate=contract.validate_row;validate_receipt=contract.validate_capture_receipt
 def row_check(row,tier):calls.append(row['id']);return validate(row,tier)
 def receipt_check(*args):receipts.append(args[1]['corpus_receipt']);return validate_receipt(*args)
 monkeypatch.setattr(contract,'validate_row',row_check);monkeypatch.setattr(contract,'validate_capture_receipt',receipt_check)
 monkeypatch.setattr(sys,'argv',['corpus.py','--captures',str(captures),'--out',str(output)])
 corpus.main();assert len(calls)==1200 and receipts==['corpora.json']
 assert all(v['states']==300 for v in json.loads((output/'corpora.json').read_text())['tiers'].values())
