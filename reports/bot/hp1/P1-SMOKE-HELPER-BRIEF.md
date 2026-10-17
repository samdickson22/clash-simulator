# HP1 P1 CPU-smoke helper brief (Sol, gpt-6.1-sol high). Relaunch from this file after a restart.

You run the P1 pre-GPU checks on 127x04 for the HP1 owner (Opus). **CPU only. Never use a GPU.** Keep
`CUDA_VISIBLE_DEVICES=` empty in every command. Finish your task only with the final result or a failure report;
send no progress messages.

## Standing rules (Sam, binding)

- **Always steer, never queue:** `t3_thread_send` mode `steer`; on `thread_not_sendable` resend with `auto`; never
  `queue`. You shouldn't need to message anyone.
- **Say less:** results, failures and decisions only.
- **Hosts:** 127x04 only. Never 02, 03, 05 (except reading local files), 06, 07 or 09–18.
- **Signals:** never `pkill -f` or `pgrep -f`. Signal only your own verified PGIDs (from each `logs/NAME.receipt.json`).
- **Times and hashes:** from commands, never typed.
- **No code edits.** If anything needs a code change, stop and report it.
- **Never overwrite or delete** an existing output, overlay or checkpoint.

## Fixed paths

```
J=/mpac/sdicks02/jobs/clasher/bot-hp1-p1-20261017
SRC=$J/src-ff5fa65fc7ba          # git archive of main ff5fa65fc (T4 qualification already verified)
S=/mpac/sdicks02/repos/clasher-t11-home-v1/data/v2-store-v1
PY=/mpac/sdicks02/envs/clasher-gpu/bin/python
V2=$J/models/v2-best-dev-step-00046459.pt
```

Older dirs in `$J` (`source/` = main 5e1003463, `smoke/cpu-cap` from it, and `logs/overlay*` and
`logs/cpu-cap-1*` from the failed first try) stay untouched; don't reuse those names.

## Launch form (one lease per step; exit marker written by the command)

```
ssh 127x04 "export BOT_CPU_CAP=70 NUMPY_MADVISE_HUGEPAGE=0; bash $SRC/bot/detach.sh $J/logs/NAME.log $J/logs/NAME.receipt.json \
  bash $SRC/bot/exit/cpu_job.sh 1 nice -n 15 bash -c 'cd $SRC && OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0 \
  NUMPY_MADVISE_HUGEPAGE=0 CUDA_VISIBLE_DEVICES= $PY -B -m MODULE ARGS; echo \$? > $J/logs/NAME.exit'"
```

Wait by polling only `$J/logs/NAME.exit`, every ≥ 30 s.

## Common trainer arguments (T4)

```
COMMON="--store $S/train --dev $S/dev --assets $J/inputs/assets.npz --qualification $J/inputs/T11-STORE-PASS.json \
 --device cpu --batch-size 64 --microbatch 64 --workers 0 --epoch-fraction 0.00001 --max-steps 50 --smoke \
 --warmup 2000 --patience 3 --tile-width 64 --checkpoint-every 1000"
```

## Steps

1. **overlay-b** (it may run at the same time as step 2).
   - `MODULE=imitation.hp1.lagshift`, `ARGS="--store $S/train --out $J/overlay-lag30"`. First check that
     `$J/overlay-lag30` does not exist.
   - Pass: exit 0, `$J/overlay-lag30/overlay.json` exists.
   - Record its full `stats` object.
2. **cap1-b:** `MODULE=imitation.hp1.train`,
   `ARGS="$COMMON --layers 6 --ffn 1536 --epochs 3 --seed 1 --output $J/smoke/cpu-cap-b --stop-after-epochs 1"`.
   Pass:
   - exit 0;
   - `$J/smoke/cpu-cap-b/complete.json` has `stopped_by_signal` true, `epoch` 1, `cursor` 0;
   - an `epoch-000-step-*.pt` exists;
   - `$J/smoke/cpu-cap-b.hp1-options.jsonl` exists beside the directory.
3. **cap2-b** (after cap1-b): the same ARGS, but `--stop-after-epochs 2 --resume <the exact epoch-000-step-*.pt path
   from step 2>`.
   - Find the name with `ls`; never pass a glob to the command.
   - Pass: exit 0; `complete.json` now has `epoch` 2, cursor 0, a larger `step`, and the same `best_dev` or a lower
     one; `train.jsonl` shows a second start event.
4. **lag-b** (after overlay-b):
   `ARGS="$COMMON --init $V2 --lr 1e-4 --overlay $J/overlay-lag30 --epochs 2 --seed 2 --output $J/smoke/cpu-lag-b --stop-after-epochs 1"`.
   - Pass: exit 0; `complete.json` epoch 1, cursor 0; `stopped_by_signal` true.
5. **lag2-b** (after lag-b): the same ARGS without `--init`, plus `--stop-after-epochs 2 --resume <exact
   epoch-000-step-*.pt of lag-b>`.
   - Pass: exit 0; epoch 2.
6. **Checkpoint pins.** For the last checkpoint of cap2-b and of lag2-b, load each on 04 with `$PY` (CPU, torch
   `weights_only=True`) and print `sorted(ck['hashes'])` and `ck['config']`.
   - Expect T4_code `301caa1003ab…`, plus T4_throughput, HP1_train, HP1_lagshift, T11_sampling and
     T5_bounded_loader.
   - lag also has HP1_init and hp1_overlay.
   - cap config: layers 6, ffn 1536. lag config: layers 4, ffn 768.
   - Use a `python -c` one-liner; don't write script files on 04.

## Finish

Final message, ≤ 15 lines:
- PASS/FAIL per step;
- the overlay `stats` (shifted_earlier, unshifted, delayed, dropped, busy rows, the dt histogram summary, and play
  counts before/after);
- the dev `best_dev` values;
- the pin check;
- wall time per step.

On failure: the step, the exit code, the log tail (≤ 30 lines), and anything still running (PGIDs).
