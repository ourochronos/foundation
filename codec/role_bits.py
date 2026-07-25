"""Role-bits side channel (D17, symbolic finish for the binding residue).

Extracts WHO-did-WHAT-to-WHOM slots from a dependency parse, normalized so
meaning-preserving reorders don't move it:

  voice      passive nsubjpass -> patient, by-pobj -> agent
  cleft      "It was X that V'd Y" / "What S V'd was X": re-root at the
             clause verb, substitute the focus for the relativizer
  nominal    "S's V-ing of O occurred ..." / "There was a V-ing of O by S":
             re-root at the event noun — poss/by -> agent, of -> patient
  agent      nsubj (active)  |  by-phrase pobj (passive/nominal)
  patient    dobj (active)   |  nsubjpass (passive) | of-pobj (nominal)
  recipient  dative, or to/for pobj
  clauses    (marker, verb-lemma, subject) fingerprint per adverbial clause,
             position-invariant -> clause_reorder matches, causal_reverse doesn't
  tense      lemma-based will/shall detection (contraction-proof: wo/'ll)

Predicate identity is deliberately NOT compared (synonym pairs change verbs);
only bindings are. Known limitation: converse-predicate paraphrases ("A sold
to B" / "B bought from A") legitimately flag as role-different.

Comparison: role_sim in [0,1] over slots present in either side; 1.0 when no
slots extracted (no claim -> defer to the s-channel via min-combination).
"""

from __future__ import annotations

_NLP = None

_LIGHT = {"occur", "happen", "come", "take", "be"}      # event-nominal carriers
_RELATIVIZERS = {"that", "which", "who", "whom", "what"}
_HEDGE_MODALS = {"may", "might", "could"}               # epistemic modals
_HEDGE_ADVS = {"reportedly", "allegedly", "possibly", "apparently",
               "supposedly", "perhaps", "probably", "presumably",
               "seemingly", "arguably", "purportedly"}
_HEDGE_ACOMPS = {"possible", "likely", "probable", "unclear", "uncertain",
                 "unconfirmed"}
_RAISING = {"appear", "seem", "tend", "happen"}         # X appears to V ...


def _nlp():
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load("en_core_web_sm", disable=["ner"])
    return _NLP


def _head_text(tok) -> str:
    return tok.text.lower().strip(".,;:!?'\"")


def _tense_of(verb, bits: dict) -> None:
    """Finite tense of the clause: will/shall -> future, else the FIRST tensed
    auxiliary (English marks finite tense on the leftmost aux — "is delivered"
    is present although the participle's morph says Past), else root morph."""
    will = any(c.lemma_.lower() in ("will", "shall") and c.dep_ == "aux"
               for c in verb.children)
    if will:
        bits["tense"] = "future"
        return
    aux = next((c for c in verb.children if c.dep_ in ("aux", "auxpass")
                and c.morph.get("Tense")), None)
    if aux is not None:
        bits["tense"] = aux.morph.get("Tense")[0].lower()
        return
    morph_tense = verb.morph.get("Tense")
    if morph_tense:
        bits["tense"] = morph_tense[0].lower()


def _hedge_of(verb, doc, bits: dict) -> None:
    """Marked epistemic feature — symbolic, like tense (hedging changes claim
    force, not bindings, so no continuous channel is positioned to catch it)."""
    modal = any(c.dep_ == "aux" and c.lemma_.lower() in _HEDGE_MODALS
                for c in verb.children)
    adv = any(t.dep_ == "advmod" and t.lemma_.lower() in _HEDGE_ADVS for t in doc)
    acomp = (verb.lemma_.lower() == "be" and
             any(c.dep_ == "acomp" and c.lemma_.lower() in _HEDGE_ACOMPS
                 for c in verb.children))
    if modal or adv or acomp:       # set only when marked — absence is the
        bits["hedge"] = "1"         # unmarked default, not a separate claim


