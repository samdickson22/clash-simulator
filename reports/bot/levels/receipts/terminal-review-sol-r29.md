# R29 independent Sol-high source review — command closure and native HP drain

2026-10-16, source-only review on127x05. W=`/mpac/sdicks02/repos/clasher-bot-levels`; J=`/mpac/sdicks02/jobs/clasher/bot-levels`. I did not implement these bytes. Only this review receipt was written. No project imports, project parsing/compilation, tests, simulator/native/model/Runtime execution, sync, cache/input/runtime/live writes, descendants or input tools were used. Read-only SSH01 inspected source, embedded API text, hashes and destination existence. No applicable AGENTS.md was found in checked ancestors or the reviewed subtree.

**Decision: APPROVE MATCHING BYTES for the three-file R28 repair and the individually inspected bounded validation sequence below. No blocking source finding (P0/P1/P2) was found.** This closes the source-review prerequisite, including approval to execute the new terminal probe/fixtures under that sequence. It establishes no runtime/test/native PASS, new-bank readiness, strength result, confirmation decision or deployment. Parent must stop dependent stages at any failed assertion, timeout/admission expiry, incomplete evidence, unexpected mandatory skip or hash discrepancy. New code bytes require a new fresh independent review.

Read the complete R28 implementation brief, completed13:16UTC handoff, focused653-line patch and109-entry manifest; original R29 brief; full R27 terminal/API audit and its API/public-facade/disassembly excerpts; stopped-run and first-failure receipts, complete stop and parent audits; actual B/case0 command/queue/final-score fields and every rejected event in all four affected rows; current DESIGN/PROGRESS/RESULTS/HANDOFF; R26/R25 reviews and response, and R24 bootstrap-cause audit. Reviewed every new function and changed production branch, relevant unchanged identity/queue/error/report/Runtime/bootstrap/import contracts. A regenerated focused patch from the saved pre-R28 match and both complete new modules compares byte-identically with the supplied patch.

## Source assessment and prior responses

1. **Public phase, validated rules and clock — source response accepted.** `bot/players/royalesim_match.py:51–88` reads the compiled ledger and the actual Battle's documented JSON-text overrides once. It binds tick milliseconds, regulation/overtime seconds, tiebreak and BATTLE_END; requires positive integral exactly representable periods; rejects malformed API/unknown rules/replay-only endings; validates exported durations, integer tick, boolean flags and active overtime consistency. The predicate uses actual public durations and overtime, with no production6000 literal and no hidden/legalmask oracle. Other three documented tiebreaks retain no early freeze. `:112–114` binds before Translator construction/player.start; `:133–136` validates refreshed native clocks. This is an intentionally bounded supported-schema contract; contradictions must fail, not receive a fallback.

2. **Guard placement and truthful queue accounting — source response accepted.** `royalesim_match.py:208–221` checks closure before `ready`, physical hand access and execute. The closed branch cannot reach either actor's information/own_packet/act/submit, command hash, play log, rejection counters or finish. It snapshots exact submitted/due/action/card/cost plus not_dispatched/reason for both real queues, distinguishing public expiry from first observed closure. It then advances only empty native commands at the normal poll boundary; pending due times never participate in this branch. No physical mana was debited and no refund/cancellation/rejection is invented. Pending reservations remain in the actual queues through `diagnostics()`, whose frozen contract requires submitted=executed+pending. The explicit second phase check at`:239–240` also precedes polling after execute/refresh. Preclosure execute/event/hash/finish semantics are unchanged.

3. **Final scoring — source response accepted, execution unproved.** The loop still runs to real native game_over or the existing safety cap. `royalesim_match.py:275–289` returns native winner/draw/crowns/all six HP/tick/state_hash; closure is additive operational diagnostics. No6000 terminal label or approximated score was added. Earlier normal crown/king endings retain their natural pending-at-end semantics. A safety-cap result remains nonterminal and the unchanged row validator rejects it. There is no GAME_OVER allowlist, historical event filtering or weakened rejection/native/exit/completeness/provenance rule. Both seats/all A/B0/B arms use this same common loop.

