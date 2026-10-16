# C1 final preparation independent review r1

Reviewed delta `93317847730cf5c62de19db24b42c10e80b5d079..476a747f75569040f9b137d0991691c95e6f1b29`
in `/mpac/sdicks02/repos/clasher-cards-c1`, 2026-10-16.

**Launcher: REJECT. Comparator normalization: APPROVE, scoped to the selected fields and reviewed source read paths.**

The launcher must be corrected and independently reviewed again before execution. Comparator approval does
not admit an integrated candidate, establish complete snapshot byte equivalence, or replace fresh combined-source
coverage. Accepted/integrated B2, verified combined-source/native provenance, affected tests and a corrected
final gate remain prerequisites. Intentionally unfilled B2/input values are not findings.

This was a read-only source review with local, serial scratch checks only. No gate/launcher, native module,
engine, simulation, build, remote command, emulator, deployment or pin change was executed. No source files
were edited, no commits made, and no descendants created. The two preexisting untracked C1 diagnostic files
were left untouched. Scratch artifacts are beside this report.

## Launcher findings requiring correction

### F1 — P1: the wrapper still loses every fixture/root child exit status

Location: `reports/cards/c1/tools/final_gate.sh:64`; reused `tools/gate.sh:18–32`
(local exact copy `/mpac/sdicks02/jobs/clasher/cards/c1-final-tools-review-local/gate.sh`).

The unchanged helper launches two fixture parents, calls bare `wait`, then launches eight root workers and
calls bare `wait` again. Its final `cat` can return success after earlier failures. The outer `set -e` cannot
recover these statuses. Raw completeness catches many truncated failures, but cannot distinguish a successful
process from one that writes all records and then fails during shutdown. The wrapper explicitly recognizes
the bare-wait issue in its comment, but no per-child status receipt exists.

Repro: the scratch check runs only `(exit 17) &; wait` in a clean local shell; the recorded wait status is zero.
No helper was launched. A child that fails after flushing its complete output is still compatible with every
post-audit assertion.

Effect: PASS can be issued without the required successful child exits, and roots can start after a failed
fixture phase. Fix: retain and individually wait for both fixture PIDs, then all eight root PIDs, write each
status, and reject any nonzero/signal status before proceeding or issuing PASS. Also check the comparator's
status explicitly. Preserve the historical commands, inputs, pools and shards; review any changed helper hash
or implement an equivalent reviewed driver rather than claiming the old helper supplies these guarantees.

### F2 — P1: readiness does not establish the declared source/B2/input provenance

Location: `reports/cards/c1/tools/final_gate.sh:29–52` and `:63`;
`reports/cards/c1/FINAL-GATE-PLAN.md:116–132`.

Preflight accepts any nonempty receipt map and compares four boolean claims, but does not require B2
acceptance, integration/ancestry, build, affected-test and independent-launcher-review receipts with matching
identities/statuses. No checked tree inventory binds the archived engine source to `integrated_commit`.
`inputs.sha256` coverage is not inspected: a manifest containing only an unrelated receipt passes both
checksum commands. Neither required fixture/root inventories nor transitive Python/runtime/tool dependencies
are required. `sha256sum -c` accepts absolute/parent paths and does not report unlisted or newly added files.

Repro: the extracted preflight accepts an empty engine tree, arbitrary all-`a` source/all-`b` B2 identities,
a declared hash of a non-library scratch file, an unrelated text receipt, and a one-entry manifest of that
receipt. The one-entry checksum check also succeeds. A separate scratch manifest using
`../outside/input.txt` is accepted by the same checksum command. These are verifier tests, not an execution
or claim that the current owner has supplied such a readiness bundle.

Effect: filling the placeholders can make the script launch without the provenance it advertises. A correct
lead attestation is valuable, but the present script does not enforce the stronger fail-closed contract in
the brief. Fix: require typed evidence entries bound to the integrated/B2 commits, actual build native,
reviewed launcher/tools, and passing affected-test inventory; verify recorded ancestry against an authenticated
local commit graph or a separately verified archive/ancestry receipt. Derive/check a complete source/input
inventory, including expected fixture IDs and root sample identity. Parse and validate manifest names and
resolved targets before checksum reads; permit external read-only inputs only through explicit allowlists
and bound inventories. Reject missing, duplicate, unexpected and output/control entries. Human approval
itself remains an owner's decision; checking a receipt hash alone is not evidence that its contents approve
this candidate.

