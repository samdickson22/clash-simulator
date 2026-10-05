# v7r5 pilot candidate

Council integration and validation passed. Both seeds launched after the v7r4h stop gate, 635 seconds apart; first-20-update measurements are complete. This kit keeps the v7r4h human-prior PPO recipe and adds `recurrent_update_mode = "stored-state"`, `tbptt_chunk = 32`, and `tbptt_burn_in = 16`. The intended comparison tests whether bounded recurrent replay improves throughput. The T32 benchmark reported 3.04x throughput, but does not establish pilot learning quality.

The two configs keep every other recipe value, including sequence_batch_size 2, critic warm-up 60, anchor 0.05, 64 environments and 8 actor workers. Paths move to v6 and this kit. With stored-state mode, sequence_batch_size counts chunks, so this unchanged setting means 64 loss-bearing tokens per full minibatch, not the 256 used in the T32 benchmark. No automatic batch-size adjustment was made.

Runtime v6 copies v5 and overlays train_recurrent.py, parallel_rollout.py, imitation.py, new tbptt.py and the coordinator-authorized council_pilot.py integration. imitation.py is included for the BC contract tests. All 342 admission-bound module hashes equal v5 and the admission receipt. The shared .venv is a symlink. The runtime is 17 MiB; this kit is about 6 MiB before runs.

The council integration accepts the three TBPTT options and forwards them to the trainer. For runtimes containing tbptt.py, it permits the seven changed learner definitions while preserving admission-imported definitions and all 342 admission-bound modules. Runtimes without tbptt.py retain the legacy bindings. Nine integration tests pass, including byte-identical v7r4h commands and source-binding reports against v5. Static verification passes 107/107, including the frozen evaluation protocol.

Historical validation before integration follows. These reference fixtures were not rewritten.

Final focused suite: 43 passed, 2 failed. Both failures compare against saved workspace-era references. Separate v5/v6 default PPO and BC comparisons match exactly; both differ from those references only in fixed card-feature buffers. See logs/default-v6-comparison.json. Fixture-cwd and stdin multiprocessing attempts are preserved as superseded logs, not accepted test results.

The launcher permits only seeds 2901/2902 and stages verify/preflight/nominal. Nominal ends at 1M plus the six diagnostic cells and six human-prior-start cells. It checks both v7r4h stop-log markers and absence of their trainers before training. orchestrate.sh refuses all work. After dry runs and preflights pass and both stop markers exist with no old trainer remaining, use two individual pilot/detach.sh calls 600 seconds apart. Both seeds are running through nominal; no league stage is launched.

Read PROGRESS.md for exact commands, hashes, receipts and next steps.

Resume validation: both dry runs and both actual no-update preflights passed. Preflights used 64 environments and 8 workers, exercised critic warm-up and PPO backward passes, made zero optimizer steps and preserved weights exactly. See logs/validation-complete.json.

First-20 warm-up throughput: 2901: 55.3181 vs 18.8573 decisions/s (2.9335x); 2902: 59.3881 vs 20.7640 decisions/s (2.8602x). Full evidence is in logs/first20-throughput.json and logs/final-evidence.json. Nominal runs continue; learning quality and post-warm-up throughput remain unmeasured.
