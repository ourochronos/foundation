"""M3 measurement — extraction vs Wikipedia's own ground truth.

  infobox P/R   extracted (page-subject, pid) facts vs infobox fields
                mapped to the same pids (targets >=0.6 / >=0.5 on
                infobox-bearing pages)
  link accuracy extracted entity OBJECTS must be wikilink targets on
                their page (target >=0.8)
  conflicts     same (subject, pid) asserted differently on DIFFERENT
                pages -> Track I candidates (target: >=20 found; 25-item
                precision audit follows separately)

Usage: .venv/bin/python scripts/m3_measure.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "wiki" / "pages"
SHARDS = ROOT / "data" / "wiki" / "shards"

IB_FIELD_PID = {
    "birth_date": "P569", "death_date": "P570",
    "birth_place": "P19", "death_place": "P20",
    "alma_mater": "P69", "education": "P69",
    "institutions": "P108", "workplaces": "P108", "work_institution": "P108",
    "nationality": "P27", "citizenship": "P27",
    "awards": "P166", "prizes": "P166",
    "known_for": "P800", "spouse": "P26", "spouses": "P26",
    "field": "P101", "fields": "P101",     # P101 absent from schema: skipped
}
SKIP_PIDS = {"P101"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def strip_wiki(v: str) -> list[str]:
    """Infobox value -> candidate strings (links resolved, templates
    reduced to their year/args)."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:\|([^\]]*))?\]\]", v):
        out.append(m.group(1))
        if m.group(2):
            out.append(m.group(2))
    years = re.findall(r"(1[0-9]{3}|20[0-2][0-9])", v)
    out += years
    plain = re.sub(r"\{\{[^}]*\}\}|\[\[|\]\]|<[^>]+>", " ", v)
    if plain.strip():
        out.append(plain)
    return [x for x in out if x.strip()]


def parse_infobox(wikitext: str) -> dict:
    i = wikitext.lower().find("{{infobox")
    if i < 0:
        return {}
    depth, j = 0, i
    while j < len(wikitext) and j < i + 20000:
        if wikitext[j:j + 2] == "{{":
            depth += 1; j += 2
        elif wikitext[j:j + 2] == "}}":
            depth -= 1; j += 2
            if depth == 0:
                break
        else:
            j += 1
    block = wikitext[i:j]
    fields = {}
    for m in re.finditer(r"\n\s*\|\s*([a-z_ ]+?)\s*=\s*(.+)", block):
        k = m.group(1).strip().replace(" ", "_")
        if k in IB_FIELD_PID:
            fields[IB_FIELD_PID[k]] = strip_wiki(m.group(2))
    return {p: v for p, v in fields.items() if p not in SKIP_PIDS and v}


def links_of(wikitext: str) -> set:
    return {norm(m.group(1)) for m in
            re.finditer(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", wikitext)}


pages = {}
for p in PAGES.glob("*.json"):
    d = json.loads(p.read_text())
    pages[d["title"]] = d

stmts = []
for f in sorted(SHARDS.glob("out_*.jsonl")):
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d.get("page") in pages and d.get("statement"):
                stmts.append(d)
        except Exception:
            continue
print(f"[m3] {len(stmts)} statements over {len(set(s['page'] for s in stmts))}"
      f" pages; pid-rate "
      f"{sum(1 for s in stmts if s.get('pid'))/max(len(stmts),1):.2f}",
      flush=True)

# ---- infobox P/R ----------------------------------------------------------
tp = fp = 0
recall_hit = recall_tot = 0
n_ib_pages = 0
for title, d in pages.items():
    ib = parse_infobox(d["wikitext"])
    if not ib:
        continue
    n_ib_pages += 1
    page_stmts = [s for s in stmts if s["page"] == title and s.get("pid")
                  and s["pid"] in ib
                  and norm(str(s.get("subject", ""))) == norm(title)]
    for s in page_stmts:
        cands = {norm(c) for c in ib[s["pid"]]}
        obj = norm(str(s["object"]))
        hit = any(obj and (obj in c or c in obj) for c in cands if c)
        tp += hit
        fp += not hit
    for pid, vals in ib.items():
        recall_tot += 1
        got = [s for s in stmts if s["page"] == title
               and s.get("pid") == pid
               and norm(str(s.get("subject", ""))) == norm(title)]
        cands = {norm(c) for c in vals}
        recall_hit += any(
            any(norm(str(s["object"])) and
                (norm(str(s["object"])) in c or c in norm(str(s["object"])))
                for c in cands if c) for s in got)
prec = tp / max(tp + fp, 1)
rec = recall_hit / max(recall_tot, 1)
print(f"[infobox] pages={n_ib_pages} precision={prec:.3f} "
      f"(tp={tp}, fp={fp}) [>=0.6] | recall={rec:.3f} "
      f"({recall_hit}/{recall_tot}) [>=0.5]", flush=True)

# ---- entity-link accuracy --------------------------------------------------
lk_hit = lk_tot = 0
for s in stmts:
    if not s.get("pid") or not s.get("object"):
        continue
    obj = str(s["object"])
    if re.search(r"\d{4}", obj) and len(obj) < 20:
        continue                                  # dates/values excluded
    L = links_of(pages[s["page"]]["wikitext"])
    o = norm(obj)
    lk_tot += 1
    lk_hit += (o in L) or any(o and (o in l or l in o) for l in L if l)
print(f"[links] entity-object link accuracy = {lk_hit}/{lk_tot} = "
      f"{lk_hit/max(lk_tot,1):.3f} [>=0.8]", flush=True)

# ---- cross-page conflicts (Track I candidates) -----------------------------
by_key = defaultdict(list)
for s in stmts:
    if s.get("pid") and s.get("subject") and s.get("object"):
        by_key[(norm(str(s["subject"])), s["pid"])].append(s)
conflicts = []
for (subj, pid), group in by_key.items():
    pgs = {g["page"] for g in group}
    objs = {norm(str(g["object"])) for g in group}
    if len(pgs) > 1 and len(objs) > 1:
        canon = sorted(objs)
        if not any(a in b or b in a for a in canon for b in canon
                   if a != b):
            conflicts.append({"subject": subj, "pid": pid,
                              "claims": [{"page": g["page"],
                                          "object": g["object"]}
                                         for g in group]})
print(f"[conflicts] {len(conflicts)} cross-page conflict candidates "
      f"[>=20]", flush=True)
json.dump(conflicts, open(ROOT / "data" / "wiki" / "conflicts.json", "w"),
          indent=1)

from codec.manifest import run_manifest, wilson_ci
json.dump({"n_statements": len(stmts),
           "pid_rate": sum(1 for s in stmts if s.get("pid")) / max(len(stmts), 1),
           "infobox": {"pages": n_ib_pages, "precision": prec,
                       "precision_ci95": wilson_ci(tp, max(tp + fp, 1)),
                       "recall": rec,
                       "recall_ci95": wilson_ci(recall_hit,
                                                max(recall_tot, 1))},
           "links": {"acc": lk_hit / max(lk_tot, 1), "n": lk_tot,
                     "ci95": wilson_ci(lk_hit, max(lk_tot, 1))},
           "conflicts_found": len(conflicts),
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / "m3_measure.json", "w"), indent=1)
print("[done] results/m3_measure.json", flush=True)
