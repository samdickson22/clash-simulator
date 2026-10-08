"""One fixed T4 shakedown, intended for the detached fleet launcher on 127x04.

No heldout role, full training recipe, process termination, or data mutation.
Every stage writes an owned receipt; failures leave artifacts for inspection.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True)
    p.add_argument("--qualification", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output)
    out.mkdir(exist_ok=False, parents=True)

    def record(stage, **fields):
        payload = {"stage": stage, "at": datetime.now(timezone.utc).isoformat(), **fields}
        (out/"status.json").write_text(json.dumps(payload, indent=2)+"\n")
        print(json.dumps(payload), flush=True)

    stage = "preflight"
    try:
        record(stage)
        import numpy as np
        import torch
        from .assets import create_assets
        from .store import PackedStore, sha256
        torch.set_num_threads(1)
        assets = out/"assets.npz"
        asset_info = create_assets(assets)
        qualification = json.loads(Path(args.qualification).read_text())
        checked = {}
        for role in ("train", "dev"):
            store = PackedStore(Path(args.store)/role, role, assets)
            store.verify_qualification(qualification)
            counts = store.column("entity_counts")
            indices = np.unique(np.append(np.linspace(0, len(store)-1, 256, dtype=np.int64), counts.argmax()))
            maximum_tokens = 0
            for index in indices:
                row, target = store[int(index)]
                assert np.isfinite(row["numeric"]).all()
                maximum_tokens = max(maximum_tokens, len(row["ids"])+1)
            checked[role] = {"rows": len(store), "perspectives": len(store.perspectives),
                             "maximum_entities": int(counts.max()), "rows_above_64_entities": int((counts>64).sum()),
                             "sampled_rows": len(indices), "maximum_sample_tokens": maximum_tokens,
                             "hashes": store.hashes}
            del store
        receipt = {"passed": True, "assets": asset_info, "roles": checked,
                   "qualification_sha256": sha256(args.qualification),
                   "torch": torch.__version__, "gpu": torch.cuda.get_device_name(),
                   "bf16": torch.cuda.is_bf16_supported()}
        (out/"preflight.json").write_text(json.dumps(receipt, indent=2)+"\n")
        common = ["--store", str(Path(args.store)/"train"), "--dev", str(Path(args.store)/"dev"),
                  "--assets", str(assets), "--qualification", args.qualification, "--seed", "2903",
                  "--device", "cuda", "--workers", "2", "--tile-width", "64"]
        commands = [
            ("subset", ["imitation.model.train", *common, "--output", str(out/"subset"),
                        "--epochs", "1", "--subset-fraction", ".02", "--epoch-fraction", ".2"]),
            ("overfit", ["imitation.model.train", *common, "--output", str(out/"overfit"),
                         "--batch-size", "1000", "--overfit-rows", "1000", "--max-steps", "200"]),
        ]
        for stage, command in commands:
            start = time.monotonic()
            record(stage, command=command)
            subprocess.run([sys.executable, "-B", "-m", *command], check=True)
            (out/(stage+"-stage.json")).write_text(json.dumps({"passed": True, "wall_seconds": time.monotonic()-start})+"\n")
        index = json.loads((out/"subset/checkpoints.json").read_text())
        checkpoint = out/"subset"/index["best_files"][-1]
        stage = "dev-evaluation"
        command = [sys.executable, "-B", "-m", "imitation.model.evaluate", "--store", str(Path(args.store)/"dev"),
                   "--assets", str(assets), "--roles", args.roles, "--checkpoint", str(checkpoint),
                   "--output", str(out/"dev-evaluation"), "--device", "cuda", "--calibrate"]
        record(stage, command=command)
        subprocess.run(command, check=True)
        record("complete", passed=True, checkpoint=str(checkpoint))
    except Exception as exc:
        record("failed", failed_stage=stage, error=repr(exc))
        raise


if __name__ == "__main__":
    main()
