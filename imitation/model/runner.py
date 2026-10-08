"""Streaming dev inference, calibration reservoir, persisted metric rows."""
from contextlib import nullcontext
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader
from .evaluate import metric_rows, fit_temperature, report_slices, offline_gates, frequency_output
from .inference import load_policy
from .store import PackedStore, collate


def transfer(b, device):
    return {k: v.to(device, non_blocking=True) for k, v in b.items()}


@torch.inference_mode()
def dev_joint_nll(model, ema, store, device, batch_size):
    saved = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(ema); model.eval()
    total, count = 0., 0
    try:
        for b, y in DataLoader(store, batch_size=batch_size, collate_fn=collate):
            b, y = transfer(b, device), transfer(y, device)
            with torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext():
                o = model(b, torch.empty(0, dtype=torch.long, device=device))
            rows = metric_rows(o, y, b["ids"][:, :4])
            values = rows["joint_nll"]
            total += np.nansum(values, dtype=np.float64); count += np.isfinite(values).sum()
    finally:
        model.load_state_dict(saved)
    if not count:
        raise ValueError("dev has no supervised rows")
    return float(total/count)


def calibration_data(model, store, device, batch_size, cap=100000, seed=1):
    """Deterministic uniform row subset from dev, independent of labels/confidence."""
    from torch.utils.data import Subset
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(len(store), min(cap, len(store)), replace=False))
    bins = {head: [[], [], []] for head in ("gate", "card", "tile")}
    model.eval()
    with torch.inference_mode():
        for b, y in DataLoader(Subset(store, indices.tolist()), batch_size=batch_size, collate_fn=collate):
            b, y = transfer(b, device), transfer(y, device)
            a = y["action"].long(); slot = (a//576).clamp(0, 3)
            with torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext():
                o = model(b, slot)
            valid = y["supervised"].bool(); play = valid & (a < 2304)
            gate = torch.where(a == 2304, 0, torch.where(a == 2305, 2, 1))
            for head, logits, mask, target, use in (
                ("gate", o["gate"], o["gate_mask"], gate, valid & o["card_mask"].any(-1)),
                ("card", o["card"], o["card_mask"], slot, play),
                ("tile", o["tile"][:, 0], o["tile_mask"][:, 0], a%576, play)):
                for dst, value in zip(bins[head], (logits, mask, target)):
                    dst.append(value[use].cpu())
    return {head: [torch.cat(values) for values in parts] for head, parts in bins.items()}


def _slices(store, rows, role_file=None):
    a = store.arrays; n = len(store)
    result = {"card": rows["label_card"]}
    arenas = store.assets["arenas"]
    result["arena"] = np.array([arenas[c] if c >= 0 else "" for c in rows["label_card"]])
    if "submitted_ticks" in a:
        ticks = a["submitted_ticks"]
        result["phase"] = np.where(ticks < 2400, "single", np.where(ticks < 3600, "double", "overtime"))
    for name in ("match_part", "archetype", "mode", "p16", "engine_phase", "forms", "ability_attributable"):
        if name in a:
            result[name] = np.asarray(a[name])
        elif store.metadata:
            values = [store.metadata.get(str(int(pid)), {}).get(name) for pid in a["perspective_ids"]]
            if all(v is not None for v in values):
                result[name] = np.asarray(values)
    if store.t3:
        roles = json.loads(Path(role_file).read_text()) if role_file else None
        if role_file:
            from .store import sha256
            if sha256(role_file) != store.hashes["roles"]:
                raise ValueError("archetype role file hash differs from T3")
        for key in ("match_part", "mode", "engine_phase", "forms", "ability_attributable", "archetype"):
            result[key] = np.full(n, "", dtype="U128")
        names = store.assets["names"].tolist()
        for item in store.perspectives:
            summary = item["summary"]; start = item["target_start"]; end = start+item["rows"]
            result["mode"][start:end] = summary["info"].get("battle_type", "other")
            result["ability_attributable"][start:end] = str(bool(summary["ability_attributable"]))
            fraction = a["submitted_ticks"][start:end] / max(1, summary["playable_end_tick"])
            result["match_part"][start:end] = np.where(fraction<.33,"early",np.where(fraction<.66,"mid","late"))
            if roles:
                result["archetype"][start:end] = roles["family"][item["identity"]]
            form_map = dict(zip(summary["own_deck"], summary["own_forms"]))
            result["forms"][start:end] = [form_map.get(names[c], "base") if c>=0 else "" for c in rows["label_card"][start:end]]
        # Unit phase is provenance from the plan, never inferred from opponent identities.
        plan = json.loads((store.root.parent/"plan.json").read_text())
        units = np.array([unit["key"].split("/")[0] for unit in plan["units"]])
        result["engine_phase"] = units[a["source_unit"]]
        if not roles:
            del result["archetype"]
        else:
            labels, counts = np.unique(result["archetype"], return_counts=True)
            # Report top ten by perspective count, not by retained duration.
            families = [roles["family"][p["identity"]] for p in store.perspectives]
            labels, counts = np.unique(families, return_counts=True)
            top = set(labels[np.argsort(-counts, kind="stable")[:10]])
            result["archetype"] = np.where(np.isin(result["archetype"],list(top)),result["archetype"],"other")
    result["ood"] = np.full(n, False)
    return result


def read_baseline(directory, row_ids):
    root = Path(directory)
    if not np.array_equal(np.load(root/"row_ids.npy", allow_pickle=False), row_ids):
        raise ValueError("baseline row identity/order differs")
    result = {}
    for key in ("joint_nll", "play_wait_nll", "card_nll", "tile_nll"):
        path = root/f"{key}.npy"
        result[key] = np.load(path, mmap_mode="r", allow_pickle=False)
    return result


def evaluate_checkpoint(args):
    torch.set_num_threads(1)
    store = PackedStore(args.store, "dev", getattr(args, "assets", None))
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise ValueError("evaluation output must be fresh")
    out.mkdir(parents=True, exist_ok=True)
    policy = load_policy(args.checkpoint)
    device = torch.device(args.device); model = policy.model.to(device).eval()
    temps = model.temperatures.detach().cpu().tolist()
    if args.calibrate:
        data = calibration_data(model, store, device, args.batch_size, args.calibration_rows)
        temps = [fit_temperature(*data[key]) for key in ("gate", "card", "tile")]
    (out/"temperatures.json").write_text(json.dumps({"role": "dev", "temperatures": temps,
                                                   "fit_row_cap": args.calibration_rows if args.calibrate else None}, indent=2)+"\n")
    # Metric arrays are appendable mmap files; no giant logits or hidden data.
    arrays = {"before": {}, "after": {}}; offset = 0
    counts = None
    if getattr(args, "frequency_counts", None):
        with np.load(args.frequency_counts, allow_pickle=False) as z:
            counts = {k: z[k] for k in ("gate", "cards", "tiles")}
        arrays["frequency"] = {}
    with torch.inference_mode():
        for b, y in DataLoader(store, batch_size=args.batch_size, collate_fn=collate):
            b, y = transfer(b, device), transfer(y, device)
            with torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext():
                o = model(b, torch.empty(0, dtype=torch.long, device=device))
            for stage, temperatures in (("before", (1., 1., 1.)), ("after", temps)):
                batch = metric_rows(o, y, b["ids"][:, :4], temperatures)
                for key, values in batch.items():
                    if key not in arrays[stage]:
                        arrays[stage][key] = np.lib.format.open_memmap(out/f"{stage}-{key}.npy", mode="w+", dtype=values.dtype, shape=(len(store),))
                    arrays[stage][key][offset:offset+len(values)] = values
            if counts is not None:
                ix = y["index"].cpu().numpy()
                ticks = torch.as_tensor(np.array(store.arrays["submitted_ticks"][ix]), device=device)
                elixir = torch.as_tensor(np.array(store.arrays["global_features"][ix,5]),device=device)
                base = frequency_output(b["action_mask"], b["ids"][:,:4], ticks, elixir, counts)
                baseline = metric_rows(base, y, b["ids"][:,:4])
                for key in ("joint_nll", "play_wait_nll", "card_nll", "tile_nll"):
                    if key not in arrays["frequency"]:
                        arrays["frequency"][key] = np.lib.format.open_memmap(out/f"frequency-{key}.npy",mode="w+",dtype=np.float32,shape=(len(store),))
                    arrays["frequency"][key][offset:offset+len(ix)] = baseline[key]
            offset += len(y["action"])
    for values in arrays.values():
        for array in values.values():
            array.flush()
    np.save(out/"row_ids.npy", store.column("row_ids")); np.save(out/"perspective_ids.npy", store.column("perspective_ids"))
    clusters = store.column("perspective_ids")
    report = {"role": "dev", "natural_row_weights": True, "bootstrap_resamples": args.bootstrap,
              "checkpoint": str(args.checkpoint), "hashes": policy.metadata["hashes"], "temperatures": temps,
              "when_primary": "playable supervised rows per DESIGN; *_all preserves frozen JSON all-row definition"}
    report["card_names"] = {str(int(i)): str(store.assets["names"][int(i)])
                            for i in np.unique(arrays["after"]["label_card"]) if i >= 0}
    slices = _slices(store, arrays["after"], getattr(args, "roles", None))
    report["missing_slices"] = sorted(set(("phase", "match_part", "archetype", "mode", "p16", "engine_phase", "forms", "ability_attributable"))-set(slices))
    for stage in ("before", "after"):
        report[stage] = report_slices(arrays[stage], clusters, slices, args.bootstrap)
    if getattr(args, "frequency_rows", None) or counts is not None:
        if not getattr(args, "card_scope", None):
            raise ValueError("A3 requires the preregistered card scope, not just observed cards")
        frequency = arrays["frequency"] if counts is not None else read_baseline(args.frequency_rows, store.column("row_ids"))
        p16 = read_baseline(args.p16_rows, store.column("row_ids")) if getattr(args, "p16_rows", None) else None
        scope = json.loads(Path(args.card_scope).read_text())
        report["dev_gate_diagnostics"] = offline_gates(arrays["after"], frequency, clusters, scope,
                                                     slices.get("p16", np.zeros(len(store),bool)), p16, args.bootstrap)
        if getattr(args, "p16_summary", None):
            p16_report = json.loads(Path(args.p16_summary).read_text())
            if p16_report["role"] != "dev":
                raise ValueError("T4 only consumes dev baseline scores")
            keep = np.asarray(slices["p16"],bool)
            expected = int(np.isfinite(arrays["after"]["tile_nll"][keep]).sum())
            if p16_report["metrics"]["play_rows"] != expected:
                raise ValueError("P16 baseline supervised play count mismatch")
            details = {}
            for key in ("card_nll", "tile_nll"):
                delta = float(np.nanmean(arrays["after"][key][keep]))-p16_report["metrics"][key]
                details[key] = {"delta": delta, "within_0.05": delta <= .05}
            report["dev_gate_diagnostics"]["A2"] = {"pass": all(d["within_0.05"] for d in details.values()), "p16": details,
                                                      "baseline_checkpoint_sha256": p16_report["checkpoint_sha256"]}
    (out/"report.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    # Export temperatures as a new artifact, leaving the training checkpoint immutable.
    policy.model = model.cpu(); policy.model.temperatures.copy_(torch.tensor(temps))
    policy.export(out/"policy.ts")
    print(json.dumps({"output": str(out), "rows": offset, "temperatures": temps,
                      "joint_nll": report["after"]["overall"]["metrics"]["joint_nll"]}, indent=2))
