# Verified branch-scoped native reads

`VerifiedNativeReadSession` replaces repeated full per-frame attestation with full pinned attestation at session entry and close. This deliberately changes verification frequency. Every level read still checks the process PID and Linux process start time, native manager, generation, state epoch, configuration revision/root/location, content-root/context identities, ready/paused status and unchanged ordinary frame. All body pointers and levels are read again.

Create the session after configuring a branch. Publish success only after the context exits successfully:

```python
with VerifiedNativeReadSession(
    adb,
    port=26789,
    serial="emulator-5580",
    expected_attestation_sha256=pinned_full_attestation_sha256,
) as session:
    levels = session.read_levels()

receipt = session.provenance
assert receipt["status"] == "verified"
```

The full attestation response must match its pinned canonical hash, including fields beyond the reader's fixed library/probe/content hash checks. At each read, content identity means native content pointers, not a fresh hash of content bytes. Content/code byte hashes are checked at both session boundaries. The provenance says this explicitly.

Each frame retains the existing `attestation` and `reader_sha256` fields and adds `verified_session` metadata. Frame metadata is marked pending final verification and names its session/read index. The final session receipt resolves that pending status. A changed closing attestation, identity change, read failure, source change, interruption or cleanup failure invalidates the entire session. Catching a read error inside the caller does not restore eligibility. PID start time also detects reuse of the same PID.

One ADB shell remains open for the session. It caches no body observations. Standalone `read_levels` behavior is unchanged and still performs full attestation on every call.

## Live check

On the same owned paused development frame at tick 3090, three standalone persistent reads had median latency **0.879 s**. Six session reads had median latency **0.564 s**, about **36% lower**. Entry took 0.474 s and verified close 0.435 s. The session made exactly two full attestation requests.

All ordinary snapshots, levels and attestation dictionaries matched the standalone reads. The frame remained unchanged, and the final session status was verified. No configure, step, play, helper installation or probe change occurred. Timings cover repeated reads of one paused frame, not a full branch or a claim of equal verification frequency. Evidence: `branch-session-parity.json` and `profile-session.py`.

The successful live path was followed by a small failed-entry cleanup hardening: a session that fails entry now drops its closed transport reference and rejects a second manual close without issuing more queries. That failure-only delta has unit-test evidence; the preserved live receipt retains the exact reader hash it exercised.

## Integration and tests

The readiness owner integrated the context into `run_readiness_v2.py` after configure. It writes a verified `native-session.json` only after successful close and preserves failed provenance on exceptions. The independent admission audit binds frame session IDs/read indices and boundary pins. Prefix-collector integration belongs to its owner.

**147 focused reader and public-level tests passed.** They cover every identity field, process replacement and PID reuse, mid-read changes, fresh levels after clock advancement, changed entry/end attestation, caught-error poisoning, interrupted close, source changes, cleanup failures and malformed pins. No gameplay fitting ran.
