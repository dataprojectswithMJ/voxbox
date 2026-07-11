"""Script screening via Fireworks (Gemma). Forces a JSON verdict the rental router can act on."""
import json
import os

import httpx

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY")
SCREENING_MODEL_ID = os.environ.get("SCREENING_MODEL_ID", "")
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"

CONDITIONS = (
    "ads", "political", "adult", "medical_claims",
    "financial_advice", "hate_violence", "impersonation",
)

_SYSTEM_PROMPT = """You classify scripts submitted for AI voice cloning. Given the script, decide which of \
these categories it actually falls under: ads, political, adult, medical_claims, financial_advice, \
hate_violence, impersonation. A script can have zero, one, or several flags — only include a category if the \
script genuinely fits it, not just because it's plausible.

Respond with ONLY a JSON object: {"flags": [...]}"""

_ALWAYS_DENY_UNDECLARED = {"hate_violence", "impersonation"}


def _compute_verdict(flags: list[str], declared_conditions: list[str]) -> tuple[bool, str]:
    """Policy is decided here in code, not by the model — the LLM only classifies flags."""
    undeclared = [f for f in flags if f not in declared_conditions]
    matches_declared_condition = not undeclared

    if matches_declared_condition:
        verdict = "auto_approve"
    elif any(f in _ALWAYS_DENY_UNDECLARED for f in undeclared):
        verdict = "auto_deny"
    else:
        verdict = "needs_review"

    return matches_declared_condition, verdict


def screen_script(script: str, declared_conditions: list[str]) -> dict:
    if not FIREWORKS_API_KEY:
        return {
            "flags": [],
            "matches_declared_condition": False,
            "verdict": "needs_review",
            "note": "Screening not configured (no FIREWORKS_API_KEY) — defaulting to human review.",
        }

    user_prompt = (
        f"Declared conditions: {declared_conditions}\n\nScript:\n{script}"
    )
    try:
        resp = httpx.post(
            FIREWORKS_URL,
            headers={"Authorization": f"Bearer {FIREWORKS_API_KEY}"},
            json={
                "model": SCREENING_MODEL_ID,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
    except Exception as exc:
        return {
            "flags": [],
            "matches_declared_condition": False,
            "verdict": "needs_review",
            "note": f"Screening call failed ({exc}) — defaulting to human review.",
        }

    flags = [f for f in result.get("flags", []) if f in CONDITIONS]
    matches_declared_condition, verdict = _compute_verdict(flags, declared_conditions)
    return {
        "flags": flags,
        "matches_declared_condition": matches_declared_condition,
        "verdict": verdict,
    }
