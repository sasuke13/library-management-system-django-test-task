from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

# Import views
from . import views

# Create router for ViewSets
router = DefaultRouter()

# Register ViewSets
router.register(r'books', views.BookViewSet, basename='book')
router.register(r'loans', views.LoanViewSet, basename='loan')
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'ratings', views.BookRatingViewSet, basename='bookrating')

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    path('auth/login/', views.UserLoginView.as_view(), name='login'),
    path('auth/logout/', views.UserLogoutView.as_view(), name='logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Profile endpoint
    path('profile/', views.UserViewSet.as_view({'get': 'profile', 'put': 'profile', 'patch': 'profile'}), name='profile'),
    
    # API endpoints
    path('', include(router.urls)),
]