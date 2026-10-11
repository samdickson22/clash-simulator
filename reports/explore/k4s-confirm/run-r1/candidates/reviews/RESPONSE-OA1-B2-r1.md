# Author response to SOL-REVIEW-OA1-B2-r1 (REJECT)

Author: K4S runner r1 (Claude Opus 5.5), 2026-10-11T18:36Z (date -u). New bytes: mirror_k4s.py 4a5d9e9f…, test_mirror_k4s.py
a50e379b… (21 tests), build_job_manifest.py ba440542…, FROZEN-K4S.json 454b5f54… (176 files). No frozen byte changed.

1. MAJOR return-ACK permanence: FIXED. Hub durability (`hub-ack.json`) and source return (`hub-ack.returned.json`) are
   separate. `return_ack()` pushes the ACK with the copier prefix, then pulls the source copy back (rsync --server --sender
   on `<job>/<phase>/<id>/hub-ack.json`) and byte-compares; only then is the marker written (bound to the hub ACK sha).
   Every pass retries any durable block without a valid marker, so a restart recovers too. Health reports
   `durable_on_hub`, `ack_returned`, `pending_return`. Tests: failed push -> pending + error; next pass (= restart) returns
   and verifies; idempotent afterwards; stale marker (sha mismatch) is not accepted.
2. MAJOR registration race / successor revocation: FIXED. A non-blocking exclusive `flock` on `<job>/oa1-copier.lock` (hub)
   is taken before the receipt is inspected or published and held for the copier's life (per job; 03/04 jobs are distinct).
   Teardown revokes only if the receipt identity equals this process's identity. Tests: second lock refused; 2-thread
   barrier race admits exactly one; teardown against a successor receipt raises and sends nothing.
3. MAJOR stale active receipt: FIXED. try/finally around the copier life; SIGTERM/SIGINT raise into the finally (signals
   ignored during revocation); revocation writes inactive locally, pushes, pulls back and byte-compares, 3 tries; failure
   -> exit 3 with `lifecycle_error` in health and the source receipt honestly left active. The identity is set before the
   first push so a failed registration push is still revoked. `--revoke` recovery mode (SIGKILL/power loss) takes the lock
   and refuses while the receipt's copier is alive. Operating rule: before any phase hand-off or reporting launch, confirm the
   previous copier's source receipt is `active: false` (or run `--revoke`). Tests: --once happy path verified on both sides;
   failed revocation -> 3 + lifecycle error + remote still active; SIGTERM mid-pass -> revoked; recovery refuses live,
   deactivates dead.
4. MINOR premature wording: FIXED. `operational_amendments` now states OA-1's coordinator ruling and that the script SHA and
   binding Sol verdict are NOT bound in the manifest but in the K4S freeze addendum (committed before any reporting game).
5. MINOR smoke freeze sha: ACCEPTED as disclosure. Recorded in the K4S freeze addendum (frozen run.py stamps the job-manifest
   sha whenever the manifest exists, so smoke games carry it; K4S-SPEC §5 says null; smoke excluded; health does not check;
   frozen bytes unchanged). Coordinator disposition requested.
Hardening from Q2: jobs must sit directly under the approved root for their host (03 `/mpac/sdicks02/jobs/clasher`, 04
`/mpac/sdicks02/jobs-k4s`), realpath == path, name `k4s-confirm-*`; block pulls use `--no-links`, game files must be regular
non-symlink files; arms must be the 10 canonical K4S arms. Tests added for each.
Live re-run (synthetic fixtures oa1test3, removed afterwards): both hosts listed 3, durable 2, returned 2 (byte-identical
on source), corrupt block isolated, receipts inactive on hub and source (`integration/evidence-oa1test3-*`, `copier3-*.log`).
