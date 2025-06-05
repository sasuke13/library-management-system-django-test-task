import django_filters
from django.db.models import Q, F
from .models import Book, Loan, User, BookRating


class BookFilter(django_filters.FilterSet):
    """
    Advanced filtering for books with multiple search options.
    """
    title = django_filters.CharFilter(lookup_expr='icontains')
    author = django_filters.CharFilter(lookup_expr='icontains')
    isbn = django_filters.CharFilter(lookup_expr='exact')
    genre = django_filters.ChoiceFilter(choices=Book.GENRE_CHOICES)
    status = django_filters.ChoiceFilter(choices=Book.STATUS_CHOICES)
    language = django_filters.CharFilter(lookup_expr='icontains')
    publisher = django_filters.CharFilter(lookup_expr='icontains')
    
    # Date range filters
    publication_date_after = django_filters.DateFilter(field_name='publication_date', lookup_expr='gte')
    publication_date_before = django_filters.DateFilter(field_name='publication_date', lookup_expr='lte')
    publication_year = django_filters.NumberFilter(field_name='publication_date__year')
    date_added_after = django_filters.DateTimeFilter(field_name='date_added', lookup_expr='gte')
    date_added_before = django_filters.DateTimeFilter(field_name='date_added', lookup_expr='lte')
    
    # Numeric filters
    min_rating = django_filters.NumberFilter(field_name='average_rating', lookup_expr='gte')
    max_rating = django_filters.NumberFilter(field_name='average_rating', lookup_expr='lte')
    min_pages = django_filters.NumberFilter(field_name='pages', lookup_expr='gte')
    max_pages = django_filters.NumberFilter(field_name='pages', lookup_expr='lte')
    
    # Availability filters
    available = django_filters.BooleanFilter(method='filter_available')
    has_copies = django_filters.BooleanFilter(method='filter_has_copies')
    
    # Search across multiple fields
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = Book
        fields = [
            'title', 'author', 'isbn', 'genre', 'status', 'language', 'publisher',
            'publication_date_after', 'publication_date_before', 'publication_year',
            'date_added_after', 'date_added_before',
            'min_rating', 'max_rating', 'min_pages', 'max_pages',
            'available', 'has_copies', 'search'
        ]

    def filter_available(self, queryset, name, value):
        """Filter books by availability status."""
        if value:
            return queryset.filter(status='available', available_copies__gt=0)
        else:
            return queryset.exclude(status='available', available_copies__gt=0)

    def filter_has_copies(self, queryset, name, value):
        """Filter books that have available copies."""
        if value:
            return queryset.filter(available_copies__gt=0)
        else:
            return queryset.filter(available_copies=0)

    def filter_search(self, queryset, name, value):
        """Search across multiple fields."""
        return queryset.filter(
            Q(title__icontains=value) |
            Q(author__icontains=value) |
            Q(isbn__icontains=value) |
            Q(description__icontains=value) |
            Q(publisher__icontains=value)
        )


class LoanFilter(django_filters.FilterSet):
    """
    Advanced filtering for loans with date ranges and status options.
    """
    user = django_filters.ModelChoiceFilter(queryset=User.objects.all())
    book = django_filters.ModelChoiceFilter(queryset=Book.objects.all())
    status = django_filters.ChoiceFilter(choices=Loan.STATUS_CHOICES)
    
    # Date range filters
    loan_date_after = django_filters.DateTimeFilter(field_name='loan_date', lookup_expr='gte')
    loan_date_before = django_filters.DateTimeFilter(field_name='loan_date', lookup_expr='lte')
    due_date_after = django_filters.DateTimeFilter(field_name='due_date', lookup_expr='gte')
    due_date_before = django_filters.DateTimeFilter(field_name='due_date', lookup_expr='lte')
    return_date_after = django_filters.DateTimeFilter(field_name='return_date', lookup_expr='gte')
    return_date_before = django_filters.DateTimeFilter(field_name='return_date', lookup_expr='lte')
    
    # Special filters
    overdue = django_filters.BooleanFilter(method='filter_overdue')
    renewable = django_filters.BooleanFilter(method='filter_renewable')
    has_fine = django_filters.BooleanFilter(method='filter_has_fine')
    fine_paid = django_filters.BooleanFilter()
    
    # Search filters
    user_search = django_filters.CharFilter(method='filter_user_search')
    book_search = django_filters.CharFilter(method='filter_book_search')

    class Meta:
        model = Loan
        fields = [
            'user', 'book', 'status', 'fine_paid',
            'loan_date_after', 'loan_date_before',
            'due_date_after', 'due_date_before',
            'return_date_after', 'return_date_before',
            'overdue', 'renewable', 'has_fine',
            'user_search', 'book_search'
        ]

    def filter_overdue(self, queryset, name, value):
        """Filter overdue loans."""
        from django.utils import timezone
        if value:
            return queryset.filter(status='borrowed', due_date__lt=timezone.now())
        else:
            return queryset.exclude(status='borrowed', due_date__lt=timezone.now())

    def filter_renewable(self, queryset, name, value):
        """Filter loans that can be renewed."""
        from django.utils import timezone
        if value:
            return queryset.filter(
                status='borrowed',
                renewal_count__lt=F('max_renewals'),
                due_date__gte=timezone.now()
            )
        return queryset

    def filter_has_fine(self, queryset, name, value):
        """Filter loans with fines."""
        if value:
            return queryset.filter(fine_amount__gt=0)
        else:
            return queryset.filter(fine_amount=0)

    def filter_user_search(self, queryset, name, value):
        """Search users by name or email."""
        return queryset.filter(
            Q(user__first_name__icontains=value) |
            Q(user__last_name__icontains=value) |
            Q(user__email__icontains=value) |
            Q(user__username__icontains=value)
        )

    def filter_book_search(self, queryset, name, value):
        """Search books by title, author, or ISBN."""
        return queryset.filter(
            Q(book__title__icontains=value) |
            Q(book__author__icontains=value) |
            Q(book__isbn__icontains=value)
        )


