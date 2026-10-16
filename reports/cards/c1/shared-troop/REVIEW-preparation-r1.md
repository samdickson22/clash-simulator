# Independent preparation review — round 1

**REJECT — preparation tooling at exact commit `b66b8f53809070344669a78b2bb825ead14eab31`.**

Two actionable findings prevent approval of the captured-root inspector for consuming the forthcoming owner-bound roots. The source ledger and source-only witnesses otherwise support the limited preparation claims. This verdict is not implementation acceptance, dynamic parity, fixture-validity classification, native/host execution approval, or approval of actual coverage.

## Findings

### R1 — P2: Preserve explicit FAIL evidence and complete result differences

Bindings: [inspect_captured_troop.py:67](../tools/inspect_captured_troop.py#L67), lines 67–68 and 114–118; [test_captured_troop_inspection.py:66](../tools/test_captured_troop_inspection.py#L66). Schema binding: B2 `reports/cards/b2/tools/probe_fixture_preflight_v1.py:165–173`, SHA256 `128bf4c98d21b672b4bcc6a15523d73ba93dda8cd91080c94ce0f52209237efa` (read only).

The draft collector distinguishes successful collection from comparison outcome: its top-level `status` becomes `CAPTURE_COMPLETE` while `semantic_status` explicitly remains `FAIL: six legacy discrepancies retained`; `natural_comparison_status` and `validation_error` can also retain failure. The inspector copies only `status` as `original_status`, dropping these outcome/error fields. Its current positive test instead invents a top-level `PREFLIGHT_FAIL`, so it does not exercise that real schema distinction.

The per-row `retained_result` whitelist also drops any `result.differences`, retaining only the first-boundary `first_context.differences`. Later continuation differences supplied in the result therefore disappear. Its `.get(k)` further turns absent result keys into JSON null, although selected actor fields correctly use an absence marker.

Independent pure-JSON reproduction: a hash-matched, six-row `CAPTURE_COMPLETE` input carrying both explicit FAIL labels, a validation error and a later result difference produces output with no FAIL string and no later difference. Missing `result.cast` and explicit null `result.cast` produce identical retained results. The output still says `NOT_EVALUATED` and retains first-context differences; this is evidence loss, not an assertion that it emits an engine PASS.

**Parent-owned correction:** preserve the owner-provided collection/comparison outcome and validation-error fields without interpreting them as acceptance; preserve complete result differences as well as the first-boundary list; distinguish absent keys from explicit null. A config-free copy of the result object, or a complete documented projection with presence markers, would suffice. Add controls shaped like the draft collector's real `CAPTURE_COMPLETE` wrapper with retained FAILs, later differences, and missing-versus-null fields. No bulk configuration output is required.

### R2 — P2: Bind mismatch boundaries to the constructor timeline

Binding: [inspect_captured_troop.py:76](../tools/inspect_captured_troop.py#L76), lines 65 and 76–80. Schema binding: B2 draft `observe_legacy_fixture`, lines 38–44, 50–55 and 59–68.

The inspector checks equal Python/native ticks within each pair, an adjacent before/after pair, and matching relative/first indices. It never relates that pair to `initial_root.tick`. Consequently unrelated boundaries can satisfy every current check. The submitted fixture likewise leaves constructor and before ticks both at 100 even for relative first indices 14 and 23 (test lines 16–25), so those positives do not verify the missing relationship.

Independent pure-JSON reproductions for blue Zap (`lead=1`, actor ID 7, relative first 0): constructor tick 100 accepts before/after 9000/9001. More decisively, it accepts before/after 99/100, preceding the purported constructor. A supplied owner SHA binds those bytes; it cannot make that sequence a coherent continuation. No actual collector failure is alleged.

**Parent-owned correction:** validate integer frame/index values and the constructor-to-first-context relationship defined by the independently reviewed collection convention, including monotonic order and the relative comparison offset. Reject pre-constructor and detached later boundaries. Add valid nonzero-offset controls for ElectroDragon/IceSpirit plus the two malformed sequences above. If that convention requires another explicit anchor, have the collection schema carry it rather than guessing phase history. This remains a structural check, not causal or provenance authentication.

## Source and provenance assessment

- The controlling integration contract was read at SHA256 `0a67e7117fe1b2f69e55acdff2512bdbcdcdb1c9339a0a394a936d55dd5f9172`. New preparation commits `5630d424b`, `df438b2ed`, `b66b8f538` change only C1 report/tool paths from `e6b017ff6`. The engine tree remains `64ed8e5bb66bff6cbe0e746ec59fbd0dd36b48f7`. Approved launcher/comparator/followup paths have no delta from `97171f5`; historical launcher rejections were not used as findings.
- All current v2 source-receipt and inspection-receipt file hashes match. A fresh in-memory execution of the permitted source AST witness is byte-identical to `source-witness-v2.json`, SHA256 `e097f0617d2bb38966f5d8a4d95806e5e9d9772c1e2cf99dbad958ed5e01eeb7`. Retained B2 summary hashes and complete difference lists match their source files; v1 and v2 retain identical failures. V1's older tool digest is a historical version, not a claim that today's expanded script has that digest.
- Zap source bindings are sound within their stated limit: Python `entities.py:389` finalizes via `battle.py:871`; retained-route facing precedes external transport and one-node advancement follows it. C1 `src/dash.rs:111` travel returns through `src/lib.rs:2844` before frozen-route service at 2861. Actual dispatch AST controls show stunned standing pauses while already-committed travel still runs. These forced-state controls do not recover the missing B2 constructor state or prove ordinary reachability.
- The heading candidate is source-grounded: Python `entities.py:304` preserves quantized-zero heading and combat calls it at 3912; native engaged combat writes unconditionally at `lib.rs:2295`, while normal movement has a guard at 1776. Avoidance and spawn/death-angle readers make retained heading meaningful. First-bad positions/locks/phase are still missing; boundary coincidence is correctly labeled as an observation, not a causal proof.
- IceSpirit bindings support a conditional mode-transition candidate: `ordinary_combat_clock.py:9`, `differential.py:175,262`, Python `cards/ice_spirit.py:100`, and native `lib.rs:2420`. Native Spirit flight at 1028 and its dispatch skip ordinary status work; generic `projectiles.rs:125` still consumes the multiplier. Cleanup at `lib.rs:3394`/Python `battle.py:2445`, `entities.py:1685` retains a concrete ordinary/clock dependency. Slow-only precision, retained-clock cleanup, optional area/chain templates and clone/reload constraints remain necessary. No exporter normalization, inert-field exemption, global ignore or two-field implementation acceptance follows.
- The JSON inspector requires an owner-supplied matching SHA, COMPLETE collection, six distinct case/seat combinations, expected lead values and actor IDs, paired ticks, and unique IDs in each root. Independent controls confirm missing/duplicate collection rejection and raw B2 `dash.timer/destination` preservation. It does not reinterpret those roots through C1's `wait/goal` schema or run either native. Its stated limitation correctly disclaims provenance authentication beyond the supplied owner hash.

## Checks and exact receipt

All commands ran locally in `/mpac/sdicks02/repos/clasher-cards-c1` with stdlib/AST/mock/JSON work only, suitable for light local execution. No engine imports, battle/native execution, simulation, Cargo/build, SSH/scp, host scripts, process polling, gate/sweep, git mutation/push, comparator/followup edits, or children occurred.

1. `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/test_captured_troop_inspection.py` — exit 0; submitted synthetic controls pass.
2. Independent stdlib receipt/source verifier — exit 0; current hashes, exact retained differences, tool AST parsing and fresh source-witness equality pass.
3. Independent hash-bound JSON harness — exit 0; R1/R2 reproduce, while denominator/collection and raw-schema preservation controls pass.
4. Additional minimal timeline-order JSON harness — exit 0; pre-constructor boundary acceptance confirmed.
5. Read-only git/blob/hash verification — exit 0; exact HEAD, tracked scope bytes, unchanged engine/protected tools confirmed. `git diff --check e6b017ff6..b66b8f538` also returned 0.

The [JSON receipt](review-preparation-r1-receipt.json) contains the full exact command bodies, outputs, exit codes, SHA256 values, git blobs, source bindings and the hash of this review. Synthetic control success supplies no actual-root or dynamic acceptance.

## Required next review boundary

Parent owns production/doc corrections and regressions for R1/R2, followed by independent exact-commit re-review. Actual B2 roots/captures are unavailable for this review: collect only after owner review and the existing 3586969 job is terminal; this review did not inspect or poll that job. Implementation, dynamic causes, ordinary reachability, fixture validity, full-state continuations and actual affected coverage still require review after captures/fixes and the frozen B2-first integration prerequisite. B2 exact-source C56 must precede combined C1 C56, with every retained failure and required C56 identity preserved. Prior f68/native631ac and launcher97171f5 approvals remain immutable and confer no approval on new work.
