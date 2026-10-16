# C1 launcher preparation independent review r2

**REJECT** — two actionable defects remain in the submitted preparation. Do not execute this candidate.

Reviewed complete delta `476a747f75569040f9b137d0991691c95e6f1b29..c45854febf93352284dd9f76b02651d989d906a7`
in `/mpac/sdicks02/repos/clasher-cards-c1`, branch `cards/c1`, 2026-10-16. HEAD remained the candidate.
Candidate tree: `31bf0bdcb54b2a47dab83edadba024d2ad428f46`.
SHA256 of the complete `git diff --binary` delta:
`c723f0dbb61163e851b0ba9bedab18df4a44c9d30bfac68af113486add04c5de`.

Read the entire original rejection at CARD LEAD `reports/cards/reviews/C1-final-tools-r1.md`, the implementation
response, current `FINAL-GATE-PLAN.md`, current PROGRESS authority and all 16 changed files. The parent supplied
two essential discoveries during review; both were independently checked against the unchanged candidate.
Their handoff is preserved at `reviews/r2-parent-discovery.txt`.

## Findings

### R2-1 — P1: the documented clean environment breaks the CPU wrapper's user accounting

Location: `reports/cards/c1/FINAL-GATE-PLAN.md:163–164`; dependency
`/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh:13,22,25`;
`cpu_job.sh:7–10`; downstream lease check `tools/final_gate.py:281–283`.

The only documented invocation applies `/usr/bin/env -i` before the existing CPU wrapper and supplies PATH,
LANG and LC_ALL, but no USER. The wrapper invokes `cpu_room.sh`, whose live-process count and leased-group
usage both run `ps -u "$USER"`. USER is an environment variable, not Bash's identity-derived UID/EUID variable;
the emptied environment does not supply it. Thus these commands receive an empty user selector. Their pipelines
do not fail admission closed: the final counting stages can yield zero, ignoring live Python workloads that
the user-scoped accounting was meant to include. Existing lease reservations may still contribute, but they
do not recover missing live-process accounting. The outer redirection also discards the accounting diagnostics.

The driver later checks that an eight-slot lease file exists with its PGID. That cannot prove that the
wrapper admitted the job using valid user accounting: `cpu_job.sh` writes the lease after its room check.
This can admit work on a host without respecting the existing live-process ceiling, contrary to the retained
owner/CPU limits. It is a preparation defect even though R2-2 currently prevents workers from launching.

Fix: supply USER derived from the actual executing identity in the sanitized environment **before** the
unchanged wrapper runs; preserve the clean BASH_ENV/pin/overlay protections. Check the wrapper's required
environment as part of the revised invocation's local source/mock controls. Do not repair this by restoring
the entire inherited environment. This finding is a source/readpath verification; no wrapper, ps command or
host script was executed to reproduce it.

### R2-2 — P2: the full bot archive always fails on an empty Git pathspec

Location: `reports/cards/c1/tools/final_gate.py:61–66`, reached by `:110–112`.

`archive_files(repo, commit, prefix='')` always invokes
`git ls-tree -r -z <commit> -- <prefix>`. The mandatory full-bot call supplies no prefix, so the actual final
argument is the empty string. Real local Git rejects that argument with exit128:

```text
fatal: empty string is not a valid pathspec. please use . instead if you meant to match all paths
```

Independently ran the read-only local command `git ls-tree -r -z HEAD -- ''`: exit128, the diagnostic above.
An AST-extracted `archive_files` check also confirms the default call constructs exactly that argument vector.
The submitted Git mock returns a canned tree for any ls-tree call and therefore misses the real rejection.

Effect: even a fully authentic, complete future readiness bundle cannot pass the mandatory bot-archive
verification. Preflight stops before fixtures and publishes failure; this is a fail-closed usability defect,
not a false PASS or a missing-input complaint.

Fix: omit the pathspec argument for a full-tree listing (or use a valid explicit full-tree pathspec), while
retaining prefix stripping/validation for engine and tools. Cover full-tree and nonempty-prefix argument
construction, and verify the corrected full-tree query with read-only local Git before the fresh review.

## Complete repair assessment and helper compatibility

Apart from the two findings above, inspection and bounded checks found the following repairs consistent with
the declared contract. These observations do not approve execution of this rejected revision.

- F1: `final_gate.py:160–170,213–245` waits each fixture parent, each of eight root workers and the comparator
  separately. A fixture exit or audit failure prevents entry to the root phase. Submitted fake-process checks
  retain both exit17 and signal-9 despite complete-output claims and wait both fixture parents; missing/failed
  root and comparator statuses reject. Cleanup/result publication preserves the all-child receipt.
