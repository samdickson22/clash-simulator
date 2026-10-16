# R26 independent Sol-high source review

2026-10-16. W = `/mpac/sdicks02/repos/clasher-bot-levels` on05; J = `/mpac/sdicks02/jobs/clasher/bot-levels`; C = `J/level-configs/50d22f86b3590abc` on01. Scope: R25-P2-1 correction and matching-byte closure of the otherwise accepted R24 source/restoration approach. Only this report was written.

**Decision: APPROVE MATCHING BYTES for the bounded correction. R25-P2-1 is closed at source level.** Parent may proceed with reviewed-source sync, deployed-hash verification, exclusive exact-byte restoration and the sequential bounded validation below. This grants no test/native/physics PASS or primary readiness. No unresolved source blocker was found within this scope; all execution obligations remain.

Read the complete R26 response first, complete R25 review and original R25 brief; R24 implementation receipt, all 780 patch lines, repair brief, authorized Astra response and bounded Astra audit. Inspected current harness/helper/config definitions and import dependencies, original failed integration evidence and good/bad support bytes, R12/s27 identity anchors, current handoff/progress context and existing launch environment. No project imports, parsing/compilation, tests, Runtime construction, native/CPU work, sync, restoration, frozen/live/input writes, descendants or input tools. Read-only SSH01 supplied cache/launcher hashes and output-path existence evidence. No applicable AGENTS.md was found in checked ancestors or the reviewed levels subtree. No unrelated strategy/physics audit was repeated.

## Correction and exact closure

`test_harness.py:14–15` now imports `fixture_support` at module collection, before the function-scoped `level_cache` fixture can replace `configs.LevelConfigs` with its constructor lambda (`:458`). `fixture_support.py:12,118` therefore imports the real class and binds `FrozenLevelConfigs` to it first. Later `run.py:378` obtains the already-loaded formatter module in the check11 mismatch branch; it no longer first creates a subclass of the lambda. This directly addresses the cold selected-test failure mechanism without requiring placement collection. The conclusion is source reasoning, not an executed reproduction.

The added import is safe for this clean invocation: helper module scope uses stdlib imports, config definitions, literal pins and function/class definitions. `configs.py` module scope sets constants/a Path and defines functions/classes; exporter, native and Runtime imports remain inside callable bodies or guarded main. Class definition/default binding does not call its constructor or cache methods. No builder/spell registry access, registry reset, disk read/write or Runtime construction is introduced by the added import. Existing bank/profile/report/run imports do not introduce an earlier actual Runtime. Primary's lazy formatter import is unchanged.

Independently hashed all 26 R24 manifest entries: **25 match exactly; only test_harness.py differs, exactly as declared.** Removing just the new comment and `fixture_support, ` import token through a read-only text stream produces the old harness SHA `7c90ca56835740ac64ed7a6b9fb512eb9d7938ba2ba9b0fc268e4371d33986b7`. Current harness independently hashes `5e95f8ce4744ce113d102cbc48dd675eb778a60180b5b722cd02b3f6abb559c0`. Thus all remaining harness bytes, including all nine mismatch cases and no-write assertions, are unchanged.

The nine cases remain missing, malformed, stale_reference, stale_comparison, missing_card, duplicate_card, wrong_unsupported, numeric_L11_difference and side_table_difference. They still require the intended ValueError, forbid Path writers and original supported/build methods, assert no installed `_level_configs`, and compare the complete synthetic cache bytes afterward. No TypeError acceptance, skipped case or weaker guard was introduced. Valid preload read-count/memory-only checks and raw-identity/resume checks remain intact.

R25's other accepted source conclusions stand at matching bytes: semantic timed WAIT checks, actual Runtime-first integration, immutable existing-only caches, exact field/type/units diagnostics, primary preloading before resume/forks/roots, both-seat actual B fairness/root/act paths, recorder and provenance coverage. Existing placement/probe/dependency hashes remain unchanged, permitting reuse of the prior v3 proof only within its existing limits. Failed R21 integration remains 179 passed/12 failed; prior probe/native/s27 results do not close current integration.

## Restoration accepted; parent only

**Accept the exact R25 fixed-path restoration sequence**, including its scp proposal and atomic sibling-copy/rename block, in `gates-review-sol-r25.md` at SHA `0d06b0a43245be3697bcbb1b6170fe963f3f049a216b6755a1c2272db45da4f4`, with all before/after checks and stop conditions. Its former source-review hold is satisfied by this verdict, conditional on deployed matching bytes and renewed exclusive parent preflight. No restoration was performed here.