4. **Pinned API and evidence boundary — accepted.** Read the shipped calibration's match rule and binary-embedded step/state_json/calibration_overrides/client_arms/save/load/state_hash documentation. Step applies commands to the current state before advancing; save is an exact snapshot, load restores its own calibration subject to catalogue/territory compatibility. The fixture's bytes(save)/load and initial state_hash equality are supported; no imaginary clone API appears. Direct01 hashes remain binary97e03055…/calibration4c7c3d95…. Public facade and mock-engine/test source at RoyaleGym HEADab0df8ff… corroborate closure and the input6067/6147 versus returned6068/6148 convention. They are not proven the installed Rust revision. Neither the historical R27 full states nor new binary measurements exist here. Exact returned tick assertions in the new probe must be measured as written; a contradiction stops, never silently shifts a baseline/tolerance.

5. **Meaningful native and common-loop fixtures — accepted for bounded execution.** `terminal_probe.py:36–120` constructs real native reset scenes, both clients and weaker seats plus exact weakest-HP ties; checks accepted5997, refused6000 while not game_over and no physical-state change, then one-tick empty native drain to actual later scoring. It checks all HP and crowns, the unequal900HP drain and the one50HP/returned6148 delayed draw. `:124–159` binds exact installed binary/calibration/arena/cards, source/env hashes and effective phase rules/clocks; exclusive output refuses overwrite and caught errors preserve already-observed case evidence/traceback. A killed process can leave an incomplete receipt; that is failure, not PASS.

   `test_terminal.py:80–120,136–172` invokes production play_match and execute/refresh/hand_card plus the real frozen CommandQueue and real native Battle. Only own-HUD packet/actor construction is deliberately lightweight; this is disclosed and does not claim learned-feature/Translator invariance. Actual5970→5997 acceptance and5975→6002 pending are tested in both seat assignments for native wins and delayed draws. Exact log/hash, accepted events, decision/poll counts, pending details and real queue accounting are checked. A second native Battle loads the postaccepted5997 snapshot, proves identical state_hash before independent one-tick continuation and compares winner/draw/crowns/all HP/final tick/final state_hash with the common five-tick loop. These are substantive independent native assertions, not merely a duplicate phase boolean.

   `test_terminal.py:175–227` poisons information/hand access with overdue reservations at6010, requires empty five-tick advances/no actors or fabricated dispatches and preserved queues; covers natural earlier crown ends, a living1HP king actually killed by a fixture Knight, no subsequent actions/steps and nonterminal safety-cap failure. `:230–279` covers altered public duration, once-only overrides, other documented rules, malformed clocks/calibration and rejection before Translator/player start. `:298–349` preserves a real preclosure WATER refusal through row_issues/parent record_exit/report failure and checks the original58-file R27 inventory before/after read-only summarization, including all16 historical refusals and four failed raw wins. Missing mandatory native/artifact dependencies fail rather than skip. The closed-start test's detailed focus is poisoned-access/queue/scheduling; complete score equality is independently exercised by the four snapshot-continuation loop cases and six boundary cases.

6. **R24/R25 dependency/cache/fairness contracts — unchanged and source response accepted.** The new modules' top-level imports contain definitions/stdlib/NumPy only, no real builder or spell-registry construction. The paths-only fixture uses Runtime.__new__ solely to select the frozen import paths; it never instantiates a real builder/Translator. Queue/PublicEvent/latency imports are definitions without game-data construction; GC window creates its existing callback, not a spell registry. The only direct Translator path in the new tests is deliberately poisoned before construction. The mandatory six-file suite retains the existing actual-Runtime-first placement bootstrap and its real builder, exact frozen cache/spell anchors and real both-seat B root/act/fairness paths. No second actual Runtime is introduced. This avoids the R24 early-builder Fireball172-versus159 contamination; no registry reset or frozen runtime edit is proposed.

   R25-P2-1's early fixture_support import/comment remains at its R26-approved5e95f8ce… bytes; helper subclass binding still precedes synthetic constructor replacement. Existing-only primary preload, FrozenLevelConfigs/read-only support/export fences and exact121 qualification are unchanged. No supported/build/export call is added by the repair/probe/new fixture. FireballL11 ordinary688/crown159, L4 ordinary357/crown83 and Poison92/21 anchors retain exact comparison. Fair estimates, levels/root/configs, common placement scope/prior, translator, models/weights/features/native physics and completed s27 are unchanged. No fresh support baseline, exporter, tolerance, selected-card/deck exclusion or L11 fallback is allowed.