- F2: `final_gate_contract.py:90–124,149–222` checks exact recursive inventories, canonical names, duplicate JSON,
  typed B2/integration/build/test/review/platform identities, raw artifact hashes and declared affected-case IDs.
  `final_gate.py:106–143` binds engine/bot/tools Git content, checks B2 ancestry, both native roles and the approved
  dependency inventories. R2-2 prevents the full-bot part from functioning. Owner approval remains explicit
  authority: hashes bind evidence bytes and identities; they do not authenticate a human's approval or establish
  the truth of arbitrary raw artifacts. The plan correctly requires the lead to inspect/authenticate those artifacts.
- F3: `final_gate.py:33–52,202–207,269–298` rejects stale bundle entries, reserves outputs exclusively, keeps helper
  files in a private nonwritable directory and publishes PASS without clobbering an existing target. Local synthetic
  checks reject input links, hardlinks, dangling paths, external-output symlinks and stale PASS writes. Independently
  exercised the AST-extracted publication tail with real scratch files for both success and an injected exception
  immediately after linking PASS: the failure path removes PASS and writes FAIL. No host main was executed.
- F4: `final_gate.py:84–104,146,213,226,243,249,275` claims before validation, retains the original control bytes and
  compares them plus the full original inventory before each phase and at completion. Synthetic changed controls
  and added/changed tool inputs reject; the trusted baseline is never regenerated from replacement controls.
- F5: `final_gate.sh:1,5–7`, `final_gate.py:22–24,196,209–211` and `gate_worker.py:9–26` isolate the interpreter and
  worker environment, fix policy to r1 and remove stale EVAL selection. Independent AST checks exercised both
  worker arms with inert runpy and synthetic sys/os: paths stay inside the capsule, the correct native/runtime
  arms are selected, fixture/bot roots relocate and argument forwarding survives. R2-1 must be repaired at the
  outer wrapper boundary while retaining these protections.
- F6: `final_gate_contract.py:225–263,285–354` derives expected fixture IDs/ticks/actions and deterministic root
  samples, checks schema/digests/check counts, full/cut pairing, shard assignment and complete root headers.
  Supplied synthetic controls accept the historical lockstep residual shape while rejecting fabricated IDs,
  empty chains/checks, wrong counts, identities, arguments and headers. Reviewed `fixture.py:75–153` and
  `rs_parity.py:65–105` as source to check the expected loader filtering, tick/action and residual record shape.
- F7: changed PROGRESS, RESULTS and SNAPSHOT-DIAGNOSTICS now say **through expiry (10 updates to expiry)**.
  The unchanged follow-up loop stops at the first missing shot. No ten-post-expiry claim or new simulation
  is needed to justify the corrected wording.

Independently reversed only the specified helper adaptations and obtained exact equality with all three
historical helpers in `reports/bot/learned-opponent/native-total-tools/`. Fixture changes consist of relocating
`rp.D` at all three entry paths and adding action_results to the existing chain result. Root changes relocate
the bot import root and add runtime/policy/legal-action metadata. The comparator is byte-identical. Pool sizes,
selection seeds, four shards, rollout arguments/styles, cumulative steps and chain calculations are preserved.
An extracted fixture main with intercepted imports and an inert Pool confirmed the relocated split path,
three-worker request, episode ordering and output/header forwarding; its callback was never run.

Source readpaths checked: bot fixture loading uses the overridden `rp.D`; worker roots and Runtime bootstrap
select the corresponding frozen runtime; differential resolves engine-speed from the materialized runtime's
parent; gamedata selection honors CLASHER_ROOT; Runtime sets EVAL root from that arm after its removal.
These are source/mock compatibility checks. Actual import/dependency closure on04, native execution and real
bundle behavior remain untested. Readpath hashes are recorded in `r2-independent/receipt.json`.

## Exact local verification and limits

All commands below used CWD `/mpac/sdicks02/repos/clasher-cards-c1` and ran serially. Scratch and logs are only
under `reports/cards/c1/reviews/r2-independent/`. Reproduction code is `independent_checks.py`; exact command
strings, result codes and artifact hashes are also in `receipt.json`.

```bash
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r2-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/tools/test_final_gate_contract.py > reports/cards/c1/reviews/r2-independent/submitted-tests.log 2>&1
/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r2-independent/independent_checks.py > reports/cards/c1/reviews/r2-independent/independent-tests.log 2>&1
bash -n reports/cards/c1/tools/final_gate.sh
git diff --check 476a747f75569040f9b137d0991691c95e6f1b29 c45854febf93352284dd9f76b02651d989d906a7
git diff --exit-code 476a747f75569040f9b137d0991691c95e6f1b29 c45854febf93352284dd9f76b02651d989d906a7 -- engine-cards reports/cards/c1/tools/probe_snapshots.py reports/cards/c1/tools/probe_snapshot_followup.py
git ls-tree -r -z HEAD -- ''
```