Read-only01 hashing still finds current supported.json equal to preserved bad SHA `4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41`; all six exports match the raw manifest below. Candidate independently hashes to the original R12/s27 support SHA `e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc`; their stored canonical support pin is `b97c2a61edd7fedc37182320a143673012f34e5b35e34effd69eb99d1aded8e7`. Original reference remains `193b6615e3a1b7c13da664243e8d70050a35e5531ef12d2bbe1a92390e97865e`, 121 cards/empty unsupported/native-json-v1. No empirical one-field-only reconstruction of failed f008… is claimed.

Preserve raw failed log/support, candidate and all seven cache hashes. Recheck no owned jobs/exporters/writers and resource admission; sync only reviewed changed sources; verify the full deployed closure with the corrected harness hash. Refuse occupied destinations, changed source/cache hashes or temporary-copy differences. Copy candidate to distinct receipt, guard current bad hash, snapshot bad bytes to fresh guarded path, capture/compare all seven before hashes, verify sibling copy, atomically publish only exact original support, verify support plus all six exports and capture `cache-restored-r25.sha256`. No exporter, recomputation, normalization, changed low-level error or new baseline. All r25 output/restore destinations checked on01 were absent, including the temporary sibling; parent must recheck immediately before use.

## Sequential bounded commands — text only

Use the R25 preamble and restoration block exactly: existing env.sh, owned runtime `J/runtime/live16402b-r2`, evaluation/LEVELS_RUNTIME absent or resolving there, proof SHA `276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf`, original bank SHA below, `set -euo pipefail`, noclobber and fresh paths. Execute on01 only, nice10, math1/GPU hidden/hashseed0/bytecode off, existing launchers/leases/full-pool priority and overall16 process cap including parents. No new host script. No source/cache/input/runtime changes during jobs; no heavy05/09–18/03 retry. Inspect terminal status, full receipt and all-seven cache checks separately between stages; any failure, timeout, admission deferral, skip or incomplete receipt stops dependent stages. Never automatically advance/retry or resume failed outputs.

0. **Mandatory cold isolation first**, fresh process collecting only this nine-case node, CPU1/outer5m. No placement collection or TypeError waiver. This directly exercises the corrected dependency; an additional whole-harness isolated run is not required for this bounded fix because all other bytes match and all affected mismatch branches are selected.

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -p no:cacheprovider 'bot/levels/test_harness.py::test_preload_bad_support_or_L11_never_repairs_cache' > "$LEVELS_RECEIPTS/pytest-preload-isolated-r25.txt" 2>&1
```

Require terminal0/all nine cases, intended exceptions and all no-write/cache-not-installed guards. Verify restored cache hashes before proceeding.

1. Fresh five-file actual integration, CPU1/outer15m:

```bash
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > "$LEVELS_RECEIPTS/pytest-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-pytest-r25.txt"
```

Require terminal0/no mandatory skips, Runtime once before builders, actual Fireball688/159 and Poison92/21/reference193b…/121 exact check11 before roots; six raw/canonical pins and L4 Fireball357/83; all real actors/candidate/fallback/proposal/recorder assertions and BOTH hidden B root/act paths with positive roots/zero FAILURES. Preserve every existing no-write/resume/provenance regression. No predicted suite count.

2. Only after inspected integration PASS, native gates, CPU2/outer15m:

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > "$LEVELS_RECEIPTS/gates-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-gates-r25.txt"
```

Require terminal0/all prior254 substantive obligations plus new fences (explain count changes):121 exports,13 towers,32 public bodies,30 each cut/snapshot/raw-fc, A→B→A distinct/reused content keys/shipped[1,2,2], four fair actual B decisions/positive roots. Read both full raw snapshot diffs. Only prior source-proven absent empty String defaults may normalize; no numeric/type/entity/order/position/owner/qualified-key waiver.

3. Only after integration AND native PASS, original four-case clean all11, run.sh2/max3 Python processes/outer15m:

```bash
test ! -e "$LEVELS_RECEIPTS/all11-placement-r25"
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out "$LEVELS_RECEIPTS/all11-placement-r25" --arms A,B --all11-gate --start 0 --count 4 > "$LEVELS_RECEIPTS/all11-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-all11-r25.txt"
```

Require eight unique complete clean terminal rows, four full-command hash pairs, both seats/controllers, all four positive B roots, parent+children exit0, exact reviewed source/runtime/proof/data/raw-token/cache/env/scope/prior identities, complete both-seat command_events and zero errors/rejections/native/child/placement failures. Command equality with rejection remains FAIL. Never resume R12 or another failed output.

