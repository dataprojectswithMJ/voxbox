"""VoxBox: challenge-phrase voice capture + Chatterbox voice cloning. Flat-file storage, no DB."""
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import torchaudio

from app import auth, phrases, screening, store, tts

app = FastAPI(title="VoxBox")

BASE_VOICES_DIR = Path("base_voices")
OUTPUTS_DIR = Path("outputs")

_pending_phrases: dict[str, dict] = {}


@app.on_event("startup")
def startup() -> None:
    BASE_VOICES_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    store.DATA_DIR.mkdir(exist_ok=True)
    tts.load_model()


@app.get("/api/phrase")
def get_phrase():
    nonce = str(uuid.uuid4())
    phrase = phrases.get_challenge_phrase()
    _pending_phrases[nonce] = {
        "phrase": phrase,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"nonce": nonce, "phrase": phrase}


@app.get("/api/personas")
def list_personas(role: str | None = None):
    return auth.personas_for_role(role) if role else auth.PERSONAS


@app.post("/api/login")
def login(
    persona_id: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
):
    persona = auth.login(persona_id, password, role)
    if persona is None:
        raise HTTPException(401, "Invalid persona, role, or password")
    return persona


@app.get("/api/consent-conditions")
def list_consent_conditions():
    return screening.CONDITIONS


@app.post("/api/voices")
async def create_voice(
    nonce: str = Form(...),
    label: str = Form(""),
    owner_persona_id: str = Form(...),
    consent_conditions: str = Form("[]"),
    price_per_100_words: float = Form(5.0),
    audio: UploadFile = File(...),
):
    pending = _pending_phrases.pop(nonce, None)
    if pending is None:
        raise HTTPException(400, "Unknown or already-used phrase challenge. Request a new phrase.")
    if not auth.is_valid_persona(owner_persona_id):
        raise HTTPException(400, "Unknown persona")
    if price_per_100_words < 0:
        raise HTTPException(400, "Price cannot be negative")

    try:
        conditions = json.loads(consent_conditions)
    except json.JSONDecodeError:
        raise HTTPException(400, "consent_conditions must be a JSON array")
    unknown = set(conditions) - set(screening.CONDITIONS)
    if unknown:
        raise HTTPException(400, f"Unknown consent conditions: {sorted(unknown)}")

    voice_id = str(uuid.uuid4())
    raw_path = BASE_VOICES_DIR / f"{voice_id}_raw{Path(audio.filename or '').suffix or '.webm'}"
    wav_path = BASE_VOICES_DIR / f"{voice_id}.wav"

    raw_path.write_bytes(await audio.read())

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path), "-ar", "24000", "-ac", "1", str(wav_path)],
        capture_output=True,
        text=True,
    )
    raw_path.unlink(missing_ok=True)
    if result.returncode != 0 or not wav_path.exists():
        raise HTTPException(500, f"Audio conversion failed: {result.stderr[-500:]}")

    entry = {
        "id": voice_id,
        "label": label or pending["phrase"],
        "phrase": pending["phrase"],
        "filename": wav_path.name,
        "owner_persona_id": owner_persona_id,
        "owner_persona_name": auth.persona_name(owner_persona_id),
        "consent_conditions": conditions,
        "price_per_100_words": price_per_100_words,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store.add_voice(entry)
    return entry


@app.get("/api/voices")
def list_voices():
    return store.list_voices()


@app.get("/api/marketplace")
def marketplace(renter_persona_id: str | None = None):
    voices = store.list_voices()
    rented_ids = {a["voice_id"] for a in store.list_access(renter_persona_id=renter_persona_id)} if renter_persona_id else set()
    for v in voices:
        v["is_rented"] = v["id"] in rented_ids
    return voices


@app.post("/api/voice-rentals")
def rent_voice(
    renter_persona_id: str = Form(...),
    voice_id: str = Form(...),
):
    """Unlocks a voice for generation. Free to unlock — billing happens per generation, by word count."""
    if not auth.is_valid_persona(renter_persona_id):
        raise HTTPException(400, "Unknown persona")
    voice = store.get_voice(voice_id)
    if voice is None:
        raise HTTPException(404, "Voice not found")
    if store.has_access(renter_persona_id, voice_id):
        raise HTTPException(400, "You already have access to this voice")

    access_entry = {
        "id": str(uuid.uuid4()),
        "voice_id": voice_id,
        "voice_label": voice["label"],
        "renter_persona_id": renter_persona_id,
        "rented_at": datetime.now(timezone.utc).isoformat(),
    }
    store.add_access(access_entry)
    return access_entry


@app.get("/api/voice-rentals")
def list_voice_rentals(renter_persona_id: str):
    return store.list_access(renter_persona_id=renter_persona_id)


@app.get("/api/dashboard")
def dashboard(owner_persona_id: str):
    voices = [v for v in store.list_voices() if v.get("owner_persona_id") == owner_persona_id]
    outputs = store.list_outputs()
    ledger = store.list_ledger(owner_persona_id=owner_persona_id)

    rows = []
    for v in voices:
        usage_count = sum(1 for o in outputs if o["voice_id"] == v["id"])
        revenue = sum(e["amount"] for e in ledger if e["voice_id"] == v["id"])
        rows.append({
            "voice_id": v["id"],
            "label": v["label"],
            "price_per_100_words": v.get("price_per_100_words", 0),
            "usage_count": usage_count,
            "revenue": revenue,
        })
    return {
        "voices": rows,
        "total_revenue": sum(r["revenue"] for r in rows),
    }


@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str):
    voice = store.get_voice(voice_id)
    if voice is None:
        raise HTTPException(404, "Voice not found")
    (BASE_VOICES_DIR / voice["filename"]).unlink(missing_ok=True)
    store.delete_voice(voice_id)
    return {"ok": True}


