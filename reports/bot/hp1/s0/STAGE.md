Staging (from 127x05, read-only on sources):
1. ssh 127x04 mkdir -p $job/{models,runs,source}; copy env.sh, run.sh.
2. Source: git archive 1e933ddc3eda1005d00182be429e79c125712260 (built on 05) | ssh 127x04 tar -x -C $job/source.
3. cp (not mv) 04:/mpac/sdicks02/repos/clasher-checkpoints/v2/main-2026100822/8779.../best-dev-step-00046459.pt
   -> $job/models/v2-best-dev-step-00046459.pt ; cp 04:/mpac/sdicks02/jobs/clasher/bot-fullpool/fits/f1a2/step-001200.pt
   -> $job/models/f1a2-step-001200.pt ; sha256sum both against the PREREG values; chmod a-w.
4. sha256sum ext/main02-fp.pt ext/R3a-fp.pt ext/policy-00010.pt -> $job/provenance-models.txt.
Launch form (env sourced BEFORE admission so BOT_CPU_CAP=70 applies; lease = WORKERS+1 python processes):
  source $job/env.sh && bash $job/source/bot/detach.sh $job/runs/NAME.log $job/runs/NAME.receipt.json \
     bash $job/source/bot/exit/cpu_job.sh $((W+1)) nice -n 15 bash $job/run.sh NAME W CANDS OPPS GAMES START BASE
Gate: after each run, copy runs/NAME back to 05 and run s0_validate.py (exact keys, 0 errors, terminal, levels,
seed/seat); nothing proceeds on an invalid run. Worker budget: at most 16 S0 game workers at any time
(cal 8 + ef 8; h uses 8 while ef is active, up to 16 only after ef has finished).
Run sequence (each a separate detach.sh + cpu_job.sh launch, explicit names, never globs):
  smoke   : run.sh smoke 6 "student:$V2@0.10,$F1A2,v1" R3a,K4C-r16 2 100 $BASE      (12 games; also validates v2 loads)
  cal-t   : run.sh cal-t 8 "$F1A2" R3a 64 $CALSTART $CALBASE                          (target plays/game)
  cal-0.. : run.sh cal-<k> 8 "student:$V2@<tau_k>" R3a 64 $CALSTART $CALBASE           (sequential)
  ef      : run.sh ef 8 "$F1A2,v1" R3a,K4C-r16 100 0 $BASE                            (may overlap calibration; total <= 16 workers)
  h       : run.sh h 8 (16 only if ef finished) "student:$V2@<tau*>" R3a,K4C-r16 100 0 $BASE               (after tau* frozen)
Rows are copied back to 05 and analysed there (no analysis code on hosts).
