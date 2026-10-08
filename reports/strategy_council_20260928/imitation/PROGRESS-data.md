# Imitation data implementation (T0–T3)

Started 2026-10-08 UTC. Code is authored on 127x05; all execution is on 127x01/03.
No commits. Frozen runtime, extractor, roles and evaluation recipe remain read-only.

- T0: starting. The hub lacks `fleet/gpu_env.sh` and `gpu_check.py`; exact copies
  are staged in the new `imitation/t0/` directory, without replacing fleet files.
- T1: implementing deck-free public-event ledger and own cycle; oracle suite pending.
- T2: pending T1. Hosts 01/03, at most 64 workers each and 80 total/host
  (16 with console users). Output only under fresh `imitation/data/` paths.
- T3: pending T2; packed role stores and baseline scores, then LAN copies to 04/08.

T1 PASS published on 127x01 and mirrored to 05. 319,077 exact elixir comparisons,
2,015,370 known facts, zero conflicts. Includes 74,440 development (74,424 plus
16 terminal), 209,575 confirmation, 23,058 srp and 12,004 Collector (12,002 plus
2 terminal) checks. 8 Collector grants and 12 abilities. Five unit tests pass.
The full development suite took 484.77 s wall / 484.57 s CPU; detailed timings
are in `data/receipts/T1-PASS.json`. API is described in `DATA-CONTRACT.md`.

T0 PASS: installer `imitation-t0-env-20261008-r1` PID 3396798, exit 0;
GPU suite `imitation-t0-check-20261008-r1` PID 3397566, exit 0, 82.32 s wall /
91.26 s CPU. All required checks pass; torch.compile is the expected optional
failure on driver 470. Receipt: `fleet/imitation-t0-gpu-check-127x01.json`.

T2 pilot `imitation-t2-pilot-r2`, PID 3401417, exit 0: 48 perspectives, 37,821
rows, 31 non-header arrays logically equal plus exact header/summary equality,
zero elixir/hand/queue/refill/own-cycle violations. 287.02 s unit wall.
Output: `data/c56-sidecars-r2/`. Initial pilot r1 stopped safely on the extra
unsupervised terminal context row: the frozen hook omits it. The adapter now
captures the retained final battle after return; no frozen source changed.
No data deleted. No fallback needed.

T2 production running 64 workers each on 01/03 (128 total). This leaves at
most 16 other Clasher workers per host under the shared total cap. Node03 has
only 1,248 original units, so a complete read-only comparison copy is staged
under fresh `imitation/data/c56-input-v1/` on 03 from the hub; no C56 file on 03
is overwritten. Production output is `data/c56-sidecars-v1/`.

Production labels and launcher PIDs:
- 01: `imitation-t2-production-01-v1`, PID 3404410, partition 0/2.
- 03: `imitation-t2-production-03-v1`, PID 3398212, partition 1/2.
- Input staging/checksum: `imitation-t2-stage-input-v1`, PID 3404417, exit 0.
- 01 continuation: `imitation-data-finish-v1`, PID 3406691. Waits on the exact
  two production exit receipts, then collects 03 outputs, finalizes, checksum
  mirrors to 04, builds the store, computes baselines, copies/verifies to 04/08,
  and writes T2/T3 PASS receipts. Script: `finish_data.py`; resumable by a fresh
  fleet label. Status: `data/operations/continuation-status.json`; failures:
  `data/operations/continuation-blocked.json`.

Resume production after inspecting exit/log/PID (never duplicate a live label):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-LABEL .venv/bin/python -B reports/strategy_council_20260928/imitation/replay_sidecars.py --out reports/strategy_council_20260928/imitation/data/c56-sidecars-v1 --partition 0 --partitions 2 --workers 64`
For 03 use partition 1 and prefix the Python command with
`env CLASHER_C56_RECON=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/c56-input-v1`.
Completed units recheck all file checksums and audit violations on resume.

Header provenance decision ACCEPTED: COORDINATOR.md 2026-10-08 03:40 UTC.
independent `verify_header_contract.py` regenerated the authoritative global
header via the frozen writer and compared all 1,767 original archives. All
common fields match; 270 originals carry the historical v3 runtime SHA
`af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82`,
while actual replay is required v3b `1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493`.
The aligned replay retains original headers; actual provenance is in the
sidecar manifest. Evidence: `data/c56-sidecars-v1/header-contract-audit.json`.
The explicit exemptions are `extra.reused_v2_episode_ids`, `extra.v2_sha256`,
and `extra.runtime_sha256` (only the two pinned SHA values above). Every other
header/summary field must match; every array must match dtype, shape and C-order
values. Original headers stay unchanged. Successful v3b reproduction of the
270 v3-era units is additional determinism evidence, recorded in the audit.
The audit passed under fresh label `imitation-t2-header-audit-v3`, PID 3417927,
exit 0 (20 s wall): 1,767 headers checked, all 270 historical unit IDs recorded.
Six negative checks reject an unknown runtime SHA or changes to phase, shard,
part, extraction and an unexpected field. Receipt mirrored to 05 at
`data/receipts/header-contract-audit.json`. Production
and `imitation-data-finish-v1` continue unchanged. The verifier change does not
require their restart. T2 PASS still requires the full replay and checksum gates.

T3 code prepared (`build_store.py`, `packed_store.py`, `baselines.py`). Real
pilot-store smoke round trip passes all 45 retained perspectives/34,545 rows;
3 excluded_leak perspectives omitted. Final smoke: `data/store-smoke-v2`,
`imitation-t3-store-smoke-v3`, PID 3408585, exit 0. `passed=false` deliberately;
only `smoke_passed=true`. Earlier smoke found/fixed a duplicate manifest key.
Balance uses the minimum of the two frozen sqrt caps, not their product.
Three loader/metric/phase tests pass; `imitation-t3-tests-v2`, PID 3410068.
P16 upgrade/forward plumbing passes on one TRAIN perspective (589 rows, ten
recurrent chunks), `imitation-t3-p16-smoke-v2`, PID 3412437, exit 0, 25.11 s wall /
24.41 s CPU. Receipt `data/receipts/t3-p16-smoke.json` mirrored to 05.
The initial attempt failed the prescribed upgrader's descriptor guard: five
values across Goblins/IceSpirit/IceSpirits differ between checkpoint gamedata
daa58b28 and extraction gamedata 3d99987c. `p16_upgrade.py` copies checkpoint
descriptor rows into a private builder copy and then calls the unchanged
`contract_v5.upgrade_policy_payload_to_v5`. Every existing checkpoint tensor
(including descriptor buffers) is asserted unchanged after remapping. No
checkpoint or frozen runtime was modified; no held-out scoring yet.

Latest combined T2 checkpoint (03:18 UTC): 374/1,767 units,
17,468/82,231 perspectives, 13,913,748/64,140,802 rows, zero violations.
Still running, not qualified.
The 270-header provenance decision is accepted as recorded above.
Other workers must still wait for the actual verified `data/receipts/T3-PASS.json`.

Jobs use `fleet/fleet_run.sh`; labels, PIDs and resume commands will be recorded
here when launched. Logs and exit receipts: `/mpac/sdicks02/jobs/clasher/`.
