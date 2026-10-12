# SOL review — K4S END S2/S4, round 3

**S2: REQUEST_CHANGES. S4: REQUEST_CHANGES.** All five enumerated round-2 findings are fixed in the reviewed entrypoints. New probes establish static Git indirection in both components and an incomplete outcome-name gate in S4. S4 also needs to finish its E4 tree-metadata checks before requesting receipt blobs. Passing tests do not establish refusal-before-read for these cases.

## Authority, scope and reviewer disclosure

Reviewed offline on 2026-10-12 against immutable candidates in `/mpac/sdicks02/repos/clasher`:

- S2: **dc278cca**, `reports/explore/k4s-confirm/run-r1/end-prep/s1s2-r3/`.
  - `s2_end_evidence.py`: **973a5ace14fd78afd39f162320a7633e8cd18206be53102679778db12dcdc19f**.
  - `RESPONSE-r2.md`: **e4825b4d2de474527392dc6f0c85115c86babccabb1d61dfc27e5f37973f434f**.
  - S1 remains **b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65**; its approved code is unchanged.
- S4: **55229c77**, sibling `b3-r3/` and superseding `b3-r3b/`. The verdict applies to r3b.
  - `b3-r3b/assemble_fleet_reference.py`: **db4095c0146350ca6a1ea6604cc0039d7103e4782da749098787560934556d10**.
  - Tests: **5001b5ad93486ceb0548669695d5ea688d61d1c69a2b5ab5652fa46536cdcea3**.
  - `RESPONSE-r2.md`: **28bcac613270415761376605dce933a4acaedb7d4b1fbb7aa9988fad786e7c5b**.

`S2:L` and `S4:L` below refer to line L in those immutable source files. I read both complete package-1 reports, the package-2 report, the candidate responses and READMEs, and coordinator rulings through `git show origin/main:reports/strategy_council_20260928/COORDINATOR.md`. The observed origin/main was **13fb31d036e0d91bc5c4c154b9ffc3926f658d9c**. E1–E4, R6/R7 and P2-1–P2-3 govern this review. Shared `safe_input` adoption is deferred to r4; absence of that adoption is not itself a finding. Static aliases and wrong input roles are distinct from the accepted concurrent check/open replacement residual.

