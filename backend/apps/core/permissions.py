from rest_framework import permissions


class IsLibrarianOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow librarians to edit objects.
    Regular users can only read.
    """
    def has_permission(self, request, view):
        # Read permissions for any user (including anonymous)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for librarians
        return request.user.is_authenticated and request.user.is_librarian


class IsOwnerOrLibrarian(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or librarians to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions for owner or librarian
        if hasattr(obj, 'user'):
            return obj.user == request.user or request.user.is_librarian
        
        return request.user.is_librarian


class IsOwnerOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user


class IsLibrarianOnly(permissions.BasePermission):
    """
    Custom permission to only allow librarians to access.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_librarian


class IsAuthenticatedOrCreateOnly(permissions.BasePermission):
    """
    Custom permission to allow unauthenticated users to create accounts,
    but require authentication for other operations.
    """
    def has_permission(self, request, view):
        if request.method == 'POST' and view.action == 'create':
            return True
        return request.user.is_authenticated


class CanBorrowBooks(permissions.BasePermission):
    """
    Custom permission to check if user can borrow books.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.method == 'POST':
            return request.user.can_borrow_books
        
        return True


class CanManageOwnLoans(permissions.BasePermission):
    """
    Custom permission for loan management - users can manage their own loans,
    librarians can manage all loans.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Librarians can manage all loans
        if request.user.is_librarian:
            return True
        
        # Users can only view their own loans
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user
        
        # Users can renew and return their own loans
        if view.action in ['renew', 'return_book']:
            return obj.user == request.user
        
        # Only librarians can create, update, delete loans
        return False


class CanRateBooks(permissions.BasePermission):
    """
    Custom permission for book ratings - users can only rate books they have borrowed.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Users can only manage their own ratings
        return obj.user == request.user