### F3 — P1: unchecked output symlinks and stale PASS markers violate bundle confinement/failure safety

Location: `reports/cards/c1/tools/final_gate.sh:16`, `:39–51`, `:58–64`, `:99–101`.

The run pathname is constrained and canonicalized, but only `gate` and `.gate-started` are checked for
existence. Existing `gate.log`, launch/exit/time receipts, checksum logs/controls and `PASS.utc` are accepted.
Redirection follows their symlinks, including into runtime or another owner's output. Directory checks also
follow `tree`, `out`, `tools` and `gate-tools` symlinks; the three `rt` equalities merely compare their resolved
targets and therefore permit an external source tree. These are distinct from the intentional `rt` and root
input symlinks in the recipe.

Repro: extracted preflight passes with `gate.log` linked to an external scratch file, a preexisting PASS,
and tree/native/tool directories linked outside the scratch bundle. The actual line-64 redirection would
truncate the external gate log; this review did not perform that redirection. On any later failed gate,
the preexisting PASS would remain because the failure trap never invalidates it.

Effect: a nominally isolated new run can overwrite an external file, or leave a false success marker after
failure. Fix: before launching, require all generated targets to be absent using lstat-style checks, including
dangling symlinks; require owned real output/source/tool directories, with narrowly enumerated read-only input
symlinks. Open new outputs exclusively without following symlinks. Publish success using an exclusively
created temporary receipt plus atomic rename only after all validations and exit statuses succeed. Make
failure receipts authoritative and ensure a failed attempt can never retain a PASS from another attempt.

### F4 — P1: the readiness baseline can change between validation and the recorded controls

Location: `reports/cards/c1/tools/final_gate.sh:25–57`, `:63`, `:99`.

The readiness and input-manifest hashes are validated before the one-use marker. Later, line 63 computes
new hashes of their current contents rather than checking that these are the bytes validated in preflight.
A staging/owner update during that interval can replace both controls; postflight then verifies the new
baseline. A helper can likewise change between its early fixed-hash check and execution when the manifest
omits it, as F2 currently permits. Receipt contents are not revalidated at the end.

Repro by source sequence: after line 53 but before line 63, replace `ready.json` and `inputs.sha256` with
a different mutually consistent pair. `controls.sha256` is generated from that replacement and later accepts
it. No race or concurrent job was executed for this review.

Effect: acceptance need not describe the controls actually approved before launch. Fix: take the persistent
claim before validation, freeze the staged inputs against further preparation writes, and retain the hashes
of the exact readiness/manifest bytes that were validated. Check those original digests immediately before
execution and at completion; never regenerate the trusted baseline after validation. Include complete
tool/source inventories and use validated immutable copies/descriptors where needed.

### F5 — P2: inherited runtime pin selection can change the check meaning in both root arms

Location: `reports/cards/c1/tools/final_gate.sh:20–21`; reused `gate.sh:25–28`;
`bot/players/runtime.py:72–76`, `:96–118`, `:139–140`.

`CLASHER_BOT_RUNTIME_PINS` is not cleared or fixed. `parity_roots.py:41` constructs `Runtime(verify=False)`;
the runtime still reads that variable and applies card-scope extensions, side-table cuts or tournament spell
overrides. The helper sets each arm's runtime/native directory but inherits pin selection into both. Thus
an inherited `r1-cards1` or `live16402` setting can select a different runtime policy while the compared
binaries and eight checked native hashes remain correct. `CLASHER_EVAL_RUNTIME_ROOT` also survives and is
only set with `setdefault`; the relevant remote Resources implementation is not available locally to bound
its downstream effect.

Repro is a source trace, not a root run: compare the explicit unset list against `selected_pins()` and its
consumers; the r1-cards1 policy enables `card_scope='full'` and `fc_side_cut=True` instead of default r1.

Effect: two arms can agree under a different policy from the historical parity check. Fix: launch with an
explicit minimal environment, fix pin selection to the historical r1 policy, clear stale evaluation-root
overrides so each Runtime derives its own root, and record the effective environment. Prevent the child
noninteractive shell from reloading inherited `BASH_ENV` after sanitization. Preserve the existing
eight-CPU wrapper/owner limits and nice/thread settings.

### F6 — P2: raw auditing counts rows but does not establish expected identities, chain schema or full headers

