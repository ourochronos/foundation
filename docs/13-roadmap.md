# Roadmap after the anchor round (D91, user-directed 2026-07-27)

Purpose, in the user's words: build something useful and contribute to
the field. Two programs, ordered.

## P1 — Harden the two candidate contributions (from the D90 assessment)

1. **Encoder-generality control** (highest leverage): rerun M2
   (recoverability), A1 (knee), B2 (minting saturation) over 2–3 modern
   embedders incl. one LLM-derived (e.g. LLM2Vec-class / gte-Qwen-class).
   If the channel-separation law and the saturating type space survive,
   both claims harden; if not, they demote to encoder-family properties
   — either way, criterion-scored.
2. **Scale**: 10–100× corpus (peS2o staged as the stream source); watch
   whether the B2 minting curve STAYS decelerating.
3. **Named baselines**: B2 vs online DP-means / streaming PQ
   head-to-head; edit semantics vs current published MQuAKE-line numbers.
   Then the write-up: "identity is symbolic, type space is small and
   saturates: an architecture for reindex-free knowledge stores."

## P2 — The dogfood corpus (the useful artifact)

Ingest a WIDE range of AI/ML/KB/KG literature (arXiv cs.CL, cs.AI,
cs.LG, cs.IR + KG/KB topics) as attributed claims, PLUS an inventory of
off-the-shelf parts from HuggingFace (model cards / dataset cards →
structured claims: task, size, license, benchmarks, lineage), into the
same store — then USE the system on its own design space:

- ask/views/brief over the literature (Track I across papers at real
  scale — 266 conflict candidates was 1k Wikipedia pages; the ML
  literature disagrees constantly);
- synthesize related work against OUR design decisions (D-log entries
  become queryable subjects linked to the papers that anticipate,
  support, or contradict them);
- the parts inventory feeds component adoption (docs/12 bakeoffs become
  store queries);
- the reflexive loop is the point AND the demo: a research-memory over
  the AI/KB/KG field, built and continuously improved by the system it
  describes. Improvements found via its own use get D-entries.

Acceptance discipline unchanged: claim extraction via the proven fleet
recipe + veto + frozen 50-claim audits (≥0.6 gate per source type, HF
cards audited separately from paper abstracts); Sol adjudication before
each audit's D-entry closes.

## Standing queue behind these

ArXiv-50 label resolutions under Sol with full abstracts · GLiREL
bakeoff + T-REx instrument · 20k deep pass over the 800 new pages ·
wire B2 minting into live ingest (T7 fast rung for the continuous
channel) · topic-alias machinery (D83 weakness).

## Re-ingestion & citation axis (user-directed 2026-07-27, second pass)

- ~2.8 claims/paper is a FLOOR, not a ceiling — retention exists so the
  system re-ingests sources as it improves: confirm existing claims
  (corroboration counts), extract deeper (fulltext passes over the
  retained HTML), and repair (D-repair rung). Reingest-to-confirm is the
  T7 medium rung applied to sources.
- CITATIONS: the retained HTML contains bibliographies — extraction
  needs no new fetching. Representation already fits the claim model:
  (page=arxiv:A, pid=P_CITES, object=<cited id/title>, statement =
  citation context sentence when available). Corpus expansion = 
  citation-vote branching (mirror of the wiki fetcher's link votes):
  references cited by >=k in-corpus papers get fetched into the slice.
  Track I bonus: citation-backed corroboration ("5 in-corpus papers cite
  X for claim Y") becomes an evidence-count signal.
- ~~Queue: P_CITES extraction pass over papers_html~~ **DONE (D92)** — and
  it needed no fleet at all: citation edges are a deterministic pattern,
  so `scripts/cite_extract.py` is a regex over the retained bibliography
  (3,840 claims, 555 in-corpus edges, 67 cited works). Corroboration is
  surfaced by `KB.cited_by`, not `ask` — `views` is subject-side by
  design and a cited work is only ever an object.
- HF admission rule (2026-07-27): union of top-K by 30-day AND all-time downloads per tag; both recorded as dated observations. Current 200-card staging (30-day only) stands for round 1; balanced rule applies from the next fetch.

## P2 status after D92 (2026-07-27)

Both source types are ACCEPTED and ingested; the corpus is live at
18,787 claims. What D92 changed about the plan:

- **The reflexive-use goal is now blocked on topic identity, not on
  corpus size.** The AI slice has **zero subjects spanning more than one
  paper** (1,041 distinct subjects over 1,106 claims) — papers name their
  own methods, so "the ML literature disagrees constantly" is currently
  unobservable at the subject level. Track I across papers works only
  along the citation axis. **Next lever for P2 is a topic/benchmark axis**
  (benchmarks and tasks as first-class entities: `P_EVALUATES_ON`
  extracted as objects), not more papers. This is the same topic-alias
  weakness flagged at D83, now measured.
- Citation-vote branching is proven and can widen the slice whenever
  wanted (cited-by>=k → fetch).
- Deeper re-ingestion (fulltext passes over the retained HTML) remains
  the stated way past ~2.8 claims/paper; the source layer is complete
  (467/467) and the batched adjudicator now handles fulltext-sized
  evidence.

Standing queue behind P2 is unchanged except: ArXiv-50 idx 37/27 is
CLOSED (D92 — instrument artifact, no label change).
