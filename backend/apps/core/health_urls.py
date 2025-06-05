"""
Health check URL configuration
"""

from django.urls import path
from . import health

urlpatterns = [
    path('', health.health_check, name='health-check'),
    path('detailed/', health.health_detailed, name='health-detailed'),
    path('ready/', health.readiness_check, name='readiness-check'),
    path('live/', health.liveness_check, name='liveness-check'),
]