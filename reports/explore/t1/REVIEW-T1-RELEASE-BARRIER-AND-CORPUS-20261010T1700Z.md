# T1 review: Amendment 1 release barrier (A) and corpus capture/builder (B)

| Part | Subject | Verdict |
|---|---|---|
| **A** | Release barrier, candidate `64608f6f90ba4f7f60ef493760a703b96051ebbb` (branch `worker/t1-amendment1-release-20261010`, base 3d6e2a56) | **APPROVE_WITH_CONDITIONS** |
| **B** | Corpus capture (`run.py`) and builder (`corpus.py`, `corpus_game.py`, `test_corpus.py`) at main `78b1e347` | **REJECT**: one blocker (B-B1), narrow fix |

- Reviewer: independent T1 reviewer, running on 127x05 with git and local files only. I made no ssh connection to 01, 03, 04 or 08.
- Reporting games read: 0. Outcomes stay sealed. No pool, check, registration or release was produced.
- Coordinator: 0523ae6f.
- Inputs checked:
  - Amendment 1 (a149a474): its file SHA is `b35bd4e5…2775`, which equals `AMENDMENT_SHA` in the code.
  - E4-v3 at HEAD: `FLEET-END-CONTRACT.md`, `FLEET-INPUT-SCHEMA.md`, `corpus_contract.py`, `fleet_pool.py`, `measure_tiers.py` and `receipts.py`.
  - Prior reviews in `reports/explore/t1/REVIEW-T1-*`.

## Part A: release barrier, 64608f6f

### Provenance and tests
- `release.diff` (SHA `5f476b06…8242`) is byte-identical to `git show --format=fuller 64608f6f`, and matches the packet SHA.
- I exported the candidate tree with `git archive` into `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/review/reviewer-rb/`. The five source SHAs equal `receipts/amendment1-release-tests.json`.
- Result: **38 passed** (`test_barrier.py` plus `test_release_reference.py`) under nice.
  - The fixture copies the real Amendment 1 file, so the tests must run from a tree that contains it.
- On main since base 3d6e2a56, `barrier.py`, `reduce.py`, `common.py` and `test_barrier.py` are unchanged, so admission does not conflict on code.

### Requirement check

| Requirement | Result | Evidence |
|---|---|---|
| Both routes gated | **PASS** | `outcome_release` restricts `reason` to the two routes, then calls `prerequisites()` before either branch. The 14-day escape must additionally show that its completion equals the checked END completion binding. |
| Committed completion, END record, v2 descriptor | **PASS** | Every input is a `{path, full commit, full SHA}` binding. `committed()` requires: the bytes at that commit equal the SHA, the commit is an ancestor of HEAD, and the working bytes are identical. Absolute paths, `..` and escaping symlinks are rejected. END must be `counted-reporting` and bind the exact completion. Its phases must equal `counted_host_phases`. The descriptor must be `fleet-pool.v2`. |
| Complete all-host, no-exclusion FLEET-POOL | **PASS** | The seal must contain all six E4 outputs. `excluded_hosts == []` and `excluded == []`. `hosts`, `included`, `host_receipts` and `attempts` all equal the counted host set. Profile is nice10, 3 repeats, physical cores, reporting load and `raw-host-times-repeat-v1`. Both ratios must be finite and within inclusive [0.95, 1.05]. Field names match E4 HEAD `fleet_pool.py` and `ReceiptStore` (which adds `scope`). |
| Recheck reruns unmodified E4 and compares every output SHA | **PASS, with C1 and C4** | `check_reference.py` runs E4's own `measure_tiers.py --pool-fleet-references` (threads pinned to 1) into fresh scratch. It requires the repeated manifest's `files` to equal the original, then re-hashes every output. "Unmodified" is enforced transitively: E4 pooling calls `verify_files(e4v3, identity.measurement_files)`, and that inventory covers every `.py`/`.sh` plus `spec-pins.json` (`prepare_bundle.py:110`). The barrier then recomputes `pool_inputs()` and requires it to equal the receipt's `input_files`. E4 pooling output contains no timestamps, so a byte-exact recheck is achievable. |
| Registration seal retaining all original attempts | **PASS, with C2** | The seal is `T1-REGISTRATION/complete`. It requires: `fleet_reference` equals the pooled object; pool manifest and check SHAs as lineage; `committed-copy` replay; the corpus receipt sealed; four times 300 unique speed IDs; speed and deadline references byte-equal to the checked pool; and every descriptor attempt, failed or passing, archived with every original file SHA sealed. |
| No bypass, fails closed | **PASS** | I found no route around `prerequisites()`. Every gap raises `ValueError` or `KeyError`, and those checks survive `python -O`. The pre-existing `assert`s in `barrier.py` do not, but they guard only the coordinator fields. `reduce.main` calls the barrier before `load_blocks`. Only `reduce.py` reads outcome fields (grep). |
| No outcomes read before release | **PASS** | The barrier reads only: completion (health), END, descriptor, pool outputs, registration, and reference-attempt seals and identities. |
| Not satisfiable by smoke or partial pools | **PASS** | END `kind` must be `counted-reporting`, and E4 `pool_context` rejects A6 `unpoolable-smoke`. Host-set equality is checked in four places, exclusions are forbidden, and a partial seal fails the `POOL_FILES` check. |