Location: `reports/cards/c1/tools/final_gate.sh:74–96`.

Fixture IDs are only checked for uniqueness/cardinality and agreement between arms, not against the frozen
577 expected IDs. Equality of `rust_only` dictionaries is counted as a chain match without requiring chain,
final, ticks, action-count fields or valid hashes. Root keys are unique and agree across arms, but are not
checked against the expected deterministic sample and per-shard full/cut pairing. Headers are checked only
for native SHA; `roots_total`, `sampled`, rollout arguments and source/native paths are not audited.

Repro: the scratch checker generates 577 arbitrary fixture IDs with `rs={}` and `rust_only={}`, plus 600
root rows at arbitrary k=10000..10299 with empty rollout/select/step checks. Header `roots_total=0`,
`sampled=0`, `args={}` contradict the body. The exact unchanged pure `compare.py` and extracted final raw
audit both accept these files, and the latter prints its full 577-chain/300+300 PASS. This demonstrates
verifier under-specification; it does not claim the normal helpers emit these malformed rows.

Effect: the advertised raw/chain/header evidence does not follow from the assertions. Fix: bind expected
fixture/root identities and deterministic shard assignment from the validated inventories; validate the
required record/chain fields and types, valid digests, expected ticks/actions and per-root variants/check
counts. Check all eight header metadata fields against the frozen input and expected historical arguments,
in addition to SHA and exact cross-arm body bytes. Preserve intentional historical lockstep residuals rather
than silently requiring a different Python-vs-native success criterion.

## Comparator decision and evidence

**APPROVE** `probe_snapshots.py` SHA256
`aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8` for this scoped normalization.

- At `probe_snapshots.py:62–75`, missing native Pingpong phase becomes zero; nonzero phase is retained.
  Both hit lists are sorted without set conversion, preserving content and multiplicity. Other classes
  receive neither normalization. Native serde at `engine-cards/src/lib.rs:422` and membership/return clearing
  at `engine-cards/src/projectiles.rs:31–63` support this representation equivalence.
- Aim is removed only for matching Pingpong classes with matching positive-period specs, present equal
  authoritative endpoints, and equal integer phase within the period. Endpoints and phase remain in CHECK.
  `entities.py:5945–6045` uses pp origin/apex/time/specs for the trajectory, not target_position; native
  pingpong stepping has the same dependency. The documented continuation and original receipt support the
  exact born axe path through return/expiry. Authoritative differences remain visible.
- At `probe_snapshots.py:76–86`, origin is removed only for matching plain Projectile/Arrows, explicit
  non-source/non-piercing state, absent shot targets, and zero count/damage/range on both sides. The native
  child call is gated at `lib.rs:3272`, with the sole native origin reader behind the damage/range guards at
  `projectiles.rs:207–214`. Python's child creation also returns before using launch origin with these zero
  stats (`entities.py:5676–5697`); its source-hit reader has no source on this spell path. SpawnProjectile and
  child-capable/changed metadata paths keep origin comparison. No global drop or engine-state mutation occurs.
- Independently ran the submitted pure axe controls plus additional pure predicate controls: missing/changed
  endpoints, unequal/nonzero/out-of-range phases, hit permutation/content/multiplicity, class restriction,
  both sides' child fields and source/piercing/target/spell metadata, missing Python child fields and compound
  child capability. All 30 named groups passed. These used AST-extracted functions only, with no engine import.

The comparator remains a selected, rounded semantic comparison with documented preexisting exclusions.
This approval does not turn it into complete-state equality. Reconfirm the dependency/read-site proof if
integration changes the relevant native/Python paths, and rerun the bounded controls against the actual
integrated native through the normal authorized workflow.

### F7 — P2, nonblocking to the narrow predicate: expiry+10 evidence is overstated

Location: `reports/cards/c1/tools/probe_snapshot_followup.py:180–183`;
`reports/cards/c1/SNAPSHOT-DIAGNOSTICS.md:101–103` and `PROGRESS.md`'s 09:38 entry.

The origin loop breaks at the first missing shot. The local first receipt records `expired_after=10`, with
trace ticks 81..90. The code compares the expiry state, then stops; it does not advance ten ticks after
expiry as the documentation says. Fix the claim to "through expiry" or deliberately test ten additional
post-expiry updates when the integrated follow-up is authorized. No simulation is needed merely to correct
the prose. Source guards still establish the origin reader is unreachable, so this does not invalidate the
narrow comparator predicate approval.