Results, in order: **12 submitted groups PASS**, **7 independent groups PASS**, exit0, exit0, exit0/empty
delta, and **expected exit128** reproducing R2-2. The independent groups include assertions demonstrating
the defects; their PASS is not a launcher approval. AST parse covers all seven Python files in the delta.
The submitted first failed harness receipt and later 12-group PASS receipt/log were read and preserved.
No local synthetic test failed during this independent round.

**No host execution:** no driver main, launcher/staging/host script, gate child process, engine/native
import, simulation, build, remote command, emulator, deployment or pin operation. No source modification,
commit, push, child delegation or other-worktree edit. Original `tools/peek.py`, `tools/snapcmp_probe.py`, old
failed artifacts and the parent discovery receipt remain untouched. Local read-only Git/source/hash commands
were used for review; the Bash check was syntax-only. Actual wrappers were read, never sourced or executed.

The approved snapshot comparator and engine/native source have no delta from the original submission.
The prior comparator approval remains scoped to selected fields/readpaths; this review does not extend it.
Accepted/integrated B2, an exact-source build and affected-test evidence, owner-authenticated platform/input
inventory, duplicate-job audit and fresh C56 remain external prerequisites. Their intentional absence is not
a code finding. This verdict concerns launcher preparation only, not integration, engine acceptance, byte
equivalence or live-pin approval. Repair both findings and obtain a fresh independent commit-bound review.

## Reviewed file SHA256

All 16 candidate delta files were hashed from the full candidate commit and matched the reviewed worktree
bytes. Hashes follow; the receipt additionally binds the unchanged comparator, follow-up, original rejection,
relevant bot readpaths and preserved diagnostic helpers.

- `reports/cards/c1/FINAL-GATE-PLAN.md`: `51cfb2dd81eb37b25c987e882fcf8c2e8afc74ebdc1645c3f32a365ed0ec8fad`.
- `reports/cards/c1/PROGRESS.md`: `bca9a288b68f5d2cff6674f877dd49001297f8b70e56dca96a75916f131dbaac`.
- `reports/cards/c1/RESULTS.md`: `e6621eef3590df8b86d024722b9bb8aa74cfb1142d6c4a957057a782171d4761`.
- `reports/cards/c1/SNAPSHOT-DIAGNOSTICS.md`: `5136eb6f3f80881a040e217e3e88220e146b0f83b2858dba7eef81856f9dbe01`.
- `reports/cards/c1/reviews/FINAL-TOOLS-r2-response.md`: `5a607c2fbc7d646bfa9cc20ee4ec829be72ef69d4a88dc54a208ff33d605062d`.
- `reports/cards/c1/reviews/repair-local-first-failure.json`: `d2c91865e1a3e75e095e7e5c786565b1e9b94ff2bd7949cfa2899c55ef683e8b`.
- `reports/cards/c1/reviews/repair-local-receipt-r2.json`: `6dd78a2db440330b90f078244ef370445909377c1b07dcb41ee21e3b2d3b8936`.
- `reports/cards/c1/reviews/repair-local-tests-r2.log`: `5d0b234bfae34376819e96bb10b1a95c9a69e391d39598daad81d5404858a633`.
- `reports/cards/c1/tools/final_gate.py`: `f1eb2e557d73010def69aea9adfeaf8a1ce47c3b5e40d87ac66342a339db2953`.
- `reports/cards/c1/tools/final_gate.sh`: `297fbbb2f0c0e3f4c4368afdd4245b78792408075ce94f655dc7bc8209caf1d5`.
- `reports/cards/c1/tools/final_gate_contract.py`: `222c69314e26d5aefcc3ad04a602ccac6e207ee7d22c65a5930a18d8ad291ad8`.
- `reports/cards/c1/tools/gate_compare.py`: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.
- `reports/cards/c1/tools/gate_fixtures.py`: `8737b53fde2966d14ce6359cd0c3e5e24cc783bb9c7b1348b3ff468df2cfbf21`.
- `reports/cards/c1/tools/gate_roots.py`: `155cbdb4b11ea8239057600e191465f073418f648070ee8f20f14cab25aefc5f`.
- `reports/cards/c1/tools/gate_worker.py`: `88a526b4cda2f8ed031c12520821a267c51a93b768bcd2ebe87da4cd230f9c60`.
- `reports/cards/c1/tools/test_final_gate_contract.py`: `6e94910e3d0e4ec120ecd18a6ad4ac17e189aa9ee76f317eae080d84f4714fcf`.
