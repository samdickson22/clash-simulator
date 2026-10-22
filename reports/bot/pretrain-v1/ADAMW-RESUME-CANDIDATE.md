# AdamW resume contract candidate

This follow-up addresses the inherited P2 in
[FP64-OFFLINE-CANDIDATE.md](FP64-OFFLINE-CANDIDATE.md). Its exact base is
`1ebd0b0a3939761ae2d33eadeed27422eee042f8`. Work is isolated at
`/mpac/sdicks02/t3/worktrees/clasher/resume-contract-20261022`, with detached HEAD.
The parent owns landing. This work does not qualify production resume, adopt
FP64, select anchors or authorize RL.

The public schema and derivation are in
[RL-LEARNER-CONTRACT.md](RL-LEARNER-CONTRACT.md#adamw-resume-invariant).
Previously, any subset of initialized optimizer states could load. The loader
now derives the complete expected set and exact scalar counters, checks canonical
parameter IDs and rejects unsupported partial-update states. It records packed
PPO actor eligibility and replays the fixed seeded shuffle schedule to derive
policy-head participation. No stored initialized-parameter allowlist is trusted.
Deleting eligibility evidence together with optimizer states cannot shorten the
required completed-update history.

The loss graph explains why an all-parameters rule would be wrong. Three warmup
updates train only `value.*`. PPO trains the trunk on every minibatch, but trains
`noop.*`, `ptr.*` and `tile.*` only when that whole optimizer minibatch has an
eligible actor row. A declined boundary can have legal slots and no eligible
actor. Masking within a connected graph gives dense zero gradients and still
initializes AdamW. The actual-gradient tests establish that distinction for
absent event tokens and masked policy rows.

For the toy budget, each update has four optimizer steps. Updates 0, 1 and 3 have
no state, value counters 4, and value counters 12, respectively. After update 4,
value counters are 16, trunk counters are 4, and head counters are 4 for the
eligible fixture, 2 for the one-eligible-row fixture, or absent for all-forced and
boundary-declined fixtures. After three PPO updates using forced, sparse and
eligible patterns, counters are 24 for value, 12 for trunk and 6 for heads.
The registered budget uses the same formulas with 256 steps per update.

## Verification on 2026-10-22

All commands used the existing pinned environment
`/mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python`, PyTorch 2.7.1,
GPU visibility empty, one CPU thread per math library, nice 15 and disabled
pytest plugin autoload. Preflight found 114.5 GiB available memory and load1 2.94.
No duplicate qualification jobs were found. Existing pure Python pytest
dependencies were read through a symlink under this worktree's ignored
`qualification-artifacts/`; neither Python environment was modified.

- New `test_optimizer_resume.py`: **51 passed in 32.28 seconds**.
- Prior focused suites: **162 passed in 58.17 seconds**. These are
  `test_fp64_qualification.py`, `test_rl_learner.py`, `test_stream_actor.py`,
  `test_rl_coordinator.py` and `test_rl_math.py`, including all 70 prior learner
  cases and the retained S100/M FP32 byte comparisons. No tests skipped.
- `git diff --check` passed.

New tests capture actual gradients immediately before optimizer steps and check
their participation and counters. They establish bitwise model, optimizer,
metrics and shuffle continuation after updates 0, 1, 3 and 4 in FP32 and
test-only FP64. Patterns include eligible, one eligible row, all-forced and
declined boundary polls. A longer mixed history checks that head participation
accumulates across multiple PPO updates.

Corruption cases delete empty, one-state and multiple-state subsets; change
value, trunk and each head's counters to old, future, fractional, nonfinite,
negative and zero values; duplicate, permute, subset or relabel canonical IDs;
remove evidence together with matching states; and damage evidence shape,
history length or padding. Update-0 unexpected state is rejected. Injected
warmup and PPO failures before a first optimizer step or after a completed step
remain saveable diagnostics and fail closed on load. Prior tests retain halted
diagnostic loads after upstream stops and validation failures before shuffling.

The model, `rl_math.py`, Session, stream actor and coordinator sources are
byte-unchanged from the exact base. The FP32 config record and default training
math are unchanged. Existing test-only FP64 conversion and identity behavior
remain unchanged. Only completed-update eligibility bookkeeping is added to
updates. `main` remains `4292e520550b4c19feaf305856508fd0a9588d9f`.

## Known limits

Older checkpoints without the required eligibility evidence fail closed. Partial
updates cannot resume; even a consumed shuffle permutation without an optimizer
step is not a completed boundary. Trusted local checkpoint serialization remains
the threat model. This contract does not authenticate coordinated rewrites of
eligibility bytes, moments, counters and checkpoint claims.

The evidence is at most 950,272 bytes at the registered 32-update budget. Shuffle
replay requires the same NumPy algorithm and exact configuration. The graph proof
applies to the current PolicyV1 and unchanged loss branches; changes to gradient
connectivity require updating this contract and its actual-gradient tests.

No engine capture, real training job, GPU, remote machine, Mac, lease or existing
job was accessed. The existing candidate worktree and dirty root checkout were
not modified. Full runtime, engine/queue/coordinator resume qualification remains
open, as do all existing production precision and launch gates. Independent
Sol high review of the committed candidate is required before parent handoff;
its result and exact reviewed SHA accompany the handoff.


## Parent integration

Independent Sol high review returned scoped GO for exact source
`0f72b1eaadaa6b8ea7384edbb7f8d842a41df4f4`, with no findings and eight additional
passing probes. The parent integrated that reviewed commit and its reviewed
test-only FP64 base into main, verifying all pretrain source blobs match exactly.
Historical worktree and root-main references above describe the implementation
run. Full runtime resume and every production precision/RL launch gate remain open.
