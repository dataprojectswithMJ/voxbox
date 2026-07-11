"""Chatterbox TTS wrapper: load once at startup, reuse for every generation."""
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS

_model: ChatterboxTurboTTS | None = None


def load_model() -> None:
    global _model
    if _model is not None:
        return
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = ChatterboxTurboTTS.from_pretrained(device=device)


def generate(text: str, audio_prompt_path: str) -> torch.Tensor:
    if _model is None:
        raise RuntimeError("TTS model not loaded")
    return _model.generate(text, audio_prompt_path=audio_prompt_path)


def sample_rate() -> int:
    if _model is None:
        raise RuntimeError("TTS model not loaded")
    return _model.sr
