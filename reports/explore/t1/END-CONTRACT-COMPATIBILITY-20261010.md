# T1 compatibility check of E4 END contract

Checked `FLEET-END-CONTRACT.md` (`d74e2dcc`) against T1 OP-4 candidate
`cb1b9f12`, frozen plan, phase producer and Amendment 1. No references or
outcomes were read; reporting remains zero/SEALED.

- **Stopped counted phases conflict.** E4 requires every exit to have null
  reason, no failures and no unstarted blocks. T1 preserves valid hub-complete
  blocks when a host stops, including an08 B-window stop; its raw exit therefore
  can contain counted completed blocks alongside failures/unstarted queue.
  Replacement phases recover the rest. END must bind those verbatim exits plus
  the blind loss/redispatch ledger and counted-block inventory, rather than
  require every contributing phase to be pristine. Never rewrite a raw exit or
  drop a counted host to satisfy the contract.
- **Guard conflict.** Current host_audit requires additional pinned sources
  `perception_confirmation.py`, `owned_supervisor.py` and `ssh_budget.py`.
  OP-4 additionally needs aggregate sample/per-block CPU metering; invoking
  census alone does not enforce its budgets. Any console user stops. E4's
  documented one-core/60-second console rule and OP-1-only interference rules
  require updating to the reviewed final reporting guard before references.
- **Compatible:** launch slots/host, exits'UTC/host,1Hz MHz and census fields.
  Both rows share the same UTC string; full occupancy is`inflight == slots`.
  Slot0, all counted hosts/attempts, committed artifact SHAs and v2 pooling agree
  with Amendment1. No actual completion receipt exists before reporting ends;
  its future health-only producer must add exact`counted_host_phases`, counts,
  completion UTC and source/inventory bindings.
- **Corpus:** retain the committed20-field/public-only contract, separate physical
  info/reserved packet, D1 pre-poll/history and cutoff-inclusive selection.
  Amendment1 A1.3 and this END contract govern full committed-posterior replay;
  the earlier partial-progress relay cannot be consumed by the committed E4
  validator. Independent corpus-builder approval is still needed before A6.

The Amendment1 release implementation will be reviewed on an isolated branch;
reporting bytes remain unchanged. Both release routes will require a verified,
committed pool and registration packet before any outcome access.
