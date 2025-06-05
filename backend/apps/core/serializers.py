from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import bleach
from .models import User, Book, Loan, BookRating


def sanitize_html(value):
    """
    Sanitize HTML content to prevent XSS attacks.
    Allows basic formatting tags but removes potentially dangerous content.
    """
    if not value:
        return value
    
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
    allowed_attributes = {}
    
    return bleach.clean(value, tags=allowed_tags, attributes=allowed_attributes, strip=True)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with password validation.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'first_name', 'last_name', 
            'phone_number', 'address', 'date_of_birth',
            'password', 'password_confirm'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_first_name(self, value):
        """Sanitize first name to prevent XSS attacks."""
        return sanitize_html(value)

    def validate_last_name(self, value):
        """Sanitize last name to prevent XSS attacks."""
        return sanitize_html(value)

    def validate_address(self, value):
        """Sanitize address to prevent XSS attacks."""
        return sanitize_html(value)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login authentication.
    """
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        email = attrs.get('email')
        password = attrs.get('password')

        if not password:
            raise serializers.ValidationError('Password is required.')
        
        if not (username or email):
            raise serializers.ValidationError('Must include username or email.')

        # Since USERNAME_FIELD is 'email', we need to find the user's email
        user = None
        login_email = email
        
        # If username is provided, find the user's email
        if username and not email:
            try:
                from .models import User
                user_obj = User.objects.get(username=username)
                login_email = user_obj.email
            except User.DoesNotExist:
                pass
        
        # Authenticate using email (which is the USERNAME_FIELD)
        if login_email:
            user = authenticate(username=login_email, password=password)
            
        if not user:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')
        attrs['user'] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile management.
    """
    full_name = serializers.ReadOnlyField()
    active_loans_count = serializers.ReadOnlyField()
    can_borrow_books = serializers.ReadOnlyField()
    membership_date = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'phone_number', 'address', 'date_of_birth', 'is_librarian',
            'membership_date', 'is_active_member', 'active_loans_count', 'can_borrow_books'
        ]
        read_only_fields = ['id', 'email', 'username', 'is_librarian', 'membership_date']


