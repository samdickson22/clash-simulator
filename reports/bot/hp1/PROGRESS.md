# HP1 (human-init full-pool policy): PROGRESS (resume here)

Owner: HP1 owner (Opus), for the BOT LEAD. Design: `DESIGN.md` (main 1a6983396). S0 pre-registration: `S0-PREREG.md`
(main 6a6708a14, registered 2026-10-17 22:57:26Z, 0 games at registration).

**STANDING RULE (Sam, via BOT LEAD, 2026-10-17): always steer, never queue.**
- Every `t3_thread_send` uses `mode: "steer"`.
- If it returns `thread_not_sendable`, resend the same text with `mode: "auto"`.
- Never `queue`. Copy this rule into every helper brief.

**STANDING RULE (Sam, via BOT LEAD, 2026-10-17): say less.** No acks or "started/queued" messages. Report only results,
failures and decisions; routine status goes here in PROGRESS.md.

## BOT LEAD decisions (2026-10-17 ~22:52Z)

1. **S0 GO (CPU):**
   - Priority: below deckopt3, LVG2 and LV2; alongside NS2; above PT1, HZ1 and K1.
   - Hosts: 04/08 within caps (04 ≤ 70 while the lab user is on). ≤ 16 workers, via `cpu_job`.
2. **P1:** write the trainer with the lag shift and get a Sol review. Then tell the BOT LEAD it is OK-to-run; they
   arrange the GPU window with the LIVE LEAD. **Never take a GPU yourself.**
3. **PT2:** the BOT LEAD tells the cycle-model owner to use v2 as π.

## S0 state

- **Job:** `04:/mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017/`.
  - `source/` = git archive of 1e933ddc3. `models/` holds v2 (`87794378…`) and f1a2 (`0c03f79f…`), read-only,
    sha-checked.
  - `provenance-models.txt` has the main02-fp `69313468…`, R3a-fp `ce7b0ea4…` and rl5 `e188e2ae…` hashes.
  - `env.sh`, `run.sh` and `STAGE.md` define the launch form and run sequence.
  - The validator `s0_validate.py` stays on 05 (`/tmp/sdicks02-hp1-work/s0/`, copied into `reports/bot/hp1/s0/`).
- **Sol review:** r1/r2/r3 findings all fixed (r3: plays must be nonnegative integers); package cleared 23:15Z.
- **Runs:** smoke launched 23:15:56Z (PGID 2649177, cpu_job lease 7, waiting for room on 04). Sequence: smoke → cal-t (f1a2 target) → cal-0.. (v2 τ) ∥ ef (f1a2, v1 arms) → h (v2@τ*).
  Validate each with `s0_validate.py` before proceeding.

## P1 state

- **Code:** `/tmp/sdicks02-hp1-work/p1/imitation/hp1/{lagshift.py,train.py,test_lagshift.py,README.md}`. 10/10
  unit tests pass locally. Not committed yet; it goes to main after the review.
- **Sol review:** r1 CHANGES-NEEDED (fresh-run blocker, channel occupancy, T4 qualification, mask hash, tests);
  all fixed, 18 tests pass. r2 pending.
- **Before the GPU window:**
  - build the overlay on 04 (CPU, minutes);
  - run the CPU smoke of both arms (`--device cpu --max-steps 2 --smoke`);
  - then the BOT LEAD arranges the GPU, starting with a GPU smoke of 20 steps.
- **Inputs:** 04 `~/repos/clasher-t11-home-v1/inputs/{assets.npz,T11-STORE-PASS.json}`. The store is on 04 and 08.

## Facts to keep

- v2 config is identical to v1: 2,254,949 parameters. rl5/f1a2 = 6L/FFN 1536, 4,918,757.
- v2 epoch-1 dev EMA joint NLL is 0.28237 (seed 22, step 7744); final 0.26592.
- Lag legality at shift 25/30 ticks: 93.9% / 90.5% of C56 train plays.
- 04 GPU: shared. 08 GPU: lent to YOLO.
