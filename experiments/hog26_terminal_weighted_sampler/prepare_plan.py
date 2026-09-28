"""Freeze a weighted-sampling comparison of the exact same auxiliary objective."""

import json
from pathlib import Path

import torch
from sampled_contract import Plan, publish, sources
from semantic_contract import runtime_signature
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_terminal_weighted_sampler_frozen_plan_20260912.json"
    if output.exists():
        raise ValueError("preserve existing sampler comparison")
    original = root / "reports/hog26_terminal_auxiliary_frozen_plan_20260912.json"
    value = json.loads(original.read_text())
    replay_path = root / "reports/hog26_terminal_auxiliary_clipping_replay_20260912.json"
    replay = json.loads(replay_path.read_text())
    if (replay["status"] != "exact-checkpoint-clipping-replay-complete"
            or not replay["checkpoint_exact"] or not replay["prediction_exact"]):
        raise ValueError("exact clipping replay required")
    review_path = root / "reports/hog26_terminal_auxiliary_fitting_review_20260912.json"
    review = json.loads(review_path.read_text())
    if sha(review_path) != replay["review_sha256"] or not review["oof_and_intervals_exact"]:
        raise ValueError("completed auxiliary review changed")
    resources = value["resources"]
    for path, expected in review["inventory"].items():
        if sha(path) != expected:
            raise ValueError("reviewed auxiliary artifact changed")
        resources[path] = expected
    for path in (original, replay_path, review_path,
                 root / "reports/hog26_terminal_auxiliary_review_pin_20260912.json"):
        resources[str(path)] = sha(path)
    for directory in ("hog26_terminal_auxiliary", "hog26_terminal_review", "hog26_weighted_optimizer_audit"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("fixed sampler comparison dependency changed")
    value.update(schema_id="clasher.hog26.terminal-weighted-sampler.v1",
                 hypothesis="Drawing rows proportional to the declared loss weights may improve optimization of the same weighted Bernoulli objective, avoiding rare batches with large importance multipliers. Compare all eight fits against the completed uniform-row recipe and the phase-only reference.",
                 sampler="draw fitting-row count per epoch with replacement proportional to original weights; unweighted minibatch mean",
                 implementation=sources(), runtime=runtime_signature())
    value["limitations"].extend([
        "The unclipped expected loss and gradient are unchanged; minibatch composition, repeated-row exposure and gradient noise change.",
        "Thirty epochs means thirty times the fitting-row count sampled with replacement, preserving the number of optimizer steps but not exhaustive per-epoch coverage.",
        "Architecture, initialization, priors, optimizer, clipping threshold, loss weights, data and reporting remain fixed.",
        "This comparison cannot isolate clipping from other stochastic-optimization effects of sampling.",
    ])
    plan = Plan.model_validate_json(json.dumps(value))
    publish(output, plan.model_dump(mode="json"))
    print(json.dumps({"status": "frozen-requires-memory-readiness", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
