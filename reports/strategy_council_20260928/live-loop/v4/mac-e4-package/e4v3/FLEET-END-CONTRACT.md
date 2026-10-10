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
    "admissions": {"system-bus-admission.json": "guard-admissions/system-bus-admission.json"},
    "seed_inputs": {"reports/explore/t1/receipts/op5-parent-source-127x08.json": "seed-inputs/reports/explore/t1/receipts/op5-parent-source-127x08.json"}
  }
}
```

`end-evidence.json` replaces the free-standing three-Boolean END marker. Schema
`clasher.e4v3.end-evidence.v1` contains `kind: counted-reporting`,
`repository: /absolute/local/committed-repo`, `completion: ARTIFACT`,
`blind_ledger: ARTIFACT`, `counted_inventory: ARTIFACT`, and
`phases: [{host,phase,launch:ARTIFACT,supervisor_exit:ARTIFACT,
mhz:ARTIFACT,census:ARTIFACT}]`. Each ARTIFACT is
`{path: relative-bundle-path, repository_path: relative-repo-path,
commit: full-40-hex-commit, sha256: full-64-hex-SHA}`. The runner verifies bundle
bytes against both SHA and committed Git bytes. All paths also appear in
`tiers-pins.json.files`. No SSH or outcome files are read.

The committed completion is the object used by T1's release barrier: Boolean
`reporting_complete` and `outcomes_sealed`, `counted_primary_blocks: 2400`,
`counted_guard_blocks: 600`, and `completed_at_utc`. It additionally binds
`counted_host_phases: {host: [reporting, replacement-r1, ...]}` and
`blind_ledger_sha256` / `counted_inventory_sha256`, matching the corresponding
ARTIFACT hashes. All counted phases and every ledger loss's source phase must
appear in `phases`; additional source phases with no counted blocks are retained.
Hosts/phases must be allowed by the pinned plan, and the counted host list equals
its `reporting_hosts` (or all allowed `compute.hosts` when that key is absent).
The counted inventory's actual
host/phase set must equal `counted_host_phases`. Launch slots must equal the
host's profile for counted phases. Completion is after all supplied raw exits.
T1 supplies the health-only inventory; E4 never derives it from game outcomes.

**Stopped phases are accepted.** Preserve verbatim `supervisor-exit.json`,
including its `reason`, `completed`, `failed`, and `unstarted` descriptors.
Valid counted completed blocks survive an 08 B-window drain, failed work or an
unstarted queue. Do not turn those exits into pristine successful exits. The
committed blind ledger is T1's existing `{utc,sealed:true,events:[...]}` from
`replace.py`; each event retains `{utc,lost,replacement,reason,evidence_sha256}`.
Every loss binds the exact raw descriptor and exit SHA. Failed descriptors must
be in this ledger. Never-started redispatches keep their original logical IDs;
their eventual exact completed exit membership proves counting. Lost IDs cannot
be counted. A replacement retains population, cell and logical `replaces`;
host/dispatch can change during blind queue redispatch, and all other descriptor
fields must equal its ledger assignment.

`counted_inventory` is a committed health-only JSON object with **exactly**:

```json
{
  "schema": "clasher.t1.counted-blocks.v1",
  "outcomes_sealed": true,
  "blocks": [
    {"host": "127x08", "phase": "reporting", "descriptor": {"id": "primary-0002", "population": "primary", "host": "127x08"}}
  ]
}
```

The example is abbreviated; production has the full original primary0000–2399
and guard0000–0599 logical population, exactly once, plus any counted descriptive
blocks. Each row has exactly `host`, `phase`, `descriptor`, matching a verbatim
raw exit's completed descriptor. Descriptor fields are T1's public schedule
fields: `id,population,index,seed,cell,seat,own_index,opponent_index,order,replaces,
dispatch,host`; unknown/outcome fields are refused. No games, outcomes or complete
proof contents are consumed by this runner. These checks preserve **every counted
host**; a counted host's failed/outlier reference fails the pool.

All reporting/replacement MHz and census files are retained verbatim. Join on
the exact UTC string within each phase; only `inflight == launch.slots` rows
enter reporting MHz. A raw stop reason does not discard the phase or its
full-occupancy observations. Missing/duplicate joins fail closed. The signed reference
to reporting mean ratio is retained in host, pooling and registration receipts.

The guard source tree contains frozen T1 `common.py`, `host_audit.py`,
`idle_services.py`, `system_bus.py`, `ssh_transport.py`,
`perception_confirmation.py`, `owned_supervisor.py`, `ssh_budget.py`, and
`parent_source_seed.py` (including its reviewed 08 join), pinned
against `guard.freeze.files`. The guard uses existing approved job admissions;
their staged copies are pinned and compared against live job bytes. No admission
identity is silently refreshed. Every existing owned-supervisor, copier or idle
admission is also pinned. Use an approved distinct reference job namespace; keep
its admission bytes immutable. E4 extends own-process accounting to its explicit
PID/start descendant tree using the frozen OP-3 full identity fields; a stale T1
job/argv predicate never grants E4 ownership. The frozen census invokes OP-2
confirmation and OP-6 source-bound SSH-family classification. All nine modules
must match the **final reviewed frozen** source inventory; an older OP-1-only
freeze is insufficient. Frozen `operational_delta_op5`, `operational_delta_op5_08`
and `operational_delta_op6` must each say `CONFIRM`. Local wiring tests use
admitted freeze aeeb3003 / OP-6 d60586b3, never the mutable shared checkout.

Before the first census, call **the frozen**
`parent_source_seed.admit(job, current_rows, ssh_budget.FAMILIES)` exactly once.
This is the same Families instance used by the frozen census. The reviewed
module verifies committed seed bytes, exact parent generation/source fields,
and the 08 server/04 client socket join. E4 does not recreate the join logic.
New generations, conflicting evidence and unknown sources receive no seed;
later revocation is not undone by reseeding. The accepted rows and raw
`parent-source-seed-admission.json` are SHA-sealed with the reference.

The live `guard.job/FROZEN-T1.json` must exactly match the staged `guard.freeze`
SHA. `guard.seed_inputs` is an exact map from every frozen seed/dependency's
repository path to its relative bundle copy (the JSON example above is
abbreviated). Include **both** frozen parent-source receipts and the 08 seed's
`source_join.server` and `source_join.client` receipts. They must appear in
`tiers-pins.json.files` with the frozen binding hashes and exist byte-identically
under `guard.job/repo/<repository path>`. Seed/join validation is delegated to
T1's frozen method, including its full commit/SHA/Git-byte checks. Neither the
job freeze nor staged/live seed dependencies may change during the reference.

Reference admission precedes loaded workers and measurement, then independent 1 Hz observations use T1's
frozen `ssh_budget.sample` and `stop_reason`, measuring elapsed time **after**
confirmation. Foreign compute/activity, **any positive console user**, owned
STOP or MemAvailable <24 GiB stops the attempt. The frozen OP-6 methods govern
operational SSH limits: source-proven LAN families stop above 150% of one core
in a sample or above 10% average after >=60 seconds; pure-idle service caps stay
at 25% per sample and 2% average after >=60 seconds. Equality passes. Unknown or
non-LAN source evidence stays under T1's identity fallback. OP-1 identity and
CPU meters remain active. Every foreground 50-state warmup/speed/deadline work
block additionally uses frozen `begin/update/finish` SSH meters. Each meter sums
host-wide eligible SSH-family exposure, including approved idle families, while
all other reporting slots remain loaded. Checkpoint IPC and census run outside
individual decision timers; block boundaries are fixed before results. A block
checkpoint preserves the previous independent 1 Hz sample; it does not create
an artificially short burst window. **Reference validity remains STRICT:** any
SSH/idle or dbus block flagged above 0.5% cannot qualify even if OP-6 allows its
reporting completion or has not reached its operational-stop duration. Retain
every failed attempt; do not remove flagged blocks or relax their thresholds.
`GUARD_RULES` is `frozen-t1-op1-op2-op3-op4-op5-op6-v1`.

SHA-sealed `guard-admission.json` retains the pre-load admission, and
`guard-blocks.jsonl` retains begin/end identities, full per-block CPU
meters, source/child commands and flags. Pooling requires all 72 speed and 144
deadline blocks plus warmup, and refuses incomplete/flagged meters or missing
OP-6 sample evidence. `capacity.jsonl` retains every 1 Hz guard result. Raw
allowlist/confirmation/SSH-family/parent-seed admission files are copied to `guard-sources/`
on success or failure. END receipts also copy verbatim completion, ledger,
counted inventory and all phase sources under `end-sources/`.

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
the coordinator-assigned T1 host outside its reporting windows, the host's pinned slots,
synthetic completion/launch/exit/ledger/counted-inventory/MHz/census
evidence, and the reviewed real corpus. Offline smoke staging retains every
original production source byte; its derived synthetic host01 counting IDs are
explicitly unpoolable and never describe T1's production ledger. The same runner still performs real
backend/spawns, >=300 seconds warmup, clocks, census and sealing. It is rejected
by the production pool regardless of timing. The coordinator assigns the host
and window with T1, and supplies the reviewed bundle path/manifest SHA before
this worker accesses the host. Use the assigned host's pinned plan nice level
(current T1 nice10). Launch through T1's approved detached mechanism so the
launching SSH closes before admission; observe only through its approved
health-only copier. No ordinary SSH inspection during timing. The earlier
Linux05 dry-run receipt does not satisfy this real T1-host fleet-mode smoke.
Coordinator 19:45Z supersedes the earlier time projection: the clean END
window is expected **Oct11, after perception serial and A2 finish, around B**.
The 04→03/08 transports must be gone and 08's HTTP cache service retired.
The coordinator will declare the actual window explicitly. No reference or
timing-host access is attempted before that declaration; a projection is not
authorization. A6 remains assigned to127x01 before production references, with
review of its result and this code still required. [A6-END-RUNBOOK.md](A6-END-RUNBOOK.md)
contains the staging/measurement commands and result-review handoff.

T1 separately owns enforcing Amendment 1 in every outcome-release route:
committed pool-complete and registration commit/SHA are prerequisites, including
the fourteen-day escape. E4 receipts do not authorize outcome release.
