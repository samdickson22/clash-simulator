"""Plain eager PyTorch trainer. CUDA bf16; exact microbatch normalization.

No eval/eval_ood path, automatic full-run launch, compile, or remote process control.
"""
import argparse
from contextlib import nullcontext
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import random
import signal
import time
import numpy as np
import torch
from torch.utils.data import DataLoader, Subset
from .inference import PROVENANCE
from .features import BUCKETS
from .losses import loss_parts, total_loss
from .network import ModelConfig, SetPolicy
from .store import PackedStore, collate, epoch_indices, sha256


def denominators(b, y):
    valid = y["supervised"].bool(); play = valid & (y["action"] < 2304)
    intent = valid & y["intent_valid"].bool()
    masks = {"gate": valid & b["action_mask"][:, :2304].any(-1), "card": play, "tile": play,
             "intent_card": intent & y["intent_observed"].bool() & (y["intent_card"] >= 0), "hazard": intent}
    return {key+"_weight": (y["weight"].float()*mask).sum() for key, mask in masks.items()}


def lr_factor(step, total, warmup=2000):
    if step < warmup:
        return (step+1)/max(1, warmup)
    fraction = min(1., (step-warmup)/max(1, total-warmup))
    return .5*(1+math.cos(math.pi*fraction))


def move(batch, device):
    return {k: v.to(device, non_blocking=True) for k, v in batch.items()}


