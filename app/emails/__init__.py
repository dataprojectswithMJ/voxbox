"""Shared email templates + Resend send helper. All outbound email (verification,
password reset, receipts, etc.) should render a template from templates/ and go
through send_email() so styling and the Resend call stay in one place."""
import os

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "VoxBox <onboarding@resend.dev>")

_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
    autoescape=select_autoescape(["html"]),
)


def render_template(template_name: str, **context) -> str:
    return _env.get_template(template_name).render(**context)


def send_email(to: str, subject: str, template_name: str, **context) -> None:
    if not RESEND_API_KEY:
        return
    html = render_template(template_name, **context)
    httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": RESEND_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
        timeout=10,
    )
