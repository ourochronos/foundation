I'll inspect the model implementation and prior review material so the critique is grounded in concrete break cases, not the document's framing.

/ Search (glob)
  │ "**/model*/**/*"
  └ 22 files found

/ Search (glob)
  │ "**/*model*v*"
  └ 3 files found

/ Search (glob)
  │ "**/data/model*/**/*"
  └ 12 files found

● List repo structure (shell)
  │ ls -la /home/zonk1024/projects/foundation && find /home/zonk1024/projects/foundation -maxdepth 4
  │ -type d | head -80
  └ 116 lines…

Reading the implementation and the full v2 doc next — not the other v2 reviews.

● Read canonical.py
  │ foundation/model/canonical.py
  └ 440 lines read

● Read 25-model-v2.md
  │ docs/25-model-v2.md
  └ 162 lines read

● Read conflict.py
  │ foundation/model/conflict.py
  └ 328 lines read

● Read identity.py
  │ foundation/model/identity.py
  └ 148 lines read

● Read predicates.py
  │ foundation/model/predicates.py
  └ 118 lines read

● Read __init__.py
  │ foundation/model/__init__.py
  └ 1 line read

Digging into tests and claim-act hashing next for concrete break cases.

● Read 23-model-v1.md
  │ docs/23-model-v1.md
  └ L1:100 (99 lines read)

/ Search (glob)
  │ "**/tests/**/*"
  └ 24 files found

/ Search (grep)
  │ "claim_act|claim_time|prop_ref|act_ref|event_address|definition_address|SCHEMA_VERSION" in
  │ **/*.{py,md}
  └ 12 files found

● Read 23-model-v1.md
  │ docs/23-model-v1.md
  └ L100:250 (151 lines read)

● Read test_canonical.py
  │ tests/test_canonical.py
  └ L1:200 (200 lines read)

● Count lines and search key symbols (shell)
  │ wc -l tests/test_*.py foundation/model/*.py; rg -n
  │ "prop_ref|act_ref|event_address|NONE|SOME|commit\(|definition|claim_act|mint_namespace" tests/
  │ foundation/model/ --type py | head -120
  └ 20 lines…

● Read test_canonical.py
  │ tests/test_canonical.py
  └ L200:414 (215 lines read)

● Read test_conflict.py
  │ tests/test_conflict.py
  └ L1:120 (120 lines read)

/ Search (grep)
  │ "prop_ref|fibre|fiber|act_ref|event_address|SCHEMA_VERSION|local:me" in **/*.{py,md}
  └ 11 files found

Checking how belief/`about` interacts with proposition keys — that looks like the break.

✗ Probe fatal flaw scenarios in model (shell)
  │ cd /home/zonk1024/projects/foundation && .venv/bin/python - <<'PY'
  │ from foundation.model.canonical import hexid, address, event_address, digest_of, ALGOS,
  │ SCHEMA_VERSION, NONE, SOME
  │ from foundation.model.conflict import Claim, conflicts, agreement, proposition_key
  │ from foundation.model.identity import Closure…
  └ Permission denied and could not request permission from user

✗ Probe break cases with system python (shell)
  │ cd /home/zonk1024/projects/foundation && python3 - <<'PY'
  │ from foundation.model.canonical import hexid, event_address, SCHEMA_VERSION, NONE, SOME
  │ from foundation.model.conflict import Claim, conflicts, proposition_key
  │ from foundation.model.identity import Closure
  │ import hashlib, json…
  └ Permission denied and could not request permission from user

✗ Locate working Python interpreter (shell)
  │ which python3; ls -la /home/zonk1024/projects/foundation/.venv/bin/python*; type python3;
  │ /usr/bin/python3 -c 'print(1)'
  └ Permission denied and could not request permission from user

● Test bash access (shell)
  │ echo hello && pwd
  └ 3 lines…

✗ Find python binaries (shell)
  │ ls /usr/bin/python* 2>/dev/null; ls /home/zonk1024/projects/foundation/.venv/bin/ | head;
  │ command -v python3; command -v python
  └ Permission denied and could not request permission from user

● List tests without python (shell)
  │ ls tests | head -5; head -1 foundation/model/conflict.py
  └ 7 lines…

## 1. Fatal flaw

**`prop_ref` does not dissolve the dilemma. It renames it and then lies about commitment.**

The doc says both of these:

