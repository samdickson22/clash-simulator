# OP-7 round-3 delta response (not admitted)

Base candidate: 1c34584b; coordinator ruling: 088f7fc4, actual22:27Z.
Round-2 review is retained at `review/op7-r2-1c34584b/REVIEW-OPUS-r2.md`.
All changes remain in the isolated aeeb3003-based candidate. Reporting on 08
continues on its unchanged OP-6 source; 01 remains stopped. Outcomes unread.

- **N1:** each unmatched credit lot expires after three scans, independently
  of newer exits. Fresh credit cannot renew older orphan credit. Tests for both
  meters reproduce G->P->C with P never waiting, wait for expiry, then confirm
  an unrelated unobserved child's CPU is fully charged (200 total, not100).
  Within the three-scan window an orphan credit can still absorb unrelated CPU;
  after expiry late reaping can over-count. Both are explicitly disclosed.
- **N2:** block Accounting starts with lifetime credit for every process alive
  at block entry, including raw rows without allowlist tags. Only CPU gained
  within the block is charged on later reaping. Tests for both meters verify
  500 pre-block ticks plus100 in-block ticks charge100. The persistent host
  sample retains its supervisor-start baseline, as separately disclosed.
- **N4:** argv0 must be a lexical direct methods child as well as resolve there.
  The methods directory and every ancestor must be root-owned and not writable
  by group/others; per-observation proofs retain their file identity. All four
  status UIDs must equal _apt, or all four must be0 for roots. Tests deny an
  outside symlink to a valid method, writable methods directory, and changed
  saved/filesystem UIDs. The EACCES-only fallback and target-file checks remain.
- **N5:** new-version proofs require both apt and SSH meters with exactly the
  same accounting rule. Missing either meter or mismatched rules fails closed,
  even when no CPU was metered. Tests cover each denial and legacy absence.
- **N6:** supervisor-start dating of a returning process generation is
  documented as a conservative sample change; no retrospective flag changes.
- **N7:** the historical r1 UID0-only PLAN paragraph is explicitly superseded.

The first prospective admitted phase uses
`OP-7-observed-child-credit-v2`. No v1 phase has been admitted or launched.
Original and replacement-r1 proofs keep their existing source, meter and flags.
Primary selection, arm/seed/cell/seat rotation, bootstrap RNG and the release
barrier are unchanged. Only synthetic outcomes were used by the test suite.

C2 stays deferred to admission: restore FROZEN, refresh hashes and bind the
independent confirmation/authorization to the exact new manifest SHA. C3:
after coordinated08 stop/final copies/copier drain, run exact-source two-host
qualification and smoke in fresh namespaces; record census scan duration and
loop cadence; retain console/foreign stop evidence and disclose limits of
non-atomic scan/drop observation.
Do not claim timing conformance from the 05 unit tests. Then reviewed blind
inventory of newly stopped r1 phases and committed balanced remainder dispatch.
