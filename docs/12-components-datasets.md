# Commodity components & open datasets — survey (D85, 2026-07-26)

Full survey by subagent (28 sources, 2025-26 checkpoints); condensed here.
Hardware frame: RX 9070 16GB ROCm (gfx1201) or CPU; anything requiring
CUDA-only flash-attn flagged. NC = non-commercial license (fine for
research; flag before any commercial turn).

## Adopt-candidates (the three cheapest high-leverage wins)

| Component | HF/id | Size | License | Slots into |
|---|---|---|---|---|
| MiniCheck-Flan-T5-Large | lytang/MiniCheck-Flan-T5-Large | 0.8B | Apache | deterministic faithfulness judge beside Haiku (LLM-AggreFact 75.0 ≈ GPT-4; >500 docs/min) |
| Maverick coref | sapienzanlp/maverick-mes-ontonotes | ~500M | CC BY-NC | the unbuilt M3 coref gap (OntoNotes 83.6 F1; trains <16GB); fastcoref (MIT) as the throughput/clean-license alternative |
| ReFinED | amazon-science/ReFinED | encoder | Apache | entity linking to Wikipedia titles = our canonical entities (also emits QIDs); unmaintained since 2022 — budget dependency archaeology |

Local judge, stronger tier: Bespoke-MiniCheck-7B (CC BY-NC; AggreFact
77.4 — above Claude-3.5-Sonnet; GGUF via ollama → runs on the llama.cpp
HIP stack). Granite Guardian 3.3 (Apache, 76.5) as clean-license 8B alt.

## Test-worthy (bakeoff before adopting)

- **GLiREL** (jackboyla/glirel-large-v0, NC): zero-shot RE Wiki-ZSL 83.7 /
  FewRel 87.6 — same band as our 0.85 mapping bottleneck, deterministic,
  free per call. **Planned bakeoff: Haiku vs GLiREL vs GLiNER2-schema on
  a gold slice of the 30-pid inventory; ensemble-veto (LLM proposes,
  GLiNER-family confirms) is the predicted precision winner.**
- GLiNER2 (fastino/gliner2-*-v1, Apache, CPU-fast): schema-driven
  entities+relations one-pass; NER competitive with GPT-4o zero-shot;
  RE evals thin. Pre-pass/veto role.
- GLiNER-Relex (2605.10108): newest family member, joint NER+RE; ids
  unverified.
- ReLiK EL (sapienzanlp, license check needed): stronger in-domain than
  ReFinED, heavier, real OOD drop on ArXiv-like text.
- Triplex (SciPhi, NC+waiver, GGUF): local LLM triple extractor on our
  llama.cpp stack; compare vs Haiku stage-1.
- FactCG-DeBERTa-L (0.4B, AggreFact 75.6) if license checks out; HHEM
  as ultra-cheap CPU tier.

## Skips

BLINK/GENRE (superseded), REBEL (aged, hallucination-prone), ReLiK-RE
(closed schema), AlignScore/plain NLI as judges (superseded), 2025-26
LLM-EL papers without checkpoints (watch LELA).

Topic-synonym splitting (D83 weakness) is NOT solved by anything above —
nearest fix stays: cluster BGE-M3 vectors + MiniCheck equivalence check.

## Open datasets (user-directed addition; alignments to OUR instruments)

- **T-REx** — (sentence ↔ Wikidata triple) alignments over Wikipedia
  abstracts at scale. **Gold calibration set for the M1 mapper and a
  per-sentence instrument that beats infobox lower bounds** (the D78
  problem class disappears where alignment gold exists). First pick.
- **KILT** — provenance-graded benchmark suite on a fixed Wikipedia
  snapshot (fact-check/QA/slot-filling with evidence spans). Our ask
  surface can be scored on it directly; also pins a REVISION-STAMPED
  snapshot (pairs with the revid-provenance fix).
- **VitaminC** — contrastive evidence from Wikipedia REVISIONS: evidence
  edits flip labels. External validation for supersession/edit-ripple
  semantics — the Track I / edit analog of what MQuAKE was for K6.
- **WebNLG / KELM** — triple↔text in both directions: renderer-template
  eval (D81 surface) and text→triple training/calibration.
- **2WikiMultiHopQA** — multi-hop with GOLD decomposition triples +
  Wikidata alignment: external validation for chain() beyond MQuAKE.
- **SciFact / SciFact-Open** — scientific claim verification with
  evidence; judge-calibration set for the ArXiv claim audits.
- **peS2o / S2ORC** — scientific full-text at scale: the stream source
  for B2 (anchor-minting-rate curve) beyond math.LO.
- License-restricted (skip unless needed): TACRED, OntoNotes, AIDA.

Adoption rule stays D67: each component/dataset enters through a
measured bakeoff against the incumbent, logged as a D-entry.

## Independent adjudication status

Standing adjudicator model (user 2026-07-27): **GPT 5.6 Sol** via
`copilot --model gpt-5.6-sol` (default in scripts/adjudicate.py). The
D86 runs used gpt-5.4 (historical; artifacts unchanged).

Gemini CLI 0.52.0 installed; OAuth completes but Google has SUNSET the
free individual Code Assist tier (`IneligibleTierError` → Antigravity
migration). Path that works: AI Studio API key in `GEMINI_API_KEY`
(no browser). Until then: MiniCheck-FT5 covers entailment-shaped second
opinions locally; cross-vendor review of instrument amendments can also
route through the user's GPT (Sol) channel.
