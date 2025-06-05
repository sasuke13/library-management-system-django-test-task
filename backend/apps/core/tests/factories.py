"""
Factory classes for generating test data using factory_boy.
"""
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from apps.core.models import Book, Loan, BookRating
from datetime import date, timedelta
from django.utils import timezone

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone_number = factory.Faker('phone_number')
    address = factory.Faker('address')
    date_of_birth = factory.Faker('date_of_birth', minimum_age=18, maximum_age=80)
    is_librarian = False
    is_active_member = True
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password for the user."""
        if not create:
            return
        
        password = extracted or 'testpass123'
        obj.set_password(password)
        obj.save()


class LibrarianFactory(UserFactory):
    """Factory for creating Librarian users."""
    
    is_librarian = True
    is_staff = True


class SuperUserFactory(UserFactory):
    """Factory for creating superuser instances."""
    
    is_librarian = True
    is_staff = True
    is_superuser = True


class BookFactory(DjangoModelFactory):
    """Factory for creating Book instances."""
    
    class Meta:
        model = Book
    
    title = factory.Faker('sentence', nb_words=4)
    author = factory.Faker('name')
    isbn = factory.Faker('isbn13')
    publisher = factory.Faker('company')
    publication_date = factory.Faker('date_between', start_date='-50y', end_date='today')
    genre = factory.Faker('random_element', elements=[
        'fiction', 'non_fiction', 'science_fiction', 'fantasy', 'mystery',
        'romance', 'biography', 'history', 'science', 'technology'
    ])
    pages = factory.Faker('random_int', min=50, max=1000)
    description = factory.Faker('text', max_nb_chars=500)
    total_copies = factory.Faker('random_int', min=1, max=10)
    available_copies = factory.LazyAttribute(lambda obj: obj.total_copies)
    status = 'available'
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override _create to mark instance as from factory before saving."""
        obj = model_class(*args, **kwargs)
        obj._from_factory = True
        obj.save()
        return obj


class UnavailableBookFactory(BookFactory):
    """Factory for creating unavailable books."""
    
    available_copies = 0
    status = 'unavailable'


class LoanFactory(DjangoModelFactory):
    """Factory for creating Loan instances."""
    
    class Meta:
        model = Loan
    
    user = factory.SubFactory(UserFactory)
    book = factory.SubFactory(BookFactory)
    loan_date = factory.LazyFunction(timezone.now)
    due_date = factory.LazyAttribute(
        lambda obj: obj.loan_date + timedelta(days=14)
    )
    status = 'borrowed'
    renewal_count = 0


class ReturnedLoanFactory(LoanFactory):
    """Factory for creating returned loans."""
    
    status = 'returned'
    return_date = factory.LazyAttribute(
        lambda obj: obj.loan_date + timedelta(days=10)
    )


class OverdueLoanFactory(LoanFactory):
    """Factory for creating overdue loans."""
    
    loan_date = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=20)
    )
    due_date = factory.LazyAttribute(
        lambda obj: obj.loan_date + timedelta(days=14)
    )
    status = 'borrowed'


class BookRatingFactory(DjangoModelFactory):
    """Factory for creating BookRating instances."""
    
    class Meta:
        model = BookRating
    
    user = factory.SubFactory(UserFactory)
    book = factory.SubFactory(BookFactory)
    rating = factory.Faker('random_int', min=1, max=5)
    review = factory.Faker('text', max_nb_chars=200)
    created_at = factory.LazyFunction(timezone.now)


# Trait factories for specific scenarios
class BookWithRatingsFactory(BookFactory):
    """Factory for creating books with multiple ratings."""
    
    @factory.post_generation
    def ratings(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # If a number is passed, create that many ratings
            for _ in range(extracted):
                BookRatingFactory(book=self)
        else:
            # Default: create 3 ratings
            for _ in range(3):
                BookRatingFactory(book=self)


class UserWithLoansFactory(UserFactory):
    """Factory for creating users with multiple loans."""
    
    @factory.post_generation
    def loans(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # If a number is passed, create that many loans
            for _ in range(extracted):
                LoanFactory(user=self)
        else:
            # Default: create 2 loans
            for _ in range(2):
                LoanFactory(user=self)


class BookWithLoansFactory(BookFactory):
    """Factory for creating books with multiple loans."""
    
    @factory.post_generation
    def loans(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # If a number is passed, create that many loans
            for _ in range(extracted):
                LoanFactory(book=self)
        else:
            # Default: create 2 loans
            for _ in range(2):
                LoanFactory(book=self)