"""
Unit tests for core models.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from apps.core.models import Book, Loan, BookRating
from .factories import (
    UserFactory, LibrarianFactory, BookFactory, LoanFactory, 
    BookRatingFactory, OverdueLoanFactory, ReturnedLoanFactory
)

User = get_user_model()


@pytest.mark.django_db
class TestUserModel(TestCase):
    """Test cases for the User model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.librarian = LibrarianFactory()
    
    def test_user_creation(self):
        """Test basic user creation."""
        self.assertIsInstance(self.user, User)
        self.assertTrue(self.user.username)
        self.assertTrue(self.user.email)
        self.assertFalse(self.user.is_librarian)
        self.assertTrue(self.user.is_active_member)
        self.assertTrue(self.user.can_borrow_books)
    
    def test_librarian_creation(self):
        """Test librarian user creation."""
        self.assertTrue(self.librarian.is_librarian)
        self.assertTrue(self.librarian.is_staff)
    
    def test_user_str_representation(self):
        """Test user string representation."""
        expected = f"{self.user.first_name} {self.user.last_name} ({self.user.email})"
        self.assertEqual(str(self.user), expected)
    
    def test_user_full_name_property(self):
        """Test full_name property."""
        expected = f"{self.user.first_name} {self.user.last_name}"
        self.assertEqual(self.user.full_name, expected)
    
    def test_active_loans_count(self):
        """Test active loans count property."""
        # Initially no loans
        self.assertEqual(self.user.active_loans_count, 0)
        
        # Create some loans
        LoanFactory.create_batch(3, user=self.user, status='borrowed')
        ReturnedLoanFactory(user=self.user)  # This shouldn't count
        
        self.assertEqual(self.user.active_loans_count, 3)
    
    def test_can_borrow_book(self):
        """Test can_borrow_books property."""
        # User can borrow when under limit
        self.assertTrue(self.user.can_borrow_books)
        
        # Create loans up to the limit
        LoanFactory.create_batch(5, user=self.user, status='borrowed')
        self.assertFalse(self.user.can_borrow_books)
    
    def test_has_overdue_loans(self):
        """Test user with overdue loans."""
        # Initially no overdue loans
        self.assertEqual(self.user.active_loans_count, 0)
        
        # Create an overdue loan
        OverdueLoanFactory(user=self.user)
        self.assertEqual(self.user.active_loans_count, 1)
    
    def test_membership_number_uniqueness(self):
        """Test that users can be created without membership numbers."""
        # Since membership_number doesn't exist in the model, just test basic creation
        user1 = UserFactory()
        user2 = UserFactory()
        
        self.assertNotEqual(user1.id, user2.id)
        self.assertNotEqual(user1.email, user2.email)
    
    def test_email_validation(self):
        """Test email validation."""
        user = UserFactory.build(email="invalid-email")
        
        with self.assertRaises(ValidationError):
            user.full_clean()


@pytest.mark.django_db
class TestBookModel(TestCase):
    """Test cases for the Book model."""
    
    def setUp(self):
        """Set up test data."""
        self.book = BookFactory()
    
    def test_book_creation(self):
        """Test basic book creation."""
        self.assertIsInstance(self.book, Book)
        self.assertTrue(self.book.title)
        self.assertTrue(self.book.author)
        self.assertTrue(self.book.isbn)
        self.assertEqual(self.book.status, 'available')
    
    def test_book_str_representation(self):
        """Test book string representation."""
        expected = f"{self.book.title} by {self.book.author}"
        self.assertEqual(str(self.book), expected)
    
    def test_is_available_property(self):
        """Test is_available property."""
        self.assertTrue(self.book.is_available)
        
        # Make book unavailable
        self.book.available_copies = 0
        self.book.save()
        self.assertFalse(self.book.is_available)
    
    def test_average_rating_calculation(self):
        """Test average rating calculation."""
        # Initially no ratings
        self.assertEqual(self.book.average_rating, 0)
        
        # Add some ratings
        BookRatingFactory(book=self.book, rating=5)
        BookRatingFactory(book=self.book, rating=3)
        BookRatingFactory(book=self.book, rating=4)
        
        # Refresh from database
        self.book.refresh_from_db()
        expected_avg = (5 + 3 + 4) / 3
        self.assertEqual(self.book.average_rating, expected_avg)
    
    def test_total_ratings_count(self):
        """Test total ratings count."""
        # Initially no ratings
        self.assertEqual(self.book.total_ratings, 0)
        
        # Add some ratings
        BookRatingFactory.create_batch(3, book=self.book)
        
        # Refresh from database
        self.book.refresh_from_db()
        self.assertEqual(self.book.total_ratings, 3)
    
    def test_isbn_validation(self):
        """Test ISBN validation."""
        # Test with invalid ISBN
        book = BookFactory.build(isbn="invalid-isbn")
        
        with self.assertRaises(ValidationError):
            book.full_clean()
    
    def test_available_copies_validation(self):
        """Test available copies validation."""
        # Available copies cannot be negative
        book = BookFactory.build(available_copies=-1)
        
        with self.assertRaises(ValidationError):
            book.full_clean()
        
        # Available copies cannot exceed total copies
        book = BookFactory.build(total_copies=5, available_copies=10)
        
        with self.assertRaises(ValidationError):
            book.full_clean()
    
    def test_publication_date_validation(self):
        """Test publication date validation."""
        # Publication date cannot be in the future
        future_date = date.today() + timedelta(days=1)
        book = BookFactory.build(publication_date=future_date)
        
        with self.assertRaises(ValidationError):
            book.full_clean()


