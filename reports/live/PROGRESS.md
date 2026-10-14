# LIVE LEAD progress (exploration tier)

- **Mandate:** Sam, 2026-10-14. Official client, throwaway account, emulator on the Mac mini only. Training Camp, then
  ladder. No detection evasion.
- **Coordinator:** thread 0523ae6f.
- **Task:** clasher-live-lead-20261014-r1.
- **Plan:** `reports/live/PLAN.md`.

## Layout

- **Mac live dir:** `~/clasher-live/`, not created yet.
  - Never touch: `~/Desktop/code/clasher*`, `~/.cache/clasher-native-reference` (reference AVD, never networked),
    `~/.cache/clasher-official` (L3 history), `~/.cache/clasher-live-v4`, the t1-* paths, or the E4 trees.
- **Mac ssh:** `ssh macmini-fleet` always exits 0, so wrap every command with `printf '__RC=%s' $?` and treat a
  missing token as failure.
- **Hosts:** 05 orchestrates only. GPU comes from the bot track on request.

## Done

- **2026-10-14T22:51Z, step 1 (PLAN) written.** Main findings:
  - The official client aborts at startup on stock AVDs: `frrh.aC: 02` from its anti-emulator check. That route is
    closed (no evasion).
  - The Mac has 9.7 GB free disk, and a Win11 VM holds 16 of its 24 GB RAM.
  - Perception has no accepted accuracy.
  - The bot needs glue: a deadline, an adapter, Mac pins.
  - Both engines support only C56 cards at level 11.

## Running

- Nothing.

## Next

1. **Coordinator:** ask for an A6000 (prefer 01, where the v4 caches are) and send Sam the list in PLAN section 4.
2. **Step B (in parallel):** v4 exploration fine-tune on train, measured on val.
3. **Step A:** after Sam frees disk and RAM, retry BlueStacks Air with default settings. Sol review before any Mac
   script runs.
