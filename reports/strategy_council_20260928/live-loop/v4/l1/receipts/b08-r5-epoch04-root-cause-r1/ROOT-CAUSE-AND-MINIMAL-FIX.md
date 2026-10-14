# Epoch 4 r5 root cause and proposed minimal fix

Status: offline analysis only; perception PAUSED under coordinator commit 19693dcecc1caf90c8a949b4ff95c279af68af79. No r6 round, code repair, epoch retry, remote inspection, or new host action was performed. Package a0046c1d remains unchanged; all 446 manifest members rechecked.

## Evidence and cause

The owner retained epoch4 actual launcher/sender exits1/1 and an empty-artifact failure envelope (stdout SHA88680a43610e6373cf4d426a9fc3e115f0d327632cb963f6574ecba88aa724f5). It returned no epoch artifact or duration. The coordinator separately diagnosed remote stderr with its one read-only SSH: `b08_producer_claims.py:54`, `KeyError: 'sha256'`, reached through `epoch_inputs` → `ProducerClaims.verify`. That remote diagnosis is coordinator evidence; this owner did not repeat the SSH.

Local SHA-verified metadata independently explains the error. Contract `3b3ebc8f3e4e3f0eedd0c30de67c853b66b3cdb3c5b85287e6fbd485dea1d431`, schema `clasher.v4.vectorized-producer-contract.v1`, contains exactly one queue_plans record. Its SHA is the map key `96519baf3d20451c83a373ceb1cf118e8546f8aa3d948a16aaa921cd8078b56e`; its value is only a `path` record. The referenced overlay bytes hash to that key. There is no nested sha256 field. The r5 consumer at line54 assumes one and raises KeyError before overlay verification. This is a consumer/contract schema mismatch, not evidence of a host or transport defect.

Epochs1–3 each have64 retained original entries and bypass this vectorized branch, explaining why their real-input PASS did not cover the defect. The first structurally affected entry in sorted traversal is epoch4 `v4-phase-a-1975101328` (`e04-v4-phase-a-1975101328`). Exact runtime first-failure identity beyond the coordinator traceback is not separately claimed.

## All24 schema coverage

All24 pinned assembly files were hashed and enumerated:1536 entries total, 522 retained, 310 original queue, 704 vectorized queue. Every vectorized entry uses the same sole contract record and missing-field assumption. Affected epochs: 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24. These are static schema findings, not execution results for unlaunched epochs.

| Epoch | Retained | Original queue | Vectorized queue affected |
|---|---:|---:|---:|
| 1 | 64 | 0 | 0 |
| 2 | 64 | 0 | 0 |
| 3 | 64 | 0 | 0 |
| 4 | 56 | 6 | 2 |
| 5 | 54 | 3 | 7 |
| 6 | 0 | 18 | 46 |
| 7 | 26 | 30 | 8 |
| 8 | 0 | 49 | 15 |
| 9 | 14 | 10 | 40 |
| 10 | 53 | 0 | 11 |
| 11 | 23 | 3 | 38 |
| 12 | 9 | 1 | 54 |
| 13 | 20 | 1 | 43 |
| 14 | 0 | 0 | 64 |
| 15 | 7 | 57 | 0 |
| 16 | 0 | 1 | 63 |
| 17 | 7 | 3 | 54 |
| 18 | 21 | 0 | 43 |
| 19 | 9 | 0 | 55 |
| 20 | 17 | 0 | 47 |
| 21 | 14 | 0 | 50 |
| 22 | 0 | 64 | 0 |
| 23 | 0 | 64 | 0 |
| 24 | 0 | 0 | 64 |

Machine-readable per-epoch pins, counts and affected episode identifiers: `all24-schema-audit.json`, SHA `beefcc82c89a699b6e1a4e03017cba07ec4e5aacf2e7e1f966015763c09205ea`. All queue_plans records were enumerated, including checking the sole referenced overlay's bytes against its key.

## Proposed minimal fix, not applied

1. Correct the consumer to the existing frozen v1 contract schema. Validate queue_plans once as a nonempty mapping whose keys are canonical lowercase64-hex SHA256 strings and whose values are exactly the v1 `{"path": <canonical absolute identifier>}` shape. Validate every record, not only the record reached by a particular epoch. Do not add or fabricate nested hashes in frozen contract bytes and do not silently accept an invented alternate schema.
2. Replace line54's nested-field lookup with validated key membership. Continue `overlay = self.read(pin)` immediately afterwards: that resolves only through the owned authentication proof map and hashes the actual overlay bytes against the key. The historical contract path remains an identifier, never a direct access target. Preserve all following overlay/base-task/worker/source/qualification/registered-owner/independent-release checks unchanged.
3. Add an offline package preflight over all24 assemblies: each vectorized entry must bind to the pinned contract and one validated queue_plans key with an available SHA-matching overlay proof. This covers the entire704-entry class before any real-input epoch, without loading payloads or CUDA.
4. In a later authorized revision, regression coverage must include the exact pinned v1 path-only record, all24 assembly schema inventory, and negative cases for missing key, malformed key, nonmapping record, missing/invalid path, unrecognized fields/schema, missing proof and wrong overlay bytes. Retain negative scientific-binding tests for modified base tasks, worker/source/qualification and registered owner/release. These are proposed future tests; no new package or qualification claim is made here.

The smallest runtime change is the consumer-side schema check and membership correction. Rehash/review/issuance of any new package and decisions about prior epoch receipts are deferred to a later coordinator resume ruling. A schema-only correction cannot establish that later unexecuted checks will pass. G5 remains3/24; no reducer drafts or run authority arise from this note.
