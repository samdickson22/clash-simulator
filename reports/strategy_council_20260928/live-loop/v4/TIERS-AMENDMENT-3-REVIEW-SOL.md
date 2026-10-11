# TIERS Amendment 3: independent Sol review record

Reviewer: GPT-6.1-Sol at high reasoning effort, run through T3 `delegate_task` from the implementer thread. Each review was read-only: no edits, no ssh, no timing sessions and no sealed-outcome access. Worktree under review: `/mpac/sdicks02/jobs/clasher/e4-amendment3-worktree` on 127x05. The verdicts below are reproduced verbatim; the implementer's responses are summarized.

## Round 1: REJECT

1. **High.** The assembled-fixture binding was only declared: a reconstruction was labelled `0addf7c0` without being compared to that pickle. **Response:** the index gained `source.verified`, which only a `--states` run sets after SHA-checking the actual `states.pkl`. `StateRows` refuses unverified indexes. `--expect-fingerprint` was added. Adoption requires T1's conversion of the actual 01 `0addf7c0` with the reviewed fingerprint.
2. **Medium.** The identity proof missed shared array and tensor storage. **Response:** `canonical_digest` and `deep_equal` now encode backing-buffer and storage sharing with offsets and strides. All 1,325 rows certified: 63,450 arrays and tensors, 0 sharing a buffer.
3. **High.** Untimed loading can alter poll qualification, because `gc_summary` counts only GC-overlapping late polls, and D8 first-load GC is labelled with the previous context. **Response:** full disclosure in the amendment (load distribution, heap, churn, duty cycle, I/O), plus the supplementary all-cause condition A3-P, computed from existing receipts.
4. **Medium.** The K4S re-pin needs downstream propagation. **Response:** a coordinator-owned companion, listed with every binding.
5. **Low.** Descriptor leaks on failure paths. **Response:** the constructor closes the store on any exception, and `close()` uses `finally`.

Round-1 verification by Sol: 87 tests passed on Python 3.8 (one skipped) and 17 on 3.12. `measure_tiers.py` was still `6066228b`. No per-decision lookup misses inside a timer; fleet lookups sit inside guard blocks but before timers.

## Round 2: REJECT

1. **High.** An A3-P failure was classified as a technical failure, which could invite a repeat. **Response:** an A3-P failure now makes the tier infeasible, like a failed frozen gate. The session and its gate inputs are retained; it is not a technical failure and grants no repeat (Addendum §F).
2. **Medium.** A failed conversion could leave an admissible index: Sol's fault-injection test was accepted after `deep_equal` failed. **Response:** the index is always written unverified. The verified index is published by an atomic `os.replace` only after every disk check and the input re-hash pass. A fault-injection test covers both `deep_equal` and `final_check` failures.

Round-2 verification by Sol: 90 tests passed and all 37 declared hashes matched.

## Round 3: APPROVE_WITH_CONDITIONS

> Both round-2 fixes are verified. No new functional regression found. All 42 hashes recorded in the amendment JSON match; frozen files and timed methods remain unchanged. Both unit-test runs succeeded: 91 tests each, with two skipped on Python 3.8.
>
> 1. **Low — stale test counts:** `make_amendment_json.py:56` hard-codes 90 total tests and 20 new tests, propagated into the amendment JSON. The current tests and both receipt logs show **91 total and 21 new**. Fix the generator counts and regenerate the JSON, preserving the updated generator's hash binding. No additional measurement run is needed.

**Response:** the generator now derives the counts from the committed test logs and the test file: 91 ran, 2 skipped on 3.8, 21 new, 70 before. The JSON was regenerated.

## Round 4 (final): APPROVE

> **APPROVE.** No findings.
>
> Confirmed the generator derives the correct counts: 91 tests per interpreter, two skipped on 3.8, 21 new, 70 before; both logs must end with `exit=0`. Read-only regeneration exactly matches the JSON, and all 42 declared file hashes match.
>
> The review record accurately reflects the supplied history and fixes. Frozen files and all 11 declared timed methods remain unchanged. Both unit-test reruns passed under `nice -n 19 taskset -c 63`. No regression found.
>
> `independent_review: null` is consistent with the planned commit-time update.

The commit then fills the amendment JSON's `independent_review` field with this record's SHA and the round-4 verdict, using the same generator. No source, receipt or test changed after round 4.
