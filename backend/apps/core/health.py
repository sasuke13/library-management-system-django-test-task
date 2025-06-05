"""
Health check endpoints for monitoring and load balancer health checks
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.core.cache import cache
import time
import os


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint for load balancers
    Returns 200 OK if the service is healthy
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'library-management-api'
    })


@csrf_exempt
@require_http_methods(["GET"])
def health_detailed(request):
    """
    Detailed health check with database and cache connectivity
    """
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'library-management-api',
        'checks': {}
    }
    
    overall_healthy = True
    
    # Database connectivity check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }
        overall_healthy = False
    
    # Cache connectivity check
    try:
        cache_key = 'health_check_test'
        cache.set(cache_key, 'test_value', 30)
        cached_value = cache.get(cache_key)
        if cached_value == 'test_value':
            health_status['checks']['cache'] = {
                'status': 'healthy',
                'message': 'Cache connection successful'
            }
        else:
            raise Exception('Cache value mismatch')
    except Exception as e:
        health_status['checks']['cache'] = {
            'status': 'unhealthy',
            'message': f'Cache connection failed: {str(e)}'
        }
        overall_healthy = False
    
    # Disk space check
    try:
        disk_usage = os.statvfs('/')
        free_space_percent = (disk_usage.f_bavail * disk_usage.f_frsize) / (disk_usage.f_blocks * disk_usage.f_frsize) * 100
        
        if free_space_percent > 10:  # More than 10% free space
            health_status['checks']['disk_space'] = {
                'status': 'healthy',
                'message': f'Disk space: {free_space_percent:.1f}% free'
            }
        else:
            health_status['checks']['disk_space'] = {
                'status': 'warning',
                'message': f'Low disk space: {free_space_percent:.1f}% free'
            }
    except Exception as e:
        health_status['checks']['disk_space'] = {
            'status': 'unknown',
            'message': f'Could not check disk space: {str(e)}'
        }
    
    # Update overall status
    if not overall_healthy:
        health_status['status'] = 'unhealthy'
    
    # Return appropriate HTTP status code
    status_code = 200 if overall_healthy else 503
    
    return JsonResponse(health_status, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes/container orchestration
    Checks if the application is ready to serve traffic
    """
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        return JsonResponse({
            'status': 'ready',
            'timestamp': time.time(),
            'service': 'library-management-api'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'timestamp': time.time(),
            'service': 'library-management-api',
            'error': str(e)
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for Kubernetes/container orchestration
    Checks if the application is alive and should not be restarted
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': time.time(),
        'service': 'library-management-api'
    })