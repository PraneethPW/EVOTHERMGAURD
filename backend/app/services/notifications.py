"""Risk-tier notification policy and optional SMTP delivery."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


POLICY = {
    "NORMAL": {"dashboard": False, "email": False, "prominent": False},
    "WARNING": {"dashboard": True, "email": False, "prominent": False},
    "HIGH_RISK": {"dashboard": True, "email": True, "prominent": False},
    "CRITICAL": {"dashboard": True, "email": True, "prominent": True},
}
_delivery_tasks: set[asyncio.Task] = set()


def policy_for(risk: str) -> dict:
    return dict(POLICY.get(risk, POLICY["NORMAL"]))


def delivery_state_for(risk: str) -> dict:
    policy = policy_for(risk)
    if not policy["email"]:
        return {"required": False, "status": "not_required"}
    if not settings.smtp_host or not (settings.smtp_from_email or settings.smtp_username):
        return {"required": True, "status": "not_configured"}
    return {"required": True, "status": "queued"}


def _send_message(recipient: str, risk: str, equipment_name: str, inspection_id: str) -> None:
    message = EmailMessage()
    message["Subject"] = f"EvoThermGuard {risk.replace('_', ' ').title()} — {equipment_name}"
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = recipient
    message.set_content(
        f"EvoThermGuard recorded a {risk.replace('_', ' ').lower()} result for "
        f"{equipment_name}. Inspection: {inspection_id}. Review the localized evidence "
        "in the dashboard and arrange qualified engineering review. This is decision "
        "support, not an automatic diagnosis."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as client:
        if settings.smtp_use_tls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_risk_email(
    recipient: str, risk: str, equipment_name: str, inspection_id: str
) -> dict:
    state = delivery_state_for(risk)
    if state["status"] != "queued":
        return state
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                _send_message, recipient, risk, equipment_name, inspection_id
            ),
            timeout=6,
        )
        return {"required": True, "status": "sent"}
    except Exception as exc:
        return {
            "required": True,
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def queue_risk_email(
    recipient: str, risk: str, equipment_name: str, inspection_id: str
) -> dict:
    state = delivery_state_for(risk)
    if state["status"] == "queued":
        task = asyncio.create_task(
            send_risk_email(recipient, risk, equipment_name, inspection_id)
        )
        _delivery_tasks.add(task)
        task.add_done_callback(_delivery_tasks.discard)
    return state
