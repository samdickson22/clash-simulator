# PREREG-K4S run r1: stop-cause disclosure (root host maintenance via ssh-login motd hooks)

Coordinator ruling 2026-10-11T21:39Z (COORDINATOR.md 11105b3f): accept and disclose. Same class as T1's OP-7 apt finding.

- **Event 1, 127x04, 2026-10-11T21:32:49Z, `foreign_compute`.**
  - The frozen census found PID 4158117 (root, parent 1): `/usr/bin/python3 /usr/lib/ubuntu-release-upgrader/check-new-release -q`.
  - The frozen supervisor SIGTERMed its 11 in-flight blocks (8 primary, 3 guard); they are lost. It did not latch the stop: once the process had exited, it resumed and launched 11 new blocks at 21:32:51Z.
  - `stop-reason.json` is preserved in the 04 reporting job.
- **Mechanism.** sshd's `pam_motd` (session, `motd=/run/motd.dynamic`) runs `/etc/update-motd.d/*` as root on every ssh session.
  - `91-release-upgrade` → `release-upgrade-motd` re-runs `check-new-release`, a Python process, whenever the stamp `/var/lib/ubuntu-release-upgrader/release-upgrade-available` is more than a day old. On 04 the stamp was rewritten at 21:32:48Z.
  - `90-updates-available` can likewise run the Python `apt-check` after apt list refreshes.
  - The trigger is our own LAN ssh logins: the OA-1 copier logs in about every 10 s, and the health checks log in every 5 min. Neither the cause nor the remedy (root timers and pam configuration) is under our control, since we have no root.
- **Forecast.** 127x03's stamp dates from 2026-10-11T00:57:43Z, so a similar stop is expected at the first ssh login after about 2026-10-12T00:58Z. Per the ruling: no copier change mid-run, and no pre-triggering.
- **Disposition.** Lost blocks are replaced after reporting by the frozen blind ledger, which preserves cell and seed (r3 §3.4/§4.4). Escalate if stops recur more than once per host per day, if cumulative lost blocks approach 10% of a replacement cap (30 primary / 9 guard), or if the supervisor fails to continue.
- **Outcomes** remain SEALED; this note uses only health and process metadata.
