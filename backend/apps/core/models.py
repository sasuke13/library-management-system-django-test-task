from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class User(AbstractUser):
    """
    Extended User model with additional fields for library management.
    """
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    is_librarian = models.BooleanField(default=False)
    membership_date = models.DateTimeField(auto_now_add=True)
    is_active_member = models.BooleanField(default=True)
    
    # Override username requirement to use email as primary identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def active_loans_count(self):
        return self.loans.filter(status='borrowed').count()
    
    @property
    def can_borrow_books(self):
        """Check if user can borrow more books (max 5 active loans)"""
        return self.is_active_member and self.active_loans_count < 5


class Book(models.Model):
    """
    Book model representing books in the library catalog.
    """
    GENRE_CHOICES = [
        ('fiction', 'Fiction'),
        ('non_fiction', 'Non-Fiction'),
        ('mystery', 'Mystery'),
        ('romance', 'Romance'),
        ('science_fiction', 'Science Fiction'),
        ('fantasy', 'Fantasy'),
        ('biography', 'Biography'),
        ('history', 'History'),
        ('science', 'Science'),
        ('technology', 'Technology'),
        ('self_help', 'Self Help'),
        ('children', 'Children'),
        ('young_adult', 'Young Adult'),
        ('poetry', 'Poetry'),
        ('drama', 'Drama'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ]
    
    # Basic book information
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13, unique=True)
    publisher = models.CharField(max_length=100)
    publication_date = models.DateField()
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES)
    
    # Physical details
    pages = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    language = models.CharField(max_length=50, default='English')
    edition = models.CharField(max_length=50, blank=True, null=True)
    
    # Library management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    total_copies = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    available_copies = models.PositiveIntegerField(default=1, validators=[MinValueValidator(0)])
    
    # Additional information
    description = models.TextField(blank=True, null=True)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    shelf_location = models.CharField(max_length=50, blank=True, null=True)
    
    # Metadata
    date_added = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='books_added')
    
    # Rating and popularity
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'),
                                       validators=[MinValueValidator(0), MaxValueValidator(5)])
    total_ratings = models.PositiveIntegerField(default=0)
    times_borrowed = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'books'
        verbose_name = 'Book'
        verbose_name_plural = 'Books'
        ordering = ['title', 'author']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['author']),
            models.Index(fields=['isbn']),
            models.Index(fields=['genre']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        """Override save to set available_copies equal to total_copies for new books."""
        is_new = self.pk is None
        force_api_behavior = kwargs.pop('force_api_behavior', False)
        
        if is_new:  # New book
            # For API creation: if available_copies is default (1) and total_copies > 1,
            # set available_copies = total_copies, but only if this is coming from API
            if (self.available_copies == 1 and self.total_copies > 1 and
                (force_api_behavior or not hasattr(self, '_from_factory'))):
                # This looks like API creation where total_copies was set but available_copies wasn't
                self.available_copies = self.total_copies
            # If available_copies != 1 or _from_factory is set, keep the explicit value
        else:  # Existing book - check if total_copies changed
            try:
                old_book = Book.objects.get(pk=self.pk)
                if old_book.total_copies != self.total_copies:
                    # Adjust available_copies by the difference
                    difference = self.total_copies - old_book.total_copies
                    self.available_copies = old_book.available_copies + difference
            except Book.DoesNotExist:
                pass
        
        # Update status based on available copies
        if self.available_copies == 0:
            if self.status == 'available':
                self.status = 'borrowed'
        elif self.available_copies > 0:
            if self.status == 'borrowed':
                self.status = 'available'
        
        super().save(*args, **kwargs)
    
    @property
    def is_available(self):
        """Check if book is available for borrowing"""
        return self.status == 'available' and self.available_copies > 0
    
    def update_availability(self):
        """Update book status based on available copies"""
        if self.available_copies == 0:
            if self.status == 'available':
                self.status = 'borrowed'
        elif self.available_copies > 0:
            if self.status == 'borrowed':
                self.status = 'available'
        self.save()
    
    def update_average_rating(self):
        """Update the average rating for this book"""
        ratings = self.ratings.all()
        if ratings.exists():
            total_rating = sum(rating.rating for rating in ratings)
            self.average_rating = Decimal(str(total_rating / ratings.count()))
            self.total_ratings = ratings.count()
        else:
            self.average_rating = Decimal('0.00')
            self.total_ratings = 0
        self.save()


class Loan(models.Model):
    """
    Loan model representing book borrowing transactions.
    """
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ]
    
    # Loan relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='loans')
    
    # Loan dates
    loan_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    return_date = models.DateTimeField(blank=True, null=True)
    
    # Loan status and management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    renewal_count = models.PositiveIntegerField(default=0)
    max_renewals = models.PositiveIntegerField(default=2)
    
    # Staff management
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='loans_issued', limit_choices_to={'is_librarian': True})
    returned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='loans_returned', limit_choices_to={'is_librarian': True})
    
    # Additional information
    notes = models.TextField(blank=True, null=True)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fine_paid = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loans'
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'
        ordering = ['-loan_date']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['book', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['loan_date']),
        ]
        unique_together = ['user', 'book', 'loan_date']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Set due date if not provided (default 14 days from loan date)
        if not self.due_date:
            self.due_date = timezone.now() + timedelta(days=14)
        
        # Update book availability when loan is created or status changes
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            old_loan = Loan.objects.get(pk=self.pk)
            old_status = old_loan.status
        
        super().save(*args, **kwargs)
        
        # Update book availability
        if is_new and self.status == 'borrowed':
            # New loan - decrease available copies
            if self.book.available_copies > 0:
                self.book.available_copies -= 1
                self.book.times_borrowed += 1
                self.book.update_availability()
        elif old_status == 'borrowed' and self.status in ['returned', 'lost', 'damaged']:
            # Book returned or lost - increase available copies
            if self.status == 'returned':
                self.book.available_copies += 1
                self.book.update_availability()
    
    @property
    def is_overdue(self):
        """Check if loan is overdue"""
        return (self.status == 'borrowed' and timezone.now() > self.due_date) or self.status == 'overdue'
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if self.is_overdue:
            return (timezone.now() - self.due_date).days
        return 0
    
    @property
    def can_renew(self):
        """Check if loan can be renewed"""
        return (self.status == 'borrowed' and 
                self.renewal_count < self.max_renewals and 
                not self.is_overdue)
    
    def renew_loan(self, days=14):
        """Renew the loan for additional days"""
        if self.can_renew:
            self.due_date = self.due_date + timedelta(days=days)
            self.renewal_count += 1
            self.save()
            return True
        return False
    
    def calculate_fine(self, daily_rate=1.00):
        """Calculate fine for overdue books"""
        if self.is_overdue:
            fine = self.days_overdue * Decimal(str(daily_rate))
            self.fine_amount = fine
            self.save()
            return fine
        return Decimal('0.00')


class BookRating(models.Model):
    """
    Model for user ratings and reviews of books.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_ratings')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'book_ratings'
        verbose_name = 'Book Rating'
        verbose_name_plural = 'Book Ratings'
        unique_together = ['user', 'book']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} ({self.rating}/5)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update book's average rating
        self.book.update_average_rating()
    
    def delete(self, *args, **kwargs):
        book = self.book
        result = super().delete(*args, **kwargs)
        # Update book's average rating after deletion
        book.update_average_rating()
        return result
