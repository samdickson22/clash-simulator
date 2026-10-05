# L1 offline perception

Read RESULTS.md for measured acceptance and remaining gaps. The final public predictions are in inference-final/ and their scores are in evaluation-final/. This folder contains a P16 baseline, not an operational player.

## Boundaries

- Only the existing isolated native reference is used. The launcher disables Wi-Fi/data and verifies IPv4/IPv6 app-UID rejection rules before starting it.
- The collector requires an owned emulator receipt and matching live PID. Use at most two emulators across the machine; this run used one at a time.
- Public JPEGs contain only the arena, isolated clock and bottom player's HUD. Sanitization happens at source resolution before resizing.
- Native owner IDs and absolute tile coordinates are retained. Entity bodies use Archer/IceGolemite/IceSpirits; card HUD and play events use Archers/IceGolem/IceSpirit. The own player is `1`; a StructuredLiveInferenceAdapter consumer must use `actor_id=1` and perform its existing coordinate canonicalization.
- `dataset/labels.jsonl` contains perception targets. Native positions and identity are exact; pixel boxes are approximate class extents around calibrated anchors. Occlusion and exact sprite silhouettes are not certified.
- `dataset/evaluation_only/` contains private truth for scoring and accepted play receipts. Neither training nor pixel inference opens it. Play receipts are not perception events.
- `infer_l1_perception.py` accepts only image paths, episode/frame IDs and media timestamps. It writes PublicVisionFrame predictions before evaluation opens truth.
- The P16 derived-state module is read without modification. Its input is the perceived clock and body-derived play events, plus a predeclared population prior. It never receives the actual opponent deck assignment, hand or elixir.

## Entry points

Run from the workspace root using `.venv/bin/python`. Long commands must be launched through `reports/strategy_council_20260928/pilot/detach.sh LOGFILE COMMAND ...`.

1. Launch a fresh owned instance with `reports/strategy_council_20260928/m0/readiness/start_local_reference.py OUTPUT --read-only --console-port 5580 --probe-port 26789`. Confirm the port is unused first. Keep the launch receipt; stop only that instance when finished.
2. Collect with `scripts/collect_l1_rendered.py --output NEW_DATASET --ownership LAUNCH_OUTPUT/complete.json --matches 7 --ticks 3600 --cadence 40`. The script validates matching serial/port, keeps PNGs in memory, and writes JPEGs. `--seed-base` selects disjoint runs. `--training-only --matches 1 --prioritize-card Tesla` supports a narrow coverage addition.
3. `scripts/audit_l1_dataset.py DATASET` verifies receipts/hashes, public masks and deck/seed separation, and creates the media-only heldout manifest.
4. `scripts/train_l1_perception.py --dataset DATASET --output NEW_MODEL_DIR --epochs 40` fits YOLOv8n on MPS and training-only HUD readers. It refuses unsupported body classes with zero training examples. No pretrained model downloads are used.
5. `scripts/infer_l1_perception.py --inputs DATASET/heldout-inputs.jsonl --image-root DATASET --model MODEL/detector/weights/best.pt --hud MODEL/hud.npz --calibration reports/strategy_council_20260928/live-loop/l1/calibration.json --output NEW_INFERENCE_DIR` freezes pixel predictions and synchronized timing.
6. `scripts/evaluate_l1_perception.py --dataset DATASET --predictions INFERENCE/frames.jsonl --prior reports/strategy_council_20260928/live-loop/l1/public-deck-prior.json --output NEW_EVAL_DIR` runs post-inference association, contract gates and derived-state scoring. A new experimental population requires its own prior, frozen before evaluation.
7. `scripts/benchmark_l1_capture.py --ownership LAUNCH_OUTPUT/complete.json --samples 10` measures PNG and raw adb capture through the trained perception model. It uses a fresh paused offline scene and the model paths from this run.

All output directories for training/inference/evaluation must be fresh. Partial collection resume requires the original owned emulator to remain at the untouched next sampling tick. Resume never replays an action; it records a fresh future policy sub-seed. A completed dataset cannot be resumed.

The convenience `run_l1_pipeline.py` is specific to this run: it waits for the owned collector, adds the independent Tesla support match, audits, trains, infers and evaluates. It is not a general scheduler or a replacement for ownership checks.

## Verification

`python -m pytest -q tests/test_l1_vision.py tests/test_rl_live_inference_contract.py tests/test_rl_perspective_sanitizer.py`

The calibrated transform and its manual annotation uncertainty are in `calibration.json`. Native observe equality across screencap proves the simulation stayed at one tick; it does not provide a compositor fence. Clock readiness checks and visual checks supplement that evidence. Do not call approximate boxes or hidden/overlapping bodies exact pixel annotations.
