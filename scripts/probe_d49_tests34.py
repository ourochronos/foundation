"""D49 acceptance tests 3 + 4 (docs/08) on the individuated union store.

Test 3 — ambiguity honesty: constructed set of collided names where BOTH
eids support the queried relation (flag expected) vs unique-name controls
(no flag). Targets: flag ≥ 0.9 on ambiguous, ≤ 0.05 spurious.

Test 4 — edit interaction: 150 supersessions on the EID store vs the same
edits on the surface-token store — new-answer P@1 (edit landed), 2-hop
ripple through the edited fact (loc_cap with edited capital). Eids must
not regress supersession.

Usage: .venv/bin/python scripts/probe_d49_tests34.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_src = (ROOT / "scripts" / "probe_individuation_j4.py").read_text()
_head = _src.split("# heads: LOADED")[0].replace(
    'ROOT = Path(__file__).resolve().parent.parent', f'ROOT = Path("{ROOT}")')
exec(_head)  # noqa: S102  — registry `reg`, store, walker, prof, etc.

from codec.manifest import run_manifest, wilson_ci                # noqa: E402
from codec.memory_store import MemoryStore, id_tokens             # noqa: E402
from codec.walker import ChannelWalker                            # noqa: E402
import v06_pipeline as P                                          # noqa: E402

rng = random.Random(11)
out = {}

# ---- Test 3: ambiguity honesty -------------------------------------------
both, unique = [], []
for form, eids_ in reg.by_form.items():
    live_eids = {reg._get(e).eid for e in eids_}
    if len(live_eids) > 1:
        with_pop = [e for e in live_eids
                    if reg.entities[e].slots.get(("population_of", "s"))]
        if len(with_pop) > 1:
            both.append(form)
    elif len(live_eids) == 1:
        e = next(iter(live_eids))
        if reg.entities[e].slots.get(("population_of", "s")):
            unique.append(form)
amb = rng.sample(both, min(100, len(both)))
ctl = rng.sample(unique, 100)
flag_amb = sum(len(reg.resolve_query(f, "population_of")) > 1 for f in amb)
flag_ctl = sum(len(reg.resolve_query(f, "population_of")) > 1 for f in ctl)
out["test3"] = {"flag_on_ambiguous": flag_amb / len(amb),
                "spurious_on_clean": flag_ctl / len(ctl),
                "n_amb": len(amb), "n_ctl": len(ctl)}
print(f"[test3] flag-on-ambiguous={flag_amb/len(amb):.3f} (n={len(amb)}) "
      f"[target ≥0.9] | spurious={flag_ctl/len(ctl):.3f} [target ≤0.05]",
      flush=True)

# ---- Test 4: edit interaction, eids vs surface tokens ---------------------
cap41 = [i for i, f in enumerate(w41["facts"])
         if f["relation"] == "capital_of"][:150]
cities = sorted({f["object"] for f in w41["facts"]
                 if f["relation"] == "capital_of"})
edits = []
for i in cap41:
    f = w41["facts"][i]
    new_city = rng.choice([c for c in cities if c != f["object"]])
    edits.append({"old_idx": i, "subject": f["subject"],
                  "old_obj": f["object"], "new_obj": new_city,
                  "text": f"The capital of {f['subject']} was moved to "
                          f"{new_city}."})
ecache = ROOT / "results" / "d49_t4_emb.npz"
if ecache.exists():
    Ze = np.load(ecache)["Ze"]
else:
    Ze = P.embed_texts([e["text"] for e in edits])
    np.savez(ecache, Ze=Ze)

art41 = P.build_artifacts(w41, Zf1, Zq1)
res4 = {}
for mode in ("eid", "token"):
    st = MemoryStore()
    if mode == "eid":
        for fi, f in enumerate(w41["facts"]):
            idx = st.add(Zf1[fi], [], f["text"])
            st.ids[idx] = set(fact_ids[fi])
            st.content_ids[idx] = set(fact_ids[fi])
    else:
        for fi, f in enumerate(w41["facts"]):
            st.add(Zf1[fi], f["entities"] + f["numbers"], f["text"])
    wk = ChannelWalker(
        st, protos={r: art41["rel_entry"][r]["proto"] for r in art41["RELS"]},
        ops={r: art41["rel_entry"][r]["t"] for r in art41["RELS"]})
    new_idx = {}
    for e, ze in zip(edits, Ze):
        if mode == "eid":
            se = reg.resolve_query(e["subject"], "capital_of")
            oe = reg.resolve_query(e["new_obj"])
            ids = ({se[0]} if len(se) == 1 else set()) \
                | ({oe[0]} if len(oe) == 1 else set())
            ni = st.add(ze, [], e["text"])
            st.ids[ni] = set(ids)
            st.content_ids[ni] = set(ids)
        else:
            ni = st.add(ze, [e["subject"], e["new_obj"]], e["text"])
        st.supersede(e["old_idx"], ni)
        new_idx[e["old_idx"]] = ni
    landed = ripple = rn = 0
    for e in edits:
        if mode == "eid":
            se = reg.resolve_query(e["subject"], "capital_of")
            hand = {se[0]} if len(se) == 1 else id_tokens([e["subject"]])
        else:
            hand = id_tokens([e["subject"]])
        got = wk.walk(hand, ["capital_of"])
        landed += got == new_idx[e["old_idx"]]
        # 2-hop ripple: population of the (edited) capital
        got2 = wk.walk(hand, ["capital_of", "population_of"])
        gold2 = next((j for j, f in enumerate(w41["facts"])
                      if f["relation"] == "population_of"
                      and f["subject"] == e["new_obj"]), None)
        if gold2 is not None:
            rn += 1
            ripple += got2 == gold2
    res4[mode] = {"landed": landed / len(edits),
                  "ripple": ripple / max(rn, 1), "ripple_n": rn}
    print(f"[test4 {mode:>5}] edit-landed={landed/len(edits):.3f} "
          f"2hop-ripple={ripple/max(rn,1):.3f} (n={len(edits)}/{rn})",
          flush=True)
out["test4"] = res4

(ROOT / "results" / "d49_tests34.json").write_text(json.dumps(
    {**out, "manifest": run_manifest(seed=11)}, indent=2))
print("[done] results/d49_tests34.json", flush=True)
