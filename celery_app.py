import os
import sys
import platform
from celery import Celery
from config.settings import settings

# Initialize Celery app with Redis as both broker and result backend
celery_app = Celery(
    "sentinai_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['tasks.simulation_worker']
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # Max 1 hour per simulation graph run
    worker_prefetch_multiplier=1,  # Ensure fair round-robin distribution among workers
    # Windows fix: prefork pool uses billiard semaphores which fail on Windows
    # Use 'solo' pool (single-threaded, no subprocess forking)
    worker_pool="solo" if platform.system() == "Windows" else "prefork",
    # Redis broker transport options — disable HELLO handshake for older Redis (<6.0)
    broker_transport_options={
        "health_check_interval": 10,
    },
    redis_socket_connect_timeout=5,
    redis_socket_timeout=5,
)

# Only use the explicit ENV setting or a dedicated env var.
# DO NOT check sys.modules for 'unittest'/'pytest' — many production libraries
# (httpx, pydantic, langgraph) import unittest internally, which would
# incorrectly set task_always_eager=True and break Celery dispatch.
is_test = (
    settings.ENV == "test" or
    os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
)

if is_test:
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )