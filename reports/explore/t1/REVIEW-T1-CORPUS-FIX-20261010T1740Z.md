# T1 review: corpus capture fix (B-B1 / B-C1 re-review)

| Subject | Verdict |
|---|---|
| Candidate `a51ea64cb878ca05bf38a8145174e6d2b9f46d7a` (branch `worker/t1-corpus-capture-fix-20261010`, parent 103fb51a) | **APPROVE_WITH_CONDITIONS** |

- Reviewer: independent T1 reviewer, running on 127x05 with git and local files only. I made no ssh connection to 01, 03, 04 or 08.
- Reporting games read: 0. Outcomes stay sealed. No corpus, pool or registration was produced.
- Coordinator: 0523ae6f.
- Prior review: `REVIEW-T1-RELEASE-BARRIER-AND-CORPUS-20261010T1700Z.md` (06dab1ea), Part B REJECT.
- Scratch: `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/review/reviewer-cfix/`. It holds `git archive` trees of a51ea64c and 103fb51a, the scripts `repro_fix.py` and `ast_eq.py`, and `pytest-a51.txt`.

**Verdict.** B-B1 is fixed and B-C1 is satisfied. The conditions below concern deployment against the reporting freeze. They do not affect the correctness of the fix.

## Provenance
- **Packet `corpus.diff`** (SHA `07f58fd0…46a1`, matches `packet.json`): it is `git show --format=fuller a51ea64c`. Below the commit header it is byte-identical to `git diff 103fb51a a51ea64c`. `corpus.stat` matches its packet SHA.
- **Scope:** the commit changes only 6 files, all under `reports/explore/t1/`. Nothing under `imitation/`, `src/`, `engine-rs/`, `reports/explore/e1/` or E4 `e4v3/` changes.
- **Exported tree:** the SHAs of `run.py` (`286bf4b7…`), `corpus.py` (`9c4a65b7…`), `corpus_capture.py` (`0e6249e5…`) and `test_corpus.py` (`0dc2af82…`) equal `receipts/corpus-capture-delta-tests.json`.

## 1. The fix is correct (B-B1): PASS, reproduced on 05

### Mechanism
- `StandalonePlayer.decide` calls `policy.sample(...)` unconditionally on every poll, at `run.py:180`, inside `WINDOW`.
- `CachedPolicy.sample` first sets `cache=None`, then performs the single charged forward, then stores `cache=(d1, mask.copy(), proposals)`.
- The capture block (`run.py:251`) is reached only for `actor==seat` on a `tick%10==0` decision with the channel free. This is the same tick and the same seat's poll. The other actor's poll comes later, and in any case uses a separate uncached `V1Policy`.
- So the cache read at capture time is exactly the proposals the timed decision computed.

### What `corpus_capture.capture_proposals` does
- It asserts the same three things as `CachedPolicy.propose`: the cache is non-empty, `cache[0] is d1` (D1 identity), and the mask is `array_equal`.
- `model_packet(packet, mask)['action_mask']` is `mask` itself (`d1.py:80-86`), so comparing against `policy.mask` is equivalent to the old comparison.
- It does not call `check()`, does not increment `proposal_calls`, `forward_calls` or `fallback_calls`, and runs no forward.
- `cached_policy.py` and `gc_window.py` are byte-unchanged and equal the FROZEN-T1 SHAs (`559ad75c…`, `0c743f3d…`), so the guard on live `propose` and `sample` is intact.

### Reproduction (`repro_fix.py`)
The script uses the real `CachedPolicy`, the real `WINDOW` and the `inference_check` closure extracted verbatim from each commit's `run.py`. The only stub is the model forward, to stay off torch weights.

| Step | 103fb51a | a51ea64c |
|---|---|---|
| `sample` + live `propose` inside WINDOW | ok, counts (1,1,1) | ok, counts (1,1,1) |
| Old capture call `cached.propose` outside WINDOW | **AssertionError (B-B1)** | still AssertionError (guard unchanged) |
| New `capture_proposals` outside WINDOW | n/a | returns a list equal to the live proposals; counters unchanged; `WINDOW.active=False` |
| Stale D1 object, different mask, or empty cache | n/a | each raises AssertionError (fails closed) |

### Equivalence of the extracted code
- `capture_row` is the former inline block with three substitutions: `policies[actor]` becomes `policy`, `reserved.packet` becomes `reserved_packet`, and the proposals source is the new accessor.
- It returns `None` exactly where the old code skipped `capture.add`.
- The independent pre-decision copies of the RNG and posterior, and the tick-90 / tick-10 eligibility, are unchanged. So timed-out roots (belief, sample or score cutoff) are still reconstructed and retained.

## 2. The live reporting path is unchanged: PASS (behaviour), with condition C1 (bytes)
- **Behaviour.** `ast_eq.py` blanks the single `if capture_before is not None:` body in both commits. The rest of `run.py` is then AST-identical between 103fb51a and a51ea64c.
  - Reporting games have `capture=None`, so `capture_before` is always `None`. Their path, timer, RNG consumption and `policy_cache_counts` are therefore unchanged.
  - `corpus_capture` is imported only inside that branch.
