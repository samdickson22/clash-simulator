import json,tempfile
from pathlib import Path
import numpy as np
from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from scripts.hog26_public_episode_diversity import public_episode_diversity,PUBLIC_TRANSCRIPT_FIELDS
from scripts.collect_hog26_direct_simple_behavior import _atomic_json,file_sha256
root=Path.cwd()
paths={k:root/f'datasets/derived/hog26_seeded_opening_{v}_seed1278951/corpus.npz' for k,v in [('mps','diagnostic'),('cpu','cpu_probe')]}
with tempfile.TemporaryDirectory(prefix='hog26-complete-opening-compare-') as directory:
 loaded={k:load_direct_simple_behavior_corpus(p,mmap_directory=Path(directory)/k) for k,p in paths.items()}
 meta,mps=loaded['mps']; cpu=loaded['cpu'][1]
 diversity=public_episode_diversity(mps)
 diversity.update(corpus=str(paths['mps']),corpus_sha256=file_sha256(paths['mps']),role='training-only-opening-diversity-diagnostic',within_stream_opening_diversity_assessable=True)
 output=root/'reports/hog26_seeded_opening_diagnostic_seed1278951_diversity.json';assert not output.exists();_atomic_json(output,diversity)
 print({'diversity':diversity['streams'],'all_distinct':diversity['all_streams_have_distinct_public_transcripts']},flush=True)
 report={'schema':'clasher.hog26.complete-opening-device-comparison.v1','role':'training-only-device-diagnostic','corpora':{k:{'path':str(p),'sha256':file_sha256(p)} for k,p in paths.items()},'comparisons':[],'limitation':'different companion openings after first terminal; divergence before first terminal excludes that confound'}
 first_lengths={}
 for stream in [0,1]:
    episodes={k:int(np.flatnonzero((c.episode_stream_rows==stream)&(c.episode_ordinals==0))[0]) for k,(_,c) in loaded.items()}
    slices={k:slice(int(c.episode_offsets[episodes[k]]),int(c.episode_offsets[episodes[k]+1])) for k,(_,c) in loaded.items()}
    lengths={k:s.stop-s.start for k,s in slices.items()};first_lengths[stream]=lengths
    record={'stream':stream,'lengths':lengths,'fields':{},'outcomes':{k:int(c.episode_arrays['episode_final_outcomes'][episodes[k]]) for k,(_,c) in loaded.items()},'terminal_margins':{k:float(c.episode_arrays['episode_terminal_tower_margins'][episodes[k]]) for k,(_,c) in loaded.items()}}
    n=min(lengths.values())
    for field in PUBLIC_TRANSCRIPT_FIELDS:
      a=np.asarray(cpu.arrays[field][slices['cpu']])[:n];b=np.asarray(mps.arrays[field][slices['mps']])[:n]
      mismatch=(a!=b).reshape(n,-1).any(1); indices=np.flatnonzero(mismatch)
      record['fields'][field]={'differing_decisions':len(indices),'first_exact_difference':int(indices[0]) if len(indices) else None}
      if a.dtype.kind=='f':
        significant=np.flatnonzero((np.abs(a-b)>1e-6).reshape(n,-1).any(1));record['fields'][field]['first_difference_above_1e-6']=int(significant[0]) if len(significant) else None
      if len(indices):
        step=int(indices[0]);coord=np.argwhere(a[step]!=b[step]); flatcoords=coord[:4] if coord.ndim else []
        if a.ndim==1: examples=[{'cpu':int(a[step]),'mps':int(b[step])}]
        else: examples=[{'coordinate':v.tolist(),'cpu':a[step][tuple(v)].item(),'mps':b[step][tuple(v)].item()} for v in flatcoords]
        record['fields'][field]['first_examples']=examples
    report['comparisons'].append(record)
 report['earliest_first_terminal_decision']=min(v for lengths in first_lengths.values() for v in lengths.values())-1
 output=root/'reports/hog26_seeded_opening_device_comparison_20260908.json';assert not output.exists();_atomic_json(output,report)
 print(json.dumps(report['comparisons'],indent=2))