@app.get("/api/base_voices/{filename}")
def get_base_voice_file(filename: str):
    path = BASE_VOICES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


def _charge_for(voice: dict, text: str) -> float:
    word_count = len(text.split())
    return round((word_count / 100) * voice.get("price_per_100_words", 0), 2)


async def _run_generation(voice: dict, text: str, renter_persona_id: str | None = None) -> dict:
    audio_prompt_path = str(BASE_VOICES_DIR / voice["filename"])
    wav = await run_in_threadpool(tts.generate, text, audio_prompt_path)

    output_id = str(uuid.uuid4())
    output_filename = f"{output_id}.wav"
    output_path = OUTPUTS_DIR / output_filename
    torchaudio.save(str(output_path), wav, tts.sample_rate())

    now = datetime.now(timezone.utc).isoformat()
    charge = _charge_for(voice, text) if renter_persona_id else 0.0
    entry = {
        "id": output_id,
        "voice_id": voice["id"],
        "voice_label": voice["label"],
        "text": text,
        "word_count": len(text.split()),
        "charge": charge,
        "filename": output_filename,
        "created_at": now,
    }
    store.add_output(entry)

    if renter_persona_id:
        store.add_ledger_entry({
            "id": str(uuid.uuid4()),
            "voice_id": voice["id"],
            "owner_persona_id": voice.get("owner_persona_id"),
            "renter_persona_id": renter_persona_id,
            "amount": charge,
            "kind": "generation_fee",
            "created_at": now,
        })
    return entry


@app.post("/api/generate")
async def generate(voice_id: str = Form(...), text: str = Form(...), owner_persona_id: str = Form(...)):
    """Owner-only preview generation — bypasses the rental/screening loop for the voice's own actor."""
    text = text.strip()
    if not text:
        raise HTTPException(400, "Text is required")
    voice = store.get_voice(voice_id)
    if voice is None:
        raise HTTPException(404, "Voice not found")
    if voice.get("owner_persona_id") != owner_persona_id:
        raise HTTPException(403, "Only the voice's owner can use preview generation")

    try:
        return await _run_generation(voice, text)
    except Exception as exc:
        raise HTTPException(500, f"Generation failed: {exc}") from exc


