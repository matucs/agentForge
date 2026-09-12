"""Real outbound webhook notifications to n8n/Slack on run state changes
(spec §19/§22). No URL configured means a logged no-op, never a fabricated
delivery — the same "unavailable, not simulated" discipline as the GitHub
client. A failed delivery (network error, non-2xx) is logged and swallowed:
a broken webhook must never fail the actual orchestration run.
"""

import httpx

from app.config import Settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10.0


async def _post_json(url: str, payload: dict, *, kind: str, event: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            logger.warning(
                "webhook_delivery_failed",
                kind=kind,
                event_name=event,
                status_code=response.status_code,
            )
        else:
            logger.info("webhook_delivered", kind=kind, event_name=event)
    except httpx.HTTPError as exc:
        logger.warning("webhook_delivery_error", kind=kind, event_name=event, error=str(exc))


async def notify_run_finished(
    settings: Settings,
    *,
    run_id: str,
    task_id: str,
    status: str,
    final_decision: str | None,
) -> None:
    """Fires when a run reaches a terminal status (completed, blocked,
    failed, stopped_by_timeout, stopped_by_budget, cancelled)."""
    if not settings.n8n_webhook_url and not settings.slack_webhook_url:
        logger.info(
            "webhook_notify_skipped", reason="no_webhook_configured", event_name="run.finished"
        )
        return

    if settings.n8n_webhook_url:
        await _post_json(
            settings.n8n_webhook_url,
            {
                "event": "run.finished",
                "run_id": run_id,
                "task_id": task_id,
                "status": status,
                "final_decision": final_decision,
            },
            kind="n8n",
            event="run.finished",
        )

    if settings.slack_webhook_url:
        text = f"AgentForge run `{run_id}` finished: *{status}*"
        if final_decision:
            text += f" ({final_decision})"
        await _post_json(
            settings.slack_webhook_url, {"text": text}, kind="slack", event="run.finished"
        )


async def notify_approval_required(
    settings: Settings,
    *,
    run_id: str,
    task_id: str,
    risk_level: str,
    reason: str,
) -> None:
    """Fires when `policy_node` classifies a change as requiring human
    sign-off before merge, so an operator doesn't have to poll
    `GET /api/approvals` to find out."""
    if not settings.n8n_webhook_url and not settings.slack_webhook_url:
        logger.info(
            "webhook_notify_skipped",
            reason="no_webhook_configured",
            event_name="run.approval_required",
        )
        return

    if settings.n8n_webhook_url:
        await _post_json(
            settings.n8n_webhook_url,
            {
                "event": "run.approval_required",
                "run_id": run_id,
                "task_id": task_id,
                "risk_level": risk_level,
                "reason": reason,
            },
            kind="n8n",
            event="run.approval_required",
        )

    if settings.slack_webhook_url:
        text = f"AgentForge run `{run_id}` needs human approval — risk: *{risk_level}*. {reason}"
        await _post_json(
            settings.slack_webhook_url, {"text": text}, kind="slack", event="run.approval_required"
        )
