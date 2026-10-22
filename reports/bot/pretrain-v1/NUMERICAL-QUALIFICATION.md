# Numerical qualification, unresolved

The registered absolute `2e-6` likelihood/value gate fails for the reviewed learner on retained real CPU Session rows from the selected v3 checkpoints. No optimizer step ran. No threshold, model, policy, objective or deployment has changed. The final RL starts must still be qualified on the exact selected larger-snapshot checkpoints.

| Measurement | PyTorch | Size | Rows | Max log-probability error | Max value error | Failing rows logp/value |
|---|---|---|---:|---:|---:|---:|
| numerics-cpu05.json | 2.10.0+cu128 | S100 | 1183 | 5.65279191e-06 | 7.83801079e-06 | 8/83 |
| numerics-cpu05.json | 2.10.0+cu128 | M | 703 | 3.98499365e-06 | 4.20212746e-06 | 2/13 |
| numerics-cpu08.json | 2.7.1+cu118 | S100 | 1183 | 4.66550963e-06 | 1.04010105e-05 | 10/97 |
| numerics-cpu08.json | 2.7.1+cu118 | M | 703 | 4.46183081e-06 | 3.09944153e-06 | 3/6 |
| numerics-cuda08-02.json | 2.7.1+cu118 | S100 | 1183 | 4.69911759e-06 | 1.06990337e-05 | 23/115 |
| numerics-cuda08-02.json | 2.7.1+cu118 | M | 703 | 1.05624318e-05 | 5.7220459e-06 | 10/19 |

These rows use microbatch 128. Measurements at batch 1 and 256 also fail. GPU peak reserved memory stayed below 1 GiB in this measurement; this is not a full PPO update memory profile. The captured actor ran PyTorch 2.10.0, so the 08 measurements also contain a framework-version difference. They must not be presented as an isolated same-version CPU/GPU comparison.

## Minimized padding reproduction

`rl-readiness/padding_probe.py` finds a single S100 row at tick 705. The actor value is `-0.16533386707305908`. Re-evaluating that row with its chunk-padded entity width 8 gives `-0.16533678770065308`, an absolute error of `2.9206275939941406e-6`. Trimming the entity width to its three present entities restores the actor value exactly. Event and reveal widths remain 13 and 5. This isolates padding as one cause, with the same process, checkpoint and PyTorch version.

Disabling the MHA fast path for that retained row changes the result again and does not restore the reference. This is diagnostic evidence, not a proposed global kernel setting. A shape-invariant mathematical policy can still produce different float32 results across padding, batching or kernels. The strict gate remains a requirement.

## Next controlled measurement

An isolated copy of the existing 01 PyTorch 2.7.1+cu118 environment was staged on 05. All 15,533 package payload files were SHA256 verified against 01; source package manifest SHA256 is `36a91f825596ecdb9f55acf524f68aef98969984616b8785c2ba34fa13287cc8`. It has its own copied Python base. Existing training and bot environments were unchanged. Matching-version actor capture is in progress before repeating CPU/GPU measurements. Its manifest includes torch and NumPy versions. Padding, kernel and framework effects remain under investigation; no numeric workaround is qualified.

The exact reviewed minimal source archive on 08 has SHA256 `3fbc176ffef9975665a410438b08f05425c74ed44cd2b2e46feef44a61a06eba`; retained v3 input archive SHA256 is `a2bf47f2c0e3c8d865894e3eebf24462dabd120afa5b7c6b3c37070c2ac16455`. Per-array digests and policy/runtime hashes are in each chunk manifest. The measurement script SHA256 is `5c6e16b3054ec81f7253032415448a6c0993606519c5c377ba7c6810266cf41f`. Source, selected anchors and inputs were checked before use. All artifacts are under `/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/`, with 08 originals under `/mpac/sdicks02/jobs/clasher/pretrain-v1/rl-numerics-v3/`.

## Matching-version control

Fresh actual Session captures on 05 using PyTorch 2.7.1+cu118 and NumPy 2.3.5 reproduce the original command hashes, 1,183/703 rows, zero rejections/discards and one deadline row per game. All old/new public feature NPY files match byte-for-byte. The matching-version input archive SHA256 is `679fa5a7797589fc3bc9a4a8274bab46ad825bc15b0d3b516a7679e642c5e8b9`. Both same-host CPU and 08 GPU measurements still fail the strict gate. Framework version alone does not resolve it.

