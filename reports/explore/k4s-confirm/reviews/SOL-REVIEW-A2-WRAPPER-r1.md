VERDICT: APPROVE

Reviewed only the wrapper's use of the already-approved r6 tools, offline, before its first run. Target: `reports/explore/k4s-confirm/run-r1/end-staging/a2/a2.sh` at commit `e8a8e32b9b0f9f19d89ca9613b5dbaf9431d2c86`; request: `end-staging/a2/A2-GO-REQUEST.md` at that commit. Line references below refer to that wrapper unless otherwise specified.

The committed bytes (read with `git show`) and `/mpac/sdicks02/k4s-runner/run-r1/end-staging/a2/a2.sh` are byte-identical. Both SHA-256 values are `49c22eec9918699f47e5e873fbcc5c19894c3af25bf91eb101d64bca3d24e603`. Bash syntax validation passed. Neither the wrapper nor either host tool was executed, and no SSH or host contact occurred.

No blocking findings.

Non-blocking finding:

- **Low — `a2.sh:16`: unchecked working-directory change.** If `/tmp` cannot be entered (for example, permissions change), `cd /tmp` fails but staging continues from the caller's working directory because there is no `set -e` or explicit check. Prefer `cd /tmp || exit 2`. This does not block this wrapper: its tool/input/record paths are absolute, Python uses `-I -B`, and S11 explicitly allocates its local temporary bundle under `/tmp`; the failed `cd` does not select a different remote host or destination.

Argument and shell checks:

- `a2.sh:19-20` matches S10's argparse (`s10_stage_host.py:1022-1048`). `--bundle` has `nargs=3`: directory, SHA-256 of `tiers-pins.json`, SHA-256 of `assembly-receipt.json`. `${!tp}` and `${!rc}` supply those two values in that order. `--guard-manifest-sha256` pins `guard-job-manifest.json`, as consumed by S3 verification through S10.
- Only pf00 gets `--create-base`, `--runtime`, `--tools-source`, and `--end-inputs`. Both later tiers get `--runtime-manifest-for-checks` plus the same manifest SHA, so they check runtime consistency without restaging the runtime or recreating the base. All six existing `end-staging/r6-rebuild/dry/s10-dry-<host>-<tier>.txt` plans agree on the host, hashes, guard name, destinations, and component sets: five components for pf00; bundle and guard only for the other tiers. Their bundle checks report runtime consistency and guard-byte equality.
- `a2.sh:22` matches S11's `provision` argparse (`s11_host_repository.py:769-777`), including the host, full commit, new record directory, and window reference. Both r6 S11 dry records agree on P, provision mode, repository destination, and transfer directory.
- `a2.sh:8` explicitly exits 2 when either directory change or checksum verification fails. Both live code directories passed a read-only `sha256sum -c --quiet SHA256SUMS`; the sums-file hashes also match the request: s3s9s10-r6 `d6c4815b7a9b91bfaadd6312a0f2d7c585e0dbdca8a1e550e507a1a26bf87124`, s5s6s7-r6 `2b4b6f215514103e97542012d4f314438d7969cd1da33503ffd22f20cade2cb6`. `a2.sh:9` explicitly rejects a missing/unreadable/different runtime manifest even though the hash pipeline lacks `pipefail`: no matching digest means exit 2.
- `a2.sh:17` saves the tool status immediately, then exits with that status on nonzero; logging does not overwrite the saved value. Thus later tiers, S11, and `__A2_DONE` are skipped after a tool failure. No retries occur. Its global `rc` assignment is safe here: the hash-name variable is expanded before entering `run()`, and line 18 resets it on every iteration.
- `a2.sh:18` maps hyphens to underscores before indirect expansion, so rd00-a00/a01 resolve the defined variable names for 03/04. The unquoted paths/host/hash expansions contain only fixed whitespace-free values. `"${first[@]}"` and `"${@:2}"` preserve argument boundaries; the arbitrary GO reference remains one quoted metadata argument and is not evaluated as shell code. The tool environment is cleared with `env -i` and gets only the explicit PATH, HOME, and LANG; execution uses nice 19 and Python `-I -B`.

Pinned artifacts:

