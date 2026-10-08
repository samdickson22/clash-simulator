# T6/T7 retained technical attempts

- Initial remote launch used a relative path from the SSH home directory and did
  not start. Corrected by changing to the checkout before fleet_run.sh.
- GPU env lacked PyAV and pytest. Installed PyAV 16.0.1, pytest 8.4.2 and its
  ordinary dependencies into the existing GPU env; no Torch/NumPy changes.
  `t7-tests-20261008-1` exited 1 (pytest absent); subsequent tests passed.
- `t6-shake-20261008-1` exited 1 during HUD/cache preparation at the inherited
  450MiB JPEG-cache guard, before any optimizer step or validation scoring.
  Preserve `/mpac/sdicks02/repos/clasher-v4-training/t6-run-1/`. Re-run identical
  population and training seed as `t6-shake-20261008-2` / `t6-run-2`, explicit
  4096MiB disk guard; default remains 450MiB. Amendment 02 records this purely
  operational change. No samples or training behavior changed.
- Initial T7 smoke (`t7-shake-1`, 32 steps) exposed contradictory body metadata
  and projectile names in the label vocabulary. Keep that diagnostic checkpoint,
  but use `t7-shake-2` (64 steps, new vocabulary, train-only quarantine) as the
  current engineering receipt. Do not resume the first checkpoint under changed
  label semantics. Amendment 01 predates heldout scoring.
- T6 second attempt completed fitting, then the trusted v1 YOLO checkpoint could
  not deserialize because dill was absent. Installed dill 0.4.0; preserved the
  empty partial stage as validation-inference-missing-dill and resumed completed
  stages under `t6-shake-20261008-3`. No weights/data/training settings changed.
- T6 third attempt decoded one frame before the unchanged public-frame validator
  rejected fractional timestamp_ms from the converter. The input adapter now
  truncates to integer milliseconds exactly as the historical v3 sample_inputs
  function does. Raw input timestamps and the failed stage are retained as
  validation-inputs-producer-ms.jsonl and validation-inference-fractional-ms.
  Fourth attempt resumes the same completed fit. This changes no detector logic.