## Preserved failure and independent hash observations

R27 remains INVALID/INCOMPLETE:55observed/300,47terminal=43clean+4failed winning rows,8SIGTERM interruptions,245missing, parent143, no identity mismatch/duplicate. All16 native GAME_OVER events occurred at>=6000; all47 terminal rows recorded nativeFAILURES0. The four raw wins cannot be omitted to obtain a strength estimate. Stop receipt verifies parent632390's directed signal and bounded cleanup/reaping of8children/session54283 exit143. Its1327 frozen-input/7cache checks are historical preservation evidence, not a new execution result.

Directly read B-00000.json, arm **B**, index0: accepted Musketeer5997, Knight refusals6027/6057, Giant+Knight6087; final6105, winner0, crowns1–0, HP[[2846,1317,658],[3026,0,1274]], accepted57/59, executed58/62, rejected1/3, pending1/1. Other actual rejected rows remain A-00010(3/6096), A-00012(4/6100), B0-00013(5/6116). Source inference about historical reservation times is not a captured queue trace.

Independently checked all109 local source hashes and all58 original R27 output hashes. One initial inventory check used W instead of the inventory's relative pilot-r27 root and found missing paths; repeating at the correct root passed all58, without changing any artifact. Direct SSH01 verified all107 original deployed source entries against the original R27 manifest, unchanged pre-R28 match35b70b45…, and all7 restored cache hashes. New modules and proposed principal r28 output paths were absent at inspection. A process listing showed the audit shell, no matching owned Python workload; parent must renew exclusivity immediately before sync/launch. No source sync or CPU experiment occurred in this review.

Important publication distinction: per-file git-object hashing against published80b7c103… confirms the old common-match bytes match the saved pre-R28 backup. Five other inherited frozen-source entries (cards/build_runtime.py, cards/test_build_runtime.py, players/royalesim_translate.py, players/royalesim_vocab.py, players/runtime.py) differ from that publication's tree but exactly match the R27 deployed107-entry identity and this handoff's baseline. They are NOT R28 changes and are not approved for replacement from a newer main tree. The correct R28 delta is one changed common match plus two new modules;106 entries remain byte-identical to the actual R27 source identity. The old local f85c66d… index also cannot represent untracked files as a meaningful working-tree patch; no checkout/reset/pull was performed or requested.

Critical raw SHA256 anchors:

```text
5f1a5987c0fd9cd44f889fda83c971374e148cd1cde1665b080a3cb6d35c25c6  W/bot/players/royalesim_match.py
bc0ea5f54103aa84944318513757e3aea85e2015e3bf0f087a68e2d18d534d63  W/bot/levels/terminal_probe.py
bb442ac23d042d20394787900caecb2bb2326bbe29d8e9270f4c3f60ea33c739  W/bot/levels/test_terminal.py
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  J/terminal-r28-royalesim_match-before.py
3b5e45cdbec0adeb5bd8144c32af21abea9be186e911023d4c1e9361cba64510  J/terminal-r28-source.sha256 (109 entries)
dc0749e80e5b616d6c6c52222bb2caf3f7caffa27885c0cf887cecd0fd632a42  J/terminal-r28-implementation.patch
dff95dc2263a81a7c13b2c43c13488e36cb6f1f59647246305c6dacd69b4b6f1  J/terminal-r28-implementation.md
89eaba07e0de0e5c895c420c66aff78ab911f8d06a11c4b10be382e304cb1af4  J/pilot-r27-source-after-05.sha256 (107 entries)
fc7f7809031227ec1a55e128e017556b86eaba0c28927bdd1fdbf8a55ad65aa5  J/pilot-r27-preserved-files.sha256 (58 files)
e7a2b39a17b4870a5f9b587e906d2817417479e8e20a8443a3afbc3f96425eb0  J/pilot-r27-stop-audit.json
d6c834387d61e2bc358f6eb35d24f1842f7338c020ee338dd0324c1c15a44ca6  J/pilot-r27/rows/B-00000.json
97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb  exact installed RoyaleSim binary01
4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf  exact installed calibration01
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  J/dev/env.sh (05 and01)
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  existing cpu_job.sh01
```

Primary `run.py:37–42` hashes immediate levels Python files, so both new modules and every changed code byte participate automatically in the109-entry identity. No identity protocol edit/exemption is needed. Runtime/data/model/token/proof/cache identity remains separately bound by the unchanged runtime_files/preload contracts. The complete independently matching109-entry manifest is appended verbatim below; it is a source closure, not a claim that static109 hashes replace the larger frozen-runtime closure.

## Approved deployment and bounded commands — parent only, sequential, not executed

Approve the R28 handoff's exact commands at handoff SHA dff95dc2… with the following concrete exclusivity, pin and backup fences. Inspect each stage's terminal status, full evidence and before/after hashes before individually deciding to start the next. No automatic advancement/retry/resume. Preserve failed/incomplete logs and use another recorded unused suffix if any destination is occupied. No new host script, exporter or placement-physics rerun is needed.

Before any mutation parent renews read-only liveness/resource admission, verifies all107 old deployed hashes, the old match35b70b45…, the seven existing caches and original R27 inventories. Save the old common source to a fresh exclusive owned backup; require both new target modules absent. Example TEXT ONLY on01, before sync:

```bash
set -euo pipefail
set -o noclobber
J=/mpac/sdicks02/jobs/clasher/bot-levels
W=/mpac/sdicks02/repos/clasher-bot-levels
test "$(hostname -s)" = 127x01
test "$(sha256sum "$W/bot/players/royalesim_match.py" | cut -d ' ' -f1)" = 35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029
test ! -e "$W/bot/levels/terminal_probe.py"
test ! -e "$W/bot/levels/test_terminal.py"
test ! -e "$J/dev/pre-r28-source-r29"
mkdir "$J/dev/pre-r28-source-r29"
cp --no-clobber "$W/bot/players/royalesim_match.py" "$J/dev/pre-r28-source-r29/royalesim_match.py"
cmp "$J/dev/pre-r28-source-r29/royalesim_match.py" "$W/bot/players/royalesim_match.py"
sha256sum -c "$J/dev/cache-restored-r25.sha256"
```

Then parent may copy ONLY the three reviewed implementation files and data-only109-entry manifest to the identical01 paths; no broad bot/runtime sync/delete. Exact text from05:

```bash
scp /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_match.py 127x01:/mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_match.py
scp /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/terminal_probe.py /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_terminal.py 127x01:/mpac/sdicks02/repos/clasher-bot-levels/bot/levels/
scp /mpac/sdicks02/jobs/clasher/bot-levels/terminal-r28-source.sha256 127x01:/mpac/sdicks02/jobs/clasher/bot-levels/terminal-r28-source.sha256
```

Common01 preamble before approved CPU commands:

```bash
set -euo pipefail
set -o noclobber
test "$(hostname -s)" = 127x01
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
J=/mpac/sdicks02/jobs/clasher/bot-levels
test "$CLASHER_BOT_RUNTIME" = "$J/runtime/live16402b-r2"
test -z "${CLASHER_EVAL_RUNTIME_ROOT:-}" || test "$(readlink -f "$CLASHER_EVAL_RUNTIME_ROOT")" = "$CLASHER_BOT_RUNTIME"
test -z "${LEVELS_RUNTIME:-}" || test "$(readlink -f "$LEVELS_RUNTIME")" = "$CLASHER_BOT_RUNTIME"
export CLASHER_LEVELS_PLACEMENT_PROOF="$J/dev/placement-micro-r21.json"
test "$(sha256sum "$J/terminal-r28-source.sha256" | cut -d ' ' -f1)" = 3b5e45cdbec0adeb5bd8144c32af21abea9be186e911023d4c1e9361cba64510
sha256sum -c "$J/terminal-r28-source.sha256"
sha256sum -c "$J/dev/cache-restored-r25.sha256"
test "$(sha256sum "$CLASHER_LEVELS_PLACEMENT_PROOF" | cut -d ' ' -f1)" = 276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf
test "$(sha256sum reports/bot/levels/receipts/all11-dev-cases.json | cut -d ' ' -f1)" = b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a
test "$(sha256sum "$J/pilot-r27-preserved-files.sha256" | cut -d ' ' -f1)" = fc7f7809031227ec1a55e128e017556b86eaba0c28927bdd1fdbf8a55ad65aa5
```

