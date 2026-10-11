# Independent check: PREREG-K4S freeze record vs coordinator decisions (round 1)

- Reviewer: Claude Opus 5.5, high effort. Independent T3 delegated task of the freeze executor r2, read-only.
- Target: freeze commit `391d2006acc5c70f42679d7f014b84bc9fe0c2f9` (parent `fbcd677d`), checked against coordinator 0523ae6f's decisions A–D and 1–9.
- Verdict: **APPROVE**.
- The non-blocking notes N1–N5 below are applied in the fill commit.
- The text below is the reviewer's final answer, verbatim.

---

I recommend **APPROVE**. The PREREG-K4S freeze record at `391d2006` faithfully reflects decisions A–D and 1–9, adds no decision of its own, and every SHA it cites matches the committed bytes. I found nothing blocking. Five small wording issues are listed under N1–N5 below; they can go into the commit that fills in the freeze SHA, which edits the record anyway.

I stayed read-only: no edits, commits, pushes or ssh. I didn't read any game outcome or result file; I only hashed `results-phaseACE.json`. I re-ran the seed audit once, in a throwaway clone of `391d2006` under /tmp that I deleted afterwards, never in the worktree.

## Checks (all passed)

1. **Decisions 1–9 are present and faithful.**
   - **1 (c\* = 0.9):** the record matches COORDINATOR.md 11:46 and commit `6ef5e2ff`. `daba6859` was committed at 09:30:42Z, before `b577a255` at 11:40:02Z.
   - **3 (Q1–Q13):** the restated Q13 order matches r3 l.119–125. The Q12 wording matches r3 l.813.
   - **5 (errata):** R2 uses the coordinator's wording. R5's .69/≈.35 → .705/.366 matches RECHECK-r3 l.176 and r3 l.821–822.
   - **9 (TIERS blocker):** `measure_tiers.py` at `5d7de8e3` calls `math.isfinite` at l.70 and has no `import math`.
   - **The 04 / Q7 note is a faithful reading, not a new decision:**
     - r3 l.601 says 04 "is allocated until 2026-10-12T12Z", so Q7's "04 not before 2026-10-12T12Z" was that allocation.
     - Receipt `5f59f7f8` releases it early at 13:57Z ("original_valid_until_utc": "2026-10-12T12:00:00Z"; "need_04_compute_before_END_or_B": false).
     - COORDINATOR.md 13:57 says storage stays off-limits and names {03, 04} as the K4S host set.
   - **03 vacancy times:** 13:01Z matches COORDINATOR.md ("03 vacant since 13:01Z"). 17:18Z matches the prep log (PROGRESS.md 17:18:21Z, "No processes of mine are running on 03 or 04").
2. **SHAs.** I recomputed all 32 path/sha pairs in the JSON from `git show 391d2006:<path>`, and all match.
   - PREREG r3 is `9650972d…`, and the file is unchanged since `daba6859`.
   - The SD1 hash `b8ce7b4c…` is the sha256 of `SD1-MANIFEST.json` at the freeze commit.
   - The Sol review file is `844f40f5…`.
   - Both transport receipts match their untracked originals in `/mpac/sdicks02/repos/clasher` (`cmp` shows them identical; c2cef696 / 5f59f7f8).
3. **SD1 supersession.** The quoted issued text (l.15–19) and the scope limits (l.35–47) of `SD1-SUPERSESSION-ISSUED.md` are identical to the draft, and they match r3 §2.1.
   - `POINTER-SD1-K4S.md` is a new file (`A`).
   - No other exit-r3 file changed between `c18249aa` and `391d2006`, and `RESULTS.md` is still `646db0a6`.
4. **Paths touched.**
   - `fbcd677d` touches 7 files, all under `k4s-confirm/`.
   - `391d2006` touches 11 files: the K4S files, the new pointer, the freeze `.md`/`.json`, and the two named perception receipts.
   - Nothing changed under `reports/explore/t1`, and no other perception file changed.
   - The commit message is exact, attributes the receipts to perception, and ends with the Co-Authored-By line.
   - A grep of the diff for common secret patterns found nothing.
5. **Seed audit.**
   - The `audit_seeds.py` diff from `c18249aa` to `fbcd677d` is exactly parts 1–4, and nothing else:
     - part 1: `SELF_DECL_PREFIX` skip, with the skipped files listed in the notes;
     - part 2: `OWN_OUTPUTS` excluded from the literal scan;
     - part 3: `k4s_declared` covers base through `stop−1+max(OFFSETS)`, and `WINDOW_BOUNDS` is both task bounds plus both F-4 bounds;
     - part 4: `sys.exit(main())`, with 1 on FAIL.
   - The 7 tests include the synthetic foreign collision, and I ran them: 7 passed in 28.45 s.
   - The committed outputs say PASS with worktree HEAD `fbcd677d`: 0 violations, 44/10/0, 691 excluded, 2 self-declaration files skipped.
   - My extra re-run at the full freeze tree also gave PASS, exit 0. It walked 205 declaration files (the freeze JSON adds no intervals), and found 54 in-window literals and 0 FAIL.
