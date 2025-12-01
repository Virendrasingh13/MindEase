from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import (
    User, Client, Counsellor, Specialization, TherapyApproach, 
    Language, AgeGroup, Certification, EmailVerification, 
    BackgroundVerification, Review
)
from django.utils import timezone



# Custom User Admin
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_email_verified', 
                   'is_background_verified', 'is_active', 'date_joined')
    list_filter = ('role', 'is_email_verified', 'is_background_verified', 'is_active', 'gender')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'gender', 'profile_picture')}),
        ('Role & Status', {'fields': ('role', 'is_email_verified', 'is_background_verified', 'is_approved')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone', 'gender', 'role', 'password1', 'password2'),
        }),
    )



# Client Admin
class ClientAdmin(admin.ModelAdmin):
    list_display = ('get_email', 'get_full_name', 'age', 'primary_concern', 'is_active', 'created_at')
    list_filter = ('primary_concern', 'is_active', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'age_display' , 'terms_accepted_at')
    
    fieldsets = (
        ('User Information', {'fields': ('user', 'age_display')}),
        ('Client Details', {'fields': ('date_of_birth', 'primary_concern', 'other_primary_concern', 'about_me')}),
        ('Session Info', {'fields': ('last_session_date', 'total_sessions')}),
        ('Terms & Status', {'fields': ('terms_accepted', 'terms_accepted_at', 'is_active')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def age_display(self, obj):
        return obj.age()
    age_display.short_description = 'Age'



# Specialization Admin
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name', 'counsellor_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    
    def counsellor_count(self, obj):
        return obj.counsellors.count()
    counsellor_count.short_description = 'Counsellors'



# Therapy Approach Admin
class TherapyApproachAdmin(admin.ModelAdmin):
    list_display = ('name', 'counsellor_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    
    def counsellor_count(self, obj):
        return obj.counsellors.count()
    counsellor_count.short_description = 'Counsellors'



# Language Admin
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'counsellor_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    
    def counsellor_count(self, obj):
        return obj.counsellors.count()
    counsellor_count.short_description = 'Counsellors'



# Age Group Admin
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_age', 'max_age', 'counsellor_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    
    def counsellor_count(self, obj):
        return obj.counsellors.count()
    counsellor_count.short_description = 'Counsellors'



# Certification Inline for Counsellor
class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = ('name', 'organization', 'year_obtained', 'certificate_file', 'is_verified', 'verified_at')



# Function to send background verification emails
def send_background_verification_email(counsellor, status, notes=None):
    """Send email notification for background verification status"""
    try:
        user = counsellor.user
        
        if status == 'approved':
            subject = "Background Verification Approved - MindEase"
            html_message = render_to_string('accounts/background_approved_email.html', {
                'user': user,
                'counsellor': counsellor,
                'site_url': settings.FRONTEND_URL
            })
        else:  # rejected
            subject = "Background Verification Update - MindEase"
            html_message = render_to_string('accounts/background_rejected_email.html', {
                'user': user,
                'counsellor': counsellor,
                'notes': notes,
                'site_url': settings.FRONTEND_URL
            })
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        return True, f"Background verification {status} email sent to {user.email}"
        
    except Exception as e:
        return False, f"Error sending background verification email: {str(e)}"



# Custom admin actions for Background Verification
def approve_background_verification(modeladmin, request, queryset):
    """Admin action to approve background verification and send email"""
    for verification in queryset:
        if verification.status != 'approved':
            verification.status = 'approved'
            verification.verified_by = request.user
            verification.verified_at = timezone.now()
            verification.save()
            
            # Update counsellor and user status
            verification.counsellor.user.is_background_verified = True
            verification.counsellor.user.is_approved = True
            verification.counsellor.user.save()
            verification.counsellor.is_active = True
            verification.counsellor.save()
            
            # Send approval email
            success, message = send_background_verification_email(
                verification.counsellor, 
                'approved'
            )
            if success:
                messages.success(request, f"Approved and email sent: {verification.counsellor.user.email}")
            else:
                messages.warning(request, f"Approved but email failed: {message}")
        else:
            messages.info(request, f"Already approved: {verification.counsellor.user.email}")


approve_background_verification.short_description = "✅ Approve selected verifications and send approval email"



def reject_background_verification(modeladmin, request, queryset):
    """Admin action to reject background verification and send email"""
    for verification in queryset:
        if verification.status != 'rejected':
            verification.status = 'rejected'
            verification.verified_by = request.user
            verification.verified_at = timezone.now()
            verification.save()
            
            # Update counsellor and user status
            verification.counsellor.user.is_background_verified = False
            verification.counsellor.user.is_approved = False
            verification.counsellor.user.save()
            verification.counsellor.is_active = False
            verification.counsellor.save()
            
            # Send rejection email
            success, message = send_background_verification_email(
                verification.counsellor, 
                'rejected',
                verification.notes
            )
            if success:
                messages.success(request, f"Rejected and email sent: {verification.counsellor.user.email}")
            else:
                messages.warning(request, f"Rejected but email failed: {message}")
        else:
            messages.info(request, f"Already rejected: {verification.counsellor.user.email}")


reject_background_verification.short_description = "❌ Reject selected verifications and send rejection email"



def resend_verification_email(modeladmin, request, queryset):
    """Admin action to resend verification email for current status"""
    for verification in queryset:
        if verification.status in ['approved', 'rejected']:
            success, message = send_background_verification_email(
                verification.counsellor, 
                verification.status,
                verification.notes
            )
            if success:
                messages.success(request, f"Email resent: {verification.counsellor.user.email}")
            else:
                messages.error(request, f"Failed to resend email: {message}")
        else:
            messages.warning(request, f"Cannot resend email for status '{verification.status}': {verification.counsellor.user.email}")


resend_verification_email.short_description = "📧 Resend verification email for current status"



# Counsellor Admin
class CounsellorAdmin(admin.ModelAdmin):
    list_display = ('get_email', 'get_full_name', 'license_type', 'years_experience', 
                   'session_fee', 'is_active', 'is_background_verified', 'created_at')
    list_filter = ('license_type', 'highest_degree', 'is_active', 'is_featured', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'license_number', 'university')
    readonly_fields = ('created_at', 'updated_at', 'license_valid_display', 'experience_level_display' , 'terms_accepted_at' , 'consent_given_at')
    filter_horizontal = ('specializations', 'therapy_approaches', 'languages', 'age_groups')
    
    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Professional Information', {'fields': (
            'license_number', 'license_type', 'other_license_type', 'license_authority',
            'license_expiry', 'license_valid_display', 'years_experience', 'experience_level_display',
            'highest_degree', 'university', 'graduation_year'
        )}),
        ('Practice Details', {'fields': (
            'session_fee', 'google_meet_link', 'professional_experience', 'about_me'
        )}),
        ('Specializations & Approaches', {'fields': (
            'specializations', 'therapy_approaches'
        )}),
        ('Languages & Age Groups', {'fields': (
            'languages', 'age_groups'
        )}),
        ('Documents', {'fields': (
            'license_document', 'degree_certificate', 'id_proof'
        )}),
        ('Availability', {'fields': (
            'is_available', 'available_from', 'available_to'
        )}),
        ('Status & Metrics', {'fields': (
            'is_active', 'is_featured', 'rating', 'total_reviews', 'total_clients', 'total_sessions'
        )}),
        ('Terms & Consent', {'fields': (
            'terms_accepted', 'terms_accepted_at', 'consent_given', 'consent_given_at'
        )}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    inlines = [CertificationInline]
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def license_valid_display(self, obj):
        if obj.is_license_valid():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Expired</span>')
    license_valid_display.short_description = 'License Status'
    
    def experience_level_display(self, obj):
        return obj.experience_level()
    experience_level_display.short_description = 'Experience Level'
    
    def is_background_verified(self, obj):
        return obj.user.is_background_verified
    is_background_verified.short_description = 'Background Verified'
    is_background_verified.boolean = True



# Certification Admin
class CertificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'counsellor_name', 'organization', 'year_obtained', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'year_obtained', 'created_at')
    search_fields = ('name', 'organization', 'counsellor__user__email', 'counsellor__user__first_name')
    readonly_fields = ('created_at', 'updated_at')
    
    def counsellor_name(self, obj):
        return obj.counsellor.user.get_full_name()
    counsellor_name.short_description = 'Counsellor'
    counsellor_name.admin_order_field = 'counsellor__user__first_name'



# Email Verification Admin
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'token', 'created_at', 'expires_at', 'is_used', 'is_valid')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__email', 'token')
    readonly_fields = ('created_at', 'expires_at', 'is_valid_display')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.short_description = 'Is Valid'
    is_valid.boolean = True
    
    def is_valid_display(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Invalid/Used</span>')
    is_valid_display.short_description = 'Token Status'



# Background Verification Admin
class BackgroundVerificationAdmin(admin.ModelAdmin):
    list_display = ('counsellor_name', 'status', 'license_verified', 'degree_verified', 
                   'identity_verified', 'certifications_verified', 'is_complete', 'created_at')
    list_filter = ('status', 'license_verified', 'degree_verified', 'identity_verified', 
                  'certifications_verified', 'created_at')
    search_fields = ('counsellor__user__email', 'counsellor__user__first_name', 'counsellor__user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'is_complete_display', 'verified_by', 'verified_at')
    list_editable = ('status', 'license_verified', 'degree_verified', 'identity_verified', 'certifications_verified')
    
    actions = [approve_background_verification, reject_background_verification, resend_verification_email]
    
    fieldsets = (
        ('Counsellor Information', {'fields': ('counsellor',)}),
        ('Verification Status', {'fields': ('status', 'is_complete_display')}),
        ('Document Verification', {'fields': (
            'license_verified', 'degree_verified', 'identity_verified', 'certifications_verified'
        )}),
        ('Verification Details', {'fields': ('verified_by', 'verified_at', 'notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    def counsellor_name(self, obj):
        return obj.counsellor.user.get_full_name()
    counsellor_name.short_description = 'Counsellor'
    counsellor_name.admin_order_field = 'counsellor__user__first_name'
    
    def is_complete(self, obj):
        return obj.is_complete()
    is_complete.short_description = 'Complete'
    is_complete.boolean = True
    
    def is_complete_display(self, obj):
        if obj.is_complete():
            return format_html('<span style="color: green;">✓ Complete</span>')
        else:
            return format_html('<span style="color: orange;">⚠ Incomplete</span>')
    is_complete_display.short_description = 'Verification Progress'
    
    def email_sent_action(self, obj):
        """Display email action buttons"""
        if obj.status in ['approved', 'rejected']:
            return format_html(
                '<a class="button" href="{}">📧 Resend Email</a>',
                reverse('admin:resend_single_verification_email', args=[obj.id])
            )
        return "-"
    email_sent_action.short_description = 'Email Actions'
    email_sent_action.allow_tags = True
    
    def save_model(self, request, obj, form, change):
        # If status is changed to approved and verification is complete, update counsellor status
        if obj.status == 'approved' and obj.is_complete():
            obj.counsellor.user.is_background_verified = True
            obj.counsellor.user.is_approved = True
            obj.counsellor.user.background_verified_at = timezone.now()
            obj.counsellor.user.approved_at = timezone.now()
            obj.counsellor.user.save()
            obj.counsellor.is_active = True
            obj.counsellor.save()
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            
            # Send approval email
            success, message = send_background_verification_email(obj.counsellor, 'approved')
            if success:
                messages.success(request, f"Approval email sent to {obj.counsellor.user.email}")
            else:
                messages.warning(request, f"Approved but email failed: {message}")
                
        elif obj.status == 'rejected':
            obj.counsellor.user.is_background_verified = False
            obj.counsellor.user.is_approved = False
            obj.counsellor.user.save()
            obj.counsellor.is_active = False
            obj.counsellor.save()
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            
            # Send rejection email
            success, message = send_background_verification_email(obj.counsellor, 'rejected', obj.notes)
            if success:
                messages.success(request, f"Rejection email sent to {obj.counsellor.user.email}")
            else:
                messages.warning(request, f"Rejected but email failed: {message}")
        
        super().save_model(request, obj, form, change)


# Register all models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(Counsellor, CounsellorAdmin)
admin.site.register(Specialization, SpecializationAdmin)
admin.site.register(TherapyApproach, TherapyApproachAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(AgeGroup, AgeGroupAdmin)
admin.site.register(Certification, CertificationAdmin)
admin.site.register(EmailVerification, EmailVerificationAdmin)
admin.site.register(BackgroundVerification, BackgroundVerificationAdmin)


# Review Admin
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('counsellor_name', 'client_name', 'rating', 'title', 'is_verified', 'is_published', 'created_at')
    list_filter = ('rating', 'is_verified', 'is_published', 'created_at')
    search_fields = ('counsellor__user__first_name', 'counsellor__user__last_name', 
                    'client__user__first_name', 'client__user__last_name', 'title', 'content')
    list_editable = ('is_verified', 'is_published')
    readonly_fields = ('created_at', 'updated_at', 'helpful_count')
    
    fieldsets = (
        ('Review Information', {'fields': ('counsellor', 'client', 'rating', 'title', 'content')}),
        ('Status', {'fields': ('is_verified', 'is_published', 'helpful_count')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    def counsellor_name(self, obj):
        return obj.counsellor.user.get_full_name()
    counsellor_name.short_description = 'Counsellor'
    counsellor_name.admin_order_field = 'counsellor__user__first_name'
    
    def client_name(self, obj):
        return obj.client.user.get_full_name()
    client_name.short_description = 'Client'
    client_name.admin_order_field = 'client__user__first_name'
    
    actions = ['verify_reviews', 'unverify_reviews', 'publish_reviews', 'unpublish_reviews']
    
    def verify_reviews(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} review(s) marked as verified.')
    verify_reviews.short_description = "Mark selected reviews as verified"
    
    def unverify_reviews(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} review(s) marked as unverified.')
    unverify_reviews.short_description = "Mark selected reviews as unverified"
    
    def publish_reviews(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} review(s) published.')
    publish_reviews.short_description = "Publish selected reviews"
    
    def unpublish_reviews(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} review(s) unpublished.')
    unpublish_reviews.short_description = "Unpublish selected reviews"


admin.site.register(Review, ReviewAdmin)


# Admin site customization
admin.site.site_header = "MindEase Administration"
admin.site.site_title = "MindEase Admin Portal"
admin.site.index_title = "Welcome to MindEase Admin Portal"