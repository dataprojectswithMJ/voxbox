"""Fixed demo personas. Real credentials live in app/accounts.py (SQLite-backed);
these personas are seeded there as real accounts (see accounts.seed_demo_users)."""

PERSONAS = [
    {"id": "persona_taylor", "name": "Taylor", "role": "actor"},
    {"id": "persona_alex", "name": "Alex", "role": "actor"},
    {"id": "persona_jordan", "name": "Jordan", "role": "actor"},
    {"id": "persona_morgan", "name": "Morgan", "role": "renter"},
    {"id": "persona_sam", "name": "Sam", "role": "renter"},
]

_PERSONAS_BY_ID = {p["id"]: p for p in PERSONAS}


def is_valid_persona(persona_id: str) -> bool:
    return persona_id in _PERSONAS_BY_ID


def persona_for_id(persona_id: str) -> dict | None:
    return _PERSONAS_BY_ID.get(persona_id)


def persona_name(persona_id: str) -> str:
    p = _PERSONAS_BY_ID.get(persona_id)
    return p["name"] if p else persona_id


def persona_role(persona_id: str) -> str | None:
    p = _PERSONAS_BY_ID.get(persona_id)
    return p["role"] if p else None