class BookRatingSerializer(serializers.ModelSerializer):
    """
    Serializer for book ratings and reviews.
    """
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = BookRating
        fields = ['id', 'book', 'user', 'user_name', 'rating', 'review', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_review(self, value):
        """Sanitize review content to prevent XSS attacks."""
        return sanitize_html(value)

    def create(self, validated_data):
        user = self.context['request'].user
        book = validated_data['book']
        
        # Check if user already rated this book
        existing_rating = BookRating.objects.filter(user=user, book=book).first()
        if existing_rating:
            raise serializers.ValidationError("You have already rated this book.")
        
        validated_data['user'] = user
        return super().create(validated_data)


class BookSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for book management.
    """
    is_available = serializers.ReadOnlyField()
    added_by_name = serializers.CharField(source='added_by.full_name', read_only=True)
    ratings = BookRatingSerializer(many=True, read_only=True)
    user_rating = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'isbn', 'publisher', 'publication_date',
            'genre', 'pages', 'language', 'edition', 'status', 'total_copies',
            'available_copies', 'description', 'cover_image', 'shelf_location',
            'date_added', 'last_updated', 'added_by', 'added_by_name',
            'average_rating', 'total_ratings', 'times_borrowed', 'is_available',
            'ratings', 'user_rating'
        ]
        read_only_fields = [
            'id', 'date_added', 'last_updated', 'added_by', 'average_rating',
            'total_ratings', 'times_borrowed', 'is_available'
        ]

    def get_user_rating(self, obj):
        """Get current user's rating for this book."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                rating = obj.ratings.get(user=request.user)
                return BookRatingSerializer(rating).data
            except BookRating.DoesNotExist:
                return None
        return None

    def validate_title(self, value):
        """Sanitize book title to prevent XSS attacks."""
        return sanitize_html(value)

    def validate_author(self, value):
        """Sanitize author name to prevent XSS attacks."""
        return sanitize_html(value)

    def validate_description(self, value):
        """Sanitize book description to prevent XSS attacks."""
        return sanitize_html(value)

    def validate_publisher(self, value):
        """Sanitize publisher name to prevent XSS attacks."""
        return sanitize_html(value)

    def create(self, validated_data):
        validated_data['added_by'] = self.context['request'].user
        # Create the book instance
        book = Book(**validated_data)
        # Save with force_api_behavior to ensure proper available_copies handling
        book.save(force_api_behavior=True)
        return book


class BookListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for book listings.
    """
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'isbn', 'genre', 'status',
            'available_copies', 'average_rating', 'total_ratings',
            'times_borrowed', 'is_available', 'cover_image', 'publication_date'
        ]


class LoanSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for loan management.
    """
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    book_author = serializers.CharField(source='book.author', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.full_name', read_only=True)
    returned_to_name = serializers.CharField(source='returned_to.full_name', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    days_overdue = serializers.ReadOnlyField()
    can_renew = serializers.ReadOnlyField()

    class Meta:
        model = Loan
        fields = [
            'id', 'user', 'user_name', 'book', 'book_title', 'book_author',
            'loan_date', 'due_date', 'return_date', 'status', 'renewal_count',
            'max_renewals', 'issued_by', 'issued_by_name', 'returned_to',
            'returned_to_name', 'notes', 'fine_amount', 'fine_paid',
            'is_overdue', 'days_overdue', 'can_renew', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'loan_date', 'issued_by', 'returned_to', 'fine_amount',
            'created_at', 'updated_at', 'is_overdue', 'days_overdue', 'can_renew'
        ]

    def validate(self, attrs):
        """Validate loan creation."""
        user = attrs.get('user', getattr(self.instance, 'user', None))
        book = attrs.get('book', getattr(self.instance, 'book', None))
        
        if self.instance is None:  # Creating new loan
            # Check if user can borrow books
            if not user.can_borrow_books:
                raise serializers.ValidationError(
                    "User has reached maximum borrowing limit or is not an active member."
                )
            
            # Check if book is available
            if not book.is_available:
                raise serializers.ValidationError("Book is not available for borrowing.")
            
            # Check if user already has this book borrowed
            if user.loans.filter(book=book, status='borrowed').exists():
                raise serializers.ValidationError("User already has this book borrowed.")
        
        return attrs

    def create(self, validated_data):
        validated_data['issued_by'] = self.context['request'].user
        return super().create(validated_data)


class LoanCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating loans.
    """
    due_date = serializers.DateTimeField(required=False)
    
    class Meta:
        model = Loan
        fields = ['book', 'due_date', 'notes']

    def validate_book(self, value):
        if not value.is_available:
            raise serializers.ValidationError("Book is not available for borrowing.")
        return value

    def create(self, validated_data):
        from django.utils import timezone
        from datetime import timedelta
        
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Auto-calculate due_date if not provided (14 days from now)
        if 'due_date' not in validated_data:
            validated_data['due_date'] = timezone.now() + timedelta(days=14)
        
        # Only set issued_by if the user is a librarian
        if user.is_librarian:
            validated_data['issued_by'] = user
        
        return super().create(validated_data)


class LoanReturnSerializer(serializers.Serializer):
    """
    Serializer for returning books.
    """
    notes = serializers.CharField(required=False, allow_blank=True)
    condition = serializers.ChoiceField(
        choices=[('good', 'Good'), ('damaged', 'Damaged'), ('lost', 'Lost')],
        default='good'
    )


class LoanRenewalSerializer(serializers.Serializer):
    """
    Serializer for renewing loans.
    """
    days = serializers.IntegerField(default=14, min_value=1, max_value=30)


class UserLoanHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for user loan history.
    """
    book_title = serializers.CharField(source='book.title', read_only=True)
    book_author = serializers.CharField(source='book.author', read_only=True)
    book_isbn = serializers.CharField(source='book.isbn', read_only=True)

    class Meta:
        model = Loan
        fields = [
            'id', 'book_title', 'book_author', 'book_isbn', 'loan_date',
            'due_date', 'return_date', 'status', 'renewal_count',
            'fine_amount', 'fine_paid'
        ]


class OverdueLoanSerializer(serializers.ModelSerializer):
    """
    Serializer for overdue loan management.
    """
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    days_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Loan
        fields = [
            'id', 'user', 'user_name', 'user_email', 'book', 'book_title',
            'loan_date', 'due_date', 'days_overdue', 'fine_amount', 'fine_paid'
        ]