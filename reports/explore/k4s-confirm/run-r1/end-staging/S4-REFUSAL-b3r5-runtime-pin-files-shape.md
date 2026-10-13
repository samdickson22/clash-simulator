# S4 REFUSAL (b3-r5, production dry-run) — recorded 2026-10-13T05:02:24Z on 127x05

Tool: /mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r5/assemble_fleet_reference.py sha256 5c1c958e4fd769667fc48544145b9d8d938ddc7fbe62b3154dae60e6a6ab8543 (b3-r5 SHA256SUMS OK)
Interpreter: /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B, cwd /tmp, env -i, nice -n 19

## Runs (both --dry-run; nothing written; rc=2)
1. 127x03 pf00: --request requests/request-127x03-pf00.json 85e9c3859ee311e29deb6ad4ab88e4f174d1fe1f30dd1150762e5a93cb6f35f6
   --repository end-prep/repo-full (HEAD 98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb), --committed-admission x2 (bus 8dbe3d10…, idle 3bb3b2c6…), --out bundles/end-ref-127x03-pf00
2. 127x04 pf00: --request requests/request-127x04-pf00.json 60895f3ad0c71958317297ca777dd316f56bc7926abf53a119b4ffc6d12a5c95, --committed-admission bus e97b17cb…, --out bundles/end-ref-127x04-pf00

stderr (both, verbatim):
ASSEMBLY REFUSED: S1 runtime pin lacks a files list
ASSEMBLY REFUSED: S1 runtime pin lacks a files list

## Cause (tool defect, not request construction)
- assemble_fleet_reference.py:606-608 RuntimeInventory.members(): reads runtime/reports/explore/s1/receipts/runtime-pin-r2.json with its pin
  (S1_RUNTIME_PIN_SHA256 = f81f3655…, which it passed) and then requires listing["files"] to be a LIST of str.
- The pinned bytes (sha256 of runtime copy: f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d; git show P':same path: f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d)
  hold "files" as a DICT {name: sha256} (1557 entries).
- The frozen rule S4 mirrors, e4v3/prepare_bundle.py:42 runtime_pins(), does set(json.loads(...)["files"]) (dict keys) — accepts it.
- S9 (s3s9s10-r3/s9_end_runtime.py:355-356) REQUIRES a dict for the same file; S4's synthetic fixture
  (b3-r5/test_assemble_fleet_reference.py:144) writes a list, so the S4 suite never exercised the real shape.
- Because the shape is fixed by the pinned SHA, no request can pass: every production S4 run refuses at this point
  (after request/pins/names/--repository/runtime walk/measurement, before models). Host-independent (03 and 04 identical).

## Action
- Not worked around; no input edited. S4 branch STOPPED. Needs an S4 fix (e.g. accept the dict form as the frozen
  rule does: names = set(listing["files"]) for dict, with the same name gates) + Sol review + adoption before step 1 can run.
- Requests (6) remain valid inputs for the fixed tool unless its schema changes.
