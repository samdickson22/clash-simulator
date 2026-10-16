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


## r1-cards2-r3 and live16402b-r3

Status: **RELEASED, READ-ONLY** on 127x03/127x04/127x08. Both roots, **6/6 Runtime verifications PASS**.
Exploration tier; no sealing, default changes or active live-pin switch. Accepted main/source commit:
`a6a5401c127bac5eab67ad25495c1922936f8a26`; core checkpoint `1802e899c`, corrected probe `ad961ee93`.
The fix recursively registers exact public identities of nested effects/spawns/deaths, preserving existing
entries, and completes translator lookups. Templates increase from 350 to 355. Native, data and checkpoint
pins match r2.

Source archive SHA256 `bd7849478d49fed1c409db7c7193dbebaf76230d134ef42fd55d40cccbac811a`; member manifest SHA256
`d9e6da30454ca439eb85710261a78c52a930d3a1af0ae3744c150e29924f4f8b`. Explicit `git -c tar.umask=0022 archive`
verified 306 git blobs / 342 members. Each host passed 306 file hashes and 343 kind/path/mode checks before
and after source freeze. The first default-mode archive was rejected and preserved before extraction.
An extra tar comparison on 03 reported only virtual archive UID/GID differences; that log remains. Fresh
independent review approved explicit complete byte/mode verification and normalization of the new source
root before continuing. Existing runtime roots were never modified.

Common paths on every requested host:

- `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards2-r3`
- `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3`

Native SHA256 in both roots: `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.

| Root | gamedata SHA256 | Config SHA256 | Content/mode/symlink manifest SHA256 | Overlay manifest SHA256 |
|---|---|---|---|---|
| live16402b-r3 | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` | `4e7fa282b37a34e0c1b2e81933b06e91523fdd15b5b0b6f51bdc7347ebd741ec` | `a5642f50650e6e763c6bbb837c0b9cc67e76941a3fc016d62d599187c828530b` | `be562eefb73f349dd1b3ae0529d579ea09f2da64245abf4827cc7e7c16542118` |
| r1-cards2-r3 | `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65` | `5ea23abe494686e3ad8cedc678852bd51417fc5920a1f05a88863998b881c6d3` | `cce1cfaeff6cb4e0ea463eada256f7ddbf2b1b2c2284c8b2b9a780203e102df6` | `b4854b9808bc17e9867e7e558e97e4611f23bc56b1e08364321a0d5c39dbdc7e` |

Every root has 474 verified overlay files, 355 templates and 121 metadata cards; config counts are 237/238.
The two changed Python files have exact hashes:

- differential.py: `2e93bdec3607fb434e46d51c5bf9c6f0108a60b534b3d216049e86ae7592860c`
- fair_player.py: `89f0c28b4aab1dba42a56c3a2d0e23949d3e0d22bd5aceee03347e2ed6fecc46`

| Root | Host | RECEIPT.json SHA256 | Runtime verification UTC | Evidence |
|---|---|---|---|---|
| live16402b-r3 | 127x03 | `1b079965c8fa846aa732c3de080c5d6e18008fe4d3467f0833374782fdf40bcd` | 2026-10-16T11:11:35Z PASS | [receipt](live16402b-r3/CREATE-03.json), [verification](live16402b-r3/VERIFY-03.json) |
| live16402b-r3 | 127x04 | `2f60094df4007faecc4b3e2502b2c338255d8fd4650ea614ba74c1f02d387193` | 2026-10-16T10:48:57Z PASS | [receipt](live16402b-r3/CREATE-04.json), [verification](live16402b-r3/VERIFY-04.json) |
| live16402b-r3 | 127x08 | `783efdec1b5e4c10e20953a6e6b5a956eeeaec06dbe28c0bf1a6cd2c3a3b5ce2` | 2026-10-16T10:52:48Z PASS | [receipt](live16402b-r3/CREATE-08.json), [verification](live16402b-r3/VERIFY-08.json) |
| r1-cards2-r3 | 127x03 | `328ddcd8e4a8f43627c368757d1aca6e1fcca54640e6ec3a90f1b2a1bf83936d` | 2026-10-16T10:57:26Z PASS | [receipt](r1-cards2-r3/CREATE-03.json), [verification](r1-cards2-r3/VERIFY-03.json) |
| r1-cards2-r3 | 127x04 | `1fbc95d200081e76fc1abfcd8516b78b02ddea56b4065f35233d474f851d22ac` | 2026-10-16T10:45:30Z PASS | [receipt](r1-cards2-r3/CREATE-04.json), [verification](r1-cards2-r3/VERIFY-04.json) |
| r1-cards2-r3 | 127x08 | `3ab433bd83712e36d52e0fc142fd503a31708c0161902e431d20e09fc8d0f301` | 2026-10-16T10:47:19Z PASS | [receipt](r1-cards2-r3/CREATE-08.json), [verification](r1-cards2-r3/VERIFY-08.json) |