class UserFilter(django_filters.FilterSet):
    """
    Filtering for users with membership and activity options.
    """
    first_name = django_filters.CharFilter(lookup_expr='icontains')
    last_name = django_filters.CharFilter(lookup_expr='icontains')
    email = django_filters.CharFilter(lookup_expr='icontains')
    username = django_filters.CharFilter(lookup_expr='icontains')
    is_librarian = django_filters.BooleanFilter()
    is_active_member = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    
    # Date filters
    membership_date_after = django_filters.DateTimeFilter(field_name='membership_date', lookup_expr='gte')
    membership_date_before = django_filters.DateTimeFilter(field_name='membership_date', lookup_expr='lte')
    date_joined_after = django_filters.DateTimeFilter(field_name='date_joined', lookup_expr='gte')
    date_joined_before = django_filters.DateTimeFilter(field_name='date_joined', lookup_expr='lte')
    
    # Activity filters
    has_active_loans = django_filters.BooleanFilter(method='filter_has_active_loans')
    has_overdue_loans = django_filters.BooleanFilter(method='filter_has_overdue_loans')
    
    # Search filter
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'username',
            'is_librarian', 'is_active_member', 'is_active',
            'membership_date_after', 'membership_date_before',
            'date_joined_after', 'date_joined_before',
            'has_active_loans', 'has_overdue_loans', 'search'
        ]

    def filter_has_active_loans(self, queryset, name, value):
        """Filter users with active loans."""
        if value:
            return queryset.filter(loans__status='borrowed').distinct()
        else:
            return queryset.exclude(loans__status='borrowed').distinct()

    def filter_has_overdue_loans(self, queryset, name, value):
        """Filter users with overdue loans."""
        from django.utils import timezone
        if value:
            return queryset.filter(
                loans__status='borrowed',
                loans__due_date__lt=timezone.now()
            ).distinct()
        return queryset

    def filter_search(self, queryset, name, value):
        """Search across multiple user fields."""
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value) |
            Q(username__icontains=value)
        )


class BookRatingFilter(django_filters.FilterSet):
    """
    Filtering for book ratings and reviews.
    """
    user = django_filters.ModelChoiceFilter(queryset=User.objects.all())
    book = django_filters.ModelChoiceFilter(queryset=Book.objects.all())
    rating = django_filters.NumberFilter()
    min_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='gte')
    max_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='lte')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Content filters
    has_review = django_filters.BooleanFilter(method='filter_has_review')
    review_search = django_filters.CharFilter(field_name='review', lookup_expr='icontains')

    class Meta:
        model = BookRating
        fields = [
            'user', 'book', 'rating', 'min_rating', 'max_rating',
            'created_after', 'created_before', 'has_review', 'review_search'
        ]

    def filter_has_review(self, queryset, name, value):
        """Filter ratings that have review text."""
        if value:
            return queryset.exclude(review__isnull=True).exclude(review__exact='')
        else:
            return queryset.filter(Q(review__isnull=True) | Q(review__exact=''))