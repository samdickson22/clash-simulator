"""Amendment12 D4 file checks. No selection/heldout authority.

The outer orchestrator must first authenticate actual capture, formal fit,
controlled-host replay, completion and source provenance. Expected hashes here
come from that admission, never from unchecked score claims. A fidelity failure
writes a durable suspension and invokes the required coordinator notifier.
"""
import gzip,hashlib,json,math
from collections import Counter
from pathlib import Path
from clock_free_records_v4 import event_predictions
from validation_replay_v4 import frame_times,completed_predictions
from measured_dominance_v4 import optimistic_counts

class VoidRecord(ValueError):pass
class RecordFidelityFailure(ValueError):pass

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def checked(path,pins):
 path=Path(path)
 if str(path) not in pins or sha(path)!=pins[str(path)]:raise VoidRecord('Missing or changed external file pin: '+str(path))
 return path

def read_rows(path):
 opener=gzip.open if str(path).endswith('.gz') else open
 with opener(path,'rt') as f:return [json.loads(x) for x in f]

def verify_d4(*,bound_path,body_seal_path,body_seal_sha256,episodes,
              bound_truth_path,measured_truth_path,truth_mapping_source,
              files_sha256,spells,incident_path,notify_coordinator):
 """Recompute both prediction multisets from actual files, not claimed counts.

    episodes maps IDs to frames/records/outputs/completions paths. The admission
    caller supplies the complete registered population and authenticated pins.
    notifier must deliver the suspension receipt; notifier failure also aborts.
 """
 if not callable(notify_coordinator):raise ValueError('Coordinator notification callback required')
 bound_path=checked(bound_path,files_sha256);body_seal_path=checked(body_seal_path,files_sha256)
 bound=load(bound_path);seal=load(body_seal_path)
 if sha(body_seal_path)!=body_seal_sha256 or bound.get('body_seal_sha256')!=body_seal_sha256:
  raise VoidRecord('D4(a): body seal hash missing or changed')
 if seal.get('schema')!='clasher.v4.clock-free-body-seal.v1' or set(seal.get('epochs',{}))!={str(e) for e in range(1,25)}:
  raise VoidRecord('D4(a): complete body seal required')
 if bound.get('body_threshold')!=seal['epochs'][str(bound['epoch'])]['body_threshold']:
  raise VoidRecord('D4(a): sealed body threshold differs')
 checked(truth_mapping_source,files_sha256)
 bt=checked(bound_truth_path,files_sha256);mt=checked(measured_truth_path,files_sha256)
 def fidelity(reason):
  receipt=dict(schema='clasher.v4.record-fidelity-suspension.v1',reason=reason,
   bound_sha256=sha(bound_path),body_seal_sha256=body_seal_sha256,
   elimination_suspended=True,selection_allowed=False,
   only_admissible_continuation='measure every remaining cell without elimination')
  p=Path(incident_path)
  with p.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
  notify_coordinator(p,receipt)
  raise RecordFidelityFailure(reason)
 if bt.read_bytes()!=mt.read_bytes() or bound.get('truth_rows_sha256')!=sha(bt):
  fidelity('D4(b): truth lists are not byte-identical under the pinned mapping source')
 truth=load(bt)
 fields={'episode','card','side','kind','execution_timestamp_ms'}
 if not isinstance(truth,list) or any(set(r)!=fields for r in truth):raise VoidRecord('Explicit truth row list required')
 if any(r['episode'] not in episodes for r in truth):raise VoidRecord('Truth population differs')
 total=0;predicted=Counter();observed=Counter();all_expected=[]
 for ep,paths in sorted(episodes.items()):
  paths={k:checked(v,files_sha256) for k,v in paths.items()}
  if set(paths)!={'frames','records','outputs','completions'}:raise VoidRecord('Complete frame and replay files required')
  frames=read_rows(paths['frames']);times=frame_times(frames)
  records=read_rows(paths['records']);outputs=read_rows(paths['outputs']);clocks=read_rows(paths['completions'])
  if len(clocks)!=len(times):raise VoidRecord('D4(c): completion population differs')
  # Strict IEEE comparison; no isclose and no epsilon. Same source stamps
  # feed record reconstruction and the bound production_timestamp_ms.
  for i,(clock,stamp) in enumerate(zip(clocks,times)):
   available=clock.get('available_timestamp_ms')
   if (type(available) not in (int,float) or not math.isfinite(available)
       or clock.get('timestamp_ms')!=stamp or available<stamp):
    raise VoidRecord('D4(c): availability precedes or differs from source frame')
  expected=event_predictions(records,episode=ep,expected_times=times,spells=spells,threshold=bound['threshold'])
  actual=completed_predictions(outputs,clocks,episode=ep,expected_frames=len(times),calibration={})
  all_expected.extend(expected)
  for p in expected:
   if p['production_timestamp_ms']!=times[p['source_seq']]:raise VoidRecord('D4(c): production stamp differs')
   if p['side']==0 and p.get('kind','card_play')=='card_play':predicted[(ep,p['source_seq'],p['card'],p['side'])]+=1
  for p in actual:
   if p['available_timestamp_ms']<times[p['source_seq']]:raise VoidRecord('D4(c): prediction precedes frame exactly')
   if p['side']==0 and p.get('kind','card_play')=='card_play':observed[(ep,p['source_seq'],p['card'],p['side'])]+=1
  total+=len(times)
 if predicted!=observed:fidelity('D4(b): opponent prediction multiset differs despite possible equal counts')
 normalized_truth=[dict(episode_id=r['episode'],**{k:v for k,v in r.items() if k!='episode'}) for r in truth]
 if bound.get('opponent')!=optimistic_counts(all_expected,normalized_truth,episodes=episodes):raise VoidRecord('Bound counts differ from same source-frame predictions and pinned truth')
 for path,digest in files_sha256.items():
  if sha(path)!=digest:raise VoidRecord('Evidence changed during verification')
 return dict(schema='clasher.v4.dominance-file-validity.v1',body_seal_sha256=body_seal_sha256,
  body_threshold=bound['body_threshold'],truth_rows_sha256=sha(bt),truth_mapping_source_sha256=sha(truth_mapping_source),
  prediction_multiset_sha256=hashlib.sha256(json.dumps(sorted((list(k),v) for k,v in predicted.items()),separators=(',',':')).encode()).hexdigest(),
  predictions=sum(predicted.values()),frames=total,files_sha256=dict(files_sha256),
  available_at_least_frame_exact=True,selection_authorized=False,heldout_opening_authorized=False)
