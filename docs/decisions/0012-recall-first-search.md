# 0012 — Search is recall-first and explains every match

**Context.** The search is for a referee instructor preparing a lecture or a
video test: "every studs-up challenge", "every penalty VAR overturned". For
that user, a missed case is worse than an extra one. A first version also
showed that a single word is not enough: "بلنتي" missed cases whose text said
"ركلة جزاء".

**Decision.** Everyday terms live in `data/vocab/terms.csv` (term → field →
value), editable without code. A term matches a case if its field matches at
any stage (on-field, after VAR, official) **or** any synonym of it appears in
the case text (description + expert summaries), with Arabic clitics allowed
(بـ، الـ، ـه). Terms of one kind are OR-ed, different kinds AND-ed; team and
referee names become filters. Terms that describe *how* something happened
("استارز") are text-only, so they never match a broad field like a card
reason. Field matches rank above text matches, and every result lists why it
matched. A gold set of queries in `tests/test_search.py` guards recall.

**Consequences.** "بلنتي" returns penalties given first, then refused claims —
what an instructor wants. Some extra results are expected and visible. A
semantic (embedding) layer can be added later on top of this, measured
against the same gold set.
