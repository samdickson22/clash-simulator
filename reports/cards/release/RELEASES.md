# CARD runtime releases (exploration tier)

## r1-cards1

Status: RELEASED, READ-ONLY. Assembled once on 127x08 and distributed to 127x03/127x04. Runtime and integrity verification PASS on every host.
No sealing or commits. Later r1-cards2 and live16402b releases were authorized by the lead's `FINAL` message; see their sections below.

- Root on all three hosts: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1`.
- Source commit (explicit requested main snapshot): `0ee42633e92f260dba9004196b0190eb38ef1b90`; frozen code used for Runtime checks.
- Release timestamp from `date -u`: `2026-10-16T03:33:21Z`.
- Native SHA256: `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b` (existing native-total-r1 binary, no compile).
- gamedata.json SHA256: `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
- RELEASE `RECEIPT.json` SHA256: `8121107cd296ece68f0daa8c11fb30bcfb9efb164e4435e5fa070ae8842b77f0`.
- Assembler `CARDS-RUNTIME-RECEIPT.json` SHA256: `13ecef349fa451bfb39c1e9f98b66a66f514501e4dcb85f5a286337b3cd31ace`.
- Overlay manifest SHA256: `b98ea61c5dd438f26bfbdd42bdf51efbabe289a26964922b69730eff7b02aad3`; 473 files, 9 changed from r1.
  Every destination-relative overlay path and command-computed SHA256 is in both root receipts.
- Base receipt: `r1/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts/linux05-20261010-r1/receipt-manifest.json`;
  SHA256 `88d48bfcfdcc2282770ab0844ae1293a702efbc76b44b5e4bcc95905980c66aa` on all three hosts.
- Full base content manifest SHA256: `1ec957e2c507c37ba6bfe15e6623ee8403deda2c4b9958c8b0e692e3380fb040` on all three hosts,
  10,256 entries. File contents, directory/symlink entries, and POSIX modes matched before assembly.
- Full released tree content manifest SHA256, before adding RECEIPT.json: `820deeb0e017196606a0fe4b0a54841d398227e68f0148f0916f5adc2a103bcd`.
- Detailed local audit directory on 127x05: `/mpac/sdicks02/jobs/clasher/cards/r1-cards1-release-sz1bk6jr`; same job path on 08 contains build/finalize/verify logs.

Procedure: exported tracked commit with git archive; `nice -n 15 python3 repo/bot/cards/build_runtime.py
--release --tree <job>/source --base /mpac/sdicks02/repos/clasher-bot-runtime/r1
--target /mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1 --native /mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1/clasher_core.abi3.so`.
Copied with `nice -n 15 rsync -a --checksum` from 08, without `--delete` or hardlinks.
All target paths were checked absent, then each destination was reserved with mkdir; any existing target would stop the procedure.
`chmod -R a-w` applied only to each new release root. Receipts were generated once on 08 and copied byte for byte.

Assumptions and observed differences from the brief:

- cards/lead had advanced, so assembly and verification use the explicitly requested 0ee42633e snapshot.
  Its engine overlays include the committed Python changes; native remains the explicitly requested r1-cards1 pin.
- Existing r1 has writable entries; it was treated as immutable input without changing its modes.
- Existing r1 has no top-level release receipt. Its packaged original receipt-manifest.json above is used,
  supplemented by the independently computed complete base content manifest. No receipt was added to r1.

