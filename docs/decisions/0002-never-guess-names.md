# 0002 — Names are normalized but never guessed

**Context.** The same official is written many ways ("محمود ناجي" /
"محمود احمد ناجي", "هشام القاضي" on the crew card is "هشام اشرف فتحي احمد"
in the referee report). Round 1 alone had 9 pairs of similar-looking names
that were different people ("محمد مجدي الشيخ" / "محمد مجدي سليمان"). A wrong
merge silently corrupts every later statistic.

**Decision.** Normalization removes spelling noise only: alef/hamza forms,
ة/ه, ى/ي, diacritics, extra spaces, and the space after عبد/أبو. Anything
else is a human decision recorded in `official_aliases.csv` with its
evidence (e.g. "same match, same role in two EFA documents"). Unknown names
stop the build. No fuzzy matching.

**Consequences.** Some manual work per round. In exchange, "أحمد جمال" and
"أحمد جمال شاهين" were proven different (both officiated on 2026-09-07), and
no merge has ever needed undoing. One known issue is documented rather than
guessed: "محمد الشناوي" (see README).
