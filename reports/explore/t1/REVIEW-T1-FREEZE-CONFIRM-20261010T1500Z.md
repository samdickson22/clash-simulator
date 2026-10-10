# T1 freeze fast confirmation — 95883be0

Reviewer: the independent T1 reviewer (author of round 3, c0813ed4). Reports to coordinator 0523ae6f.
Base: afa3f10e (round 3 APPROVE_WITH_CONDITIONS C1, C2). Candidate: **95883be0bfd4d0a6e8dade56ca6a6669637c4a49**.
Method: git only (`git diff afa3f10e 95883be0 -- reports/explore/t1`, `git show`, `git archive` into /tmp). No ssh to 01/03/08, and no job directories or outcomes read.

## Verdict: **CONFIRM** (reporting may start, subject to the gates the freeze already lists)

The delta is C1 + C2 + OP-1 + freeze records. The verifier files and the round-3 review in the diff are mine (c0813ed4) and were excluded from this review.

## 1. Attribution of every changed T1-owned file

| File | Δ | Attribution |
|---|---|---|
| run.py | 1 line | **C1.** The per-game stdout is now `{game, terminal}` only. `terminal` is `b.game_over` (a health bit, and line 337 asserts it is true). Wall and CPU stay in the sealed game JSON. The block-level line 340 prints only `{block, complete_games, wall_seconds}`, the block wall receipt that was allowed in round 3. |
| guard-decks.json | 2 lines | **C2.** Only `utc` and `selector_sha256` changed. The deck lists, support and skips are byte-identical. The new `selector_sha256` 21125180… equals the manifest SHA of the unchanged `select_guard_decks.py`. |
| host_audit.py | +35 | **OP-1.** `exe`/`exe_evidence` fields, with the argv0 fallback only for UID 103 and argv0 `/usr/bin/dbus-daemon` when `/proc/exe` is unreadable. A system dbus or an sshd session with children is foreign unless it is allowlisted. Census classifies allowlist kinds, records `allowlist-occurrences.jsonl` with block IDs, and admission pins the bus. The old `sshd` name exemption from the active-CPU meter is removed (that was the broken `sshd:` parser). |
| system_bus.py, ssh_transport.py, test_op1.py | new | **OP-1.** |
| supervise.py | +11/−4 | **OP-1.** Passes active block IDs to census, adds a per-block dbus CPU meter and per-kind allowlist counters, and puts `interference.system_dbus` and `allowlist_observations` into interference.json and complete.json. Bus interference ORs into `interfered`, so it flags the block without stopping it. |
| **mirror.py (+33)** | | **OP-1, owned copier.** `register()` writes `owned-copier-admission.json` (pid, pgid, start, cmd SHA, uid, exe, source IP, phase, job) and pushes it to the target hosts before supervisors start. Every remote `rsync --server`/`find` now runs as `env T1_COPIER_PID=… T1_COPIER_PGID=… <cmd>`, so `ssh_transport.copier_activity` can attribute it. The copy logic (exclude, pending, hash-verify, ack) is unchanged. It also adds an assertion that the phase name matches the regex. There's no outcome access. |
| **seed-audit.json (+7)** | | **Freeze record.** Only `utc`, `status` DRAFT-PASS→FROZEN-PASS and a new `frozen_at_utc` changed. The ranges and historical intervals are unchanged, and `intersections` is still `[]`. |
| **health.py (+1)** | | **OP-1 recording.** Sums `interference.allowlist_observations` into `counts['allowlist_<kind>']` (a Counter, so no KeyError). It reads only interference metadata, never outcomes. |
| **qualify.sh (+1/−1)** | | **OP-1.** Adds `test_op1.py` to the qualification pytest list (55 → 60 tests on the hosts). |
| PLAN.md, PROGRESS-T1.md, FREEZE-T1.md, FROZEN-T1.json, receipts/* | | **Freeze records:** status, C1 wording, Amendment-1 note, qualification bindings, the system-bus/idle admission receipts and the excluded-smoke receipt. |

Unchanged from afa3f10e (from the diff name-status): reduce.py, barrier.py, schedule.py, replace.py, stage.py, smoke_pass.py, audit_seeds.py, select_guard_decks.py, plan.json, anchor/belief/planner/latency/gc_window, cached_policy, corpus*, all inherited/*.

## 2. OP-1 narrowness and deny paths

- **dbus:** the pin needs exactly one row with UID 103, the exact full system command and exe `/usr/bin/dbus-daemon`. Membership needs pid, start_ticks, exe, cmdline SHA and uid to all match. Any other UID-103 or `--system` dbus-daemon is forbidden even when idle. Session buses get no allowance. If the pinned bus is absent at block entry, `begin` asserts, which fails closed. The per-block meter flags at `ticks*100 > hz*elapsed`, which is strictly above 1%. The receipts for 01, 03 and 08 record `exe_evidence = "argv0 (proc/exe unreadable, unprivileged)"`, as the ruling requires.
- **sshd:** only `sshd: $USER@notty` sessions with our own UID qualify. Every descendant branch must end in a perception_reader, idle_cache or owned_copier_child leaf. The only intermediates allowed are sh, bash and env, and one unknown branch rejects the whole session. Any other `sshd: …@…` with children is foreign. The copier leaf needs the registered PID/PGID in its environ, `SSH_CONNECTION` from the hub IP to port 22, `rsync --server` or the exact `find` argv, and absolute paths only under the job dir. On the hub it also needs the live copier identity to match.
- **Recording:** each 1 Hz census appends every allowlisted identity (kind, pid, pgid, start, cmd SHA, block IDs) to `allowlist-occurrences.jsonl`, and each block's complete.json carries per-kind counts.
- **Tests (7 passed locally, `uv run pytest test_op1.py test_idle_services.py` on the archived tree):**
  - allow and deny cases for each of dbus pid, start, exe, cmd SHA and uid;
  - the 1% boundary;
  - sshd with an extra or unknown child, with no child, with uid 0, with a preauth title, and with a shell hiding an unknown leaf;
  - copier with the wrong PID, wrong PGID, wrong origin, an out-of-job path, or an unapproved program;
  - the foreign_compute integration for both dbus and sshd.
- The host bindings show 60/60 tests passing on each of 01, 03 and 08 (qualification-freeze-summary.json).

Non-blocking observations (all fail closed; none affect validity):
- **O1:** Any other user's SSH session that has children (for example a student's interactive login) is now foreign and will stop the host. The tty console exemption in supervise.py probably doesn't cover sshd rows. This is the strict reading of the ruling. Expect availability stops on busy hosts and record them as stops, not as interference.
- **O2:** `register()` pushes the copier receipt to the target hosts with plain rsync. While supervisors are live, that unattributed transport would be foreign. FREEZE-T1.md already requires registering before admission and running one copier phase at a time. Don't restart or re-register the copier while reporting supervisors run on the target hosts.
- **O3:** Approved sshd transport and copier children are excluded from the active-CPU meter without their own per-block CPU flag (only dbus has one). The ruling doesn't require one, every occurrence is logged, and the copy volume is small sealed JSON. Disclose this alongside the allowlist counts.
- **O4:** Because the system bus is always present, `allowlist-occurrences.jsonl` gains about one line per second per host (tens of MB over the run). That's acceptable.

## 3. Science, seeds and reducer

No arm, candidate, score, seed range, gate, schedule or reducer byte changed. run.py's game logic is identical apart from the C1 print. The excluded smoke attempt started at 14:24:49Z is preserved and excluded entirely (0 complete blocks, `outcomes_read: false`). Rerunning it on smoke-class seeds in a fresh namespace is fine; interrupted reporting seeds are never reused, and none exist (reporting_games_started = 0).

## 4. Sealing

All 93 SHAs in FROZEN-T1.json match the committed blobs at 95883be0, checked with `git show | sha256`. The only tracked T1 files outside the manifest are FROZEN-T1.json itself and three older receipts. None of the new receipts contain outcome fields. health.py and stdout stay outcome-free. When T1 records this verdict, FROZEN-T1.json and PROGRESS may change, but none of the 93 hashed files (including FREEZE-T1.md) may change. Bind the reporting authorization to the resulting commit and manifest SHA.

## 5. Amendment 1 pool-before-release

**Acceptable.** Deferring enforcement to "before any release, not before reporting" is fine, because nothing in reporting can open outcomes. barrier.py only opens on a coordinator-signed committed Mac summary, or on a signed fourteen-day escape at least 14 days after a committed completion receipt. The new precondition is procedural until its implementation is reviewed. **Binding condition (release-time, not reporting-time):** the coordinator must not sign any release receipt, including the escape, until a separately reviewed barrier/reduce amendment that checks the committed pooled-reference + registration packet (commit + SHAs) is committed and frozen. Recording that in the release runbook is enough.

## Remaining gates (unchanged, already listed in FROZEN-T1.json `pending`)

1. Post-freeze excluded 64-game smoke and health-only admission.
2. Explicit reporting authorization bound to the manifest commit and SHA.
