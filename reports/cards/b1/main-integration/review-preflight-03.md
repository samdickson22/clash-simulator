**REFERENCE execution safety: APPROVED** for the documented fresh 04 run, after genuine successful build/test/affected receipts. No remaining actionable preflight blocker found.

[reference_jobs.sh](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/tools/reference_jobs.sh:54) now verifies native identity immediately after source/tool verification both before reference work and before `reference.done`. Serialization, duplicate prevention, process-group draining, CPU/nice limits, scratch-only writes, original/current source selection and shared stat overlay are consistent with HOST-PLAN. The corrected absolute old04 manifest binding is acceptable.

Exact reviewed SHA-256 identities:

```text
reference_jobs.sh
c584f793e557523b1837fe6ea01b71936e75a5a83d7faf45d0d6f6df0e8cf226
reference.py — unchanged from review02
9da9790071b0dd0e23437be24944b97030db641c0a115a09b947b4c2613cb52d
source.sha256 — unchanged from review02
7d68fdd82b92e62dfb875ba18cac8e10a1e6679cd115d3c8f188ae69a8c19d80
```

**Prior approvals remain applicable:** all 506 current source entries verify; jobs.sh, affected.py, first_update_paths.py and the original 16-case runner match their approved hashes. Engine/tool files are unchanged from source commit `5c8afc2d78cb9160c42cd2536f1588cc0dc98c6e` through reviewed HEAD `6cf7dbcfdeb029f84e9ded67add842179c2ba93e`. Diffcheck against fixed main passes.

This approves execution procedure only. Remote staging/liveness remains supplied receipt evidence; no scripts, imports, SSH, jobs or edits were performed. Fresh combined **577/577 + 600/600** results and final independent evidence review remain required. Partial reference fidelity, Rune Giant coverage limits and disclosed snapshot differences remain; no whole-state certification is implied.