Each internal RECEIPT.json records host/time, parent receipt/full inventory, exact patch source, every
overlay and preserved assembler receipts. Portable RECEIPT.json in each report directory is the 04 receipt;
CREATE-HH.json retains each actual host's receipt bytes. VERIFICATION.json binds all three host results.
Full content/overlay/config manifests agree per root. Runtime verification checks parent invariance and
the complete immutable inventory before/after resource construction. Final postflight passed 963
source-overlay/native/data/checkpoint/receipt hashes and four read-only parent/new trees on each host.

Creation/verification used independently reviewed release_objects.py, SHA256
`6ef8f571c337c643911ef26c0bf454e0c3e7691f79a1b01096393775ac650d3e`. It guards overlap/symlink paths,
uses ordinary copies and new-inode patches, preserves parent/assembler receipts, freezes new roots and
publishes with atomic renameat2 NOREPLACE. Fresh outputs and absent destinations are mandatory; failed
artifacts remain preserved. `J=/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3`,
`S=$J/release-source-a6a5401c127b`, `D=$J/release-a6a5401c127b`. Exact command per host/root/mode:

```sh
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 env \
  -u CLASHER_ROOT -u CLASHER_EVAL_RUNTIME_ROOT -u CLASHER_DELAY_NATIVE_DIR \
  PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= \
  nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B \
  "$S/reports/cards/runtime/tools/release_objects.py" MODE --name NAME \
  --source "$S" --commit a6a5401c127bac5eab67ad25495c1922936f8a26 --out "$D/NAME-MODE.json"
```

MODE is create/verify; NAME is r1-cards2-r3/live16402b-r3. Every job used normal admission. All owned jobs
and leases exited. Independent implementation/release/protocol/coverage/source-mode/scheduling verdicts,
commands and PIDs are retained in [the scoped UTC audit](../runtime/MISSING-TEMPLATES-PROGRESS.md).

Final gates: **122 definitions / 366 scenarios / 96,171 checks / 0 exceptions**, 187 observed/native-
materialized objects and 142/142 config identities; **K4L 12/12 exact**, assembler original **11/11** and
review **12/12**; actual-r3 **55,834 None-stat checks / 0 exceptions**, **8,496 exact C56 rankings**;
totality **26,828 probes / 0 panics / 0 unexpected errors**, 487 deliberate plain unsupported-card guards,
both scrub variants with zero failures. Exact game 5000110 completes on r3 at tick 4079, winner 0, command
SHA256 `dc7c5a5c20648c930852405cbd69a59b9bbd02d5028d10aec6863e12796920c2`. Its fresh r2 pair reproduces
BarbarianRageDamage/AreaEffect with all eight frozen input hashes identical before/after both runs. All
331 teacher rows stayed in memory. Historical r2 negative control is retained.
[Machine result and all receipt hashes](../runtime/receipts/MISSING-TEMPLATES-RESULTS.json);
[class table and scope limits](../runtime/MISSING-TEMPLATES.md).

PIN_SETS: `bot/players/runtime.py:77` r1-cards2-r3 and `:79` live16402b-r3, full scope/fc_side_cut, matching
native/data/checkpoint pins; live Fireball/Poison crown settings retained. The separate LIVE two-call vocab
patch was integrated by its owner at `ae3f6b0c579c5c817630b92a64089917c6623704`, source only. No code patch
remains for this fix. Active LIVE pin selection stays with LIVE LEAD.

Rollback selects the retained matching r2 root and pin in the opt-in caller:
`CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2` and
`CLASHER_BOT_RUNTIME_PINS=live16402b-r2`, or the corresponding r1-cards2-r2 pair. Existing roots remain
immutable and retained. G1/K1 keep their existing selections/retry rules until their owner accepts released
receipts and host preflights; publication does not migrate them.


## r1-cards3 and live16402c

Status: **RELEASED, READ-ONLY on 127x03/127x04/127x08; 6/6 Runtime(verify=True) PASS**. Exploration tier, no sealing, default change or active LIVE pin switch. Release authorized by CARD LEAD’s FINAL and subsequent explicit adjudication of the orphan-rider fixture artifact and handled GoblinGiant fallback.

Engine: **main + B1 + B2**, exact source `8eaa7d1ecac2f46a2c7d8d512a46ba4f03f7cb63`; native SHA256 on every host/root: `326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732`. All 507 tracked engine files in the B1+B2 native build tree match this commit; the 508-file export also includes committed fair_player.py. Native copied from 08 `jobs/clasher/cards/b1b2/out`; build UTC 2026-10-16T17:12:53Z–17:13:23Z. The accepted r3 None-stat/template fixes remain present. Matching PIN_SETS use full scope, fc_side_cut=True, inherited v1/R3a checkpoints, and Fireball/Poison crown derivation for live16402c.

| Root (same path on 03/04/08) | gamedata SHA256 | Complete read-only content/mode/symlink manifest SHA256 (excluding RECEIPT.json) |
|---|---|---|
| `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards3` | `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65` | `30425d27563d87f2d76052bcfd929f64ce476e42d99abaf8bada325084cd6652` |
| `/mpac/sdicks02/repos/clasher-bot-runtime/live16402c` | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` | `7de3ed3cfb9516f626a6db11b7aabe2bde1f96adf5a09205a19b6abe42ed52b8` |

| Root | Host | RECEIPT.json SHA256 | Runtime(verify=True) UTC |
|---|---|---|---|
| r1-cards3 | 127x03 | `e90489148b1e08930f32f9dc84724e9ba7f44aa9df3e0adb65f202b43942ff61` | 2026-10-16T19:38:22Z PASS — [receipt](r1-cards3/CREATE-03.json), [verify](r1-cards3/VERIFY-03.json) |
| r1-cards3 | 127x04 | `0e0de113e68b73895259a8ec760b146847ba43fc87c86454008ab06847e543c7` | 2026-10-16T19:35:12Z PASS — [receipt](r1-cards3/CREATE-04.json), [verify](r1-cards3/VERIFY-04.json) |
| r1-cards3 | 127x08 | `86a62b245ac7c1be7f40d52730a7bfca727cdcb0f9ce669898700663efda8221` | 2026-10-16T19:35:12Z PASS — [receipt](r1-cards3/CREATE-08.json), [verify](r1-cards3/VERIFY-08.json) |
| live16402c | 127x03 | `0b8701c289ebfc81269847979c6219957b1a6ba6eb0a62eaafefd80005096619` | 2026-10-16T19:42:24Z PASS — [receipt](live16402c/CREATE-03.json), [verify](live16402c/VERIFY-03.json) |
| live16402c | 127x04 | `4617b19092b7fdc7a2114704b7468c6a514522dfdbe93ffed92ce9a7a5b160be` | 2026-10-16T19:36:43Z PASS — [receipt](live16402c/CREATE-04.json), [verify](live16402c/VERIFY-04.json) |
| live16402c | 127x08 | `2e0891da57f5952fcd292182af0b22838df14a4ff30d50ee7bbdbef5072270ac` | 2026-10-16T19:36:40Z PASS — [receipt](live16402c/CREATE-08.json), [verify](live16402c/VERIFY-08.json) |

Every host passed all **476 overlay hashes**, native/data/checkpoint pins, complete copied content/modes/symlinks before/after Runtime, read-only permissions and unchanged r1-cards2-r3/live16402b-r3 parents. Both roots have 121 metadata cards and 359 templates; config entries are 237/238. Per-root complete content manifests agree across all three hosts. Receipts intentionally differ by host/time/parent receipt; each portable RECEIPT.json above is the 04 receipt, with CREATE-HH.json preserving actual host bytes.

Procedure: verified dev roots on 08 → private ordinary read-only snapshots → checksum rsync to 03/04 → new sibling staging directory → host/time/source/parent receipt → freeze → atomic Linux renameat2 NOREPLACE. No hardlinks or deletion/replacement of existing roots. All six targets checked absent globally and again at publication. Snapshot manifest SHA256 `ccb6a89141cfcbd9344aa4e61978b8b1167c6f029e97083a0863b2c9892f6563`; release tool SHA256 `0b2afd9cf99a40b59e749bf15b819dc62d9d11290f701b0248b7bf37d19a23e8`; verified runtime.py SHA256 `24e98fd761767f3ed1a2f3add4321ab7996ccd2b533039a5cb126e0632579787`. Preserved assembler receipts retain their historical labels/paths; each new RECEIPT.json selects the actual root/pins. All source/overlay details remain in runtime roots; git carries hashes and aggregate receipts only.

Gates: **Runtime 2/2**, **K4L HEADLINE 12/12 identical** vs r1-total, **26,828 totality probes / 0 panics / 0 unexpected errors**, **77,684 full-pool None-stat checks / 0 exceptions**, **122 definitions / 366 corrected class scenarios / 96,792 checks / 0 exceptions**, 191 observed/materialized objects and 144 config identities, **6/6 mixed LIVE K4L + fast runs / 0 crashes**. The lead’s independent combined gate passed 577 fixtures/577 chains/300+300 roots and stun 192/192. The corrected harness honors explicit public aliases and supplies an observed GoblinGiant parent for attached-rider fixtures; it does not suppress root exceptions. Original orphan rejections remain negative controls. Five filesystem release controls passed, including atomic no-replace and parent/source invariance.

**Known issue:** one mixed LIVE GoblinGiant game recorded one root-graph error and fast fallback, without a crash/panic. The lead accepted this as nonblocking and routed it to the B1 owner separately. No claim that all GoblinGiant public boards reconstruct successfully. HEADLINE/mixed measurements use the documented frozen r3-compatible caller contract; current slot-permission callers need their owner’s matching package. See [RESULTS](../r1-cards3/RESULTS.md) for exact caller hashes, historical attempts, scope and receipts.

All compute used normal cpu_job leases ≤4 (release/verification1), nice 15 and single-thread numerical libraries. No 01/02 or09–18 compute; no emulator, tailscale, crontab, model/account/default/live-selection changes. Existing release roots and original dev roots remain unchanged. Rollback selects the retained r3 root and matching r3 pin. This publication does not migrate active callers.
