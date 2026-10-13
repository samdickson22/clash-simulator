# FSC: full-speed cost of always-on S-default (U3 on 127x03, U4 on 127x04; exploration, NEVER ADOPTABLE)

The assignment is U3/U4 in COORDINATOR 2026-10-13 01:15Z, from the fleet utilization plan r1, Items 3–4 and §2. It uses
the PR-1 harness-reuse lane. Readout: [READOUT.md](READOUT.md). Log: [PROGRESS.md](PROGRESS.md).

**Question.** At full speed, does making the R3a student the cutoff default (K4S) cost anything against plain K4?
Today's estimate is +2.2 [−0.3, +4.7] pp on X and +0.6 [−0.8, +2.2] pooled (X4S, X4S2).

## Arms and seeds
- **Arms:** K4-200 and K4S-200 from X4S2 `plan.json`; K4-180 and K4S-180 from X4S2 `plan-ext.json` (1501be97f).
  Every spec is equal by value, which `make_config.py` asserts.
  - [plan-fsc.json](plan-fsc.json) (03) has the two 200 ms arms.
  - [plan-fsc-04.json](plan-fsc-04.json) (04) adds the 180 ms pair. It is a strict superset with identical seed ranges.
- **Population X only:** X4S's five decks under the X4S mapping. **No G worklist.** `populations.G` stays in the
  config only because `run.py` asserts the guard decks are in the catalogue; no G seed range exists, so a G block
  cannot run.
- **Fresh bank** `X-reporting` = 4503607007370496 + [0, 7900) (2^52 + 7.38e9). Smoke uses +1e7 + [0, 8) and the STOP test +2e7 + [0, 8).
  - The block was chosen by command ([pick_seed_block.py](pick_seed_block.py), receipt
    [pick-seed-block.json](pick-seed-block.json)): it is the first 1e8 block on the X4S2 grid above every literal in the
    dense allocation region. That region tops out at K4S's declared audit-window end, 4503606999999999, above X4S-3
    (6.48e9) and X4S-4 (6.68–6.78e9).
  - The audit is [audit_seeds.py](audit_seeds.py), X4S2's with three edits: it reads plan-fsc-04.json, audits every FSC
    range as fresh, and has no paired reuse. It ran on a **git export of origin/main only**. Receipt:
    [seed-audit.json](seed-audit.json).

| Host | Worklist (dispatch order) | Blocks × games |
|---|---|---|
| 127x03 | [wl-03.json](wl-03.json): 200 pair, indices 0–2399 (primary), then 3900–5899 (top-up) | 4,400 × 2 |
| 127x04 | [wl-04.json](wl-04.json): 180 pair, indices 2400–3899, then 200 pair, 5900–7899 (top-up) | 3,500 × 2 |

At about 1,100 games/h per host, the 03 primary block takes about 4.4 h, and the 04 180 pair about 2.7 h. The top-ups
run only until STOP; they are sized to roughly fill the 8 h cap.

## Harness (X4S2 at 1501be97f; the diff is constants only)
`harness/run.py` and `harness/supervise.py` are installed as `reports/explore/x4s2/{run,supervise}.py`. The edits:
- **Host tuples:** `run.py:358` and `supervise.py:56` change from ('127x03','127x08') to ('127x03','127x04'). 08 is
  removed, because it is B's host.
- **Ceiling:** `supervise.py:65–66`. The fixed per-host date dict is replaced by "this supervisor's start + 8 h". The
  `--stop-at` is asserted ≤ that, so every phase is code-capped at launch + 8 h.
- **04 only:** `harness/plan-04.json` is installed as `x4s2/plan.json`. It is X4S2 plan.json with only the two
  checkpoint path strings pointed at `fsc-04-20261013/inputs/`. On 03, `x4s2/plan.json` is byte-identical to the pin,
  and the checkpoints are read from X4S2's job inputs.

Unchanged (byte-identical, SHA-checked at staging): `anchor_x.py`, `sdefault.py`, `runtime.sh`, `detach.sh`,
`plan.json` (03), `reduce.py`, `leftover.py`, and the 1,557-file S1 runtime pin f81f3655 (repo), plus native 44874fd6,
v1 d77005d5, R3a 37509a43 and calibration e3003533. There are no game, kernel or student changes.

## Host procedure (r2, after Sol r1 REQUEST_CHANGES; see [REVIEW-RESPONSE-r1.md](REVIEW-RESPONSE-r1.md))
Every contact goes through [session.sh](session.sh) on 05: `session.sh launch|progress|stop HOST COMMIT MANIFEST_SHA256 [STOP_AT]`.

