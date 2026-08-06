# Direction brief: slot instantiation, closure, and faults as acquisition

**This is a pivot, and it is being put to you before anything is built.** Sunk
cost is explicitly not a consideration — the author has said so and the record
below shows it is meant. Recommending abandonment is a legitimate answer.

---

## 1. Where this came from

Eighteen experiments on extraction into a claim store. The measurements that
matter for judging this proposal:

| finding | number |
|---|---|
| extraction recall, every method tried | **0.155–0.266** across REBEL, prompted generation, windowing, hybrid filtering, enumeration, calibration |
| the missed relations are **plainly stated in the text** | missed gold verifies "STATED" at 0.636 — *identical* to recovered gold, against 0.136 for fabricated controls |
| run-to-run noise floor, byte-identical prompts | **0.041 F1**, plus a 2/12 hard-failure rate |
| corroboration across four discourse corpora | **0** (papers cite rather than repeat; positions disagree rather than concur) |
| corroboration in multi-source news | 41 triples — the only non-zero |
| three vocabularies (predicate, frame, entity) must close **simultaneously** | closing two of three yields exactly zero |
| blanket LLM extraction | 473 predictions for 87 correct answers; a prior system by the same author hit the same wall at 29k claims |

**The honest reading**: most of that arc's rankings sit inside the noise floor,
and the one robust finding is that recall is pinned near 0.2 regardless of
method while the information demonstrably *is* in the text. That is a
representation-mismatch cost, not an extractor-quality problem.

## 2. What is proposed instead

Stop treating the store as a passive index to be filled and queried. Build
around **concept loading for reasoning**, with four pieces:

**(a) Slot instantiation as the primitive.** A concept is a frame with typed
slots. `sale` requires seller, item, time. An unfilled slot is *visibly*
incomplete, so **completeness becomes computable** — filled/total, and
specifically *which* are missing. The author's framing: this is the mechanism
that lets you reason in complete or incomplete ways *while knowing how
complete*.

**(b) Closure over declared dependencies.** "Everything needed" is a transitive
closure over declared concept dependencies, not a top-k similarity result.
Retrievability becomes a property of closure operators rather than of indexes.
Partial machinery exists: a predicate lattice with subsumption/composition/
opposition, premise chains, an identity closure — three closure structures with
no unified "what does this query depend on" operation over them.

**(c) Demand paging, not prefetch.** You cannot predict what a chain of
reasoning needs, because the need is discovered mid-inference. So: reason until
something is unresolved, fetch, continue.

**(d) A fault is not a refusal — it is a fetch or an acquisition.** This is the
author's correction to an earlier framing and it may be the load-bearing idea.
Faults sort four ways:

    resolvable locally     -> fetch from the store
    resolvable externally  -> ACQUISITION GOAL (search, read, ask)
    genuinely unresolvable -> refusal
    cannot tell which      -> ?

Only the third is refusal. The second turns **open slots into a research
agenda**, typed by the slot that wants filling — which inverts ingestion from
push to pull. Instead of extracting everything and filtering, ingest what fills
an open slot. Given that blanket extraction has now failed twice with numbers,
that is a concrete policy change and not just a framing one.

## 3. The obvious objection, stated by the author rather than hidden

**This is frames and scripts.** Minsky, Schank, 1970s AI. They died on the
**knowledge-acquisition bottleneck**: someone had to author every frame by
hand, and the world has more frames than anyone can write.

The claim that something is different now is precisely (d) — faults generate
typed acquisition goals, and an LLM can fill them, so frames could be acquired
on demand rather than authored up front. **That is simultaneously the strongest
part of this proposal and the part most likely to be wrong**, and it deserves
attacking first.

A second, weaker prior: exp85 enumerated entity pairs and asked a model to fill
the relation or answer NONE — an accidental one-slot instantiation. It produced
the best precision of any arm (0.463). Single run, and later measurement showed
a 0.041 noise floor, so treat this as suggestive at most.

## 4. What to answer

1. **Is slot instantiation the right primitive**, or a familiar idea that
   already failed? If the acquisition bottleneck is genuinely dissolved by
   LLM-filled slots, say why. If it is not, say what it becomes instead.
2. **Attack the fault taxonomy.** Is "resolvable externally" separable from
   "unresolvable" *in practice*, or does the fourth case (cannot tell which)
   swallow both and make the distinction useless?
3. **What is the completeness guarantee actually worth?** Closure over
   *declared* dependencies is complete only relative to the declarations, and
   the gaps in declarations are invisible by construction. Is detectable
   incompleteness a real advance or a restatement of the frame problem?
4. **Prior art, honestly.** Name what this reinvents — description logics,
   truth maintenance, planning with open preconditions, semantic frames,
   FrameNet, neuro-symbolic retrieval, anything. Then say where the genuine
   white space is, or that there is none.
5. **The first experiment that could kill this**, buildable by one person on
   one consumer GPU in days rather than months. Prefer something that fails
   informatively over something that demonstrates the idea.
6. **What to abandon** from the eighteen-experiment extraction arc. Be
   specific: which artifacts, corpora, or components are sunk cost being
   carried forward out of habit?

Commit to positions. Disagreement between you is worth more than consensus, and
a specific falsifiable view that the others are unlikely to share is worth most.
