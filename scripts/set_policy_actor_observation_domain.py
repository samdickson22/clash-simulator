from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import torch


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy a V2 checkpoint with only its actor observation domain changed"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--domain",
        choices=("simulator-exact", "causal-vision-v1", "causal-frame-v1"),
        required=True,
    )
    args = parser.parse_args()
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    payload = torch.load(source, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("input is not a V2 checkpoint")
    config = dict(payload["model_config"])
    previous_domain = str(config.get("actor_observation_domain", "simulator-exact"))
    config["actor_observation_domain"] = args.domain
    if args.domain.startswith("causal-") and not bool(
        config.get("public_observation_confidence", False)
    ):
        raise ValueError("causal actor domains require confidence-aware inputs")
    payload["model_config"] = config
    payload["actor_domain_conversion"] = {
        "source": str(source),
        "source_sha256": _sha256(source),
        "previous_domain": previous_domain,
        "domain": args.domain,
        "weights_unchanged": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output)
    print(f"output={output}")
    print(f"sha256={_sha256(output)}")


if __name__ == "__main__":
    main()
