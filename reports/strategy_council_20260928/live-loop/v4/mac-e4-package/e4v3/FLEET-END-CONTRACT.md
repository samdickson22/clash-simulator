# Amendment 1 fleet interface (implementation/review draft)

This extends `FLEET-INPUT-SCHEMA.md`; the measurement CLI is unchanged. T1 owns
the excluded own-tier 300-state corpora and END runs on its reporting hosts.
E4 owns the runner. The generic 125 states remain separate exactness inputs.
T1 freeze `95883be0` retains the reviewed `ba3dc8b0` row contract. No reference
readiness is asserted: A6 requires T1's reviewed bundle and a real fleet smoke.

The SHA-pinned profile additionally names `end_evidence` and `guard`:

```json
{
  "end_evidence": "end-evidence.json",
  "guard": {
    "root": "t1-guard",
    "job": "/absolute/approved-t1-job",
    "freeze": "t1-freeze.json",
    "admissions": {"system-bus-admission.json": "guard-admissions/system-bus-admission.json"}
  }
}
```

`end-evidence.json` replaces the free-standing three-Boolean END marker. Schema
`clasher.e4v3.end-evidence.v1` contains `kind: counted-reporting`,
`repository: /absolute/local/committed-repo`, `completion: ARTIFACT`, and
`phases: [{host,phase,launch:ARTIFACT,supervisor_exit:ARTIFACT,
mhz:ARTIFACT,census:ARTIFACT}]`. Each ARTIFACT is
`{path: relative-bundle-path, repository_path: relative-repo-path,
commit: full-40-hex-commit, sha256: full-64-hex-SHA}`. The runner verifies bundle
bytes against both SHA and committed Git bytes. All paths also appear in
`tiers-pins.json.files`. No SSH or outcome files are read.

The committed completion is the object used by T1's release barrier: Boolean
`reporting_complete` and `outcomes_sealed`, `counted_primary_blocks: 2400`,
`counted_guard_blocks: 600`, and `completed_at_utc`. It additionally binds
`counted_host_phases: {host: [reporting, replacement-r1, ...]}`. The exact host
and phase set must equal the evidence inventory and be allowed by the pinned
plan. Every supervisor exit must have the right host, null reason, no failed or
unstarted blocks. Launch slots must equal the host's profile. Completion is
after all supervisor exits. T1 supplies this health-only projection; E4 never
derives it from game outcomes.

All reporting/replacement MHz and census files are retained verbatim. Join on
the exact UTC string within each phase; only `inflight == launch.slots` rows
enter reporting MHz. Missing/duplicate joins fail closed. The signed reference
to reporting mean ratio is retained in host, pooling and registration receipts.

The guard source tree contains frozen T1 `common.py`, `host_audit.py`,
`idle_services.py`, `system_bus.py`, `ssh_transport.py` and `plan.json`, pinned
against `guard.freeze.files`. The guard uses existing approved job admissions;
their staged copies are pinned and compared against live job bytes. No admission
identity is silently refreshed. E4 extends own-process accounting to its exact
PID/start-time descendant tree, then runs T1's OP-1 census/console/memory rules
at 1 Hz. Foreign compute/activity, console load above one core for >60 seconds,
MemAvailable below 24 GiB, or OP-1 identity/CPU interference stop the reference.
The raw guard receipts and stop cause are sealed.

Pooling descriptor schema becomes `clasher.e4v3.fleet-pool.v2`:

```json
{
  "schema": "clasher.e4v3.fleet-pool.v2",
  "context": {"bundle": "/absolute/approved-bundle", "manifest_sha256": "SHA256"},
  "hosts": [
    {"host": "127x01", "attempts": [
      {"directory": "/absolute/attempt-0", "manifest_sha256": "SHA256"}
    ]}
  ]
}
```

The context pins the reporting plan and committed END inventory. Every counted
host must be present exactly once. Every attempt is listed in chronological
order; at most one mechanically classified technical repeat is allowed. Use
the first passing attempt. A successful first attempt forbids a second attempt.
Native/belief/RNG exactness failures never allow repeats; Linux qualification
must be EXACT with zero discrepancy. Counted hosts outside ±5% fail the entire
END pool; none are silently excluded. Cross-host bindings include registered
slot 0, warmup, perception, plan nice and each host's launch slot count.

The mechanical failure rule is committed with E4 before any reference: only
typed crash/host loss, MHz-gate failure and validity-census failure are technical
repeat candidates. Classification grants no session authorization. A second
failure makes the reference unavailable pending an outcome-blind amendment.

For A6 only, use `kind: unpoolable-smoke`, a smoke-labelled pinned plan naming
the non-reporting host, reduced slots, synthetic completion/launch/MHz/census
evidence, and the reviewed real corpus. The same runner still performs real
backend/spawns, >=300 seconds warmup, clocks, census and sealing. It is rejected
by the production pool regardless of timing. This worker may execute it only
on 05 at nice19 with light load after the reviewed bundle is available.

T1 separately owns enforcing Amendment 1 in every outcome-release route:
committed pool-complete and registration commit/SHA are prerequisites, including
the fourteen-day escape. E4 receipts do not authorize outcome release.
