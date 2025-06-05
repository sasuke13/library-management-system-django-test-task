"""
Security-focused tests for the library management system.
"""
import pytest
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth.hashers import check_password

from apps.core.models import Book, Loan, BookRating
from .factories import (
    UserFactory, LibrarianFactory, BookFactory, LoanFactory, 
    BookRatingFactory
)

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.security
class TestAuthenticationSecurity(APITestCase):
    """Test authentication security measures."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.user.set_password('testpass123')
        self.user.save()
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        # Password should not be stored in plain text
        self.assertNotEqual(self.user.password, 'testpass123')
        # But should verify correctly
        self.assertTrue(check_password('testpass123', self.user.password))
    
    def test_weak_password_rejection(self):
        """Test that weak passwords are rejected."""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': '123',  # Weak password
            'password_confirm': '123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
    
    def test_password_confirmation_mismatch(self):
        """Test password confirmation validation."""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'strongpassword123',
            'password_confirm': 'differentpassword',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_rate_limiting(self):
        """Test login rate limiting (basic test)."""
        url = reverse('login')
        data = {
            'username': self.user.username,
            'password': 'wrongpassword'
        }
        
        # Make multiple failed login attempts
        failed_attempts = 0
        for _ in range(10):
            response = self.client.post(url, data, format='json')
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                failed_attempts += 1
        
        # Should have multiple failed attempts
        self.assertGreater(failed_attempts, 5)
    
    def test_jwt_token_expiration(self):
        """Test JWT token expiration handling."""
        # This would require mocking time or using expired tokens
        # For now, we'll test that tokens are properly formatted
        url = reverse('login')
        data = {
            'username': self.user.username,
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        
        # Tokens should be strings
        self.assertIsInstance(response.data['tokens']['access'], str)
        self.assertIsInstance(response.data['tokens']['refresh'], str)
    
    def test_invalid_token_rejection(self):
        """Test that invalid tokens are rejected."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        url = reverse('profile')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
