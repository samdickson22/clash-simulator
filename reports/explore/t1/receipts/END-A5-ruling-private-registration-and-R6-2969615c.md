
## 2026-10-12 10:34Z: T1 registration: private local commit approved; reducer check moves to release

**1. Reducer check at release.** Reducer aebb2017 reads games (outcomes) before it emits its sensitivity ledger, so its equality check against the PC4 sidecar can't run beforehand. **It runs at release**: if the emitted ledger differs from the PC4 sidecar in anything but `utc`, release fails closed and nothing is reported. R6 is now limited to `release_reference.prerequisites` with its in-barrier recheck. If that path itself would read outcomes, STOP before the read and report.

**2. Private registration commit.** Some sealed registration sources are large raw health files (`capacity.jsonl` of 332 MB and 287 MB). They can't go into the public repo, so they are committed as a **local, never-pushed** commit in canonical `<R>`.
- **Protection:** the commit sits under a local ref, `refs/private/t1-registration-20261012`.
- **Content:** health and metadata only. No outcome bytes.
- **Backups:** a verified `git bundle` is stored in two places: on 05 at `t1-20261010-r1/private-registration/`, and on 08 at `t1-private-backup/`.
- **Public receipt** binds:
  - the commit SHA and tree SHA;
  - every path with its SHA and size;
  - the bundle SHAs;
  - `<R>`'s final HEAD (an ancestor check is required by `release_reference.committed`).
- **Verification:** R7 checks all of this.
