# Sol r9 — focused gate API/serialization review

**Verdict: CONDITIONALLY APPROVE one full default-suite diagnostic on 127x01 through the existing wrapper2/nice10, after deployed hashes match. No gate pass or bank approval is established.** The r6 receipt remains failed: 85/90, including both mandatory native-snapshot comparisons and three API exceptions.

Reviewed current 640-line `bot/levels/gates.py`, r1/r2/r5/r6 reviews, failed r6 receipt, current DESIGN/PROGRESS/HANDOFF/SCOPE, and relevant native/API consumers and source copy. HEAD is `f85c66d375a949e007d9aeff6983c3f028c64b50`. Configs/root/player/scope/lopp/lopp_fast/royalesim_match hashes still match r6. `gates.py` is untracked, so Git supplies no historical r6 patch; conclusions follow current code and recorded r6 evidence, not a claimed bytewise historical diff. Unrelated harness files were not reviewed. Only this report written; no tests, project imports, simulations, synchronization, remote jobs, delegation, GPU work or runtime writes.

**API repair is source-correct** (`gates.py:131–154`). It reads the current hand, selects the requested card's slot, reflects world coordinates by `(18-x,32-y)` for seat1, and encodes `slot*576+row*18+col`. Native `scripts.rs:879–911` decodes that same grid and reflection, then resolves the card against the supplied state's config. The public PyO3 `apply_discrete` wrapper exists (`:570–574`). Successful calls require the selected slot emptied, matching `last_card`, and reduced elixir, consistent with `lib.rs:3754–3765`; rejected calls fail their callers' acceptance checks. Remaining native-state uses—construction, snapshot, step and cloning through rollout consumers—have exposed APIs. No obsolete native `deploy_card` call remains; Python reference deployments retain their actual API.

**Selected physics values and ordering remain checked** (`:481–533`). Rows retain entity index, id, owner, class, x/y, HP, stat name/max_hp/damage, payload key and spell name. There is no sorting, rounding, scaling or tolerance. Missing required numeric fields raise. Only absent payload_key/spell_name become empty strings; nulls and qualified strings remain unchanged. Both String fields have `serde(default)` in the inspected `lib.rs`, supporting that narrow hypothesis. Every selected raw difference logs entity/index, field, presence, JSON value and Python type before normalization. This is selected-field preservation, not exhaustive entity equality.

**Acceptance caveat:** `:531` uses Python equality, which treats equal-valued int/float (and bool/int) pairs as equal; `_difference` does too. Raw diagnostics at `:501` detect these type differences, but they do not independently fail the gate. Thus “numeric types remain strict” is not enforced automatically. This does not block collecting the bounded diagnostic. Before accepting snapshot physics, inspect both raw diagnostic lists: require differences exclusively attributable to the two omitted String defaults. Any numeric/type, coordinate, identity/order or qualified-key discrepancy remains unresolved and blocks acceptance, even if `normalized_equal` is true. Do not infer schema-only repair from a green summary alone.

Run with the unchanged pinned dev environment, GPU hidden, threads one, bytecode disabled, hashseed zero, no overlapping exporter, and pool start unset/`fork`:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-all-r9.txt 2>&1
```

Use that distinct unused receipt; preserve r6. Maximum two Python processes, parent plus one fork cut worker; other gates serial. Require terminal zero, all seven substantive gates, no failures, 32 root bodies, schema-only snapshot evidence, cut/snapshot/pool 30/30/30 values, distinct A/B keys and final A reuse `[1,2,2]`, and four fair decisions with positive root calls across both seats. Timeout/missing summary fails. Forced-all11 parity across seats/controllers and separate launcher/provenance acceptance remain mandatory before bank draw. Accepted conditional-population/common-prior serial semantics stand; no pooled LIVE claim follows.

Reviewed gates.py SHA256:
`3a692e9b04471cea68a6af2f8ef37d39d69809408101eee007915cf633047bc7`
