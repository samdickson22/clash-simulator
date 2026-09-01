# Hog 2.6 joint-Q matched gameplay gate

Date: 2026-09-01

## Purpose

The five-update CUDA pilot is not allowed to promote a joint-Q candidate from
training loss or throughput alone.  This gate evaluates all three matched
control/candidate seed pairs against all six deterministic strategy bots plus
the random opponent, four games per opponent and arm: 168 games total.

## Reproducibility correction

The prior Simple evaluator made the learner policy deterministic but did not pin
the random opponent's RNG.  It now seeds NumPy and PyTorch independently for
each opponent from a stable base seed.  It also accepts CUDA so the resident
CUDA-graph simulator can perform the breadth screen on the rented host.  No CUDA
evaluation throughput is claimed until that exact route runs.

## Frozen development gate

The candidate advances to an expanded evaluation only if all are true:

- total matched outcome score exceeds control;
- at least two of three initializer seeds improve and none regress;
- at least two of seven opponent buckets improve and none regress;
- every candidate opponent bucket retains a placement rate in `[0.05, 0.35]`.

Outcome score is wins plus half draws.  A passing result writes
`PROMOTE_CANDIDATE`, whose content explicitly says expanded evaluation is still
required.  A failed candidate still publishes a complete immutable summary so
the control lineage can be considered without rerunning the screen.

## Gates

- Bash syntax clean.
- Ruff and mypy clean for both Python drivers.
- `11 passed` across synthetic broad-improvement, shifted-regression,
  passivity, opponent-seed, shell-contract, factorized-pretrain, and joint-Q
  tests.

This is a predeclared decision contract, not gameplay evidence.  The required
three-seed CUDA training output does not exist yet.
