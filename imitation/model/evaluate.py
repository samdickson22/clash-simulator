"""Natural-row offline metrics, dev-only calibration, paired cluster inference.

No training weights enter reporting. Metric arrays preserve perspective and row
identity so external baselines can be compared with exactly paired resamples.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from .network import masked_log_softmax
from .losses import hazard_loss


def _numpy(t):
    return t.detach().float().cpu().numpy()


@torch.inference_mode()
def metric_rows(o, y, hand_ids, temperatures=(1., 1., 1.)):
    """Return O(rows) statistics rather than retaining 2306-way distributions."""
    a = y["action"].long(); n = len(a)
    r = torch.arange(n, device=a.device)
    supervised = y["supervised"].bool()
    play = supervised & (a < 2304)
    slot = (a//576).clamp(0, 3); tile = a.remainder(576)
    gate_y = torch.where(a == 2304, 0, torch.where(a == 2305, 2, 1))
    gp = masked_log_softmax(o["gate"]/temperatures[0], o["gate_mask"])
    cp = masked_log_softmax(o["card"]/temperatures[1], o["card_mask"])
    tp = masked_log_softmax(o["tile"]/temperatures[2], o["tile_mask"])
    if tp.shape[1] != 4:
        raise ValueError("evaluation needs all-card tile conditionals")
    # Aggregate duplicate hand tokens for card metrics (frozen spec).
    token_p = torch.zeros(n, 360, device=a.device).scatter_add_(1, hand_ids, cp.exp())
    labelled_card = hand_ids[r, slot]
    card_nll = -token_p[r, labelled_card].clamp_min(1e-30).log()
    card_rank = token_p.argsort(-1, descending=True)[:, :3]
    tile_nll = -tp[r, slot, tile]
    when = supervised & o["card_mask"].any(-1)
    p_act = (gp[:, 1:].exp()).sum(-1)
    binary_nll = torch.where(a == 2304, -gp[:, 0], -torch.logsumexp(gp[:, 1:], -1))
    joint = -gp[r, gate_y] + torch.where(play, -cp[r, slot] + tile_nll, 0.)
    pred_tile = tp[r, slot].argmax(-1)
    distance = ((pred_tile%18-tile%18).float().square() +
                (pred_tile//18-tile//18).float().square()).sqrt()
    joints = (cp[:, :, None]+tp).flatten(1)
    top = joints.topk(8, dim=-1).indices
    legal_top = o["tile_mask"].flatten(1).gather(1, top)
    top_cards = hand_ids.gather(1, top//576)
    delta = (top%576%18-tile[:, None]%18).square() + (top%576//18-tile[:, None]//18).square()
    matching_card = top_cards == labelled_card[:, None]
    within = (matching_card & (delta <= 1) & legal_top).any(-1)
    exact = ((top == a[:, None]) & legal_top).any(-1)
    def values(t, mask):
        return t.float().masked_fill(~mask, float("nan"))
    result = {
        "play_wait_nll": values(binary_nll, when),
        "play_wait_brier": values((p_act-(a != 2304).float()).square(), when),
        "play_wait_nll_all": values(binary_nll, supervised),
        "play_wait_brier_all": values((p_act-(a != 2304).float()).square(), supervised),
        "joint_nll": values(joint, supervised), "card_nll": values(card_nll, play),
        "card_top1": values(card_rank[:, 0] == labelled_card, play),
        "card_top3": values((card_rank == labelled_card[:, None]).any(-1), play),
        "tile_nll": values(tile_nll, play), "tile_error": values(distance, play),
        "tile_within1": values(distance <= 1, play), "top8_recall": values(exact, play),
        "top8_within1": values(within, play),
        "ability_nll": values(-gp[:, 2], supervised & (a == 2305)),
        "gate_confidence": values(gp.exp().max(-1).values, when),
        "gate_correct": values(gp.argmax(-1) == gate_y, when),
        "card_confidence": values(token_p.max(-1).values, play),
        "card_correct": values(card_rank[:, 0] == labelled_card, play),
        "p_act": values(p_act, when), "acted": values(a != 2304, when),
        "label_card": torch.where(play, labelled_card, -1),
    }
    intent_use = supervised & y["intent_valid"].bool()
    observed = y["intent_observed"].bool(); bins = y["intent_bin"].long()
    result["intent_hazard_nll"] = values(hazard_loss(o["hazard"], bins, observed), intent_use)
    ic = y["intent_card"].long()
    result["intent_card_nll"] = values(F.cross_entropy(o["intent_card"].float(), ic.clamp(0, 7), reduction="none"),
                                        intent_use & observed & (ic >= 0))
    for k in range(13):
        at_risk = intent_use & ((bins > k) | (observed & (bins == k)))
        result[f"hazard_p_{k}"] = values(o["hazard"][:, k].float().sigmoid(), at_risk)
        result[f"hazard_y_{k}"] = values(observed & (bins == k), at_risk)
    # One device-to-host transfer for all O(rows) sufficient statistics.
    packed = torch.stack([v.float() for v in result.values()], 1).cpu().numpy()
    result = {key: packed[:, i] for i, key in enumerate(result)}
    result["label_card"] = result["label_card"].astype(np.int64)
    return result


def calibration(confidence, correct, bins=10, equal_mass=False):
    use = np.isfinite(confidence) & np.isfinite(correct)
    p, y = confidence[use], correct[use]
    if not len(p):
        return {"ece": None, "bins": []}
    groups = np.array_split(np.argsort(p, kind="stable"), bins) if equal_mass else [
        np.flatnonzero(np.minimum((p*bins).astype(int), bins-1) == i) for i in range(bins)]
    detail = [{"count": len(ix), "confidence": float(p[ix].mean()), "observed": float(y[ix].mean())}
              for ix in groups if len(ix)]
    return {"ece": sum(d["count"]*abs(d["confidence"]-d["observed"]) for d in detail)/len(p), "bins": detail}


def _cluster_ci(values, clusters, resamples, seed, median=False):
    """Resample WHOLE perspectives, including clusters with zero eligible rows.

    Discrete squared tile distances make an exact median histogram practical.
    np.median's even-sample convention is preserved in each resample.
    """
    _, group = np.unique(clusters, return_inverse=True)
    count = int(group.max())+1 if len(group) else 0
    if not count or not np.isfinite(values).any() or resamples <= 0:
        return None
    use = np.isfinite(values)
    if median:
        levels, level = np.unique(values[use], return_inverse=True)
        hist = np.zeros((count, len(levels)), np.float64)
        np.add.at(hist, (group[use], level), 1)
    else:
        sums = np.bincount(group[use], values[use], minlength=count)
        nums = np.bincount(group[use], minlength=count)
    rng = np.random.default_rng(seed); samples = []
    for start in range(0, resamples, 128):
        w = rng.multinomial(count, np.full(count, 1/count), size=min(128, resamples-start))
        if median:
            h = w @ hist; cumulative = h.cumsum(-1); total = h.sum(-1)
            lo = ((total-1)//2).clip(0); hi = (total//2).clip(0)
            li = (cumulative <= lo[:, None]).sum(-1).clip(0, len(levels)-1)
            ui = (cumulative <= hi[:, None]).sum(-1).clip(0, len(levels)-1)
            v = (levels[li]+levels[ui])/2
            v[total == 0] = np.nan
        else:
            den = w @ nums
            v = np.divide(w @ sums, den, out=np.full(len(w), np.nan), where=den > 0)
        samples.extend(v.tolist())
    finite = np.asarray(samples); finite = finite[np.isfinite(finite)]
    return None if not len(finite) else np.quantile(finite, [.025, .975]).tolist()


def calibration_ci(confidence, correct, clusters, resamples=10000, seed=1, bins=10):
    """Exact fixed-width ECE under perspective-cluster multiplicities."""
    use = np.isfinite(confidence) & np.isfinite(correct)
    if not use.any() or resamples <= 0:
        return None
    _, group = np.unique(clusters, return_inverse=True)
    count = int(group.max())+1
    bucket = np.minimum((confidence[use]*bins).astype(int), bins-1)
    num = np.zeros((count, bins)); delta = np.zeros_like(num)
    np.add.at(num, (group[use], bucket), 1)
    np.add.at(delta, (group[use], bucket), confidence[use]-correct[use])
    rng = np.random.default_rng(seed); values = []
    for start in range(0, resamples, 128):
        w = rng.multinomial(count, np.full(count, 1/count), size=min(128, resamples-start))
        totals = (w@num).sum(-1)
        v = np.divide(np.abs(w@delta).sum(-1), totals, out=np.full(len(w), np.nan), where=totals>0)
        values.extend(v[np.isfinite(v)])
    return np.quantile(values, [.025, .975]).tolist() if values else None


MEAN_METRICS = ("play_wait_nll", "play_wait_brier", "play_wait_nll_all", "play_wait_brier_all",
                "joint_nll", "card_nll", "card_top1", "card_top3", "tile_nll", "tile_within1",
                "top8_recall", "top8_within1", "ability_nll", "intent_hazard_nll", "intent_card_nll")


def summary_cluster_cis(rows, clusters, resamples, seed):
    """Reuse identical perspective draws across all statistics in one summary.

    Matches the original seeded multinomial stream (128 draws/chunk), cluster
    universe, quantiles and even-median convention. No approximation/subsampling.
    """
    _, group = np.unique(clusters, return_inverse=True)
    count = int(group.max())+1 if len(group) else 0
    if not count or resamples <= 0:
        return {}
    names = [k for k in MEAN_METRICS if k in rows]
    sums, nums = [], []
    for name in names:
        v=rows[name]; use=np.isfinite(v)
        sums.append(np.bincount(group[use],v[use],minlength=count))
        nums.append(np.bincount(group[use],minlength=count))
    sums=np.stack(sums,1); nums=np.stack(nums,1)
    ece={}
    for name,p,y in (("gate_ece","p_act","acted"),("gate_multiclass_ece","gate_confidence","gate_correct"),("card_ece","card_confidence","card_correct")):
        use=np.isfinite(rows[p]) & np.isfinite(rows[y]); bucket=np.minimum((rows[p][use]*10).astype(int),9)
        number=np.zeros((count,10));delta=np.zeros_like(number)
        np.add.at(number,(group[use],bucket),1)
        np.add.at(delta,(group[use],bucket),rows[p][use]-rows[y][use])
        ece[name]=(number,delta)
    hist=None
    if 'tile_error' in rows:
        use=np.isfinite(rows['tile_error'])
        if use.any():
            levels,level=np.unique(rows['tile_error'][use],return_inverse=True)
            hist=np.zeros((count,len(levels)))
            np.add.at(hist,(group[use],level),1)
    samples={k:[] for k in names+list(ece)+['tile_error']}
    rng=np.random.default_rng(seed)
    for start in range(0,resamples,128):
        w=rng.multinomial(count,np.full(count,1/count),size=min(128,resamples-start))
        den=w@nums
        v=np.divide(w@sums,den,out=np.full(den.shape,np.nan),where=den>0)
        for i,k in enumerate(names): samples[k].append(v[:,i])
        for k,(number,delta) in ece.items():
            den=(w@number).sum(-1)
            samples[k].append(np.divide(np.abs(w@delta).sum(-1),den,out=np.full(len(w),np.nan),where=den>0))
        if hist is not None:
            h=w@hist; cumulative=h.cumsum(-1); total=h.sum(-1)
            lo=((total-1)//2).clip(0); hi=(total//2).clip(0)
            li=(cumulative<=lo[:,None]).sum(-1).clip(0,len(levels)-1)
            ui=(cumulative<=hi[:,None]).sum(-1).clip(0,len(levels)-1)
            v=(levels[li]+levels[ui])/2;v[total==0]=np.nan
            samples['tile_error'].append(v)
    result={}
    for k,parts in samples.items():
        values=np.concatenate(parts) if parts else np.array([])
        values=values[np.isfinite(values)]
        result[k]=np.quantile(values,[.025,.975]).tolist() if len(values) else None
    return result


def summarize(rows, clusters, resamples=10000, seed=1):
    report = {"rows": len(clusters), "perspectives": len(np.unique(clusters)), "metrics": {}}
    intervals = summary_cluster_cis(rows, clusters, resamples, seed)
    for name in (*MEAN_METRICS, "tile_error"):
        if name not in rows:
            continue
        values = rows[name]; use = np.isfinite(values); median = name == "tile_error"
        label = "median_tile_error" if median else name
        report["metrics"][label] = {
            "n": int(use.sum()), "value": float(np.median(values[use]) if median else values[use].mean()) if use.any() else None,
            "ci95": intervals.get(name)}
    for name, p, y, mass in (("gate_ece", "p_act", "acted", False),
                            ("gate_multiclass_ece", "gate_confidence", "gate_correct", False),
                            ("card_ece", "card_confidence", "card_correct", False),
                            ("timing_hazard_calibration", "p_act", "acted", True)):
        report[name] = calibration(rows[p], rows[y], equal_mass=mass)
        if not mass:
            report[name]["ci95"] = intervals.get(name)
    report["intent_hazard_calibration"] = []
    for k in range(13):
        p, y = rows[f"hazard_p_{k}"], rows[f"hazard_y_{k}"]
        use = np.isfinite(p)
        report["intent_hazard_calibration"].append({"bin": k, "at_risk": int(use.sum()),
            "predicted": float(p[use].mean()) if use.any() else None,
            "observed": float(y[use].mean()) if use.any() else None})
    return report


def offline_gates(rows, frequency, clusters, card_scope, p16_mask, p16_baseline=None,
                  resamples=10000, seed=1):
    """A1–A4 comparisons; caller must first verify baseline row identity.

    An unobserved card is unassessed, never silently counted as passing. On dev,
    these are diagnostic only; T4 does not admit arms or score heldout roles.
    """
    comparisons = compare_paired(rows, frequency, clusters, resamples, seed)
    a1 = all(v["ci95"] is not None and v["ci95"][1] < 0 for v in comparisons.values())
    a2_details = {}
    if p16_baseline is not None:
        keep = np.asarray(p16_mask, bool)
        for key in ("card_nll", "tile_nll"):
            use = keep & np.isfinite(rows[key]) & np.isfinite(p16_baseline[key])
            delta = rows[key][use]-p16_baseline[key][use]
            a2_details[key] = {"delta": float(delta.mean()) if len(delta) else None,
                              "within_0.05": bool(len(delta) and delta.mean() <= .05)}
    cards = {}
    for card in card_scope:
        use = rows["label_card"] == card
        delta = np.where(use, rows["tile_nll"]-frequency["tile_nll"], np.nan)
        ci = _cluster_ci(delta, clusters, resamples, seed)
        cards[str(card)] = {"n": int(np.isfinite(delta).sum()), "ci95": ci,
                            "significantly_worse": ci is not None and ci[0] > 0}
    gate_ece = calibration(rows["p_act"], rows["acted"])["ece"]
    return {"A1": {"pass": a1, "paired_differences": comparisons},
            "A2": {"pass": all(x["within_0.05"] for x in a2_details.values()) if a2_details else None,
                   "p16": a2_details},
            "A3": {"pass": all(v["n"] and not v["significantly_worse"] for v in cards.values()),
                   "passing_cards": sum(bool(v["n"] and not v["significantly_worse"]) for v in cards.values()),
                   "scoped_cards": len(cards), "cards": cards},
            "A4": {"ece": gate_ece, "pass": gate_ece is not None and gate_ece <= .01}}


def report_slices(rows, clusters, slices, resamples=10000, seed=1):
    report = {"overall": summarize(rows, clusters, resamples, seed), "slices": {}}
    for name, labels in slices.items():
        labels = np.asarray(labels)
        report["slices"][name] = {}
        for label in np.unique(labels):
            if str(label) in ("-1", "", "None"):
                continue
            keep = labels == label
            subset = {k: v[keep] for k, v in rows.items()}
            report["slices"][name][str(label)] = summarize(subset, clusters[keep], resamples, seed)
    return report


def compare_paired(rows, baseline, clusters, resamples=10000, seed=1):
    report = {}
    for key in ("joint_nll", "play_wait_nll", "card_nll", "tile_nll"):
        if key not in baseline:
            raise ValueError(f"baseline missing {key}")
        if rows[key].shape != baseline[key].shape or not np.array_equal(np.isfinite(rows[key]), np.isfinite(baseline[key])):
            raise ValueError("baseline must align row ids and eligibility exactly")
        delta = rows[key]-baseline[key]
        use = np.isfinite(delta)
        report[key] = {"delta": float(delta[use].mean()) if use.any() else None,
                       "ci95": _cluster_ci(delta, clusters, resamples, seed)}
    return report


def fit_temperature(logits, mask, target, role="dev"):
    if role != "dev":
        raise ValueError("temperatures may be fitted on dev only")
    if not len(target):
        return 1.0
    logits, mask, target = logits.detach().float().cpu(), mask.detach().cpu(), target.detach().long().cpu()
    log_t = torch.zeros((), requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=.3, max_iter=60, line_search_fn="strong_wolfe")
    def closure():
        opt.zero_grad()
        lp = masked_log_softmax(logits/log_t.clamp(-4, 4).exp(), mask)
        loss = F.nll_loss(lp, target)
        loss.backward()
        return loss
    opt.step(closure)
    return float(log_t.detach().clamp(-4, 4).exp())


def frequency_output(action_mask, hand, ticks, own_elixir_normalized, counts):
    """T3 train-frequency counts, no fitting and no legacy baseline code import."""
    device = hand.device
    tile_mask = action_mask[:, :2304].view(-1, 4, 576)
    card_mask = tile_mask.any(-1)
    gate_mask = torch.stack((action_mask[:, 2304], card_mask.any(-1), action_mask[:, 2305]), -1)
    phase = torch.where(ticks < 2400, 0, torch.where(ticks < 3600, 1, 2))
    bucket = phase*11 + (own_elixir_normalized*10+1e-5).floor().long().clamp(0,10)
    gc = torch.as_tensor(counts["gate"], device=device, dtype=torch.float64)
    gate = gc[bucket]*gate_mask
    gate = torch.where((gate.sum(-1)==0)[:, None], gc.sum(0)[None]*gate_mask, gate)
    if (gate.sum(-1)==0).any():
        raise ValueError("train-frequency counts have no legal gate mass")
    card = torch.as_tensor(counts["cards"], device=device, dtype=torch.float64)[hand]*card_mask
    card = torch.where((card.sum(-1)==0)[:,None], card_mask.double(), card)
    tile = (torch.as_tensor(counts["tiles"], device=device, dtype=torch.float64)[hand]+1)*tile_mask
    n = len(hand)
    return {"gate": gate.clamp_min(1e-30).log(), "card": card.clamp_min(1e-30).log(),
            "tile": tile.clamp_min(1e-30).log(), "gate_mask": gate_mask, "card_mask": card_mask,
            "tile_mask": tile_mask, "intent_card": torch.zeros(n,8,device=device),
            "hazard": torch.zeros(n,13,device=device)}


def main():
    p = argparse.ArgumentParser(description="T4 dev evaluator; heldout scoring is intentionally disabled")
    p.add_argument("--store", required=True); p.add_argument("--checkpoint", required=True)
    p.add_argument("--output", required=True); p.add_argument("--device", default="cpu")
    p.add_argument("--assets", help="v5 static NPZ built against T3's frozen runtime")
    p.add_argument("--roles", help="frozen role JSON for archetype reporting only")
    p.add_argument("--frequency-rows", help="aligned natural per-row frequency-baseline metric directory")
    p.add_argument("--frequency-counts", help="T3's train-only frequency-counts.npz")
    p.add_argument("--p16-rows", help="aligned upgraded P16 baseline metric directory")
    p.add_argument("--p16-summary", help="T3's already-scored dev-only p16-bc-dev.json; no legacy code is imported")
    p.add_argument("--card-scope", help="JSON list of token IDs; required for an A3 gate report")
    p.add_argument("--bootstrap", type=int, default=10000); p.add_argument("--batch-size", type=int, default=1024)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--calibrate", action="store_true"); p.add_argument("--calibration-rows", type=int, default=100000)
    args = p.parse_args()
    from .runner import evaluate_checkpoint
    evaluate_checkpoint(args)


if __name__ == "__main__":
    main()
