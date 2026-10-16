# Sol R11 — focused public spell identity review

**Verdict: CONDITIONALLY APPROVE one full default-suite diagnostic and one focused `test_configs.py` run, sequentially on 01 after deployed hash verification. No execution, passing-gates receipt, snapshot acceptance, or primary-bank approval is established.** All three requested local hashes match.

Read the prior R9 review and R6 review/failed execution receipt. Inspected current root, regressions, gate assertions, config qualification/cutting, public-template construction source, environment and wrapper. Only this report written; no project imports, tests, synchronization, remote jobs, delegation or GPU work. Other R6 dependency/environment/wrapper hashes checked still match that receipt. The pinned runtime directory is absent locally; owner must verify the deployed runtime and hashes on 01.

**Fairness/card selection:** `root.py:105–115,197` now gives nonempty template `spell_name` precedence over the shared stats name. It removes a `level…:` prefix, requires the resulting card in the known config, and otherwise retains the previous producer/deck fallback. Unknown nonempty identities fail explicitly. The template comes from the observed public token/kind, not a hidden match entity. The stripped level is never used to choose physics: `level()` still selects our declared level or the fixed opponent estimate. Thus this repairs public card identity without importing hidden opponent levels.

**Qualification:** selecting Fireball now selects its own level export/delta. Projectile handling preserves unit max HP and excludes exported `spell_name` replacement; the existing subsequent qualification changes a plain Fireball carrier to `level4:Fireball` or `level7:Fireball`, resolving against the mixed/cut config. This review establishes the ordinary public-template path; the qualified-input unit assertion establishes identity stripping, not end-to-end requalification of an already-qualified template.

**Regression coverage:** `test_configs.py:41–48` explicitly supplies both empty-name producers and both deck cards, asserting Fireball, qualified Fireball and Arrows selection. The Fireball assertions fail under the former alphabetical fallback. `gates.py:261–319` strengthens integration coverage by replacing Knight with Arrows while retaining Fireball. Across both seats and owners, independently exported Fireball fields, HP, exact qualified carrier identity, retained qualified card and complete spell payload are checked. This catches wrong producer/damage and missing qualification even though both deck cards share the same assigned level. Arrows payload integration and unknown-identity rejection lack dedicated tests; these are nonblocking coverage limits for this focused diagnostic approval.

**Owner execution:** use the existing pinned `dev/env.sh`, GPU hidden, threads one, bytecode disabled, hashseed zero, pool start unset/`fork`, prebuilt complete caches and no overlapping exporters. For the full suite use `timeout --kill-after=10s 15m .../bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates`; maximum parent plus one cut worker. Separately run `"$PY" -m pytest -q bot/levels/test_configs.py` through wrapper1/nice10 and a bounded timeout. Write fresh distinct R11 receipts; preserve failures.

Require terminal zero, all seven substantive gates, no failures, 32 bodies, cut/snapshot/pool 30/30/30, distinct A/B keys and final A reuse `[1,2,2]`, and four fair decisions with positive root calls. Inspect BOTH actual raw snapshot difference lists before acceptance: only omission versus empty-string defaults for `stats.payload_key` and `spell_name` may normalize. Numeric/type, position, identity/order or qualified-key differences block even with green normalized equality. R6 remains 85/90 failed; current raw diagnostics have not been executed. Full mandatory gates, forced-all11 parity and separate primary provenance/launcher acceptance remain required before the bank. Accepted serial/common-prior design stands; no pooled LIVE approval.

SHA256:
```text
root.py fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8
test_configs.py 762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0
gates.py 2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3
```