4. Only after accepted runner completion, report, CPU1/outer5m:

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report "$LEVELS_RECEIPTS/all11-placement-r25" > "$LEVELS_RECEIPTS/all11-placement-r25-report.txt" 2>&1
```

Require registered completeness/provenance/quality PASS. **No primary BASE/bank/outcomes until cold isolation, full integration, native, clean all11 and report all PASS at reviewed matching bytes.** Existing100-case×A/B/B0 authority/pre-outcome registration/conditional population/serial crown-controller interpretation remain with parent. No extra diagnostic, s27 rerun, new strategy requirement, LIVE promotion or physics claim.

Rollback/evidence obligations from R25 remain: retain failed receipts and good/bad support, handoff patch and saved pre-R24 bytes/durable parent backup. Reverting only this correction returns known-unaccepted R25 source; selecting older failing sources does not authorize execution. Experimental rollback selects standard A/removes experimental hooks without changing original prior/frozen pins/models. No automatic bad-cache restore, arbitrary kill or deletion.

## Reviewed exact source manifest

Relative to W; all hashes independently checked. The historical R24 manifest itself remains unchanged, with its old harness entry intentionally superseded only here.

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  bot/levels/__init__.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
674bf0fbb966c6e0a8ded4805ae615a3187ae25e13a5eab3fd32463a033fe4f4  bot/levels/fixture_support.py
d59475d3b4cf44983541a497d9a96106d4fe3023ea540a2fbde9fc38bd8cf41f  bot/levels/gates.py
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  bot/levels/placement.py
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  bot/levels/placement_probe.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
29d6509ec18452ffe3d535b1f91afed9d84cea61be38b42a79f5a942faa8850f  bot/levels/run.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
5e95f8ce4744ce113d102cbc48dd675eb778a60180b5b722cd02b3f6abb559c0  bot/levels/test_harness.py
3fe16baa155120959ce541a78e4b24fba6336855296eb14981db305758fc7bc9  bot/levels/test_placement.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
```

## Reviewed receipt and cache anchors

J-relative, raw SHA256. Complete R25 context/constraints are incorporated at the pinned review bytes; this review supersedes only its source hold for R25-P2-1.

```text
52e8537a74d94c45e08797221a28610280328a9e1056e693c38b2dfa5ad28d48  gates-r26-response.md
0d06b0a43245be3697bcbb1b6170fe963f3f049a216b6755a1c2272db45da4f4  gates-review-sol-r25.md
ee4f9443dc873cc798e6a0734166fa2181143f189cb15dd31dc279a0e86a4112  gates-r25-review-brief.md
c857fa061b3de69ffacdd1712e12bde25858263152c64c78f749f53703636dfc  gates-r24-repair-brief.md
1ebcc9a5f000737eb1e789d4e73872c78c1f92b29663dee855d894af7e16f164  gates-r24-astra-response.md
99cce4d024a66c5033ebdc81ffdc3ae985cf2f1cc85afd84b3a50ed8a8115ed4  gates-r24-implementation.md
7298068407d2ee9ec3abbe8f62abcd63569946f84ce64b152bb531cbc5c3daa6  gates-r24-implementation.patch
eec161f8aa8eec743233658ba9f7e67c846c3f1a9f1384d06d0b0567bc452b63  gates-r24-source.sha256
df8ad6a76e257c02fb310648beeaa1720aa371cdc6ea3337109a1f096e263505  fireball-bootstrap-astra-r24.md
219700e61efcf489939f5377ed02940772f99c2031ff0f050a087705e1e25455  dev/pytest-placement-r21.txt
4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41  dev/supported-after-pytest-r21-failed.json
e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc  dev/supported-restoration-candidate-r24.json
276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf  dev/placement-micro-r21.json
b2b3036e7c757d78664fd98c33c3b6397fe2e7b6d46ecd5708967a0b9b12b6d6  dev/all11-r12-launch.json
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  dev/env.sh (also directly hashed on01)
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh (on01)
```

Approved raw cache manifest, independently matched on01 except support, which remains the preserved bad hash above. Canonical pairs remain exactly the R25/helper/R12/s27 pins; no JSON reserialization was performed here.

```text
e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc  supported.json (restoration target)
bd77caea134e469c89dc1d25d60f30474a404feef6b529d26b0e307a8f3a7d95  L4.json
e88a6e04183f449754775b7f9d999c2ca3982601cb6f35dbbc1aec28d1555dfe  L5.json
ad4b725b180cb2aa0abf50c13cf378ba2a954233eac43080b248f2f40146dcbb  L6.json
8fc9633bbd50906d7f95575b7c93ba6a39e540aec2997f67c2d50b8a1477b6f3  L7.json
88a2472e54b090853bd18016cdafda642aafa1fd00f03ca6e7fa20f3edd638b2  L9.json
1a36f377d55be3ea34e20225aa17eb92bead8e148b216b5b1346f0e7d04c8a94  L11.json
```