**What session.sh enforces:**
- It rebuilds the bundle from COMMIT ([make_bundle.sh](make_bundle.sh)) and refuses it unless MANIFEST.json matches the given hash.
- One SSH session per call: BatchMode, no ControlMaster/ControlPath/ControlPersist, StrictHostKeyChecking=yes, UpdateHostKeys=no.
- A call succeeds only if the SSH exit status and the remote's last `__RC` are both 0.
- It refuses:
  - a second launch;
  - a progress call within 2 h of the last session;
  - any call after a successful stop;
  - a 04 launch once 03 is stopped.

**Launch.** [remote_bootstrap.sh](remote_bootstrap.sh) creates the fresh prefix atomically (`mkdir`, canonical parent) and
extracts the bundle. It refuses non-regular entries and checks the manifest hash and every file, then execs
[host_session.sh](host_session.sh) `launch`. That session runs under errexit and pipefail, every step is checked, and an EXIT trap prints the true `__RC`:
1. **Read-only preflight, fail-closed.** Every probe's status and numeric output is validated. Console users =
   max(`fleet-console-users`, other users' logins in `who`), and `loginctl` must succeed. Foreign processes come from two checked
   `ps` samples taken 15 s apart.
2. **Staging by exact allowlist, never copying symlinks** (`rsync --no-links`). The repo gets exactly the S1 pin's
   1,557 files, plus the native dir and three inputs.
   - **03:** the copy comes from the X4S2 job (read-only). Source roots must be canonical, non-symlinked directories. A shadow scan refuses
     any unpinned module in a runtime import directory that shares a name with a pinned or overlay module.
   - **04:** [lan_copy_04.sh](lan_copy_04.sh) runs instead.
   - `stage.py install` then refuses symlinks anywhere under the prefix and any write that resolves outside it. It verifies that the repo is exactly
     the pin plus the overlay, and checks the native, input and checkpoint pins plus the runtime python's return code.
3. **Smoke:** 8 seeds; the `hostcheck.py smoke` gate must pass.
4. **Live STOP test.**
   - Before STOP: a block must have started, the run group must have ≥ 2 live processes, and the supervisor must be alive. Otherwise the test fails.
   - STOP is touched and its time recorded. Exit must follow within ≤ 120 s, with reason `owned_STOP`, an empty census of every pre-STOP PID, and
     ≥ 1 started block left without proof.
5. **Reporting run,** detached; the group must be live 60 s later.

**Supervisor instances.** Each one runs with its own job dir `J/inst/<phase>` and its own STOP file, and **no STOP file is ever removed**.
The supervisor needs only `runtime.sh` under `--job`, which is a checked copy. `X4S2_JOB=J` keeps the runtime in J.
`J/STOP` is the permanent stop: once it exists, nothing launches or relaunches.

**Progress.** Read-only; an unplanned exit reason fails the call. **Yield:** this applies when a console user is present on a 12-slot
run and `J/STOP` is absent. The session touches that instance's STOP and requires reason `owned_STOP` plus an empty group and
census. It then relaunches the never-started blocks (`leftover.py`) as a fresh instance on 10 slots, with the same stop-at.

**Stop.**
1. Touch `J/STOP` and every instance's STOP, then wait for exit.
2. Every instance must show an empty census (receipt PID/PGID plus child PGID and supervisor PID) and a planned exit reason.
3. Check the prefix is link-free, then rsync outputs (`--no-links`, explicit non-persistent `-e ssh`) into
   `127x05:/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013/<host>/`. session.sh creates that directory fresh and canonical before the
   session and checks it link-free after. This path is coordinator-authorized (F6).

**After stop there is no further contact.** The coordinator's STOP comes ≥ 3 h before the first K4S END host step on that
host.

**Disclosed and accepted (F8).** The reused X4S2 supervisor stops its run by `os.killpg` (TERM, then KILL) on **its own
child process group only**. This is the reviewed harness behaviour. The FSC scripts themselves never signal groups or
pattern-kill; they verify by PID census.

**04 depends on 03.** The 04 copy reads 03's staged prefix (two rsync connections), so 04 must launch while 03 is still in
contact, before 03's STOP session.

## Never touched
- K4S paths (`k4s-*`, `jobs-k4s`, `k4s-end-r1`), `t1-*`, and 03's T1 corpus copy. The X4S2 job's `corpus/` is not copied.
- 04 perception storage, and the G population and its decks (no G runs).
- Sealed outcomes of any study.

Writes happen only under the FSC prefixes and the 05 mirror directory.