def _slots_from_verb(verb) -> dict:
    """agent/patient/recipient + clause fingerprints + tense from a verbal head."""
    bits: dict[str, str] = {}
    kids = {c.dep_: c for c in verb.children}
    passive = "nsubjpass" in kids or "auxpass" in kids

    if passive:
        if "nsubjpass" in kids:
            bits["patient"] = _head_text(kids["nsubjpass"])
        ag = kids.get("agent")
        if ag is not None:
            pobj = next((c for c in ag.children if c.dep_ == "pobj"), None)
            if pobj is not None:
                bits["agent"] = _head_text(pobj)
    else:
        if "nsubj" in kids:
            bits["agent"] = _head_text(kids["nsubj"])
        if "dobj" in kids:
            bits["patient"] = _head_text(kids["dobj"])

    if "dative" in kids:
        d = kids["dative"]
        tgt = next((c for c in d.children if c.dep_ == "pobj"), d)
        bits["recipient"] = _head_text(tgt)
    else:
        # the to/for phrase attaches to the DIRECT OBJECT at least as often as
        # to the verb ("audited 40 accounts for Trenton Bank" hangs `for` off
        # `accounts`), so both hosts have to be searched
        hosts = [verb] + ([kids["dobj"]] if "dobj" in kids else [])
        for host in hosts:
            for prep in (c for c in host.children if c.dep_ == "prep"
                         and c.text.lower() in ("to", "for")):
                pobj = next((c for c in prep.children if c.dep_ == "pobj"), None)
                if pobj is not None:
                    bits["recipient"] = _head_text(pobj)
                    break
            if "recipient" in bits:
                break

    # adverbial-clause fingerprints, keyed by their marker (because/after/...).
    # Value = the clause SUBJECT only — clause verb lemmas are predicate
    # identity, which this channel deliberately does not compare (synonym and
    # register rewrites rename verbs); causal_reverse still separates because
    # its clause subjects swap sides.
    for adv in (c for c in verb.children if c.dep_ == "advcl"):
        mark = next((c for c in adv.children if c.dep_ in ("mark", "advmod")), None)
        subj = next((c for c in adv.children
                     if c.dep_ in ("nsubj", "nsubjpass")), None)
        key = f"clause:{mark.text.lower() if mark is not None else 'sub'}"
        bits[key] = _head_text(subj) if subj is not None else ""

    _tense_of(verb, bits)
    return bits


def _cleft_reroot(root):
    """(clause_verb, focus_tok|None) for it-clefts and pseudo-clefts, else None.

    acomp frames ("It is possible that ...") are hedges, not clefts — the
    embedded roles ARE unchanged there, but re-rooting is reserved for
    constructions whose only function is focus movement.
    """
    if root.lemma_.lower() != "be":
        return None
    kids = {c.dep_: c for c in root.children}
    if "acomp" in kids:
        return None
    nsubj = kids.get("nsubj") or kids.get("expl")
    attr = kids.get("attr")
    if "csubj" in kids and attr is not None:            # pseudo-cleft
        return kids["csubj"], attr
    if nsubj is not None and nsubj.lemma_.lower() == "it":
        if attr is not None:                            # it-cleft on a nominal
            # the relcl can attach anywhere inside the focus phrase
            rel = next((t for t in attr.subtree
                        if t.dep_ in ("relcl", "acl") and t is not attr), None)
            if rel is not None:
                return rel, attr
        for dep in ("ccomp", "advcl", "relcl"):         # clause hung off the root
            cl = kids.get(dep)
            if cl is None:
                continue
            marked = any(m.dep_ == "mark" and m.text.lower() == "that"
                         for m in cl.children)
            rel_subj = any(c.dep_ in ("nsubj", "dobj")
                           and c.lemma_.lower() in _RELATIVIZERS
                           for c in cl.children)
            if marked or rel_subj:
                return cl, attr
    return None


def _raising_reroot(root):
    """(content_verb, matrix_subject) for "X appears to V ...", else None.

    The raising verb carries the hedge; the bindings live in its xcomp, and the
    surface subject is the embedded verb's subject.
    """
    if root.lemma_.lower() not in _RAISING:
        return None
    kids = {c.dep_: c for c in root.children}
    xcomp = kids.get("xcomp")
    if xcomp is None:
        return None
    return xcomp, kids.get("nsubj")


