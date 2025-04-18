# interrogator/celery.py

import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'interrogator.settings')

app = Celery('interrogator')

# Pull in any CELERY_* settings defined in Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# **Add these two lines** to force eager mode for prototyping:
app.conf.task_always_eager = True
app.conf.task_eager_propagates = True

# Auto‑discover tasks in your INSTALLED_APPS
app.autodiscover_tasks()