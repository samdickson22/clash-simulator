# K4S run r1: reducer and verifier in sealed mode (PREREG-K4S §4.5)

- **Recorded:** 2026-10-12T14:48:09Z (`date -u`).
- **Authority:** coordinator DBus ruling R1/R2. The R2 disclosure was committed in bb7c7f88 before these runs. "Sealed mode only; anything outcome-reading needs GO."
- **Frozen code at 391d2006:**
  - `reduce.py` 9c2e5ac0…
  - `verifier/verify_k4s.py` 43c4a574…
  - `barrier.py` 01a58c66…
- **Sealed, per PREREG §4.5:** no outcome field is read before release, and the reducer fails closed before it opens any game bytes. Both tools were run on the final counted view (`final-view/`, 3,900 symlinks to the hub copies) **without `--release`**.
- **Guard:** `sealed_guard.py` (sha256 `f9c6f943e458f165…`) runs each frozen tool unchanged via runpy, with a Python audit hook. The hook logs every open/listdir/scandir and **raises** on any path under `/final-view`, `/hub-blocks/` or `/games`.
  - **Why not strace:** `strace` was unusable. Attempt 1 failed because `openat2` isn't known to this strace. Attempt 2 failed because ptrace is not permitted. Neither attempt ran the tools. Their records are kept as `attempt1-*` and `attempt2-*`.

| tool | exit | result | block/game/hub accesses | output written |
|---|---|---|---|---|
| reduce.py | 1 | **fails closed in `barrier.outcome_release`** (barrier.py:23 `read(None)` → TypeError), called at reduce.py:310 **before `load_blocks`** (l.311). The ledger was not read either. | **0**; guard BLOCKED 0 | none (no `reducer-out.json`) |
| verify_k4s.py | 2 | **REFUSED: "no release receipt: refusing to open any game file"** | **0**; guard BLOCKED 0 | `verifier-out.json` = the refusal only |

**Files outside the interpreter that either tool opened:** `plan.json` (reducer), the verifier's own out file, and two directory listings (its script directory and `sealed/`). The logs are `reducer-opens.log` and `verifier-opens.log`.

No outcome was computed, printed or committed. Outcome release, K4S END and the Mac steps each need the coordinator's explicit GO.
