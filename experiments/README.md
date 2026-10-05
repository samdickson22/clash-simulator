# Archived experiments

This directory is archived in place. These Hog26 experiment drivers and helper modules support older reports. They are retained at `experiments/` because some compare exact source hashes, index manifests by the original path, or inspect process command lines. Moving the tree to `archive/experiments/` would require changing those contracts and reproducing their evidence.

The public cleanup leaves their code and recorded pins unchanged. Treat this directory as historical, not as a recommended training recipe. Many runners require local datasets, checkpoints, or machine-specific paths. Read the relevant study before running a supervisor.

| Study family | Directories |
| --- | --- |
| Scalar corpus and early baselines | `hog26_scalar_pilot`, `hog26_seed_transfer`, `hog26_data_scaling` |
| Cache construction and scaling | `hog26_expanded_corpus`, `hog26_scaling_fit`, `hog26_scaling_eval` |
| Public features and history | `hog26_public_semantics`, `hog26_public_history`, `hog26_online_value_features` |
| Outcome, margin, and auxiliary models | `hog26_*margin*`, `hog26_*value*`, `hog26_terminal_*` |
| Parallel collection and review | `hog26_parallel_*`, `hog26_threaded_*`, `hog26_tree_*` |

Current public-player results are indexed in [reports](../reports/README.md). Historical acceptance rules remain attached to their original runs.
