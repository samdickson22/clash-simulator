# Rejected hard-gate PPO pilot

This lineage is rejected at update 3 despite two completed on-policy wins.

The rollout behavior was repaired: placement cadence stayed near the retained
parent (6.2%, 7.8%, 6.2%).  The PPO implementation nevertheless recomputed the
learned hard hazard gate after optimizer changes.  At update 3 that discrete
gate changed support for stored actions, producing approximate KL
`1953125.00025` and an early stop after four optimizer steps.  Update 3 is
invalid and must not be promoted.  Update 0-2 remain audit-only.

The next lineage must condition PPO ratios on the behavior gate that generated
each stored action.  Under gated collection, placement iff the gate fired, so
the stored action recovers that discrete behavior state exactly.  The hazard
head itself must be preserved with an explicit differentiable anchor term
rather than by recomputing a discontinuous threshold inside PPO.