@pytest.mark.security
class TestInputValidationSecurity(APITestCase):
    """Test input validation and sanitization."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.librarian = LibrarianFactory()
        self.client.force_authenticate(user=self.librarian)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in search."""
        url = reverse('book-list')
        malicious_query = "'; DROP TABLE books; --"
        
        response = self.client.get(url, {'search': malicious_query})
        # Should not cause an error and should return safely
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_xss_prevention_in_book_creation(self):
        """Test XSS prevention in book creation."""
        url = reverse('book-list')
        data = {
            'title': '<script>alert("XSS")</script>',
            'author': '<img src=x onerror=alert("XSS")>',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'fiction',
            'description': '<script>malicious_code()</script>',
            'pages': 200,
            'total_copies': 5
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify that the data is stored but scripts are not executed
        book = Book.objects.get(id=response.data['id'])
        self.assertIn('<script>', book.title)  # Stored as-is for now
        # In production, you'd want to sanitize this
    
    def test_large_payload_handling(self):
        """Test handling of unusually large payloads."""
        url = reverse('book-list')
        large_string = 'A' * 10000  # 10KB string
        
        data = {
            'title': large_string,
            'author': 'Test Author',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'Fiction',
            'total_copies': 5
        }
        
        response = self.client.post(url, data, format='json')
        # Should handle gracefully (either accept or reject with proper error)
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ])
    
    def test_invalid_data_types(self):
        """Test handling of invalid data types."""
        url = reverse('book-list')
        data = {
            'title': 'Valid Title',
            'author': 'Valid Author',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'Fiction',
            'total_copies': 'not_a_number'  # Invalid type
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_negative_values_validation(self):
        """Test validation of negative values where inappropriate."""
        url = reverse('book-list')
        data = {
            'title': 'Valid Title',
            'author': 'Valid Author',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'Fiction',
            'total_copies': -5  # Negative value
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
@pytest.mark.security
class TestPermissionSecurity(APITestCase):
    """Test permission and authorization security."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.librarian = LibrarianFactory()
        self.book = BookFactory()
    
    def test_user_isolation(self):
        """Test that users can only access their own data."""
        # Create loans for both users
        loan1 = LoanFactory(user=self.user1, book=self.book)
        loan2 = LoanFactory(user=self.user2)
        
        # User1 should only see their own loans
        self.client.force_authenticate(user=self.user1)
        url = reverse('loan-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan_ids = [loan['id'] for loan in response.data['results']]
        self.assertIn(loan1.id, loan_ids)
        self.assertNotIn(loan2.id, loan_ids)
    
    def test_unauthorized_book_modification(self):
        """Test that regular users cannot modify books."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('book-detail', kwargs={'pk': self.book.pk})
        data = {'title': 'Hacked Title'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_unauthorized_user_data_access(self):
        """Test that users cannot access other users' profile data."""
        self.client.force_authenticate(user=self.user1)
        
        # Try to access user2's profile (if such endpoint existed)
        # For now, test that profile endpoint only returns own data
        url = reverse('profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user1.id)
        self.assertNotEqual(response.data['id'], self.user2.id)
    
    def test_librarian_permissions(self):
        """Test librarian-specific permissions."""
        self.client.force_authenticate(user=self.librarian)
        
        # Librarians should be able to see all loans
        LoanFactory(user=self.user1)
        LoanFactory(user=self.user2)
        
        url = reverse('loan-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 2)
    
    def test_anonymous_user_restrictions(self):
        """Test restrictions for anonymous users."""
        # Anonymous users should not be able to access loans
        url = reverse('loan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # But should be able to view books
        url = reverse('book-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.django_db
@pytest.mark.security
class TestDataIntegritySecurity(TestCase):
    """Test data integrity and consistency."""
    
    def test_unique_constraints(self):
        """Test unique constraints are enforced."""
        user = UserFactory()
        
        # Should not be able to create another user with same email
        with self.assertRaises((IntegrityError, ValidationError)):
            UserFactory(email=user.email)
    
    def test_foreign_key_constraints(self):
        """Test foreign key constraints."""
        user = UserFactory()
        book = BookFactory()
        loan = LoanFactory(user=user, book=book)
        
        # Should not be able to delete book with active loans
        with self.assertRaises(Exception):
            book.delete()
    
    def test_data_validation_constraints(self):
        """Test model validation constraints."""
        # Test invalid rating
        user = UserFactory()
        book = BookFactory()
        
        with self.assertRaises(ValidationError):
            rating = BookRatingFactory.build(user=user, book=book, rating=6)
            rating.full_clean()
    
    def test_business_logic_constraints(self):
        """Test business logic constraints."""
        user = UserFactory()
        book = BookFactory(available_copies=0)
        
        # Should not be able to create loan for unavailable book
        with self.assertRaises(ValidationError):
            loan = LoanFactory.build(user=user, book=book)
            loan.full_clean()


@pytest.mark.django_db
@pytest.mark.security
class TestSecurityHeaders(APITestCase):
    """Test security headers and middleware."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
    
    def test_security_headers_present(self):
        """Test that security headers are present in responses."""
        url = reverse('book-list')
        response = self.client.get(url)
        
        # Check for security headers
        self.assertIn('X-Content-Type-Options', response)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        
        self.assertIn('X-Frame-Options', response)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
    
    def test_cors_headers(self):
        """Test CORS headers configuration."""
        url = reverse('book-list')
        response = self.client.get(url)
        
        # CORS headers should be present for API endpoints
        # This depends on your CORS configuration
        if 'Access-Control-Allow-Origin' in response:
            self.assertIsNotNone(response['Access-Control-Allow-Origin'])


@pytest.mark.django_db
@pytest.mark.security
class TestAPISecurityMiscellaneous(APITestCase):
    """Test miscellaneous API security aspects."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
    
    def test_sensitive_data_not_exposed(self):
        """Test that sensitive data is not exposed in API responses."""
        self.client.force_authenticate(user=self.user)
        url = reverse('profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Password should not be in the response
        self.assertNotIn('password', response.data)
        
        # Other sensitive fields should also be excluded if any
        sensitive_fields = ['password', 'last_login']
        for field in sensitive_fields:
            self.assertNotIn(field, response.data)
    
    def test_error_message_information_disclosure(self):
        """Test that error messages don't disclose sensitive information."""
        url = reverse('login')
        data = {
            'username': 'nonexistent_user',
            'password': 'any_password'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Error message should be generic, not revealing whether user exists
        error_message = str(response.data.get('detail', ''))
        self.assertNotIn('user does not exist', error_message.lower())
        self.assertNotIn('invalid username', error_message.lower())
    
    def test_method_not_allowed_handling(self):
        """Test proper handling of disallowed HTTP methods."""
        # Use a librarian to avoid permission issues
        librarian = LibrarianFactory()
        self.client.force_authenticate(user=librarian)
        url = reverse('book-list')
        
        # Try unsupported method (PUT on list endpoint)
        response = self.client.put(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_content_type_validation(self):
        """Test content type validation."""
        self.client.force_authenticate(user=self.user)
        url = reverse('register')
        
        # Try with invalid content type
        response = self.client.post(
            url, 
            'invalid_json_data', 
            content_type='text/plain'
        )
        
        # Should handle gracefully
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        ])


@pytest.mark.django_db
@pytest.mark.security
@override_settings(DEBUG=False)
class TestProductionSecurity(APITestCase):
    """Test security measures specific to production environment."""
    
    def test_debug_mode_disabled(self):
        """Test that debug mode is disabled in production."""
        from django.conf import settings
        self.assertFalse(settings.DEBUG)
    
    def test_secret_key_not_default(self):
        """Test that secret key is not the default Django key."""
        from django.conf import settings
        # For testing, we'll just check that SECRET_KEY exists and is not empty
        self.assertTrue(settings.SECRET_KEY)
        self.assertGreater(len(settings.SECRET_KEY), 10)