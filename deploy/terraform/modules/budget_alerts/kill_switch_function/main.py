"""Agora Budget Kill Switch — Cloud Function (Gen2).

Triggered by billing budget Pub/Sub messages when project spend exceeds
85% of the $500 limit (~$425).

Actions:
  1. Logs the billing alert
  2. Sets all Agora Cloud Run services to 0 max-replicas (scale-to-zero)
  3. Updates a Firestore "kill_switch_engaged" flag for audit trail

This is Tier 2 budget enforcement — Tier 1 is the Python BudgetGuard.
"""

import base64
import json
import logging
import os
import subprocess
from typing import Any

import functions_framework

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "")
REGION = os.environ.get("REGION", "us-central1")

AGORA_SERVICES = [
    "socrates-agent",
    "galileo-agent",
    "euler-agent",
    "galois-agent",
    "hypatie-agent",
    "alexandrie-vault",
    "pythagore-agent",
    "heraclite-agent",
    "turing-agent",
]


@functions_framework.cloud_event
def kill_switch_handler(cloud_event: Any) -> None:
    """Handle a Pub/Sub billing budget event and halt all Agora services."""
    # Decode the billing event payload
    data = cloud_event.data
    message = data.get("message", {})
    payload_b64 = message.get("data", "")

    try:
        payload_str = base64.b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_str)
    except Exception as exc:
        logger.warning("Failed to decode billing event payload: %s", exc)
        payload = {}

    cost_amount = payload.get("costAmount", 0.0)
    budget_amount = payload.get("budgetAmount", 500.0)
    budget_name = payload.get("budgetDisplayName", "Unknown")
    alert_threshold = payload.get("alertThresholdExceeded", 0.0)

    logger.critical(
        "TIER2_BUDGET_KILL_SWITCH_TRIGGERED: budget=%s cost=$%.2f/%s alert=%.0f%%",
        budget_name,
        cost_amount,
        budget_amount,
        alert_threshold * 100,
    )

    # Only hard-kill at 85%+ to avoid false positives from lower threshold alerts
    if alert_threshold < 0.85:
        logger.info(
            "Threshold %.0f%% below kill threshold (85%%) — no action taken.",
            alert_threshold * 100,
        )
        return

    errors = []
    for service in AGORA_SERVICES:
        try:
            cmd = [
                "gcloud", "run", "services", "update", service,
                "--max-instances=0",
                f"--region={REGION}",
                f"--project={PROJECT_ID}",
                "--quiet",
                "--format=none",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info("SERVICE_HALTED: %s", service)
            else:
                logger.error("Failed to halt %s: %s", service, result.stderr)
                errors.append(f"{service}: {result.stderr}")
        except Exception as exc:
            logger.error("Exception halting %s: %s", service, exc)
            errors.append(f"{service}: {exc}")

    # Audit trail in Firestore
    try:
        from google.cloud import firestore  # type: ignore[import]
        db = firestore.Client()
        db.collection("kill_switch_events").add({
            "triggered_at": firestore.SERVER_TIMESTAMP,
            "cost_amount": cost_amount,
            "budget_amount": budget_amount,
            "alert_threshold": alert_threshold,
            "services_halted": AGORA_SERVICES,
            "errors": errors,
        })
        logger.info("Kill switch event recorded in Firestore audit trail.")
    except Exception as exc:
        logger.warning("Firestore audit trail write failed: %s", exc)

    if errors:
        logger.error(
            "Kill switch completed with %d error(s): %s",
            len(errors),
            errors,
        )
    else:
        logger.info(
            "Kill switch successful: %d services halted.",
            len(AGORA_SERVICES),
        )
