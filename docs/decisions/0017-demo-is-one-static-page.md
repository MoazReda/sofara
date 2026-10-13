# 0017 — The demo is one static Arabic page, with search checked against Python

**Context.** The committee demo is 15 minutes in a meeting room whose network
we don't control, and the same page should live on as the portfolio's front
door. A server (Streamlit, Flask) would need hosting and a connection, and
would add dependencies to a package that uses only the standard library.

**Decision.** `sofara-site` writes one self-contained HTML file: Arabic,
right-to-left, light and dark, with the data embedded as JSON. It has three
tabs: the case library with search and filters, where experts disagree, and
how the data was made. The search must answer like `sofara-search`, so Python
precomputes, for every vocabulary term, which cases it hits (on a field or
only in the text); `site/search.js` reads the query with the same rules
(normalization, clitics, names as filters, longest term first, AND across
kinds, OR within a kind). A test runs the JavaScript under Node on every gold
query and requires the same cases as Python.

**Consequences.** The page opens from a USB stick, from GitHub Pages, or as a
shared link, with nothing to install. It is rebuilt from `data/raw` like the
database and is not committed (`site/` is git-ignored). Changing the search
rules means changing both files; the parity test fails until they agree.
