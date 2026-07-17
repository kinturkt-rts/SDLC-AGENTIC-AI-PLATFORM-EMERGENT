"""Process-wide background task registry for AgentCore async invocations.

AgentCore keeps a runtime session alive only while /ping reports "HealthyBusy".
Fire-and-forget entrypoints (orchestrator pipeline, developer implementation)
return an ack immediately and continue on a background thread — this registry
is how the /ping handler in agentcore_serve.py knows those threads are still
working, so the session is not terminated as idle mid-run
(docs: bedrock-agentcore runtime-long-run "asynchronous processing model").
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_active: dict[str, str] = {}


def begin_background_task(name: str) -> str:
    """Register a background task; returns a task id for end_background_task."""
    task_id = uuid.uuid4().hex
    with _lock:
        _active[task_id] = name
    logger.info("[background-tasks] started %s (id=%s, active=%d)", name, task_id, len(_active))
    return task_id


def end_background_task(task_id: str) -> None:
    """Unregister a background task (idempotent)."""
    with _lock:
        name = _active.pop(task_id, None)
        remaining = len(_active)
    if name:
        logger.info("[background-tasks] finished %s (id=%s, active=%d)", name, task_id, remaining)


def active_background_tasks() -> int:
    """Number of in-flight background tasks (drives HealthyBusy ping)."""
    with _lock:
        return len(_active)


def run_in_background(name: str, fn: Callable[[], None]) -> threading.Thread:
    """Run ``fn`` on a daemon thread, tracked so /ping reports HealthyBusy.

    The wrapper guarantees the task is unregistered even when ``fn`` raises, so
    a crashed background run cannot leave the session pinned busy until
    maxLifetime (which would exhaust the session quota).
    """
    task_id = begin_background_task(name)

    def _runner() -> None:
        try:
            fn()
        except BaseException:
            logger.exception("[background-tasks] %s failed", name)
        finally:
            end_background_task(task_id)

    thread = threading.Thread(target=_runner, name=f"bg-{name}", daemon=True)
    thread.start()
    return thread