Verification environment on every host: `CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1`,
`CLASHER_BOT_RUNTIME_PINS=r1-cards1`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`,
all library thread counts 1, `nice -n 15`, and existing clasher-bot/.venv/bin/python.
`CLASHER_ROOT`, `CLASHER_EVAL_RUNTIME_ROOT`, and `CLASHER_DELAY_NATIVE_DIR` cleared first so the root supplies its own engine/native.
Checks include `Runtime(verify=True)`, pin settings (`full`, fc_side_cut=True), all overlay hashes,
base/assembler receipt hashes, and absence of write permission on all non-symlink entries.

Host results (121 metadata cards, 237 config entries including Mirror payloads, 350 templates on each host):

- 127x03: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1`; `Runtime(verify=True)` **PASS** at `2026-10-16T03:36:22Z` (95.119 s).
  Native SHA256 `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `8121107cd296ece68f0daa8c11fb30bcfb9efb164e4435e5fa070ae8842b77f0`; assembler receipt SHA256 `13ecef349fa451bfb39c1e9f98b66a66f514501e4dcb85f5a286337b3cd31ace`.
  All 473 overlay hashes PASS; full release content manifest PASS; read-only PASS; base r1 contents and modes unchanged PASS.
- 127x04: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1`; `Runtime(verify=True)` **PASS** at `2026-10-16T03:35:48Z` (63.021 s).
  Native SHA256 `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `8121107cd296ece68f0daa8c11fb30bcfb9efb164e4435e5fa070ae8842b77f0`; assembler receipt SHA256 `13ecef349fa451bfb39c1e9f98b66a66f514501e4dcb85f5a286337b3cd31ace`.
  All 473 overlay hashes PASS; full release content manifest PASS; read-only PASS; base r1 contents and modes unchanged PASS.
- 127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards1`; `Runtime(verify=True)` **PASS** at `2026-10-16T03:34:52Z` (62.1 s).
  Native SHA256 `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `8121107cd296ece68f0daa8c11fb30bcfb9efb164e4435e5fa070ae8842b77f0`; assembler receipt SHA256 `13ecef349fa451bfb39c1e9f98b66a66f514501e4dcb85f5a286337b3cd31ace`.
  All 473 overlay hashes PASS; full release content manifest PASS; read-only PASS; base r1 contents and modes unchanged PASS.

All three release receipts and assembler receipts are byte-identical by SHA256, and their complete release content manifests match.
Portable evidence: [RECEIPT.json](r1-cards1/RECEIPT.json), [assembler receipt](r1-cards1/CARDS-RUNTIME-RECEIPT.json), [per-host verification](r1-cards1/VERIFICATION.json).

Existing runtime directories were not written, renamed, chmodded or deleted. No commits or sealing performed.
Step 1 completed before the lead's `FINAL` authorization for the later releases below.


## r1-cards2

Status: RELEASED, READ-ONLY on 127x03/127x04/127x08. Runtime and complete-content verification PASS on all three hosts. Authorized by the lead's `FINAL` message. No sealing or commits by this worker.

- Root on 127x03, 127x04, and 127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2`.
- Verified source dev root: `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards2-dev`; copied without hardlinks.
- Engine source commit: `878d5f459d58112527e9c3e76c804f27e5d7c0a3`.
- Runtime/PIN_SETS snapshot: `e545eb6bda67d30418c6136bbdcda7f52374e0c8` (git archive; no uncommitted source shipped).
- Release creation from `date -u`: `2026-10-16T06:48:05Z`.
- Native SHA256: `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
- gamedata.json SHA256: `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
- RELEASE `RECEIPT.json` SHA256: `257f309de64b315de6723833a05b896729fbe21f8a320110d08225a058e7516b`.
- Preserved assembler `CARDS-RUNTIME-RECEIPT.json` SHA256: `87d4cf225ebdaf39a00650080246a5b01d42c8ac54e702005aab0a2b1e50439c`.
- Engine overlay source manifest SHA256: `b98ea61c5dd438f26bfbdd42bdf51efbabe289a26964922b69730eff7b02aad3`; all 473 committed source overlay files verified against the exact 878d5f459 export.
- Released overlay manifest SHA256: `b98ea61c5dd438f26bfbdd42bdf51efbabe289a26964922b69730eff7b02aad3`; all 473 destination overlay hashes recorded in the release receipt (including the final gamedata.json).
- Complete copied content manifest SHA256 before adding the release receipt: `7175dfba05b209dc5cfe7764678d5341f807e146e627ed74a30e650f0597fab5`. Includes the native, assembler receipts, all other runtime files, directories, and symlink targets.
- Base r1 receipt: `/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts/linux05-20261010-r1/receipt-manifest.json`; SHA256 `88d48bfcfdcc2282770ab0844ae1293a702efbc76b44b5e4bcc95905980c66aa`.

