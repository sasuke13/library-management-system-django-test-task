"""
API tests for core views and endpoints.
"""
import pytest
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Book, Loan, BookRating
from .factories import (
    UserFactory, LibrarianFactory, BookFactory, LoanFactory, 
    BookRatingFactory, OverdueLoanFactory, ReturnedLoanFactory
)

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationAPI(APITestCase):
    """Test authentication endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
    
    def test_user_registration(self):
        """Test user registration endpoint."""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '+1234567890',
            'address': '123 Test St',
            'date_of_birth': '1990-01-01'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_user_registration_validation(self):
        """Test user registration validation."""
        url = reverse('register')
        
        # Test password mismatch
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'testpass123',
            'password_confirm': 'different',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_user_login(self):
        """Test user login endpoint."""
        url = reverse('login')
        data = {
            'username': self.user.username,
            'password': 'testpass123'  # Default password from factory
        }
        
        # Set password for the user
        self.user.set_password('testpass123')
        self.user.save()
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        url = reverse('login')
        data = {
            'username': self.user.username,
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh(self):
        """Test token refresh endpoint."""
        refresh = RefreshToken.for_user(self.user)
        url = reverse('token_refresh')
        data = {'refresh': str(refresh)}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_user_profile(self):
        """Test user profile endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('profile')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)
    
    def test_logout(self):
        """Test logout endpoint."""
        refresh = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse('logout')
        data = {'refresh': str(refresh)}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.django_db
