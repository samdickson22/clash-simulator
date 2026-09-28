"""Replay one frozen fit exactly while recording its existing clipping factors."""

import fcntl
import json
from pathlib import Path

import numpy as np
import torch
from scalar_evaluation import EvaluationIndex
from terminal_contract import load_plan, publish
from terminal_experiment import prepare
from terminal_labels import sha
from terminal_model import TerminalPredictor, optimizer_for, predict


def main():
    lock = Path("/Users/sam/Library/Application Support/ClasherMonitor/comparison.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_terminal_auxiliary_clipping_replay_20260912.json"
    if output.exists():
        raise ValueError("preserve existing clipping replay")
    review_path = root / "reports/hog26_terminal_auxiliary_fitting_review_20260912.json"
    review = json.loads(review_path.read_text())
    if review["status"] != "completed-auxiliary-terminal-fitting-review" or not review["checkpoint_predictions_exact"]:
        raise ValueError("complete checkpoint reproduction required before clipping replay")
    plan_path = root / "reports/hog26_terminal_auxiliary_frozen_plan_20260912.json"
    plan = load_plan(plan_path)
    source_sha = sha(__file__)
    data, labels = prepare(plan)
    fold = data.folds[0]
    rows, weights = fold.indices, fold.margin_weights
    prior = float(np.sum(labels[fold.mask] * weights[fold.mask]))
    torch.manual_seed(1279501)
    model = TerminalPredictor(prior)
    optimizer = optimizer_for(model)
    x, y, w = torch.from_numpy(data.features), torch.from_numpy(labels), torch.from_numpy(weights.astype(np.float32))
    selected = torch.from_numpy(rows.astype(np.int64))
    index = EvaluationIndex(data.evaluation[0], data.evaluation[1])
    groups = {"all": np.ones(len(labels), dtype=bool), "positive": labels == 1,
              "negative": labels == 0, "late": index.phases == 2,
              "representative": index.representative_mask,
              "late_representative": index.representative_mask & (index.phases == 2)}
    totals = {name: {"coefficient_before_clip": 0., "coefficient_after_clip": 0.,
                     "logit_derivative_mass_before_clip": 0., "logit_derivative_mass_after_clip": 0.}
              for name in groups}
    epochs = []
    for epoch in range(30):
        order = torch.randperm(len(rows))
        clipped, batches, norm_sum = 0, 0, 0.
        for start in range(0, len(rows), 512):
            chosen = selected[order[start:start + 512]]
            optimizer.zero_grad(set_to_none=True)
            logits = model(x[chosen])
            losses = torch.nn.functional.binary_cross_entropy_with_logits(logits, y[chosen], reduction="none")
            loss = (losses * w[chosen]).sum() * len(rows) / len(chosen)
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite replay loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
            optimizer.step()
            # The update above is the frozen step verbatim. The following reads
            # consume no randomness and do not change gradients or parameters.
            factor = float(torch.clamp(1. / (norm + 1e-6), max=1.))
            clipped += float(norm) > 1
            batches += 1
            norm_sum += float(norm)
            ids = chosen.numpy()
            coefficient = w[chosen].numpy().astype(np.float64) * len(rows) / len(chosen)
            derivative = np.abs(torch.sigmoid(logits.detach()).numpy() - labels[ids])
            for name, membership in groups.items():
                active = membership[ids]
                mass = float(coefficient[active].sum())
                derivative_mass = float((coefficient[active] * derivative[active]).sum())
                totals[name]["coefficient_before_clip"] += mass
                totals[name]["coefficient_after_clip"] += mass * factor
                totals[name]["logit_derivative_mass_before_clip"] += derivative_mass
                totals[name]["logit_derivative_mass_after_clip"] += derivative_mass * factor
        epochs.append({"epoch": epoch + 1, "batches": batches, "clipped_batches": clipped,
                       "mean_preclip_norm": norm_sum / batches})
        print(json.dumps(epochs[-1]), flush=True)
    directory = root / "reports/hog26_terminal_auxiliary_comparison_20260912"
    checkpoint = directory / "seed1279501-fold0.pt"
    saved = torch.load(checkpoint, weights_only=True, map_location="cpu")
    if any(not torch.equal(value, saved[name]) for name, value in model.state_dict().items()):
        raise ValueError("instrumented replay did not reproduce checkpoint exactly")
    probability = predict(model.eval(), data.features)
    prediction_path = directory / "seed1279501-fold0-predictions.npz"
    with np.load(prediction_path, allow_pickle=False) as saved_predictions:
        if not np.array_equal(probability, saved_predictions["terminal_probability"]):
            raise ValueError("replayed probabilities differ")
    for group in totals.values():
        group["coefficient_retention"] = group["coefficient_after_clip"] / group["coefficient_before_clip"]
        group["logit_derivative_retention"] = group["logit_derivative_mass_after_clip"] / group["logit_derivative_mass_before_clip"]
    p = np.clip(probability[fold.mask], 1e-12, 1 - 1e-12)
    target = labels[fold.mask]
    weight = weights[fold.mask]
    nll = float(np.sum(weight * -(target * np.log(p) + (1 - target) * np.log1p(-p))))
    prior_nll = float(-(prior * np.log(prior) + (1 - prior) * np.log1p(-prior)))
    load_plan(plan_path)
    if sha(__file__) != source_sha:
        raise ValueError("replay source changed")
    publish(output, {"status": "exact-checkpoint-clipping-replay-complete", "seed": 1279501, "fold": 0,
                     "checkpoint_exact": True, "prediction_exact": True, "epochs": epochs,
                     "groups": totals, "fitting_weighted_nll": nll, "fitting_prior_nll": prior_nll,
                     "fitting_weighted_nll_gain": prior_nll - nll,
                     "fitting_weighted_predicted_mass": float(np.sum(weight * p)), "fitting_weighted_observed_mass": prior,
                     "source_sha256": source_sha, "plan_sha256": sha(plan_path),
                     "review_sha256": sha(review_path), "checkpoint_sha256": sha(checkpoint),
                     "new_candidate_saved": False, "acceptance": False,
                     "limitations": ["One exact replay measures this recipe; it does not establish clipping as the sole cause.",
                                     "Coefficient and logit-derivative retention describe clipping before Adam preconditioning, not effective parameter influence.",
                                     "Any sampler or optimizer change requires a separate frozen experiment and complete review."]})
    print(json.dumps({"status": "exact-checkpoint-clipping-replay-complete", "groups": totals,
                      "fitting_weighted_nll_gain": prior_nll - nll}), flush=True)


if __name__ == "__main__":
    main()
