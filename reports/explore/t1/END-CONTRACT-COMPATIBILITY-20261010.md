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

## Post-launch check, 2026-10-10T19:37:28Z

The reviewed final E4 END changes now accept verbatim stopped contributing phases and bind the blind ledger/counted inventory. Option B supplies both original phases and the new replacement-r1 phase:157 durable originals preserved,22 started losses replaced, and2893 unstarted originals redispatched. Never pass the original dispatch twice or omit a stopped contributing phase. Reporting uses immutable aeeb3003 / OP6 d60586b3; post-dispatch main release/corpus changes are not reporting-source inputs.

Two remaining END integration points require the E4 owner's reviewed disposition before references:

- The current fleet_validity.ReportingGuard imports the eight OP1–OP4 modules and invokes frozen ssh_budget methods, so its actual thresholds can follow OP6. FLEET-END-CONTRACT.md/GUARD_RULES still describe OP4. Final profile/source inventory must name the reviewed OP6 guard regime, preserving the prior pure-idle caps and0.5% flag. No T1 change to the E4 code is authorized here.
- OP5 seeds populate ssh_budget.FAMILIES.sources inside host_audit.admission via parent_source_seed.admit. The current E4 ReportingGuard calls census without that admission path and starts with a new Families object. It therefore does not automatically reuse T1's exact-generation committed source seed for the long-lived04→08 parent. If that transport survives at END, the owner must provide reviewed enforcement for the pinned seed/join, or obtain source proof through ordinary capture. Do not assume another process's in-memory source cache transfers to the reference guard, refresh a parent generation, or loosen unknown-source rules.

Reference validity is deliberately stricter than reporting: fleet_validity stops on OP1 DBus/idle interference and rejects SSH-flagged work blocks. Fresh08 smoke r7 observed8/8 SSH flags and8/8 DBus flags. An END reference with the same flagged exposure cannot qualify under the current reviewed adapter. Preserve and disclose any failed attempt; a clean END window or an outcome-blind reviewed ruling is needed. No production reference has been attempted, and this does not block the sealed reporting run.
