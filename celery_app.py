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
    task_time_limit=3600, # Max 1 hour per simulation graph run
    worker_prefetch_multiplier=1, # Ensure fair round-robin distribution among workers
)