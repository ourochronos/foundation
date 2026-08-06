Here are my direct answers to the brief. I am assuming the role of a reviewer who has seen this failure mode before and has zero patience for hedging.

### 1. Is slot instantiation the right primitive?
**No. The bottleneck does not dissolve; it shifts from authoring to ontological alignment.**
If you pre-author the frames, you are back in 1970 and the knowledge-acquisition bottleneck remains exactly where Minsky left it. If you let the LLM generate the frames and slots on the fly to bypass the authoring bottleneck, it will generate a `sale` frame with `seller` for Document A, a `transaction` frame with `vendor` for Document B, and an `exchange` frame with `merchant` for Document C. 

The moment you rely on LLMs to fill open slots, you realize LLMs are highly sensitive to the surface syntax of the prompt and the source text. You will not get clean, aligning schema keys. You will get an explosive proliferation of nearly-identical slots that never close. Slot instantiation only works if the ontology is rigid, and if the ontology is rigid, LLMs cannot save you from the authoring bottleneck.

### 2. Attack the fault taxonomy.
**The taxonomy is epistemologically broken.** 
"Resolvable externally" is not a state you can identify *a priori*; it is an empirical outcome. You cannot know if a missing slot is resolvable externally until you actually execute the external search and fail to find it. Therefore, the fourth category ("cannot tell which") entirely swallows the second ("resolvable externally") and third ("unresolvable"). 

The real taxonomy of faults is purely operational:
1. **Local Hit** (in cache)
2. **Cache Miss** (triggers an external fetch agenda)
3. **Search Exhausted** (the fetch failed, so it becomes a refusal)

You do not categorize the fault before the fetch; the fault *is* the fetch trigger. Stop trying to classify the unknown before observing it.

### 3. What is the completeness guarantee actually worth?
**It is a hazard, and worse than having no guarantee at all.**
Closure over declared dependencies is a restatement of the Frame Problem, masquerading as a mathematical guarantee. It gives you computable confidence that you have exhaustively mapped a 3-dimensional schema onto a 12-dimensional reality. 

If your `sale` frame declares three slots (seller, item, time), and you fill them, your system registers as "complete" and stops reasoning. But if the real-world text hinges on a fourth, undeclared variable (e.g., currency, jurisdiction, or condition of goods), your system is confidently, mathematically wrong. A completeness metric based on a bounded schema actively discourages the system from noticing when the schema itself is inadequate. 

### 4. Prior art and the white space
You are reinventing:
* **The Open World Assumption in Description Logics (OWL/DL):** specifically, the idea that missing information is not false, but unknown, triggering a derivation or fetch.
* **Backward Chaining in Prolog/Datalog:** reasoning backward from a goal (the open slot) to sub-goals (external fetches).
* **CYC:** Doug Lenat's 40-year nightmare of manually building predicate lattices and frames.

**The actual white space:** Ephemeral, query-scoped micro-ontologies. Do not build a persistent global graph of frames. The white space is using the LLM to generate a rigid, formal schema *specifically tailored to the immediate user query*, compiling the text into that exact schema to answer the question, and then **throwing the schema away** when the reasoning chain is done. No persistent store, no global ontology alignment. 

### 5. The killer experiment (falsifiable in 48 hours)
**The Schema Drift Stress Test.**
Take 100 complex entities or events. Write two short, distinct texts for each: one in academic passive voice, one in punchy news style. Both texts contain the exact same factual payload. 

Prompt the LLM: *"Define a formal frame with slots to capture the information in this text, then fill the slots."* 

Run this for all 200 texts. 
**The metric:** Measure the exact string overlap (Intersection over Union) of the slot *keys* (not values) generated for Text A vs Text B of the same event.
**The kill threshold:** If the exact key overlap is less than 0.85, the project is dead. It proves that the LLM's frame generation is entangled with the surface syntax of the text. If the keys don't align perfectly, your "closure over declared dependencies" shatters, because the graph will never connect.

### 6. What to abandon
Execute a brutal purge of the 18-experiment arc. Specifically:
1. **The predicate lattice:** Throw it out. You noted that three vocabularies must close simultaneously and failing one yields zero. A global predicate lattice is a brittle monolith that will drag down your demand-paging. 
2. **The "Claim Store":** Abandon the concept of a passive, persistent global index entirely. If you are moving to demand-paging, state is a liability. 
3. **The four discourse corpora:** Drop them. They already proved they don't corroborate (papers cite rather than repeat). Stop carrying them forward out of habit; they are the wrong testing ground for on-demand reasoning. 
4. **Any code relying on REBEL or hybrid filtering:** Burn it. The 0.155–0.266 recall ceiling is a terminal diagnosis for these methods. Cut the cord.


[stderr] 

Changes    +0 -0
Requests   1 Premium (28s)
Tokens     ↑ 21.8k • ↓ 1.2k (1.7k reasoning)
Resume     copilot --resume=4019c1de-13a9-4334-b6a4-f0ac6ac532ae