def _nominal_reroot(root):
    """The event noun for light-verb nominal frames, else None."""
    if root.lemma_.lower() not in _LIGHT:
        return None
    kids = {c.dep_: c for c in root.children}
    n = kids.get("nsubj") or kids.get("attr")
    if n is not None and any(c.dep_ == "prep" and c.text.lower() == "of"
                             for c in n.children):
        return n
    return None


def extract(text: str) -> dict:
    doc = _nlp()(text)
    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if root is None:
        return {}

    raising = _raising_reroot(root)
    if raising is not None:
        verb, subj = raising
        bits = _slots_from_verb(verb)
        if subj is not None and "agent" not in bits:
            bits["agent"] = _head_text(subj)
        _tense_of(root, bits)              # tense is on the matrix verb
        _hedge_of(root, doc, bits)
        bits["hedge"] = "1"
        return bits

    cleft = _cleft_reroot(root)
    if cleft is not None:
        verb, focus = cleft
        bits = _slots_from_verb(verb)
        ftext = _head_text(focus) if focus is not None else None
        for k in ("agent", "patient", "recipient"):
            if bits.get(k) in _RELATIVIZERS:
                if ftext:
                    bits[k] = ftext
                else:
                    bits.pop(k)
        if ftext and "patient" not in bits and bits.get("agent") != ftext:
            bits["patient"] = ftext
        _hedge_of(verb, doc, bits)
        return bits

    nom = _nominal_reroot(root)
    if nom is not None:
        bits = {}
        poss = next((c for c in nom.children if c.dep_ == "poss"), None)
        if poss is not None:
            bits["agent"] = _head_text(poss)
        holders = [nom, root]
        for holder in holders:
            for prep in (c for c in holder.children if c.dep_ == "prep"):
                pobj = next((c for c in prep.children if c.dep_ == "pobj"), None)
                if pobj is None:
                    continue
                p = prep.text.lower()
                if p == "of" and "patient" not in bits:
                    bits["patient"] = _head_text(pobj)
                    holders.append(pobj)      # by/to often hang under the object
                elif p == "by" and "agent" not in bits:
                    bits["agent"] = _head_text(pobj)
                elif p in ("to", "for") and "recipient" not in bits:
                    bits["recipient"] = _head_text(pobj)
        _tense_of(root, bits)
        _hedge_of(root, doc, bits)
        return bits

    bits = _slots_from_verb(root)
    _hedge_of(root, doc, bits)
    return bits


def _words(s: str) -> set[str]:
    """Alphabetic word set, punctuation-stripped.

    Stripping matters: without it a sentence-final filler ("... in Trenton.")
    tokenizes as "trenton." and fails isalpha(), so the slot silently drops out
    of the comparability gate — and sentence-final patients/recipients are the
    common case.
    """
    out = set()
    for w in s.lower().replace("|", " ").split():
        w = w.strip(".,;:!?'\"()[]")
        if w.isalpha():
            out.add(w)
    return out


def role_sim(a: dict, b: dict, x_text: str = "", y_text: str = "") -> float:
    """Compare only slots whose filler words survive in BOTH texts — if a slot's
    words were renamed (register shift, synonymy), the parse heads are not
    comparable and the slot makes no claim. Tense is comparable whenever BOTH
    sides extracted one (a missing tense is a parse failure, not a claim of
    tenselessness). 1.0 when nothing is comparable (defer to the s-channel)."""
    xw, yw = _words(x_text), _words(y_text)

    def comparable(k) -> bool:
        if k == "hedge":
            return True
        if k == "tense":
            return "tense" in a and "tense" in b
        if not x_text:
            return True
        va, vb = a.get(k), b.get(k)
        wa = _words(va) if va else set()
        wb = _words(vb) if vb else set()
        return bool((wa and wa & yw) or (wb and wb & xw))

    keys = [k for k in (set(a) | set(b)) if comparable(k)]
    if not keys:
        return 1.0
    return sum(a.get(k) == b.get(k) for k in keys) / len(keys)
