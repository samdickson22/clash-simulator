"""Use only the approved v5 feature builders, never an old model/checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def create_assets(output):
    from clasher.rl.contract_v5 import ContractV5ObservationBuilder
    from clasher.rl.structured_obs import build_canonical_tile_features
    builder = ContractV5ObservationBuilder()
    descriptors = builder.card_stat_features.astype(np.float32)
    costs = descriptors[:, 0] * 10
    names = list(builder.token_names)
    # CardDataLoader's raw public gamedata owns unlockArena; no learned slicing.
    arenas = []
    for name in names:
        stats = builder.loader.get_card(name)
        raw = getattr(stats, "_raw_entry", {}) if stats is not None else {}
        arenas.append(str(raw.get("unlockArena", "unknown")))
    np.savez(output, descriptors=descriptors, tiles=build_canonical_tile_features(), costs=costs,
             names=np.asarray(names), arenas=np.asarray(arenas))
    metadata = {"token_sha256": builder.pinned_tokens.sha256,
                "asset_sha256": hashlib.sha256(Path(output).read_bytes()).hexdigest(),
                "descriptor_width": descriptors.shape[1]}
    Path(str(output)+".json").write_text(json.dumps(metadata, indent=2)+"\n")
    return metadata


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("output")
    print(json.dumps(create_assets(p.parse_args().output), indent=2))
