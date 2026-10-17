# Live regression positions (cycle-model owner; bot live-diag analysis)

`positions.json` lists live decision points whose right answer we have reasoned about: the run, the tick and poll n,
what live did, what we think it should do, and what each checked arm chose with its root scores. Any new search arm
should be replayed on all of them before a live claim.

**Check an arm:** replay the run through live-diag's trace harness with pos_cf.py, on a fleet host with the run copied
there (never on the Mac):

    CODE=<tree> bash <run-pos.sh> OUT.json <PLAYER> --run <run dir> --tick <tick> [--levels ...]
          [--lines 'a=0:<act>;b=<k>:<act>' --free 'a=0,b=<k>' --seeds 30]

run-pos.sh is live-diag's tail/run-trace.sh with the script path pointed at pos_cf.py.

**What it records:**
- the decision at the first search at or after the tick: candidates, final scores, choice;
- optionally, counterfactual lines from that root: our forced actions at tick offsets; otherwise we WAIT until the
  free tick, then play the native 'balanced' script; the opponent is the learned rollout opponent, sample j = seed.
