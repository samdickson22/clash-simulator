**Partial preflight approval; reference procedure changes requested.** Read-only inspection found no further actionable source defect; all 506 manifest entries verify and match staged engine files.

One **P2 procedure blocker** remains: [reference_jobs.sh:54](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/tools/reference_jobs.sh:54) and line 75 verify sources/tools but omit `native.sha256`, contrary to HOST-PLAN’s before/after guarantee. Add native verification before reference work and before `reference.done`; gate’s later check does not satisfy that phase’s provenance contract.

Separate dispositions:

- **Build:** approved for the documented fresh 04 run.
- **Test:** approved unchanged 16-case procedure, after successful build.
- **Affected:** approved revised imports, controls and container/Freeze/continuation witnesses for execution.
- **Reference:** comparator accepted; launcher blocked by the missing checks.
- **Gate safety:** approved launcher design; execution remains conditional on genuine successful preceding receipts, including corrected reference.

Exact reviewed SHA-256 identities:

```text
source.sha256
7d68fdd82b92e62dfb875ba18cac8e10a1e6679cd115d3c8f188ae69a8c19d80
jobs.sh
5ceae3a6722ade9714e72cb4cd6a7e6b27ee186a9a229c1962d84fe6399ddcd3
affected.py
241fe52f0dae33d10095c1230064d36ef4a56f7f9c80261342a7780960ff74d1
first_update_paths.py
0f0f8604699c9b5c5564d77d32a9e12534b4e3f7689df3fd3512517b963efba0
reference.py
9da9790071b0dd0e23437be24944b97030db641c0a115a09b947b4c2613cb52d
reference_jobs.sh — changes requested
d02ad2e877a948d68c74f01e7ff2232cc56666e7d6c9769ffa6cc46bb7e43d2f
HOST-PLAN.md
e21f4622063e97f9c6f80e501d52cc9e26105b593dfc1fb5a254d26fb73b0c8b
```

Reviewed HEAD `1dab5bce4a550eb4a99e21558d62ab231db84b5a` plus fixed main `ae3f6b0c579c5c817630b92a64089917c6623704`. No scripts/imports/builds/SSH/jobs/edits performed; remote liveness and fingerprints remain supplied-record evidence.

This does **not** establish readiness: fresh combined 577/600 gates and final independent evidence review remain required, with existing partial-fidelity limits and B2-before-C1 order retained.