class TestBookAPI(APITestCase):
    """Test book-related endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
        self.book = BookFactory()
    
    def test_book_list_anonymous(self):
        """Test book list for anonymous users."""
        url = reverse('book-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_book_list_authenticated(self):
        """Test book list for authenticated users."""
        self.client.force_authenticate(user=self.user)
        url = reverse('book-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_book_detail(self):
        """Test book detail endpoint."""
        url = reverse('book-detail', kwargs={'pk': self.book.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.book.title)
    
    def test_book_search(self):
        """Test book search functionality."""
        BookFactory(title="Python Programming", author="John Doe")
        BookFactory(title="Django Web Development", author="Jane Smith")
        
        url = reverse('book-list')
        response = self.client.get(url, {'search': 'Python'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_book_filter_by_genre(self):
        """Test book filtering by genre."""
        BookFactory(genre="science_fiction")
        BookFactory(genre="fantasy")
        
        url = reverse('book-list')
        response = self.client.get(url, {'genre': 'science_fiction'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have at least one Science Fiction book
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_book_filter_by_availability(self):
        """Test book filtering by availability."""
        BookFactory(available_copies=0, status='unavailable')
        
        url = reverse('book-list')
        response = self.client.get(url, {'available': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All returned books should be available
        for book in response.data['results']:
            self.assertGreater(book['available_copies'], 0)
    
    def test_book_create_librarian(self):
        """Test book creation by librarian."""
        self.client.force_authenticate(user=self.librarian)
        url = reverse('book-list')
        data = {
            'title': 'New Book',
            'author': 'New Author',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'fiction',
            'pages': 300,
            'description': 'A test book',
            'total_copies': 5
        }
        
        response = self.client.post(url, data, format='json')
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error response: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title='New Book').exists())
    
    def test_book_create_regular_user(self):
        """Test book creation by regular user (should fail)."""
        self.client.force_authenticate(user=self.user)
        url = reverse('book-list')
        data = {
            'title': 'New Book',
            'author': 'New Author',
            'isbn': '9781234567890'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_book_update_librarian(self):
        """Test book update by librarian."""
        self.client.force_authenticate(user=self.librarian)
        url = reverse('book-detail', kwargs={'pk': self.book.pk})
        data = {'title': 'Updated Title'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Updated Title')
    
    def test_book_delete_librarian(self):
        """Test book deletion by librarian."""
        self.client.force_authenticate(user=self.librarian)
        url = reverse('book-detail', kwargs={'pk': self.book.pk})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())


@pytest.mark.django_db
class TestLoanAPI(APITestCase):
    """Test loan-related endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
        self.book = BookFactory()
        self.loan = LoanFactory(user=self.user, book=self.book)
    
    def test_loan_list_user(self):
        """Test loan list for regular user (own loans only)."""
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User should only see their own loans
        for loan in response.data['results']:
            self.assertEqual(loan['user'], self.user.id)
    
    def test_loan_list_librarian(self):
        """Test loan list for librarian (all loans)."""
        # Create loans for different users
        other_user = UserFactory()
        LoanFactory(user=other_user)
        
        self.client.force_authenticate(user=self.librarian)
        url = reverse('loan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Librarian should see all loans
        self.assertGreaterEqual(len(response.data['results']), 2)
    
    def test_borrow_book(self):
        """Test borrowing a book."""
        available_book = BookFactory()
        self.client.force_authenticate(user=self.user)
        url = reverse('book-borrow', kwargs={'pk': available_book.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Loan.objects.filter(user=self.user, book=available_book).exists())
    
    def test_borrow_unavailable_book(self):
        """Test borrowing an unavailable book."""
        unavailable_book = BookFactory(available_copies=0)
        self.client.force_authenticate(user=self.user)
        url = reverse('book-borrow', kwargs={'pk': unavailable_book.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_borrow_book_over_limit(self):
        """Test borrowing when user is over limit."""
        # Create loans up to the limit
        LoanFactory.create_batch(5, user=self.user, status='borrowed')
        
        available_book = BookFactory()
        self.client.force_authenticate(user=self.user)
        url = reverse('book-borrow', kwargs={'pk': available_book.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_return_book(self):
        """Test returning a book."""
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-return', kwargs={'pk': self.loan.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, 'returned')
    
    def test_return_book_not_owner(self):
        """Test returning a book not owned by user."""
        other_user = UserFactory()
        other_loan = LoanFactory(user=other_user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-return', kwargs={'pk': other_loan.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_renew_loan(self):
        """Test renewing a loan."""
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-renew', kwargs={'pk': self.loan.pk})
        
        original_due_date = self.loan.due_date
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.loan.refresh_from_db()
        self.assertGreater(self.loan.due_date, original_due_date)
    
    def test_renew_overdue_loan(self):
        """Test renewing an overdue loan (should fail)."""
        overdue_loan = OverdueLoanFactory(user=self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-renew', kwargs={'pk': overdue_loan.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_loan_history(self):
        """Test loan history endpoint."""
        # Create some returned loans
        ReturnedLoanFactory.create_batch(3, user=self.user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-history')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 3)
    
    def test_overdue_loans(self):
        """Test overdue loans endpoint."""
        OverdueLoanFactory.create_batch(2, user=self.user)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('loan-overdue')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)


@pytest.mark.django_db
class TestBookRatingAPI(APITestCase):
    """Test book rating endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.book = BookFactory()
    
    def test_create_rating(self):
        """Test creating a book rating."""
        self.client.force_authenticate(user=self.user)
        url = reverse('bookrating-list')
        data = {
            'book': self.book.id,
            'rating': 5,
            'review': 'Excellent book!'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(BookRating.objects.filter(user=self.user, book=self.book).exists())
    
    def test_create_duplicate_rating(self):
        """Test creating duplicate rating (should fail)."""
        BookRatingFactory(user=self.user, book=self.book)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('bookrating-list')
        data = {
            'book': self.book.id,
            'rating': 4,
            'review': 'Another review'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_rating(self):
        """Test updating a book rating."""
        rating = BookRatingFactory(user=self.user, book=self.book, rating=3)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('bookrating-detail', kwargs={'pk': rating.pk})
        data = {'rating': 5, 'review': 'Updated review'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rating.refresh_from_db()
        self.assertEqual(rating.rating, 5)
    
    def test_delete_rating(self):
        """Test deleting a book rating."""
        rating = BookRatingFactory(user=self.user, book=self.book)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('bookrating-detail', kwargs={'pk': rating.pk})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BookRating.objects.filter(pk=rating.pk).exists())
    
    def test_rating_permissions(self):
        """Test rating permissions (users can only modify their own ratings)."""
        other_user = UserFactory()
        rating = BookRatingFactory(user=other_user, book=self.book)
        
        self.client.force_authenticate(user=self.user)
        url = reverse('bookrating-detail', kwargs={'pk': rating.pk})
        
        # Should not be able to update other user's rating
        response = self.client.patch(url, {'rating': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
class TestAPIThrottling(APITestCase):
    """Test API throttling and rate limiting."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
    
    def test_anonymous_rate_limiting(self):
        """Test rate limiting for anonymous users."""
        url = reverse('book-list')
        
        # Make multiple requests quickly
        responses = []
        for _ in range(10):
            response = self.client.get(url)
            responses.append(response.status_code)
        
        # All requests should succeed for now (rate limit is high for testing)
        self.assertTrue(all(status_code == 200 for status_code in responses))
    
    def test_authenticated_rate_limiting(self):
        """Test rate limiting for authenticated users."""
        self.client.force_authenticate(user=self.user)
        url = reverse('book-list')
        
        # Make multiple requests quickly
        responses = []
        for _ in range(20):
            response = self.client.get(url)
            responses.append(response.status_code)
        
        # All requests should succeed (rate limit is high for authenticated users)
        self.assertTrue(all(status_code == 200 for status_code in responses))


@pytest.mark.django_db
class TestAPIPermissions(APITestCase):
    """Test API permissions and security."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
        self.book = BookFactory()
    
    def test_unauthenticated_access(self):
        """Test access without authentication."""
        # Books should be readable without authentication
        url = reverse('book-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Loans should require authentication
        url = reverse('loan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_librarian_permissions(self):
        """Test librarian-specific permissions."""
        self.client.force_authenticate(user=self.librarian)
        
        # Librarians should be able to create books
        url = reverse('book-list')
        data = {
            'title': 'Librarian Book',
            'author': 'Test Author',
            'isbn': '9781234567890',
            'publisher': 'Test Publisher',
            'publication_date': '2023-01-01',
            'genre': 'fiction',
            'pages': 250,
            'total_copies': 3
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_user_permissions(self):
        """Test regular user permissions."""
        self.client.force_authenticate(user=self.user)
        
        # Regular users should not be able to create books
        url = reverse('book-list')
        data = {
            'title': 'User Book',
            'author': 'Test Author',
            'isbn': '9781234567890'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)