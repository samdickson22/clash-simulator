# T1 END verifier r5 (legacy-only): narrow diff check

- Reviewer: Claude Opus 5.5 (1M), independent and read-only, on 127x05. Written 2026-10-12T01:28Z.
- Bytes checked against `origin/main` (b5ea3ed1):
  - verifier `end_verify_push.py` `753722c9…60d1` ✔
  - wrapper `end_exit_push.sh` `0a87166f…61b1` ✔ (unchanged, frozen as ruled)
  - diff `END-verifier-r5-legacy-only.diff` `6422005c…952896` ✔ (169 lines; verifier-only)
- Context read: r3 review, ruling 81b7c01e, candidate receipt, launch-preparation, receive-prepare and launch receipts.
- I did not SSH anywhere, edit T1 files or open outcome data. For the live A6 receive dir I only checked `PREPARED.json` (stat and content: procedural, written on 05 at 01:08:13.19Z). Directory mtime = that same instant, so nothing has been pushed yet.
- Synthetic tests used `nice -n19 taskset -c63 python3 -I`, real rsync 3.1.3 for local pushes, and a scratch copy with only `BASE` repointed. Scratch is deleted.

## Verdict: **APPROVE_WITH_CONDITIONS**

Every control in the ruling is implemented and fails closed. I found no early return before the binding checks, no swallowed exception and no str/bytes or timezone error. The conditions below are operator pins, plus one optional one-word hardening.

## Control-by-control

| Control | Where | Result |
|---|---|---|
| R3-1: explicit raises | `:17-19`, all checks | PASS. No `assert` is left in the file. |
| R3-1: refuse optimized Python | `:13-14` | PASS. `-O` and `PYTHONOPTIMIZE=1` both give `SystemExit` at import, before `main`. |
| R3-2: prepared dir required | `:58` | PASS. Without `PREPARED.json` it gives "Receive was not prepared". |
| R3-2: pinned proof and nonce | `:60-62`, `:134-136` | PASS. Whole-dict equality covers the nonce. The pinned file's SHA is checked. Note: the A6 proof has 3 extra keys, but equality is still True against the committed receipt (I checked). |
| R3-2: prepare before launch | `:76` | PASS. `proof.utc < launch.utc`, both fixed-format `Z` strings, so lexical order = time order. |
| R3-2: reject PUSH-FAILED | `:54-57` | PASS for every file the wrapper can produce. Gap for a dangling symlink, see F2. |
| R3-2: marker mtime ≥ exit | `:74-75` | PASS. Parsed as UTC (`replace(tzinfo=utc)`, so not naive). The stale-marker case is rejected. |
| R3-3: legacy PUSH-FAILED = no ACK | `:56-57` | PASS. The message carries `rsync_exit_code=legacy-unspecified`. It is recorded only on stderr, see F3. |
| V3: argv byte-equal | `:78-79` | PASS. bytes vs bytes. The A6 launch receipt's `measurement_argv` re-encodes to exactly `d3a6e81e…`. |
| Launch binding | `:63`, `:77` | PASS. `job` is matched by basename only, but argv equality pins the full job path (`--output $job/measurement`). That closes the r3 two-parent reuse case. |
| Wrapper pin | `:77` | PASS (`0a87166f` literal). |

**No r3 behavior lost.**
- The exact file set, all file hashes, the seal-stamp check, exit 0 ⇔ `complete`, the no-symlink checks, UNSEALED → exit 2 and the `open('x')` receipt are all byte-equivalent apart from assert → `require`.
- The UNSEALED early return (`:88-90`) now comes *after* every binding check, which is stricter than r3.
- The only change outside the ruling's scope: `--prepare` now writes `PREPARED.json`. That is compatible with the wrapper, because rsync runs without `--delete` and the top level of the receive dir is not enumerated.

**Q2: stale, partial or foreign receive dirs.** I found no ACK path.
- **Stale marker:** its mtime is earlier than the exit time, so it is rejected (tested).
- **Foreign or reused attempt:** the argv bytes differ, or the nonce/proof differs.
- **Unprepared dir:** refused.
- **Partial transfer:** no marker is written, or PUSH-FAILED is present. A `--partial` truncated marker fails JSON parsing.
- **Extra or missing measurement files:** rejected, as in r3.

## Q4: is the mtime rule sound against 0a87166f?

Yes.
- `exit_utc` is `date` on 01 right after `"$@"` returns (`end_exit_push.sh:43`), truncated to whole seconds.
- The marker is written on 01 at `:79-80`, after all metadata and measurement pushes. `mv` keeps the mtime.
- It is pushed with `rsync -a` (`:60`), and `-a` includes `-t`, so the 05 copy carries **01's** write mtime. I confirmed this with real rsync: nanoseconds are kept, because both sides use protocol 31.

