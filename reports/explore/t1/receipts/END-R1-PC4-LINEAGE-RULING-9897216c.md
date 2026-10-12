
## 2026-10-12 08:29Z: Ruling R1 (PC4/reducer lineage = OP-7); landing and PC4 procedure

The basis is the independent investigation `END-PC4-LINEAGE-INVESTIGATION-r1.md` (T1 job dir).
- 2,361 of the 3,072 counted blocks (replacement r2/r3) ran under OP-7 manifest **488f6c8d** (ef4c073a, confirmation 1947830b).
- That manifest pins `ssh_sensitivity.py` bb124cc4, `reduce.py` aebb2017, and the OP-7 PC4 text 9b0704e2, which applies to both release routes.
- The committed sidecar 48730da5 was produced by bb124cc4 over a single root.
- Main's e643a342/fdea088c and the PC4 wording ff0b7afe are OP-6-era and stale for these blocks.

**R1 ruling:**
1. **PC4 CLI = `ssh_sensitivity.py` bb124cc4**, applying the OP-7 PC4 text 9b0704e2. e643a342 is rejected for PC4.
2. **Release reducer = `reduce.py` aebb2017**, run from main's lineage (which carries c5b2e059's barrier, release_reference and check_reference).
   - Its emitted sensitivity ledger must equal the PC4-checked sidecar in every field except `utc`.
   - Its results must include the prespecified `apt_sensitivity` and `ssh_or_apt_sensitivity`.
3. **Landing (no merge).** T1 makes a narrow commit copying the frozen bytes from ef4c073a to their canonical `reports/explore/t1/` paths:
   - `ssh_sensitivity.py` bb124cc4, `reduce.py` aebb2017, `apt_budget.py` c1578535, `cpu_accounting.py` 5ecae99d, `RELEASE-PRODUCTION-CHECKS-20261010.md` 9b0704e2;
   - plus `receipts/release-lineage-op7-20261012.json`, binding the landed SHAs to 488f6c8d and ef4c073a, OP-7 reviews r1–r3 and 1947830b, and disclosing that `FROZEN-T1.json` 24817e16 stays as the E4/r1 freeze and is stale for these files.

   Leave `FROZEN-T1.json`, `host_audit.py`, `ssh_budget.py`, `supervise.py` and every e4v3 file unchanged.
   - **Tests:** the reducer, op6, barrier, release_reference and reference_packet tests, plus the e4v3 suite, on the landing tree. Run the full `test_op7` on a `git archive ef4c073a` export.
   - **Tag:** ef4c073a is tagged `t1-op7-freeze-ef4c073a` (pushed).
   - **Review:** a narrow independent **Opus** diff review of the landing (T1 is a Sol worker, so Opus reviews), plus a 977c4dfb addendum.
4. **PC4 run.** An independent reviewer runs the CLI on hub 127x01, by read-only execution:
   - **Code:** extracted from `git archive ef4c073a reports/explore/t1` into a scratch directory outside every job root, with the SHAs checked against 488f6c8d.
   - **Interpreter:** the r3 job's cpython 3.12.13.
   - **Flags:** `PYTHONDONTWRITEBYTECODE=1 -E -s`.
   - **Root:** `…/replacement-frozen-op7-0108-r3/hub-blocks`.
   - **Ledger:** 866e6f7f.
   - **Pass condition:** the output equals 48730da5 except `utc`, with 3,072 entries (2400/600/72), IDs matching 50f24dd6 and 6f6f0007, and 2,361 v2 and 711 legacy.
   - **Record:** a reviewer check receipt binding the sidecar, ledger, inventory, complete-proof digest, CLI, source, interpreter and argv. T1 commits it verbatim.
5. **Freeze.** The four T1 job directories on 01 (`reporting-frozen-0108-r1`, `replacement-frozen-op6-0108-r1`, `replacement-frozen-op7-0108-r2`, `replacement-frozen-op7-0108-r3`), the host roots, the release roots and `end-received` are **frozen until release**. No moves, cleaning or rsync, and the hub mirror stays paused.
   - A durability copy of 01's counted blocks to a dedicated prefix on another clasher host comes in a separate ruling, after PC4.
6. **Then:**
   - R3 confirms that its pool check was run in the final `<R>`, a descendant of the landing; regenerate it if the prefix differs.
   - R5 seal and registration (registration still waits on the A4 Mac inputs: the builder's 03 read happens at the current K4S gap).
   - R6 barrier under e4v3-venv 3.12.12.
   - R7 production-packet review r2.
