# Decision memo for Sam: how much search the Mac can run live (2026-10-10)

From the research planner (Opus) via coordinator `0523ae6f`. This is a draft; nothing has been launched.

## What we learned today

We tested on the lab fleet how strong the bot is at different amounts of CPU. Each result below comes from 600
fresh games against the plain v1 policy, with the bot **charged honestly for being late**.

| Setup | CPU | Loss rate |
|---|---|---:|
| Search on 4 threads (K4) | 5 cores | **16–19%** |
| Search on 2 threads (K2) | 3 cores | 25–29% |
| 1 core + small distilled "student" model guiding the search (S) | 1 core | **28%** |
| 1 core, plain search (K0) | 1 core | 44–48% |

What this means:
- **More cores help a lot.** Four threads cut losses by about two-thirds against one core.
- **The student is the surprise.** On one core it matches two-thread search: 28% vs 29%, a statistical tie.
- **It holds up when slowed.** At a simulated 20% slower CPU, the student tier only rises to 32%, while plain
  one-core search collapses to 79%.
- **There is a speed cliff.** Search needs at least about 80% of a lab core's speed per core. At 60% it falls apart.
- **One caveat about the student.** It was formally "killed" in an earlier study, by narrow misses on imitation
  scores. We propose to re-test **the same file** under a new, stricter, game-outcome test on fresh games, not to
  quietly adopt it.

Everything above is simulation on Linux. None of it tells us what the Mac can actually sustain while it is also
running perception (and the emulator).

## What we propose

1. **A fleet confirmatory study** (pre-registered, independently reviewed). It plays all four setups at full and
   at 80% speed, on 2,400 fresh games each, plus 600 on the live L2 decks. That checks that the student isn't
   tuned to its training decks. It takes about 4–6 hours on idle lab machines and needs nothing from you.
2. **One Mac measurement session**, which needs your authorisation. It replays recorded training matches through
   perception, the same way as the existing package. While that runs, it times each search setup on a fixed batch
   of positions whose fleet times we already know. It measures:
   - **how many cores are really free** while perception runs, split by performance and efficiency cores;
   - **each setup's speed relative to a lab core** under that load, and whether perception still keeps 18+ FPS
     while the setup runs;
   - **pauses from Python garbage collection** that could delay a move, with timestamps against move deadlines;
   - **the student model's cost on Apple silicon**, CPU vs MPS (GPU), and that it makes the same choices as on
     Linux;
   - that the **arm64 search build** gives exactly the same scores as Linux.
3. **A fixed rule picks the setup.** It takes the strongest setup the Mac can actually run, but steps down to a
   cheaper one when the cheaper one is within 5 points. The rule is written down before any Mac numbers exist.
   **My expectation:** K4 is unlikely to fit next to perception on a 12-core M4 Pro, so the likely pick is the
   1-core student. If nothing qualifies, live play keeps today's configuration.

## Time and cost

- **Mac:** about 1.5–2 hours on its own. If it runs together with the already-prepared E4 package, about
  2.5–3 hours. Your part is about 15 minutes of staging: recordings, model files and the Python environment.
- **Fleet:** about 500 core-hours on lab machines that are otherwise idle.

## Risks

- **Account and game:** none. The session is replay only: no taps, no login, no client, no ladder, no emulator
  control. The live-play rules (throwaway account, no detection evasion, fair information) apply later, unchanged.
- **Mac machine:** heavy CPU use for about 2 hours at low priority (nice 10). It might throttle when hot; we
  record that. Everything goes in fresh folders, and the live installation is untouched.
- **The result could be provisional.** The v4 perception selection is still blocked on an owner-supplied
  launcher. In that case the session uses the older v3 perception as the load, and the answer must be
  re-confirmed in the later formal emulator-on test, where the lower speed wins.
- **Simulation vs live gap:** the simulator has perfect vision. The chosen setup also changes live search from 4
  belief samples to 1, which is what all of today's evidence used. Both need the existing L2-v4 amendment and
  live tests before any ladder play.
- **The student's past "kill"** is handled openly: same file, new pre-registered test, and its old record stays
  as it is.

## What we need from you

**Authorise one replay-only Mac measurement session** (this addendum, plus the existing E4 package if its
prerequisites are ready). Nothing else is needed from you for the fleet study.
