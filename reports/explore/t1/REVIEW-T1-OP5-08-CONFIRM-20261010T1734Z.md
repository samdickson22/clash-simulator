# T1 OP-5 08-extension fast confirmation: CONFIRM

- Reviewer: independent T1 reviewer (Claude, on 127x05), for coordinator 0523ae6f, 2026-10-10T17:34Z
- Candidate: `c32015b16f41b0e8dae7b9502c00c9074b0b3be9`. Inputs: server generation `0e137378`, client receipt `274aed9a`, joined seed `ce042b97`. Base: `103fb51a` (OP-5 `a697647b`, CONFIRMED in `627f7842`).
- Scope: git plus local 127x05 only. No SSH to 01/03/04/08. No outcomes read. Reporting is untouched.

## Verdict: CONFIRM

The 08 seed is an exact, fail-closed join of two committed, SHA-pinned receipts. The 03 path and every OP-4 meter and cap are unchanged. No runner, reducer, plan, dispatch or meter file changed. There's one non-blocking residual (R1) on the 08 side.

## 1. The join is exact

- **Three committed blobs.** `git show <commit>:<path> | sha256sum` equals both the working copy and the pin, for all three:
  - `0e137378`: `f47a87ab…a420f`
  - `274aed9a`: `10735e94…50961`
  - `ce042b97`: `7081bb44…a7c27`

  `FROZEN-T1.json` lists all three in `files`. `admit()` runs each through `committed_binding()`, which checks the path prefix, the manifest pin, the on-disk SHA and the bytes at the commit, and asserts on any failure.
- **The manifest.** All 128 `files` hashes verify in a clean worktree at `c32015b1`. The packet's `extension.diff` and `source-join.diff` match `git show --format=fuller` byte for byte.
- **Parent, six fields.** The seed's `parent` must equal the server generation's `parent` plus `cmdline_sha256` as a whole dict. That gives 1896254 / 138108616 / 3822945 / PPID=PGID 1896170 / `4c329d01…`. The live row must also match all six fields and be `authenticated()`. Other requirements: `cmd == 'sshd: sdicks02@notty'`, `host == 127x08`, schema.
- **04 client generation.** The seed's `client_identity` (2508732 / 94882802 / `c15e293c…` / PPID 1 / PGID 2508732 / UID 3822945) must equal both `identity` and `identity_recheck`:
  - all four UID fields are checked;
  - the argv must equal the frozen mux title;
  - `sha256(cmdline_hex)` is recomputed;
  - `client_pid` and `client_starttime` are checked;
  - exactly one owner is allowed;
  - the owner must hold `fd → socket:[69931223]`, which is the inode of the ESTABLISHED (`01`) tuple 129.65.221.14:55838 → 129.65.221.18:22 with UID 3822945.
- **Reversed tuple.** `ssh_connection` must be exactly `129.65.221.14 55838 129.65.221.18 22`, with `candidate_peer` and `destination` exact. The committed 08 `/proc/net/tcp` must contain `12DD4181:0016 0EDD4181:DA1E 01` with inode 59570153. I decoded these independently: .18:22 ← .14:55838, ESTABLISHED.
- **ControlPath.** Both `control_path` and `exact_cmdline_argv` must equal the frozen `…/v4-a1-parallel-r2/sockets/sdicks02@127x08-22-a1-body-seal-r4`, and `result` must be `ESTABLISHED_SOCKET_OWNER_AND_SERIAL_SLOT_BINDING_CONFIRMED`.
- **My extra mutation probes** each returned no seed (19 of them):
  - server: host, schema, cmd, `candidate_peer`, extra parent key, TCP state 06, missing TCP table;
  - client: result, observation host, two owners, state, UID, argv, `cmdline_hex`, recheck PPID, fd link, `client_pid`, schema;
  - the 08 receipt with no dependencies.

## 2. The 03 semantics are unchanged