- a `prop_ref` is stored as a **syntactic** content address (stable, commitment-grade);
- a belief on `prop_ref(Ha)` **covers `Hb`** once identity is accepted (fibre resolution).

Those cannot both be true of the same bytes.

Concrete case:

```
Store A:  Ha = addr(s.alice:p1, dob, 1907-05-22)
Store B:  Hb = addr(s.bob:p9,  dob, 1907-05-22)
both:     sameAs → wikidata:Q152

A:  (s.alice:me, believed, 0.9, +, {about: prop_ref(Ha)})
A:  (s.alice:me, believed, 0.2, +, {about: prop_ref(Hb)})
```

Under the shipped code:

- `proposition_key` only runs the closure on **entity** subjects/objects. A `prop_ref` is left as raw `Ha`/`Hb`.
- The test encoding puts the target in qualifier `about`, and `_tc` **drops every unregistered qualifier**, including `about`. So the target of the belief is not in the key at all.
- Grouping for conflict is `(canon(subject), predicate)` → both rows are `(s.alice:me, believed)` with objects `0.9` vs `0.2`. You either get a bogus functional conflict about the agent’s confidence number, or no “same proposition” conflict at all. You never get “two beliefs about one fibre.”

So the v1 break case the section claims to fix is still open, and the “commitment-grade prop_ref” story is false for the product goal (ZK / cross-store agreement on a proposition). A content address still cannot name a fibre; putting “the mutability in the reading” does not make `H(salt ‖ Ha)` a commitment to the fibre of `Hb`.

The principle in §0 is also wrong as a unifier: `local:`, n-ary role sets, and `claim_time` in act hashes are separate design errors. Treating them as one root cause is what licensed the non-fix of leaving fibre identity out of Layer 0 while still calling `prop_ref` commitment-grade.

---

## 2. What forces a CLOSED-layer change within a year

**Fix now: event identity is not domain-separated and is precision-fragile.**

`event_address` hashes bare JSON of type + key roles. It does **not** go through `digest_of` / `kind ‖ schema_version`. Every other address does. One encoding tweak later and every `event:` id in the wild is either ambiguous or requires a global rewrite — the failure §6 says is unfixable.

Worse, identity is over **canonical role values**, so precision splits the event:

```
identifying = (seller, item, time)
A: time = 2020        (year)
B: time = 2020-06-15  (day)
→ two event: ids for one sale
```

That is the original n-ary federation failure, back under a new name. Declaring “identifying roles” does not help if the values of those roles do not round-trip across extractors.

Also fix now, while addresses are free:

- **`(uri, null)` vs `(uri, def)`** never dedupe. One store versions predicates, the other uses bare URIs (explicitly allowed) → same SPO, two assertion addresses, forever. Either forbid bare URIs on the wire, or keep definition **out** of the assertion hash and bind it only via a separate typed edge.
- **`NONE` vs `¬SOME`**: `(s,p,NONE,+)` and `(s,p,SOME,−)` are the same claim in English and different addresses here; only `NONE` fights `(s,p,bob,+)`. Pick one encoding for empty extension and hard-alias the other in canonical form.

Accept later (do not pretend it is closed): a real **fibre id** if you insist beliefs/commitments target propositions. That is a new Layer-0 kind, not a reading rule. Prefer not to mint it until you know you need commitments over fibres rather than over acts.

---

## 3. Over-built — delete

**Salted commitments as a Layer-0 content kind.**  
`CONTENT_KINDS` includes `"commitment"`, and §5 argues salt destruction must be Layer 0. It must not. Commitments are an export/presentation crypto envelope. Baking them into the address kind set freezes a format you have not used. Deletion-by-salt-destruction also does not work as specified: if `content_addr = H(bytes)` **survives** so refs do not dangle, the private address is still dictionary-attackable against the shared seed vocabulary — the attack §5 opens with. If only `public_commit` survives, every `prop_ref`/`act_ref` to `content_addr` dangles. That contradiction means the feature is not ready to close; demote `commit()` to a library helper and drop `"commitment"` from the kind enum until a real public log exists.

Also delete or stop advertising: the claim that **act_ref / prop_ref** is a finished Layer-0 fix. You need at most one address sort (`ref`) plus a **required role** on the higher-order claim (`about_act` vs `about_prop`). Two sorts without a fibre key is ceremony.

