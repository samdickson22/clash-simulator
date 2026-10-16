# Sol r6 — gate fixture review

**Verdict: CONDITIONALLY APPROVE the single bounded default-gates execution on 127x01. No execution was performed by this reviewer.** First verify the deployed `bot/levels/gates.py` matches SHA256 `51d4c1f72e6ebd71feb60b754055b1d41d727001578874a36597f1bb110a55ba` (562 lines), together with the reviewed dependencies below. No source-level blocker found for this diagnostic command. This is not a passing-gates receipt or pilot-launch approval.

Reviewed `/mpac/sdicks02/repos/clasher-bot-levels` at HEAD `f85c66d375a949e007d9aeff6983c3f028c64b50`, including the uncommitted fixture, original r1/r2 findings, owner responses, current DESIGN/PROGRESS/SCOPE, and relevant config/root/player/scope, rollout/pool, player and RoyaleSim APIs. Only this report was written; no implementation edits, project imports, tests, synchronization, jobs, remote execution, commits, GPU work or delegation. Reported 121/121 mapping, 13 tower checks and four regression passes remain owner evidence.

## Findings and resolved objections

- **Existing-cache boundary is appropriate for this invocation** (`gates.py:37–64`): all paths are checked before loading; levels are 4/5/6/7/9/11 for the default gates, augmented by the actual estimator; the injected instance refuses builds, including later requests. Completeness requires every expected card to have either data or an explicit error. The exports gate additionally requires exact L11 card coverage and complete successful native-JSON comparison (`:94–108`), closing the partial-cache false pass. Lower-level recorded errors are not declared usable support. Common scope installation occurs before player creation, verifies fixed population counts/digests and idempotence, and the factory applies that same scope.

- **Exact public-root fixture now exercises the requested API** (`:228–304`): real public templates, both seats/owners, troop, ordinary projectile, tower buildings/projectile, qualified Fireball carrier, Tombstone and its child. Expected HP/damage/payload fields come from raw exports, with explicit tower expectations. Exact body/leveled/tower/unmapped counters prevent silently omitted rows. Native snapshot comparison checks the reconstructed fields and spell name. This addresses the prior tower-shot and missing-body coverage objections. It is selected-field coverage, not exhaustive equality of every mechanic field.

- **Cut fixture is substantive** (`:307–359`): accepted deployments precede deterministic pre-impact capture; exact Musketeer fields, a live qualified Fireball, reachable Tombstone and exact production/death tables are required in the actual cut. The old legacy recut is absent. Full, cut and snapshot-rebuilt roots are independently rolled out with ten actions over 80 ticks per trial. `batch_rollouts` clones roots, so successive comparisons preserve the reference fixture.

- **Actual cache transport is covered** (`:362–425`): one Linux fork child receives matching B native metadata; production `begin(base_cut=True)/submit/collect` is used. Explicit A→B→A requires distinct A/B content keys and final A reuse with shipped sizes `[1,2,2]`; all 30 pooled values are compared with their own uncut references, alongside 30 cut and 30 snapshot values. Missing results, errors or pending chunks fail. This proves bounded scripted raw-fc transport if executed successfully; it does not establish learned-opponent equivalence, pooled LIVE initialization/recovery, or arbitrary cache eviction behavior.

- **Fair-information fixture now makes decisions** (`:464–518`): actual RoyaleSim resets vary only hidden opponent levels 5 versus 7, require complete public-information equality, and run actual B roots and acts for both seats. Each act must call B's root, leave `FAILURES` unchanged, and match action/wait. This is one initial public state per seat with no enemy deployment; broader revealed-state invariance is not established. Separate synthetic roots cover observed bodies. No hidden-profile input into the factory was found.

## Execution conditions and interpretation

Use the existing reviewed environment and wrapper, a fresh distinct receipt, and no overlapping exporter:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-all-r6.txt 2>&1
```

Run only on 01 with the documented pinned runtime, GPU hidden, threads one, hash seed zero, bytecode disabled, and pool start unset or `fork`. Maximum two Python processes: parent plus one cut worker; other gates are serial. The pool is closed in `finally`; close joins for one second, kills a remaining worker and joins again. Collection has a 30-second deadline; the outer timeout bounds admission and native work, with group termination followed by kill. A native hang may prevent an in-process summary; timeout/nonzero exit or absent summary is failure, never acceptance.

Require exit zero, all seven gates represented with substantive check counts, no failures, roots 32 bodies, cut counters 30/30/30 and sizes `[1,2,2]`, fair four decisions and positive root calls. Preserve failed receipts. Forced-all11 command-hash parity across seats/controllers and launcher/provenance acceptance remain separate mandatory prerequisites before drawing the pilot bank. Accepted serial metadata and common-prior semantics need no renewed blanket Opus hold; no pooled LIVE claim/deployment follows.

## Additional reviewed SHA256

```text
configs.py  9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3
root.py     4ec56d835fd85a055926ccc77e71cf328024291caa0e67addb57adea19aac394
player.py   5eab866d622b8024f8b3c2f698996c972335e2adcbdcbdfd7007f0565503768d
scope.py    0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2
bot/search/lopp_fast.py dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b
bot/search/lopp.py c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8
bot/players/royalesim_match.py 321d9e45068c84fa07603995bbb137f803ffcc3377733f57748627bca7a7d19d
DESIGN.md d5b5044217d270f5a9276ba4ea0c5f8463d393d7e69982f139b7ea8fad5e66dd
PROGRESS.md 4494f79de90708608bcc7e2be47da70731becbd24dc1667ceaae4b73db63a052
env.sh      b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc
cpu_job.sh  e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949
```
