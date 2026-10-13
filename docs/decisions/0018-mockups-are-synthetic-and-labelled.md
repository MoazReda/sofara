# 0018 — Part D mockups are synthetic, invented and labelled everywhere

**Context.** Part D shows the committee what its unpublished data (assessor
reports, VAR-room logs, appointment history) would let us build: a referee's
progress over a season, an appointment assistant, VAR review times. We have
none of that data, and the brief allows synthetic data only as clearly
labelled mockups.

**Decision.** `mockups.py` generates the data from a fixed seed, so the page is
identical on every build. Every name is invented (الحكم أ…و, فريق س…ر); a test
fails if any real referee or team name appears. The tab opens with a permanent
banner saying the data is synthetic, every chart carries an "مثال توضيحي"
stamp, and each mockup ends with the exact data it would need. The
appointment assistant explains each exclusion and says the decision stays
with the committee; the progress view is framed as development, not ranking.

**Consequences.** The demo can show the pitch without implying anything about
real people. When real data arrives, each mockup's "needs" line is the data
request, and the synthetic generator is replaced, not edited.
