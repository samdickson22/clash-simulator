Offloaded to f35 (2026-10-07, disk full): artifacts/worktree-data (archival pre-consolidation worktree evidence) and live-loop/l1/v3 (perception frames). Verified identical copies at f35:/data2/sdicks02/repos/clasher/ (rsync dry-run + checksums 2026-10-05). File manifest: reports/strategy_council_20260928/pilot/logs/offloaded-to-f35-manifest-20261007.tsv

## 2026-10-08: bulk data offloaded to the 127x fleet (supersedes f35 for these paths)

81,517 untracked files (35.8 GB) were deleted from the Mac after a checksum match against two fleet copies:
`127x01:/mpac/sdicks02/repos/clasher` and `127x04:/mpac/sdicks02/repos/clasher`.

Paths covered:
- `m0/readiness`
- `checkpoints/`
- `datasets/` (untracked parts)
- `c56/data`
- `human-prior-p16`
- `reports/persistent_batch_v1`
- pilot `v7r1`, `v7r2` and `v7r2c` launches

The full list is in `reports/strategy_council_20260928/pilot/logs/offload-mac-bulk-20261008T015508Z.files`, and the script is `pilot/offload_mac_bulk.sh`. Both fleet copies are now the only copies of these files.
