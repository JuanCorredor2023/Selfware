"""
api/_mock_para.py -- Person 4's TEMPORARY mock of the PARA tree.

The real PARA index belongs to Person 2. The endpoints in api/app.py
(/para, /projects, /areas, /resources, /archive) serve this data in the
shape the real index should eventually provide, so the dashboard can be
wired now. Mirrors web/src/mocks/para.js.

Item shape: {id, name, email_count, last_activity, status?}
`status` ("active" / "inactive") only exists for Projects.
"""

from __future__ import annotations

# Order matters: it is the order the dashboard shows the categories in.
PARA_KEYS = ("projects", "areas", "resources", "archive")

_TREE: dict[str, list[dict]] = {
    "projects": [
        {"id": "atlas-hackathon", "name": "Atlas / Selfware: Nebius x NVIDIA Hackathon", "status": "active", "email_count": 42, "last_activity": "2026-09-29"},
        {"id": "thesis", "name": "Master's thesis", "status": "active", "email_count": 18, "last_activity": "2026-09-24"},
        {"id": "year-end-trip", "name": "Year-end trip", "status": "inactive", "email_count": 5, "last_activity": "2026-07-02"},
    ],
    "areas": [
        {"id": "health", "name": "Health", "email_count": 14, "last_activity": "2026-09-21"},
        {"id": "finances", "name": "Personal finances", "email_count": 27, "last_activity": "2026-09-27"},
        {"id": "university", "name": "University admin", "email_count": 33, "last_activity": "2026-09-26"},
    ],
    "resources": [
        {"id": "ml-papers", "name": "ML papers and newsletters", "email_count": 61, "last_activity": "2026-09-28"},
        {"id": "recipes", "name": "Recipes", "email_count": 9, "last_activity": "2026-08-30"},
    ],
    "archive": [
        {"id": "summer-internship-2025", "name": "Summer internship 2025", "email_count": 37, "last_activity": "2025-09-05"},
        {"id": "apartment-2024", "name": "Apartment search 2024", "email_count": 22, "last_activity": "2024-12-11"},
    ],
}


def get_category(key: str) -> list[dict]:
    """Items of one PARA category. Returns copies, safe to mutate."""
    return [dict(item) for item in _TREE[key]]


def get_tree() -> list[dict]:
    """All four categories: [{"key": "projects", "items": [...]}, ...]."""
    return [{"key": key, "items": get_category(key)} for key in PARA_KEYS]
