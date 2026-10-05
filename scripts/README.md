# Scripts

Run these utilities from the repository root. Most accept `--help`; seed-specific shell drivers may launch long jobs and expect local artifacts, so read them first. The flat layout is retained because tests, imports, configs, and historical report commands refer to these paths.

| Task | Entry points and naming patterns |
| --- | --- |
| CLI | `run_clasher.py`; use `paths`, `gym-smoke`, `train`, `eval`, or `imitation` |
| Data and replay | `acquire_tv_royale_*`, `audit_tv_royale_*`, `build_*`, `collect_*`, `filter_*` |
| Evaluation | `evaluate_*`, `compare_*`, `gate_*`, `validate_*`, `finalize_*` |
| Native reference and parity | `native_*`, `probe_*`, `audit_enabled_mirror.py`; also [engine-rs](../engine-rs/) |
| Training and imitation | `train_*`, `run_*`, `continue_*`, `generate_*`, `distill_*` |
| Vision | `*_l1_*`, `*_youtube_*`, `*_current_client_*` |
| Analysis | `analyze_decks.py`, `attribute_usage_analysis.py`, `analyze_*`, `audit_*`, `report_*` |
| Historical diagnostics | `test_entity_iteration.py`, `archive_*`, and seed-specific experiment drivers |

Find a particular tool with `rg --files scripts | rg 'keyword'`. See [reports](../reports/README.md) for the evidence and commands associated with a study, and [usage](../docs/usage.md) for policy training and evaluation examples. Scripts are not a uniform public API, and filenames alone do not establish that an experiment passed.
