# Decision memo for Sam: how much search the Mac can run live (2026-10-10, r2)

From the research planner (Opus) via coordinator `0523ae6f`. This is a draft; nothing has been launched. r2 applies
the independent review's conditions (`live-loop/v4/REVIEW-PREREG-SEARCH-TIERS-20261010.md`, C1–C14; map in
`live-loop/v4/C1-C14-RESPONSE.md`).

## What we learned today

We tested on the lab fleet how strong the bot is at different amounts of CPU. Each result below comes from 600
fresh games against the plain v1 policy, with the bot **charged honestly for being late**.

| Setup | CPU | Loss rate |
|---|---|---:|
| Search on 4 threads (K4) | 5 cores | **16–19%** |
| Search on 2 threads (K2) | 3 cores | 25–29% |
| 1 core + small distilled "student" model (R3a) guiding the search (S) | 1 core | **28%** |
| 1 core, plain search (K0) | 1 core | 44–48% |

What this means:
- **More cores help a lot.** Four threads cut losses by about two-thirds against one core.
- **The student is the surprise.** On one core it came **within the 5-point margin of two-thread search in one
  exploratory study** (28% vs 29%). That is one study, not a confirmed result.
- **It holds up when slowed.** At a simulated 20% slower CPU, the student tier only rises to 32%, while plain
  one-core search collapses to 79%.
- **There is a speed cliff.** Search needs at least about 80% of a lab core's speed per core. At 60% it falls apart.
- **The student's past "kill", stated plainly.** An earlier study (R3) killed this exact student file on narrow
  imitation-score misses and labelled it "never adoptable, regardless of benefit". After later game results looked
  good, we propose to **override that label for this one file only**, openly and on the record: it keeps its name
  (R3a), R3's files are not edited, and it must pass a new, stricter, pre-registered game test on fresh games. The
  earlier exploratory results are used only to size the study, never as evidence. The student also trained on the
  same decks and the same v1 opponent the tests use, which favours it; we say so in the report.

Everything above is simulation on Linux. None of it tells us what the Mac can actually sustain while it is also
running perception (and the emulator).

## What we propose

1. **A fleet confirmatory study** (pre-registered, independently reviewed). It plays all four setups at full and
   at 80% speed, on 2,400 fresh games each, plus 600 games in which our L2 decks face **three common human decks
   the student never trained against**. That guard checks two things: that each setup still beats the control, and
   that a cheaper setup is not more than 10 points worse than a costlier one on those unseen opponent decks. It runs
   on four lab machines (127x01, 03, 04, 08; 02 and 07 are down), takes about 7 hours, and needs nothing from you.
   **Its results stay sealed until the Mac numbers are committed**, so the Mac numbers cannot be nudged by the
   game results.
2. **One Mac measurement session**, which needs your authorisation. It replays recorded training matches through
   perception, the same way as the existing package. While that runs, it times each search setup on a fixed batch
   of **complete decisions** (including the belief and Python work, not just the search core), against lab times
   measured under full load on every lab machine. It measures:
   - **how many cores are really free** while perception runs, split by performance and efficiency cores;
   - **each setup's speed relative to a loaded lab core**, judged by the slow tail as well as the middle, and whether
     perception still keeps 18+ FPS while the setup runs;
   - **a direct check at the real 200 ms deadline**: the Mac must cut off no more often than the lab did;
   - **pauses from Python garbage collection** that could delay a move, with timestamps against move deadlines;
   - **the student model's cost on Apple silicon**, CPU vs MPS (GPU), and that it makes the same choices as on
     Linux;
   - that the **arm64 build** gives the same scores, belief samples and random numbers as Linux. Any mismatch in the
     shared search code rules out **every** setup.
3. **A fixed rule picks the setup.** It takes the cheapest setup the Mac can run that is **shown, with 97.5%
   confidence, to be no more than 5 points worse than every costlier setup the Mac can also run**. The rule is
   written down before any Mac numbers exist.
   **My expectation:** K4 is unlikely to fit next to perception on a 12-core M4 Pro, so the likely pick is the
   1-core student. **But if the Mac runs K4 at 80–100% of lab speed, K4 is the likely pick**: at that speed K4 has
   lost about 27% against the student's 32%, more than 5 points apart. If nothing qualifies, live play keeps
   today's configuration (whose own Mac fit is unmeasured).
4. **The Mac answer is provisional.** This session has no emulator running, so it overstates the spare CPU. The
   pick only becomes usable after the later formal emulator-on test re-measures everything on the same positions,
   with the worse value winning.

## Time and cost

- **Mac:** about 2–2.5 hours on its own. If it runs together with the already-prepared E4 package, about 3–3.5
  hours. Your part is about 15 minutes of staging: recordings, model files and the Python environment. No other
  agent may use the Mac during the session.
- **Fleet:** about **1,500 reserved core-hours** (about 400–450 actually used), about 7 hours on four lab
  machines, or about 9.5 hours if one drops out. Lost machines are handled by a pre-set replacement list of games;
  if more than 10% need replacing, we stop and amend before looking at results.

## Risks

- **Account and game:** none. The session is replay only: no taps, no login, no client, no ladder, no emulator
  control (we only read the process list). The live-play rules (throwaway account, no detection evasion, fair
  information) apply later, unchanged.
- **Mac machine:** heavy CPU use for 2–3.5 hours at low priority (nice 10). It might throttle when hot; we
  record that. Everything goes in fresh folders, and the live installation is untouched.
- **Waiting on the Mac holds the fleet results.** If the session is not authorised within 14 days of the fleet
  finishing, the results open anyway, and any later Mac repeat needs an independent check first.
- **The perception load could be the older one.** The v4 perception selection is still blocked on an
  owner-supplied launcher. In that case the session uses the older v3 perception as the load and is labelled
  provisional-load.
- **Simulation vs live gap:** the simulator has perfect vision, and the opponent is the v1 bot, not humans. The
  chosen setup also changes live search from 4 belief samples to 1, which is what all of today's evidence used.
  That needs an L2-v4 amendment and live tests before any ladder play.
- **If the lab baseline drifts** (plain one-core search outside 36–54% loss), selection pauses for an independent
  code review: a harness defect voids the study and restarts it with new games; no defect lets it proceed unchanged.

## What we need from you

**Authorise one replay-only Mac measurement session** (addendum r2, plus the existing E4 package if its
prerequisites are ready), ideally while the fleet study runs. Nothing else is needed from you for the fleet study.
