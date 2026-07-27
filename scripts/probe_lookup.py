"""Feasibility probe: can a store lookup surface the entity an extractor
should have reused? Embeds every entity's canonical form, queries with
real AI-paper subjects, prints neighbours for judgement."""
import sys, json, random, collections
sys.path.insert(0, '/home/zonk1024/projects/foundation')
import numpy as np
from foundation.kb import KB

kb = KB(backend='pg', table='poc')
# canonical form per eid = shortest form (surface name, not a sentence)
forms = {}
for f, eids in kb.reg.by_form.items():
    for e in eids:
        cur = forms.get(e)
        if cur is None or len(f) < len(cur):
            forms[e] = f
eids = sorted(forms)
texts = [forms[e] for e in eids]
print(f"{len(eids)} entities to index", flush=True)

from codec.encode import M3Encoder
enc = M3Encoder()
Z, _ = enc.encode(texts, sparse=False, max_length=64)
Z = np.asarray(Z, np.float32)
Z /= (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-9)
np.save('/tmp/claude-1000/-home-zonk1024-projects-foundation/d8283ce1-0c3c-47aa-89e5-27777f401372/scratchpad/form_z.npy', Z)
json.dump({'eids': eids, 'texts': texts}, open('/tmp/claude-1000/-home-zonk1024-projects-foundation/d8283ce1-0c3c-47aa-89e5-27777f401372/scratchpad/form_meta.json','w'))

# page of each eid (first claim that uses it as subject) for provenance
page_of = {}
for c in kb.claims:
    page_of.setdefault(c['subj_eid'], c['page'])

ai = [c for c in kb.claims if c['page'].startswith('arxiv:') and c['pid'] == 'P_ASSERTS']
rng = random.Random(11)
sample = rng.sample(ai, 25)
idx = {e: i for i, e in enumerate(eids)}
out = []
for c in sample:
    i = idx.get(c['subj_eid'])
    if i is None:
        continue
    sims = Z @ Z[i]
    order = np.argsort(-sims)[:8]
    neigh = []
    for j in order:
        if eids[j] == c['subj_eid']:
            continue
        neigh.append((round(float(sims[j]), 3), texts[j][:52],
                      page_of.get(eids[j], '?')[:26]))
    out.append({'subject': c['subject'], 'page': c['page'],
                'statement': kb.store.texts[c['idx']][:120],
                'neighbours': neigh[:5]})
json.dump(out, open('/tmp/claude-1000/-home-zonk1024-projects-foundation/d8283ce1-0c3c-47aa-89e5-27777f401372/scratchpad/lookup_probe.json','w'), indent=1)
for o in out:
    print(f"\n### {o['subject']}   [{o['page']}]")
    for s, t, p in o['neighbours']:
        print(f"    {s}  {t:54s} {p}")
