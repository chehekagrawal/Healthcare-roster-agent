"""
src/tools/states.py
===================
Finds which market a question is about.

The old code did `if "CA" in query.upper()`, so "root cause for FL" matched
the "CA" inside "CAUSE" and traced California, and only 6 states were known.
This module matches whole words only, knows every market in the data, accepts
full state names ("Georgia"), and treats codes that are also English words
("in", "me", "oh", "co", "la") as states only when typed in capitals.
"""

import re
from typing import Iterable, Optional

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "WNY": "Western New York", "NATIONAL": "National",
}

# Codes that are also ordinary English words: only accepted when typed in capitals.
AMBIGUOUS_CODES = {"IN", "ME", "OH", "CO", "LA", "OK", "OR", "HI", "ID", "PA", "MA", "DE", "AL", "NATIONAL"}


def detect_state(query: str, known_states: Iterable[str]) -> Optional[str]:
    """
    Returns the market code a question refers to, or None.
    Full names win over codes, and longer names over shorter ones
    ("West Virginia" before "Virginia", "Western New York" before "New York").
    """
    if not query:
        return None
    known = {s.upper() for s in known_states}

    # 1. Full state names, longest first, case-insensitive.
    names = sorted(((code, STATE_NAMES[code]) for code in known if code in STATE_NAMES),
                   key=lambda cn: len(cn[1]), reverse=True)
    for code, name in names:
        if code == "NATIONAL":
            continue
        if re.search(rf"\b{re.escape(name)}\b", query, flags=re.IGNORECASE):
            return code

    # 2. Codes as whole words. Unambiguous codes match in any case ("ga", "GA");
    #    ambiguous ones only as typed in capitals ("IN" yes, "in" no).
    for code in sorted(known, key=len, reverse=True):
        flags = 0 if code in AMBIGUOUS_CODES else re.IGNORECASE
        if re.search(rf"\b{re.escape(code)}\b", query, flags=flags):
            return code

    # 3. "nationally" / "national" in lower case means the national market.
    if "NATIONAL" in known and re.search(r"\bnational(ly)?\b", query, flags=re.IGNORECASE):
        return "NATIONAL"
    return None