All 18 SHA-256 values below were independently recomputed from file bytes and matched lines 10-15 and the corresponding r6 dry record. Under `/mpac/sdicks02/k4s-runner/run-r1/end-staging/`, TP is `bundles/end-ref-<host>-<tier>/tiers-pins.json`, RC is the sibling `assembly-receipt.json`, and GM is `guard-jobs/guard-<host>-<tier>/guard-job-manifest.json`.

- 127x03 / pf00: TP `5082e8b21f687c7e92af9e93ed5c1b0c21e9af858ad3ab90955ed49e07fd1b03`; RC `c0874a6f6a33dc17a166e2fde415b3a22947f849f00868ac582f82a73700535a`; GM `a068acdd508b5da79fa5b786784c98215ff5bae7e2bb0b283c0fc7ec18c2ff50`.

- 127x03 / rd00-a00: TP `39e3f2566a2dd528053101f982934898f24821ba58db6d960a92e4a0ca428070`; RC `49b96b98bc65a9f27adfa65c46b51620f27189fa1ac74c5432a4fba30f5ab857`; GM `86e396c05912ea7ba737c01a798dd0fef369469c7d289044dcea3c87519743a9`.

- 127x03 / rd00-a01: TP `03b8f52e08447141cb436fcd683867376ca482bf7689eb1550d7d0380f825fc5`; RC `7e0814a7afb54e264135052aed3c6f3d277aab74cdc70cfed13004b954b1c173`; GM `ec474156bab1564d315d8c61aba84f75ee0dbe3e072d415181383acde9bfab6e`.

- 127x04 / pf00: TP `fd8c9ee5e8fc262f49f17961b62668b2daa156e1c49bfbc26be93754e00faa0f`; RC `9fc01c8053e958e637a34de44fed1123ae53b88aaec6aa5c4ea66fd7a3883729`; GM `8eb50146d98b726d6be75839d5e9dd394cbde7cef254da9f8d9e52aa2c7bacde`.

- 127x04 / rd00-a00: TP `2fb48c3e71ca4dbc6be3300cf557eba94d0f6eab36d994385ef1ac7d92f2fb6e`; RC `ce9d6c2a8ce75132bb1ef4cd0c536731cb1e3bec71d73ce7acda3473806a63d5`; GM `065e1a10fdd15f9a34e05c35449d007aa996d12ebafc7e2f6376bca29dfeb3d9`.

- 127x04 / rd00-a01: TP `d1292b2eff22e2449237187d6bc8d8dc45e623d43f164bd639a920a549d2a458`; RC `f563d2c05e69e066f2c5d64e0ad451d1abe5b3619f55d5df024a7f133c9502ad`; GM `5c391e34b602a20bc7c8ef7a2bc4abd6041d56f06cef1ebbbe4dd3a0a0e663ac`.

RM independently recomputed from `runtime-98566c032d0b/runtime-manifest.json`: `9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43`, matching line 6. P is a Git commit ID, not a file SHA-256: hashing the raw commit object with Git's object header recomputed `98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb`. It matches the runtime manifest's commit, the runner full clone's `refs/remotes/origin/k4s-end-r1`, and both S11 dry records.

Host/write scope:

`a2.sh:7` permits only 127x03/127x04, and every invocation uses that same H. The wrapper supplies no destination override. The tools' declared bases and all six dry plans agree: 03 `/mpac/sdicks02/jobs/clasher/k4s-end-r1`, 04 `/mpac/sdicks02/jobs-k4s/k4s-end-r1`. S11 writes repository/transfer paths within those bases. The intended exception outside each base is the three guard jobs (and staging partials) under its explicitly declared Q4 guard parent: `/mpac/sdicks02/jobs/clasher` on 03, `/mpac/sdicks02/jobs-k4s` on 04, with names `k4s-end-guard-r1-{pf00,rd00-a00,rd00-a01}`. No wrapper argument selects another host or another remote write root; 04 destinations stay outside `/mpac/sdicks02/jobs/`. The interpreter probe path mentioned in the request is a read-only tool operation, not a staging destination.

Approval covers the wrapper, with the request's operator preconditions retained: coordinator GO/window checks, no concurrent staging, and completing 03 before invoking 04. This is a one-host wrapper and does not enforce the cross-host sequence itself. All eight intended local record directories were absent when inspected; each tool also opens its new record before host contact. No repository edits or other file writes were made; the only output is this review.
