# CARD runtime releases (exploration tier)

## r1-cards1

Status: RELEASED, READ-ONLY. Assembled once on 127x08 and distributed to 127x03/127x04. Runtime and integrity verification PASS on every host.
No sealing or commits. Later r1-cards2 and live16402b releases await the lead's explicit `final` message.

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
Step 1 complete; waiting for the lead to say `final` before creating r1-cards2 or live16402b.

