"""Flat-file JSON index for base voices and generated outputs. No DB."""
import json
import threading
from pathlib import Path

BASE_VOICES_DIR = Path("base_voices")
OUTPUTS_DIR = Path("outputs")
DATA_DIR = Path("data")
VOICES_INDEX = BASE_VOICES_DIR / "index.json"
OUTPUTS_INDEX = OUTPUTS_DIR / "index.json"
RENTALS_INDEX = DATA_DIR / "rentals.json"
ACCESS_INDEX = DATA_DIR / "voice_access.json"
LEDGER_INDEX = DATA_DIR / "ledger.json"

_lock = threading.Lock()


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _write(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, indent=2))


def add_voice(entry: dict) -> None:
    with _lock:
        items = _read(VOICES_INDEX)
        items.append(entry)
        _write(VOICES_INDEX, items)


def list_voices() -> list[dict]:
    return _read(VOICES_INDEX)


def get_voice(voice_id: str) -> dict | None:
    return next((v for v in list_voices() if v["id"] == voice_id), None)


def delete_voice(voice_id: str) -> bool:
    with _lock:
        items = _read(VOICES_INDEX)
        remaining = [v for v in items if v["id"] != voice_id]
        if len(remaining) == len(items):
            return False
        _write(VOICES_INDEX, remaining)
        return True


def add_output(entry: dict) -> None:
    with _lock:
        items = _read(OUTPUTS_INDEX)
        items.append(entry)
        _write(OUTPUTS_INDEX, items)


def list_outputs() -> list[dict]:
    return _read(OUTPUTS_INDEX)


def add_rental(entry: dict) -> None:
    with _lock:
        items = _read(RENTALS_INDEX)
        items.append(entry)
        _write(RENTALS_INDEX, items)


def list_rentals(status: str | None = None) -> list[dict]:
    items = _read(RENTALS_INDEX)
    if status is None:
        return items
    return [r for r in items if r["status"] == status]


def get_rental(rental_id: str) -> dict | None:
    return next((r for r in list_rentals() if r["id"] == rental_id), None)


def update_rental(rental_id: str, **fields) -> dict | None:
    """Internal-only mutation; never expose a generic PATCH route for this."""
    with _lock:
        items = _read(RENTALS_INDEX)
        for r in items:
            if r["id"] == rental_id:
                r.update(fields)
                _write(RENTALS_INDEX, items)
                return r
        return None


def add_access(entry: dict) -> None:
    """Voice access grant: a renter paid to unlock a voice for generation."""
    with _lock:
        items = _read(ACCESS_INDEX)
        items.append(entry)
        _write(ACCESS_INDEX, items)


def list_access(renter_persona_id: str | None = None, voice_id: str | None = None) -> list[dict]:
    items = _read(ACCESS_INDEX)
    if renter_persona_id is not None:
        items = [a for a in items if a["renter_persona_id"] == renter_persona_id]
    if voice_id is not None:
        items = [a for a in items if a["voice_id"] == voice_id]
    return items


def has_access(renter_persona_id: str, voice_id: str) -> bool:
    return bool(list_access(renter_persona_id=renter_persona_id, voice_id=voice_id))


def add_ledger_entry(entry: dict) -> None:
    with _lock:
        items = _read(LEDGER_INDEX)
        items.append(entry)
        _write(LEDGER_INDEX, items)


def list_ledger(owner_persona_id: str | None = None, voice_id: str | None = None) -> list[dict]:
    items = _read(LEDGER_INDEX)
    if owner_persona_id is not None:
        items = [e for e in items if e["owner_persona_id"] == owner_persona_id]
    if voice_id is not None:
        items = [e for e in items if e["voice_id"] == voice_id]
    return items