6. **Mac manifest.** `781d25ba` → `d89cab16`. A key-by-key diff shows only `frozen` (false → true) and `status` (→ "FROZEN") changed.
7. **DELTA-MANIFEST and skeleton history.**
   - The manifest SHAs at each commit match the record: `d15715ba` at `962ecce2` (new 65), `19586d20` at `247ef6d4` and `c18249aa` (new 81), `32240719` at `fbcd677d` (new 83), `34eca2b7` at `391d2006` (new 84, inventory 174).
   - The row changes are exactly as recorded: 19586d20 → 32240719 adds 2 rows and refreshes 4 SHAs; 32240719 → 34eca2b7 adds 1 row and refreshes 4 SHAs. No row changed class, and nothing else at the top level changed.
   - `rebind.py verify` reports exactly one failure, the skeleton row.
   - The skeleton pins `34eca2b7`. Its sections G/H match the prep version at `247ef6d4`, with only the new review added.
   - The prep skeleton pinned `d771e459` with "new 73", and that is corrected.
8. **Freeze JSON shapes.** It contains no `base`/`count`/`pairs`/`start`/`stop`/`stop_exclusive`/`*seed_interval` keys and no `45036…` 16-digit literals. The `.md`, the issued file and the pointer have none either.
9. **Mac test note.** I reproduced it: 94 passed, 1 failed at `test_measure_k4s.py:609` (`frozen is False`).

## Wording issues for the SHA-fill commit (not blocking)

- **N1. Freeze time vs commit time** (`PREREG-K4S-FREEZE-20261011.md:4`, json `freeze_utc`, `SD1-SUPERSESSION-ISSUED.md:3` and l.31).
  - **Problem:** the freeze time 17:43:02Z is earlier than the skeleton generation in the frozen tree (17:43:32Z, skeleton l.3) and the freeze commit (17:45:00Z). The SD1 supersession is "ISSUED at … 17:43:02Z", before it existed in any commit.
  - **Fix:** say that 17:43:02Z is when the record was composed, and add the freeze commit's time, 2026-10-11T17:45:00Z.
- **N2. Mac test note understates what the failing test drops** (`.md:115`).
  - **Problem:** the test aborts at l.609, so its SHA-mismatch and forged-pin refusal checks (l.612–619) no longer run. The record's re-check mentions only the frozen load and the refusal of the draft bytes.
  - **Context:** I confirmed that the frozen manifest still refuses a wrong SHA ("K4S manifest SHA mismatch") and a forged `measure_tiers.py` pin ("Pin mismatch").
  - **Fix:** say both tamper refusals were re-checked against the frozen manifest.
- **N3. SHA references still unfilled** (`.md:5`; json `freeze_commit`; `SD1-SUPERSESSION-ISSUED.md:6` and l.31; `POINTER-SD1-K4S.md:5`).
  - **Problem:** these say the SHA "is recorded in the freeze record", which isn't true yet.
  - **Fix:** fill in `391d2006acc5c70f42679d7f014b84bc9fe0c2f9` in both the `.md` and the `.json`. Whether to also touch the issued file or the pointer is your call; leaving them as they are is fine once the record carries the SHA.
- **N4. Attestation and checklist labels** (`.md:28`).
  - **Problem:** CONFORMANCE-r2 F-10 says "except N1–N3, M1–M6 and the F-1…F-9 fills"; the record says "F-1..F-10". It's still true, because r3's bytes haven't changed since `daba6859`. But F-1, F-7, F-9 and F-10 are covered only implicitly, by decisions 1, 2, 3 and 6.
  - **Fix (optional):** add those labels next to the decisions.
- **N5. 03 vacancy sources not cited** (`.md:22`).
  - **Problem:** the 13:01Z and 17:18Z vacancy times have no source attached.
  - **Fix (optional):** cite COORDINATOR.md 13:06 for 13:01Z and `k4s-confirm/PROGRESS.md` 17:18:21Z for 17:18Z.

Neither "182 violations" (`.md:76`) nor "all fail against the pre-fix tool" (`.md:83`) can be checked from the repo. Both are plausible: before the fix, `WINDOW_BOUNDS`, `k4s_declared` and `classify` didn't exist, the tool always exited 0, and it read its own outputs as prior declarations.

VERDICT: APPROVE
