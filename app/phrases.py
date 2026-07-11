"""Challenge-phrase generation: LLM-backed pool with a static fallback bank."""
import json
import random
import threading

import httpx

from app import screening

STATIC_BANK = (
    "The old lighthouse keeper counted seventeen ships before breakfast.",
    "A quiet river carved this canyon over ten thousand years.",
    "Nobody expected the meeting to end before noon.",
    "Bright orange lanterns lined the narrow market street.",
    "The recipe calls for three cups of toasted flour.",
    "Somewhere north of the harbor, the fog never lifts.",
    "Her favorite chess opening always starts with the knight.",
    "The train to the coast leaves twice a day.",
    "A single ember was enough to relight the whole fire.",
    "Most maps of the region are at least a decade old.",
    "The orchard behind the barn produces more pears than apples.",
    "Every winter the lake freezes thick enough to walk on.",
    "He kept a spare key hidden under the granite step.",
    "The choir rehearses in the basement on Tuesday evenings.",
    "A soft breeze carried the smell of rain across the field.",
    "The museum's newest exhibit features glass sculptures from the coast.",
    "Nobody could explain why the clock ran backward that day.",
    "The bakery sells out of sourdough by mid-morning.",
    "Their cabin sits just past the second bend in the trail.",
    "A stray cat has been sleeping on the porch all week.",
)

_POOL_TARGET = 10
_POOL_REFILL_BATCH = 12
_pool: list[str] = []
_lock = threading.Lock()

_GEN_SYSTEM_PROMPT = """Generate short, standalone, unrelated English sentences for a voice-recording \
challenge (the speaker reads them aloud so a TTS model has enough varied phonetic material to clone their \
voice). Each sentence must be a complete, grammatically simple sentence between 8 and 16 words, with no \
profanity, no numbers-as-digits, and no ties to current events or real named public figures. Return ONLY a \
JSON object: {"sentences": ["...", "...", ...]}"""


def _fetch_llm_sentences(count: int) -> list[str]:
    if not screening.FIREWORKS_API_KEY:
        return []
    try:
        resp = httpx.post(
            screening.FIREWORKS_URL,
            headers={"Authorization": f"Bearer {screening.FIREWORKS_API_KEY}"},
            json={
                "model": screening.SCREENING_MODEL_ID,
                "messages": [
                    {"role": "system", "content": _GEN_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Generate {count} sentences."},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.9,
            },
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        sentences = json.loads(content).get("sentences", [])
        return [s.strip() for s in sentences if isinstance(s, str) and s.strip()]
    except Exception:
        return []


def _refill_pool() -> None:
    fresh = _fetch_llm_sentences(_POOL_REFILL_BATCH)
    if fresh:
        _pool.extend(fresh)


def get_challenge_phrase() -> str:
    """Two unrelated sentences, pulled from an LLM-generated pool (refilled as needed)."""
    with _lock:
        if len(_pool) < 2:
            _refill_pool()
        if len(_pool) >= 2:
            picks = random.sample(range(len(_pool)), 2)
            sentences = [_pool[i] for i in sorted(picks, reverse=True)]
            for i in sorted(picks, reverse=True):
                _pool.pop(i)
            if len(_pool) < 2:
                threading.Thread(target=_refill_pool, daemon=True).start()
            return " ".join(sentences)

    return " ".join(random.sample(STATIC_BANK, 2))
