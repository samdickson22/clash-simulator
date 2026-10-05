# Resume search-noise

This directory owns the perception-noise experiment. The active runtime is frozen in evaluation-manifest.json, SHA-256 b4ec3f8d6ab47949f1db88bdda9a44bfdfe18f93602f75fc55b966c9aa1bf7eb. Do not change a pinned file or remove a receipt.

First inspect PROGRESS.md, launcher-children.json, workerN-current.json and the reported process IDs. The original supervisor PID was 88788; workers were 88791, 88792 and 88793. Verify current command lines before treating a PID as owned. Do not signal extraction, Stage 6, emulators, watchdog, caffeinate or any unrelated process.

If the original supervisor and workers are running, leave them running. Status is available without reading strength outcomes:

```sh
cd /Users/sam/Desktop/code/clasher
.venv/bin/python -B reports/strategy_council_20260928/search-noise/status.py
```

Only if the previous supervisor and workers have exited, launch a resume with a fresh log filename:

```sh
cd /Users/sam/Desktop/code/clasher
reports/strategy_council_20260928/pilot/detach.sh \
  reports/strategy_council_20260928/search-noise/launcher-resume-UNIQUE.log \
  bash reports/strategy_council_20260928/search-noise/launch.sh
```

Replace UNIQUE with a fresh timestamp or attempt number. The helper truncates its specified log, so do not reuse an existing log filename. Exclusive locks prevent duplicate owned supervisors/workers. A live orphaned worker should be allowed to finish before relaunching; do not start a fourth heavy process. Workers skip only terminal receipts carrying the exact manifest hash. Preserve failed attempts and their logs. Diagnose failures without changing the registration based on outcomes.

The schedule has 1,664 terminal games: four variants each with 128 games versus A and 128 versus scripts, plus five source-repair ablations with 128 script games each. The model and statistical analysis are in PREREG.md. No interim strength scores have been inspected. The three-worker supervisor writes worker exits and runs analyze.py when all workers finish successfully. The final analyzer requires all receipts, source pins and clean exits. It writes RESULTS.md, result.json, FINAL.txt and completion.json.

Before reporting completion, verify 1,664 receipts, completion.json, all worker exits and launcher.exit equal to zero, unchanged manifest files, outputs below 300 MB, and no active owned worker. Read RESULTS.md and FINAL.txt, check the uncertainty and modelling limits, then return the requested plain-text final report of no more than 200 words. A placeholder RESULTS.md or a progress count is not completion evidence.

Preparation passed five boundary tests, a 50,000-event-per-condition rate check, nine terminal development games, seven-family smoke coverage, and a final terminal smoke verifying 0.66099 all-truth HP coverage and 0.04977 readable-bar MAE. Seed audit scanned 918,159 seed fields and 3,946 NPZ archives. A pre-confirmation amendment restored unknown event placements and corrected the HP coverage denominator. No confirmation outcomes informed these changes.

Restart incident 20261005T073001Z: verified 991 receipts and all 456 source hashes. See INCIDENT-20261005T073001Z.md and resume-audit-20261005T073001Z.json.
