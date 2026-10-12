# PREREG-K4S run r1: OP-1 system-DBus flag disclosure (outcome-blind; coordinator DBus ruling R2)

- **Recorded:** 2026-10-12T14:46:15Z (`date -u`) on 127x05, before any reducer or verifier run.
- **Authority:** coordinator DBus ruling (COORDINATOR entry after 3f7240f9, commit 26d68687). Investigation `audits/K4S-DBUS-FLAG-INVESTIGATION-r1.md` (sha256 `cc1c56ff…`), retained verbatim.
- **Basis:** the final counted inventory `completion/counted-inventory.json` (sha256 `f10ab9433b6582299caeeb3055c4c7db494e3e99019e1cf8c8e0abc2fccbe38d`, 3,900 blocks). The recount is `completion/dbus-recount.json` (sha256 `79f3009f395cf39d1f058dab0e9aded831ed1c2326332c5c5e3cbcf9fb09fb3b`, by `tools/dbus_recount.py`).
- **Read boundary:** only the hub `interference.json` operational meters were read. No game file, `games/` directory, outcome field or contrast was opened.

## Counts per host and phase (counted blocks only)

| host | phase | counted | DBus-flagged | % | dbus-daemon core % p10 / p50 / p90 / max | SSH/apt/idle flags | pin retired |
|---|---|---|---|---|---|---|---|
| 127x03 | replacement-r1 | 1205 | 0 | 0.0 | 0.376 / 0.399 / 0.419 / 0.465 | 0/0/0 | 0 |
| 127x03 | replacement-r2 | 268 | 0 | 0.0 | 0.379 / 0.402 / 0.421 / 0.456 | 0/0/0 | 0 |
| 127x03 | replacement-r3 | 219 | 0 | 0.0 | 0.38 / 0.402 / 0.423 / 0.438 | 0/0/0 | 0 |
| 127x03 | replacement-r4 | 71 | 0 | 0.0 | 0.356 / 0.403 / 0.423 / 0.442 | 0/0/0 | 0 |
| 127x03 | reporting | 206 | 0 | 0.0 | 0.371 / 0.385 / 0.4 / 0.437 | 0/0/0 | 0 |
| 127x04 | replacement-r1 | 1194 | 1189 | 99.6 | 1.349 / 1.478 / 1.594 / 1.772 | 0/0/0 | 0 |
| 127x04 | replacement-r2 | 266 | 263 | 98.9 | 1.33 / 1.491 / 1.617 / 1.824 | 0/0/0 | 0 |
| 127x04 | replacement-r3 | 217 | 214 | 98.6 | 1.353 / 1.489 / 1.621 / 1.763 | 0/0/0 | 0 |
| 127x04 | replacement-r4 | 68 | 65 | 95.6 | 1.143 / 1.5 / 1.639 / 1.676 | 0/0/0 | 0 |
| 127x04 | reporting | 186 | 175 | 94.1 | 1.214 / 1.373 / 1.468 / 1.584 | 0/0/0 | 0 |

**Totals:**
- 127x04: **1906 of 1931 counted blocks flagged (98.7%)**, median 1.472% of one core.
- 127x03: **0 of 1969 (0.0%)**, median 0.398%.
- Across both hosts, SSH, apt and idle-service flags are **0** and pin retirements are **0**.
- The pinned daemon identity never changed: 04 PID 2005 (start ticks 1032), 03 PID 2049 (start ticks 1273).

## Cause

The cause is a constant host property of 127x04.
- **The level:** 04's system dbus-daemon runs at about **1.47%** of one core per block (03: about 0.40%). The OP-1 per-block threshold is 1%.
- **Probable source:** 04's resident GDM/GNOME greeter session (45 uid-125 processes, including Xorg and gnome-shell, present in every admission snapshot). 03 has none. Each copier SSH login adds broadcasts that those subscribers amplify.
- **Stability:** the level is flat across all rounds. The few unflagged 04 blocks fall in each phase's first wave.
- **Attribution is inferential.** There is no per-sender bus accounting.

## What the flag is in this study (R1)

- **Classification.** OP-1 DBus flags are **descriptive**. They are not a stop rule, not an exclusion and not part of the §5.3(2) sensitivity (OP-6/OP-7 only). The primary analysis includes these blocks (PREREG r3 §4.2 and §5.3; T1 OP-1).
- **The flag is effectively "host 127x04".** Every flagged block is a 04 block, and almost every 04 block is flagged. Any 04 effect is read in the prespecified §5.3(4) per-host contrasts and host×arm table, not through the flag.
- **`interference_any_flag_excluded` is a count only.** In the frozen reducer this field counts blocks whose `interference.interfered` is true. Here that is DBus only: **1459 primary and 447 guard**. **No block is excluded** by it.
- **§5.3(2) drops nothing.** The interference sensitivity excludes OP-6/OP-7 (SSH/apt) flagged blocks, and there are **0 primary and 0 guard** of those. So it is identical to the primary analysis, which is disclosed here as vacuous.
- **No DBus-exclusion analysis is added (R3).**
- **Monitoring (R5).** 04's DBus level is known, disclosed and constant. Future alerts fire only on a change in level or a pin retirement.

No frozen byte changes.
