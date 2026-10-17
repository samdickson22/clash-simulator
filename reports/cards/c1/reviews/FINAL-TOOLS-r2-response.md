# C1 final-tools r2 implementation response

Original request: repair all six rejected safety/provenance findings and expiry+10 overclaim, obtain fresh
independent review bound to revised commit. Original review remains at CARD LEAD
`reports/cards/reviews/C1-final-tools-r1.md`; rejected source476a747f75569040f9b137d0991691c95e6f1b29.

| Finding | Concrete repair | Local negative evidence |
|---|---|---|
| F1 | Dedicated driver waits each fixture parent before roots, all8 root workers before comparator, comparator before PASS; records individual exit/status/time/command; own-PGID cleanup | Complete-output fake parent exit17/signal-9 still rejects after waiting both; missing/failed root/comparator status rejects |
| F2 | Exact complete lstat inventory, canonical names checked before reads; no input links/external allowlist; authenticated engine+bot Git archives and B2 ancestor; typed source/native/build/tests/owner/review/platform/raw-artifact receipts; explicit affected case identities | Partial/unrelated/extra manifest, traversal/control names, duplicate JSON, wrong Git commit/blob bytes, wrong/missing receipt/commit/native/review/testcase/raw file reject |
| F3 | Fresh private owned real bundle; only3 initial entries allowed, persistent exclusive claim/output; nofollow/exclusive generated files; reserved helper outputs under nonwritable private directory; atomic no-clobber PASS, publication errors remove PASS | Symlink/hardlink/dangling input rejected; output symlink cannot truncate sentinel; existing PASS cannot be overwritten |
| F4 | Frozen copies/controls required; claim before any control validation; keep original bytes, exact inventory rechecked before each phase/completion; no generated replacement baseline | Replaced ready/control or added/changed helper rejected against original |
| F5 | env-i before wrapper and shell, bash-p, isolated interpreter, explicit sys.path/standalone base_prefix, explicit r1, EVAL root derived per arm, single threads/nice15, effective env receipt | Environment lacks BASH_ENV/PYTHONPATH/OPTIMIZE/stale roots/pins/preload; worker source enforces r1/base_prefix |
| F6 | Derive577 IDs/ticks/action counts and300 deterministic roots/shard pairs; validate full chains/actions/digests/rollout parts/views/masks/select/apply/steps and all headers; exact bodies | Fabricated IDs, empty chains/checks, wrong counts/sample/schema/header/args/native/runtime/seat/tick rejected; historical lockstep residual accepted |
| F7 | Correct to through expiry (10 updates to expiry) | Source loop breaks at first missing shot; no additional simulation or byte-equivalence claim |

`tools/gate_fixtures.py` and `gate_roots.py` are copies of historical native-total-tools helpers with explicitly
reviewed adaptations: frozen input/bot paths, action_results/legal_actions metadata, root runtime/pins headers.
No native or engine mechanics changed. `gate_compare.py` is byte-identical to the old pure comparator.
The old `gate.sh` is retained only as historical evidence, never executed by the replacement driver.

Review scope: all revised tools/plan/prose, original six findings and this response. Independently test pure
validators/AST helpers with scratch synthetic records; no host script main, native/engine import, simulation,
build, remote command, or staging/launch execution before approval. Do not substitute local verifier success
for host/bundle/gate coverage. Human authority/authenticity remains owning lead's explicit decision; typed
hashes alone cannot create approval. Missing future B2/readiness bundle is a prerequisite, not filled data.

Unresolved external prerequisites: accepted/integrated B2, actual source/native build and affected-test
receipts, owner-authenticated dependency/input platform inventory, duplicate audit, exact reviewed-code staging
and final fresh C56. No engine/native/pin change requested. Old native2ac historical gate and631ac artifacts,
rejected review and failed scratch evidence preserved. Tools rollback is revert candidate scoped commit(s)
without executing rejected schema1. Local receipt/log hashes indexed by repair-local-receipt-r2.json.
