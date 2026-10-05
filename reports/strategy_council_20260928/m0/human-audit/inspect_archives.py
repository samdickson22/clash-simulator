"""Read archive headers and small provenance arrays; never construct labels."""
import json
import zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
paths = [
'datasets/katacr_hog26_human_v1.npz',
'datasets/human_safety_fullhuman_tvtrain_seed1043701.npz',
'datasets/tv_royale_human_chronological_expanded_v2.npz',
'datasets/tv_royale_replay_disjoint_train_seed1043201.npz',
'datasets/tv_royale_replay_disjoint_holdout_seed1043201.npz',
]
results=[]
for name in paths:
 path=Path(name)
 row={'path':name,'exists':path.exists()}
 if not path.exists():
  results.append(row);continue
 row['file_bytes']=path.stat().st_size
 fields={}
 with zipfile.ZipFile(path) as z:
  for member in z.namelist():
   with z.open(member) as f:
    version=np.lib.format.read_magic(f)
    shape, order, dtype=(np.lib.format.read_array_header_1_0(f) if version == (1,0) else np.lib.format.read_array_header_2_0(f))
   fields[member.removesuffix('.npy')]={'shape':shape,'dtype':str(dtype)}
 row['fields']=fields
 with np.load(path,allow_pickle=False) as data:
  metadata=json.loads(str(data['metadata_json'].item()))
  row['metadata']={k:v for k,v in metadata.items() if k!='token_names'}
  row['tokens_count']=len(metadata['token_names'])
  actions=data['expert_actions'];episode_ids=data['episode_ids']
  row['rows']=len(actions);row['episodes']=len(np.unique(episode_ids))
  row['plays']=int((actions<2304).sum());row['waits']=int((actions==2304).sum())
  row['abilities']=int((actions==2305).sum())
  runs=np.r_[True,episode_ids[1:]!=episode_ids[:-1]]
  row['episode_runs']=int(runs.sum()); row['episodes_contiguous']=row['episode_runs']==row['episodes']
  row['episode_lengths']={k:float(fn(np.unique(episode_ids,return_counts=True)[1])) for k,fn in [('min',np.min),('median',np.median),('max',np.max)]}
  for field in ('source_replays','source_actor_ids','source_frames','source_ids'):
   if field in data.files:
    a=data[field]
    row[field+'_unique_count']=len(np.unique(a))
    row[field+'_examples']=[str(x) for x in np.unique(a)[:5]]
  if 'source_frames' in data.files:
   frames=data['source_frames']
   row['non_increasing_frames_within_episode']=int(((episode_ids[1:]==episode_ids[:-1])&(frames[1:]<=frames[:-1])).sum())
  if len(actions)<10000:
   mask=data['action_masks']
   row['masked_labels']=int((~mask[np.arange(len(actions)),actions]).sum())
  row['missing_v4_fields']=sorted(set(['entity_levels','entity_level_confidence','hand_levels','hand_level_confidence','entity_id_confidence','entity_feature_confidence','hand_id_confidence','global_feature_confidence','own_last_play_ids','own_last_play_features','opponent_history_ids','opponent_history_ages','opponent_seen_card_ids','terminal_status','board_rotated'])-set(fields))
 results.append(row)
(ROOT/'archive-inventory.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:
 print(r['path'],{k:v for k,v in r.items() if k not in ('path','fields','metadata','missing_v4_fields')})
