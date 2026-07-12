"""Speech-to-text verification: confirms an uploaded recording actually says the challenge phrase."""
import re
from difflib import SequenceMatcher

from faster_whisper import WhisperModel

_model: WhisperModel | None = None

MATCH_THRESHOLD = 0.70


def load_model() -> None:
    global _model
    if _model is not None:
        return
    _model = WhisperModel("tiny.en", device="cpu", compute_type="int8")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def transcribe(audio_path: str) -> str:
    if _model is None:
        raise RuntimeError("STT model not loaded")
    segments, _ = _model.transcribe(audio_path)
    return " ".join(seg.text.strip() for seg in segments)


def matches_phrase(audio_path: str, phrase: str) -> tuple[bool, float]:
    transcript = _normalize(transcribe(audio_path))
    target = _normalize(phrase)
    ratio = SequenceMatcher(None, transcript, target).ratio()
    return ratio >= MATCH_THRESHOLD, ratio
