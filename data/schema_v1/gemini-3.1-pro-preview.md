Here is a definitive, unsoftened review of the extraction schema. 

### 1. Which field will we regret?
**You will regret `attribution.mode` ("asserts|reports|infers|predicts").** It forces annotators to make deep epistemic judgments about the author’s state of mind. Inter-annotator agreement (IAA) will be abysmal, and the downstream routing value is near zero because a 1.5B model will learn to guess the base rate (likely "asserts") rather than actual semantics.

**Annotation cost per unit of value (Worst to Best):**
1. `flags` (Unstructured dumping ground; high cognitive cost, zero programmatic value)
2. `attribution.mode` (Subjective, kills IAA)
3. `scope.under_assumption` (Open-ended string extraction is difficult to align)
4. `link_confidence` (Subjective but fast)
5. `evidence_span` (Tedious but objective)
6. `link_proposal` (High value)
7. `polarity` (High value, objective)
8. `entities` & `claims` (Core payload)

### 2. What is missing that forces a schema change?
**Reification (Claims as Objects).** 
Your schema strictly enforces `object: entity | literal | marker`. It cannot represent *"The UN reports that [climate change causes famine]"*. If you flatten this, you lose the graph structure entirely. If you add it later by allowing `object: {"claim_id": "c1"}`, you invalidate the entire existing dataset because annotators previously had to hack around it.

### 3. Attribution vs Claimant (§3)
**"Keynesians hold that X" is the Claimant (Attribution).** 
The test for annotation is **epistemic responsibility**. 
* If the sentence establishes a boundary within which the author asserts the claim is true ("Under Keynesian economics, X"), it is `scope`.
* If the sentence shifts the responsibility for the truth of the claim to a third party ("Keynesians hold X"), it is `attribution.holder`. 

Do not mix them. World-states are scope; belief-states are attribution.

### 4. Is "bundle inference, decompose output" sound?
**No. It is a hallucination cascade.**
Scoring fields "separately" is a statistical illusion. The JSON is a dependency graph. If the model hallucinates or truncates `e1` in the `entities` array, every claim relying on `"subject": "e1"` becomes structurally unscorable. Joint objectives on complex JSON cause 1.5B models to suffer from early-token commitment errors; a bad entity boundary ruins the downstream claim extraction.

### 5. Steelman not doing this
**The baseline was rigged.** You dismissed LLMs based on an *unoptimized, first-draft prompt* on a 12B model. Polarity, scope, and attribution are pragmatic reasoning tasks, not syntactic ones. A 3B fine-tune will memorize syntax; a state-of-the-art LLM (Claude 3.5 Sonnet / GPT-4o) with a heavily engineered 15-shot prompt will crush it on pragmatics.
* **The test:** Hand-annotate 200 complex cases (negation, nested scope). Spend 4 hours optimizing a prompt for a frontier model. If the API beats the fine-tune's F1, abandon the 1.5B fine-tune. Sunk cost is zero.

### 6. What is the smallest schema that works?
**Cut `flags`, `attribution.mode`, `link_confidence`, and all of `scope` except a boolean `is_qualified: true/false`.**
* **What breaks:** You lose the ability to write SQL-like queries for specific spatiotemporal overlaps. 
* **Why it works:** You triple your annotation speed. If a claim has `is_qualified: true`, the downstream system relies on the `evidence_span` for a retrieval-augmented agent to read the exact conditions. Do not make human annotators extract boundary strings for `valid_time`.


[stderr] 

Changes    +0 -0
Requests   1 Premium (32s)
Tokens     ↑ 21.0k • ↓ 896 (2.4k reasoning)
Resume     copilot --resume=ea9a3637-73b1-4820-8e14-cc8272a5f1f1
