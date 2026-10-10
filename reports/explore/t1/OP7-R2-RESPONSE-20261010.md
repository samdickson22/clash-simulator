# OP-7 round-2 response (candidate only)

Authority: coordinator a3b7d82b/c1c9a38d, actual 21:46Z, and 7c581dc5,
actual 22:03Z. Independent r1: `REVIEW-OPUS-r1.md` in the disk review packet.
Candidate remains on the exact aeeb3003 reporting base. Neither live 08 nor
stopped 01 reporting bytes have changed; outcomes remain sealed and unread.

- **F1:** new generation-bound `cpu_accounting.Accounting` charges self CPU and
  unobserved reaped CPU, with subtree credits for already-metered observed
  children. Deepest-first credit transfer handles nested simultaneous reaping;
  persistent sample trackers carry credits across a scan-before-wait race.
  Both apt and SSH use it only in the prospective new phase. Tests cover a
  5-second observed child exiting without a sample-cap stop, a 4-deep chain
  counting 100 ticks once, simultaneous nested exits, delayed wait, unobserved
  short children and pre-block CPU. Old proofs and flags are never rewritten.
- **F2:** `_apt` is resolved from `/etc/passwd`; real/effective UID evidence
  comes from `/proc/status`. Same protected cgroup and observed approved root
  are mandatory. Kernel executable evidence must resolve to a direct methods
  child. Only EACCES permits captured raw argv0: absolute, no `..`, resolved
  direct-child regular file, root-owned and not group/other writable. Per-row
  evidence records exe versus argv0, errno and file identity. Tests deny other
  errno values, relative/escaping/wrong paths, writable/non-root targets, wrong
  UIDs/cgroups and missing ancestors. No other `_apt` executable is admitted.
- **F3:** three independent descriptive sensitivities (SSH, apt, SSH OR apt),
  fresh RNG2026101040 each; both/either counts by population and cell. Tests
  preserve primary rows, statistics and RNG, and validate both proofs even
  when the SSH flag alone already makes the union true.
- **F4:** a malformed command falls back to whitespace parsing only for the
  deny/name detector. It receives no provenance allowance and apt lookalikes
  still stop. Exact provenance parsing stays strict.
- **F5:** documentation names the protected kernel cgroup as the trust anchor;
  actual OP-7 UID checks use real/effective status fields, not proc-directory
  ownership. The base guard outside this exception is unchanged.
- **F6:** sensitivity ledger flag lookup is required-key access; a missing
  flag fails closed. Every new standalone ledger writes the separate and
  derived union flags.
- **F7:** candidate stays AWAITING_OP7_REVIEW. At admission only, restore
  FROZEN and bind the confirmation and authorization to the new manifest SHA.
- **F8:** r2 tests actually ran `/mpac/sdicks02/venvs/t1-verifier/bin/python`;
  the receipt records its resolved executable, version and pytest module.
  The historical r1 worker command used the E4 venv interpreter plus pytest
  from the reviewer-cfix PYTHONPATH overlay; that omitted environment context
  is added to the historical receipt, without inventing a different r1 run.
- **F9:** tests cover the full hybrid cgroup file, actual collector wiring,
  apt admission surviving the later allowlist-kind assignment, guard priority
  (foreign before SSH before apt), and ubuntu_apt_sample in stop-reason.json.
- **F10/F11:** PC4 discloses complete apt/SSH proofs with stop=True and mixed
  meter versions. Fresh source qualification covers the added scan overhead.

Residuals: process scans are not atomic, so CPU credit settlement can cross
samples. Auto-reaped/orphaned CPU can escape; unobserved or pre-block child CPU
can arrive as a lump. Missing approved ancestry fails closed. Budgets and
paired exposure are unchanged. No privileged reader or system-service changes.

After independent confirmation: coordinated 08 hard stop under reviewed
completion-race rules; final raw durability/ACKs; old copier drain; fresh
two-host qualification/smoke; blind inventory of only the newly stopped r1
phases; committed balanced remainder dispatch. Original phases remain
inventoried once. No one-host dispatch or END work before its declaration.
