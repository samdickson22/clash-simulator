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

## Host procedure ([host_session.sh](host_session.sh); new host-touching code, so it gets a narrow review)
The bundle is built from committed bytes by [make_bundle.sh](make_bundle.sh) (fsc at the commit, plus the X4S2 files from
1501be97f, plus MANIFEST.json). Every SSH below is a single session; there are no pollers, cron entries, timers or
units. Everything runs under nice 19 (supervisors also taskset 62, game slots 0–59).

1. **Launch, one session per host:** `tar -C BUNDLE -cf - . | ssh 127x0N '<fresh J check>; mkdir -p $J/bundle && tar -xf - -C $J/bundle && exec nice -n 19 bash $J/bundle/fsc/host_session.sh launch 127x0N [STOP_AT]'`
   1. **Read-only preflight:**
      - `fleet-console-users`;
      - MemAvailable ≥ 24 GiB;
      - /mpac free ≥ 20 GiB;
      - no foreign sdicks02 python/rsync/clasher process in two samples 15 s apart;
      - runtime python present;
      - no STOP file.
   2. **Stage:**
      - **03:** local copy of the X4S2 job's repo, excluding the x4s, x4s2, k4s-confirm and t1 overlays and any `t1-*`/`k4s-*` path, plus native and the three inputs. The source is read-only.
      - **04:** [lan_copy_04.sh](lan_copy_04.sh).
      - Then `stage.py install` installs the overlay and verifies the S1 pin, native, inputs, the X4S2 pins and the FSC files. It writes `staging.json`.
   3. **8-seed smoke** (8 workers, smoke range): `hostcheck.py smoke` gate. It checks proofs, X4S2 game checks, deck, checkpoint, `s_default`, and a clean exit. No losses are printed.
   4. **Live STOP test** (4 workers, STOP-test range): STOP is touched about 20 s after the first block starts. `hostcheck.py stoptest` requires `owned_STOP`, an empty group, a PID census of 0, and reports the STOP-to-exit time. STOP is then removed.
   5. **Detached reporting run** (`setsid`): 12 slots, or 10 with a console user, with `--stop-at` = min(now + 7 h 55 min, the coordinator's STOP_AT). The session prints the PID/PGID receipt and `launch.json`, checks the group is alive 60 s later, prints `__RC`, and disconnects.
2. **Progress:** at most one SSH per host every 2 h (`progress`), read-only. **Yield:** if a console user is present on a 12-slot run, the session touches STOP, waits for exit, keeps the never-started blocks in order (`leftover.py`, X4S2, unchanged), and relaunches them on 10 slots with the same stop-at.
3. **STOP session, one per host** (the coordinator's STOP, or after the code stop-at):
   1. touch STOP and wait for `supervisor-exit.json`;
   2. run a PID census of every receipt (supervisor PID + child PGID), which must be 0;
   3. rsync outputs, excluding repo/native/inputs/cache/bundle, to `127x05:/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013/<host>/` (fresh directory, no `--delete`);
   4. print `__RC`.

   **After this, no further contact with that host.**
4. **The coordinator's STOP** comes ≥ 3 h before the first K4S END host step on that host. A K4S-runner request triggers an immediate STOP.

**04 depends on 03.** The 04 copy reads 03's staged prefix, so 04 must launch while 03 is still in contact, before 03's
STOP session.

## Never touched
- K4S paths (`k4s-*`, `jobs-k4s`, `k4s-end-r1`), `t1-*`, and 03's T1 corpus copy. The X4S2 job's `corpus/` is not copied.
- 04 perception storage, and the G population and its decks (no G runs).
- Sealed outcomes of any study.

Writes happen only under the FSC prefixes and the 05 mirror directory.
