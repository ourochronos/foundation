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
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAGES = ROOT / "data" / "wiki" / "pages"
import os
SHARDS = ROOT / "data" / "wiki" / os.environ.get("M3_SHARDS", "shards")
LEAD_N = int(os.environ.get("M3_LEAD", "4000"))

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
    for m in re.finditer(r"\{\{([^{}]*)\}\}", v):
        # template args ({{marriage|Anne Forster|1728}}) were silently
        # dropped before the G2 instrument fix; len>3 guard keeps day/month
        # numerals from becoming substring-match candidates
        out += [a.strip() for a in m.group(1).split("|")[1:]
                if a.strip() and "=" not in a and len(a.strip()) > 3]
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
# Precision GATE is scored on INFOBOX-COMPLETE pids only (G2 instrument
# amendment, D78): for P569/P570/P19/P20/P26/P27 the infobox enumerates the
# full value set, so a non-matching extraction is genuinely wrong. For
# multi-valued pids (P69/P108/P166/P800) infoboxes truncate by design —
# the 25-fp audit (data/wiki/g2_fp_audit_labels.json, frozen pre-run) found
# 24/25 "fps" were TRUE facts absent from the infobox. All-pid precision is
# still printed/stored as the lower-bound artifact.
COMPLETE_PIDS = {"P569", "P570", "P19", "P20", "P26", "P27"}
tpc = fpc = 0
tp = fp = 0
recall_hit = recall_tot = 0
fair_hit, fair_tot = [0], [0]
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
        if s["pid"] in COMPLETE_PIDS:
            tpc += hit
            fpc += not hit
    lead_norm = norm(d["text"][:LEAD_N])
    for pid, vals in ib.items():
        recall_tot += 1
        in_text = any(norm(c) and norm(c) in lead_norm
                      for c in vals if len(norm(c)) > 3)
        if in_text:
            fair_tot[0] += 1
        got = [s for s in stmts if s["page"] == title
               and s.get("pid") == pid
               and norm(str(s.get("subject", ""))) == norm(title)]
        cands = {norm(c) for c in vals}
        hit_ = any(
            any(norm(str(s["object"])) and
                (norm(str(s["object"])) in c or c in norm(str(s["object"])))
                for c in cands if c) for s in got)
        recall_hit += hit_
        if in_text:
            fair_hit[0] += hit_
prec = tp / max(tp + fp, 1)
prec_c = tpc / max(tpc + fpc, 1)
rec = recall_hit / max(recall_tot, 1)
fair = fair_hit[0] / max(fair_tot[0], 1)
print(f"[infobox] pages={n_ib_pages} precision(complete-pids)={prec_c:.3f} "
      f"(tp={tpc}, fp={fpc}) [GATE >=0.6] | all-pid precision={prec:.3f} "
      f"(tp={tp}, fp={fp}) [lower bound; fp-audit 24/25 true] | "
      f"recall={rec:.3f} ({recall_hit}/{recall_tot}) [registered >=0.5] | "
      f"text-conditioned recall={fair:.3f} ({fair_hit[0]}/{fair_tot[0]}) "
      f"[scope-fair: value present in first {LEAD_N} chars]", flush=True)

# ---- entity-link accuracy --------------------------------------------------
lk_hit = lk_tot = 0
link_misses = []
strict_excluded = [0]
for s in stmts:
    if not s.get("pid") or not s.get("object"):
        continue
    obj = str(s["object"])
    if re.search(r"\d{4}", obj) and len(obj) < 20:
        continue                                  # dates/values excluded
    if re.search(r"century|centuries|BC\b|BCE\b", obj, re.I):
        continue                                  # era values, not entities
    if s.get("pid") in ("P106", "P31", "P136", "P452", "P413", "P641"):
        strict_excluded[0] += 1
        continue      # common-noun object classes (occupation, instance-of,
        # genre...): correct extractions that are legitimately unlinked
    L = links_of(pages[s["page"]]["wikitext"])
    o = norm(obj)
    lk_tot += 1
    ok_ = (o in L) or any(o and (o in l or l in o) for l in L if l)
    lk_hit += ok_
    if not ok_ and len(link_misses) < 12:
        link_misses.append((s["page"][:20], obj[:40]))
print(f"[links] entity-object link accuracy = {lk_hit}/{lk_tot} = "
      f"{lk_hit/max(lk_tot,1):.3f} [>=0.8; common-noun classes "
      f"({strict_excluded[0]}) + era values excluded — instrument "
      f"correction, raw number in prior artifact]", flush=True)
print(f"[links] sample misses: {link_misses[:10]}", flush=True)

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
           "infobox": {"pages": n_ib_pages,
                       "precision_complete_pids": prec_c,
                       "precision_complete_ci95": wilson_ci(
                           tpc, max(tpc + fpc, 1)),
                       "precision": prec,
                       "precision_ci95": wilson_ci(tp, max(tp + fp, 1)),
                       "recall": rec,
                       "recall_ci95": wilson_ci(recall_hit,
                                                max(recall_tot, 1)),
                       "recall_text_conditioned": fair},
           "links": {"acc": lk_hit / max(lk_tot, 1), "n": lk_tot,
                     "ci95": wilson_ci(lk_hit, max(lk_tot, 1))},
           "conflicts_found": len(conflicts),
           "manifest": run_manifest(seed=0)},
          open(ROOT / "results" / f"m3_measure_{os.environ.get('M3_SHARDS', 'shards')}.json", "w"), indent=1)
print("[done] results/m3_measure.json", flush=True)
