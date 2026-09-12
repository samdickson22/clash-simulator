# Active Clasher objective

Build and rigorously validate a calibrated actor-visible Hog 2.6 outcome model
from complete games, predicting undiscounted W/D/L and terminal tower margin
across held-out seeds, opponents, seats and phases. Privileged information is
permitted only in a training-only teacher. Search, policy updates, PPO and
self-play learning remain gated on public calibration and counterfactual ranking.

Sam explicitly authorized clearing and resetting the stale goal on September12.
The local backend thread/goal/clear operation succeeded, and thread/goal/set
recreated this exact objective as active with no token budget. The backend
read-back verified active status. No work was falsely marked complete.
The ten-minute scheduled continuation checks remain configured.

Immediate work:
1. Finish the existing frozen comparison, without duplicate fitting jobs.
2. Review both neural seeds and all excluded-family folds. Compare fitting
   versus excluded errors to distinguish fit capacity from generalization.
3. Record the data coverage limits, especially natural draws and late-game
   independent scenarios. Do not treat decision count as independent games.
4. Use the completed comparison to draft the next data/model experiment with
   frozen roles, exact quotas, sources and evaluation rules before collection.
   Do not silently expand the completed pilot quota or open reserved outcomes.
5. Pursue calibration and ranking acceptance on the preserved protocol.

Read reports/hog26_protocol_reassessment_20260908.md for current evidence and
/Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json
for live supervision. This file records the continuing objective, not a passed
gate or permission to change frozen acceptance requirements.

Current execution update: both384-game corpora and all20frozen-model transfer
evaluations are complete and reviewed. Collection of1152fresh training games
is now running under reports/hog26_scaling_frozen_plan_20260912.json, with no
automatic fitting. Original384+new1152 form the proposed1536-game comparison.
Preserve pinned source while collecting; prepare new fitting code separately,
then verify complete combined audit, actual training memory and fitting-source
pins before execution. Diagnostic384 remains excluded from training. Read the
latest chronology and live supervisor state; do not relaunch prior jobs.
