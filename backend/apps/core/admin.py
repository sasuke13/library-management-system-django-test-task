from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Book, Loan, BookRating


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for the custom User model.
    """
    list_display = ('email', 'username', 'full_name', 'is_librarian', 'is_active_member', 'active_loans_count', 'membership_date')
    list_filter = ('is_librarian', 'is_active_member', 'is_staff', 'is_active', 'membership_date')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Library Information', {
            'fields': ('phone_number', 'address', 'date_of_birth', 'is_librarian', 'is_active_member')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Library Information', {
            'fields': ('email', 'phone_number', 'address', 'date_of_birth', 'is_librarian', 'is_active_member')
        }),
    )
    
    def active_loans_count(self, obj):
        """Display the number of active loans for the user."""
        count = obj.active_loans_count
        if count > 0:
            return format_html('<span style="color: orange;">{}</span>', count)
        return count
    active_loans_count.short_description = 'Active Loans'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Book model.
    """
    list_display = ('title', 'author', 'isbn', 'genre', 'status', 'available_copies', 'total_copies', 'average_rating', 'times_borrowed')
    list_filter = ('genre', 'status', 'publication_date', 'language', 'date_added')
    search_fields = ('title', 'author', 'isbn', 'publisher')
    ordering = ('title', 'author')
    readonly_fields = ('date_added', 'last_updated', 'times_borrowed', 'average_rating', 'total_ratings')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'author', 'isbn', 'publisher', 'publication_date', 'genre')
        }),
        ('Physical Details', {
            'fields': ('pages', 'language', 'edition', 'description', 'cover_image')
        }),
        ('Library Management', {
            'fields': ('status', 'total_copies', 'available_copies', 'shelf_location', 'added_by')
        }),
        ('Statistics', {
            'fields': ('average_rating', 'total_ratings', 'times_borrowed', 'date_added', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set the added_by field to the current user when creating a new book."""
        if not change:  # Only set on creation
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Loan model.
    """
    list_display = ('user', 'book', 'loan_date', 'due_date', 'status', 'is_overdue', 'days_overdue', 'fine_amount')
    list_filter = ('status', 'loan_date', 'due_date', 'fine_paid')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'book__title', 'book__author')
    ordering = ('-loan_date',)
    readonly_fields = ('loan_date', 'created_at', 'updated_at', 'is_overdue', 'days_overdue')
    
    fieldsets = (
        ('Loan Information', {
            'fields': ('user', 'book', 'status')
        }),
        ('Dates', {
            'fields': ('loan_date', 'due_date', 'return_date')
        }),
        ('Management', {
            'fields': ('issued_by', 'returned_to', 'renewal_count', 'max_renewals')
        }),
        ('Financial', {
            'fields': ('fine_amount', 'fine_paid')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue(self, obj):
        """Display if the loan is overdue."""
        if obj.is_overdue:
            return format_html('<span style="color: red;">Yes</span>')
        return 'No'
    is_overdue.short_description = 'Overdue'
    is_overdue.boolean = True
    
    def days_overdue(self, obj):
        """Display the number of days overdue."""
        days = obj.days_overdue
        if days > 0:
            return format_html('<span style="color: red;">{}</span>', days)
        return 0
    days_overdue.short_description = 'Days Overdue'
    
    actions = ['mark_as_returned', 'calculate_fines']
    
    def mark_as_returned(self, request, queryset):
        """Mark selected loans as returned."""
        updated = queryset.filter(status='borrowed').update(status='returned')
        self.message_user(request, f'{updated} loans marked as returned.')
    mark_as_returned.short_description = 'Mark selected loans as returned'
    
    def calculate_fines(self, request, queryset):
        """Calculate fines for overdue loans."""
        count = 0
        for loan in queryset.filter(status='borrowed'):
            if loan.is_overdue:
                loan.calculate_fine()
                count += 1
        self.message_user(request, f'Fines calculated for {count} overdue loans.')
    calculate_fines.short_description = 'Calculate fines for overdue loans'


@admin.register(BookRating)
class BookRatingAdmin(admin.ModelAdmin):
    """
    Admin configuration for the BookRating model.
    """
    list_display = ('user', 'book', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'book__title', 'book__author')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Rating Information', {
            'fields': ('user', 'book', 'rating', 'review')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Customize admin site headers
admin.site.site_header = 'Library Management System'
admin.site.site_title = 'Library Admin'
admin.site.index_title = 'Welcome to Library Management System Administration'