### Conditions (must hold before the coordinator relies on a release)

- **C1. The barrier trusts a self-attested check receipt.**
  - **Gap:** `prerequisites()` validates `pool-check.json` fields (`passes`, `output_files`, `input_files`, `checker_sha256`) but never re-executes the recheck. A hand-written JSON with correct, recomputable fields is indistinguishable from a real run. This needs deliberate fabrication, not an accident.
  - **Fix:** E4 pooling is cheap, read-only and reads no outcomes. Have `outcome_release` call `check_reference.check(...)` itself into a scratch output after `prerequisites()`, and require its `output_files` and `input_files` to equal the committed receipt. Alternatively, the independent packet reviewer re-runs the check and records the receipt SHA they reproduced.
- **C2. Attempt completeness rests on the descriptor alone.**
  - **Gap:** "Retain all original attempts" is verified only against `descriptor.hosts[].attempts`. If a failed first attempt were omitted, the descriptor would list only the later passing attempt, and nothing would catch it.
  - **Fix:** bind attempts to an independent record. Either require every attempt directory to sit under one per-host attempts root whose directory listing equals the descriptor list, or cross-check the detached-launch receipts and the coordinator-assigned windows.
- **C3. Re-verify against the final committed E4 END interface.**
  - **Gap:** the working tree currently has uncommitted E4 changes (another thread's, which I did not touch). They add `blind_ledger` and `counted_inventory` ARTIFACTs, completion fields `blind_ledger_sha256` and `counted_inventory_sha256`, a `reporting_hosts` rule, and `validate_admission`/`validate_blocks` in pooling.
  - **Fix:** once those land, add cheap redundant barrier checks that the completion's two new SHAs equal the END ARTIFACT SHAs, and re-run the 38 tests together with a real E4 pool fixture (see C4).
- **C4. The checker's success path has never run.**
  - **Gap:** the fixture's `pool-check.json` is synthesized from `pool_inputs()`, not produced by `check()`. The only `check()` test mocks `subprocess.run` for the differing case. In addition, `check()` discards E4 stdout and stderr, and the E4 `failure.json` disappears with the TemporaryDirectory, so the first production failure would be opaque.
  - **Fix:** keep E4's `failure.json` or stderr in a health-only side file. Have the first production check independently reviewed before admission.

### Notes (non-gating)
- **N1.** Registration `sets.speed[t]` is checked for count and uniqueness, but not for equality with the keys of the checked `speed-reference.json[t]`. Suggest adding that check, plus a check that the registered corpus-receipt SHA equals E4's cross-host `corpus_receipt_sha256` binding.
- **N2.** For hygiene, run the E4 subprocess with `-I` so an inherited `PYTHONPATH` cannot shadow stdlib modules. Inputs are pinned, so this is not a known escape.
- **N3.** `pool_inputs` keys are absolute paths and the scratch root `/mpac/sdicks02/tmp` is hard-coded. The check and the release must therefore run in the same path layout. This fails closed.
- **N4.** If the END pool can never conform (a second failure, per E4's rule), the barrier keeps outcomes closed indefinitely. Amendment A1.1 requires that. Any release then needs an outcome-blind amendment; no code path should be added for it.

## Part B: corpus capture and builder (main 78b1e347; files clean against HEAD)

### Blocker
- **B-B1. The capture path crashes every K0c and S corpus game.**
  - **Cause:** the capture block (`run.py:251-272`) runs after the `with WINDOW:` block, by design, so it stays off the timer. For cached-policy tiers it calls `cached.propose(...)` (`run.py:260`). In the plan, K0c-200 is `v1-cached` and S-200 is `R3a-cached`.
  - `CachedPolicy.propose` calls `self.check()` first (`cached_policy.py:38`). That is `inference_check`, which asserts `WINDOW.active`. `WINDOW.__exit__` has just set `active` to False.
  - **Reproduced on 05:** I extracted the `inference_check` closure verbatim from `run.py` and used the real `gc_window.WINDOW`. `propose` inside WINDOW returns; the same call in the capture position raises `AssertionError`. The script is `review/reviewer-rb-scripts/repro_window.py` (not committed).
  - **Effect:** for K0c and S, every capture-eligible decision (`tick >= 90`, `tick % 10 == 0`, channel free) raises before any row is added. `local-complete.json` is never written, so the builder finds no captures, and `assert paths, tier` fails. This fails closed (no bad corpus can be produced), but K0c and S get no 300-state corpus. K2 and K4 (`cached is None`, so `proposals = ()`) are unaffected.
  - **Fix:** fetch proposals in the capture block without the inference check. Either save the proposals the live path already obtained, or read `cached.cache` through a non-checking accessor; it is a cache read, not a forward. The poll at `run.py:180` always fills the cache inside WINDOW, even when the decision later hits `preparation_hit`. Keep `inference_check` unchanged for real forwards. Do not count capture reads in `proposal_calls`.
- **B-C1 (required with the fix). Add a capture-path test.**
  - `test_corpus.py` covers quotas, bins, the `_pending` snapshot and the resume-equals-fresh belief check. It never runs the `run_game` capture path, and that is how B-B1 escaped.
  - Add a short test that drives the capture block for a cached-policy tier and for an uncached one, through a real or stub `CachedPolicy` and the real `WINDOW`. Pass every emitted row through E4's `corpus_contract.validate_row(row, tier)`.
  - Also call `validate_row` from `corpus.main` on every selected row, and `validate_capture_receipt` on `corpora.json`. Today the builder never imports `corpus_contract`.

### Everything else checked: PASS (approve once B-B1 and B-C1 are done)

| Requirement | Result |
|---|---|
| Never from reporting games | `corpus_game` requires `phase == 'corpus'`, `game_class == 'qualification'`, `0 <= index < 64`, and a seed equal to the corpus base plus index. The corpus bank base `4503603407370496` is disjoint from the primary, guard, replacement, smoke and descriptive banks. The builder re-checks phase and class, the seed range, the `local-complete` capture SHA and `excluded_indices` [0, 1, 2], and reads no game JSON. |
| Exactly the 20 fields | 8 `capture_before` keys plus 12 row keys equal `REQUIRED_ROW` exactly. This agrees with the 16:10Z source audit. |
| `d1_before`, `d1_events`, strata | `d1_before` is the D1 tracker `__dict__` without `builder`. `d1_events` is the public recorder stream. `strata` is `{elixir, legal_play_count, bins}`, with bins from the plan's `[3,6]` / `[1,128]`, identical to the contract's bins. |
| Physical `info` plus `reserved_packet` | Both are stored separately: `info` is `fair_player.Information` (tick, seat, public v5 packet, own HUD, events), and `reserved_packet` is the own-channel packet. |
| Sealed `pending` | A deep-copied tuple of the own channel's pending commands, taken before the decision. |
| Kept whether or not the live decision reached root | Eligibility, posterior, sample and root are reconstructed after the timer, from independent copies of the pre-decision state. This happens regardless of whether the live run hit a belief, sample or score cutoff. The only filter is more than one reconstructed non-2305 candidate, as the plan specifies. Capture health counts `deadline_cut` and `suspended_transaction`. |
| Committed posterior | `committed_belief` gives `_pending = None` and a deep copy, and the live object is untouched (tested). `belief_had_suspended_transaction` is a bool. Replay is a full `update(deadline=None)` from the committed copy; the resume-equals-fresh test passes, so there is no `belief_resume`. |
| Fair-information rule | `info` holds only the public builder output and own state. `opponent` is sampled from the posterior. `root` is built by `R.root` from public entity rows plus the sampled opponent. `opponent_elixir` comes from the public tracker. I found no battle object or hidden-hand reference in a row. |
| Selection | Outcome-independent: SHA-256 priority over tier/seed/tick, a reservoir capped at 300 per stratum, proportional quotas with at least one per occupied stratum, and largest remainders. `corpora.json` matches the shape of E4 `validate_capture_receipt`. |
| Tests | `test_corpus.py`: 4 passed with the T1 runtime `PYTHONPATH`. |

**Non-gating note.** `core = copy.copy(p.core)` is a shallow copy, so the excluded corpus game's later live state may share mutable internals with the capture work. This affects only excluded games and reads no outcomes.

## Summary for coordinator
- **A: APPROVE_WITH_CONDITIONS.** I found no bypass. The barrier fails closed, SHA-binds its inputs, reads no outcomes before release and rejects smoke and partial pools. C1–C4 (re-execute the recheck, independent attempt inventory, re-verify after E4 END lands, observable checker success path) should be met before a release relies on it.
- **B: REJECT.** The capture's `cached.propose` runs outside `WINDOW`, so every K0c and S corpus game asserts. The fix is a small accessor, plus a capture-path test and `validate_row` in the builder. Everything else meets the contract.
