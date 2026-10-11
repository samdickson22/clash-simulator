# K4S seed audit receipt (PREREG-K4S-DRAFT-r3 §3.4; CONFORMANCE-r2 F-4)

- UTC: 2026-10-11T17:42:50Z
- Worktree HEAD: `fbcd677d3c51d9baf922243a3ad5ef5b460e4449`
- Result: **PASS**
- Tool: `reports/explore/k4s-confirm/audit_seeds.py` sha256 `93646e2f0241c797cf8f7d8520a53b7c356d154035471ed009c036e7cd1afffd`
- Seed-audit JSON: `reports/explore/k4s-confirm/seed-audit.json`

## Result counts

- Seven K4S ranges checked at 8 helper offsets against 279 unique prior intervals (204 declaration files walked at HEAD + named banks).
- Named banks found: 13/13 (named ranges 43).
- Literal scan: 20348 occurrences, 6563 distinct literals in 489 files.
- In-window occurrences: 54 — classes {'EXCLUDED_K4S_DECLARATION': 44, 'WINDOW_BOUND_TEXT': 10, 'FAIL': 0}.
- Violations: 0

## Named-bank table

| Name | Range | Base | Count | Stop (excl.) | Found in |
|---|---|---|---|---|---|
| K (k-anytime) | reporting | 4503601407370496 | 600 | 4503601407371096 | `HEAD:reports/explore/k-anytime/plan.json` |
| K (k-anytime) | smoke | 4503601417370496 | 8 | 4503601417370504 | `HEAD:reports/explore/k-anytime/plan.json` |
| K-v2 | reporting | 4503601807370496 | 600 | 4503601807371096 | `HEAD:reports/explore/k-v2/plan.json` |
| K-v2 | smoke | 4503601817370496 | 8 | 4503601817370504 | `HEAD:reports/explore/k-v2/plan.json` |
| K2 | reporting | 4503602307370496 | 600 | 4503602307371096 | `HEAD:reports/explore/k2/plan.json` |
| K2 | smoke | 4503602317370496 | 8 | 4503602317370504 | `HEAD:reports/explore/k2/plan.json` |
| S1 (both banks, plus smoke) | abandoned R1 reporting | 4503602607370496 | 600 | 4503602607371096 | `HEAD:reports/explore/s1/history/r1/plan.json` |
| S1 (both banks, plus smoke) | R2 reporting | 4503602707370496 | 600 | 4503602707371096 | `HEAD:reports/explore/s1/plan.json`, `HEAD:reports/explore/s1/FROZEN-R2.json` |
| S1 (both banks, plus smoke) | smoke | 4503602617370496 | 8 | 4503602617370504 | `HEAD:reports/explore/s1/plan.json` |
| R3 (imitation exit-r3) | reporting | 4503601907370496 | 600 | 4503601907371096 | `HEAD:reports/strategy_council_20260928/imitation/exit-r3/PLAN.md`, `HEAD:reports/explore/k2/receipts/R3-freeze-provenance.json` |
| R3 (imitation exit-r3) | smoke | 4503601917370496 | 8 | 4503601917370504 | `HEAD:reports/strategy_council_20260928/imitation/exit-r3/PLAN.md`, `HEAD:reports/explore/k2/receipts/R3-freeze-provenance.json` |
| R3 (imitation exit-r3) | regret replay | 4503601927370496 | 65536 | 4503601927436032 | `HEAD:reports/strategy_council_20260928/imitation/exit-r3/PLAN.md`, `HEAD:reports/explore/k2/receipts/R3-freeze-provenance.json` |
| R1/G | R1 round-2 full allocation | 4503599727370496 | 10000000 | 4503599737370496 | `HEAD:reports/strategy_council_20260928/imitation/exit-r1/PLAN.md` |
| R1/G | G full reservation | 4503601607370496 | 3000000 | 4503601610370496 | `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| R1/G | G 04 reservation | 4503601607370496 | 1000000 | 4503601608370496 | `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| R1/G | G 01 reservation | 4503601609370496 | 1000000 | 4503601610370496 | `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/HOST01-AMENDMENT.json` |
| R1/G | G 03 reservation | 4503601611370496 | 1000000 | 4503601612370496 | `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/HOST03-AMENDMENT.json` |
| X (X population) | h2h | 4503601507370496 | 256 | 4503601507370752 | `HEAD:reports/strategy_council_20260928/PLAN-NEXT-20261010.md`, `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| X (X population) | paired | 4503601517370496 | 600 | 4503601517371096 | `HEAD:reports/strategy_council_20260928/PLAN-NEXT-20261010.md`, `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| X (X population) | smoke | 4503601527370496 | 32 | 4503601527370528 | `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| X4S | reporting | 4503604807370496 | 600 | 4503604807371096 | `HEAD:reports/explore/x4s/plan.json` |
| X4S | smoke | 4503604817370496 | 8 | 4503604817370504 | `HEAD:reports/explore/x4s/plan.json` |
| X4S | qualification | 4503604827370496 | 8 | 4503604827370504 | `HEAD:reports/explore/x4s/plan.json` |
| X4S | reservation block | 4503604807370496 | 100000000 | 4503604907370496 | `HEAD:reports/explore/x4s/plan.json` |
| X4S-2 (incl. phases E/F) | G-reporting (phases B/D/F; E/F reuse G 0..1079) | 4503605107370496 | 1080 | 4503605107371576 | `HEAD:reports/explore/x4s2/plan.json`, `HEAD:reports/explore/x4s2/plan-ext.json` |
| X4S-2 (incl. phases E/F) | smoke | 4503605117370496 | 8 | 4503605117370504 | `HEAD:reports/explore/x4s2/plan.json`, `HEAD:reports/explore/x4s2/plan-ext.json` |
| X4S-2 (incl. phases E/F) | qualification | 4503605127370496 | 8 | 4503605127370504 | `HEAD:reports/explore/x4s2/plan.json`, `HEAD:reports/explore/x4s2/plan-ext.json` |
| X4S-2 (incl. phases E/F) | X-reporting paired reuse of X4S (phases A/C/E) | 4503604807370496 | 600 | 4503604807371096 | `HEAD:reports/explore/x4s2/plan.json`, `HEAD:reports/explore/x4s2/plan-ext.json` |
| X4S-2 (incl. phases E/F) | fresh reservation block | 4503605107370496 | 100000000 | 4503605207370496 | `HEAD:reports/explore/x4s2/plan.json`, `HEAD:reports/explore/x4s2/plan-ext.json` |
| T1 (all banks) | primary | 4503603107370496 | 2400 | 4503603107372896 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | primary replacements | 4503603107372896 | 480 | 4503603107373376 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | guard | 4503603207370496 | 600 | 4503603207371096 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | guard replacements | 4503603207371096 | 120 | 4503603207371216 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | smoke | 4503603307370496 | 8 | 4503603307370504 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | corpus | 4503603407370496 | 64 | 4503603407370560 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| T1 (all banks) | descriptive | 4503603507370496 | 72 | 4503603507370568 | `HEAD:reports/explore/t1/plan.json`, `main:reports/explore/t1/plan.json`, `ef4c073a:reports/explore/t1/plan.json` |
| DAgger | open-ended; bounded below window start | 4503601707370496 | 3792629504 | 4503605500000000 | `HEAD:reports/strategy_council_20260928/PLAN-NEXT-20261010.md`, `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json` |
| noise-ceiling | entire replay reservation | 4503609917370496 | 262144 | 4503609917632640 | `HEAD:reports/strategy_council_20260928/imitation/exit-r2/ANALYSIS-NOISE-CEILING-20261010.md`, `HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/receipts/utilization08-seed-audit.json` |
| L2-v4 (10-digit spans, not 2^52) | confirmatory worlds 1976300001+1009i, i<216 | 1976300001 | 216936 | 1976516937 | `HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md` |
| L2-v4 (10-digit spans, not 2^52) | P4 re-test 1976100001+101k, k<704 | 1976100001 | 71004 | 1976171005 | `HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md` |
| L2-v4 (10-digit spans, not 2^52) | integration smoke 1976200001+101k, k<32 | 1976200001 | 3132 | 1976203133 | `HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md` |
| L2-v4 (10-digit spans, not 2^52) | simulator prediction worlds 9783000001+1009i, i<216 | 9783000001 | 216936 | 9783216937 | `HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md` |
| L2-v4 (10-digit spans, not 2^52) | simulator prediction sensors 9883000001+1009i, i<216 | 9883000001 | 216936 | 9883216937 | `HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md` |

## Proposed K4S ranges (from plan.json, unchanged)

| Range | Base | Count | Stop (excl.) |
|---|---|---|---|
| primary | 4503605807370496 | 3000 | 4503605807373496 |
| primary_replacements | 4503605807373496 | 600 | 4503605807374096 |
| guard | 4503605817370496 | 900 | 4503605817371396 |
| guard_replacements | 4503605817371396 | 180 | 4503605817371576 |
| smoke | 4503605827370496 | 8 | 4503605827370504 |
| qualification | 4503605837370496 | 8 | 4503605837370504 |
| reserve | 4503605847370496 | 64 | 4503605847370560 |

## Literal scan summary

- Pattern `45036[0-9]{11}`, scope git grep -I at HEAD (tracked text files, all paths except the tool's own two outputs); tracked files 10467, text files with content 10407.
- Windows: task `[4503605500000000, 4503606999999999]` inclusive; F-4 `2^52+[5.87e9, 7.37e9)` = `[4503605497370496, 4503606997370496)`.
- Nearest out-of-window literal below: `4503605207370496`; above: `4503609917370496`.
- In-window hits (file:line, class):

  - `4503605807370496` `reports/explore/k4s-confirm/K4S-SPEC.md:56` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/explore/k4s-confirm/K4S-SPEC.md:57` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/explore/k4s-confirm/K4S-SPEC.md:58` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/explore/k4s-confirm/K4S-SPEC.md:59` — EXCLUDED_K4S_DECLARATION
  - `4503605827370496` `reports/explore/k4s-confirm/K4S-SPEC.md:60` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/explore/k4s-confirm/K4S-SPEC.md:61` — EXCLUDED_K4S_DECLARATION
  - `4503605847370496` `reports/explore/k4s-confirm/K4S-SPEC.md:62` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/explore/k4s-confirm/QUALIFICATION.md:63` — EXCLUDED_K4S_DECLARATION
  - `4503605500000000` `reports/explore/k4s-confirm/audit_seeds.py:21` — WINDOW_BOUND_TEXT
  - `4503606999999999` `reports/explore/k4s-confirm/audit_seeds.py:21` — WINDOW_BOUND_TEXT
  - `4503605500000000` `reports/explore/k4s-confirm/audit_seeds.py:253` — WINDOW_BOUND_TEXT
  - `4503606999999999` `reports/explore/k4s-confirm/audit_seeds.py:253` — WINDOW_BOUND_TEXT
  - `4503605837370496` `reports/explore/k4s-confirm/check_games.py:46` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/explore/k4s-confirm/plan.json:184` — EXCLUDED_K4S_DECLARATION
  - `4503605807373496` `reports/explore/k4s-confirm/plan.json:188` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/explore/k4s-confirm/plan.json:192` — EXCLUDED_K4S_DECLARATION
  - `4503605817371396` `reports/explore/k4s-confirm/plan.json:196` — EXCLUDED_K4S_DECLARATION
  - `4503605827370496` `reports/explore/k4s-confirm/plan.json:200` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/explore/k4s-confirm/plan.json:204` — EXCLUDED_K4S_DECLARATION
  - `4503605847370496` `reports/explore/k4s-confirm/plan.json:208` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/explore/k4s-confirm/qual_tasks.py:8` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/explore/k4s-confirm/qualify_games.py:84` — EXCLUDED_K4S_DECLARATION
  - `4503605807370497` `reports/explore/k4s-confirm/test_reduce.py:105` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/explore/k4s-confirm/verifier/VERIFIER-NOTES.md:129` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/explore/k4s-confirm/verifier/VERIFIER-NOTES.md:130` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/explore/k4s-confirm/verifier/verify_k4s.py:55` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/explore/k4s-confirm/verifier/verify_k4s.py:56` — EXCLUDED_K4S_DECLARATION
  - `4503605500000000` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:327` — WINDOW_BOUND_TEXT
  - `4503606999999999` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:327` — WINDOW_BOUND_TEXT
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:331` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:332` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:333` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:334` — EXCLUDED_K4S_DECLARATION
  - `4503605827370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:335` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:336` — EXCLUDED_K4S_DECLARATION
  - `4503605847370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md:337` — EXCLUDED_K4S_DECLARATION
  - `4503605500000000` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:408` — WINDOW_BOUND_TEXT
  - `4503606999999999` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:408` — WINDOW_BOUND_TEXT
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:412` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:413` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:414` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:415` — EXCLUDED_K4S_DECLARATION
  - `4503605827370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:416` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:417` — EXCLUDED_K4S_DECLARATION
  - `4503605847370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r2.md:418` — EXCLUDED_K4S_DECLARATION
  - `4503605500000000` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:444` — WINDOW_BOUND_TEXT
  - `4503606999999999` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:444` — WINDOW_BOUND_TEXT
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:448` — EXCLUDED_K4S_DECLARATION
  - `4503605807370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:449` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:450` — EXCLUDED_K4S_DECLARATION
  - `4503605817370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:451` — EXCLUDED_K4S_DECLARATION
  - `4503605827370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:452` — EXCLUDED_K4S_DECLARATION
  - `4503605837370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:453` — EXCLUDED_K4S_DECLARATION
  - `4503605847370496` `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md:454` — EXCLUDED_K4S_DECLARATION

In K4S docs, a literal from a K4S range base through its last seed plus the largest helper offset (inclusive) is a K4S declaration; window-bound text is the inclusive task bound pair (PREREG-K4S-DRAFT r1/r2/r3 §3.4 prose) or either F-4 bound. Neither is a foreign seed; both are disclosed, not counted as FAIL.

## Re-run

From the worktree root at the freeze commit (system Python 3.8 stdlib; no venv exists at the path given in the task):

```
nice -n 19 /bin/python3 reports/explore/k4s-confirm/audit_seeds.py
sha256sum reports/explore/k4s-confirm/seed-audit.json reports/explore/k4s-confirm/audit_seeds.py
```

