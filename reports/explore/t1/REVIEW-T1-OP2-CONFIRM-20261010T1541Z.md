# T1 OP-2 fast confirmation: 78c9bd5b

**Verdict: CONFIRM**

- Reviewer: independent T1 reviewer, reporting to coordinator thread 0523ae6f.
- Host: 127x05. Evidence came from git and 05 files only; I did not ssh to 01, 03 or 08.
- Time: 2026-10-10T15:41Z.
- Candidate: `78c9bd5bafd1d4d0b4bb8f5570a37da5e4e17c36` (671+/12−), on top of freeze 95883be0, which was confirmed in 9a7126f6.

## 1. Scope (PASS)

- **The commit touches only `reports/explore/t1/` files:**
  - guard and host-audit code: `host_audit.py` and the new `perception_confirmation.py`;
  - `qualify.sh`, where the only change appends `test_op2.py` to the pytest list;
  - `test_op2.py`;
  - three receipts under `receipts/op2-*`;
  - `OP2-T1.md` and `PROGRESS-T1.md`.
- **No scientific code changes.** No runner, reducer, deck, seed, plan or `FROZEN-T1.json` file is touched. T1 commits since the freeze (fe1c882f, 55114607, 00ef90e9) touch only `PROGRESS` and `FROZEN` host-set metadata.
- **The matcher's command and path set is unchanged.** `perception_reader` still accepts:
  - `argv0` with basename `cat` or `sha256sum`;
  - an optional leading `--`;
  - non-empty operands, all under `plan().perception_io_exception.path_prefix`, with no `..`;
  - `SSH_CONNECTION` whose source is `source_ip` and whose port is 22.
- **The only matcher edits narrow it:**
  - it now requires `uid==3822945`;
  - it guards against an empty-cmd ancestor;
  - when a child snapshot has a source, that child's collected `ssh_parent_snapshot` must equal the parent's `[pid, start_ticks, uid, cmdline_sha256]`;
  - the source now comes from the collection-time snapshot, or from a cached proof, instead of a late `/proc/<pid>/environ` read.

## 2. The race window admits only the frozen reader from 04 (PASS)

**How the window works:**
- The window opens only for a 127x03 `authenticated` parent with UID 3822945, and only when one of these proves the source:
  - a child snapshot with a `129.65.221.14 … 22` source that also passes the unchanged reader matcher, with its `ssh_ancestor_pid` equal to this parent; or
  - a proof cached for this job, keyed by the exact parent `(pid, start_ticks, uid, cmdline_sha256)` and pruned when that parent is no longer live.
- Without a proof, nothing waits and OP-1 applies unchanged.
- The deadline is `min(start + 2 s, first-sight snapshot + 2 s)`. It is checked again after every collect.

**Cases I checked:**

| Case | Result | Evidence |
|---|---|---|
| Unrelated child of the same proven parent: `python3`, `sleep`, `cat -- /etc/passwd`, a mixed in/out operand, a `..` path, `gzip -dc`, bare `sha256sum` | Foreign at once, with no wait | `non-reader child`; probe parametrized ×6 |
| `bash -c` wrapper with a compute grandchild | Foreign | probe |
| Resolved reader that later execs something else | Foreign | `resolved child changed command`; probe |
| Child with another UID | Foreign | probe |
| Different parent with a spoofed title (new pid/start), after a genuine parent was cached | No cache reuse, no wait, foreign | probe; T1 parametrized start/uid/cmdline change |
| Non-04 source on a child snapshot (uncached, and cached) | Foreign; the cache can't override it | T1 test, and a probe |
| Non-04 source in a spoofed parent's env | No wait, foreign | probe |
| Transient (empty argv, or the inherited title) still unresolved after 2 s | `confirmation limit`, clock ≤ 2 s | T1 test, and a probe on the real cache path |
| Transient that exits unresolved | `exited unresolved child` | T1 test |
| `op2_denied` parent in `foreign_compute` | Always forbidden. The check runs before the `allowlist_kind` and `own_process` checks, so neither can hide it | T1 test, and code read |

## 3. Tests (PASS)

- **T1's suite.** I re-ran it on 05 from a `git archive 78c9bd5b` export at `/mpac/sdicks02/tmp/t1-op2-review-2811532`: `test_op2.py` plus `test_op1.py` gave **19 passed**.
  - This ran under uv Python 3.12 with pytest, not the frozen runtime: `repo/.venv` is absent on 05.
- **Authorized paths covered by T1:**
  - positive, with the source bound to the exact parent and `block_ids` recorded;
  - the race, with no late environ read;
  - fork/exec resolving within 2 s;
  - the 2 s limit;
  - an exited unresolved child;
  - wrong source;
  - a non-reader child;
  - a changed parent identity (×3);
  - every observed child must resolve;
  - a cached parent can't override a wrong source;
  - a denial can't disappear from the foreign guard;
  - an unbound collected source.
- **My extra probes:** 15 passed, in `probe/test_probe_op2.py` in the export directory. They aren't committed to T1 files.
- **Live check:** `processes()` ran on 05 and returned 1278 rows in 0.17 s, with 29 SSH source snapshots. Real sshd parents were never bound, which is expected on 05.

## Non-blocking notes

None of these changes the admitted set, which remains only frozen readers from 04.

- **N1. The parent-snapshot evidence path can't be reached by a genuine sshd.**
  - A genuine `sshd: sdicks02@notty` is non-dumpable: on 05, reading pid 1307334's environ gives EACCES. Its `ssh_connection_snapshot` is therefore always None, and `evidence='parent snapshot'` can only fire for a same-UID process that spoofs the title.
  - T1's fork/exec, 2 s limit, exited-child and every-child tests all build the parent with `source=SOURCE`.
  - The real path is: a child snapshot, then the identity-keyed cache, then a transient. I checked that path with two probes (accept within 2 s; deny at the limit), and it behaves identically.
  - Suggestion for later: drop the parent-snapshot evidence, or re-base those tests on the cache path.
- **N2. Residual from the confirmed OP-1 trust model.** This existed before OP-2, which didn't widen it.
  - `authenticated()` checks the title and UID only, not the exe, and the source comes from the environment.
  - So a same-UID title impostor that has a 04-sourced environment, with only reader children, is accepted. My probe `test_residual_…` documents this.
  - It still admits nothing except reader children.
- **N3. Failures that stop the smoke but admit nothing:**
  - an sh/bash wrapper resolves only on the first loop pass, and a later pass trips `resolved child changed command`;
  - a zombie child (empty cmdline) is treated as transient, then denied once it's reaped;
  - each parent's wait is sequential, up to 2 s each.
  - This doesn't affect the observed 776414 pattern, where the children are direct `cat` processes.

