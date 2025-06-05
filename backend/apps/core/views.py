from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination

from .models import User, Book, Loan, BookRating
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    BookSerializer, BookListSerializer, LoanSerializer, LoanCreateSerializer,
    LoanReturnSerializer, LoanRenewalSerializer, UserLoanHistorySerializer,
    OverdueLoanSerializer, BookRatingSerializer
)
from .permissions import (
    IsLibrarianOrReadOnly, IsOwnerOrLibrarian, IsOwnerOnly, IsLibrarianOnly,
    IsAuthenticatedOrCreateOnly, CanBorrowBooks, CanManageOwnLoans, CanRateBooks
)
from .filters import BookFilter, LoanFilter, UserFilter, BookRatingFilter


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for API responses.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserRegistrationView(APIView):
    """
    API endpoint for user registration.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'User registered successfully',
                'user': UserProfileSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(TokenObtainPairView):
    """
    API endpoint for user login with JWT tokens.
    """
    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Login successful',
                'user': UserProfileSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_200_OK)
        # Check if the error is about invalid credentials
        if 'non_field_errors' in serializer.errors:
            for error in serializer.errors['non_field_errors']:
                if 'Invalid credentials' in str(error):
                    return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    """
    API endpoint for user logout (blacklist refresh token).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsLibrarianOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserFilter

    @action(detail=False, methods=['get', 'put', 'patch'])
    def profile(self, request):
        """Get or update current user's profile."""
        # Explicit authentication check - must be authenticated
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsLibrarianOnly])
    def toggle_librarian(self, request, pk=None):
        """Toggle librarian status for a user."""
        user = self.get_object()
        user.is_librarian = not user.is_librarian
        user.save()
        return Response({
            'message': f'User {"promoted to" if user.is_librarian else "demoted from"} librarian',
            'is_librarian': user.is_librarian
        })

    @action(detail=True, methods=['post'], permission_classes=[IsLibrarianOnly])
    def toggle_active(self, request, pk=None):
        """Toggle active membership status for a user."""
        user = self.get_object()
        user.is_active_member = not user.is_active_member
        user.save()
        return Response({
            'message': f'User membership {"activated" if user.is_active_member else "deactivated"}',
            'is_active_member': user.is_active_member
        })


class BookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for book management with search and filtering.
    """
    queryset = Book.objects.all()
    permission_classes = [IsLibrarianOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = BookFilter

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return BookListSerializer
        return BookSerializer

    def get_queryset(self):
        """Return all books - filtering is handled by BookFilter."""
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Book.objects.none()
        return Book.objects.all()

    def perform_create(self, serializer):
        """Set the added_by field when creating a book."""
        serializer.save(added_by=self.request.user)

    @action(detail=True, methods=['get'])
    def ratings(self, request, pk=None):
        """Get all ratings for a specific book."""
        book = self.get_object()
        ratings = book.ratings.all().order_by('-created_at')
        serializer = BookRatingSerializer(ratings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def rate(self, request, pk=None):
        """Rate a book."""
        book = self.get_object()
        
        # Add book to request data
        data = request.data.copy()
        data['book'] = book.pk
        
        serializer = BookRatingSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            # Check if user already rated this book
            existing_rating = BookRating.objects.filter(user=request.user, book=book).first()
            if existing_rating:
                # Update existing rating
                serializer = BookRatingSerializer(existing_rating, data=data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
            else:
                # Create new rating
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most popular books (most borrowed)."""
        books = Book.objects.filter(times_borrowed__gt=0).order_by('-times_borrowed')[:10]
        serializer = BookListSerializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        """Get top-rated books."""
        books = Book.objects.filter(total_ratings__gt=0).order_by('-average_rating')[:10]
        serializer = BookListSerializer(books, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def borrow(self, request, pk=None):
        """Borrow a book (create a loan)."""
        from django.db import transaction
        
        book = self.get_object()
        
        # Check if user can borrow books
        if not request.user.can_borrow_books:
            return Response(
                {'error': 'User cannot borrow books'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use atomic transaction to prevent race conditions
        try:
            with transaction.atomic():
                # Re-fetch book with select_for_update to lock the row
                book = Book.objects.select_for_update().get(pk=book.pk)
                
                # Check if book is available (inside the transaction)
                if not book.is_available:
                    return Response(
                        {'error': 'Book is not available for borrowing'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create loan
                loan_data = {'book': book.pk}
                serializer = LoanCreateSerializer(data=loan_data, context={'request': request})
                
                if serializer.is_valid():
                    loan = serializer.save()
                    response_serializer = LoanSerializer(loan, context={'request': request})
                    return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {'error': 'Failed to borrow book'},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for loan management.
    """
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer
    permission_classes = [CanManageOwnLoans]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = LoanFilter

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Loan.objects.none()
        
        if self.request.user.is_authenticated and getattr(self.request.user, 'is_librarian', False):
            return Loan.objects.all()
        elif self.request.user.is_authenticated:
            return Loan.objects.filter(user=self.request.user)
        return Loan.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return LoanCreateSerializer
        return LoanSerializer

    def create(self, request, *args, **kwargs):
        """Create a new loan (borrow a book)."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            loan = serializer.save()
            response_serializer = LoanSerializer(loan, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_name='return')
    def return_book(self, request, pk=None):
        """Return a borrowed book."""
        loan = self.get_object()
        
        # Check if user can return this book (owner or librarian)
        if not request.user.is_librarian and loan.user != request.user:
            return Response(
                {'error': 'You can only return your own books'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if loan.status not in ['borrowed', 'overdue']:
            return Response(
                {'error': 'Book is not currently borrowed or overdue'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = LoanReturnSerializer(data=request.data)
        if serializer.is_valid():
            condition = serializer.validated_data.get('condition', 'good')
            notes = serializer.validated_data.get('notes', '')
            
            # Update loan status based on condition
            if condition == 'good':
                loan.status = 'returned'
            elif condition == 'damaged':
                loan.status = 'damaged'
            elif condition == 'lost':
                loan.status = 'lost'
            
            loan.return_date = timezone.now()
            loan.returned_to = request.user
            if notes:
                loan.notes = notes
            
            # Calculate fine if overdue
            if loan.is_overdue:
                loan.calculate_fine()
            
            loan.save()
            
            response_serializer = LoanSerializer(loan, context={'request': request})
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_name='renew')
    def renew(self, request, pk=None):
        """Renew a loan."""
        loan = self.get_object()
        
        if not loan.can_renew:
            return Response(
                {'error': 'Loan cannot be renewed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = LoanRenewalSerializer(data=request.data)
        if serializer.is_valid():
            days = serializer.validated_data.get('days', 14)
            success = loan.renew_loan(days)
            
            if success:
                response_serializer = LoanSerializer(loan, context={'request': request})
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to renew loan'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_loans(self, request):
        """Get current user's loan history."""
        loans = Loan.objects.filter(user=request.user).order_by('-loan_date')
        serializer = UserLoanHistorySerializer(loans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_name='history')
    def history(self, request):
        """Get current user's loan history (alias for my_loans)."""
        loans = Loan.objects.filter(user=request.user).order_by('-loan_date')
        page = self.paginate_queryset(loans)
        if page is not None:
            serializer = UserLoanHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = UserLoanHistorySerializer(loans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current user's active loans."""
        loans = Loan.objects.filter(user=request.user, status='borrowed')
        serializer = LoanSerializer(loans, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue loans (all for librarians, own for users)."""
        base_query = Loan.objects.filter(
            status='borrowed',
            due_date__lt=timezone.now()
        )
        
        # Filter by user permissions
        if request.user.is_librarian:
            overdue_loans = base_query.order_by('due_date')
        else:
            overdue_loans = base_query.filter(user=request.user).order_by('due_date')
        
        # Update status to overdue
        for loan in overdue_loans:
            if loan.status == 'borrowed':
                loan.status = 'overdue'
                loan.calculate_fine()
                loan.save()
        
        # Paginate the results
        page = self.paginate_queryset(overdue_loans)
        if page is not None:
            serializer = OverdueLoanSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = OverdueLoanSerializer(overdue_loans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsLibrarianOnly])
    def statistics(self, request):
        """Get loan statistics."""
        total_loans = Loan.objects.count()
        active_loans = Loan.objects.filter(status='borrowed').count()
        overdue_loans = Loan.objects.filter(status='overdue').count()
        returned_loans = Loan.objects.filter(status='returned').count()
        
        return Response({
            'total_loans': total_loans,
            'active_loans': active_loans,
            'overdue_loans': overdue_loans,
            'returned_loans': returned_loans,
            'return_rate': (returned_loans / total_loans * 100) if total_loans > 0 else 0
        })


class BookRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for book ratings and reviews.
    """
    queryset = BookRating.objects.all()
    serializer_class = BookRatingSerializer
    permission_classes = [CanRateBooks]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = BookRatingFilter

    def get_queryset(self):
        """Filter queryset to show only user's own ratings or all if librarian."""
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return BookRating.objects.none()
        
        if self.request.user.is_authenticated and getattr(self.request.user, 'is_librarian', False):
            return BookRating.objects.all()
        elif self.request.user.is_authenticated:
            return BookRating.objects.filter(user=self.request.user)
        return BookRating.objects.none()

    def perform_create(self, serializer):
        """Set the user when creating a rating."""
        serializer.save(user=self.request.user)
