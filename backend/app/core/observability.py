"""
app/core/observability.py — Prometheus metrics instrumentation.
Tracks: agent latency, workflow success rate, policy violations, errors.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Optional

import structlog
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    start_http_server,
)

from app.core.config import settings

log = structlog.get_logger(__name__)

# ── Metrics Definitions ───────────────────────────────────────────

AGENT_CALLS_TOTAL = Counter(
    "b2a_agent_calls_total",
    "Total number of agent invocations",
    ["tenant_id", "agent_name", "status"],
)

AGENT_LATENCY = Histogram(
    "b2a_agent_latency_seconds",
    "Agent execution latency in seconds",
    ["tenant_id", "agent_name"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

WORKFLOW_TOTAL = Counter(
    "b2a_workflow_total",
    "Total number of workflow executions",
    ["tenant_id", "workflow_type", "status"],
)

WORKFLOW_DURATION = Histogram(
    "b2a_workflow_duration_seconds",
    "Workflow total execution time in seconds",
    ["tenant_id", "workflow_type"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

POLICY_VIOLATIONS = Counter(
    "b2a_policy_violations_total",
    "Total number of policy violations",
    ["tenant_id", "agent_name", "action"],
)

BILLING_CHARGED_USD = Counter(
    "b2a_billing_charged_usd_total",
    "Total USD charged across all tenants",
    ["tenant_id"],
)

ACTIVE_WORKFLOWS = Gauge(
    "b2a_active_workflows",
    "Number of currently running workflows",
    ["tenant_id"],
)

ERRORS_TOTAL = Counter(
    "b2a_errors_total",
    "Total application errors",
    ["tenant_id", "component", "error_type"],
)

AUDIT_EVENTS_TOTAL = Counter(
    "b2a_audit_events_total",
    "Total audit events appended to chain",
    ["tenant_id"],
)


# ── Helper Contexts ───────────────────────────────────────────────

@contextmanager
def track_agent_execution(tenant_id: str, agent_name: str):
    """Context manager to track agent call latency and status."""
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        AGENT_LATENCY.labels(tenant_id=tenant_id, agent_name=agent_name).observe(elapsed)
        AGENT_CALLS_TOTAL.labels(
            tenant_id=tenant_id, agent_name=agent_name, status=status
        ).inc()


@contextmanager
def track_workflow_execution(tenant_id: str, workflow_type: str):
    """Context manager to track workflow duration and outcome."""
    start = time.perf_counter()
    status = "completed"
    ACTIVE_WORKFLOWS.labels(tenant_id=tenant_id).inc()
    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        elapsed = time.perf_counter() - start
        WORKFLOW_DURATION.labels(tenant_id=tenant_id, workflow_type=workflow_type).observe(elapsed)
        WORKFLOW_TOTAL.labels(
            tenant_id=tenant_id, workflow_type=workflow_type, status=status
        ).inc()
        ACTIVE_WORKFLOWS.labels(tenant_id=tenant_id).dec()


def record_policy_violation(tenant_id: str, agent_name: str, action: str) -> None:
    POLICY_VIOLATIONS.labels(
        tenant_id=tenant_id, agent_name=agent_name, action=action
    ).inc()


def record_billing_charge(tenant_id: str, amount: float) -> None:
    BILLING_CHARGED_USD.labels(tenant_id=tenant_id).inc(amount)


def record_error(tenant_id: str, component: str, error_type: str) -> None:
    ERRORS_TOTAL.labels(
        tenant_id=tenant_id, component=component, error_type=error_type
    ).inc()


def record_audit_event(tenant_id: str) -> None:
    AUDIT_EVENTS_TOTAL.labels(tenant_id=tenant_id).inc()


# ── Metrics Server ────────────────────────────────────────────────

def init_metrics() -> None:
    if not settings.METRICS_ENABLED:
        return
    try:
        thread = threading.Thread(
            target=start_http_server,
            args=(settings.METRICS_PORT,),
            daemon=True,
        )
        thread.start()
        log.info("observability.metrics_server_started", port=settings.METRICS_PORT)
    except Exception as exc:
        log.warning("observability.metrics_server_failed", error=str(exc))