- **Bytes.** `run.py`, `corpus.py` and `test_corpus.py` are all pinned in `FROZEN-T1.json` `files` (`run.py` = `110116eb…`). `reporting_release` (`barrier.py:41,49-51`) requires every pinned file in the job repo, and at `freeze_commit`, to equal its pin.
  - This candidate therefore cannot go into a reporting namespace without re-freezing.
  - That failure is closed (reporting refuses to start), but it is an operational hazard if a51ea64c is merged to `main` and a reporting namespace is later prepared from `main`.

## 3. Rows meet E4 `corpus_contract.py` exactly: PASS
- **Contract version.** E4 `corpus_contract.py` is identical at a51ea64c, `origin/main` and the 05 working tree. `TIERS = ("K0c","S","K2","K4")`.
- **Fields.** The 20 fields are unchanged from the approved inline block: `dict(capture_before, …12 keys)`, with the 8 `capture_before` keys at `run.py:175`.
- **Committed posterior.** `belief_before=committed_belief(...)` with `_pending=None`. Replay is `update(deadline=None)` on a deep copy, plus `sample(deadline=None)` from the copied belief RNG. There is no `belief_resume`. `belief_had_suspended_transaction` is a bool.
- **Fair information.** The row holds:
  - `info`: the physical public observation plus own HUD;
  - `reserved_packet`, stored separately;
  - `opponent`: sampled from the posterior;
  - `root`: built from public rows plus that sample;
  - `opponent_elixir`: from the public D1 tracker.

  No battle or hidden-hand object is present (unchanged from 06dab1ea).
- **Builder.** `corpus.main` calls the unmodified E4 `validate_row(row, tier)` on every selected row before writing that tier's file. After writing `corpora.json` it calls `validate_capture_receipt(out, manifest, by_id)`.
  - The manifest's `sets.speed` comes from the same selected rows, so the receipt check is self-consistency, not independent verification. It still enforces `outcomes_read=False`, exactly 300 per tier, the SHA inventory format, integer health bounds and the suspended-transaction disclosure.
- **Shadowing.** `contract()` inserts `e4v3/` at the front of `sys.path`. I checked for shadowing: no `e4v3/*.py` name collides with a `reports/explore/t1/*.py` name. E4's `receipts.py` takes precedence over T1's `receipts/` data directory, which is the intended module.

## 4. Tests: PASS (6/6 on 127x05)
- **Command:** `nice -n 19 … -m pytest reports/explore/t1/test_corpus.py` in the a51ea64c export.
  - It used the T1 runtime `PYTHONPATH` (per `runtime.sh`) with the E4 job's `student-source` read-only for `exit_r3`.
  - Interpreter: E4 venv Python with pytest from a scratch `--target` dir.
- **Result: 6 passed in 1.32 s.** This includes `test_capture_path_cached_and_uncached_outside_window_validates_rows` and `test_builder_validates_every_selected_row_and_published_capture_receipt`.
- **The capture test** drives the actual `capture_row` used by `run.py` for all four tiers.
  - It covers the real `WINDOW`, the real `CachedPolicy` (K0c and S) and `cached=None` (K2 and K4).
  - It asserts `propose` outside WINDOW raises, zero counters, physical/reserved separation, unchanged RNG snapshots, and that E4 `validate_row` passes.
- **The builder test** counts exactly 1,200 `validate_row` calls and one `corpora.json` receipt validation.

## Conditions
- **C1. Deployment isolation from the reporting freeze.**
  - Run corpus games from a dedicated corpus namespace, a repo copy at a51ea64c or its admitted descendant. Never use the reporting namespace.
  - Do not merge to `main` while any reporting namespace may still be prepared from `main`. If you do merge first, also commit a FROZEN-T1 disclosure that the three pinned files changed only in the excluded capture branch, citing this review and the AST-equality result.
  - `reference_schedule` already places the corpus in the END window, so the simplest route is to admit after the reporting games are dispatched.
- **C2. Bind the capture code identity in the corpus receipts.**
  - Today `local-complete.json` records the capture SHA but not the code that produced it. `corpora.json` records only the selection script's SHA.
  - Have the corpus launch record the commit and the SHAs of `run.py`, `corpus_capture.py`, `corpus.py` and `cached_policy.py`, so the corpus's lineage is checkable at registration.

## Notes (non-gating)
- **N1.** `capture_proposals` returns a shallow `list(...)` copy, the same as `propose`. Mutating a returned dict would alter the cache, but `capture_row` only reads `v['action']`, and the next poll clears the cache.
- **N2.** The 06dab1ea shallow-copy `copy.copy(p.core)` note still applies. It affects excluded games only.
- **N3.** `validate_capture_receipt` runs after `corpora.json` and the state files are written. On failure, the output dir holds an unvalidated receipt, but the process exits non-zero and `--out` refuses reuse (`exist_ok=False`). This fails closed.

## Summary for coordinator
**APPROVE_WITH_CONDITIONS.**
- **The fix:** capture reads the cache that this tick's timed poll already filled, checking the same D1 identity and mask. It runs no forward and leaves the counters and the CachedPolicy guard unchanged.
- **Checks on 05:** I reproduced B-B1 at 103fb51a and confirmed the fix at a51ea64c. Reporting behaviour is AST-identical, rows meet E4 `validate_row`, and the tests pass 6/6.
- **C1:** the pinned files changed, so keep this out of the reporting namespace. Merge to main only after reporting dispatch, or with a FROZEN disclosure.
- **C2:** record the capture code's SHAs in the corpus receipts.
