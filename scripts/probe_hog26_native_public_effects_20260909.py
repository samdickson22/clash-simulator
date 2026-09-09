"""Trace a known visible native projectile through the public sidecar prototype."""

import argparse
import hashlib
import json
from dataclasses import fields
from pathlib import Path

import torch

from clasher.torch_sim.simple_effects import FastEffectState, step_fast_effects
from clasher.torch_sim.simple_state import FastGymState
from scripts.hog26_public_effect_probe import project_visible_effects


def digest(*objects):
    result = hashlib.sha256()
    for obj in objects:
        for field in fields(obj):
            value = getattr(obj, field.name)
            if isinstance(value, torch.Tensor):
                result.update(field.name.encode())
                result.update(value.detach().cpu().contiguous().numpy().tobytes())
    return result.hexdigest()


def fixture(device):
    state = FastGymState.empty(1, max_entities=2, device=device)
    state.active[0, 0] = True
    state.stable_id[0, 0] = 8
    state.owner[0, 0] = 1
    state.x_units[0, 0] = 1000
    state.hp[0, 0] = state.max_hp[0, 0] = 100
    effect = FastEffectState.empty(1, max_effects=1, device=device)
    effect.active[0, 0] = True
    effect.source_owner[0, 0] = 0
    effect.target_id[0, 0] = 8
    effect.speed_units_per_tick[0, 0] = 400
    effect.damage[0, 0] = 10
    effect.radius_units[0, 0] = 1
    effect.lifetime_ticks[0, 0] = 5
    status = torch.zeros_like(state.owner, dtype=torch.int8)
    status_ticks = torch.zeros_like(state.owner, dtype=torch.int32)
    return state, effect, status, status_ticks


def known_projectile_frame(effect):
    # This fixture declares one visible flying projectile, not arbitrary effects.
    # A general adapter still needs an independently audited appearance registry.
    return project_visible_effects(
        torch.stack((effect.x_units, effect.y_units), dim=-1),
        effect.source_owner, torch.ones_like(effect.source_owner),
        effect.active[:, None].expand(-1, 2, -1),
    )


def run(device):
    state, effect, status, status_ticks = fixture(device)
    control, control_effect, control_status, control_status_ticks = fixture(device)
    frames = []
    for tick in range(4):
        before = digest(state, effect)
        features, mask = known_projectile_frame(effect)
        assert digest(state, effect) == before
        assert digest(state, effect) == digest(control, control_effect)
        frames.append({"tick": tick, "features": features.cpu().tolist(),
                       "mask": mask.cpu().tolist()})
        if tick < 3:
            step_fast_effects(state, effect, status, status_ticks)
            step_fast_effects(control, control_effect, control_status, control_status_ticks)
            torch.testing.assert_close(status, control_status, rtol=0, atol=0)
            torch.testing.assert_close(status_ticks, control_status_ticks, rtol=0, atol=0)
    assert state.hp[0, 0] == 90
    assert not effect.active.any()
    assert [frame["mask"][0][0][0] for frame in frames] == [True, True, True, False]
    expected_x = torch.tensor([0, 400 / 18000, 800 / 18000])
    actual_x = torch.tensor([frame["features"][0][0][0][0] for frame in frames[:3]])
    torch.testing.assert_close(actual_x, expected_x, rtol=0, atol=1e-7)

    _, private, _, _ = fixture(device)
    expected, expected_mask = known_projectile_frame(private)
    allowed = {"active", "source_owner", "x_units", "y_units", "device"}
    perturbed = []
    for field in fields(private):
        value = getattr(private, field.name)
        if field.name in allowed or not isinstance(value, torch.Tensor):
            continue
        if value.dtype == torch.bool:
            value.logical_not_()
        else:
            value.add_(7)
        perturbed.append(field.name)
    actual, actual_mask = known_projectile_frame(private)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert torch.equal(actual_mask, expected_mask)
    return {"device": device, "frames": frames,
            "projection_is_read_only": True, "native_control_trace_identical": True,
            "private_fields_perturbed_without_changing_projection": perturbed,
            "post_impact_hp_for_physics_audit_only": float(state.hp[0, 0].cpu())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite a probe report")
    devices = ["cpu"] + (["mps:0"] if torch.backends.mps.is_available() else [])
    results = [run(device) for device in devices]
    if len(results) == 2:
        assert results[0]["frames"] == results[1]["frames"]
    report = {"status": "bounded fixture passed; not production event coverage",
              "scope": "One explicitly visible native projectile fixture. No complete-game enrichment, appearance registry, real-camera acceptance or model acceptance is established.",
              "policy_inputs_changed": False, "results": results,
              "cpu_mps_frames_identical": len(results) == 2,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "projection_sha256": hashlib.sha256(Path('scripts/hog26_public_effect_probe.py').read_bytes()).hexdigest()}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "devices": devices,
                      "cpu_mps_frames_identical": report["cpu_mps_frames_identical"]}))


if __name__ == "__main__":
    main()