Procedure: verify final dev receipts against `reports/cards/r1-cards2/receipts/artifacts-de11f124.json`, source overlays against the exact engine export, and native/gamedata against e545eb6bd PIN_SETS; copy once on 08; generate a release receipt with command-computed SHA256s and `date -u`; distribute using `nice -n 15 rsync -a --checksum`, without `--delete`; apply `chmod -R a-w` only to each new root. Targets checked absent before creating each destination; any existing target stops the operation.

Original assembler receipts are unchanged, including their legacy `pins=r1-cards1` / `pins=live16402` labels and dev output paths. The release receipt records the actual new root and pin selection. The r1-cards2 dev source has writable entries; it remains unchanged while all release copies are read-only.

Verification uses `CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2`, `CLASHER_BOT_RUNTIME_PINS=r1-cards2`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, existing clasher-bot/.venv/bin/python, `nice -n 15`, and one thread per numerical library. Clear CLASHER_ROOT/CLASHER_EVAL_RUNTIME_ROOT/CLASHER_DELAY_NATIVE_DIR before each fresh process. Each check builds `Runtime(verify=True)` and verifies all overlay/receipt hashes, the full copied content manifest before and after Runtime, and read-only permissions.

Detailed audit job: `/mpac/sdicks02/jobs/clasher/cards/final-cards-release-w0wsioqg` on 05/08; per-host runtime logs use that same path. Portable release receipt: [r1-cards2/RECEIPT.json](r1-cards2/RECEIPT.json).

Host results for r1-cards2:

- 127x03: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:50:33Z` (67.561 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `257f309de64b315de6723833a05b896729fbe21f8a320110d08225a058e7516b`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 237 config entries, 350 templates.
- 127x04: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:50:26Z` (61.556 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `257f309de64b315de6723833a05b896729fbe21f8a320110d08225a058e7516b`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 237 config entries, 350 templates.
- 127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:49:28Z` (57.842 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
  RECEIPT.json SHA256 `257f309de64b315de6723833a05b896729fbe21f8a320110d08225a058e7516b`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 237 config entries, 350 templates.

All three release receipts are byte-identical by SHA256; full copied contents match the verified final dev source on each host. Existing runtime directories, including r1-cards1, remain unchanged (contents, modes, and symlinks checked before/after on each host). Both original dev source trees also remain unchanged. Evidence: [r1-cards2/VERIFICATION.json](r1-cards2/VERIFICATION.json).


## live16402b

Status: RELEASED, READ-ONLY on 127x03/127x04/127x08. Runtime and complete-content verification PASS on all three hosts. Authorized by the lead's `FINAL` message. No sealing or commits by this worker.

- Root on 127x03, 127x04, and 127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b`.
- Verified source dev root: `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/live16402b-dev`; copied without hardlinks.
- Engine source commit: `878d5f459d58112527e9c3e76c804f27e5d7c0a3`.
- Runtime/PIN_SETS snapshot: `e545eb6bda67d30418c6136bbdcda7f52374e0c8` (git archive; no uncommitted source shipped).
- Release creation from `date -u`: `2026-10-16T06:48:12Z`.
- Native SHA256: `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
- gamedata.json SHA256: `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
- RELEASE `RECEIPT.json` SHA256: `2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac`.
- Preserved assembler `CARDS-RUNTIME-RECEIPT.json` SHA256: `87d4cf225ebdaf39a00650080246a5b01d42c8ac54e702005aab0a2b1e50439c`.
- Preserved assembler `LIVE16402-RECEIPT.json` SHA256: `81f5ccb3e054449cd64788161514ef2f302481f28b1167a1594c6542f08d4204`.
- Engine overlay source manifest SHA256: `b98ea61c5dd438f26bfbdd42bdf51efbabe289a26964922b69730eff7b02aad3`; all 473 committed source overlay files verified against the exact 878d5f459 export.
- Released overlay manifest SHA256: `71f04931e77d9c58038b4c3d5a4679c82204899796baa3cd7c7559a9346aab7c`; all 473 destination overlay hashes recorded in the release receipt (including the final gamedata.json).
- Complete copied content manifest SHA256 before adding the release receipt: `fbd96843d2a73895b559274e9f406fc4bb550fe9f7787ac6cfbc9bd2de2110db`. Includes the native, assembler receipts, all other runtime files, directories, and symlink targets.
- Base r1 receipt: `/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts/linux05-20261010-r1/receipt-manifest.json`; SHA256 `88d48bfcfdcc2282770ab0844ae1293a702efbc76b44b5e4bcc95905980c66aa`.
- Balance overlay: 79 applied slots; all 4 source-input hashes verified against their existing files. Original overlay detail retained inside the runtime; only hashes recorded here.

Procedure: verify final dev receipts against `reports/cards/r1-cards2/receipts/artifacts-de11f124.json`, source overlays against the exact engine export, and native/gamedata against e545eb6bd PIN_SETS; copy once on 08; generate a release receipt with command-computed SHA256s and `date -u`; distribute using `nice -n 15 rsync -a --checksum`, without `--delete`; apply `chmod -R a-w` only to each new root. Targets checked absent before creating each destination; any existing target stops the operation.

Original assembler receipts are unchanged, including their legacy `pins=r1-cards1` / `pins=live16402` labels and dev output paths. The release receipt records the actual new root and pin selection. The r1-cards2 dev source has writable entries; it remains unchanged while all release copies are read-only.

Verification uses `CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b`, `CLASHER_BOT_RUNTIME_PINS=live16402b`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, existing clasher-bot/.venv/bin/python, `nice -n 15`, and one thread per numerical library. Clear CLASHER_ROOT/CLASHER_EVAL_RUNTIME_ROOT/CLASHER_DELAY_NATIVE_DIR before each fresh process. Each check builds `Runtime(verify=True)` and verifies all overlay/receipt hashes, the full copied content manifest before and after Runtime, and read-only permissions.

Detailed audit job: `/mpac/sdicks02/jobs/clasher/cards/final-cards-release-w0wsioqg` on 05/08; per-host runtime logs use that same path. Portable release receipt: [live16402b/RECEIPT.json](live16402b/RECEIPT.json).

Host results for live16402b:

- 127x03: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:51:46Z` (69.051 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
  RECEIPT.json SHA256 `2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 238 config entries, 350 templates.
- 127x04: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:51:30Z` (61.54 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
  RECEIPT.json SHA256 `2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 238 config entries, 350 templates.
- 127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b`; `Runtime(verify=True)` **PASS** at `2026-10-16T06:50:27Z` (56.507 s, including final content audit).
  Native SHA256 `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata SHA256 `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
  RECEIPT.json SHA256 `2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac`; full content manifest, all 473 output overlay hashes, and read-only checks **PASS**.
  121 metadata cards, 238 config entries, 350 templates.

All three release receipts are byte-identical by SHA256; full copied contents match the verified final dev source on each host. Existing runtime directories, including r1-cards1, remain unchanged (contents, modes, and symlinks checked before/after on each host). Both original dev source trees also remain unchanged. Evidence: [live16402b/VERIFICATION.json](live16402b/VERIFICATION.json).


Final release step complete: r1-cards2 and live16402b are released and verified on all three requested hosts. No existing runtime roots modified, no commits, no sealing.


## r1-cards2-r2 and live16402b-r2

Status: **RELEASED, READ-ONLY** on 127x03/127x04/127x08. Final Runtime and complete-content verification **6/6 PASS** (exploration tier; no sealing).
Patch source commit: `234e5cd899ebea077e3cbe3e95dab5e0cf4aa0b6`.
Python fixes: optional spell building/ordinary damage and the public body HP fallback for ThreeMusketeers.
Native and gamedata pins are unchanged. Both roots contain three patched Python files; all other copied
files are inherited from their immutable parent roots.

r1-cards2-r2:

- Root on 127x03/127x04/127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2-r2`.
- Native SHA256: `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
- gamedata.json SHA256: `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
- Final RECEIPT.json SHA256: `4c509b531959c90dd07e7a83cc9a877345333e2e7d06992f01444de8ed1b1dba` (same receipt bytes on every host).
- Complete content/mode/symlink manifest SHA256: `64ae60c2b2121a112fef1c322e378ae8264096148ca7c07d74c018882401c6c3`.
- Parent receipt SHA256: `257f309de64b315de6723833a05b896729fbe21f8a320110d08225a058e7516b`; parent contents and modes checked unchanged.
- [RECEIPT.json](r1-cards2-r2/RECEIPT.json); [per-host verification](r1-cards2-r2/VERIFICATION.json).

live16402b-r2:

- Root on 127x03/127x04/127x08: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2`.
- Native SHA256: `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
- gamedata.json SHA256: `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
- Final RECEIPT.json SHA256: `32028a65d30f08b5efdbde77c020f93e9aaf252d98a7efaec407e02b0ebb9499` (same receipt bytes on every host).
- Complete content/mode/symlink manifest SHA256: `ff8dc4d2dcda59abeac2b8e76c8e0ec182387f148127c58a51a346fed6c5f5ba`.
- Parent receipt SHA256: `2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac`; parent contents and modes checked unchanged.
- [RECEIPT.json](live16402b-r2/RECEIPT.json); [per-host verification](live16402b-r2/VERIFICATION.json).

Procedure: reserve absent destinations, copy each immutable parent without hardlinks, and apply only committed
Python patches. The second audit found a real ThreeMusketeers HP conversion crash during final validation.
The newly created r2 assemblies were corrected before final handoff; their receipts retain the first assembly
receipt SHA and the correction reason. Only these task-created r2 assemblies were written during correction;
all pre-existing parent/runtime roots stayed untouched. Final assemblies are read-only, including receipts.
Assembler receipts and the parent release receipt are preserved byte for byte inside each new root.

`release_none_stats.py verify` checks Runtime(verify=True), all 473 overlay hashes, assembler and parent receipts,
all three committed patch hashes, the complete content/mode/symlink manifest before/after Runtime, read-only
permissions, and parent-root invariance. Full-pool/None audit, K4L command hashes, native totality probes, and
exact game 2000024 replay are recorded in [NONE-STATS.md](../runtime/NONE-STATS.md).

Scratch job: `/mpac/sdicks02/jobs/clasher/cards/none-stats-r2-bchzbvd5` on 03/04/08, with local receipts on 05.
04/08 work used `bot/exit/cpu_job.sh` leases of 1, 2 or 4 and nice 15; numerical libraries used one thread.

r1-cards2-r2 final Runtime(verify=True), full content and read-only checks:

- 127x03: **PASS**, `2026-10-16T07:40:11Z`; 473 overlays, parent unchanged, 121 metadata cards, 237 config entries, 350 templates.
- 127x04: **PASS**, `2026-10-16T07:39:32Z`; 473 overlays, parent unchanged, 121 metadata cards, 237 config entries, 350 templates.
- 127x08: **PASS**, `2026-10-16T07:39:42Z`; 473 overlays, parent unchanged, 121 metadata cards, 237 config entries, 350 templates.

live16402b-r2 final Runtime(verify=True), full content and read-only checks:

- 127x03: **PASS**, `2026-10-16T07:42:04Z`; 473 overlays, parent unchanged, 121 metadata cards, 238 config entries, 350 templates.
- 127x04: **PASS**, `2026-10-16T07:40:40Z`; 473 overlays, parent unchanged, 121 metadata cards, 238 config entries, 350 templates.
- 127x08: **PASS**, `2026-10-16T07:40:57Z`; 473 overlays, parent unchanged, 121 metadata cards, 238 config entries, 350 templates.

Final gates: all-card probe **55,834 checks / 0 exceptions or panics**, C56 ranking **8,496 exact comparisons**,
K4L HEADLINE **12/12 command hashes identical**, native totality **26,828 probes / 0 panics / 0 unexpected errors**.
Game 2000024 reproduces the original crash and completes on live16402b-r2 at tick 3601 with command SHA256
`fa51cd35e7ceca754336735355d75717dac0aea98947f01cc76b5839d2a39df9`. No training rows sealed.
