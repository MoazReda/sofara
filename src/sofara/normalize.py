"""Arabic name normalization for matching names across sources.

This is deterministic cleanup of *spelling noise* only — the same name
typed with/without hamza, ta marbuta vs ha, extra spaces, diacritics.
It never guesses that two *different* names are the same person;
that decision is made by a human in official_aliases.csv.

    >>> normalize_name("إبراهيم  نور الدين")
    'ابراهيم نور الدين'
    >>> normalize_name("محمد عطيّة") == normalize_name("محمد عطيه")
    True
    >>> normalize_name("شريف عبد الله") == normalize_name("شريف عبدالله")
    True
"""

from __future__ import annotations

import re
import unicodedata

# Arabic diacritics (tashkeel) + Quranic marks + tatweel
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")

_CHAR_MAP = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",  # alef variants -> bare alef
        "ة": "ه",  # ta marbuta -> ha
        "ى": "ي",  # alef maqsura -> ya
        "ؤ": "و",
        "ئ": "ي",
    }
)


def normalize_name(name: str) -> str:
    """Return a canonical matching key for an Arabic or Latin name."""
    if name is None:
        return ""
    text = unicodedata.normalize("NFKC", str(name))
    text = _DIACRITICS.sub("", text)
    text = text.translate(_CHAR_MAP)
    text = text.casefold()  # for Latin names: 'Osman' == 'OSMAN'
    text = re.sub(r"\s+", " ", text).strip()
    # compound-name prefixes are written both joined and split:
    # 'عبد الله' / 'عبدالله', 'ابو العطا' / 'ابوالعطا' -> always joined
    text = re.sub(r"(?<!\S)(عبد|ابو) (?=\S)", r"\1", text)
    return text
