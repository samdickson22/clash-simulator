# Hog 2.6 parent stochasticity audit

Date: 2026-08-29

## Decision

The retained parent's unit-temperature stochastic distribution is not a
competent PPO behavior initializer.  Reject further unit-temperature PPO from
this checkpoint, regardless of curriculum weighting.

The same checkpoint, decks, seeds, and paired seats produced:

| Opponent | Deterministic | Stochastic T=1 | Win delta |
|---|---:|---:|---:|
| balanced | 3-3 | 0-6 | -3 |
| random | 6-0 | 0-6 | -6 |
| **total** | **9-3** | **0-12** | **-9** |

Stochastic placement rate rose from roughly 7% to 11.1% against balanced and
13.1% against random.  Thus the model's argmax policy is meaningfully better
than samples from its learned spatial tail.  Every prior PPO campaign began
from the latter behavior distribution, explaining why even random/Hog-mirror
curricula immediately generated nearly all losses.

## Required correction

Measure a frozen sampling-temperature sweep before changing training source.
Any adopted temperature must be used consistently for rollout sampling, stored
old log probabilities, PPO new log probabilities, entropy terms, and the
behavior-space anchor KL.  Deterministic deployment evaluation remains
unchanged.  A temperature that cannot retain competent free-running play is
rejected before PPO.
