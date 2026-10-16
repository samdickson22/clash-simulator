"""CPU proposal API and portable scripted tensor model."""
from dataclasses import asdict
import json
from pathlib import Path
import torch
from .features import build_row
from .network import ModelConfig, SetPolicy

PROVENANCE = "human-prior research artifact; not a Tier A admitted pilot arm"


def single_features(public_packet, d1, costs):
    # Training buckets group different row lengths. One CPU request needs no
    # padding, and should not pay for a larger bucket at a rare length boundary.
    return {k: torch.from_numpy(v).unsqueeze(0)
            for k, v in build_row(public_packet, d1, costs).items()}


class Policy:
    def __init__(self, model, metadata=None):
        self.model = model.cpu().eval()
        self.metadata = metadata or {}
        self.costs = self.model.costs.detach().numpy()

    @torch.inference_mode()
    def propose(self, public_packet, d1, k=8):
        """List of {action, slot, tile, probability}; excludes wait and ability.

        Probabilities are conditional on gate=play. Search must add no-op itself.
        Returns fewer than k if fewer legal pairs, and [] if no legal play.
        """
        if k < 0:
            raise ValueError("k must be nonnegative")
        b = single_features(public_packet, d1, self.costs)
        count = min(k, int(b["action_mask"][0, :2304].sum()))
        if not count:
            return []
        lp = self.model.log_policy(b)
        joint = (lp["card"][:, :, None] + lp["tile"]).flatten(1)[0]
        values, indices = torch.topk(joint, count)
        return [{"action": int(i), "slot": int(i)//576, "tile": int(i)%576,
                 "probability": float(p)} for i, p in zip(indices.tolist(), values.exp().tolist())]

    @torch.inference_mode()
    def sample(self, public_packet, d1, generator=None):
        b = single_features(public_packet, d1, self.costs)
        lp = self.model.log_policy(b)
        gate = int(torch.multinomial(lp["gate"][0].exp(), 1, generator=generator))
        if gate != 1:
            return 2304 if gate == 0 else 2305
        slot = int(torch.multinomial(lp["card"][0].exp(), 1, generator=generator))
        tile = int(torch.multinomial(lp["tile"][0, slot].exp(), 1, generator=generator))
        return slot*576+tile

    def export(self, path):
        scripted = torch.jit.script(self.model)
        scripted.save(str(path), _extra_files={"metadata.json": json.dumps(self.metadata)})
        # Feature adapter is deliberately plain NumPy, shared by train and serve.
        Path(str(path)+".json").write_text(json.dumps({**self.metadata,
            "tensor_contract": "features.build_row + collate_features; v6-t4-1",
            "provenance": PROVENANCE}, indent=2)+"\n")
        return scripted


def load_policy(path, ema=True):
    if Path(path).suffix == ".ts":
        extra = {"metadata.json": ""}
        model = torch.jit.load(str(path), map_location="cpu", _extra_files=extra)
        metadata = json.loads(extra["metadata.json"]) if extra["metadata.json"] else {}
        return Policy(model, metadata)
    payload = torch.load(path, map_location="cpu", weights_only=True)
    c = ModelConfig(**payload["config"])
    state = payload["ema"] if ema else payload["model"]
    model = SetPolicy(c, state["descriptors"], state["tile_features"], state["costs"])
    model.load_state_dict(state)
    return Policy(model, {"config": asdict(c), "hashes": payload.get("hashes", {}),
                          "provenance": PROVENANCE})
