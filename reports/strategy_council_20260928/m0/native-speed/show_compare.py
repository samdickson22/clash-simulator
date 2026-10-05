import json, sys
D = json.load(open(sys.argv[1]))
print("identical pairs", D["identical_pairs"], "/", D["pairs"])
for k, d in D["reports"].items():
    if "decisions" not in d:
        print(k, "FAILURE", {x: d[x] for x in d if x.endswith("failure")}); continue
    ff = d.get("first_frame", {})
    print(k, d["identical"], "dec", d["decisions"], "pkt-eq", d["decision_rows_identical"], "cmds", d["commands_submitted"],
          "cmd-eq", d["command_stream_identical"], "term", d["terminal_identical"], d["terminal_ordinary_identical"],
          "res", d["result_identical"], d["result"]["a"]["score"], d["result"]["a"]["own_remaining_hp"],
          d["result"]["a"]["enemy_remaining_hp"], "tick", d["terminal"]["a"]["final_tick"],
          "nontele-dec", d["compact_frame_decisions_with_nontelemetry_differences"],
          "ff-ord", ff.get("ordinary_identical_excluding_allocation"), "ff-lvl", ff.get("levels_identical"),
          "ff-nontele", ff.get("nontelemetry_differing_paths"))
