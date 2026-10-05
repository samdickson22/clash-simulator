"""Assemble supported_cards.json and summary.json from the scan outputs."""
import collections, json, statistics, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from card_map import APPROX, BODY_ONLY, NO_EFFECT, PILOT16, SLUG_TO_GAMEDATA, TOWER_SUBSTITUTE
G66 = set(json.loads((ROOT / "training_decks/simple_gym_supported_v1.json").read_text())["support_profile"]["supported_public_cards"])
tiers = json.loads((HERE / "corpus_tiers.json").read_text())
freq = tiers["card_deck_frequency_all"]
idx_forms = collections.defaultdict(set)
import gzip
with gzip.open(HERE / "corpus_index.jsonl.gz", "rt") as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        for s in ("team", "opponent"):
            for k in r["sides"][s]["deck"]:
                for suf, form in (("-ev1", "evo"), ("-hero", "hero")):
                    if k.endswith(suf):
                        idx_forms[k[: -len(suf)]].add(form)
cards = []
for slug, name in sorted(SLUG_TO_GAMEDATA.items()):
    status = "no_effect" if slug in NO_EFFECT else "body_only" if slug in BODY_ONLY else "approx" if slug in APPROX else "supported"
    cards.append({"slug": slug, "gamedata": name, "status": status, "note": NO_EFFECT.get(slug) or BODY_ONLY.get(slug) or APPROX.get(slug),
                  "pilot16": name in PILOT16, "simple_gym66": name in G66, "scalar_s120": status in ("supported", "approx"),
                  "variant_forms_substituted_by_base": sorted(idx_forms.get(slug, ())), "decks_containing": freq.get(slug, 0)})
sup = {"cards": cards, "counts": {
    "base_cards_in_corpus": len(cards), "pilot16": sum(c["pilot16"] for c in cards), "simple_gym66": sum(c["simple_gym66"] for c in cards),
    "scalar_s120_supported_or_approx": sum(c["scalar_s120"] for c in cards), "no_effect": sorted(NO_EFFECT), "body_only": sorted(BODY_ONLY),
    "approx": sorted(APPROX), "slugs_with_evo": sum("evo" in c["variant_forms_substituted_by_base"] for c in cards),
    "slugs_with_hero": sum("hero" in c["variant_forms_substituted_by_base"] for c in cards)},
    "tower_troops": TOWER_SUBSTITUTE,
    "method": "card_smoke.py + spell_probe.py: deploy_card accepted at L11 in a fresh scalar BattleState and the defining effect observed (damage/spawn/heal/clone/speed). Shallow behavioural smoke, not parity calibration."}
(HERE / "supported_cards.json").write_text(json.dumps(sup, indent=1) + "\n")
resim = {}
for f in sorted(HERE.glob("resim_*_n*.json")):
    D = json.loads(f.read_text()); s = D["summary"]
    fc = s["first_contradiction_frac_of_match"]
    resim[f.stem] = {k: s[k] for k in ("pool", "pool_size", "n", "errors", "winner_agreement", "crowns_exact_rate", "mean_crown_abs_err",
                     "mean_tower_down_agreement_6", "placement_accept_rate", "hand_forced_rate", "elixir_topup_rate",
                     "matches_without_timed_contradiction", "contradiction_kinds_first", "matches_with_real_kill_missing_in_sim",
                     "real_team_win_rate_in_sample", "sim_team_win_rate_in_sample", "wall_s")}
    resim[f.stem]["median_first_contradiction_frac_incl_uncontradicted_as_1"] = statistics.median(fc + [1.0] * s["matches_without_timed_contradiction"])
    resim[f.stem]["median_first_contradiction_s_contradicted_only"] = statistics.median(s["first_contradiction_s"]) if fc else None
summary = {"source": json.loads((HERE / "scan_shards.json").read_text()) | {"shards": "52 replay shards, SHA-256 verified; see scan_shards.json"},
           "funnel": tiers["funnel"], "tiers_by_scope": tiers["tiers_by_scope"], "scope_definitions": tiers["scope_definitions"],
           "greedy_top20": {k: v for k, v in tiers["greedy_cumulative_top20"].items()},
           "marginal_top": {k: v[:20] for k, v in tiers["marginal_single_card_unlocks"].items()},
           "support_counts": sup["counts"], "resim": resim}
(HERE / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(sup["counts"], indent=1))