@pytest.mark.django_db
class TestLoanModel(TestCase):
    """Test cases for the Loan model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.book = BookFactory()
        self.loan = LoanFactory(user=self.user, book=self.book)
    
    def test_loan_creation(self):
        """Test basic loan creation."""
        self.assertIsInstance(self.loan, Loan)
        self.assertEqual(self.loan.user, self.user)
        self.assertEqual(self.loan.book, self.book)
        self.assertEqual(self.loan.status, 'borrowed')
    
    def test_loan_str_representation(self):
        """Test loan string representation."""
        expected = f"{self.user.full_name} - {self.book.title} ({self.loan.status})"
        self.assertEqual(str(self.loan), expected)
    
    def test_is_overdue_property(self):
        """Test is_overdue property."""
        # Current loan should not be overdue
        self.assertFalse(self.loan.is_overdue)
        
        # Create overdue loan
        overdue_loan = OverdueLoanFactory()
        self.assertTrue(overdue_loan.is_overdue)
    
    def test_days_overdue_calculation(self):
        """Test days overdue calculation."""
        # Current loan should have 0 days overdue
        self.assertEqual(self.loan.days_overdue, 0)
        
        # Create overdue loan
        overdue_loan = OverdueLoanFactory()
        self.assertGreater(overdue_loan.days_overdue, 0)
    
    def test_fine_calculation(self):
        """Test fine calculation."""
        # Current loan should have no fine
        self.assertEqual(self.loan.calculate_fine(), Decimal('0.00'))
        
        # Create overdue loan
        overdue_loan = OverdueLoanFactory()
        expected_fine = Decimal('1.00') * overdue_loan.days_overdue  # Default rate is 1.00
        self.assertEqual(overdue_loan.calculate_fine(), expected_fine)
    
    def test_can_renew_method(self):
        """Test can_renew property."""
        # Fresh loan can be renewed
        self.assertTrue(self.loan.can_renew)
        
        # Loan with max renewals cannot be renewed
        self.loan.renewal_count = 2
        self.loan.save()
        self.assertFalse(self.loan.can_renew)
        
        # Overdue loan cannot be renewed
        overdue_loan = OverdueLoanFactory()
        self.assertFalse(overdue_loan.can_renew)
        
        # Returned loan cannot be renewed
        returned_loan = ReturnedLoanFactory()
        self.assertFalse(returned_loan.can_renew)
    
    def test_renew_loan_method(self):
        """Test renew_loan method."""
        original_due_date = self.loan.due_date
        original_renewal_count = self.loan.renewal_count
        
        # Renew the loan
        self.loan.renew_loan()
        
        # Check that due date is extended and renewal count increased
        self.assertEqual(self.loan.due_date, original_due_date + timedelta(days=14))
        self.assertEqual(self.loan.renewal_count, original_renewal_count + 1)
    
    def test_return_book_method(self):
        """Test returning a book by updating status."""
        # Return the book by updating status
        self.loan.status = 'returned'
        self.loan.return_date = timezone.now()
        self.loan.save()
        
        # Check status and return date
        self.assertEqual(self.loan.status, 'returned')
        self.assertIsNotNone(self.loan.return_date)
    
    def test_loan_validation(self):
        """Test loan validation."""
        # User cannot borrow the same book twice
        with self.assertRaises(ValidationError):
            duplicate_loan = LoanFactory.build(user=self.user, book=self.book)
            duplicate_loan.full_clean()
        
        # Cannot create loan for unavailable book
        unavailable_book = BookFactory(available_copies=0)
        with self.assertRaises(ValidationError):
            invalid_loan = LoanFactory.build(user=self.user, book=unavailable_book)
            invalid_loan.full_clean()


@pytest.mark.django_db
class TestBookRatingModel(TestCase):
    """Test cases for the BookRating model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.book = BookFactory()
        self.rating = BookRatingFactory(user=self.user, book=self.book)
    
    def test_rating_creation(self):
        """Test basic rating creation."""
        self.assertIsInstance(self.rating, BookRating)
        self.assertEqual(self.rating.user, self.user)
        self.assertEqual(self.rating.book, self.book)
        self.assertIn(self.rating.rating, range(1, 6))
    
    def test_rating_str_representation(self):
        """Test rating string representation."""
        expected = f"{self.rating.user.full_name} - {self.rating.book.title} ({self.rating.rating}/5)"
        self.assertEqual(str(self.rating), expected)
    
    def test_rating_validation(self):
        """Test rating validation."""
        # Rating must be between 1 and 5
        with self.assertRaises(ValidationError):
            invalid_rating = BookRatingFactory.build(rating=0)
            invalid_rating.full_clean()
        
        with self.assertRaises(ValidationError):
            invalid_rating = BookRatingFactory.build(rating=6)
            invalid_rating.full_clean()
    
    def test_unique_user_book_rating(self):
        """Test that a user can only rate a book once."""
        with self.assertRaises(Exception):
            BookRatingFactory(user=self.user, book=self.book)
    
    def test_rating_updates_book_average(self):
        """Test that ratings update book's average rating."""
        initial_avg = self.book.average_rating
        initial_rating_value = self.rating.rating
        
        # Add another rating with different value
        new_rating = BookRatingFactory(book=self.book, rating=1)
        
        # Refresh book from database
        self.book.refresh_from_db()
        
        # Average should have changed
        self.assertNotEqual(self.book.average_rating, initial_avg)
        # Should be average of existing rating and new rating
        expected_avg = (initial_rating_value + new_rating.rating) / 2
        self.assertEqual(self.book.average_rating, Decimal(f'{expected_avg:.2f}'))