---

## 4. The seven open questions

1. **Subsumption-blind conflict** — **Wrong as “open.”** `conflict.py` already has `_subsumption_conflicts` when a lattice is passed. What is open is wiring and defaults: if `lattice=None`, you silently regress. Make lattice mandatory for any store that has registered subsumptions, or always consult the registry (empty lattice = current behaviour).

2. **Derived scope** — **Intersection of step scopes is right; leave unspecified is wrong.** Ship it with composition or refuse to derive. Example: `mother_of@1980 ∘ parent_of@1990` must not yield `grandmother_of` with unrestricted validity.

3. **Lattice cycles** — **Reject at registration only** (code already does). Bounding at query time is how you ship a corrupt lattice and pay forever. Wrong to leave “or.”

4. **Merge quarantine / per-class conflict budgets** — **Yes; first merge feature, before any automatic `sameAs` accept.** Without it, one bad link × functional predicates detonates conflict volume. Not Layer 0 bytes; do not close merge without it.

5. **Claim acts never dedupe** — **Wrong as policy.** Distinct speech acts are real; wall-clock `claim_time` in the hash is not. Two extractors of the same sentence, or one act merged across nodes with clock skew, double forever. Hash `(assertion_id, claimant, mode, evidence_id)` and keep `claim_time` as a non-identifying field (or coarse bucket). “Stated cost” is not a design.

6. **`mode` open registry** — **Right. Do it.** Closed enum will migrate the first time someone needs `quotes` / `denies` / `corrects`.

7. **Qualifier registry; unknown ⇒ overlap** — **Right default.** Current code hardcodes five names and drops the rest (overlap-by-drop), with equality for place/assumption baked in. That is not a registry with `overlap_op`. Implement the registry; keep unknown ⇒ unrestricted; do not allow free-form qualifiers inside the assertion hash without registration (unregistered belongs on the act as annotation).

---

## 5. What breaks first at scale

**10⁶ assertions, one Postgres**

- `Closure.rep` scans **all** `_parent` members on every representative choice → effectively O(n) per `canonicalise`. At 10⁶ identity-touched refs, proposition-key work dies before SQL does.
- `conflicts` is O(|group|²) per `(subject_rep, predicate)`. High-degree keys (`member_of` on a country, `cites` on a paper) dominate. Functional + popular subject is quadratic CPU and quadratic conflict rows.
- `proposition_key` re-`json.dumps` on every call with no materialised column — CPU-bound interpretation layer thrashing on every merge/query.

What actually fails first: **identity-canonicalised conflict pass on a few hot predicates**, not raw row store size.

**Merge of two 10⁶ stores**

- Claim acts **strictly double** (by their own admission) → write amplification and index bloat on the first full mesh merge.
- Every foreign `sameAs` re-enters `Closure.accept` under local policy; then **global** recomputation of proposition keys and pairwise conflicts. No quarantine → one aggressive identity packet produces a conflict storm and poisons agreement counts.
- Assertion bodies mostly union; **interpretation** does not. Merge cost is closure + conflict, not `UNION` of immutable rows. The “merge is set union CRDT” story in `canonical.py`’s header is false for any store that uses `local`/store-scoped refs — i.e. the common case.

---

### Concrete alternative (fibre / belief)

Do not store beliefs as commitments to assertion hashes. Store:

```text
claim_act  := (assertion_addr, claimant, mode, evidence, claimed_at)   -- time NOT in id
belief     := (claimant, assertion_addr, value, dims…)                 -- points at ACT or ASSERTION
# at read/conflict time only:
fibre(A)   := proposition_key(assert(A), closure)   -- derived, Layer 4
conflict if claimant equal and fibre(A)=fibre(B) and belief values disagree
```

If you later need a commitable proposition id for ZK, add explicitly:

```text
fibre_commit := H("fibre" ‖ schema ‖ rep(s) ‖ p ‖ rep(o) ‖ n ‖ scope)
```

and accept that it is **invalidated/reissued** when closure moves — never pretend a frozen `prop_ref` to `Ha` is that object.


[stderr] 

Changes    +0 -0
Requests   1 Premium (3m 39s)
Tokens     ↑ 660.6k (594.8k cached) • ↓ 10.7k (5.6k reasoning)
Resume     copilot --resume=062aedb6-ca8f-4a1b-9069-f607d1e31939