These environment settings retain nice10, seed0, NumPy hugepage0, math threads1, CUDA hidden and bytecode off, with normal owned runtime and existing CPU leases/full-pool priority. Parent renews the complete unchanged runtime/model/input identity alongside the new source closure; do not mistakenly demand the old match hash after intentional deployment. All source/cache/runtime/model/proof/frozen input bytes remain fixed during every job.

1. **Exact API boundary probe first: CPU1, outer5m, at most1 Python.** Fresh six-case full receipt/exit0, actual accepted/refused public boundary and later native win/draw/all HP/ticks required. No Runtime/model/cache construction. Expected refusals in this isolated API fixture are observations, not pilot plays or waivers.

```bash
test ! -e "$J/dev/terminal-boundary-r28.json"
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.terminal_probe --out "$J/dev/terminal-boundary-r28.json" > "$J/dev/terminal-boundary-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-terminal-probe-r28.txt"
```

2. **Cold isolated primary cache failures: CPU1, outer5m,1 Python.** Require9 intended no-write faults without placement collection or TypeError waiver.

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -p no:cacheprovider 'bot/levels/test_harness.py::test_preload_bad_support_or_L11_never_repairs_cache' > "$J/dev/pytest-preload-isolated-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-isolated-r28.txt"
```

3. **All six files, actual integration: CPU1, outer15m,1 Python.** Require every old obligation and new terminal fixture, no mandatory skips, true integration flag/proof, actual Runtime-first once, exact Fireball/Poison/reference/cache anchors, real both-seat B roots/acts and preserved refusal/provenance tests. No guessed new total PASS count.

```bash
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py bot/levels/test_terminal.py > "$J/dev/pytest-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-pytest-r28.txt"
```

4. **Native gates: CPU2, outer15m, maximum2 Python including the raw-fc child.** Require all prior254 substantive checks:121 exports/13 towers/32 public bodies, four actual fair B decisions/positive roots,30each cut/snapshot/raw-fc, content-key change/reuse/shipped[1,2,2]. Inspect all raw snapshot differences. Only the prior proven absent spell_name→empty String representation is allowed; no numeric/type/entity/owner/position/key waiver.

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > "$J/dev/gates-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-gates-r28.txt"
```

5. **Same original four-case all11: run.sh2, outer15m, maximum3 Python=parent+2serial game children.** Require8unique clean terminal rows,4full-command pairs, all4positive B roots, both seats/controllers, parent/children0, exact source/runtime/prior/proof/env/cache identity and full both-seat command/phase evidence, zero errors/rejections/native failures. Hash equality with any rejection remains FAIL. New output only; no R27/R12/failed-output resume.

```bash
test ! -e "$J/dev/all11-terminal-r28"
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out "$J/dev/all11-terminal-r28" --arms A,B --all11-gate --start 0 --count 4 > "$J/dev/all11-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-all11-r28.txt"
```

