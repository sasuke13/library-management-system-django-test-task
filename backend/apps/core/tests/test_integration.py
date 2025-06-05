"""
Integration tests for complete workflows in the library management system.
"""
import pytest
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Book, Loan, BookRating
from .factories import (
    UserFactory, LibrarianFactory, BookFactory, LoanFactory, 
    BookRatingFactory
)

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestCompleteUserWorkflow(APITestCase):
    """Test complete user workflow from registration to book return."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.book = BookFactory(available_copies=5)
    
    def test_complete_user_journey(self):
        """Test complete user journey: register → login → borrow → return → rate."""
        
        # Step 1: User Registration
        register_url = reverse('register')
        register_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'strongpassword123',
            'password_confirm': 'strongpassword123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '+1234567890',
            'address': '123 Test St',
            'date_of_birth': '1990-01-01'
        }
        
        response = self.client.post(register_url, register_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data['tokens'])
        
        # Extract user ID and tokens
        access_token = response.data['tokens']['access']
        user_id = response.data['user']['id']
        
        # Step 2: User Login (alternative path)
        login_url = reverse('login')
        login_data = {
            'username': 'testuser',
            'password': 'strongpassword123'
        }
        
        response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 3: Browse Books
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        books_url = reverse('book-list')
        response = self.client.get(books_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # Step 4: View Book Details
        book_detail_url = reverse('book-detail', kwargs={'pk': self.book.pk})
        response = self.client.get(book_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.book.id)
        
        # Step 5: Borrow Book
        borrow_url = reverse('book-borrow', kwargs={'pk': self.book.pk})
        response = self.client.post(borrow_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify loan was created
        loan_id = response.data['id']
        self.assertTrue(Loan.objects.filter(id=loan_id, user_id=user_id).exists())
        
        # Verify book availability decreased
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 4)
        
        # Step 6: View User's Loans
        loans_url = reverse('loan-list')
        response = self.client.get(loans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Step 7: Return Book
        return_url = reverse('loan-return', kwargs={'pk': loan_id})
        response = self.client.post(return_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify loan status changed
        loan = Loan.objects.get(id=loan_id)
        self.assertEqual(loan.status, 'returned')
        
        # Verify book availability increased
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 5)
        
        # Step 8: Rate the Book
        rating_url = reverse('bookrating-list')
        rating_data = {
            'book': self.book.id,
            'rating': 5,
            'review': 'Excellent book! Highly recommended.'
        }
        
        response = self.client.post(rating_url, rating_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify rating was created
        self.assertTrue(BookRating.objects.filter(
            user_id=user_id, 
            book=self.book
        ).exists())
        
        # Step 9: View Loan History
        history_url = reverse('loan-history')
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


@pytest.mark.django_db
@pytest.mark.integration
class TestLibrarianWorkflow(APITestCase):
    """Test librarian workflow for book and loan management."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.librarian = LibrarianFactory()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.librarian)
    
    def test_librarian_book_management_workflow(self):
        """Test librarian workflow: create book → manage loans → generate reports."""
        
        # Step 1: Create a New Book
        books_url = reverse('book-list')
        book_data = {
            'title': 'New Library Book',
            'author': 'Famous Author',
            'isbn': '9781234567890',
            'publisher': 'Great Publisher',
            'publication_date': '2023-01-01',
            'genre': 'fiction',
            'description': 'A wonderful new book for our library.',
            'pages': 300,
            'total_copies': 10
        }
        
        response = self.client.post(books_url, book_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book_id = response.data['id']
        
        # Step 2: Verify Book Creation
        book = Book.objects.get(id=book_id)
        self.assertEqual(book.title, 'New Library Book')
        self.assertEqual(book.available_copies, 10)
        
        # Step 3: User Borrows the Book (simulate)
        self.client.force_authenticate(user=self.user)
        borrow_url = reverse('book-borrow', kwargs={'pk': book_id})
        response = self.client.post(borrow_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan_id = response.data['id']
        
        # Step 4: Librarian Views All Loans
        self.client.force_authenticate(user=self.librarian)
        loans_url = reverse('loan-list')
        response = self.client.get(loans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see the loan
        loan_ids = [loan['id'] for loan in response.data['results']]
        self.assertIn(loan_id, loan_ids)
        
        # Step 5: Librarian Updates Book Information
        book_detail_url = reverse('book-detail', kwargs={'pk': book_id})
        update_data = {
            'description': 'Updated description with more details.',
            'total_copies': 12
        }
        
        response = self.client.patch(book_detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        book.refresh_from_db()
        self.assertEqual(book.total_copies, 12)
        self.assertIn('Updated description', book.description)
        
        # Step 6: Check Book Availability After Update
        # Available copies should be total - borrowed
        self.assertEqual(book.available_copies, 11)  # 12 - 1 borrowed


@pytest.mark.django_db
@pytest.mark.integration
class TestOverdueWorkflow(APITestCase):
    """Test overdue loan workflow and fine calculation."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
        self.book = BookFactory()
    
    def test_overdue_loan_workflow(self):
        """Test workflow for overdue loans and fine calculation."""
        
        # Step 1: Create an overdue loan (simulate past date)
        past_date = timezone.now() - timedelta(days=20)
        due_date = past_date + timedelta(days=14)
        
        loan = LoanFactory(
            user=self.user,
            book=self.book,
            loan_date=past_date,
            due_date=due_date,
            status='borrowed'
        )
        
        # Step 2: User checks their loans
        self.client.force_authenticate(user=self.user)
        loans_url = reverse('loan-list')
        response = self.client.get(loans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 3: Check overdue loans endpoint
        overdue_url = reverse('loan-overdue')
        response = self.client.get(overdue_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Step 4: Verify fine calculation
        loan.refresh_from_db()
        expected_fine = loan.calculate_fine()
        self.assertGreater(expected_fine, 0)
        
        # Step 5: Try to renew overdue loan (should fail)
        renew_url = reverse('loan-renew', kwargs={'pk': loan.pk})
        response = self.client.post(renew_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Step 6: Return the overdue book
        return_url = reverse('loan-return', kwargs={'pk': loan.pk})
        response = self.client.post(return_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 7: Verify loan is returned
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'returned')
        self.assertIsNotNone(loan.return_date)


@pytest.mark.django_db
@pytest.mark.integration
class TestSearchAndFilterWorkflow(APITestCase):
    """Test search and filtering functionality across the system."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        
        # Create diverse books for testing
        self.fiction_book = BookFactory(
            title="The Great Adventure",
            author="John Smith",
            genre="fiction",
            publication_date="2020-01-01"
        )
        
        self.scifi_book = BookFactory(
            title="Space Odyssey",
            author="Jane Doe",
            genre="science_fiction",
            publication_date="2022-01-01"
        )
        
        self.history_book = BookFactory(
            title="Ancient Civilizations",
            author="Dr. History",
            genre="history",
            publication_date="2019-01-01"
        )
    
    def test_comprehensive_search_workflow(self):
        """Test comprehensive search and filter workflow."""
        
        books_url = reverse('book-list')
        
        # Step 1: Search by title
        response = self.client.get(books_url, {'search': 'Adventure'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [book['title'] for book in response.data['results']]
        self.assertIn('The Great Adventure', titles)
        
        # Step 2: Search by author
        response = self.client.get(books_url, {'search': 'Jane Doe'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        authors = [book['author'] for book in response.data['results']]
        self.assertIn('Jane Doe', authors)
        
        # Step 3: Filter by genre
        response = self.client.get(books_url, {'genre': 'science_fiction'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        genres = [book['genre'] for book in response.data['results']]
        self.assertTrue(all(genre == 'science_fiction' for genre in genres))
        
        # Step 4: Filter by publication year
        response = self.client.get(books_url, {'publication_year': '2020'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        years = [book['publication_date'][:4] for book in response.data['results']]
        self.assertTrue(all(year == '2020' for year in years))
        
        # Step 5: Combined search and filter
        response = self.client.get(books_url, {
            'search': 'Space',
            'genre': 'science_fiction'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Space Odyssey')
        
        # Step 6: Filter by availability
        # Make one book unavailable
        self.fiction_book.available_copies = 0
        self.fiction_book.save()
        
        response = self.client.get(books_url, {'available': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should not include the unavailable book
        titles = [book['title'] for book in response.data['results']]
        self.assertNotIn('The Great Adventure', titles)


@pytest.mark.django_db
@pytest.mark.integration
class TestRatingAndReviewWorkflow(APITestCase):
    """Test rating and review system workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.book = BookFactory()
    
    def test_rating_aggregation_workflow(self):
        """Test rating aggregation and book recommendation workflow."""
        
        # Step 1: Multiple users rate the same book
        ratings_data = [
            (self.user1, 5, "Excellent book!"),
            (self.user2, 4, "Very good read."),
            (self.user3, 3, "Decent book.")
        ]
        
        rating_url = reverse('bookrating-list')
        
        for user, rating, review in ratings_data:
            self.client.force_authenticate(user=user)
            data = {
                'book': self.book.id,
                'rating': rating,
                'review': review
            }
            response = self.client.post(rating_url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 2: Check book's updated average rating
        book_detail_url = reverse('book-detail', kwargs={'pk': self.book.pk})
        response = self.client.get(book_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Average should be (5 + 4 + 3) / 3 = 4.0
        expected_average = 4.0
        self.assertEqual(float(response.data['average_rating']), expected_average)
        self.assertEqual(response.data['total_ratings'], 3)
        
        # Step 3: User updates their rating
        self.client.force_authenticate(user=self.user1)
        rating = BookRating.objects.get(user=self.user1, book=self.book)
        rating_detail_url = reverse('bookrating-detail', kwargs={'pk': rating.pk})
        
        update_data = {
            'rating': 2,
            'review': "Changed my mind, not so great."
        }
        
        response = self.client.patch(rating_detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 4: Verify updated average
        response = self.client.get(book_detail_url)
        # New average should be (2 + 4 + 3) / 3 = 3.0
        expected_average = 3.0
        self.assertEqual(float(response.data['average_rating']), expected_average)
        
        # Step 5: Filter books by minimum rating
        books_url = reverse('book-list')
        response = self.client.get(books_url, {'min_rating': '3.5'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Our book with 3.0 rating should not appear
        book_ids = [book['id'] for book in response.data['results']]
        self.assertNotIn(self.book.id, book_ids)


@pytest.mark.django_db
@pytest.mark.integration
class TestConcurrencyAndEdgeCases(TransactionTestCase):
    """Test concurrency scenarios and edge cases."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.book = BookFactory(available_copies=1)  # Only one copy
    
    def test_concurrent_borrowing_edge_case(self):
        """Test edge case where multiple users try to borrow the last copy."""
        
        # Both users try to borrow the same last copy
        borrow_url = reverse('book-borrow', kwargs={'pk': self.book.pk})
        
        # User 1 borrows successfully
        self.client.force_authenticate(user=self.user1)
        response1 = self.client.post(borrow_url)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # User 2 should fail to borrow (no copies left)
        self.client.force_authenticate(user=self.user2)
        response2 = self.client.post(borrow_url)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify only one loan exists
        self.assertEqual(Loan.objects.filter(book=self.book).count(), 1)
        
        # Verify book availability
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)
    
    def test_borrowing_limit_edge_case(self):
        """Test borrowing limit enforcement."""
        
        # Create books for user to borrow up to limit
        books = BookFactory.create_batch(6)  # More than the limit of 5
        
        self.client.force_authenticate(user=self.user1)
        
        successful_borrows = 0
        for book in books:
            borrow_url = reverse('book-borrow', kwargs={'pk': book.pk})
            response = self.client.post(borrow_url)
            
            if response.status_code == status.HTTP_201_CREATED:
                successful_borrows += 1
            else:
                # Should fail after reaching limit
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                break
        
        # Should have borrowed exactly 5 books (the limit)
        self.assertEqual(successful_borrows, 5)
        self.assertEqual(self.user1.active_loans_count, 5)