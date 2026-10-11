# Amendment 4 no-copy staging helper on the Mac (non-counted, synthetic data only)

- **Run** on 2026-10-11 between 23:17:13Z and 23:18:52Z, on the Mac mini with Python 3.12.13 (existing venv, read-only), at nice 10.
- **Helper:** `reports/explore/mac-registration/stage_nocopy.py` 96abd847, copied to
  `$S/helpers/mac-registration/`, outside e4v3 and the runtime root. Its test is `tests/test_stage_nocopy.py`
  f75cd3a3. `CLASHER_E4V3` pointed at `$S/runtime-a3/.../e4v3`, i.e. runtime 76887b33.
- **Guard:** `measurement_files(runtime-a3 e4v3)` equals END-A3's 18 entries, so it is True.
- **`tests.test_stage_nocopy`:** 9 run, 7 ok, 1 skipped (the Linux-only clonefile check), 1 failure.
  - The failure is `FrozenPrepareBundle.test_manifest_byte_identical_and_fixture_not_copied` at line 174, an inode
    equality assertion. That line assumes a **hard link** (the Linux path). On APFS the helper correctly uses
    `clonefile(2)`, which by design creates its own inode, so the assertion is Linux-specific.
  - The byte-identity assertions just before it, at lines 169–171 (`tiers-pins.json`, `tiers-pins.sha256`, file set),
    **passed**.
  - This is a test-portability issue for the builder's test, not a helper defect.
- **Ad-hoc Darwin check (`darwin_check.py`, same fixture):**
  - `tiers_pins_identical` and `sidecar_identical` are both true;
  - all three fixture files use method `apfs-clone` and are read-only at 0o444;
  - `verify_bundle` passes;
  - after the bundle's `states-rows.json` is made writable again, it fails closed (PermissionError).
- Nothing was staged and no timing was run. Temporary directories only.