| Measurement | Size | Max log-probability error at microbatch 128 | Max value error |
|---|---|---:|---:|
| numerics-cpu05-py271.json | S100 | 4.12991258e-06 | 7.83801079e-06 |
| numerics-cpu05-py271.json | M | 4.3356405e-06 | 2.86102295e-06 |
| numerics-cuda08-py271.json | S100 | 4.97701173e-06 | 1.07288361e-05 |
| numerics-cuda08-py271.json | M | 8.80182043e-06 | 7.21216202e-06 |

A further measurement-only probe evaluates one explicit attention math-backend configuration on CPU references and GPU batches, using retained real states and exact Session conditional likelihood normalization. It does not generate actual actor samples under that configuration, change production source, or qualify a new runtime setting. The completed result also fails for both sizes. At microbatch 128, CPU logp/value errors are 5.566e-6/6.557e-6 for S100 and 3.199e-6/3.338e-6 for M; GPU errors are 5.566e-6/9.775e-6 and 9.500e-6/4.888e-6. Batch 256 also fails. Thus matching versions and this explicit math backend do not resolve the gate. No kernel setting is adopted. Evidence: `rl-readiness/kernel-probe-math271.json`.


## Higher-precision forward diagnostic

The isolated `kernel_probe_fp64.py` measurement passes the same absolute `2e-6` gate on all retained
real states. The variant changes the model's 22 explicit float input casts to its class-token dtype,
then converts the network to float64 for this forward-only probe. It uses the explicit attention math
settings above. Production source, actor sampling and optimizer state remain unchanged.

| Size | Rows | CPU128 max logp/value error | GPU128 max logp/value error | Failing rows |
|---|---:|---:|---:|---:|
| S100 | 1183 | 7.7525e-7 / 2.0539e-14 | 7.7525e-7 / 4.5519e-14 | 0 |
| M | 703 | 4.8579e-7 / 6.7168e-15 | 5.4056e-7 / 9.5479e-15 | 0 |

Microbatch 256 also passes on CPU and GPU. The reference is unpadded CPU batch 1 with exact Session
conditional normalization and selected-slot tile head; these are recomputed distributions, not fresh
Session samples under FP64. Total probe wall time is 248.410 seconds. The GPU guard records completion
at 10:40:27Z. Output: `rl-readiness/kernel-probe-fp64.json`. The unchanged likelihood helper still casts
its logits to float32, which contributes sub-budget error in this diagnostic.

Prototype model SHA256: `5ac5c1c2818b2f00c88f530ee1496323cddc62138e10d438316e6361c47044dc`.
Source archive SHA256: `ec875e0523b2746873527321f17958904b2030561b5075bc765bec6e346e7d35`.
Measurement script SHA256: `6bb5af71bf9f92d041ca8bd3e4c290766d10a4fcf63d8f7a0a3fcb43776fa989`.

A five-pass M CPU1 padded-row forward measurement on 05, explicit math settings and no gradients,
gives mean/p95 16.963/17.039 ms FP32 versus 26.444/26.513 ms FP64, about 1.56x mean cost.
`rl-readiness/precision-forward-cost-05.json` retains individual timings. This is a network-only small
sample, excludes featurization, and does not measure Mac latency, full RL updates or actor games/h.

The result supports preparing a concrete higher-precision engineering option for review. It does not
qualify or adopt it. Required evidence still includes actual production Session sampling, exact next
selected BC starts, a reviewed dtype contract across actor/anchor/learner/optimizer/checkpoints, strict
parity after an update, throughput/memory and target latency. Full RL remains blocked.


## Actual FP64 Session candidate, offline-only GO

Fresh independent Sol high review gives offline candidate handoff GO for code
`bf96bd145f381367c667f639cc262326f58c87e1`; evidence-only commit
`1ebd0b0a3939761ae2d33eadeed27422eee042f8` follows it. The isolated worktree is
`/mpac/sdicks02/t3/worktrees/clasher/t3-a37980ca`. Its 162 focused tests pass on PyTorch 2.7.1.
Default FP32 outputs and policy digests match landed source exactly on retained real fixtures.
The candidate is explicit `test_only=True` and cannot admit FP64 into production.
Candidate package SHA256 is `2d9842c8d8ab9631767b8f9fc732b66bff9bcba282cba6228d04e69e2958e9f6`.

