from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "temmyCollection.settings")

app = Celery("temmyCollection")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
