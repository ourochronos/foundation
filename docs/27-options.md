# Options — target domains, tested for availability rather than plausibility

The status panel converged 4/4 on a reframing: this machinery is a **consistency
auditor, not a truth aggregator**. Provenance, scoping, conflict and refusal all
serve auditing; corroboration is not merely unavailable there but *irrelevant* —
as one reviewer put it, "three documents repeating a requirement does not make
it truer."

Several target domains follow from that, and the panel named some that turn out
to be gated. **Every endpoint below was probed, not assumed**, because the whole
argument for these domains is that they supply closed vocabularies *for free* —
and a vocabulary behind a licence desk is not free.

## 1. Availability, measured

| domain / ontology | probe | verdict |
|---|---|---|
| **US CFR** — federal regulations (eCFR API) | `200 application/json` | **open, JSON API** |
| **Gene Ontology** | `200 application/json` | **open, direct download** |
| **MeSH** (NIH, SPARQL) | `200` | **open** |
| **Schema.org** | `200 application/ld+json` | **open** |
| **EUR-Lex** — EU law | `200` | open, HTML (scrape/CELLAR) |
| SNOMED CT | `405` | **licence required** |
| UMLS | `401` | **licence required** (free for US, still an account) |
| ICD-11 (WHO) | `401` | **API key required** |
| FIBO | `403` | blocked at this URL; nominally open, needs another route |

**The panel's headline suggestion is the gated one.** SNOMED/UMLS was named as
the domain that closes all three vocabularies at once, and both need a licence.
That does not kill the idea — it means the free options are Gene Ontology,
MeSH, and regulation.

## 2. The options, ranked by what they'd actually test

**(a) US federal regulation (eCFR).** Open JSON API over the entire CFR.
Regulations are *obligations with scopes* — jurisdiction, effective date,
exemption, agency — which is precisely the shape `under_assumption` and
`valid_time` were built for, and precisely where conflicting obligations are a
real and costly problem. Closed vocabulary comes from the regulatory text's own
defined-terms sections. **Strongest fit for the auditor framing, and free.**

**(b) Gene Ontology / MeSH.** Open, genuinely closes the entity and predicate
vocabularies, mature alias handling. Weakness: the author cannot evaluate
biomedical correctness, so a wrong answer looks like a right one — the failure
mode this project has been most careful about everywhere else.

**(c) Software requirements / specs / ADRs.** No public ontology, but the
vocabulary closes *per project* and the author can judge correctness directly.
Weakest external validity, strongest evaluability, and the only option where
the dogfooding corpus is this repository's own decision log.

**(d) Multi-source news.** Not an auditor domain — this is the **falsifier** for
the corroboration closure (§3), not a product direction.

**(e) Stay with philosophy/politics.** Already built, already extracted, and
already shown to produce disagreement. Weakness: no external ontology, so every
result stays in the "validated against our own artifacts" column.

## 3. The two experiments that gate all of this

Both were fetched and verified before any of the above is worth choosing.

**Corroboration falsifier — `multi_news`.** 300 event clusters, median 2 source
articles per event, **137 with ≥3 independent sources**. Reportage repeats by
construction, and named entities are where linking actually works — unlike the
abstract concepts that produced 510 distinct terms from 316 claims. If
corroboration is ~0 *here*, it is dead and `min_sources` should be deleted
rather than mothballed. If it fires, the closure was wrong.

**Extraction fidelity — `Re-DocRED`.** 200 documents with human-annotated
entities (`vertexSet`) and relations (`labels`). This measures the single
largest unmeasured quantity after eight experiments: whether the extractor's
triples match human labels at all. 176 tests cover the model; zero cover this,
and the extractor discards half of every corpus it sees.

**Neither is a build.** Both can kill a direction, which is why they come first.