**Reviewer boundary lapse:** my initial frozen-code export used a recursive e4v3 tree listing rather than a direct-file allowlist. It consequently copied **92 committed files under e4v3/receipts/**, including the `linux05-20261010-r1` and `-r2` receipt subtrees and their `tiers-complete.json` files. This consumed committed host-receipt bytes and violated the requested no-real-host-data boundary. Their contents were not displayed, parsed, decompressed or used in the tests or findings. I removed all receipt/test subtrees from the scratch export and retained only direct e4v3 files plus the specifically required frozen guard/plan/reference metadata. This disclosure does not undo the access. None of the four real E4 `complete.json` blobs was opened or hashed, and no live host files, Q6 bytes, SSH connection, candidate edit, repository commit or push was performed. Fixture repositories alone received synthetic commits and replacement refs.

## S2 — round-2 disposition

1. **S2-R2-F1 — FIXED for its enumerated filesystem/auxiliary cases.** `forbidden_reason()` rejects outcome/strict-END components, receipt-name families, K4S/T1 job trees and host-job roots (`S2:210–232`). `Roots` supplies role-specific allowed roots (`:235–254`). `gate_paths()` checks every supplied path lexically before its lstat pass (`:285–294`). Build, validate and both diagnosis routes use it (`:571–573`, `:839–842`, `:1038–1039`, `:1056`); main gates the result before writing (`:1147`). S1 receipts and profiles use `read_gated()` (`:516`, `:823`), with component-wise no-follow reads and regular/nlink/identity checks (`:328–360`, `:387–391`). Exact evidence roles remain enforced before the frozen reader (`:753–774`, `:864–885`). The new Git finding below is a separate boundary beneath these filesystem gates.

   Independent repeat: a valid profile and a valid S1 receipt at synthetic `reports/explore/k4s-confirm/end/end-raw.json` each refused with exit 2; audit events showed no access to the forbidden canary. The delivered full-entrypoint tests also cover build/diagnosis, aliases, wrong SHAs and invalid schemas.

2. **S2-R2-F2 — FIXED.** Exactly one profile source is required, including test mode (`S2:813–816`). Every host profile must be a nonempty object with the required fields and exact types/values (`:787–808`); duplicate keys and nonfinite JSON constants refuse (`:415–427`). The supplied profile is used directly, without defaults (`:899`). Source path and SHA are recorded (`:830–831`, `:925`). Independent `{ "127x03": {}, "127x04": {} }` and null-per-host repeats both returned exit 2/`ok:false`, without `profile_source` or `hosts`. Valid supplied/default profiles and their source labels pass the delivered controls.

The fixed 74314eda bootstrap, cached verified-module execution, exact artifacts, S1 metadata bindings, membership and finite-positive MHz checks remain in place. No new masked-nonzero finding: `git()` checks status before returning stdout (`S2:195–198`), and a valid-looking stdout/rc-37 probe refused.

## S2 — new required finding

1. **S2-R3-F1 — BLOCKING: Git replacement refs and inherited repository overrides bypass the declared read identity/root.** `git()` invokes `git -C <repository>` with the inherited environment and replacement-object handling enabled (`S2:195–198`). `pinned_completion()` consumes `git show` output before its SHA decision (`:501–504`); build/diagnosis use it (`:577`, `:1058`). Fixed role names do not prevent Git from substituting another object's bytes. The frozen reader's `k4s_logic.git_bytes()` has the same inherited-environment behavior (committed `mac/k4s_logic.py:510–514`).

   **Independent reproductions, normal and -O:** in a synthetic repository, create a static `git replace <completion-blob-oid> <games-canary-oid>`. The unchanged S2 helper returns the synthetic outcome canary when asked for the fixed completion path. A full S2 build passes its path gates, reads those replacement bytes, then refuses the completion SHA with exit 2. No concurrent replacement occurs. Separately, `GIT_DIR=<synthetic games repository>/.git` makes unchanged `git -C <allowed repository> show HEAD:allowed.json` return bytes from the foreign repository.

   **Required:** disable replacement objects and reject or sanitize inherited Git repository/object/config indirection before authoritative Git access. `GIT_NO_REPLACE_OBJECTS=1` restores the original blob in the reproduction. Ensure the same controlled Git environment reaches the immutable frozen readers; protecting only S2's wrapper leaves their later Git reads exposed. Preserve legitimate detached-worktree support and existing nonzero-status checks. Add synthetic replacement-ref and GIT_DIR controls asserting zero returned outcome bytes, not merely a later SHA refusal. This is a static Git alias, not the accepted TOCTOU residual or a demand to adopt the r4 library early.

## S4 — round-2 disposition

1. **S4-R2-F1 — FIXED.** All ordinary file walks require `st_nlink == 1` (`S4:304–305`), and the opened descriptor is independently checked before being exposed to hashing/parsing/copying (`:320–335`). Source reads/hashes and copies use that descriptor gate (`:338–362`, `:873–881`). E1 recursively walks its target through the same checks (`:292–297`). Independent runtime and measurement hard-link aliases to a synthetic games canary now refuse before that inode is opened. The delivered 25-class matrix, request/self-file controls and post-walk/post-plan link substitutions pass.

2. **S4-R2-F2 — FIXED for the enumerated strict-END namespace cases.** `location_free()` applies the full-path name and END-pair gates (`S4:252–270`); `walk()` calls it before lstat (`:280`). Evidence artifacts, committed admission paths, generic Git paths, seed names, output and guard-job parent also call it (`:560`, `:605–607`, `:721`, `:756`, `:810`, `:855`). Runtime scanning refuses the strict END directory before descending (`:456–460`). The exact previous `end/receipts/round-00/127x03/raw-00/reference-warmup.json` sets reproduction now refuses without opening its inode. Standalone outcome-name gaps remain as a new finding below.

3. **S4-R2-F3 — FIXED.** Synthetic pins now use `absolute()` and `read_confined()` before parsing (`S4:407`), then require the test marker and fixed exception-key sets (`:408–423`). Independent games-location, ancestor-symlink and hard-link pin probes all refuse. Test mode changes pins/stamps, not these gates.

E1 requires exactly the committed root-level mode-120000 entry and exact link text (`S4:564–571`) and the same runtime link (`:292–297`). E3 requires the exact committed admission path (`:596–615`), committed/request/work-tree SHA agreement, and the pinned identities (`:782–801`); stale identity errors expressly require a coordinator re-pin. Production Q6/model/sets/freeze/topology pins, StateRows mirror checks and fresh -pfNN/-rdRR-aNN job forms remain enforced. Live freshness, topology, native/model load and preflight qualification remain external gates.

## S4 — new required findings

1. **S4-R3-F1 — BLOCKING: Git indirection also substitutes outcome bytes beneath S4's E4/role gates.** `git_run()` inherits all Git environment settings except adding `GIT_OPTIONAL_LOCKS=0` (`S4:546–554`). `git_blob()` gates the textual requested path (`:557–561`), and `committed_receipts()` extracts a tree OID then calls `git cat-file blob <oid>` (`:579–593`). Neither disables Git replacement objects.

   **Independent reproductions, normal and -O:** replace the synthetic E2 receipt blob with a synthetic `games/reviewer-outcome.json` blob through a static replacement ref. Even `cat-file blob <original-oid>` returns the outcome canary. Full `plan_bundle()` reads it through the E4 branch, then refuses its SHA. Separately, inherited GIT_DIR redirects `git_blob()` from a permitted textual repository to a synthetic games repository. These mechanisms require no symlink, hard link, concurrent mutation or modification to a confinement helper.

   **Required:** apply the controlled Git environment from S2-R3-F1 to every S4 Git command, including E1/E4 and admission/evidence lookups. Retain the rc check at `:553`; the independent rc-37 control already refuses correctly.

2. **S4-R3-F2 — BLOCKING: the generic gate admits standalone END/outcome receipt names and variants.** `OUTCOME_LEAVES` is a six-name exact, case-sensitive list (`S4:173–184`); `outcome_free()` checks only the exact leaf membership (`:234–243`). The strict END check only identifies adjacent `k4s-confirm/end` components (`:252–257`). Consequently auxiliary reads outside that pair accept `END-FINAL.json`, `attempt-00.json`, `end-raw-copy.json` and `complete-v2.json`. S2's corresponding name-family predicate refuses these.

   **Independent reproductions, normal and -O:** supply valid synthetic sets at each of those four names outside the strict END directory. Unchanged full S4 planning opens each file and accepts the plan with its sets. Synthetic pins make the full fixture possible; the location/read branches themselves are identical in production. With real outcome bytes, production's later sets hash/shape decision cannot undo the read (`S4:669–673`).

   **Required:** reject the END authority/claim and outcome receipt name families before access, consistently across auxiliary inputs, inventory names and Git-relative paths. Preserve legitimate declared health filenames and restrict E4 leaf exemptions to their exact four roles. Add audited controls with valid and invalid payloads proving zero forbidden reads. This is a semantic correction now; it does not require premature shared-layer adoption.

3. **S4-R3-F3 — HIGH: E4 metadata screening is interleaved with blob access, rather than completed first.** The four production path/SHA pairs are correct (`S4:93–101`, `:153`, `:414–423`). However, `committed_receipts()` checks and immediately opens each record inside one loop (`:580–593`). A late unlisted or wrong-mode entry is discovered after earlier receipt blobs have been consumed. The advertised “tree metadata first” ordering is therefore only per entry.

   **Independent reproduction, normal and -O:** commit synthetic stand-ins for all four permitted entries, then `zz-outcome/complete.json`. The helper performs four `cat-file blob` calls before refusing the fifth path. **It does not request the unlisted fifth blob**; this finding must not be described as an unlisted-blob read. A separate production-map probe confirms a changed blob at an exact E4 path is consumed before its SHA refusal.

   **Required for the requested pre-blob gate:** first validate the entire tree's complete.json paths and modes, then access allowed blobs in a second pass. To refuse a changed exact-path blob before its content is consumed, bind its tree OID to approved immutable metadata alongside the ruled SHA256, with replacement objects disabled; retain the hash-only SHA256 verification afterward. No real receipt need be opened to obtain its approved tree identity. Add late-extra/wrong-mode and changed-identity controls that check the blob-call sequence. If hash-before-refusal of changed exact-path receipts is intended as an additional exemption, obtain an explicit coordinator ruling; the present exact-pair exception should not silently become a path-only read grant.

## E4, R6/R7 and test results

Apart from S4-R3-F1/F3, E4 behavior is sound: the exception map cannot widen/narrow/move in test mode; any other complete.json component, including a directory component, refuses before that entry's blob access. Wrong modes and hashes refuse. Runtime entries pass no-symlink/nlink checks and are hashed without JSON parsing (`S4:439–503`). The three non-E2 entries do not enter runtime_files on the frozen membership fixture and none enters the bundle; the delivered opaque-read and frozen-membership tests pass. Missing nonmember runtime copies do not widen the four-entry exception list. DESIGN/OPEN-QUESTIONS remain stale, but the README explicitly identifies the superseding r3b text; this was disclosed, not treated as a new blocking code defect.

R6's evidence-commit route remains necessary: S4 rejects an actual runtime `k4s-confirm/end/` subtree. The separate repository clone can carry END claims. S9 must establish the evidence/END-JOB-only commit relationship and equivalence required by P2-2. R7 plain copies/nlink 1 remain mandatory; S4 writes exclusive independent copies and rehashes them. No real runtime build, production assembly or host preflight was attempted.

All suite/probe interpreters used **/mpac/sdicks02/venvs/k4s-freeze/bin/python 3.12.12**, `nice -n 19`, `taskset -c 0-3`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, and both ordinary and `-O` execution. Source copies were under `/dev/shm/sol-s2s4-r3-PAGV8oJ3`; test fixtures were under `/tmp/sol-s2s4-r3-6bsdHjcS` because S2's test-root rule requires /tmp. Pytest cacheprovider was disabled. Child interpreters inherit affinity/priority, and the supplied S2/S4 helpers propagate optimization; S4 frozen consumers explicitly use -B. S1 tests use their synthetic local SSH shim.

