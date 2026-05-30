import json, sys
from collections import defaultdict

path = sys.argv[1]
rows = [json.loads(l) for l in open(path)]
print("n=", len(rows))
g = defaultdict(list)
for d in rows:
    asst = [m["content"] for m in d["completion"] if m["role"] == "assistant"]
    j = " ".join(asst)
    g[d["example_id"]].append(round(d["reward"], 2))
    print("ex%-5s r=%6.2f adv=%5.2f turns=%s compl=%s za=%-5s CT=%d bareEnd=%d FINAL=%s term=%s" % (
        d["example_id"], d["reward"], d["advantage"], d["num_turns"], d["is_completed"],
        d["filters"]["zero_advantage"], j.count("CALLTYPE"),
        sum(a.strip() == "<|im_end|>" for a in asst), "FINAL" in j,
        ("cargo_test" in j or "cargo_run" in j)))
print("groups:", dict(g))
