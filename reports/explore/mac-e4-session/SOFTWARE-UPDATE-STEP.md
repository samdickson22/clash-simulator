# Mac session: software-update deferral step (Sol computer use) and caffeinate

Coordinator rulings (sent 2026-10-11 at 22:30:53Z, and the reply to the 22:35Z report):
- **Update step:** the coordinator routes one short GPT-6.1-Sol computer-use step before the TIERS session and one
  after it. The operator only reads the preferences, before and after, and records them. The operator never changes
  them itself.
- **caffeinate:** approved. The session runs under its own `caffeinate -i`.

## Baseline (operator read-only, 2026-10-11T22:30:58Z)

`/Library/Preferences/com.apple.SoftwareUpdate`:

| Key | Value |
| --- | --- |
| AutomaticDownload | 1 |
| AutomaticallyInstallMacOSUpdates | 1 |
| ConfigDataInstall | 1 |
| CriticalUpdateInstall | 1 |

- Automatic checking is on.
- RecommendedUpdates is macOS 27.0.1 (`MSU_UPDATE_26A434_patch_27.0.1_minor`), already staged
  (`com.apple.os.update-MSUPrepareUpdate` snapshot).
- There is no passwordless sudo, so the change has to be made in the GUI.

## Step 1: before the session (Sol computer use, Mac mini GUI)

1. Open **System Settings → General → Software Update → Automatic Updates** (the ⓘ next to it).
2. Turn **off** "Install macOS updates" and "Download new updates". Leave every other toggle as it is, and change
   nothing else.
3. Do **not** click "Update Now" or "Restart", and don't install anything.
4. Close System Settings and **quit every app this step opened**. Leave Sam's other apps and windows untouched,
   and don't touch the `simonfarshid` session.
5. **End the computer-use session.** Codex Computer Use must be idle for the whole run, because its own CPU and the
   WindowServer load it drives fail the quiescence census.

The operator then re-reads the preferences and expects `AutomaticallyInstallMacOSUpdates=0` and
`AutomaticDownload=0`. The census is the authority for whether the Mac is quiet.

## Step 2: after the session

1. Restore the two toggles to the baseline above, both ON.
2. The operator re-reads the preferences, confirms they equal the baseline, and records the before, during and
   after values in the session receipt.

## caffeinate

The session's locked launcher runs under `/usr/bin/caffeinate -i`. This is operational only and uses negligible CPU.
Sam's own `caffeinate -is` (PID 98902) stays untouched. The receipt records the caffeinate PID and arguments.

## Expected session length

About **6–6.5 h**, set by the P1 sealed-tick cadence.
- D7 default plus D8 freeze is about 24.3 min per tier pass, for up to 4 + 4 tier passes.
- D5 and D5b each take at least 5 min per tier.
- Also included: the 5-minute pre-session census, the build, and the 5-minute warm-up plus 3-minute capacity window.

The quiet window must cover the whole session.