- **S1/S2 delivered suite: 221 passed normally (60.42 s), 221 passed under -O (61.85 s).** This includes 34 unchanged S1 tests, 53 S2 tests and 134 gate/profile tests.
- **S4 r3b delivered permitted suite: 326 passed, 2 deselected normally (32.10 s); 326 passed, 2 deselected under -O (33.03 s).** The two `test_production_q6*` tests were excluded before execution because they read the real T1 Q6 index. Collection performs the delivered existence check only. All permitted frozen-consumer tests ran. I do not independently confirm 328/328 or real-Q6 acceptance.
- **24 independent reviewer probes completed normally and under -O** (2.21 s / 2.19 s). They verify prior reproduction refusals, static aliases, nonzero statuses, and the new acceptance/read behaviors described above. A passing observational probe is evidence of the reported behavior, not a safety approval.
- Optimized runs emitted pytest's standard assertion warning. Delivered test-module assertions are rewritten; S4 and reviewer checks use explicit raises. The inspected candidate gates do not rely on removable asserts.
- Runner mutation claims **53/53** and **43/43** were inspected as supplied records, not independently rerun or adopted as reviewer-verified counts.

## What r4 safe_input adoption must preserve

Preserve lexical refusal before access; complete role/root validation; S2's all-path lexical pass, profile source exclusivity and strict field checks; regular/nlink checks at both walk and opened descriptor; E1's exact committed alias with independently gated target; E4's four immutable opaque roles and frozen inventory membership; E3's exact committed location and stale-identity refusal; exclusive outputs and plain independent copies; fixed pre-import frozen closure verification; exact artifact/S1 bindings; test-only output stamps; immutable clock-join refusal and report-only diagnosis; and status-preserving subprocess handling. The shared Git boundary must additionally disable replacements, prevent inherited root/object redirection and complete metadata checks before protected blob access. All new findings need reviewer regression controls in that layer's consumers.

All temporary source exports, receipt copies, logs, fixture repositories, canaries and reviewer scripts were removed after verification. This report is the sole persistent reviewer output. The new findings require revised immutable candidates and another review; code review does not authorize any host step.

S2: REQUEST_CHANGES — both R2 findings fixed; static Git indirection still reads synthetic outcome bytes.
S4: REQUEST_CHANGES — all three R2 findings fixed; Git indirection, receipt-name gaps and E4 ordering remain.
Tests: 221 S1/S2 + 326 S4 passed in both modes; 2 real-Q6 tests excluded; 24 reviewer probes per mode.
Boundary: initial committed-receipt export lapse disclosed; no real E4 complete.json opened; temporary files removed.
