"""Materialize pinned native configs without emulator access or registration."""

from __future__ import annotations

import argparse
from pathlib import Path

from clasher.rl.readiness_native_config import materialize_configs
from clasher.rl.readiness_root_bank import RootBank


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-bank", type=Path, required=True)
    parser.add_argument("--template-capture", type=Path, required=True)
    parser.add_argument("--template-plan-sha256", required=True)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--gamedata-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = materialize_configs(
        RootBank.model_validate_json(args.root_bank.read_text()),
        template_capture=args.template_capture,
        expected_template_plan_sha256=args.template_plan_sha256,
        gamedata=args.gamedata,
        expected_gamedata_sha256=args.gamedata_sha256,
        output=args.output,
    )
    print(
        f"{manifest.configured_count} configs; {manifest.failed_count} retained failures; no capture or registration"
    )


if __name__ == "__main__":
    main()