That gives `marker_mtime ≥ exit instant ≥ floor(exit) = exit_epoch`, with both times from 01's clock. So 01↔05 clock skew can't cause a false REFUSE. Even if mtime were truncated to the second, the ordering would still hold. A same-second exit and marker ACKs (tested).

A marker written before exit can pass only if someone deliberately forges its mtime on 01. That is out of scope; the argv and nonce binding still apply.

## Findings

1. **F1: Medium (operator pin, false REFUSE risk). The brief names the wrong launch receipt.**
   - `END-A6-launch-preparation-01-r1.json` stores the argv under `argv`, not `measurement_argv`.
   - The verifier reads `launch['measurement_argv']` (`:78`), so pinning that file gives `KeyError` and no ACK. I tested this; it fails closed but is a false REFUSE.
   - The correct pin is `END-A6-launch-receipt-01-20261012T011336Z.json`:
     - SHA-256 `45bd9dc30ec6de5c2c7f67929209c33144162191f93211f23bc7ef79a2a741b8`;
     - `utc` = detach launch time 01:13:36Z;
     - committed in 733a27d8;
     - it has `measurement_argv` (→ `d3a6e81e…`), `host`, `job` and `wrapper_sha256`.
2. **F2: Low (`:54`). `.exists()` follows symlinks, so a *dangling* `PUSH-FAILED.json` symlink is ignored and the run ACKs** (tested).
   - The wrapper can't produce this: it `printf`s a regular file and pushes it with `rsync -a`. So it is not blocking.
   - Minimal fix if T1 touches the file: `if os.path.lexists(root / 'PUSH-FAILED.json'):`.
3. **F3: Low (`:57`, `:134-142`). On refusal, including legacy PUSH-FAILED, the verifier writes no receipt; the reason exists only in the traceback.**
   - The `legacy_PUSH_FAILED_without_exit_code_is_failure` flag (`:115`) appears only on ACK receipts, where it is a static policy flag.
   - Under r3 V3, the operator must capture stderr and the exit code into the T1 verification receipt. That satisfies "recorded in the receipt".
4. **F4: Info. The verifier trusts the self-reported `proof.utc`.**
   - "Prepared before launch" is really guaranteed by the pinned proof having been committed before launch. For A6 that is `END-A6-receive-prepare-01-r1.json`, SHA `b6597ae1…d520`, in e6c73498 at 01:11:41Z, which is before the 01:13:36Z launch.
   - On-disk `PREPARED.json` (`da21a039…`) is JSON-equal to it, and its mtime is 01:08:13.19Z.
   - Pass the committed receipt, never the receive dir's own `PREPARED.json`. The latter would make `:60` a tautology.
5. **F5: Info.**
   - `:76` uses strict `<` at one-second granularity, so a prepare and launch in the same second would REFUSE. That is not the case for A6, and later runs should leave at least 1 s.
   - The ACK receipt doesn't record the launch-receipt or prepare-proof SHAs. Optionally add `launch_receipt_sha256` and `prepare_proof_sha256` to the receipt dict at `:111-116`.
   - Run the verifier only after `exit_utc` + ~1300 s (the wrapper's maximum lifetime) or after C1 proof. That way a late PUSH-FAILED, after a nonzero rsync that had already landed the marker, can't arrive after an ACK.

## Conditions (all procedural; no code change required)

- **C-a (F1, F4):** invoke exactly
  `nice -n 19 taskset -c 63 python3 -I <staged 753722c9 verifier> --receive …/end-received/127x01/end-a6-127x01-0a87166f-r1 --launch-receipt <END-A6-launch-receipt-01-20261012T011336Z.json> --launch-receipt-sha256 45bd9dc30ec6de5c2c7f67929209c33144162191f93211f23bc7ef79a2a741b8 --prepare-proof <END-A6-receive-prepare-01-r1.json as committed in e6c73498> --prepare-proof-sha256 b6597ae13f1740ba5d8eb14de1b8a182a557340e3770ae498e94de310c4cd520`
  - Check the staged verifier's SHA first.
  - For the 08 and 01 references, pin the analogous launch receipt (with `measurement_argv`) and a prepare proof committed before that launch.
- **C-b (F3):** on any non-zero exit, record argv, exit code and full stderr in a T1 receipt. A traceback means no ACK.
- **C-c (F2, optional code):** apply the one-word `lexists` change. If not applied, record `test ! -e PUSH-FAILED.json && test ! -L PUSH-FAILED.json` in the verification receipt.
- **C-d (F5):** verify no earlier than `exit_utc` + 1300 s, or after C1 proof that the wrapper is gone. C5 still holds.
