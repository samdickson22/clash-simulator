# DRAFT: role-scoped SD1 supersession of R3's never-adoptable label (for the coordinator to issue)

**Status: DRAFT. Not issued.**
- Only coordinator `0523ae6f` issues this, at the PREREG-K4S freeze, under the owner's delegation.
- The prep worker drafted it on 2026-10-11 and issues nothing.
- Nothing in `reports/strategy_council_20260928/imitation/exit-r3/` is edited.

Text source: PREREG-K4S r3 §2.1 (sha256 `9650972d…`), "Status and supersession", with the CONFORMANCE-r2 M5 wording.

---

## Text to issue (verbatim from r3 §2.1)

> This PREREG, issued by coordinator `0523ae6f` under the owner's delegation, supersedes R3's 'ALWAYS
> NEVER-ADOPTABLE … regardless of its paired benefit' clause
> (`reports/strategy_council_20260928/imitation/exit-r3/RESULTS.md` l.85, 97, 125) **for these exact bytes in the
> K4S S-default role defined by §2.3 only (all three uses: the seat poll, the coarse ordering and the cutoff
> default)**.

## Binding (fill at the freeze)

| Item | Value |
|---|---|
| Artifact | `SD1`, `clasher-sd1-k4s-default-20261011` |
| SD1 hash (sha256 of `reports/explore/k4s-confirm/SD1-MANIFEST.json` at the freeze commit) | `________________` (prep value at 2026-10-11, pre-review: see FREEZE-RECORD-SKELETON) |
| EMA checkpoint | `37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85` |
| Calibration | `e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414` |
| Threshold | 0.5005528330802917 |
| Superseded clause | `exit-r3/RESULTS.md` sha256 `646db0a6b77ce89d42dda26fbb77d2349bf185e8c065d90557c8a9ce3576b146`, l.85 ("R3a descriptive is ALWAYS NEVER-ADOPTABLE"), l.97 ("R3a descriptive remains ineligible regardless of its paired benefit"), l.125 ("R3a descriptive — NEVER ADOPTABLE") |
| Freeze commit / issuing UTC | `________________` / `________________` |

## Scope limits (part of the issued text; r3 §2.1)

- **R3a remains KILLED** under R3 Stage 1. R3's files are not edited.
- **Outcome-informed.** The supersession follows X4S and X4S-2 (and, for tier S, r1(b) and S1), and the final
  report says so.
- **Claims attach only to SD1 in this role.** They never attach to the R3 recipe or to tier S.
- **TIERS §2.1's separate tier-S supersession** is unaffected.
- **No live play is authorised** by this supersession or by PREREG-K4S. Activation needs the TIERS D2 one-root
  L2-v4 amendment, formal E4/T9 and the coordinator's review (r3 §1.5).
- **The three uses** are covered only as frozen in r3 §2.3 and `reports/explore/k4s-confirm/sdefault.py` /
  `run.py`:
  1. seat poll (one cached forward per poll; WAIT below threshold or with no legal play);
  2. coarse-scan order (SD1 top-8 legal plays first; the candidate set is unchanged);
  3. cutoff default (the SD1 play only when no legal play has a complete score; an SD1 WAIT keeps the frozen
     choice).

---

# DRAFT: additive pointer for `reports/strategy_council_20260928/imitation/exit-r3/`

**Draft only.** The prep worker does not write into exit-r3. At the freeze, the coordinator may add it as a new
file, for example `exit-r3/POINTER-SD1-K4S.md`, leaving every existing exit-r3 file byte-identical.

```markdown
# Pointer: R3a bytes re-frozen as SD1 for PREREG-K4S (additive; no R3 file is edited)

- The exact R3a final-EMA bytes (checkpoint sha256 37509a43…, calibration e3003533…, threshold 0.5005528330802917)
  are re-frozen as artifact SD1 (`clasher-sd1-k4s-default-20261011`) for PREREG-K4S
  (`reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md`, frozen at <freeze commit>).
- Manifest: `reports/explore/k4s-confirm/SD1-MANIFEST.json` (SD1 hash <sha256>).
- Coordinator 0523ae6f issued a role-scoped supersession of RESULTS.md l.85/97/125 for these exact bytes in the
  K4S S-default role only (seat poll, coarse ordering, cutoff default); see <freeze record path>.
- R3a remains KILLED under R3 Stage 1. Claims never attach to the R3 recipe or to tier S. The supersession is
  outcome-informed (X4S, X4S-2).
```
