# Data sources

Every row in `data/raw/` carries its source. This page lists the sources, how
they are used, and what they are not.

| Data | Source | How collected | Notes |
|---|---|---|---|
| Match crews (referee, assistants, 4th, VAR, AVAR) | EFA official Facebook crew cards, one post per round | By hand from screenshots; names verified by Moaz | Round 1 post: https://www.facebook.com/photo/?fbid=1089370470111912. Saturday matches of round 1 from Akhbar El Yom text. Post links for rounds 2–5 still to add. |
| Full legal names of one crew | EFA referee match report (Al Ahly × Sharqia ENPPI, R1), as published by Cairo24 | Read by hand | Used for aliases only. The image is not republished. |
| Key Match Incidents | Press articles (إرم نيوز، الوطن، الكابتن، كل الكورة، الدستور) | Read in full, checked against our match/referee/score data before entry | 3 articles rejected because they described other seasons or rounds. |
| Key Match Incidents + opinions | Nasser Abbas (former international referee, CAF referee assessor): https://www.facebook.com/nasserabbas.abbas | Notes taken by Moaz from his videos and posts | Covers matches the press ignores. |
| Expert commendations | Nasser Abbas's "best of the round" posts (rounds 1, 2, 4) | Copied by Moaz from his page | Reasons summarised; post links still to add. |
| Match reviews | Nasser Abbas's per-match review reels (13 matches, rounds 1–5) | Links collected by Moaz from his public Facebook profile | Links only; one row per match per source. |
| Official rulings | Referees Committee round videos on the EFA Facebook page — R1 https://www.facebook.com/reel/1561638358556934, R2 https://www.facebook.com/reel/1287410006693633, R3 https://www.facebook.com/reel/1698670264551381, R4 https://www.facebook.com/reel/2024526304868493, R5 https://www.facebook.com/reel/1039780975731497 | Links found by Moaz; verdicts read from press reports, confirmed by Moaz watching the videos | [Decision 0015](decisions/0015-committee-round-videos-are-rulings.md). |
| Committee positions (second-hand) | النهار المصري, 2026-09-20 — summary of the committee's analysis of rounds 1–4 | Used to read the round videos; describes cases 40–42 | It calls السويس بتروجيت "منتخب السويس"; matched by round and incident. |
| EFA referee lists | efa.com.eg → لجنة الحكام الرئيسة (main committee, international list, first-degree referees) | Copied by Moaz from the page, 2026-10-13 | The first-degree page is labelled 2025-2026; Egyptian referees missing from it are listed by `sofara-report`. |
| Expert opinions | The articles and posts above | Summarised in our own words | Never the article text. |
| Law changes | IFAB / FIFA media releases | Linked where used | e.g. VAR review of red cards from a clearly incorrect second yellow (28 Feb 2026). |

**Not used, on purpose:** automated scraping of any site (Facebook, Sofascore,
Flashscore); synthetic data for analysis; the committee's confidential
assessor reports (not public).

**Copyright:** EFA images and articles are not stored in this repository. We
store facts (who, when, what) with a link to the source, and summaries in our
own words.