6. **Report after clean runner completion: CPU1, outer5m,1 Python.** Require registered completeness/provenance/quality PASS and inspect raw rows; a nonzero or incomplete report blocks recovery.

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report "$J/dev/all11-terminal-r28" > "$J/dev/all11-terminal-r28-report.txt" 2>&1
```

The maximum in this sequential sequence is3 Python processes, within the existing16 task cap. No overlapping auxiliary jobs, heavy05/GPU/09–18 work, new host script, broad pkill,03 retry or frozen/live write. No signal is needed now. Existing static v3 proof145/1024 may be reused only with unchanged placement/probe/binary/data dependencies, as independently hash-verified here; avoid a redundant physics matrix.

## Recovery and rollback

Only after all final matching-byte gates PASS may the parent exercise the existing100-valid-case authority by drawing/publishing a NEW full100-case BASE/bank before games, same population/assumptions/A/B0/B semantics/policy/rule. No new BASE has been drawn here. R27 remains wholly invalid, with all16 events/raw outcomes and original registration13deb… retained; never selectively reuse/relabel/exclude its outcomes. No extra confirmation permission, strategy redesign or blanket Opus parking is needed for this supported reversible repair. Conditional200ms work follows only a valid promising pilot; no contemporary pooled LIVE benchmark is required to approve this clock repair. Completed required s27 diagnostic23/23/52tests remains untouched and is not rerun.

Concrete rollback after all owned jobs are verified stopped: preserve the new modules/failed outputs, verify and restore only the pre-R28 common match from J/dev/pre-r28-source-r29/royalesim_match.py (or the independently pinned J/terminal-r28-royalesim_match-before.py), and move the two newly owned terminal modules out of the immediate bot/levels source directory into an owned retained receipt location. Verify old match35b70b45… and old107-entry identity. This restores the known old lifecycle defect and grants no restart/PASS. Experimental operational rollback selects standard A/removes experimental hooks outside this pilot. Retain original/restricted prior, good and bad support/export caches, original failed gates/R27, frozen pins/models and existing live/runtime bytes; never restore bad cache implicitly or reset the shared old branch/index.

## Exact full109-entry source closure (verbatim independently checked manifest)

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/__init__.py
694b3028c71033f821b724163f3861ca5693d9cc906868e02293757e02bbf7d3  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/balance_overlay.py
b06e3968408f8a0fda26f71ec09d07d605269d29b67cb9c6b28e465e70c3d1e1  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/build_live16402.py
03f7ca8916cec3da10823476ff15385c7d8c174bd47e6830fea2f6da3638df5b  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/build_runtime.py
9ab2bc406db4a7b09a9858703e32518bbbb9fd057298e6b23f84ce6554c916fd  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/fc_cut.py
72c3a4a964b5454a5ceacef9eb1a0785538c54b28d9c8dce02b15dfe7c1e52f3  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/proxy_table.py
f116b76ab4079a1cbe208e7220587cf001c2966156ec939517780c2bb53dde98  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/scope.py
5457218e99c3a89af11895d5daa12625458f86b24f08de95734b519a43fd23fa  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/test_balance_overlay.py
3b585db0f2b039abca4594d1240a674c0761212b7247fb59a90ba5022a353818  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/test_build_runtime.py
b5c95aa2c92296126289f037fd57ec3f9249ea9ad42193ef55554cd50ef1a1c9  /mpac/sdicks02/repos/clasher-bot-levels/bot/cards/test_proxy_table.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /mpac/sdicks02/repos/clasher-bot-levels/bot/eval/__init__.py
d0f5777199c2a8d121bdf4caa121c27bd42ef825588fa33c5846c671bae90bd8  /mpac/sdicks02/repos/clasher-bot-levels/bot/eval/headline.py
6994cf1fea2edf8472d68e2428df0132bf35b593a82637dfae952ad31532465a  /mpac/sdicks02/repos/clasher-bot-levels/bot/eval/pair_by_name.py
07ba50d46a058a6279bbea325edf5dd483bc746b7118314df53e3edff1f3954b  /mpac/sdicks02/repos/clasher-bot-levels/bot/eval/paired_engines.py
598f143a905a4133b551245fb47f079747e54dcf8d8acf211f3e989d0fcbccca  /mpac/sdicks02/repos/clasher-bot-levels/bot/eval/summarize.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/__init__.py
7395a1679053744814c3bd1156282fc79693d2dcf18ffa7187b9852f588591ac  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/banks.py
3d1e62a2d87aa8bfc41d33e848aff3fdd88d2be9e072b86b0fc3a33358348e6b  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/belief.py
8d62b355fed6072db5c3dd996372bd92ccbbe342eca669bbf7f2827a8cf342cc  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/cards.py
35dc25b15792e04b1a39357e0669ccdaeeeb2cb9c5d017bec6de5a11791459e8  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/decks.py
96d5870e61f40591bf21f3fd3f800ed1f96584ccde3807cdc425a5aa92a26c36  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/extend.py
a624bffdf58d2d844c26e0debb5c8a3dc1123aef1a874058372b8433bb3d56d4  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/models.py
7f4e00ed5b89b856106015cb7cdbfe9606504ae15cdc03f8fd36897f2b60be24  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/parity.py
e8d695bd1e9bcac8ffd5aced98aed107d45232c34b127aca5bbaf46307c434c9  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/provenance.py
02c416195b70db3999cecb25d4df49f4648f294a73ac474cedcbc573c4737578  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/smoke.sh
9d7163f4073cb7c68ceb1237a81b3e59cb564561d4c6f7be15e6b712d91fa68b  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/smoke_summary.py
0f8ec024a26fe5bc55ebc734df795bdf802518fb7e20e569a57f6af2c953d3d0  /mpac/sdicks02/repos/clasher-bot-levels/bot/fullpool/test_fullpool.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/__init__.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/bank.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/configs.py
674bf0fbb966c6e0a8ded4805ae615a3187ae25e13a5eab3fd32463a033fe4f4  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/fixture_support.py
d59475d3b4cf44983541a497d9a96106d4fe3023ea540a2fbde9fc38bd8cf41f  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/gates.py
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/placement.py
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/placement_probe.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/player.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/profile.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/report.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/root.py
29d6509ec18452ffe3d535b1f91afed9d84cea61be38b42a79f5a942faa8850f  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/run.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/run.sh
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/scope.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_bank.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_configs.py
5e95f8ce4744ce113d102cbc48dd675eb778a60180b5b722cd02b3f6abb559c0  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_harness.py
3fe16baa155120959ce541a78e4b24fba6336855296eb14981db305758fc7bc9  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_placement.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_scope.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  /mpac/sdicks02/repos/clasher-bot-levels/bot/live/levels.py
f1137a8b9dad9158029d108ee133ec58c1a5da5636352811519088f674324477  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/__init__.py
fd66e0370fe580b917e2d1612194c01f4b19835e0c275ca5711e3e78dab08c2b  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/base.py
6d923289692467b7f5e07b2249c4c97f0b2bf1abc4ec8e2ee58789b5aef9187d  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/ours.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/policy.py
8b1379cf6637c4a62e87da49509e0f1ccdcf9286d5c005318fc6ad876383f8d0  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_check.py
d003623c5a9002a13e1c7a4196f88528a2031cc26f7fc6a3b5277a7c003fae5a  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_envs.py
65597b367ff115d3cf87921e399d66a7269fb754564871243a747664e0a6e047  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_eval.py
3bbd46619b7cc50fe99580e3aa4b7834e8e9c2ad688bf5d1c429d17b33d5ae96  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_imitate_clone.py
e956e1ba7e10c64eb824698a2fafaef0e5f678eb8a75833397cb7982b1e0d8fa  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_imitate_h2h.py
87ce0f6b1d9386f512ed1e2a9294de366b89a08eef80b29d8f860b911708663d  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_imitate_ppo.py
af6fadae71c898dee4b0b68ca9782321be3e784f4ff02b49044a4f8a7a329bbe  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_imitate_replays.py
b01c5fbd0df38b60e6905a0990a51496fb6fbee3ad79e6d01651388aa3f55a96  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_policy.py
74a4572520fe3375ee29a1d6f699d66d1790021b96c9d43fc60f26c1b3488cf2  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/rext_train.py
164cd6e92158e57c0fef2ede7f29a103ef2846c6a0d35b9c93250d50004b6d2f  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_adapter.py
0243465936fc05376a997b0b0bb740b71927571d4e2f3aa18d5ec43095883e2a  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_crosscheck.py
5f1a5987c0fd9cd44f889fda83c971374e148cd1cde1665b080a3cb6d35c25c6  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_match.py
cb666e9000591806d0c997cef0f7f89813d47ad43e145dc3c754e981b7f3bec9  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_opponents.py
5a4c0ca258b4a3579210fb29033727c35680ee1c064d1e7ecfa2ad21cd8435e2  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_run.py
89e593dac9a56114fac2d9bf49c87f832b3f85e697b20c25be854a0747a1b72a  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_summary.py
96229925be51b54ae330f0711082198dae997f0031189988125bbeb00de1bf36  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_translate.py
24c21cb6c31fb0c4b0f2ae7dbc7104897c4181cdbf9100607bf9138b47b81a16  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/royalesim_vocab.py
8c15ee64262748e1e37bb64c1d1e8ae9cabaaa5562ebc94299aa63251dee870f  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/run.sh
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/runtime.py
e130eb2eade973f969766c31cb9b1ae16953f2a3eb89e9719a2e24ac6b90a8f1  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/search.py
092dd1e5fdaec5ced2087d31d47bb38e22a6d9d4ea507302d20e7633095b80de  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/smoke.py
b8359300fb9192677f28483a80f00daae6c03605c92d3f48cb3869cb9dd00331  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/test_royalesim_translate.py
4944a2fbabe06ca93122465d354b4056fdadaf9484a5421647a33bcfdded7651  /mpac/sdicks02/repos/clasher-bot-levels/bot/players/variants.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/__init__.py
4ed974ff0562ea662d9626574706dbe81612570a26f58665747dd2e42a1139f2  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/cand_run.py
0c2e14fe334828ffdc91c207d546847fc78eb88ea5e1ef27e6cba7107f4cb14a  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/candidates.py
e4157f519e3481a43a69f19f21ea3b61c9b1d5df4a56a199a610bfedcffd6f3c  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/diag_roots.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp.py
38a919fa88a0693986acc7c6531b1d790fc889d380c431cfb9389a5b8bda7e6e  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_check.py
9accf6fc34a2a94f62830f99e37f792b78d190e9e7b580cb91ee726c6eef6a37  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_diag.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_fast.py
a03eaea134dba9cb5e43f0eaf587e01829ee96cd1db4ad0fea15d9f5cea48774  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_fast_check.py
123c5281fb445a45a6c9712f5558927d0c37a92c695cfea917c115d316640204  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_feat.py
df23014d31c05fcdf79cbbda120b2ad86d17dd308440ce1e1d2e50777644eeb9  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_gil.py
42a94362f1f7e960d409aa4a35ac0a4dae9779b94d619d087068841a1f2ff261  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_record.py
6801ebfbd1180e08630a980c5bb9fc2cf15de8b165dfc8c9b45a7fe534859935  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_safety_test.py
5c2dcc8e60dc01f7c9d5906994cbb6dba28a4a3c872019911cc4dc24b8081307  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_screen.py
8fe020ec62b866f2660a35e7b6ddb5d25595daef9f746fdf58a05241e367a063  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_threads.py
3155fe50cfa579bcc156787cd571ce3275c9f7c31efaf56b89b0d10d4d56ddff  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_time.py
f161cb9af23011bc24de70010b6a7144f9f447b93359a144016cb08eebd8484d  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/lopp_train.py
9d9f44e3004204c373e31a78094e65a02a270da57874e476328d57a8341327e2  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/opp_run.py
8e54abe94dd58e3c7241037cf81fa8b024b664550bf8e5602cd6bfaaa99c57aa  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/oppmodel.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/players.py
6471fa45429ec917d9f985e4479712e89235cea9bf0c0bf3b630af9f8c90c436  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/report.py
162176425001983aef13c058d7b0e170bf24a77069bf8476a5e56e4e8eca265f  /mpac/sdicks02/repos/clasher-bot-levels/bot/search/run.py
4e3e454d709bd2d7d0e21869a222a6de3ebd61274e1a97a75b8f81ed1932fea7  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/audit_seeds.py
23a5dfaa49336ef540d4c55fcb446b9fa3807687ff4ec81167d9e1ea8a8e0fc9  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/detach.sh
1a9526e5fba78a4c31c101d1b4225a0b3d86a80402c839457d87a25e50e45aeb  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/qualify.py
6d15a4cb53859efe9a6d4cde9309d264921c79ca847a0a2f3b11f70f837bf46a  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/reduce.py
85dbc37e990d74d80a30a2c948528987a7075ec142226273117f7e34d82c0b8d  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/run.py
b2eaef4bcb9556b02c78c3d7eb198953001473dec93f56da1abbae5498877cec  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/runtime.sh
e14dd6a9add7d3d0b7d9ab0cf08a66a6c70371cf2c9cbdfc21cfd4c18e106ce8  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/sdefault.py
0da9b7583e5f73c0dec3acfab73577739ac5ff7233531c18d8556e416cb824b1  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/supervise.py
ea017a41f3ece48d98b30e77421315d2eddb2d04917cb275494be2b32d6954c8  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/sync.py
521c71ede110d00c1cc100ffc66eec3cd626812382ac208c425f050eae817377  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/test_sdefault.py
be43c4e9ae5e37261cdfc211bb1ece92ff1aba0e1d9107a6dceaf44aae75e87c  /mpac/sdicks02/repos/clasher-bot-levels/reports/explore/x4s/write_report.py
bc0ea5f54103aa84944318513757e3aea85e2015e3bf0f087a68e2d18d534d63  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/terminal_probe.py
bb442ac23d042d20394787900caecb2bb2326bbe29d8e9270f4c3f60ea33c739  /mpac/sdicks02/repos/clasher-bot-levels/bot/levels/test_terminal.py
```

Source review complete. Automatic final delivery only; parent owns execution/interpretation. No runtime PASS claimed.
