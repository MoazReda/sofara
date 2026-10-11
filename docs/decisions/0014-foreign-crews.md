# 0014 — Foreign crews are recorded, but never analysed as Egyptian referees

**Context.** The Referees Committee sometimes brings a foreign crew for a
high-profile match (round 6 of 2026/27: a Slovenian crew for الزمالك ×
الأهلي). The project is about developing Egyptian refereeing, so a foreign
referee should not appear in anything that describes Egyptian referees. But
dropping the match would break the round (9 matches instead of 10), lose the
match with the most expert opinions, and hide a fact worth reporting: which
matches the committee hands to foreign crews.

**Decision.** Record the match and its crew like any other, with
`officials.nationality` set (empty means `Egypt`, the schema default; the
names are the EFA card's Arabic spelling). Cases from these matches stay in
the case library, because the Laws are the same and the cases teach the same
things. Every analysis of Egyptian referees (appointment assistant,
commendations, per-official summaries) filters on `nationality = 'Egypt'`.

**Consequences.** `sofara-report` counts foreign officials and the matches
they worked. Part C can ask whether experts judge foreign and Egyptian
referees by the same standard. Any new per-official query must include the
filter; a test should cover it when such a query is added.
