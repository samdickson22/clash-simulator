# RoyaleSim adapter: progress (exploration)

Owner: the bot-lead implementation sub-agent. The code is in `bot/players/royalesim_*.py` (worktree `bot/lead` on
127x05), synced to 127x03 with `rsync -a bot/ 127x03:/mpac/sdicks02/repos/clasher-bot/bot/`. All runs are on 03, under
`/mpac/sdicks02/jobs/clasher/bot-rsim-adapter/`. Nothing is committed or pushed. Details and numbers are in
[NOTES.md](NOTES.md).

## Done (as of 2026-10-14T04:01Z)

**Vocabulary:** `royalesim_vocab.py` → `royalesim_vocab.json`.
- It was built from paired duel and push demos of all 56 C56 cards.
- Nothing is unresolved and nothing lacks a template or statics.

**Translator** (`royalesim_translate.py`), **match loop** (`royalesim_match.py`), **opponents**
(`royalesim_opponents.py`), and the **runner and summary** tools (`royalesim_run.py`, `royalesim_summary.py`).

**Tests:** `test_royalesim_translate.py`, 7/7 pass on 03 with the final code.

**Cross-check** (`crosscheck3/`, final code): 5 cases × 600 ticks.
- To tick 300, rows are equal in 100/105 compared ticks.
- Every gap is physics, apart from the Arrows representation.

**Smoke 1** (`smoke1/`): both engines, an older vocabulary.

**Smoke 2** (`smoke2/`): the final code.
- K4S-b48 vs v1 and v1 vs v1 played ×2 each; every repeat gives an identical hash.
- 0 rejected commands, 0 translator drops and 0 own-cycle mismatches.
- One full game each of R3a, scripted-balanced and rgym-patient vs v1, and K4S-b48 vs rgym-patient.
- The 16.402 arm: a 900-tick game ran clean (`shake/c16402.jsonl`).

## Running

Nothing. No adapter process is left on 03.

## Next (for the lead)

1. Reserve a fresh seed bank (`reports/explore/x4s/audit_seeds.py`).
2. Run N paired games with the NOTES.md "Commands" loop (`--engine rsim` and `--engine ours`, same indices).
3. Run `royalesim_summary.py` on the output.
4. Optional fidelity work:
   - an Arrows multi-row expansion;
   - an option to give the RoyaleGym players RoyaleSim's native command delay instead of our 27-tick queue.