@app.get("/api/outputs")
def list_outputs():
    return store.list_outputs()


@app.get("/api/outputs/{filename}")
def get_output_file(filename: str):
    path = OUTPUTS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@app.post("/api/rentals")
async def create_rental(
    renter_persona_id: str = Form(...),
    voice_id: str = Form(...),
    script: str = Form(...),
):
    script = script.strip()
    if not script:
        raise HTTPException(400, "Script is required")
    if not auth.is_valid_persona(renter_persona_id):
        raise HTTPException(400, "Unknown persona")
    voice = store.get_voice(voice_id)
    if voice is None:
        raise HTTPException(404, "Voice not found")
    if not store.has_access(renter_persona_id, voice_id):
        raise HTTPException(403, "Rent this voice before submitting a script")

    result = screening.screen_script(script, voice.get("consent_conditions", []))
    verdict = result["verdict"]
    now = datetime.now(timezone.utc).isoformat()

    rental_id = str(uuid.uuid4())
    rental = {
        "id": rental_id,
        "voice_id": voice_id,
        "voice_label": voice["label"],
        "owner_persona_id": voice.get("owner_persona_id"),
        "renter_persona_id": renter_persona_id,
        "renter_persona_name": auth.persona_name(renter_persona_id),
        "script": script,
        "flags": result["flags"],
        "matches_declared_condition": result["matches_declared_condition"],
        "screening_note": result.get("note"),
        "decided_by": "system",
        "decided_at": now,
        "created_at": now,
        "output_id": None,
    }

    if verdict == "auto_deny":
        rental["status"] = "denied"
    elif verdict == "auto_approve":
        try:
            output = await _run_generation(voice, script, renter_persona_id=renter_persona_id)
            rental["status"] = "approved"
            rental["output_id"] = output["id"]
        except Exception as exc:
            rental["status"] = "denied"
            rental["screening_note"] = f"Auto-approved but generation failed: {exc}"
    else:
        rental["status"] = "pending_actor_review"
        rental["decided_by"] = None
        rental["decided_at"] = None

    store.add_rental(rental)
    return rental


@app.get("/api/rentals")
def get_rentals(status: str | None = None):
    return store.list_rentals(status)


@app.post("/api/rentals/{rental_id}/decision")
async def decide_rental(
    rental_id: str,
    decider_persona_id: str = Form(...),
    decision: str = Form(...),
):
    if decision not in ("approve", "deny"):
        raise HTTPException(400, "decision must be 'approve' or 'deny'")
    if not auth.is_valid_persona(decider_persona_id):
        raise HTTPException(400, "Unknown persona")

    rental = store.get_rental(rental_id)
    if rental is None:
        raise HTTPException(404, "Rental not found")
    if rental["status"] != "pending_actor_review":
        raise HTTPException(400, f"Rental is not pending review (status: {rental['status']})")
    if rental.get("owner_persona_id") != decider_persona_id:
        raise HTTPException(403, "Only the voice's owner persona can decide this rental")

    now = datetime.now(timezone.utc).isoformat()
    if decision == "deny":
        return store.update_rental(rental_id, status="denied", decided_by=decider_persona_id, decided_at=now)

    voice = store.get_voice(rental["voice_id"])
    if voice is None:
        raise HTTPException(404, "Voice no longer exists")

    try:
        output = await _run_generation(voice, rental["script"], renter_persona_id=rental["renter_persona_id"])
    except Exception as exc:
        raise HTTPException(500, f"Generation failed: {exc}") from exc

    return store.update_rental(
        rental_id,
        status="approved",
        decided_by=decider_persona_id,
        decided_at=now,
        output_id=output["id"],
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