- The 03 receipt has no `source_join`, and its binding (`b2f9e25e`, `167cbe71…`) is unchanged. Its path in `matching()` is the old predicate, and `test_op5.py` (12 tests) passes.
- Host gating comes before any join. On 01, both receipts are skipped, so there's no seed (tested). On 03, the 08 receipt is skipped. On 08, the 03 receipt is skipped.
- A new generation or any semantic mismatch gives no seed: `joined_08` returns False and catches every lookup and type error. Contradictory live source evidence is never overwritten (tested).
- Integrity failure aborts. A tampered or uncommitted dependency raises `AssertionError` (tested). So does a missing `source_join` key.

## 3. OP-4 is unchanged

- `ssh_budget.py` and the meter are untouched. A seeded parent's non-reader child is still charged. Over 60 s it flags interference, a 1 s sample stops it, and an over-budget 60 s window stops it (`test_08_join_still_budgets_nonreader_children_and_stops`).
- The 08 long-window CPU (1.07% over 1360 s) and recent CPU (2.64% over 99 s) are disclosed as diagnostic only. Real admission and block metering still govern.

## 4. Nothing else changed

`git diff --name-only 103fb51a c32015b1` contains only these 11 files:

- `FROZEN-T1.json`
- `OP5-08-T1.md`
- `PROGRESS-T1.md`
- `parent_source_seed.py`
- `qualify.sh` (adds `test_op5_08.py` only)
- `test_op5_08.py`
- the four new receipts
- the 04 receipt

There are no runner, reducer, plan, launch, supervisor, `ssh_budget` or dispatch changes, and dispatch stays at `a4c16936`. In `FROZEN-T1.json`, two hashes change (`qualify.sh` and `parent_source_seed.py`) and seven are added. Nothing is removed.

## 5. The PPID-1 limitation is adequately handled

The PPID-1 gap only leaves open *which serial launched* the mux. That question doesn't matter for OP-5, which asks whether the 08 parent's peer is our own LAN client. That is proven on 04 at the kernel level: the fd-to-socket-inode link, the TCP tuple and state, the UID, identity plus recheck, and an exe and argv that equal the frozen ControlPath. The mux also holds the ControlPath's unix listener (inode 69931234, a `ControlPath.<suffix>` row), and the canonical ControlPath is a socket owned by UID 3822945. The limitation is disclosed in both the seed and the receipt.

Later commit `13a5c535` repinned the mux's affinity to CPU 53. It explicitly checked that PID, start time and cmdline were unchanged and that there was no restart. Affinity isn't a join field, so the join still holds.

**R1 (residual, non-blocking).** On 08, `inode_to_pid_proof` is false, because `/proc/1896254/fd` is unreadable. The code checks that the tuple and inode exist, not that 1896254 owns them. I checked the committed diagnostics independently, and elimination closes the gap:

- Only two ESTABLISHED inbound :22 sockets exist: tcp6 has none, and the second socket comes from .15, which is 127x05.
- The .15 port changed between 17:18:18Z (48464) and 17:18:33Z (53038). That means those were transient observer sessions.
- 1896254 lives from 16:08:51Z to 17:18:33Z.

One sshd session process serves exactly one connection, so 1896254 can only be on .14:55838. That holds for this pinned snapshot only. A future join should add a uniqueness assertion over the inbound :22 rows, but this seed doesn't need one.

## 6. Tests

- **Where they ran:** a clean detached worktree at `c32015b1`, with venv `/mpac/sdicks02/venvs/t1-verifier` under `nice -n 19`.
- **Overlay:** I overlaid the 7 untracked `src/clasher/analysis/loss_review/*.py` modules that T1 imports (`delay_fixes` and others). They are pre-existing, not part of this change and not in the manifest. Tracked `src` stays at `c32015b1`; the main checkout's uncommitted `src` edits were excluded.
- **Full `qualify.sh` list (17 files):** 147 passed.
- **The 92 guard tests** (op1 5 + op2 14 + op3 7 + op4 20 + op5 12 + op5_08 34): all pass, which matches the receipt's 92/34.

## Decision

**CONFIRM** `c32015b1` (seed `ce042b97`) for admission. Next, per FROZEN, run the fresh qualification `qualified-op5-08join-r2`, then smoke-r6. Reporting stays at 0 / SEALED.
