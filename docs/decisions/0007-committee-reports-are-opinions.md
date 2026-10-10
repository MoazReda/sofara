# 0007 — Committee positions reported by the press are opinions

**Context.** Articles say "the committee clarified…" or quote "a source in the
committee", but publish no statement. Treating that as an official ruling
would let a newspaper's paraphrase decide a verdict.

**Decision.** An `official` stage needs a published statement with a link.
Press-reported committee positions are stored as expert opinions under two
distinct names: "لجنة الحكام (بحسب الصحافة)" (`committee`) and
"مصدر بلجنة الحكام (غير مسمى)" (`committee_source`).

**Consequences.** Cases stay "controversial" until a real statement exists,
but the committee's reported view is kept and can be analysed separately.
