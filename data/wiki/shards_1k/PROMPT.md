# 1k-tranche extraction instructions (shared by all shard agents)

Input: your assigned shard file `in_K.json` — a JSON array of 13 Wikipedia
pages {title, revid, text}.

Extract SELF-CONTAINED factual statements with Wikidata-property
assignments. Per page: 10-20 statements covering the lead's main facts;
bio-fact priority for person pages (birth/death dates & places, education,
employers, citizenship, awards, notable works, spouse, positions).

Schema inventory (assign pid ONLY from this list; use null when none fits):
P569 birth date · P570 death date · P19 birthplace · P20 deathplace ·
P26 spouse · P27 citizenship · P69 educated at · P106 occupation ·
P108 employer · P166 award received · P800 notable work · P50 author
(person subject, titled work object) · P31 instance of · P937 work
location · P39 position held · P463 member of · P184 doctoral advisor ·
P185 doctoral student · P551 residence · P571 inception (thing-created
subject) · P112 founded by (org subject) · P127 owned by (org subject) ·
P123 publisher · P138 named after · P159 headquarters · P276 location ·
P170 creator · P36 capital · P17 country · P131 located in admin entity

PRECISION RULES (obey strictly):
1. P50/P800 objects must be TITLED artifacts (books, named theorems,
   papers) — concepts/fields are NOT works.
2. P571 binds to the thing CREATED ("Hilbert presented the problems in
   1900" is NOT P571 on Hilbert).
3. "lived/flourished c. X" is NOT a birth date.
4. P112/P127 take the ORGANIZATION as subject (never person-subject
   founder claims).
5. Objects are entities, dates, or numbers — never descriptive phrases,
   roles, qualities, or quotations.
6. ASSERT-NOT-INFER: P31/P106 only when the text asserts the class
   ("X is a mathematician"), never merely implies it.

Each statement is one self-contained sentence naming its subject
explicitly (no pronouns). subject = the entity the fact is about.

Compose ALL rows first, then ONE Write call to your assigned `out_K.jsonl`
— one JSON object per line:
{"page": <title>, "revid": <revid>, "subject": ..., "pid": <"P..."|null>,
 "object": ..., "statement": ...}

Final text: just "done: N statements, M pages".