## Verification and evidence limits

`bash -n`, AST parse of both embedded verification blocks and both probes, and the scoped committed
`git diff --check` passed. The first scratch attempt used local Python 3.8 and stopped at the preflight's
Python-3.9+ `Path.is_relative_to`; rerunning the scratch verifier with the exact local bot venv Python 3.12.12
passed all stated reproductions and pure controls. This is not a finding against the launcher's configured
interpreter. The launcher clears `PYTHONOPTIMIZE` before its assertion-based pre/post checks; retain that
protection and apply it to any future verification environment too.

Hash-verified the supplied first `followup.json`, its two-case PASS log, and the existing local native.
The final `followup-final.json`/log were not supplied locally: their documented hashes were read but not
independently verified. Do not describe their authenticity as checked by this review. Before using them as
coverage receipts, the owning lead must obtain and hash/inspect the actual files, including comparator/probe
revision provenance and successful exit status. No remote evidence was fetched and no job was started.

The unchanged helper and all three pure helper sources are locally available and match the exact plan
hashes. Remote r1/bot interpreter/runtime/input manifests and the actual future frozen readiness bundle were
not audited; they must be verified by the owner before admission. None of these missing future inputs was
treated as a placeholder code defect.

Reproductions: `static_checks.py` and `static-check-results.json` beside this report. They execute only
extracted verification/predicate code, the pure JSON summary comparator, scratch checksum checks, and a
minimal local shell wait-semantics example. They never invoke the host gate scripts or any engine/native code.

## Exact reviewed hashes

- Commit: `476a747f75569040f9b137d0991691c95e6f1b29` (base `93317847730cf5c62de19db24b42c10e80b5d079`).
- `tools/final_gate.sh`: `57c3bd179aac3f9b50b930606b22c5f139ef7b37713202647cd7ebd589faa282`.
- `tools/probe_snapshots.py`: `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`.
- `tools/probe_snapshot_followup.py`: `60be8aaf65052557b333d5fe6cfd74636841d55ff7c4a3eef15835e1d66a3208`.
- `FINAL-GATE-PLAN.md`: `a77e889f711ec62d1875f4052c17d5a099ab986d536e8e8a3f165615a1914b24`.
- `SNAPSHOT-DIAGNOSTICS.md`: `4e4e0f20f036ae148b40fea2c7fd752497d430eaadaa638664d16e752fc1c4a7`.
- `PROGRESS.md`: `22b3429d3117eb83f4f0c6d3c099fa7d4b5768842579e1a43c4279e2abc30fc4`.
- `RESULTS.md`: `a5273f5832452cf6bd6dfb2fac4f3bcc11ba54db7004c1941a38c5c6a9146a33`.
- Reused `gate.sh`: `21bbecaf168be4c5b5ff44f96208025b58424b62efdf80ecf9179db37353e170`.
- Reused `parity_fixtures.py`: `057bd386f022d3770baf0a47d19b7eac2b8e9fc978a0464746ae4a6fc7afe976`.
- Reused `parity_roots.py`: `2d721a49d003abfaadd0e5f532749f700addfd733c493e7acf2b6abe225063eb`.
- Reused `compare.py`: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.
- Supplied first follow-up receipt: `b123676e3c17bce9cb7397c75b260bf2dde1b147fd6c9a109e89fb5c2bf9111b`.
- Supplied local native (hashed, not loaded): `631ac18d27cb15d4eba7011113a9f69a4b85740ef68a27a87cabb0d68320ad86`.

Engine files were consulted solely for normalization dependencies, not for another engine review. Current
read-site hashes: `src/lib.rs` `8dfe545cce45f96817a0c948d8da4f934ba377e74db42bda7771f18b509e20ba`;
`src/projectiles.rs` `e2d86027667b5f665be75915b874f46f645b74766ad1f01c52d99960d9940e4e`;
`py/src/clasher/entities.py` `19226704747aba6d4947be492a1673e41b4f426caa4df523dfc72a29ea980780`;
`live_snapshot.py` `57392c70a5c99159a893acb598ca130a241418bab55859e45a94090f85a95e83`;
`differential.py` `693a825bc57a78f59841ad1e2a8e30518102360075517343e574738f0343b7e9`.
