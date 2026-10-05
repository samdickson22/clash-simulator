"""Inventory existing historical manifest claims and artifact availability."""
import hashlib
import json
from pathlib import Path
import numpy as np

root=Path.cwd()
out=Path(__file__).resolve().parent
source=Path('reports/tv_royale_youtube_clocked_rotate_20260826/deck_closed_causal_corpus_audit_58games.json')
audit=json.loads(source.read_text())
rows=[]
for match in audit['matches']:
 path=Path(match['manifest']['path'])
 row={'manifest':str(path),'split_group_id':match['split_group_id'],'historic_counts':match['counts'],'historic_contract_status':match['contract']['status'],'manifest_exists':path.exists()}
 if path.exists():
  row['manifest_hash_matches']=hashlib.sha256(path.read_bytes()).hexdigest()==match['manifest']['sha256']
  m=json.loads(path.read_text());row['video_id']=m['source'].get('video_id');row['limitations']=m.get('limitations',[])
  row['sampling']=m.get('sampling',{})
  artifacts=m['artifacts'];required=[artifacts['neutral_sequence'],*artifacts['actor_trajectories'],artifacts['offline_actor_targets']]
  row['required_artifacts']=[{'path':a['path'],'exists':Path(a['path']).exists(),'rows':a.get('rows')} for a in required]
  row['required_artifacts_present']=all(a['exists'] for a in row['required_artifacts'])
  video_path=m['source'].get('video_path','')
  local_path=video_path.replace('/home/ubuntu/clasher',str(root),1)
  row['source_video_path']=video_path;row['source_video_exists']=Path(video_path).is_file()
  row['local_mapped_source_video_path']=local_path;row['local_mapped_source_video_exists']=Path(local_path).is_file()
 rows.append(row)
summary={'historical_audit':str(source),'historical_counts':audit['counts'],'manifests':len(rows),'matching_manifest_hashes':sum(r.get('manifest_hash_matches',False) for r in rows),'required_artifacts_present':sum(r.get('required_artifacts_present',False) for r in rows),'local_mapped_source_videos_present':sum(r.get('local_mapped_source_video_exists',False) for r in rows),'historically_verified_with_full_actor_targets':sum(r['historic_contract_status']=='passed' and r['historic_counts']['full_actor_ready']>0 for r in rows),'new_public_v4_clean_sequences_certified':0,'clean_sequences_exist':'not established by this inventory; no visual adjudication or v4 conversion performed'}
with np.load('datasets/tv_royale_replay_disjoint_train_seed1043201.npz',allow_pickle=False) as a, np.load('datasets/tv_royale_replay_disjoint_holdout_seed1043201.npz',allow_pickle=False) as b:
 overlap=set(a['source_replays'])&set(b['source_replays'])
summary['legacy_train_holdout_replay_overlap_live']=len(overlap)
summary['historical_full_actor_targets_with_local_mapped_video']=sum(r['historic_counts']['full_actor_ready'] for r in rows if r.get('local_mapped_source_video_exists'))
(out/'causal-source-inventory.json').write_text(json.dumps({'summary':summary,'matches':rows},indent=2)+'\n')
print(json.dumps(summary,indent=2))
