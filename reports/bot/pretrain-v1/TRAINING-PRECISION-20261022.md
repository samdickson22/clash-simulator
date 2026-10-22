# Candidate training precision amendment

This amendment is prepared before registered RL starts. It requires independent source review and the
complete launch review. It does not by itself authorize training or admit an experiment result.

The strict absolute 2e-6 CPU actor versus learner likelihood gate remains unchanged. FP32 failed that gate.
Both exact selected 41k-snapshot anchors passed the R38 FP64 fixture, including a PPO update and fresh
post-update actor rows. Maximum post-update likelihood errors were 3.292e-7 for S100 and 6.414e-7 for M.
R40 then measured maximum token shapes at microbatch128 with a frozen anchor and resident AdamW moments.
Reserved GPU memory peaked at 8.95 GiB for S100 and 19.44 GiB for M, within the 43.5 GiB admission budget.
The fixture and allocation limitations in PPO-FIXTURE-READOUT.md and PROGRESS.md still apply.

The proposed registered training configuration explicitly uses
`precision='float64', precision_registration='dual-size-fp64-20261022-r1', test_only=False`
for both sizes and all three paired seeds. Convert each verified FP32 BC start to FP64 before constructing
the human anchor and optimizer. CPU actors, model parameters, gradients and AdamW moments use FP64.
The existing joint-distribution implementation still casts logits to FP32. This amendment preserves it.
There is no AMP, TF32, attention-backend change, tolerance relaxation or change to Session sampling.

Both arms keep 262,144 generated polls per update, 32 updates, three critic warmups, effective batch2048,
microbatch128 with exact accumulation, two optimizer epochs, LR1e-5, zero weight decay, the same PPO/KL
objective, seeds, opponents and terminal-only reward. The numerical trajectory can differ from FP32;
this is recorded rather than treated as bitwise FP32 continuation. No existing run is resumed or reinterpreted.
The original FP32 default configuration record and model behavior remain unchanged. A registered FP64
configuration without the exact amendment identifier is rejected. Checkpoints carry that identifier, so a
different precision or missing registration cannot be silently resumed as this experiment.

Primary RL evaluation uses the exact saved training policy and records its precision. Report comparisons to
each own BC start with both numerical identities explicit. Sam's accepted M deployment target remains FP32
CPU1, with prior p95 about16ms. No serving conversion, live configuration change, new Mac run or deployment
occurs here. Any later FP64-to-FP32 serving conversion needs its own behavior and game-strength validation.

Independent review of this amendment covers only the precision/configuration component. The integrated
driver must bind the reviewed source and this document's SHA in its launch receipt. It must also enforce
the unchanged strict parity gate, full rollout accounting, frozen populations/banks, independent worker
resource monitoring and the registered soak. Missing gates remain launch blockers.
