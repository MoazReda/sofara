# 0016 — How expert agreement is measured, and what it never claims

**Context.** Part ج asks how far experts agree with each other and with the
committee. The library has 52 opinions, but 29 of them are Nasser Abbas's and
only 8 cases have two or more. Moaz's first idea, agree ÷ disagree, divides by
zero when everyone agrees and gives different numbers for 4–3 and 3–4. And two
opinions that split 1–1 look exactly as "controversial" as twenty that split
10–10. Experts are also not independent: two pundits on the same channel, or
with the same club leaning, can agree for the same wrong reason.

**Decision.**
- **Split score** = 2 × minority ÷ n (0 = all agree, 1 = even split). It is
  symmetric and never divides by zero.
- Every share is shown with its **95% Wilson range**, so a 1–1 split reads
  "between 10% and 90%", which honestly means "we can't tell".
- **Labels:** fewer than 3 opinions → `small_sample` (no claim); minority of a
  third or more → `contested`; otherwise `consensus`.
- Only **independent experts** count. The committee's own view is the
  official ruling and is compared separately; unnamed committee sources are
  left out; `unclear` opinions count for neither side.
- **What a disagreement is about** comes from the grounds each expert cites
  (`opinion_reasons`, coded into `reason_codes`, each with a kind: fact,
  threshold, law, var, process, consistency). An opinion whose grounds are only
  about the card is compared with the committee's `card_verdict`, any other
  with its `call_verdict`.
- Expert-vs-committee is reported as **agreement, never accuracy** (the
  committee can be wrong), with its n, and as a rate only from 10 ruled cases.
  Experts are listed by name, never ranked.

**Consequences.** Today only two cases carry a real label (1 and 34, both
contested) and only one expert has a rate. The numbers grow with the library;
the rules do not move with them. Coding the grounds is a judgement made from
our own summaries, so `opinion_reasons.csv` is reviewable line by line.