One fresh production Session game per old v3 size generated 1,183 S100 and 703 M rows, with zero
discards or rejected commands and one deadline row each. CPU1/CPU4 learner checks at batches 128/256
pass the unchanged `2e-6` bound on every row. These are actual sampled Session likelihoods and values,
replacing the earlier diagnostic's recomputed reference limitation.

The exact reviewed source and actual captures were hash-verified on 08. GPU checks at batches
128/256 also pass every row. Both sizes complete a fresh 256-row warmup fixture with two AdamW
steps and a checkpoint roundtrip. Results are retained on 05 as `rl-readiness/fp64-S100-cuda1.json`
and `rl-readiness/fp64-M-cuda1.json`; 08 originals and launch receipt are under
`/mpac/sdicks02/jobs/clasher/pretrain-v1/fp64-candidate-bf96bd145/`.

| Size | Actual rows | GPU128 max logp/value error | GPU256 max logp/value error | Test peak reserved GiB |
|---|---:|---:|---:|---:|
| S100 | 1183 | 7.7525e-7 / 4.5519e-14 | 7.7525e-7 / 3.9135e-14 | 1.012 |
| M | 703 | 5.4056e-7 / 9.5479e-15 | 5.4056e-7 / 8.7153e-15 | 1.762 |

The GPU guard records clean completion at 11:17:43Z. Reserved memory includes these small
forward/warmup/roundtrip fixtures; it does not qualify full effective-batch-2048 PPO, maximum entity
widths or the production 262,144-row update buffer. No registered RL run started.

The admitted next-snapshot S100 anchor also has a fresh CPU1 Session capture and check: 886 real rows,
true terminal, zero discards/rejections and no nominal-deadline row in this game. Batches 128/256
pass with max logp error 1.0419e-6 and value error 2.0151e-14; the 256-row warmup fixture passes too.
Its exact source anchor SHA256 is `74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f`.
These artifacts are under the candidate's `qualification-artifacts/<package-sha>/capture-next-S100-cpu1`
and `check-next-S100-cpu1`. Its GPU check is independently guarded on own host 02. Next-M remains
pending selection.

Remaining evidence includes real-size PPO and post-update actual Session parity, production memory
and throughput, exact next-M starts, target Mac CPU latency, engine continuation/recycling and the
integrated harness review. A separate fix addresses the inherited incomplete-AdamW-state resume
weakness identified by review. Neither that finding nor these passes authorize production precision
adoption, model selection or RL launch. The reviewed candidate code is now on main behind its explicit test-only gate. Production precision is unchanged.

The exact next-S100 GPU check completed cleanly on 02 at 11:22:17Z. All 886 rows pass at
batches 128/256, max logp error 1.0419e-6 and max value error 3.4750e-14. The 256-row warmup
fixture and checkpoint roundtrip pass. Peak reserved memory is 0.869 GiB for this small fixture.
05 receipt: `rl-readiness/fp64-next-S100-cuda1.json`. This closes this checkpoint's initial
CPU/GPU parity measurement only; full PPO and post-update captures remain open.


### Both exact next anchors pass real PPO fixture, 2026-10-22 12:52Z

The revised source, independently approved in R38, completes both selected next starts. Each has 8,448
retained polls, zero discards, three critic warmups, one real PPO update and 256 fresh post-update polls.
Maximum post-PPO CPU/GPU likelihood error is 3.292e-7 S100 and 6.414e-7 M, below the unchanged 2e-6 bound;
all value/padding/optimizer/anchor proofs pass. Ordinary rejected taps are retained and separately counted
under Sam's preregistered amendment. No other execution failures occurred. This supersedes the pending
bounded-fixture gate only. [PPO-FIXTURE-READOUT.md](PPO-FIXTURE-READOUT.md) binds full results, counters,
observed memory, costs and archive hashes. Production rollout, soak, precision and launch gates remain open.
