"""Card-presence OLS screen. Associations are queue hints, never causal evidence."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from clasher.card_aliases import resolve_card_name

ENGINE = Path(__file__).resolve().parents[2]


def fit(rows, cards, censor):
    selected = [r for r in rows if censor or r.get("first_contradiction_s") is not None]
    x = np.array(
        [
            [
                1.0,
                float(r["pool"] == "g66"),
                float(r["real_end_s"]) / 100,
                *[
                    float(c in set(r["decks"]["team"] + r["decks"]["opponent"]))
                    for c in cards
                ],
            ]
            for r in selected
        ]
    )
    # Censoring sensitivity truncates at observed match end; it is NOT an
    # event-time estimate. Primary fit includes only observed finite events.
    y = np.array(
        [
            min(
                float(
                    r["real_end_s"]
                    if r["first_contradiction_s"] is None
                    else r["first_contradiction_s"]
                ),
                float(r["real_end_s"]),
            )
            if censor
            else float(r["first_contradiction_s"])
            for r in selected
        ]
    )
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    inv = np.linalg.pinv(x.T @ x)
    residual = y - x @ beta
    leverage = np.sum((x @ inv) * x, axis=1)
    adjusted = residual / np.maximum(1 - leverage, 1e-8)
    covariance = inv @ ((x * adjusted[:, None]).T @ (x * adjusted[:, None])) @ inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0))
    return {
        "n": len(y),
        "rank": int(rank),
        "columns": x.shape[1],
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "coefficients": {
            c: {
                "seconds": float(beta[i + 3]),
                "hc3_se": float(se[i + 3]),
                "present": int(x[:, i + 3].sum()),
            }
            for i, c in enumerate(cards)
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--complete", action="store_true")
    args = p.parse_args()
    if not args.complete:
        p.error("pass --complete only after screen process finishes")
    source = ENGINE / "screen/resim_screen.jsonl"
    rows = [json.loads(l) for l in source.read_text().splitlines() if l.strip()]
    assert len({r["tag"] for r in rows}) == len(rows), "duplicate screen tags"
    bundles = json.loads((ENGINE / "scenarios/manifest.json").read_text())["bundles"]
    cards = [card for bundle in bundles.values() for card in bundle]
    valid = [r for r in rows if "error" not in r and r.get("real_end_s") is not None]
    for row in valid:
        row["decks"] = {
            side: [resolve_card_name(name) for name in deck]
            for side, deck in row["decks"].items()
        }
    primary = fit(valid, cards, False)
    sensitivity = fit(valid, cards, True)
    ranked = sorted(cards, key=lambda c: primary["coefficients"][c]["seconds"])
    output = {
        "screen_rows": len(rows),
        "errors": len(rows) - len(valid),
        "finite_events": primary["n"],
        "null_event_times": len(valid) - primary["n"],
        "screen_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "model": "OLS: first_contradiction_s ~ intercept + g66_pool + real_end_s/100 + 40 any-side card-presence indicators",
        "caveats": [
            "Finite-event subset is selected; missing real kills have no event timestamp and are not zero-time events.",
            "Co-occurring deck cards confound attribution; rank and standard errors are diagnostic only.",
            "Pre-repair baseline source; no evidence of repair benefit or native parity.",
            "Sensitivity outcome is min(event time, real match end), with null events assigned match end; not survival regression.",
        ],
        "primary": primary,
        "end_censored_sensitivity": sensitivity,
        "ranked_cards": ranked,
    }
    (ENGINE / "audit/screen_attribution.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    lines = [
        "# Screen attribution",
        "",
        f"{len(rows)} rows, {len(rows) - len(valid)} errors, {primary['n']} finite event times, {len(valid) - primary['n']} null event times.",
        "",
        output["model"],
        f"Design rank {primary['rank']}/{primary['columns']}; RMSE {primary['rmse']:.2f} s.",
        "",
        "Negative coefficients associate a card with earlier contradiction, conditional on the other included variables. This is queue prioritization, not causal attribution or native acceptance.",
        "",
        "| Rank | Card | Conditional seconds | HC3 SE | Finite-event presence | End-censored sensitivity |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for i, c in enumerate(ranked, 1):
        r = primary["coefficients"][c]
        s = sensitivity["coefficients"][c]
        lines.append(
            f"| {i} | {c} | {r['seconds']:.2f} | {r['hc3_se']:.2f} | {r['present']} | {s['seconds']:.2f} |"
        )
    lines += ["", *output["caveats"]]
    (ENGINE / "audit/SCREEN_ATTRIBUTION.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                k: output[k]
                for k in [
                    "screen_rows",
                    "errors",
                    "finite_events",
                    "null_event_times",
                    "ranked_cards",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