def optimizer_step(model, optimizer, b, y, microbatch, device):
    den = move(denominators(b, y), device)
    optimizer.zero_grad(set_to_none=True)
    totals = {name: 0. for name in ("loss", "gate", "card", "tile", "intent_card", "hazard")}
    for begin in range(0, len(y["action"]), microbatch):
        bb = {k: v[begin:begin+microbatch] for k, v in b.items()}
        length = int(bb["valid"].sum(-1).max())+1
        width = next(bucket for bucket in BUCKETS if bucket >= length)-1
        for key in ("ids", "types", "numeric", "valid"):
            bb[key] = bb[key][:, :width]
        bb = move(bb, device)
        yy = move({k: v[begin:begin+microbatch] for k, v in y.items()}, device)
        teacher = (yy["action"].long()//576).clamp(0, 3)
        with torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext():
            output = model(bb, teacher)
            parts = loss_parts(output, yy)
            terms = total_loss(parts, den)
        if not torch.isfinite(terms["loss"]):
            raise RuntimeError("nonfinite loss; checkpoint remains untouched")
        terms["loss"].backward()
        for key in totals:
            totals[key] += float(terms[key].detach())
    grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    optimizer.step()
    totals["grad_norm"] = float(grad)
    return totals


def update_ema(ema, model):
    with torch.no_grad():
        for key, value in model.state_dict().items():
            if value.is_floating_point() and key not in ("temperatures", "costs", "descriptors", "tile_features", "frequencies"):
                ema[key].lerp_(value, .001)
            else:
                ema[key].copy_(value)


def save_checkpoint(path, model, ema, optimizer, scheduler, config, state, hashes, args):
    payload = {"model": model.state_dict(), "ema": ema, "optimizer": optimizer.state_dict(),
               "scheduler": scheduler.state_dict(), "config": asdict(config), "state": state,
               "hashes": hashes, "provenance": PROVENANCE, "args": vars(args),
               "torch_rng": torch.get_rng_state(), "python_rng": random.getstate(),
               "numpy_rng": {"name": np.random.get_state()[0], "keys": np.random.get_state()[1].tolist(),
                             "pos": np.random.get_state()[2], "has_gauss": np.random.get_state()[3],
                             "cached": np.random.get_state()[4]},
               "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}
    temporary = path.with_suffix(path.suffix+".partial")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True); p.add_argument("--dev", required=True)
    p.add_argument("--output", required=True); p.add_argument("--resume")
    p.add_argument("--assets", help="v5 static NPZ built against T3's frozen runtime")
    p.add_argument("--qualification", help="actual T3-PASS.json receipt; required for real fitting")
    p.add_argument("--device", default="cuda"); p.add_argument("--seed", type=int, default=2903)
    p.add_argument("--epochs", type=int, default=12); p.add_argument("--batch-size", type=int, default=8192)
    p.add_argument("--microbatch", type=int, default=64); p.add_argument("--workers", type=int, default=2)
    p.add_argument("--tile-width", type=int, default=64); p.add_argument("--warmup", type=int, default=2000)
    p.add_argument("--max-steps", type=int); p.add_argument("--subset-fraction", type=float, default=1.)
    p.add_argument("--epoch-fraction", type=float, default=1.); p.add_argument("--overfit-rows", type=int, default=0)
    p.add_argument("--patience", type=int, default=3); p.add_argument("--checkpoint-every", type=int, default=1000)
    p.add_argument("--synthetic-smoke", action="store_true")
    args = p.parse_args()
    if args.workers > 8 or args.workers < 0:
        p.error("T4 trainer allows 0..8 loader workers; host process budget is checked at launch")
    if not 0 < args.subset_fraction <= 1 or not 0 < args.epoch_fraction <= 1:
        p.error("subset/epoch fractions must be in (0,1]")
    out = Path(args.output)
    if out.exists() and any(out.iterdir()) and not args.resume:
        raise ValueError("nonempty output directory: use --resume or a fresh path")
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    torch.manual_seed(args.seed); np.random.seed(args.seed); random.seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and (not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()):
        raise RuntimeError("CUDA bf16 required")
    train, dev = PackedStore(args.store, "train", args.assets), PackedStore(args.dev, "dev", args.assets)
    if train.hashes["assets"] != dev.hashes["assets"]:
        raise ValueError("train/dev public assets differ")
    hashes = dict(train.hashes)
    if args.synthetic_smoke and not (train.manifest.get("synthetic") and dev.manifest.get("synthetic")):
        raise ValueError("--synthetic-smoke cannot bypass qualification for real stores")
    if not args.synthetic_smoke:
        if not args.qualification:
            raise ValueError("real fitting requires the actual passed T3 qualification receipt")
        qualification = json.loads(Path(args.qualification).read_text())
        train.verify_qualification(qualification)
        dev.verify_qualification(qualification)
        hashes["T3_qualification"] = sha256(args.qualification)
        for key in ("tokens", "roles", "eval_spec", "sidecar_manifest"):
            if key not in hashes or len(hashes[key]) != 64:
                raise ValueError(f"T3 must supply qualified full contract hash: {key}")
    config = ModelConfig(descriptors=train.assets["descriptors"].shape[1], tile_width=args.tile_width)
    model = SetPolicy(config, torch.tensor(train.assets["descriptors"]), torch.tensor(train.assets["tiles"]),
                      torch.tensor(train.assets["costs"])).to(device)
    ema = {k: v.detach().clone() for k, v in model.state_dict().items()}
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=.05)
    initial_ix = epoch_indices(train, 0, args.seed, args.subset_fraction)
    if not len(initial_ix):
        raise ValueError("selected training subset has no supervised rows")
    steps_epoch = math.ceil(len(initial_ix)*args.epoch_fraction/args.batch_size)
    total_steps = args.max_steps or args.epochs*steps_epoch
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step: lr_factor(step, total_steps, args.warmup))
    state = {"epoch": 0, "cursor": 0, "step": 0, "best_dev": float("inf"), "bad_epochs": 0, "rows": 0}
    if args.resume:
        ckpt = torch.load(args.resume, map_location=device, weights_only=True)
        if ckpt["hashes"] != hashes or ckpt["config"] != asdict(config):
            raise ValueError("resume contract/config mismatch")
        for key in ("seed", "batch_size", "subset_fraction", "epoch_fraction", "overfit_rows", "warmup", "epochs", "max_steps"):
            if ckpt["args"][key] != vars(args)[key]:
                raise ValueError(f"resume recipe mismatch: {key}")
        model.load_state_dict(ckpt["model"]); ema = ckpt["ema"]
        optimizer.load_state_dict(ckpt["optimizer"]); scheduler.load_state_dict(ckpt["scheduler"])
        state = ckpt["state"]
        torch.set_rng_state(ckpt["torch_rng"].cpu()); random.setstate(ckpt["python_rng"])
        nr = ckpt["numpy_rng"]; np.random.set_state((nr["name"], np.array(nr["keys"], np.uint32), nr["pos"], nr["has_gauss"], nr["cached"]))
        if device.type == "cuda":
            torch.cuda.set_rng_state_all([s.cpu() for s in ckpt["cuda_rng"]])
    stopped = [False]
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.__setitem__(0, True))
    log = open(out/"train.jsonl", "a", buffering=1)
    log.write(json.dumps({"event": "start", "parameters": sum(p.numel() for p in model.parameters()),
                          "args": vars(args), "hashes": hashes, "provenance": PROVENANCE})+"\n")
    start = time.monotonic(); measured_rows = 0
    if args.max_steps and state["step"] >= args.max_steps:
        log.close()
        return
    for epoch in range(state["epoch"], args.epochs):
        indices = epoch_indices(train, epoch, args.seed, args.subset_fraction)
        indices = indices[:math.ceil(len(indices)*args.epoch_fraction)]
        if args.overfit_rows:
            fixed = initial_ix[:args.overfit_rows]
            indices = np.tile(fixed, math.ceil(len(indices)/len(fixed)))[:len(indices)]
        cursor = state["cursor"] if epoch == state["epoch"] else 0
        # Locally sort each effective batch by token-count proxy; preserves iid batch membership.
        counts = np.diff(train.column("entity_offsets"))
        for begin in range(0, len(indices), args.batch_size):
            part = indices[begin:begin+args.batch_size]
            indices[begin:begin+len(part)] = part[np.argsort(counts[part], kind="stable")]
        loader = DataLoader(Subset(train, indices[cursor:].tolist()), batch_size=args.batch_size,
                            num_workers=args.workers, collate_fn=collate, pin_memory=device.type == "cuda",
                            generator=torch.Generator().manual_seed(args.seed+epoch))
        model.train()
        for b, y in loader:
            step_start = time.monotonic()
            if not args.overfit_rows:
                # Store weights already include any 50% pre-thinning correction.
                y["weight"] = y["weight"].float()*torch.where(y["action"] == 2304, 4*train.wait_keep_probability, 1.)
            result = optimizer_step(model, optimizer, b, y, args.microbatch, device)
            scheduler.step(); update_ema(ema, model)
            n = len(y["action"]); cursor += n; measured_rows += n
            state.update(epoch=epoch, cursor=cursor, step=state["step"]+1, rows=state["rows"]+n)
            record = {"event": "step", **state, **result, "lr": optimizer.param_groups[0]["lr"],
                      "best_dev": state["best_dev"] if math.isfinite(state["best_dev"]) else None,
                      "rows_per_second_step": n/(time.monotonic()-step_start),
                      "rows_per_second_including_loader": measured_rows/(time.monotonic()-start),
                      "gpu_peak_allocated_mib": torch.cuda.max_memory_allocated()/2**20 if device.type == "cuda" else 0,
                      "gpu_peak_reserved_mib": torch.cuda.max_memory_reserved()/2**20 if device.type == "cuda" else 0}
            log.write(json.dumps(record)+"\n"); print(json.dumps(record), flush=True)
            if state["step"] % args.checkpoint_every == 0 or stopped[0] or (args.max_steps and state["step"] >= args.max_steps):
                save_checkpoint(out/f"step-{state['step']:08d}.pt", model, ema, optimizer, scheduler, config, state, hashes, args)
            if stopped[0] or (args.max_steps and state["step"] >= args.max_steps):
                break
        from .runner import dev_joint_nll
        # Persist the completed training cursor before a potentially long dev pass.
        # A validation/data failure must not discard the epoch's optimizer state.
        save_checkpoint(out/f"step-{state['step']:08d}.pt", model, ema, optimizer, scheduler, config, state, hashes, args)
        score = dev_joint_nll(model, ema, dev, device, args.microbatch)
        improved = score < state["best_dev"]
        state["bad_epochs"] = 0 if improved else state["bad_epochs"]+1
        if improved:
            state["best_dev"] = score
            save_checkpoint(out/f"best-dev-step-{state['step']:08d}.pt", model, ema, optimizer, scheduler, config, state, hashes, args)
        log.write(json.dumps({"event": "dev", "step": state["step"], "ema_joint_nll": score})+"\n")
        if cursor >= len(indices):
            state.update(epoch=epoch+1, cursor=0)
        path = out/f"epoch-{epoch:03d}-step-{state['step']:08d}.pt"
        save_checkpoint(path, model, ema, optimizer, scheduler, config, state, hashes, args)
        # No deletion: an index marks the last three and best; older artifacts remain.
        checkpoints = sorted(out.glob("step-*.pt"), key=lambda p: p.stat().st_mtime)
        (out/"checkpoints.json").write_text(json.dumps({"last": path.name, "last_three": [p.name for p in checkpoints[-3:]],
            "best_dev": state["best_dev"], "best_files": [p.name for p in out.glob("best-dev-*.pt")]}, indent=2)+"\n")
        if stopped[0] or (args.max_steps and state["step"] >= args.max_steps) or state["bad_epochs"] >= args.patience:
            break
    log.close()
    (out/"complete.json").write_text(json.dumps({"stopped_by_signal": stopped[0], **state}, indent=2)+"\n")


if __name__ == "__main__":
    main()
