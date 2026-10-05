# Cleanup 2026-09-29 (approved by Sam)

- Deleted 165 raw YouTube .webm files (24.17 GiB) from datasets/external/tv_royale_youtube_clocked_rotate_20260826 and datasets/external/tv_royale_youtube_persistent_batch_v1_20260825. Per-video manifests and small metadata kept; full file list with sizes in youtube-raw-deleted-files.txt. Re-download via the manifests is possible but not guaranteed. Derived datasets untouched.
- Deleted legacy AVDs ~/.android/avd/{clasher_current,clasher_current_oracle,clasher_play_oracle} (16.3 GiB; last written Aug 5-6). Inventory of their ini/config in legacy-avds-inventory.txt. The pinned native reference AVD (~/.cache/clasher-native-reference/avd/clasher_reference_api35) and medium_phone were not touched.
- Free space: 12 GiB -> 53 GiB.
