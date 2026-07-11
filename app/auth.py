"""Mock auth: fixed personas with a role and a shared demo password. No real password storage."""

DEMO_PASSWORD = "123456"

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


def persona_name(persona_id: str) -> str:
    p = _PERSONAS_BY_ID.get(persona_id)
    return p["name"] if p else persona_id


def persona_role(persona_id: str) -> str | None:
    p = _PERSONAS_BY_ID.get(persona_id)
    return p["role"] if p else None


def personas_for_role(role: str) -> list[dict]:
    return [p for p in PERSONAS if p["role"] == role]


def login(persona_id: str, password: str, role: str) -> dict | None:
    p = _PERSONAS_BY_ID.get(persona_id)
    if p is None or p["role"] != role or password != DEMO_PASSWORD:
        return None
    return p
